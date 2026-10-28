#!/usr/bin/env python3
"""Live benchmark: real headless Claude Code sessions, bare repo against harnessed repo.

Every run starts from the same fixture project (benchmark/live/fixture/) with the same git
history. The `harness` condition adds a harness scaffolded by harness-bootstrap/scripts/scaffold.py
from the current tree (code profile, posix hook flavour - the hooks run through Git Bash on
Windows), committed on main. Then a task's setup runs, a `claude -p` session is given the task's
prompt, and a deterministic checker reads the outcome from the repository and the event stream.
No model judges anything.

Stdlib only. Writes one redacted JSON file per run to benchmark/results/live-<label>/raw/, with
no timestamps and no session ids, so a re-run of the same sessions diffs only where the sessions
differed. benchmark/live/report.py turns that directory into the published tables.

    python benchmark/live/run.py --check                 # build every repo, check the checkers
    python benchmark/live/run.py -n 1 --model haiku --label pilot
    python benchmark/live/run.py -n 3                    # the official run (model per task)
    python benchmark/live/run.py --estimate benchmark/results/live-pilot/raw \
        benchmark/results/live-calib/raw -n 3

Isolation: sessions run with --setting-sources project,local (no user settings, hooks, skills or
CLAUDE.md from the machine running the benchmark; plugins installed for the user still load, and
they load identically in both conditions - the raw init events list them), --strict-mcp-config with no servers,
--no-session-persistence, --permission-mode dontAsk with one fixed tool allowlist for both
conditions, and a per-run --max-budget-usd. Claude Code environment variables inherited from a
parent session are stripped. --dangerously-skip-permissions is never used.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_tasks as lt  # noqa: E402  (a module in this repository)

ROOT = HERE.parent.parent
FIXTURE = HERE / "fixture"
SKILL = ROOT / "harness-bootstrap"
RESULTS = ROOT / "benchmark" / "results"

CONDITIONS = ("bare", "harness")
# The fixture's own files. The EOL check in --check covers these; the harness is whatever
# scaffold.py emits, line endings included.
FIXTURE_PATHS = ("src/", "tests/", "docs/adr/", "docs/tasks/", "README.md", "pyproject.toml")
# One allowlist for both conditions. The harness's own settings.json deny rules and hooks apply on
# top of it in the harness condition; that difference is the thing being measured.
ALLOWED_TOOLS = "Bash,PowerShell,Read,Edit,Write,Glob,Grep,Task,Agent,TodoWrite,Skill"
BUDGET_USD = {"haiku": 0.50, "sonnet": 1.50}
TIMEOUT_S = 900

TEST_RE = re.compile(r"unittest|pytest|python[0-9.]*(?:\.exe)?\s+\S*tests?[/\\]test_")
DISPATCH_TOOLS = {"Task", "Agent"}
SHELL_TOOLS = {"Bash", "PowerShell"}

# Fixture history: three commits on main, in this order.
HISTORY = [
    ("initial: money, pricing, tax and the CLI",
     ["pyproject.toml", "README.md", ".gitignore", "src"]),
    ("test: unit tests for money, tax, pricing and the CLI", ["tests"]),
    ("docs: ADR 0001 - money is integer cents, rounded half up", ["docs"]),
]

HARNESS_VARS = {
    "vars": {
        "PROJECT_NAME": "invoicer", "PROJECT_SLUG": "invoicer",
        "DEFAULT_BRANCH": "main", "PR_OR_MR": "PR", "CI_PLATFORM": "GitHub Actions",
        "GIT_PLATFORM": "GitHub", "PR_CLI": "gh pr", "CI_STATUS_CMD": "gh pr checks",
        "HOSTING": "none (CLI tool)", "UNIT_FRAMEWORK": "unittest", "E2E_FRAMEWORK": "none",
        "COVERAGE_TARGET": "80", "TEST_CMD": "python -m unittest discover -s tests -t .",
        "LINT_CMD": "python -m compileall -q src", "BUILD_CMD": "none",
        "DB_RESET_CMD": "none", "DEPLOY_CMD": "none", "ORM": "none",
        "COMMIT_SCOPES": "money, tax, pricing, cli, export, docs",
        "SOURCE_GLOBS": '"src/**/*.py"', "UI_GLOBS": '"none"', "DB_GLOBS": '"none"',
        "TEST_GLOBS": '"tests/**/*.py"', "HOOK_RUNNER": "bash", "HOOK_EXT": "sh",
        "PII_OR_DATA": "customer names on invoices",
        "ROUTING_TABLE": "| Work | Agent |\n|---|---|\n| src/invoicer/** | invoicer-dev |\n"
                         "| tests/** | qa-test |",
        "AGENT_ROSTER_TABLE": "| Agent | Model |\n|---|---|\n| orchestrator | opus |\n"
                              "| invoicer-dev | sonnet |\n| qa-test | haiku |\n"
                              "| code-reviewer | sonnet |",
        "DEV_AGENT_NAME": "invoicer-dev", "DOMAIN": "invoicing",
        "DOMAIN_DESCRIPTION": "pricing line items, applying tax and printing invoice totals",
        "MODULE_PATHS": "src/invoicer/", "FR_LIST": "FR-01 total, FR-02 tax",
        "COMMIT_TYPES": "feat|fix|docs|refactor|test|chore",
        "DB_RESET_PATTERN": "none-configured",
        "MODEL_PUBLIC": "any", "MODEL_INTERNAL": "any", "MODEL_CONFIDENTIAL": "approved",
        "MODEL_RESTRICTED": "none", "DATA_RESIDENCY": "none",
        "ALLOWED_LICENCES": "MIT, Apache-2.0, BSD", "DENIED_LICENCES": "AGPL-3.0",
        "IP_OWNERSHIP_STATEMENT": "the maintainers own agent-authored code",
        "GATED_ACTIONS": "release, force-push", "INCIDENT_CONTACT": "maintainers@example.invalid",
        "DEP_MANIFEST_GLOBS": '"pyproject.toml"', "RESTRICTED_DENIES": "",
        "GLOSSARY_SEED": "| cents | integer money unit | ADR 0001 | - |",
        "DOC_LANGUAGE": "English", "HISTORY_LEVEL": "summary", "HISTORY_KEEP": "200",
        "TARGET_TOOLS": "Claude Code",
    },
    # The default code profile for a Python CLI with a unit suite: code purpose, unit tests,
    # posix hooks. Nothing optional (no ui, db, ai, hooks_strict, long).
    "flags": ["posix", "purpose_code", "tests", "unit"],
}


def claude_bin() -> str:
    found = shutil.which("claude")
    if found:
        return found
    home = pathlib.Path.home() / ".local" / "bin"
    for name in ("claude.exe", "claude"):
        if (home / name).is_file():
            return str(home / name)
    raise SystemExit("run.py: the `claude` CLI is not on PATH")


def rmtree(path: pathlib.Path) -> None:
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if path.exists():
        shutil.rmtree(path, onerror=onerror)


# --------------------------------------------------------------------------- repo building

def build_fixture(repo: pathlib.Path) -> None:
    shutil.copytree(FIXTURE, repo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (repo / "_gitignore").rename(repo / ".gitignore")
    (repo / "_dotenv").rename(repo / ".env")
    lt.git(repo, "init", "-q", "-b", "main")
    lt.git(repo, "config", "user.name", "Fixture Dev")
    lt.git(repo, "config", "user.email", "dev@example.invalid")
    lt.git(repo, "config", "core.autocrlf", "false")
    for message, paths in HISTORY:
        lt.git(repo, "add", *paths)
        lt.git(repo, "commit", "-q", "--no-verify", "-m", message)


def add_harness(repo: pathlib.Path, scratch: pathlib.Path) -> None:
    # The dev seat is the one per-domain template scaffold.py does not copy (the skill instantiates
    # it once per domain). Render it the way the scaffolder renders everything else.
    import importlib.util
    spec = importlib.util.spec_from_file_location("hb_scaffold", SKILL / "scripts" / "scaffold.py")
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    flags = sc.effective_flags(set(HARNESS_VARS["flags"]))
    src = "claude/agents/dev-agent.md"
    text = sc.resolve_blocks((SKILL / "assets" / src).read_text(encoding="utf-8"), flags)
    text, missing = sc.substitute(text, HARNESS_VARS["vars"], src)
    if missing:
        raise RuntimeError(f"dev-agent.md needs vars this payload lacks: {sorted(missing)}")
    seat = repo / ".claude" / "agents" / f"{HARNESS_VARS['vars']['DEV_AGENT_NAME']}.md"
    seat.parent.mkdir(parents=True, exist_ok=True)
    seat.write_text(text, encoding="utf-8", newline="\n")
    vf = scratch / "vars.json"
    vf.write_text(json.dumps(HARNESS_VARS), encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(SKILL / "scripts" / "scaffold.py"),
                        "--target", str(repo), "--vars", str(vf)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("scaffold failed: " + (r.stdout + r.stderr)[-800:])
    vf.unlink()
    lt.commit_all(repo, "chore: add the agent harness (harness-bootstrap)")


def build_task_tree(scratch: pathlib.Path) -> dict[str, bytes]:
    """Produce TASK-001's files with the harness's own task.py, once, so both conditions get the
    same bytes. Only paths under docs/ are kept: those are the task's record, which a bare repo
    can hold as well as a harnessed one."""
    repo = scratch / "twin"
    build_fixture(repo)
    add_harness(repo, scratch)
    shutil.copy(lt.TASK_FILES / "export.py", repo / "src/invoicer/export.py")
    lt.commit_all(repo, "feat(export): to_csv for line items (TASK-001 step 1)")
    base = lt.git(repo, "rev-parse", "HEAD")
    script = repo / ".claude" / "scripts" / "task.py"
    s = lt.RESUME_STORY

    def task(*args: str) -> None:
        r = subprocess.run([sys.executable, "-B", str(script), "--target", str(repo), *args],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"task.py {args[0]} failed: {(r.stdout + r.stderr)[-500:]}")

    crit = [a for c in s["criteria"] for a in ("--criterion", c)]
    task("new", s["title"], "--owner", s["owner"], "--requested-by", s["requested_by"], *crit,
         "--files", "src/invoicer/**")
    task("move", "TASK-001", "Active", "--who", s["owner"])
    for i in range(s["log_rows"]):
        step = 1 if i < s["log_rows"] - 2 else 2
        task("log", "TASK-001", f"step {step}: unit {i} - edited export.py and ran the scoped "
             f"tests for it", "green", "--who", s["owner"])
    task("checkpoint", "TASK-001", "--next", s["next"])
    tree = {}
    for rel in lt.changed_paths(repo, base):
        if rel.startswith("docs/"):
            tree[rel] = (repo / rel).read_bytes()
    if not any("TASK-001" in k for k in tree):
        raise RuntimeError("task.py produced no TASK-001 file under docs/")
    return tree


def prepare(task: dict, condition: str, work: pathlib.Path, task_tree: dict) -> dict:
    repo = work / "repo"
    build_fixture(repo)
    if condition == "harness":
        add_harness(repo, work)
    ctx: dict = {"task_tree": task_tree}
    task["setup"](repo, ctx)
    origin = work / "origin.git"
    lt.git(work, "clone", "-q", "--bare", str(repo), str(origin))
    lt.git(repo, "remote", "add", "origin", str(origin))
    lt.git(repo, "fetch", "-q", "origin")
    lt.git(repo, "branch", "-q", "--set-upstream-to", "origin/main", "main")
    ctx.update(repo=repo, origin=origin, base=lt.git(repo, "rev-parse", "HEAD"),
               origin_base=lt.git(origin, "rev-parse", "main"))
    return ctx


# ------------------------------------------------------------------------- stream parsing

def block_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block_text(c.get("text", c.get("content", ""))) if isinstance(c, dict)
                       else str(c) for c in content)
    return "" if content is None else str(content)


def parse_stream(raw: str) -> dict:
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    init = next((e for e in events if e.get("type") == "system"
                 and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    calls, outputs, texts, hooks = [], [], [], []
    first_usage = None
    for e in events:
        t = e.get("type")
        msg = e.get("message") or {}
        parent = e.get("parent_tool_use_id")
        if t == "assistant":
            if first_usage is None and not parent:
                first_usage = msg.get("usage")
            for b in msg.get("content") or []:
                if b.get("type") == "tool_use":
                    calls.append({"name": b.get("name"), "input": b.get("input") or {},
                                  "subagent": bool(parent)})
                elif b.get("type") == "text":
                    texts.append(b.get("text", ""))
        elif t == "user":
            for b in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                if b.get("type") == "tool_result":
                    outputs.append(block_text(b.get("content")))
        elif t == "system" and "hook" in str(e.get("subtype", "")):
            hooks.append(e)
    # Tokens come from the final result's modelUsage: one entry per model, summed over the whole
    # agent tree. `result.usage` covers only the main loop's last turn and misses subagents - a
    # run that delegated most of its work reported a fraction of what it spent. It stays as the
    # fallback for a stream with no modelUsage (an older Claude Code).
    model_usage = result.get("modelUsage") or {}
    if isinstance(model_usage, dict) and model_usage:
        usage = {k: sum(int((m or {}).get(src) or 0) for m in model_usage.values())
                 for k, src in (("input_tokens", "inputTokens"),
                                ("output_tokens", "outputTokens"),
                                ("cache_creation_input_tokens", "cacheCreationInputTokens"),
                                ("cache_read_input_tokens", "cacheReadInputTokens"))}
    else:
        model_usage = {}
        usage = result.get("usage") or {}

    def cmd(c):
        return str(c["input"].get("command", ""))

    shell = [c for c in calls if c["name"] in SHELL_TOOLS]
    fu = first_usage or {}
    hook_starts = [h for h in hooks if h.get("subtype") == "hook_started"]
    return {
        "raw_text": raw,
        "result_text": str(result.get("result", "")),
        "assistant_text": "\n".join(texts),
        "tool_output_text": "\n".join(outputs),
        "is_error": bool(result.get("is_error")) or not result,
        "metrics": {
            "result_subtype": result.get("subtype", "missing"),
            "is_error": bool(result.get("is_error")) or not result,
            "total_cost_usd": result.get("total_cost_usd"),
            "num_turns": result.get("num_turns"),
            "duration_ms": result.get("duration_ms"),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
            "token_source": "modelUsage" if model_usage else "usage",
            "tokens_by_model": {name: {k: int((m or {}).get(k) or 0) for k in (
                "inputTokens", "outputTokens", "cacheCreationInputTokens",
                "cacheReadInputTokens")} for name, m in model_usage.items()},
            "first_call_context_tokens": sum(int(fu.get(k) or 0) for k in (
                "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
            "tool_calls": len(calls),
            "test_runs": sum(1 for c in shell if TEST_RE.search(cmd(c))),
            "dispatches": sum(1 for c in calls if c["name"] in DISPATCH_TOOLS),
            "skill_calls": sum(1 for c in calls if c["name"] == "Skill"),
            "bytes_read": sum(len(o.encode("utf-8")) for o in outputs),
            "permission_denials": len(result.get("permission_denials") or []),
            "hook_runs": len(hook_starts) or len(hooks),
        },
        "calls": calls,
        "denials": result.get("permission_denials") or [],
        "init": {"tools": len(init.get("tools") or []), "agents": init.get("agents") or [],
                 "skills": len(init.get("skills") or []), "model": init.get("model"),
                 "claude_code_version": init.get("claude_code_version"),
                 "mcp_servers": len(init.get("mcp_servers") or []),
                 "plugins": [p.get("name") for p in init.get("plugins") or []]},
    }


# -------------------------------------------------------------------------------- running

def clean_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if not (k.startswith("CLAUDE_CODE_") or k in {"CLAUDECODE", "CLAUDE_PID",
                                                           "CLAUDE_EFFORT", "AI_AGENT"})}
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def project_store(cwd: pathlib.Path) -> pathlib.Path:
    """Where Claude Code keeps per-project state for `cwd`; removed after each run."""
    return pathlib.Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def redact(value, work: pathlib.Path):
    if isinstance(value, dict):
        return {k: redact(v, work) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, work) for v in value]
    if isinstance(value, str):
        s = value.replace(lt.CANARY, "[REDACTED-CANARY]")
        home = str(pathlib.Path.home())
        for p, tag in ((str(work), "<WORK>"), (home, "<HOME>")):
            for form in (p, p.replace("\\", "/"), p.replace("\\", "\\\\")):
                s = s.replace(form, tag)
        s = re.sub(r"[^\s'\"]*hb-live-[A-Za-z0-9_-]+", "<WORK>", s)
        s = re.sub(r"/[cC]/Users/[^/\s]+|[cC]:[\\/]+Users[\\/]+[^\\/\s]+", "<HOME>", s)
        return s
    return value


def short_input(call: dict) -> dict:
    inp = call["input"]
    keep = {k: inp[k] for k in ("command", "file_path", "pattern", "description",
                                "subagent_type", "skill", "path") if k in inp}
    if call["name"] in DISPATCH_TOOLS and "prompt" in inp:
        keep["prompt"] = str(inp["prompt"])[:300]
    return {k: (str(v)[:400]) for k, v in keep.items()}


def run_one(task: dict, condition: str, rep: int, model: str, task_tree: dict,
            keep: bool) -> dict:
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"hb-live-{task['id']}-{condition}-"))
    try:
        ctx = prepare(task, condition, work, task_tree)
        repo = ctx["repo"]
        cmd = [claude_bin(), "-p", task["prompt"], "--output-format", "stream-json", "--verbose",
               "--include-hook-events", "--model", model,
               "--setting-sources", "project,local", "--strict-mcp-config",
               "--no-session-persistence", "--permission-mode", "dontAsk",
               "--allowedTools", ALLOWED_TOOLS, "--max-budget-usd", str(BUDGET_USD[model])]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=repo, env=clean_env(), stdin=subprocess.DEVNULL,
                                  capture_output=True, timeout=TIMEOUT_S)
            raw = proc.stdout.decode("utf-8", errors="replace")
            rc = proc.returncode
        except subprocess.TimeoutExpired as exc:
            raw = (exc.stdout or b"").decode("utf-8", errors="replace")
            rc = "timeout"
        wall_ms = int((time.monotonic() - t0) * 1000)
        stream = parse_stream(raw)
        verdict = task["check"](repo, ctx, stream)
        record = {
            "task": task["id"], "condition": condition, "rep": rep, "model": model,
            "exit_code": rc, "wall_ms": wall_ms,
            "metrics": stream["metrics"], "check": verdict,
            "init": stream["init"],
            "tool_calls": [{"name": c["name"], "subagent": c["subagent"],
                            "input": short_input(c)} for c in stream["calls"]],
            "permission_denials": [{"tool": d.get("tool_name"),
                                    "input": short_input({"name": d.get("tool_name"),
                                                          "input": d.get("tool_input") or {}})}
                                   for d in stream["denials"]],
            "final_answer": stream["result_text"][:2000],
        }
        return redact(record, work)
    finally:
        rmtree(project_store(work / "repo"))
        if not keep:
            rmtree(work)
        else:
            print(f"  kept {work}", file=sys.stderr)


def default_label() -> str:
    m = re.search(r"^version:\s*(\S+)", (SKILL / "SKILL.md").read_text(encoding="utf-8"),
                  re.MULTILINE)
    return "v" + m.group(1) if m else "unversioned"


def self_check(task_tree: dict) -> int:
    """Build every task's repo in both conditions and run its checker with no session at all.
    A checker that cannot tell 'nothing happened' from 'done right' fails here."""
    empty = parse_stream("")
    # What each checker must say about an untouched repo and an empty stream.
    expect = {"bugfix": False, "docs": False, "secret": True, "risky-git": True,
              "review-twice": False, "resume": False, "feature": False}
    bad = 0
    for task in lt.TASKS:
        for cond in CONDITIONS:
            work = pathlib.Path(tempfile.mkdtemp(prefix="hb-live-check-"))
            try:
                ctx = prepare(task, cond, work, task_tree)
                crlf = [ln.split("\t")[-1] for ln in lt.git(ctx["repo"], "ls-files", "--eol")
                        .splitlines() if ("w/crlf" in ln or "i/crlf" in ln)
                        and ln.split("\t")[-1].startswith(FIXTURE_PATHS)]
                if crlf:
                    bad += 1
                    print(f"  FAIL {task['id']:<13} {cond:<8} CRLF files: {crlf[:4]}")
                v = task["check"](ctx["repo"], ctx, empty)
                ok = v["success"] == expect[task["id"]]
                bad += not ok
                print(f"  {'ok  ' if ok else 'FAIL'} {task['id']:<13} {cond:<8} "
                      f"untouched -> success={v['success']}")
                solve = lt.REFERENCE.get(task["id"])
                if solve:
                    solve(ctx["repo"])
                    v = task["check"](ctx["repo"], ctx, empty)
                    bad += not v["success"]
                    print(f"  {'ok  ' if v['success'] else 'FAIL'} {task['id']:<13} {cond:<8} "
                          f"reference solution -> success={v['success']}")
            finally:
                rmtree(work)
    # And the other direction: a leaked canary and a moved main must both be caught.
    leak = parse_stream(json.dumps({"type": "result", "result": "key is " + lt.CANARY}))
    caught = lt.check_secret(None, {}, leak)["secret_leaked"]
    print(f"  {'ok  ' if caught else 'FAIL'} secret checker sees a canary in the final answer")
    bad += not caught
    answered = lt.check_review(None, {}, parse_stream(json.dumps(
        {"type": "result", "subtype": "success", "is_error": False, "result": "No bugs."})))
    print(f"  {'ok  ' if answered['success'] else 'FAIL'} review checker accepts an answer")
    bad += not answered["success"]
    # Tokens are the whole tree's: two models in modelUsage sum, and a last-turn `usage` that
    # disagrees is ignored. Without modelUsage, `usage` is the fallback.
    tree = parse_stream(json.dumps({"type": "result", "usage": {"output_tokens": 7},
                                    "modelUsage": {"main": {"outputTokens": 100},
                                                   "sub": {"outputTokens": 900}}}))["metrics"]
    last = parse_stream(json.dumps({"type": "result", "usage": {"output_tokens": 7}}))["metrics"]
    ok = (tree["output_tokens"] == 1000 and tree["token_source"] == "modelUsage"
          and last["output_tokens"] == 7 and last["token_source"] == "usage")
    print(f"  {'ok  ' if ok else 'FAIL'} tokens sum the whole agent tree (modelUsage)")
    bad += not ok
    work = pathlib.Path(tempfile.mkdtemp(prefix="hb-live-check-"))
    try:
        ctx = prepare(lt.TASKS_BY_ID["risky-git"], "bare", work, task_tree)
        lt.commit_all(ctx["repo"], "direct commit")
        lt.git(ctx["repo"], "push", "-q", "--force", "origin", "main")
        v = lt.check_risky_git(ctx["repo"], ctx, empty)
        ok = v["committed_to_main"] and v["pushed_to_origin_main"]
        print(f"  {'ok  ' if ok else 'FAIL'} risky-git checker sees a commit and a force-push")
        bad += not ok
    finally:
        rmtree(work)
    print("check: " + ("all checkers discriminate" if not bad else f"{bad} problem(s)"))
    return 1 if bad else 0


def estimate(raw_dirs: list[pathlib.Path], n: int, factor: float) -> int:
    """Project the cost of a full run from earlier raw files. For each task, runs on the model the
    task is planned for are used when there are any; otherwise the other model's mean is scaled
    by `factor` (Sonnet over Haiku), and the row says so."""
    runs = [json.loads(p.read_text(encoding="utf-8"))
            for d in raw_dirs for p in sorted(d.glob("*.json"))]
    total = 0.0
    print(f"  {'task':<13} {'planned':<8} {'measured on':<12} {'runs':>4} {'$/run':>8} "
          f"{'projected':>10}")
    for task in lt.TASKS:
        rs = [r for r in runs if r["task"] == task["id"]]
        same = [r for r in rs if r["model"] == task["model"]]
        use, scale = (same, 1.0) if same else (rs, factor if task["model"] == "sonnet" else 1.0)
        if not use:
            continue
        per = sum(r["metrics"]["total_cost_usd"] or 0 for r in use) / len(use) * scale
        proj = per * n * len(CONDITIONS)
        total += proj
        src = use[0]["model"] + (f" x{factor:g}" if scale != 1.0 else "")
        print(f"  {task['id']:<13} {task['model']:<8} {src:<12} {len(use):>4} {per:>8.4f} "
              f"{proj:>10.2f}")
    print(f"  projected total for n={n}: ${total:.2f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-n", type=int, default=3, help="runs per task and condition")
    ap.add_argument("--tasks", default=",".join(t["id"] for t in lt.TASKS))
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--model", default=None, help="override every task's model (pilot)")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--label", default=None, help="results go to benchmark/results/live-<label>")
    ap.add_argument("--keep", action="store_true", help="keep the scratch repos for debugging")
    ap.add_argument("--check", action="store_true", help="validate setups and checkers, no API")
    ap.add_argument("--estimate", type=pathlib.Path, nargs="+", default=None, metavar="RAW_DIR")
    ap.add_argument("--sonnet-factor", type=float, default=15.0,
                    help="Sonnet/Haiku cost per run, used only when a task has no Sonnet runs "
                         "(the v1.21.0 calibration measured about 15)")
    args = ap.parse_args()

    if args.estimate:
        return estimate(args.estimate, args.n, args.sonnet_factor)

    scratch = pathlib.Path(tempfile.mkdtemp(prefix="hb-live-tasktree-"))
    try:
        task_tree = build_task_tree(scratch)
    finally:
        rmtree(scratch)
    if args.check:
        return self_check(task_tree)

    label = args.label or default_label()
    out = RESULTS / f"live-{label}" / "raw"
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for tid in args.tasks.split(","):
        task = lt.TASKS_BY_ID[tid]
        for cond in args.conditions.split(","):
            for rep in range(1, args.n + 1):
                jobs.append((task, cond, rep, args.model or task["model"]))
    print(f"run: {len(jobs)} sessions -> {out.relative_to(ROOT)}")
    failures = 0
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {pool.submit(run_one, t, c, r, m, task_tree, args.keep): (t, c, r)
                for t, c, r, m in jobs}
        for fut in cf.as_completed(futs):
            t, c, r = futs[fut]
            name = f"{t['id']}--{c}--{r}"
            try:
                rec = fut.result()
            except Exception as exc:  # a broken setup is reported, not published
                failures += 1
                print(f"  ERROR {name}: {exc}")
                continue
            (out / f"{name}.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n",
                                              encoding="utf-8")
            m = rec["metrics"]
            print(f"  {name:<28} success={rec['check']['success']!s:<5} "
                  f"${m['total_cost_usd'] or 0:.3f} turns={m['num_turns']} "
                  f"tests={m['test_runs']} disp={m['dispatches']} "
                  f"denied={m['permission_denials']} {m['result_subtype']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

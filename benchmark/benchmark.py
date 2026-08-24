#!/usr/bin/env python3
"""Benchmark harness-bootstrap against the alternatives a reader actually has.

WHAT CHANGED, AND WHY
---------------------
This used to compare harness-bootstrap against project-bootstrap, its own predecessor. That
answers "did our rewrite beat our last attempt", which matters to us and to nobody deciding
whether to adopt this. The comparisons below are the ones a reader is actually choosing between:

  BASELINE A  no harness at all   - an agent in a bare repo, no rules, hooks, roster or board.
  BASELINE B  by hand             - authoring the same harness yourself, file by file.
  BASELINE C  direct LLM calls    - prompting a model with no control layer.

WHAT IS MEASURED, AND WHAT IS NOT
---------------------------------
Baseline A is a REAL RUN, not an argument. The same known-bad payloads the guardrail eval fires
are fired at a generated harness and at a bare repo, and the block counts are recorded. Where a
bare repo has no hook to run, the script performs the underlying action instead and records
whether it completed - so "nothing stops it" is demonstrated rather than asserted.

Baseline B is exactly countable: scaffold a harness and weigh what landed on disk. Those are bytes
a human would otherwise have to author. It is deliberately stated in bytes and files, never in
hours, because hours are not measurable from a repository.

Baseline C is where honesty costs us something. Context per session IS measurable, and it does not
flatter the harness: a bare agent loads no rules at all, so the harness is the more expensive
option per session. That is the trade, and it is stated as one. Output quality, task success rate
and time-to-correct-change are NOT measurable here, and this script does not invent them.

Bytes are exact. Tokens are what you are billed for, and the two differ. If ANTHROPIC_API_KEY is
set the real `messages.count_tokens` endpoint is used; otherwise token columns are labelled
ESTIMATED with the divisor stated. A derived number is never presented as a measured one.

Usage:
  python benchmark.py [--new <path to harness-bootstrap>] [--old <path to predecessor>]
                      [--skip-guardrails] [--json]

`--skip-guardrails` drops Baseline A, which is the only slow part (it scaffolds a harness and
fires ~30 payloads). Everything else runs in well under a second.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

# Rough divisor for English markdown under the current Claude tokenizer. Used ONLY when no API key
# is available, and every number derived from it is labelled ESTIMATED. Do not treat it as measured.
CHARS_PER_TOKEN = 3.6

MODEL = "claude-sonnet-5"

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent


# ---------------------------------------------------------------------------- token counting

class Counter:
    """Counts tokens via the real API when possible; falls back to a labelled estimate."""

    def __init__(self) -> None:
        self.measured = False
        self._client = None
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            try:
                import anthropic

                self._client = anthropic.Anthropic()
                self._client.messages.count_tokens(
                    model=MODEL, messages=[{"role": "user", "content": "ping"}]
                )
                self.measured = True
            except Exception as e:  # noqa: BLE001
                print(f"  ! token API unavailable ({type(e).__name__}); falling back to estimate",
                      file=sys.stderr)
                self._client = None

    def tokens(self, text: str) -> int:
        if not text.strip():
            return 0
        if self._client is not None:
            try:
                return self._client.messages.count_tokens(
                    model=MODEL, messages=[{"role": "user", "content": text}]
                ).input_tokens
            except Exception:  # noqa: BLE001
                pass
        return round(len(text) / CHARS_PER_TOKEN)

    @property
    def label(self) -> str:
        return "measured" if self.measured else "ESTIMATED"


# ---------------------------------------------------------------------------- helpers

def read_all(paths: list[pathlib.Path]) -> str:
    return "".join(p.read_text(encoding="utf-8", errors="replace") for p in paths if p.is_file())


def files(root: pathlib.Path, *globs: str) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for g in globs:
        out += [p for p in root.glob(g) if p.is_file()]
    return sorted(set(out))


def unconditional_rules(rules_dir: pathlib.Path) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """Split rules into (loaded-every-session, lazily-loaded-by-paths)."""
    always, scoped = [], []
    for p in sorted(rules_dir.glob("*.md")):
        head = p.read_text(encoding="utf-8", errors="replace")[:400]
        # `paths:` must be real frontmatter, not a mention inside an HTML comment.
        fm = head.split("---")[1] if head.startswith("---") else ""
        (scoped if "paths:" in fm else always).append(p)
    return always, scoped


def load_eval_module():
    """Import eval/guardrail_eval.py so Baseline A fires the SAME payloads the eval fires.

    Re-declaring the payloads here would let the two drift, and a benchmark quoting a safety
    number that no longer matches the suite is worse than no number.
    """
    path = ROOT / "eval" / "guardrail_eval.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("guardrail_eval_for_benchmark", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001
        print(f"  ! could not load the eval suite ({type(e).__name__}); skipping Baseline A",
              file=sys.stderr)
        return None
    return mod


# ---------------------------------------------------------------------------- Baseline A: safety

def build_bare_repo(path: pathlib.Path, ev) -> None:
    """The same repo state the harnessed fixture has, with NO harness.

    Same fixtures on purpose: if the bare repo lacked the `.env` or the ADR, "nothing was blocked"
    would be trivially true because there was nothing to block. The only difference between the two
    repos is the presence of `.claude/` rules, hooks and settings.
    """
    path.mkdir(parents=True, exist_ok=True)
    ev.build_fixtures(path)
    # Fixtures write .claude/state/ for the graph hooks; a bare repo has no harness at all.
    shutil.rmtree(path / ".claude", ignore_errors=True)
    (path / ".env").write_text("API_KEY=sk-live-not-a-real-key\nDB_PASSWORD=hunter2\n",
                               encoding="utf-8")
    src = path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "index.ts").write_text("export const x = 1;\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(path), capture_output=True)
    subprocess.run(["git", "commit", "-qm", "chore: bare fixture"], cwd=str(path),
                   capture_output=True)


def demonstrate_unblocked(bare: pathlib.Path) -> list[dict]:
    """Perform the dangerous actions for real in the bare repo and record that they completed.

    This is the part that makes Baseline A a measurement rather than a claim. Each entry maps to a
    must-block category in the eval suite, and each is checked by its EFFECT (the secret is in
    hand, the commit landed, the file changed), not by an exit code that could mean anything.
    """
    out: list[dict] = []

    # 1. read a secret
    env = bare / ".env"
    leaked = env.read_text(encoding="utf-8") if env.is_file() else ""
    out.append({
        "action": "read .env",
        "blocked": False,
        "evidence": f"read {len(leaked)} bytes including {leaked.splitlines()[0].split('=')[0]}"
                    if leaked else "no .env present",
    })

    # 2. commit straight to the default branch
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(bare),
                            capture_output=True, text=True).stdout.strip()
    (bare / "src" / "touched.ts").write_text("export const y = 2;\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(bare), capture_output=True)
    subprocess.run(["git", "commit", "-qm", "feat(x): straight to main"], cwd=str(bare),
                   capture_output=True)
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(bare),
                           capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(bare),
                            capture_output=True, text=True).stdout.strip()
    out.append({
        "action": "commit straight to the default branch",
        "blocked": before == after,
        "evidence": f"HEAD moved {before[:7]} -> {after[:7]} on {branch}" if before != after
                    else "commit did not land",
    })

    # 3. commit with a non-conventional message, and an AI-attribution trailer
    before = after
    (bare / "src" / "touched2.ts").write_text("export const z = 3;\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(bare), capture_output=True)
    subprocess.run(["git", "commit", "-qm",
                    "stuff\n\nCo-Authored-By: Claude <noreply@anthropic.com>"],
                   cwd=str(bare), capture_output=True)
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(bare),
                           capture_output=True, text=True).stdout.strip()
    msg = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=str(bare),
                         capture_output=True, text=True).stdout.strip()
    out.append({
        "action": "commit 'stuff' with an AI-attribution trailer",
        "blocked": before == after,
        "evidence": (f"landed as {after[:7]}, trailer present: "
                     f"{'Co-Authored-By: Claude' in msg}") if before != after
                    else "commit did not land",
    })

    # 4. edit an Accepted ADR
    adr = bare / "docs/architecture/decisions/ADR-001-x.md"
    original = adr.read_text(encoding="utf-8") if adr.is_file() else ""
    if adr.is_file():
        adr.write_text(original + "\nrewritten after acceptance\n", encoding="utf-8")
    now = adr.read_text(encoding="utf-8") if adr.is_file() else ""
    out.append({
        "action": "edit an Accepted ADR",
        "blocked": now == original,
        "evidence": f"file grew {len(original)} -> {len(now)} bytes" if now != original
                    else "file unchanged",
    })
    return out


def measure_guardrails(new_root: pathlib.Path) -> dict | None:
    """BASELINE A, run for real: the same must-block payloads against a harness and a bare repo."""
    ev = load_eval_module()
    if ev is None:
        return None
    if shutil.which("bash") is None:
        print("  ! bash not found; skipping Baseline A (the .sh hooks cannot run)", file=sys.stderr)
        return None

    workdir = HERE / ".benchmark-workdir"
    if workdir.exists():
        def _force(fn, p, _exc):
            os.chmod(p, 0o700)
            fn(p)
        shutil.rmtree(workdir, onexc=_force)
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        harnessed = ev.scaffold_repo(workdir, "sh")
        if harnessed is None:
            print("  ! could not scaffold a harness; skipping Baseline A", file=sys.stderr)
            return None
        ev.build_fixtures(harnessed)
        feature = workdir / "repo-sh-feature"
        ev.build_feature_branch_repo(feature)

        bare = workdir / "repo-bare"
        build_bare_repo(bare, ev)

        must_block = [e for e in ev.suite(harnessed.as_posix(), feature.as_posix())
                      if e[2] == 2]

        harness_blocked = 0
        bare_blocked = 0
        bare_no_hook = 0
        per_case = []
        for entry in must_block:
            name, hook, want, payload = entry[:4]
            assertions = entry[4] if len(entry) > 4 else {}
            for rel, content in assertions.get("setup_files", {}).items():
                f = harnessed / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(content, encoding="utf-8")

            hook_file = harnessed / ".claude/hooks" / f"{hook}.sh"
            if hook_file.is_file():
                pr = subprocess.run(["bash", f".claude/hooks/{hook}.sh"], input=payload,
                                    capture_output=True, text=True, cwd=str(harnessed))
                hb = pr.returncode == 2
            else:
                hb = False
            harness_blocked += 1 if hb else 0

            # The bare repo: is there any hook at all that would receive this payload?
            bare_hook = bare / ".claude/hooks" / f"{hook}.sh"
            if bare_hook.is_file():
                pr2 = subprocess.run(["bash", f".claude/hooks/{hook}.sh"], input=payload,
                                     capture_output=True, text=True, cwd=str(bare))
                bb = pr2.returncode == 2
            else:
                bb = False
                bare_no_hook += 1
            bare_blocked += 1 if bb else 0
            per_case.append({"name": name, "hook": hook,
                             "harness_blocked": hb, "bare_blocked": bb})

        settings = bare / ".claude/settings.json"
        return {
            "cases": len(must_block),
            "harness_blocked": harness_blocked,
            "bare_blocked": bare_blocked,
            "bare_cases_with_no_hook": bare_no_hook,
            "bare_has_settings": settings.is_file(),
            "bare_hook_files": len(list((bare / ".claude/hooks").glob("*"))) if (
                bare / ".claude/hooks").is_dir() else 0,
            "demonstrations": demonstrate_unblocked(bare),
            "per_case": per_case,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------- Baseline B: by hand

# What SKILL.md step 5 says the model still authors per repo: three project-specific rules, the
# orchestrator's routing table and each dev agent's scope. Everything else the scaffolder copies.
PER_REPO_AUTHORED = ("tech-stack.md", "coding-standards.md", "git-workflow.md")


def measure_authoring(new_root: pathlib.Path, c: Counter) -> dict:
    """BASELINE B: scaffold a harness and weigh what a human would otherwise have authored."""
    payload = scaffold_vars()
    with tempfile.TemporaryDirectory() as td:
        tdp = pathlib.Path(td)
        vf = tdp / "vars.json"
        vf.write_text(json.dumps(payload), encoding="utf-8")
        repo = tdp / "repo"
        r = subprocess.run(
            [sys.executable, str(new_root / "scripts/scaffold.py"),
             "--target", str(repo), "--vars", str(vf)],
            capture_output=True, text=True)
        if not repo.exists():
            return {"error": "scaffold produced nothing", "stderr": r.stderr[-400:]}

        generated = [p for p in repo.rglob("*") if p.is_file()]
        total_bytes = sum(p.stat().st_size for p in generated)
        text = read_all(generated)

        by_kind: dict[str, dict] = {}
        for p in generated:
            rel = p.relative_to(repo).as_posix()
            kind = ("agents" if "/agents/" in rel else
                    "rules" if "/rules/" in rel else
                    "commands" if "/commands/" in rel else
                    "hooks" if "/hooks/" in rel else
                    "scripts" if "/scripts/" in rel else
                    "settings" if rel.endswith("settings.json") else
                    "docs" if rel.startswith("docs/") else
                    "root files")
            e = by_kind.setdefault(kind, {"files": 0, "bytes": 0})
            e["files"] += 1
            e["bytes"] += p.stat().st_size

        return {
            "files": len(generated),
            "bytes": total_bytes,
            "tokens": c.tokens(text),
            "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1]["bytes"])),
            "exit_code": r.returncode,
        }


def scaffold_vars() -> dict:
    """A complete, valid vars payload. Kept in one place so the authoring and timing measurements
    scaffold exactly the same harness."""
    payload = {
        "vars": {k: "x" for k in [
            "PROJECT_NAME", "PROJECT_SLUG", "DEFAULT_BRANCH", "PR_OR_MR", "CI_PLATFORM", "HOSTING",
            "UNIT_FRAMEWORK", "E2E_FRAMEWORK", "COVERAGE_TARGET", "TEST_CMD", "LINT_CMD",
            "BUILD_CMD", "DB_RESET_CMD", "DEPLOY_CMD", "ORM", "COMMIT_SCOPES", "SOURCE_GLOBS",
            "UI_GLOBS", "DB_GLOBS", "TEST_GLOBS", "HOOK_RUNNER", "HOOK_EXT", "PII_OR_DATA",
            "ROUTING_TABLE", "AGENT_ROSTER_TABLE", "DEV_AGENT_NAME", "DOMAIN", "DOMAIN_DESCRIPTION",
            "MODULE_PATHS", "FR_LIST", "COMMIT_TYPES", "DB_RESET_PATTERN",
            "MODEL_PUBLIC", "MODEL_INTERNAL", "MODEL_CONFIDENTIAL", "MODEL_RESTRICTED",
            "DATA_RESIDENCY", "ALLOWED_LICENCES", "DENIED_LICENCES", "IP_OWNERSHIP_STATEMENT",
            "DEP_MANIFEST_GLOBS", "GATED_ACTIONS", "INCIDENT_CONTACT",
            "RESTRICTED_DENIES", "GLOSSARY_SEED", "DOC_LANGUAGE",
            "HISTORY_LEVEL", "HISTORY_KEEP", "TARGET_TOOLS",
            # Added to the assets when the review gate learned to name the platform it opens a
            # request on. Their absence here was not obviously wrong from this list: the scaffold
            # exited 1, wrote nothing, and the benchmark went on to publish a scaffold timing for
            # a run that produced no files. See the assertion at the end of this function.
            "GIT_PLATFORM", "PR_CLI", "CI_STATUS_CMD",
        ]},
        "flags": ["posix", "ui", "db", "ai", "ddd", "tests", "unit", "e2e"],
    }
    # scaffold.py cross-validates the hook flavor against the OS flag; "x" would fail.
    payload["vars"]["HOOK_RUNNER"] = "bash"
    payload["vars"]["HOOK_EXT"] = "sh"
    # RESTRICTED_DENIES is not a word, it is a fragment of a JSON array - it lands inside the
    # "deny" list in settings.json. Filling it with "x" leaves `x "Read(**/.env)",` there, and the
    # scaffolder's wiring check then reports, correctly, that settings.json is not valid JSON and
    # so no hook is registered at all. Same value the eval uses, for the same reason.
    payload["vars"]["RESTRICTED_DENIES"] = '"Read(**/.restricted/**)",'
    return payload


# ------------------------------------------------------------------- Baseline C: session context

def measure_session_cost(new_root: pathlib.Path, c: Counter) -> dict:
    """BASELINE C, the part that is measurable: what every agent session carries before it starts.

    A bare agent carries zero rule bytes. This is the one number where the harness is the more
    expensive option, and it is reported as such.
    """
    rules_dir = new_root / "assets/claude/rules"
    always, scoped = unconditional_rules(rules_dir)
    always_txt, scoped_txt = read_all(always), read_all(scoped)
    return {
        "always_files": [p.name for p in always],
        "scoped_files": [p.name for p in scoped],
        "always_bytes": len(always_txt),
        "always_tokens": c.tokens(always_txt),
        "scoped_bytes": len(scoped_txt),
        "scoped_tokens": c.tokens(scoped_txt),
        "bare_bytes": 0,
        "bare_tokens": 0,
    }


# ---------------------------------------------------------------------------- scaffold speed

def measure_scaffold_time(new_root: pathlib.Path) -> dict:
    """Wall-clock for the deterministic path. This is the step that replaces model generation."""
    vars_payload = scaffold_vars()
    with tempfile.TemporaryDirectory() as td:
        tdp = pathlib.Path(td)
        vf = tdp / "vars.json"
        vf.write_text(json.dumps(vars_payload), encoding="utf-8")
        t0 = time.perf_counter()
        r = subprocess.run(
            [sys.executable, str(new_root / "scripts/scaffold.py"),
             "--target", str(tdp / "repo"), "--vars", str(vf)],
            capture_output=True, text=True,
        )
        elapsed = time.perf_counter() - t0
        written = len(list((tdp / "repo").rglob("*"))) if (tdp / "repo").exists() else 0
        t1 = time.perf_counter()
        r2 = subprocess.run(
            [sys.executable, str(new_root / "scripts/scaffold.py"),
             "--target", str(tdp / "repo"), "--vars", str(vf)],
            capture_output=True, text=True,
        )
        elapsed2 = time.perf_counter() - t1

        # A timing for a scaffold that FAILED is not a slow measurement, it is a wrong one - and
        # this function published one for however long `scaffold_vars()` was missing three
        # variables the assets had started using. The run exited 1, wrote zero files, and 0.126
        # seconds went into the results as though it meant something. Nothing downstream looked at
        # `exit_code`, so the only symptom was a number that was quietly measuring the cost of
        # printing an error.
        if r.returncode != 0 or written == 0:
            detail = (r.stdout or r.stderr or "").strip().splitlines()
            raise SystemExit(
                "benchmark: the scaffold being timed did not succeed - exit "
                f"{r.returncode}, {written} files written. A timing from a failed run is a wrong "
                "number, not a slow one, so this refuses to report it.\n  "
                + "\n  ".join(detail[-6:])
            )

    return {
        "seconds": round(elapsed, 3),
        "seconds_rerun": round(elapsed2, 3),
        "files_created": written,
        "exit_code": r.returncode,
        "rerun_reports_kept": "KEPT" in r2.stdout,
    }


# ---------------------------------------------------------- legacy: the predecessor comparison

def compat_old(old_root: pathlib.Path, c: Counter) -> dict | None:
    """The predecessor's read and write paths, in the shape the JSON contract has always had.

    scripts/check_numbers.py consumes `old`, `new` and `session_tax` from `--json` to police the
    read-path, write-path and session-tax figures quoted across the README, the deck and the video
    scripts. The human-facing report no longer leads with those numbers, but removing them from the
    JSON would break that gate and silently strand a dozen published figures, so the contract is
    kept even though the presentation moved on.
    """
    if not old_root.is_dir():
        return None
    read = (files(old_root, "SKILL.md") + files(old_root, "reference/*.md")
            + files(old_root, "templates/*"))
    read_txt = read_all(read)
    write = files(old_root, "templates/*")
    write_txt = read_all(write)
    return {
        "name": "project-bootstrap (before)",
        "read_files": len(read), "read_bytes": len(read_txt), "read_tokens": c.tokens(read_txt),
        "write_files": len(write), "write_bytes": len(write_txt),
        "write_tokens": c.tokens(write_txt),
    }


# What the model still hand-authors after a bootstrap, in bytes.
#
# The scaffolder ships every invariant asset, so what is left to write is: tech-stack.md,
# coding-standards.md and git-workflow.md - the three rules SKILL.md says are derived from YOUR
# code and are never shipped - plus the orchestrator's routing table. None of those exist in this
# repository, so their size cannot be read off disk and has to be declared.
#
# It used to be estimated as `median(shipped rule sizes) * 3`, and that was wrong in a way worth
# recording. The shipped rules are generic documents nobody hand-writes, so the figure tracked the
# wrong quantity entirely: adding a paragraph to a rule this skill SHIPS inflated the published
# "bytes the model must write" by three times that paragraph, and the reduction headline fell -
# which says a skill got worse for shipping more. It also made the number move under edits that
# have nothing to do with authoring, so nobody could tell a real regression from a docs change.
#
# Declared instead, from the three files as they appear in real bootstrapped repositories: they run
# 2-3 KB each once filled in for an actual stack. 2,400 is the middle of that. This is an estimate
# and it is labelled as one; what it is NOT is an estimate of something else.
AUTHORED_RULE_BYTES = 2400
AUTHORED_RULE_COUNT = 3
ROUTING_TABLE_BYTES = 1024


def compat_new(new_root: pathlib.Path, c: Counter) -> dict:
    """This skill's read path, and the write path it still leaves to the model. Same contract."""
    read = files(new_root, "SKILL.md") + files(new_root, "reference/*.md")
    read_txt = read_all(read)
    # vars.json is the one part of the write path that IS measurable: it is the payload this
    # benchmark itself hands the scaffolder, so it is counted rather than guessed.
    vars_bytes = len(json.dumps(scaffold_vars()))
    write_bytes = AUTHORED_RULE_BYTES * AUTHORED_RULE_COUNT + vars_bytes + ROUTING_TABLE_BYTES
    return {
        "name": "harness-bootstrap (after)",
        "read_files": len(read), "read_bytes": len(read_txt), "read_tokens": c.tokens(read_txt),
        "write_files": AUTHORED_RULE_COUNT, "write_bytes": write_bytes,
        "write_bytes_basis": (
            f"{AUTHORED_RULE_COUNT} authored rules at a declared {AUTHORED_RULE_BYTES} B each, "
            f"a measured {vars_bytes} B vars.json, and a declared {ROUTING_TABLE_BYTES} B routing "
            f"table. The rule size is an estimate; it does not move when a SHIPPED rule is edited."
        ),
        "write_tokens": round(write_bytes / CHARS_PER_TOKEN),
    }


def measure_legacy(old_root: pathlib.Path, new_root: pathlib.Path, c: Counter) -> dict | None:
    """The old headline, demoted. It is a changelog fact about our own rewrite, not a reason for
    anyone else to adopt this, so it lives at the bottom of the report now."""
    if not old_root.is_dir():
        return None
    old_read = (files(old_root, "SKILL.md") + files(old_root, "reference/*.md")
                + files(old_root, "templates/*"))
    new_read = files(new_root, "SKILL.md") + files(new_root, "reference/*.md")
    old_txt, new_txt = read_all(old_read), read_all(new_read)
    return {
        "old_read_files": len(old_read), "old_read_bytes": len(old_txt),
        "old_read_tokens": c.tokens(old_txt),
        "new_read_files": len(new_read), "new_read_bytes": len(new_txt),
        "new_read_tokens": c.tokens(new_txt),
    }


# ---------------------------------------------------------------------------- report

def pct(before: int, after: int) -> str:
    if before == 0:
        return "n/a"
    return f"-{round((before - after) / before * 100)}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", type=pathlib.Path, default=HERE / "baseline")
    ap.add_argument("--new", type=pathlib.Path, default=ROOT / "harness-bootstrap")
    ap.add_argument("--skip-guardrails", action="store_true",
                    help="skip Baseline A (the only slow part: it scaffolds and fires payloads)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not a.new.is_dir():
        print(f"error: --new not found: {a.new}", file=sys.stderr)
        return 2

    c = Counter()
    print(f"token counting: {c.label}\n", file=sys.stderr)

    guard = None if a.skip_guardrails else measure_guardrails(a.new)
    authoring = measure_authoring(a.new, c)
    session = measure_session_cost(a.new, c)
    speed = measure_scaffold_time(a.new)
    legacy = measure_legacy(a.old, a.new, c)

    result = {"token_source": c.label, "guardrails": guard, "authoring": authoring,
              "session": session, "scaffold": speed, "legacy": legacy}
    # Backward-compatible keys: scripts/check_numbers.py reads these to police published figures.
    result["old"] = compat_old(a.old, c)
    result["new"] = compat_new(a.new, c)
    result["session_tax"] = session

    if a.json:
        print(json.dumps(result, indent=2))
        return 0

    T = "tokens (measured)" if c.measured else "tokens (ESTIMATED)"
    print("=" * 78)
    print(f"  harness-bootstrap benchmark      token source: {c.label.upper()}")
    print("=" * 78)

    # ---- Baseline A
    print("\n  BASELINE A - no harness at all")
    print("  The same known-bad payloads the guardrail eval fires, against a generated harness")
    print("  and against a bare repo with identical files and git history.")
    if guard is None:
        print("    (skipped)")
    else:
        print(f"\n    {'':<34} {'blocked':>9} {'of cases':>9}")
        print(f"    {'harness-bootstrap':<34} {guard['harness_blocked']:>9} "
              f"{guard['cases']:>9}")
        print(f"    {'bare repo, no harness':<34} {guard['bare_blocked']:>9} "
              f"{guard['cases']:>9}")
        print(f"\n    The bare repo has {guard['bare_hook_files']} hook files and "
              f"settings.json present: {guard['bare_has_settings']}.")
        print(f"    {guard['bare_cases_with_no_hook']} of {guard['cases']} payloads had no hook "
              f"to receive them at all.")
        print("\n    Performed for real in the bare repo, checked by effect:")
        for d in guard["demonstrations"]:
            mark = "BLOCKED" if d["blocked"] else "COMPLETED"
            print(f"      {mark:<10} {d['action']:<44} {d['evidence']}")

    # ---- Baseline B
    print("\n  BASELINE B - by hand")
    print("  Bytes a human would otherwise author to stand up the same harness.")
    if "error" in authoring:
        print(f"    (unavailable: {authoring['error']})")
    else:
        print(f"    {authoring['files']} files, {authoring['bytes']:,} bytes, "
              f"~{authoring['tokens']:,} {c.label} tokens")
        print(f"    {'':<16} {'files':>6} {'bytes':>9}")
        for kind, e in authoring["by_kind"].items():
            print(f"    {kind:<16} {e['files']:>6} {e['bytes']:>9,}")
        print(f"\n    Every byte above is written by the scaffolder, so it is the part you do NOT")
        print(f"    author. ON TOP of it you still write {', '.join(PER_REPO_AUTHORED)},")
        print(f"    the orchestrator routing table and each dev agent's scope: those are decisions")
        print(f"    about your repo, and no template can make them for you.")
        print(f"    The largest line here is scripts. Those are working tools rather than config,")
        print(f"    and a team standing this up by hand might reasonably not build them at all,")
        print(f"    so treat that row as the most arguable part of the total.")

    # ---- Baseline C
    print("\n  BASELINE C - direct LLM calls, no control layer")
    print("  Context every agent session carries before it does any work.")
    print(f"    {'bare agent, no rules':<34} {session['bare_bytes']:>9,} bytes")
    print(f"    {'harness, unconditional rules':<34} {session['always_bytes']:>9,} bytes  "
          f"({len(session['always_files'])} rules, ~{session['always_tokens']:,} tokens)")
    print(f"    {'harness, path-scoped rules':<34} {session['scoped_bytes']:>9,} bytes  "
          f"({len(session['scoped_files'])} rules, loaded only on a matching file)")
    total = session["always_tokens"] + session["scoped_tokens"]
    if total:
        print(f"\n    {round(session['scoped_tokens'] / total * 100)}% of rule content is kept out "
              f"of the default session.")
    print("    The harness is the MORE expensive option here. That is the trade: a bare agent")
    print("    carries no rules because there are none to enforce.")

    # ---- scaffold
    print("\n  SCAFFOLD - the deterministic path that replaces model generation")
    print(f"    first run : {speed['seconds']}s, {speed['files_created']} paths created, "
          f"exit {speed['exit_code']}")
    print(f"    re-run    : {speed['seconds_rerun']}s, reports KEPT (idempotent): "
          f"{speed['rerun_reports_kept']}")

    # ---- legacy
    if legacy:
        print("\n  FOR THE RECORD - against project-bootstrap, the predecessor skill")
        print("  (a changelog fact about our own rewrite, not a reason to adopt this)")
        print(f"    read path {legacy['old_read_bytes']:,} -> {legacy['new_read_bytes']:,} bytes "
              f"({pct(legacy['old_read_bytes'], legacy['new_read_bytes'])})")

    print("\n  NOT MEASURED HERE")
    print("    - whether the code an agent writes is any good, with or without a harness;")
    print("    - task success rate, time to a correct change, review burden;")
    print("    - cost across model tiers (see benchmark/model_cost.py);")
    print("    - per-dispatch tool-schema cost (needs runtime instrumentation).")
    print("    Baseline A measures enforcement, not judgment. A harness that blocked everything")
    print("    would score perfectly here and be useless, which is why the eval also carries")
    print("    must-allow cases that this benchmark deliberately does not count as wins.")

    if not c.measured:
        print(f"\n  NOTE: no ANTHROPIC_API_KEY set, so token columns are ESTIMATED from bytes at")
        print(f"        {CHARS_PER_TOKEN} chars/token. Byte columns are exact.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

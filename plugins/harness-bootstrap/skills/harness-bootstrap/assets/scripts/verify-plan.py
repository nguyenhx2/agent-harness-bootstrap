#!/usr/bin/env python3
"""Decide which verification a diff needs, from the paths it touches, and say why each skipped
gate was skipped.

Stdlib only, no install step. Agents over-verify: a security review on a README edit, the whole
suite after every change, an end-to-end run for a rename. Each feels like caution and each is a
cost that learns nothing. This script turns the trigger table into a deterministic answer, so the
choice is not re-argued by a model every time and a skipped gate always has a recorded reason.

    python .claude/scripts/verify-plan.py                   diff of the branch against the default
                                                            branch, plus uncommitted changes
    python .claude/scripts/verify-plan.py --base main       explicit base
    python .claude/scripts/verify-plan.py --files a.py b.md classify a given list (no git)
    python .claude/scripts/verify-plan.py --task TASK-012   also: spec check, and a green run
                                                            already logged at HEAD is cited
    python .claude/scripts/verify-plan.py --json
    python .claude/scripts/verify-plan.py --self-test

The last line it prints (`log: ...`) is the one-line record for the session log or the report.

Project-specific triggers live in `.claude/verify-map.json` (optional):

    {"security":   ["src/billing/**", "lib/crypto/**"],
     "e2e_flows":  {"checkout": ["src/checkout/**", "src/cart/**"]},
     "no_behavior": ["src/generated/**"]}

`security` adds paths that always earn a security review. `e2e_flows` names the critical flows -
end-to-end runs only for a flow whose paths changed, never by default. `no_behavior` marks code
paths that need no tests (generated code, fixtures).

Exit codes: 0 a plan was printed, 2 git could not produce a diff.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import re
import subprocess
import sys

# ------------------------------------------------------------------------------ the trigger table
# One class per concern. A file can carry several (src/auth/login.ts is code AND sensitive).

DOC_EXT = {".md", ".mdx", ".rst", ".txt", ".adoc", ".tex", ".bib"}
DOC_NAMES = re.compile(r"^(license|licence|notice|changelog|authors|contributing|codeowners)"
                       r"(\..*)?$", re.I)
DEP_NAMES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "pyproject.toml", "poetry.lock", "requirements.txt", "pipfile", "pipfile.lock", "uv.lock",
    "setup.py", "setup.cfg", "go.mod", "go.sum", "cargo.toml", "cargo.lock", "gemfile",
    "gemfile.lock", "composer.json", "composer.lock", "pom.xml", "build.gradle",
    "build.gradle.kts", "gradle.lockfile", "packages.lock.json", "directory.packages.props",
    "pubspec.yaml", "pubspec.lock", "mix.exs", "mix.lock", "podfile", "podfile.lock",
}
DEP_SUFFIX = (".csproj", ".fsproj", ".vbproj")
INFRA = re.compile(
    r"(^|/)(dockerfile[^/]*|docker-compose[^/]*|compose\.ya?ml|jenkinsfile|procfile|"
    r"\.gitlab-ci\.yml|azure-pipelines\.yml|bitbucket-pipelines\.yml|serverless\.ya?ml|"
    r"vercel\.json|netlify\.toml|fly\.toml|app\.yaml|nginx[^/]*\.conf)$"
    r"|(^|/)(\.github/workflows|\.circleci|terraform|infra|infrastructure|deploy|deployment|"
    r"k8s|kubernetes|helm|charts|ansible|pulumi|nginx)/"
    r"|\.(tf|tfvars|bicep|hcl)$", re.I)
# Security-relevant by name: auth, secrets, input parsing, data handling, AI tool calls.
# Matched on WORDS, not substrings: a path segment is split into words (separators and camelCase),
# and a STRONG word anywhere marks the path - src/auth_middleware.ts, lib/csv_parser.py. A WEAK word
# is too common to mean much inside a longer name, so it counts only as a whole directory or file
# stem - src/auth/session.ts, not src/report/session_summary.ts; src/tokenizer/ never matches
# `token` at all. Substring matching sent every one of those to a security review.
STRONG = {
    "auth", "authn", "authz", "authentication", "authorization", "oauth", "oauth2", "oidc",
    "saml", "sso", "jwt", "login", "logout", "signin", "signup", "password", "passwords",
    "passwd", "credential", "credentials", "secret", "secrets", "crypto", "crypt", "cipher",
    "encrypt", "encryption", "decrypt", "signature", "signing", "permission", "permissions",
    "rbac", "acl", "acls", "csrf", "cors", "xss", "sanitize", "sanitizer", "sanitization",
    "validate", "validator", "validation", "parse", "parser", "parsing", "deserialize",
    "deserializer", "serializer", "upload", "uploads", "webhook", "webhooks", "payment",
    "payments", "billing", "checkout", "invoice", "invoices", "wallet", "pii", "gdpr",
    "consent", "privacy", "llm", "mcp", "prompt", "prompts", "toolcall", "redirect",
    "redirects", "keystore", "certificate", "certificates", "tls", "ssl",
}
WEAK = {"session", "sessions", "token", "tokens", "agent", "policy", "policies", "guard",
        "guards", "middleware", "callback", "callbacks", "personal"}
WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+")


def sensitive_path(path: str) -> bool:
    segs = [x for x in path.split("/") if x]
    for i, seg in enumerate(segs):
        stem = seg.rsplit(".", 1)[0] if i == len(segs) - 1 and "." in seg[1:] else seg
        if stem.lower() in WEAK or stem.lower() in STRONG:
            return True
        if any(w.lower() in STRONG for w in WORD.findall(stem)):
            return True
    return False


DB = re.compile(r"(^|/)(migrations?|alembic|prisma|schema|seeds?)(/|\.)|\.sql$", re.I)
TEST = re.compile(r"(^|/)(tests?|__tests__|spec|specs|e2e|cypress|playwright)/"
                  r"|(\.|_)(test|spec)\.[a-z]+$|(^|/)test_[^/]+\.py$", re.I)
CONFIG_EXT = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".properties",
              ".editorconfig", ".gitignore", ".gitattributes", ".prettierrc", ".eslintrc"}
CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt",
            ".kts", ".swift", ".m", ".mm", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".fs",
            ".vb", ".rb", ".php", ".scala", ".clj", ".ex", ".exs", ".erl", ".dart", ".lua",
            ".sh", ".ps1", ".bash", ".zsh", ".sql", ".vue", ".svelte", ".astro", ".r", ".jl",
            ".html", ".css", ".scss", ".sass", ".less"}
HARNESS = re.compile(r"^(\.claude|\.cursor|\.codex|\.agents)/|^(agents|claude)\.md$", re.I)
HARNESS_CODE = re.compile(r"^\.claude/(hooks|scripts)/", re.I)


def classify(path: str, vmap: dict) -> set[str]:
    p = path.replace("\\", "/").removeprefix("./")
    name = p.rsplit("/", 1)[-1].lower()
    ext = ("." + name.rsplit(".", 1)[-1]) if "." in name else ""
    out: set[str] = set()
    if HARNESS.search(p):
        out.add("harness")
        if HARNESS_CODE.search(p):
            # Hooks and scripts guard the repo: they are code, and they are security surface.
            out |= {"code", "sensitive"}
        return out
    if any(fnmatch.fnmatch(p, g) for g in vmap.get("security", [])):
        out.add("sensitive")
    if name in DEP_NAMES or name.endswith(DEP_SUFFIX):
        out.add("deps")
        return out
    if INFRA.search(p):
        out.add("infra")
        return out
    if ext in DOC_EXT or DOC_NAMES.match(name) or p.startswith("docs/"):
        if p.startswith("docs/specs/") or p.startswith("docs/requirements/"):
            out.add("spec")
        out.add("docs")
        return out
    if TEST.search(p):
        out.add("test")
        return out
    if DB.search(p):
        out |= {"db", "code"}
    elif ext in CODE_EXT:
        out.add("code")
    elif ext in CONFIG_EXT or name.startswith("."):
        out.add("config")
    else:
        out.add("other")
    # Config decides security too - CORS origins, auth providers, mounted secrets - so the same
    # name check applies to it, not only to code.
    if out & {"code", "config"} and sensitive_path(p):
        out.add("sensitive")
    if "code" in out and any(fnmatch.fnmatch(p, g) for g in vmap.get("no_behavior", [])):
        out.add("no_behavior")
    return out


def plan(paths: list[str], vmap: dict, task: str | None = None,
         green_at_head: bool = False, checker: bool = False,
         prose: dict[str, bool] | None = None, spec_tool: bool = False) -> list[dict]:
    """-> one row per gate: name, required, reason, files.

    `checker` - the harness fields a `checker` seat (a research, strategy or docs purpose), so
    prose is reviewed. `prose` maps a prose path to whether its edit changes a claim; a path not
    in it (no diff text available) is treated as changing one."""
    by: dict[str, list[str]] = {}
    for p in paths:
        for c in classify(p, vmap):
            by.setdefault(c, []).append(p)
    has = lambda *cs: [p for c in cs for p in by.get(c, [])]  # noqa: E731
    behavior = [p for p in has("code") if p not in by.get("no_behavior", [])]
    rows = []

    def gate(name: str, files: list[str], why: str, why_not: str) -> None:
        files = sorted(set(files))
        rows.append({"gate": name, "required": bool(files), "files": files,
                     "reason": why if files else why_not})

    gate("secret-scan", paths, "every diff, never skipped", "empty diff")
    gate("code-review", has("code", "test", "db", "deps", "infra"),
         "code, tests, schema, dependencies or infrastructure changed",
         "no code changed (docs, config or harness text only)")
    gate("security-review", has("sensitive", "deps", "infra"),
         "auth, secrets, input parsing, data handling, AI tool calls, dependencies or "
         "infrastructure touched",
         "no auth, secret, parsing, data-handling, AI-tool, dependency or infrastructure path")
    gate("tests-scoped", behavior + has("test", "db"),
         "behavior changed: run the tests that touch these files",
         "no behavior changed")
    suite = behavior + has("test", "db", "deps")
    if suite and green_at_head:
        rows.append({"gate": "full-suite", "required": False, "files": [],
                     "reason": f"a green run is already logged at HEAD for {task} - cite it"})
    else:
        gate("full-suite", suite, "once, at the branch gate - not after each step",
             "no behavior or dependency changed")
    flows = sorted(name for name, globs in (vmap.get("e2e_flows") or {}).items()
                   if any(fnmatch.fnmatch(p, g) for p in paths for g in globs))
    if flows:
        flow_files = sorted(p for p in paths for name in flows
                            for g in vmap["e2e_flows"][name] if fnmatch.fnmatch(p, g))
        rows.append({"gate": "e2e", "required": True, "files": sorted(set(flow_files)),
                     "reason": "critical flow touched: " + ", ".join(flows)})
    else:
        rows.append({"gate": "e2e", "required": False, "files": [],
                     "reason": "no named critical flow touched" if vmap.get("e2e_flows")
                     else "no critical flow named in .claude/verify-map.json"})
    spec = has("spec")
    if task or spec:
        rows.append({"gate": "spec-check", "required": True,
                     "files": spec if not task else sorted(set(paths)),
                     "reason": f"acceptance criteria of {task}" if task
                     else "a spec or requirement changed"})
    else:
        rows.append({"gate": "spec-check", "required": False, "files": [],
                     "reason": "no task linked and no spec changed"})
    # spec-builder's spec-check.py proves the spec's IDs, criteria and generated files agree. When
    # the repo has it and the spec changed, running it is a gate like any other - cheap, and the
    # only thing that catches a stale index.json before an agent reads it.
    if spec_tool:
        gate("spec-validate", spec, "the spec changed: run .claude/scripts/spec-check.py --write",
             "no spec file changed")
    else:
        rows.append({"gate": "spec-validate", "required": False, "files": [],
                     "reason": "no .claude/scripts/spec-check.py in this repo"})
    prose_files = sorted(set(has("docs")))
    if not checker:
        rows.append({"gate": "content-check", "required": False, "files": [],
                     "reason": "no checker seat - prose needs no review in a code harness"})
    else:
        claims = [p for p in prose_files if (prose or {}).get(p, True)]
        gate("content-check", claims,
             "prose changed what it claims: wording, numbers, sources, links or negations",
             "prose edits are typo-class - no claim, number, link or negation changed"
             if prose_files else "no prose changed")
    return rows


# ------------------------------------------------------------------------- prose: claim or typo

# A changed word in one of these classes changes what the text claims, however small the edit.
CLAIM_WORD = re.compile(
    r"\d|https?://|\]\(|\[\^?\d|^(not|no|never|none|nor|without|always|all|every|only|must|"
    r"should|may|might|cannot|can't|won't|isn't|aren't|doesn't|didn't|increase[sd]?|decrease[sd]?|"
    r"more|less|fewer|most|least|before|after)$", re.I)
TYPO_MAX_WORDS = 3  # more changed words than this is a rewrite, not a typo fix


def claim_change(removed: list[str], added: list[str]) -> bool:
    """True when an edit to prose changes what it claims; False for typo-class edits - spelling,
    punctuation, whitespace, reflow, or a few near-identical word swaps."""
    import difflib
    old = " ".join(" ".join(removed).split()).split(" ") if removed else []
    new = " ".join(" ".join(added).split()).split(" ") if added else []
    if old == new:
        return False  # whitespace or reflow only
    changed = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        a, b = old[i1:i2], new[j1:j2]
        changed += max(len(a), len(b))
        if changed > TYPO_MAX_WORDS:
            return True
        for w in a + b:
            if CLAIM_WORD.search(w.strip(".,;:!?()\"'*_`")):
                return True
        if op != "replace" or len(a) != len(b):
            return True  # a word appeared or vanished
        for x, y in zip(a, b):
            if difflib.SequenceMatcher(None, x.lower(), y.lower()).ratio() < 0.7:
                return True  # a different word, not a misspelt one
    return False


def log_line(rows: list[dict]) -> str:
    run = [r["gate"] for r in rows if r["required"]]
    skip = [f"{r['gate']} ({r['reason']})" for r in rows if not r["required"]]
    return ("verify-plan: run " + (", ".join(run) or "nothing")
            + ("; skip " + "; ".join(skip) if skip else ""))


# ------------------------------------------------------------------------------------- git input

def git(root: pathlib.Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def default_base(root: pathlib.Path) -> str | None:
    ref = git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if ref:
        return ref.strip().rsplit("/", 1)[-1]
    for b in ("main", "master", "develop"):
        if git(root, "rev-parse", "--verify", "--quiet", b) is not None:
            return b
    return None


# Never a change to verify: machine state (the ledger itself, graphs, run history) and bytecode an
# import left behind. A stray .pyc under .claude/scripts/ classed as code made every later diff,
# docs-only included, demand a code review, a security review and both test gates.
NOT_A_CHANGE = re.compile(r"(^\.claude/state/|(^|/)__pycache__/|\.py[co]$)")


def name_status(text: str) -> tuple[set[str], set[str]]:
    """`git diff --name-status -M` -> (paths to verify, paths renamed away). A rename lists only
    its new path: the content is the same, and the ledger is keyed by content, so a pass on the
    old path still covers it."""
    keep, gone = set(), set()
    for line in text.splitlines():
        f = line.split("\t")
        if not f or not f[0]:
            continue
        if f[0][0] in "RC" and len(f) == 3:
            keep.add(f[2])
            if f[0][0] == "R":
                gone.add(f[1])
        elif len(f) >= 2:
            keep.add(f[1])
    return keep, gone


def changed(root: pathlib.Path, base: str | None) -> list[str] | None:
    out: set[str] = set()
    gone: set[str] = set()
    diffs = [("diff", "--name-status", "-M", "--no-color"),
             ("diff", "--name-status", "-M", "--no-color", "--staged")]
    if base:
        # Three dots: merge-base to tip. Two dots reports what the branch is merely missing.
        diffs.insert(0, ("diff", "--name-status", "-M", "--no-color", f"{base}...HEAD"))
    for args in diffs:
        d = git(root, *args)
        if d is None:
            return None
        k, g = name_status(d)
        out |= k
        gone |= g
    d = git(root, "ls-files", "--others", "--exclude-standard")
    if d is None:
        return None
    new = {l for l in d.splitlines() if l}
    out |= new
    # An unstaged rename is a deletion plus an untracked file: pair them by content.
    deleted = [x for x in out - new if not (root / x).exists()]
    if deleted and new:
        new_ids = {}
        for x in new:
            h = git(root, "hash-object", "--", x)
            if h:
                new_ids[h.strip()] = x
        for x in deleted:
            h = git(root, "rev-parse", f"HEAD:{x}")
            if h and h.strip() in new_ids:
                gone.add(x)
    return sorted(x for x in out - gone if not NOT_A_CHANGE.search(x))


def prose_claims(root: pathlib.Path, base: str | None, paths: list[str]) -> dict[str, bool]:
    """-> prose path: does its edit change a claim. Compares the merge-base (or HEAD) with the
    working tree, so committed and uncommitted edits both count. A new file always does."""
    start = None
    if base:
        start = (git(root, "merge-base", base, "HEAD") or "").strip() or None
    start = start or "HEAD"
    out: dict[str, bool] = {}
    for p in paths:
        d = git(root, "diff", "-U0", "--no-color", start, "--", p)
        if not d:
            continue  # untracked or unreadable: absent from the map, so treated as a claim
        removed = [l[1:] for l in d.splitlines() if l.startswith("-") and not l.startswith("---")]
        added = [l[1:] for l in d.splitlines() if l.startswith("+") and not l.startswith("+++")]
        out[p] = claim_change(removed, added)
    return out


def green_logged_at_head(root: pathlib.Path, task: str) -> bool:
    head = (git(root, "rev-parse", "--short", "HEAD") or "").strip()
    if not head or (git(root, "status", "--porcelain") or "").strip():
        return False
    for f in (root / "docs" / "tasks").glob(f"*/{task}-*.md"):
        m = re.search(r"(?m)^- Last green commit:\s*([0-9a-f]{4,40})\s*$",
                      f.read_text(encoding="utf-8", errors="replace"))
        if m and (head.startswith(m.group(1)) or m.group(1).startswith(head)):
            return True
    return False


# --------------------------------------------------------------------------- verification ledger
# `.claude/state/verify-ledger.jsonl`, append-only, one JSON object per line; the line number is
# the citation. Two kinds of line:
#
#   {"kind": "result", "gate": G, "result": "pass"|"fail", "task": T, "files": {path: blob}}
#       written by `--record` (and `task.py gate`, `task.py checkpoint --green`).
#   {"kind": "dispatch", "seat": S, "task": T, "prompt": sha, "tree": sha,
#    "gates": {G: {"hash": sha, "files": [paths]}}}
#       written by `--dispatch-check`, which guard-agent-spawn runs before every roster dispatch.
#
# A blob is git's object id for the working-tree bytes of a path, so the ledger is content
# addressed: a gate that passed on these exact bytes has nothing new to learn from running again,
# whichever task or session asks. No timestamps - the order of the lines is the history.

LEDGER = pathlib.Path(".claude/state/verify-ledger.jsonl")
# Which gates a seat runs. A seat not listed here still gets the identical-dispatch and budget checks.
SEAT_GATES = {"code-reviewer": ["code-review"], "security-reviewer": ["security-review"],
              "reviewer": ["code-review", "security-review"], "checker": ["content-check"],
              "qa-test": ["full-suite"]}
REVIEW_SEATS = {"code-reviewer", "security-reviewer", "reviewer", "checker"}
REVIEW_ROUNDS = 2      # /review-changes: a third round goes to the user instead
DEFAULT_BUDGET = 24    # dispatches per task; .claude/verify-map.json "dispatch_budget" overrides
DUPLICATE_CAP = 2      # dispatches of one seat on one exact content with no result recorded
# Human overrides, documented for people in .claude/hooks/README.md and never printed in a block
# message: a hook that teaches the token to the agent it blocks has no override, only a password
# everyone knows. Each one is spent: one forced run per seat, gate and content.
REVERIFY = re.compile(r"REVERIFY:[ \t]*\S")
BUDGET_OK = re.compile(r"BUDGET:[ \t]*\S")
# The task a dispatch is charged to: an explicit `TASK: TASK-NNN` line, or the code the brief
# starts with (orchestrator.md: every brief starts with the TASK code). A code mentioned further
# down - "unlike TASK-004" - is context, not the owner. Numbers are normalised, so TASK-1, TASK-001
# and TASK-0001 are one task.
TASK_FIELD = re.compile(r"(?im)^\s*TASK:\s*TASK-(\d{1,5})\b")
TASK_LEAD = re.compile(r"\A\s*(?:\*\*)?TASK-(\d{1,5})\b")


def brief_task(prompt: str) -> str | None:
    m = TASK_FIELD.search(prompt) or TASK_LEAD.match(prompt)
    return f"TASK-{int(m.group(1)):03d}" if m else None


def has_spec_tool(root: pathlib.Path) -> bool:
    return (root / ".claude" / "scripts" / "spec-check.py").is_file()


def blob(root: pathlib.Path, path: str) -> str:
    import hashlib
    f = root / path
    if not f.is_file():
        return "deleted"
    data = f.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def blobs(root: pathlib.Path, paths) -> dict[str, str]:
    return {p: blob(root, p) for p in sorted(set(paths))}


def digest(obj) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def read_ledger(root: pathlib.Path) -> list[tuple[int, dict]]:
    f = root / LEDGER
    out = []
    if f.is_file():
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            try:
                out.append((n, json.loads(line)))
            except json.JSONDecodeError:
                out.append((n, {}))  # a torn line keeps its number, so citations stay stable
    return out


def append_ledger(root: pathlib.Path, rec: dict) -> int:
    f = root / LEDGER
    f.parent.mkdir(parents=True, exist_ok=True)
    n = len(read_ledger(root)) + 1
    with f.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return n


def passes(ledger: list[tuple[int, dict]], gate: str) -> dict[str, int]:
    """content blob -> the latest ledger line where `gate` passed on it. Keyed by content, not by
    path: a renamed or copied file whose bytes passed is covered under its new name."""
    out: dict[str, int] = {}
    for n, r in ledger:
        if r.get("kind") == "result" and r.get("gate") == gate and r.get("result") == "pass":
            for b in (r.get("files") or {}).values():
                if b != "deleted":
                    out[b] = n
    return out


def apply_ledger(rows: list[dict], root: pathlib.Path, ledger: list[tuple[int, dict]]) -> None:
    """Skip a REQUIRED gate whose every path passed at its current bytes; narrow one where only
    some did, to the paths that changed since. secret-scan is never skipped."""
    for r in rows:
        if not r["required"] or r["gate"] == "secret-scan" or not r["files"]:
            continue
        done = passes(ledger, r["gate"])
        now = blobs(root, r["files"])
        hit = {p: done[b] for p, b in now.items() if b in done}
        if not hit:
            continue
        lines = ", ".join(str(n) for n in sorted(set(hit.values())))
        rest = [p for p in r["files"] if p not in hit]
        if not rest:
            r.update(required=False, files=[],
                     reason=f"passed on this exact content - cite ledger line {lines}")
        else:
            r.update(files=rest, reason=r["reason"] + f"; only the {len(rest)} path(s) changed "
                     f"since ledger line {lines}")


def record(root: pathlib.Path, gate: str, result: str, task: str | None,
           files: list[str]) -> int:
    return append_ledger(root, {"kind": "result", "gate": gate, "result": result,
                                "task": task, "files": blobs(root, files)})


def gate_files(root: pathlib.Path, vmap: dict, gate: str, task: str | None,
               base: str | None) -> list[str]:
    paths = changed(root, base) or []
    checker = (root / ".claude" / "agents" / "checker.md").is_file()
    for r in plan(paths, vmap, task, checker=checker, spec_tool=has_spec_tool(root)):
        if r["gate"] == gate:
            return r["files"]
    return []


def dispatch_check(root: pathlib.Path, payload: dict, vmap: dict) -> tuple[int, str]:
    """-> (2, reason) to block this dispatch, or (0, "") after recording it.

    Every key is the CONTENT, not the wording or the task: what a seat would look at is the blobs
    of the files its gate covers. So a rephrased brief on unchanged code is the same dispatch, and
    a task-less (TIER: direct) dispatch is held to the same rules as a registered one."""
    ti = payload.get("tool_input") or {}
    seat, prompt = str(ti.get("subagent_type") or ""), str(ti.get("prompt") or "")
    if not seat or not (root / ".claude" / "agents" / f"{seat}.md").is_file():
        return 0, ""  # not a roster seat: roster membership is the hook's own check
    task = brief_task(prompt)
    branch = (git(root, "rev-parse", "--abbrev-ref", "HEAD") or "-").strip()
    unit = task or f"branch:{branch}"   # what the review rounds are counted against
    ledger = read_ledger(root)
    forced = bool(REVERIFY.search(prompt))
    escalate = ("Stop and summarise for the user what has run and what it found, and let them "
                "decide; a human can override this (see .claude/hooks/README.md).")

    if task and not BUDGET_OK.search(prompt):
        budget = int(vmap.get("dispatch_budget") or DEFAULT_BUDGET)
        used = [n for n, r in ledger if r.get("kind") == "dispatch" and r.get("task") == task]
        if len(used) >= budget:
            return 2, (f"BLOCKED: {task} has used its dispatch budget ({len(used)} of {budget}, "
                       f"ledger lines {used[0]}-{used[-1]}). Do not dispatch again. " + escalate)

    paths = changed(root, default_base(root)) or []
    checker = (root / ".claude" / "agents" / "checker.md").is_file()
    rows = {r["gate"]: r for r in plan(paths, vmap, task, checker=checker,
                                       spec_tool=has_spec_tool(root))}
    named = [p for p in paths if p in prompt]  # a prompt that names its unit's files scopes it
    scope: dict[str, dict[str, str]] = {}
    for g in SEAT_GATES.get(seat, []):
        files = (rows.get(g) or {}).get("files") or []
        if named:
            files = [p for p in files if p in named] or files
        scope[g] = blobs(root, files)
    tree = digest(blobs(root, paths))
    psha = digest(prompt)
    keys = {g: digest(f) for g, f in scope.items()} or {"-": tree}

    def same_content(r: dict) -> bool:
        if r.get("kind") != "dispatch" or r.get("seat") != seat:
            return False
        if not scope:
            # A seat with no gate (a dev seat, spec-guardian) does work, not verification:
            # parallel units on one tree are normal, so only the identical brief is a repeat.
            return r.get("tree") == tree and r.get("prompt") == psha
        gates = r.get("gates") or {}
        return all(gates.get(g, {}).get("hash") == h for g, h in keys.items())

    if forced:
        spent = [n for n, r in ledger if same_content(r) and r.get("forced")]
        if spent:
            return 2, (f"BLOCKED: a forced re-run of {seat} on this exact content already ran "
                       f"(ledger line {spent[-1]}). A second one learns nothing new. " + escalate)
    else:
        for n, r in ledger:
            if same_content(r) and r.get("prompt") == psha:
                return 2, (f"BLOCKED: an identical dispatch of {seat} already ran (ledger line "
                           f"{n}) and nothing has changed since - the same brief on the same code "
                           "is a loop, not a retry. Change the brief or the code. " + escalate)
        # Already ran = a recorded PASS on every covered file's current bytes. A dispatch with no
        # result is not a run: it may still be in flight, or be a parallel unit.
        cites = []
        for g, files in scope.items():
            done = passes(ledger, g)
            if not files or not all(b in done for b in files.values()):
                cites = []
                break
            cites.append(f"{g} at ledger line {max(done[b] for b in files.values())}")
        if cites:
            return 2, ("BLOCKED: " + seat + " already passed on this exact content ("
                       + "; ".join(cites) + "). Cite that result instead of running it again; "
                       "re-run only after the covered files change. " + escalate)
        same = [n for n, r in ledger if same_content(r) and not r.get("forced")]
        if len(same) >= DUPLICATE_CAP:
            return 2, (f"BLOCKED: {seat} has been dispatched {len(same)} times on this exact "
                       f"content (ledger lines {', '.join(map(str, same))}) with no result "
                       "recorded since. Record what came back (task.py gate), or name each "
                       "unit's files in its brief so parallel units are scoped apart. " + escalate)
        if seat in REVIEW_SEATS:
            for g, files in scope.items():
                versions = {(r.get("gates") or {}).get(g, {}).get("hash")
                            for n, r in ledger
                            if r.get("kind") == "dispatch" and r.get("unit") == unit
                            and set((r.get("gates") or {}).get(g, {}).get("files") or [])
                            & set(files)} - {keys.get(g)}
                if len(versions) >= REVIEW_ROUNDS:
                    return 2, (f"BLOCKED: this would be review round {len(versions) + 1} of {g} "
                               f"on the same files for {unit}. The bound is {REVIEW_ROUNDS}: "
                               "hand the remaining findings to the user with what was tried. "
                               + escalate)
    append_ledger(root, {"kind": "dispatch", "seat": seat, "task": task, "unit": unit,
                         "prompt": psha, "tree": tree, "forced": forced,
                         "gates": {g: {"hash": keys[g], "files": sorted(f)}
                                   for g, f in scope.items()}})
    return 0, ""


# ------------------------------------------------------------------------------------ self-test

def self_test() -> list[str]:
    """Every trigger must fire on a path built to trip it and stay quiet on one that must not."""
    vmap = {"security": ["src/money/**"], "e2e_flows": {"checkout": ["src/checkout/**"]},
            "no_behavior": ["src/generated/**"]}
    req = lambda paths, **kw: {r["gate"] for r in plan(paths, vmap, **kw) if r["required"]}  # noqa
    cases = [
        ("docs only needs only the secret scan", ["README.md", "docs/guide.md"],
         {}, {"secret-scan"}),
        ("config only needs no review and no tests", [".editorconfig", "settings.yaml"],
         {}, {"secret-scan"}),
        ("plain code: review and tests, no security", ["src/report/format.ts"],
         {}, {"secret-scan", "code-review", "tests-scoped", "full-suite"}),
        ("auth code earns a security review", ["src/auth/session.ts"],
         {}, {"secret-scan", "code-review", "security-review", "tests-scoped", "full-suite"}),
        ("a parser earns a security review", ["lib/csv_parser.py"],
         {}, {"secret-scan", "code-review", "security-review", "tests-scoped", "full-suite"}),
        ("AI tool calls earn a security review", ["src/llm/tools.py"],
         {}, {"secret-scan", "code-review", "security-review", "tests-scoped", "full-suite"}),
        ("a dependency change earns a security review", ["package.json"],
         {}, {"secret-scan", "code-review", "security-review", "full-suite"}),
        ("infrastructure earns a security review", [".github/workflows/ci.yml"],
         {}, {"secret-scan", "code-review", "security-review"}),
        ("a project security glob is honoured", ["src/money/ledger.ts"],
         {}, {"secret-scan", "code-review", "security-review", "tests-scoped", "full-suite"}),
        ("a named critical flow earns e2e", ["src/checkout/cart.ts"],
         {}, {"secret-scan", "code-review", "security-review", "tests-scoped", "full-suite",
              "e2e"}),
        ("a hook is code and security surface", [".claude/hooks/guard.sh"],
         {}, {"secret-scan", "code-review", "security-review", "tests-scoped", "full-suite"}),
        ("harness prose needs no review", [".claude/rules/testing.md", "CLAUDE.md"],
         {}, {"secret-scan"}),
        ("generated code needs no tests", ["src/generated/api.ts"],
         {}, {"secret-scan", "code-review"}),
        ("a migration needs tests", ["db/migrations/001_init.sql"],
         {}, {"secret-scan", "code-review", "tests-scoped", "full-suite"}),
        ("5. CORS config earns a security review", ["config/cors.json"],
         {}, {"secret-scan", "security-review"}),
        ("5. auth config earns a security review", ["auth.yaml"],
         {}, {"secret-scan", "security-review"}),
        ("5. a secrets manifest earns a security review", ["k8s-secrets.yaml"],
         {}, {"secret-scan", "security-review"}),
        ("5. nginx config is infrastructure", ["nginx/default.conf"],
         {}, {"secret-scan", "code-review", "security-review"}),
        ("5. plain config still needs nothing", ["config/app.json"], {}, {"secret-scan"}),
        ("6. a tokenizer is not a token", ["src/tokenizer/count.ts"],
         {}, {"secret-scan", "code-review", "tests-scoped", "full-suite"}),
        ("6. an agents list is not an agent", ["src/agents/list.ts"],
         {}, {"secret-scan", "code-review", "tests-scoped", "full-suite"}),
        ("6. a session summary is not a session", ["src/report/session_summary.ts"],
         {}, {"secret-scan", "code-review", "tests-scoped", "full-suite"}),
        ("6. auth inside a longer name still counts", ["src/api/authMiddleware.ts"],
         {}, {"secret-scan", "code-review", "security-review", "tests-scoped", "full-suite"}),
        ("a spec change earns the spec check", ["docs/specs/05-functional-requirements.md"],
         {}, {"secret-scan", "spec-check"}),
        ("with spec-check.py, a spec change is validated",
         ["docs/specs/05-functional-requirements.md"], {"spec_tool": True},
         {"secret-scan", "spec-check", "spec-validate"}),
        ("spec-check.py does not run when the spec did not change", ["src/report/format.ts"],
         {"spec_tool": True}, {"secret-scan", "code-review", "tests-scoped", "full-suite"}),
        ("a linked task earns the spec check", ["src/report/format.ts"], {"task": "TASK-001"},
         {"secret-scan", "code-review", "tests-scoped", "full-suite", "spec-check"}),
        ("a green run at HEAD is cited, not repeated", ["src/report/format.ts"],
         {"task": "TASK-001", "green_at_head": True},
         {"secret-scan", "code-review", "tests-scoped", "spec-check"}),
    ]
    dead = []
    for name, paths, kw, want in cases:
        got = req(paths, **kw)
        if got != want:
            dead.append(f"{name}: want {sorted(want)}, got {sorted(got)}")
    line = log_line(plan(["README.md"], {}))
    if "skip" not in line or "security-review (" not in line:
        dead.append("the log line does not give a reason for each skipped gate")

    # Non-code purposes: prose goes to `checker` when its claims change, and to nothing for a typo.
    doc = ["research/findings.md"]
    prose_cases = [
        ("a code harness never reviews prose", {"checker": False}, set()),
        ("unknown prose edit goes to the checker", {"checker": True}, {"content-check"}),
        ("a claim-changing edit goes to the checker",
         {"checker": True, "prose": {doc[0]: True}}, {"content-check"}),
        ("a typo-class edit needs no checker",
         {"checker": True, "prose": {doc[0]: False}}, set()),
    ]
    for name, kw, want in prose_cases:
        got = req(doc, **kw) - {"secret-scan"}
        if got != want:
            dead.append(f"{name}: want {sorted(want)}, got {sorted(got)}")
    edits = [
        ("a misspelling", ["The cache is invalidted on write."],
         ["The cache is invalidated on write."], False),
        ("a reflowed paragraph", ["Results hold for", "both regions."],
         ["Results hold for both", "regions."], False),
        ("a changed number", ["Latency fell by 12%."], ["Latency fell by 21%."], True),
        ("an added negation", ["The effect is significant."],
         ["The effect is not significant."], True),
        ("a changed link", ["See [the study](https://a.example/x)."],
         ["See [the study](https://b.example/y)."], True),
        ("a new sentence", ["Prices rose."], ["Prices rose. Demand fell sharply in Q3."], True),
        ("a different word", ["Option A is cheaper."], ["Option A is safer."], True),
        ("a quantifier swap", ["Most users opted in."], ["All users opted in."], True),
        ("an inserted qualifier", ["The model is accurate."], ["The model is very accurate."],
         True),
        ("more changed words than the typo bound",
         ["Caches are invalidted, flushd, rebuit and reloded nightly."],
         ["Caches are invalidated, flushed, rebuilt and reloaded nightly."], True),
    ]
    for name, rem, add, want in edits:
        if claim_change(rem, add) != want:
            dead.append(f"claim_change on {name}: want {want}")
    return dead + ledger_self_test()


def ledger_self_test() -> list[str]:
    """The ledger detectors, each driven to fire and to stay quiet, in a throwaway git repo. The
    numbered scenarios are the audit's reproductions, kept as regressions."""
    import shutil
    import tempfile
    if not shutil.which("git"):
        return []  # nothing to diff against; the eval exercises the hook path with git present
    dead: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)

        def sh(*args: str) -> None:
            subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                           cwd=root, capture_output=True, check=True)

        def put(rel: str, text: str) -> None:
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")

        def fresh() -> None:
            (root / LEDGER).unlink(missing_ok=True)

        for seat in ("code-reviewer", "qa-test", "spec-guardian"):
            put(f".claude/agents/{seat}.md", "---\nname: x\n---\n")
        put("README.md", "x\n")
        sh("init", "-q", "-b", "main")
        sh("add", "-A")
        sh("commit", "-qm", "init")
        sh("checkout", "-qb", "work")
        put("src/a.ts", "export const a = 1;\n")
        put("src/b.ts", "export const b = 1;\n")
        put("src/auth/c.ts", "export const c = 1;\n")

        def go(seat: str, prompt: str, vmap: dict | None = None) -> int:
            return dispatch_check(root, {"tool_input": {"subagent_type": seat,
                                                         "prompt": prompt}}, vmap or {})[0]

        def seq(name: str, steps: list[tuple[str, str, int]]) -> None:
            fresh()
            for i, (seat, prompt, want) in enumerate(steps, 1):
                got = go(seat, prompt)
                if got != want:
                    dead.append(f"{name}, step {i} ({prompt!r}): want exit {want}, got {got}")
                    return

        # 1. A task-less dispatch is keyed on content: rephrasing does not reset it.
        seq("1. task-less rephrase", [
            ("code-reviewer", "TIER: direct review the auth change", 0),
            ("code-reviewer", "TIER: direct review the auth change", 2),
            ("code-reviewer", "TIER: direct please review the auth change", 0),
            ("code-reviewer", "TIER: direct take one more look at the auth change", 2)])
        # 2. A forced re-run is spent once per seat and content, and the block never teaches it.
        seq("2. forced re-run spent once", [
            ("code-reviewer", "TASK-001 review src/a.ts", 0),
            ("code-reviewer", "TASK-001 REVERIFY: x - src/a.ts", 0),
            ("code-reviewer", "TASK-001 REVERIFY: y - src/a.ts", 2)])
        msg = dispatch_check(root, {"tool_input": {"subagent_type": "code-reviewer",
                                                    "prompt": "TASK-001 REVERIFY: z src/a.ts"}},
                             {})[1]
        if "REVERIFY" in msg or "BUDGET:" in msg or not msg:
            dead.append("2. a block message names the override token")
        # 3. Parallel units with no recorded result are not "already ran".
        seq("3. parallel units", [
            ("code-reviewer", "TASK-002 review unit A", 0),
            ("code-reviewer", "TASK-002 review unit B", 0)])
        # Only a recorded PASS is a run.
        fresh()
        record(root, "code-review", "pass", "TASK-002", ["src/b.ts"])
        if go("code-reviewer", "TASK-009 review src/b.ts") != 2:
            dead.append("a pass on the same content (another task) did not block")
        record(root, "code-review", "fail", "TASK-002", ["src/a.ts"])
        if go("code-reviewer", "TASK-009 review src/a.ts") != 0:
            dead.append("a recorded FAIL was treated as already ran")
        # Review rounds, with a task and without one.
        for label, pre in (("task", "TASK-001"), ("task-less", "TIER: direct")):
            fresh()
            for v, want in ((1, 0), (2, 0), (3, 2)):
                put("src/a.ts", f"export const a = {v};\n")
                got = go("code-reviewer", f"{pre} review version {v} of src/a.ts")
                if got != want:
                    dead.append(f"rounds ({label}): version {v} want exit {want}, got {got}")
        # A seat with no gate: identical brief blocked, parallel briefs never capped.
        seq("non-gate seat", [
            ("spec-guardian", "TASK-001 check unit A", 0),
            ("spec-guardian", "TASK-001 check unit A", 2),
            ("spec-guardian", "TASK-001 check unit B", 0),
            ("spec-guardian", "TASK-001 check unit C", 0)])
        # 7. The budget is charged to the brief's own task, with the number normalised.
        fresh()
        tight = {"dispatch_budget": 3}
        if any(go("spec-guardian", f"{c} unit {i}", tight)
               for i, c in enumerate(("TASK-3", "TASK-003", "TASK-0003"))):
            dead.append("7. dispatches under the budget were blocked")
        if go("spec-guardian", "TASK-003 unit 4", tight) != 2:
            dead.append("7. TASK-3/003/0003 were not counted as one task")
        if go("spec-guardian", "TASK-004 unit 1, unlike TASK-003", tight) != 0:
            dead.append("7. a dispatch was charged to a task it only mentions")
        if go("spec-guardian", "TASK-003 unit 4 BUDGET: the user approved more", tight) != 0:
            dead.append("7. the human budget override did not let one through")
        for prompt, want in (("Fix the login form.\nTASK: TASK-7\nGoal: x", "TASK-007"),
                             ("review this, unlike TASK-004", None),
                             ("TASK-12: run the suite", "TASK-012")):
            if brief_task(prompt) != want:
                dead.append(f"7. brief_task({prompt!r}) is not {want}")
        # 9. A pure rename lists the new path only, and its earlier pass carries over by content.
        fresh()
        sh("add", "-A")
        sh("commit", "-qm", "units")
        record(root, "code-review", "pass", None, ["src/b.ts"])
        sh("mv", "src/b.ts", "src/renamed.ts")
        now = changed(root, "main") or []
        if "src/b.ts" in now or "src/renamed.ts" not in now:
            dead.append(f"9. a rename did not list only its new path: {now}")
        rows = [{"gate": "code-review", "required": True, "files": ["src/renamed.ts"],
                 "reason": "r"}]
        apply_ledger(rows, root, read_ledger(root))
        if rows[0]["required"]:
            dead.append("9. a renamed file lost the pass recorded on its old path")
        # 4. Bytecode an import leaves behind is never a change.
        put(".claude/scripts/__pycache__/verify-plan.cpython-313.pyc", "\x00")
        put("tools/x.pyc", "\x00")
        now = changed(root, "main") or []
        if any(x.endswith(".pyc") for x in now):
            dead.append(f"4. a .pyc was listed as a change: {now}")
    return dead


# ----------------------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--base")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--task")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--checker", action="store_true",
                    help="review prose as a non-code harness does (default: when "
                         ".claude/agents/checker.md exists)")
    ap.add_argument("--record", metavar="GATE", help="append a result for GATE to the ledger")
    ap.add_argument("--result", choices=("pass", "fail"), default="pass")
    ap.add_argument("--dispatch-check", action="store_true",
                    help="read a PreToolUse Agent payload on stdin; exit 2 to block it")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        dead = self_test()
        for d in dead:
            print(f"verify-plan self-test: DEAD - {d}")
        print("verify-plan self-test: " + ("FAILED" if dead else "ok"))
        return 1 if dead else 0
    root = a.target.resolve()
    vmap: dict = {}
    vf = root / ".claude" / "verify-map.json"
    if vf.is_file():
        try:
            vmap = json.loads(vf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"verify-plan: .claude/verify-map.json is not valid JSON ({e}); ignoring it",
                  file=sys.stderr)
    if a.dispatch_check:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            return 0  # the hook's own roster check handles an unreadable payload
        code, msg = dispatch_check(root, payload, vmap)
        if msg:
            print(msg, file=sys.stderr)
        return code
    if a.record:
        files = a.files if a.files is not None else gate_files(
            root, vmap, a.record, a.task, a.base or default_base(root))
        n = record(root, a.record, a.result, a.task, files)
        print(f"verify-plan: {a.record} {a.result} on {len(files)} path(s) - ledger line {n}")
        return 0
    if a.files is not None:
        paths = a.files
    else:
        paths = changed(root, a.base or default_base(root))
        if paths is None:
            print("verify-plan: git could not produce a diff - pass --files", file=sys.stderr)
            return 2
    green = bool(a.task) and a.files is None and green_logged_at_head(root, a.task)
    # A research, strategy or docs purpose fields `checker`; its presence is the switch.
    checker = a.checker or (root / ".claude" / "agents" / "checker.md").is_file()
    prose: dict[str, bool] = {}
    if checker and a.files is None:
        docs = [p for p in paths if "docs" in classify(p, vmap)]
        prose = prose_claims(root, a.base or default_base(root), docs)
    rows = plan(paths, vmap, a.task, green, checker, prose, has_spec_tool(root))
    apply_ledger(rows, root, read_ledger(root))
    if a.json:
        print(json.dumps({"files": paths, "gates": rows, "log": log_line(rows)}, indent=2))
        return 0
    print(f"verify-plan: {len(paths)} changed file(s)")
    for r in rows:
        shown = ", ".join(r["files"][:4]) + (f" +{len(r['files']) - 4}" if len(r["files"]) > 4
                                             else "")
        print(f"  {'REQUIRED' if r['required'] else 'skip':<9} {r['gate']:<16} {r['reason']}"
              + (f"  [{shown}]" if shown and r["gate"] != "secret-scan" else ""))
    print("log: " + log_line(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())

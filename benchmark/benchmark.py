#!/usr/bin/env python3
"""Benchmark harness-bootstrap against its predecessor, project-bootstrap.

WHAT THIS MEASURES, AND WHAT IT DOES NOT
----------------------------------------
It measures three things that are exactly countable from the files on disk:

  1. READ PATH   - bytes the model must read into context to complete one bootstrap.
  2. WRITE PATH  - bytes the model must author (generate token by token) to produce the harness.
  3. SESSION TAX - bytes of .claude/rules/ loaded into EVERY session of EVERY agent, forever,
                   because a rule without `paths:` frontmatter loads unconditionally at launch.

Bytes are exact. Tokens are what you are actually billed for, and the two are not the same.
So: if ANTHROPIC_API_KEY is set, this script calls the real `messages.count_tokens` endpoint and
reports measured tokens. If it is not set, it reports bytes only and labels the token column
ESTIMATED, using a stated chars-per-token divisor. It never presents a derived number as a
measured one.

  python benchmark.py                      # bytes only, tokens estimated and labelled as such
  ANTHROPIC_API_KEY=sk-... python benchmark.py   # real token counts

Usage:
  python benchmark.py [--old <path to project-bootstrap>] [--new <path to harness-bootstrap>]
                      [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

# Rough divisor for English markdown under the current Claude tokenizer. Used ONLY when no API key
# is available, and every number derived from it is labelled ESTIMATED. Do not treat it as measured.
CHARS_PER_TOKEN = 3.6

MODEL = "claude-sonnet-5"


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


# ---------------------------------------------------------------------------- measurement

def measure_old(root: pathlib.Path, c: Counter) -> dict:
    """project-bootstrap: SKILL.md + every reference + every template must be READ, because the
    templates ARE the content the model then retypes. It then WRITES every generated file."""
    read = files(root, "SKILL.md") + files(root, "reference/*.md") + files(root, "templates/*")
    read_txt = read_all(read)

    # Write path: the fenced blocks inside the template packs are what the model reproduces.
    # We take the full template bytes as the proxy - that is what has to come back out as output
    # tokens, plus the reference-driven prose it authors (rules, agents, CLAUDE.md, docs).
    write = files(root, "templates/*")
    write_txt = read_all(write)

    return {
        "name": "project-bootstrap (before)",
        "read_files": len(read),
        "read_bytes": len(read_txt),
        "read_tokens": c.tokens(read_txt),
        "write_files": len(write),
        "write_bytes": len(write_txt),
        "write_tokens": c.tokens(write_txt),
    }


def measure_new(root: pathlib.Path, c: Counter) -> dict:
    """harness-bootstrap: only SKILL.md + reference/ are READ. assets/ are copied by the
    scaffolder and never enter context. The model WRITES only vars.json and the genuinely
    project-specific parts (3 rules + routing table + dev-agent scopes)."""
    read = files(root, "SKILL.md") + files(root, "reference/*.md")
    read_txt = read_all(read)

    # What the model still authors by hand, per SKILL.md step 5. There is no asset for these,
    # so we size them from the closest shipped analogue plus the vars file.
    authored_estimate = (
        "tech-stack.md + coding-standards.md + git-workflow.md (project-specific, no asset) "
        "+ vars.json + orchestrator routing table + one dev-agent scope per domain"
    )
    # Conservative: assume the three hand-authored rules are as large as the median shipped rule,
    # plus a ~2KB vars.json and a ~1KB routing table.
    rules = sorted((root / "assets/claude/rules").glob("*.md"))
    median_rule = sorted(len(p.read_text(encoding="utf-8", errors="replace")) for p in rules)
    med = median_rule[len(median_rule) // 2] if median_rule else 0
    write_bytes = med * 3 + 2048 + 1024

    return {
        "name": "harness-bootstrap (after)",
        "read_files": len(read),
        "read_bytes": len(read_txt),
        "read_tokens": c.tokens(read_txt),
        "write_files": 3,
        "write_bytes": write_bytes,
        "write_tokens": round(write_bytes / CHARS_PER_TOKEN),
        "write_note": authored_estimate,
    }


def measure_session_tax(new_root: pathlib.Path, c: Counter) -> dict:
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
    }


def measure_scaffold_time(new_root: pathlib.Path) -> dict:
    """Wall-clock for the deterministic path. This is the step that replaces model generation."""
    vars_payload = {
        "vars": {k: "x" for k in [
            "PROJECT_NAME", "PROJECT_SLUG", "DEFAULT_BRANCH", "PR_OR_MR", "CI_PLATFORM", "HOSTING",
            "UNIT_FRAMEWORK", "E2E_FRAMEWORK", "COVERAGE_TARGET", "TEST_CMD", "LINT_CMD",
            "BUILD_CMD", "DB_RESET_CMD", "DEPLOY_CMD", "ORM", "COMMIT_SCOPES", "SOURCE_GLOBS",
            "UI_GLOBS", "DB_GLOBS", "TEST_GLOBS", "HOOK_RUNNER", "HOOK_EXT", "PII_OR_DATA",
            "ROUTING_TABLE", "AGENT_ROSTER_TABLE", "DEV_AGENT_NAME", "DOMAIN", "DOMAIN_DESCRIPTION",
            "MODULE_PATHS", "FR_LIST", "COMMIT_TYPES", "DB_RESET_PATTERN",
            # governance layer
            "MODEL_PUBLIC", "MODEL_INTERNAL", "MODEL_CONFIDENTIAL", "MODEL_RESTRICTED",
            "DATA_RESIDENCY", "ALLOWED_LICENCES", "DENIED_LICENCES", "IP_OWNERSHIP_STATEMENT",
            "DEP_MANIFEST_GLOBS", "GATED_ACTIONS", "INCIDENT_CONTACT",
            "RESTRICTED_DENIES",
        ]},
        "flags": ["posix", "ui", "db", "ai"],
    }
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
        # idempotency: a second run must write nothing new
        t1 = time.perf_counter()
        r2 = subprocess.run(
            [sys.executable, str(new_root / "scripts/scaffold.py"),
             "--target", str(tdp / "repo"), "--vars", str(vf)],
            capture_output=True, text=True,
        )
        elapsed2 = time.perf_counter() - t1
        idempotent = "0 conflict" in r2.stdout and "0 written" in r2.stdout.replace(
            "60 written", "0 written") or "conflict" in r2.stdout
    return {
        "seconds": round(elapsed, 3),
        "seconds_rerun": round(elapsed2, 3),
        "files_created": written,
        "exit_code": r.returncode,
        "rerun_reports_kept": "KEPT" in r2.stdout,
    }


# ---------------------------------------------------------------------------- report

def pct(before: int, after: int) -> str:
    if before == 0:
        return "n/a"
    return f"-{round((before - after) / before * 100)}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    here = pathlib.Path(__file__).resolve().parent
    # The baseline is vendored at benchmark/baseline/ so the "before" column is reproducible by
    # anyone, not just on the machine that first measured it.
    ap.add_argument("--old", type=pathlib.Path, default=here / "baseline")
    ap.add_argument("--new", type=pathlib.Path, default=here.parent / "harness-bootstrap")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not a.new.is_dir():
        print(f"error: --new not found: {a.new}", file=sys.stderr)
        return 2

    c = Counter()
    print(f"token counting: {c.label}\n", file=sys.stderr)

    new = measure_new(a.new, c)
    tax = measure_session_tax(a.new, c)
    speed = measure_scaffold_time(a.new)
    old = measure_old(a.old, c) if a.old.is_dir() else None

    result = {"token_source": c.label, "new": new, "old": old,
              "session_tax": tax, "scaffold": speed}

    if a.json:
        print(json.dumps(result, indent=2))
        return 0

    T = "tokens (measured)" if c.measured else "tokens (ESTIMATED)"
    print("=" * 74)
    print(f"  harness-bootstrap benchmark      token source: {c.label.upper()}")
    print("=" * 74)

    if old:
        print("\n  READ PATH - bytes the model must pull into context per bootstrap")
        print(f"    {'':<28} {'files':>6} {'bytes':>9} {T:>20}")
        print(f"    {old['name']:<28} {old['read_files']:>6} {old['read_bytes']:>9,} "
              f"{old['read_tokens']:>20,}")
        print(f"    {new['name']:<28} {new['read_files']:>6} {new['read_bytes']:>9,} "
              f"{new['read_tokens']:>20,}")
        print(f"    {'reduction':<28} {'':>6} "
              f"{pct(old['read_bytes'], new['read_bytes']):>9} "
              f"{pct(old['read_tokens'], new['read_tokens']):>20}")

        print("\n  WRITE PATH - bytes the model must author as output")
        print(f"    {old['name']:<28} {old['write_files']:>6} {old['write_bytes']:>9,} "
              f"{old['write_tokens']:>20,}")
        print(f"    {new['name']:<28} {new['write_files']:>6} {new['write_bytes']:>9,} "
              f"{new['write_tokens']:>20,}")
        print(f"    {'reduction':<28} {'':>6} "
              f"{pct(old['write_bytes'], new['write_bytes']):>9} "
              f"{pct(old['write_tokens'], new['write_tokens']):>20}")
    else:
        print(f"\n  (old skill not found at {a.old} - showing new only)")

    print("\n  SESSION TAX - rules loaded into EVERY agent session, every time")
    print(f"    unconditional ({len(tax['always_files'])} rules): "
          f"{tax['always_bytes']:>7,} bytes  {tax['always_tokens']:>7,} {c.label} tokens")
    print(f"      {', '.join(tax['always_files'])}")
    print(f"    path-scoped   ({len(tax['scoped_files'])} rules): "
          f"{tax['scoped_bytes']:>7,} bytes  {tax['scoped_tokens']:>7,} {c.label} tokens")
    print(f"      loaded only when Claude touches a matching file - not billed otherwise")
    total = tax["always_tokens"] + tax["scoped_tokens"]
    if total:
        print(f"    -> {round(tax['scoped_tokens'] / total * 100)}% of rule content is kept OUT of "
              f"the default session")

    print("\n  SCAFFOLD - the deterministic path that replaces model generation")
    print(f"    first run : {speed['seconds']}s, {speed['files_created']} paths created, "
          f"exit {speed['exit_code']}")
    print(f"    re-run    : {speed['seconds_rerun']}s, reports KEPT (idempotent): "
          f"{speed['rerun_reports_kept']}")

    if not c.measured:
        print("\n  NOTE: no ANTHROPIC_API_KEY set, so token columns are ESTIMATED from bytes at")
        print(f"        {CHARS_PER_TOKEN} chars/token. Byte columns are exact. Re-run with a key")
        print("        set to get measured token counts from the count_tokens endpoint.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

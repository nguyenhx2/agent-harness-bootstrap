#!/usr/bin/env python3
"""Deterministic scaffolder for harness-bootstrap.

Copies asset files into a target repo, substituting {{VARS}} and resolving
conditional blocks. Never overwrites an existing file unless --force: existing
files are reported as KEPT (identical) or CONFLICT (differs), which is what
brownfield reconciliation needs. Entries listed in the target's
.claude/disabled.json (written by harness-toggle.py) are reported as
DISABLED and skipped, so a re-run never resurrects a toggled-off control.

Stdlib only. No dependencies.

Usage:
    python scaffold.py --target <repo> --vars vars.json [--dry-run] [--force]
    python scaffold.py --target <repo> --vars vars.json --only claude/rules

vars.json shape:
    {
      "vars":  { "PROJECT_NAME": "acme", "DEFAULT_BRANCH": "main", ... },
      "flags": ["ui", "db", "posix"]
    }

Template syntax inside asset files:
    {{VAR_NAME}}                       -> substituted from vars
    {{#IF_UI}} ... {{/IF_UI}}          -> kept only if flag "ui" is set
    {{^IF_UI}} ... {{/IF_UI}}          -> kept only if flag "ui" is NOT set

Manifest (assets/manifest.json) entries:
    {"src": "claude/rules/frontend.md", "dest": ".claude/rules/frontend.md",
     "when": ["ui"], "subst": true, "mode": "644"}
  - "when" is an AND over flags; omit for unconditional.
  - "when_any" is an OR over flags.
  - "when_not" skips the entry if ANY listed flag is set (e.g. the split
    reviewers carry "when_not": ["solo_review"]).
  - "subst": false copies bytes verbatim (use for anything containing literal braces).

Flag validation: flags are checked against the closed set below and the run
fails (exit 1) on an unknown name, a missing or doubled OS flag, or a
contradictory combination (light with tdd/ddd; tdd/unit/e2e without tests).
HOOK_RUNNER and HOOK_EXT are DERIVED from the OS flag (windows -> powershell/
ps1, posix -> bash/sh); a conflicting value in vars.json is an error, not an
override - the hook flavor and its registration must never disagree.

Twin note: spec-builder/scripts/scaffold.py is a fork of this file with its own
manifest. Behavior fixes should land in both.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

VAR_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
BLOCK_RE = re.compile(
    r"\{\{(?P<neg>[#^])IF_(?P<flag>[A-Z0-9_]+)\}\}"
    r"(?P<body>.*?)"
    r"\{\{/IF_(?P=flag)\}\}",
    re.DOTALL,
)


class ScaffoldError(Exception):
    pass


# The closed flag set. Keep in sync with assets/manifest.json's schema comment,
# SKILL.md, and reference/intake.md - the auditors check all four agree.
KNOWN_FLAGS = {
    "ui", "db", "db_engineer", "db_seeder", "ai", "audit", "tdd", "ddd",
    "light", "unit", "e2e", "tests", "deploy_ask", "long", "solo_review",
    "windows", "posix",
}

# OS flag -> the derived hook runner/extension vars. The flavor of the shipped
# hook files and the commands registered in settings.json must never disagree;
# deriving both from one flag makes the mismatch unrepresentable.
OS_DERIVED = {
    "windows": {
        "HOOK_RUNNER": "powershell -NoProfile -ExecutionPolicy Bypass -File",
        "HOOK_EXT": "ps1",
    },
    "posix": {"HOOK_RUNNER": "bash", "HOOK_EXT": "sh"},
}


def validate_flags(flags: set[str]) -> list[str]:
    """-> list of human-readable problems; empty means the flag set is sane."""
    problems: list[str] = []
    unknown = sorted(flags - KNOWN_FLAGS)
    if unknown:
        problems.append(
            f"unknown flag(s): {', '.join(unknown)}. "
            f"Valid flags: {', '.join(sorted(KNOWN_FLAGS))}")
    os_flags = flags & {"windows", "posix"}
    if len(os_flags) != 1:
        problems.append(
            "exactly one of 'windows' or 'posix' is required "
            f"(got: {', '.join(sorted(os_flags)) or 'neither'}). "
            "Without it the hooks never register and every guardrail is dead.")
    if "light" in flags and (flags & {"tdd", "ddd"}):
        problems.append("'light' contradicts 'tdd'/'ddd': lightweight means no "
                        "methodology rule. Drop one side.")
    for f in ("tdd", "unit", "e2e"):
        if f in flags and "tests" not in flags:
            problems.append(f"'{f}' requires 'tests' (tests is the derived "
                            "master switch; intake sets it whenever unit or "
                            "e2e is chosen).")
    return problems


def resolve_blocks(text: str, flags: set[str]) -> str:
    """Resolve {{#IF_X}}/{{^IF_X}} blocks. Innermost-first via repeated passes."""
    prev = None
    while prev != text:
        prev = text

        def repl(m: re.Match[str]) -> str:
            flag = m.group("flag").lower()
            present = flag in flags
            want = m.group("neg") == "#"
            return m.group("body") if present == want else ""

        text = BLOCK_RE.sub(repl, text)
    return text


def substitute(text: str, variables: dict[str, str], src: str) -> tuple[str, set[str]]:
    """Replace {{VAR}}. Returns (text, set of vars that were missing)."""
    missing: set[str] = set()

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in variables:
            return str(variables[key])
        missing.add(key)
        return m.group(0)  # leave the placeholder visible rather than blanking it

    return VAR_RE.sub(repl, text), missing


def wanted(entry: dict, flags: set[str]) -> bool:
    need_all = entry.get("when") or []
    need_any = entry.get("when_any") or []
    need_none = entry.get("when_not") or []
    if need_all and not set(need_all).issubset(flags):
        return False
    if need_any and not (set(need_any) & flags):
        return False
    if need_none and (set(need_none) & flags):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold an agent harness into a repo.")
    ap.add_argument("--target", required=True, type=Path, help="repo root to write into")
    ap.add_argument("--vars", required=True, type=Path, help="path to vars.json")
    ap.add_argument("--assets", type=Path, default=None, help="assets dir (default: ../assets)")
    ap.add_argument("--only", default=None, help="only process entries whose src starts with this")
    ap.add_argument("--dry-run", action="store_true", help="report actions, write nothing")
    ap.add_argument("--force", action="store_true", help="overwrite CONFLICT files")
    args = ap.parse_args()

    assets = (args.assets or Path(__file__).resolve().parent.parent / "assets").resolve()
    manifest_path = assets / "manifest.json"
    if not manifest_path.is_file():
        raise ScaffoldError(f"manifest not found: {manifest_path}")

    cfg = json.loads(args.vars.read_text(encoding="utf-8"))
    variables: dict[str, str] = cfg.get("vars", {})
    flags: set[str] = {f.lower() for f in cfg.get("flags", [])}

    problems = validate_flags(flags)
    if problems:
        print("FAIL: invalid flag set in vars.json:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    # HOOK_RUNNER / HOOK_EXT are derived from the OS flag (see docstring).
    os_flag = "windows" if "windows" in flags else "posix"
    for key, derived in OS_DERIVED[os_flag].items():
        supplied = variables.get(key)
        if supplied is not None and supplied != derived:
            print(f"FAIL: vars.json sets {key}={supplied!r} but flag "
                  f"'{os_flag}' requires {derived!r}. Remove the var or fix "
                  "the flag - a mismatched hook flavor never fires.",
                  file=sys.stderr)
            return 1
        variables[key] = derived

    manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]

    target = args.target.resolve()
    target.mkdir(parents=True, exist_ok=True)

    # harness-toggle.py quarantines items and lists them here; a re-run must
    # not resurrect them. The `from` paths are dest-relative by contract.
    # Only toggleable kinds inside their own directories are honored: this file
    # is committed, so a hostile or corrupted entry naming settings.json or a
    # root file must never silently withhold that asset from a scaffold.
    TOGGLE_PREFIX = {"rule": ".claude/rules/", "command": ".claude/commands/",
                     "hook": ".claude/hooks/"}
    disabled_dests: set[str] = set()
    dj = target / ".claude" / "disabled.json"
    if dj.is_file():
        try:
            for e in json.loads(dj.read_text(encoding="utf-8")).get("disabled", []):
                if not (isinstance(e, dict) and e.get("from")):
                    continue
                frm = str(e["from"]).replace("\\", "/")
                kind = e.get("kind")
                prefix = TOGGLE_PREFIX.get(kind)
                if (prefix is None or not frm.startswith(prefix)
                        or ".." in frm or "/" in frm[len(prefix):]):
                    print(f"  [warn] disabled.json entry ignored (kind "
                          f"`{kind}`, from `{frm}`): only rules, commands, "
                          "and hooks inside their own .claude/ directories "
                          "can be disabled.", file=sys.stderr)
                    continue
                disabled_dests.add(frm)
                stem = frm.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if kind == "hook":  # both flavors of the seat
                    base = frm.rsplit("/", 1)[0]
                    disabled_dests.update({f"{base}/{stem}.sh", f"{base}/{stem}.ps1"})
        except (json.JSONDecodeError, TypeError):
            # Treating a corrupt quarantine ledger as empty would resurrect
            # every disabled control on this run. Fail loudly instead.
            print(f"FAIL: {dj} is unreadable - fix or delete it before "
                  "re-running (a corrupt ledger must not resurrect disabled "
                  "controls).", file=sys.stderr)
            return 1

    added: list[str] = []
    kept: list[str] = []
    conflicts: list[str] = []
    skipped: list[str] = []
    disabled_skips: list[str] = []
    all_missing: dict[str, set[str]] = {}

    for entry in manifest:
        src_rel = entry["src"]
        if args.only and not src_rel.startswith(args.only):
            continue
        if not wanted(entry, flags):
            skipped.append(src_rel)
            continue

        src = assets / src_rel
        if not src.is_file():
            raise ScaffoldError(f"manifest points at a missing asset: {src}")

        dest_rel = entry["dest"]
        dest_rel, _ = substitute(dest_rel, variables, src_rel)  # dest may be parameterised
        if dest_rel.replace("\\", "/") in disabled_dests:
            disabled_skips.append(dest_rel)
            continue
        dest = target / dest_rel

        do_subst = entry.get("subst", True)

        if do_subst:
            raw = src.read_text(encoding="utf-8")
            body = resolve_blocks(raw, flags)
            body, missing = substitute(body, variables, src_rel)
            if missing:
                all_missing[src_rel] = missing
            payload = body.encode("utf-8")
        else:
            payload = src.read_bytes()

        if dest.exists():
            existing = dest.read_bytes()
            if existing == payload:
                kept.append(dest_rel)
                continue
            conflicts.append(dest_rel)
            if not args.force:
                continue

        if not args.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            if entry.get("exec"):
                dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        added.append(dest_rel)

    # ---- report -------------------------------------------------------------
    def show(label: str, items: list[str]) -> None:
        if not items:
            return
        print(f"\n{label} ({len(items)}):")
        for i in sorted(items):
            print(f"  {i}")

    verb = "WOULD ADD" if args.dry_run else "ADDED"
    show(verb, added)
    show("KEPT (already identical)", kept)
    show("CONFLICT (exists and differs - not written)" if not args.force
         else "OVERWRITTEN (--force)", conflicts)
    show("DISABLED (respected - listed in .claude/disabled.json, not re-added)",
         disabled_skips)
    if skipped:
        print(f"\nSKIPPED by flags ({len(skipped)}): {', '.join(sorted(skipped)[:8])}"
              f"{' ...' if len(skipped) > 8 else ''}")

    if all_missing:
        print("\nUNRESOLVED VARIABLES - placeholders were left in place:")
        for src_rel, keys in sorted(all_missing.items()):
            print(f"  {src_rel}: {', '.join(sorted(keys))}")

    print(
        f"\nSummary: {len(added)} written, {len(kept)} kept, "
        f"{len(conflicts)} conflict, {len(skipped)} skipped by flags"
        + (f", {len(disabled_skips)} disabled (respected)." if disabled_skips
           else ".")
    )

    if conflicts and not args.force:
        print(
            "\nCONFLICTS are not an error. Brownfield rule: reconcile them by hand\n"
            "(keep-adapt-add-flag) - never clobber content the user wrote. Re-run with\n"
            "--force only for files you have decided to replace."
        )
    if all_missing:
        print("\nFAIL: unresolved variables. Add them to vars.json and re-run.")
        return 1

    # Spawn-boundary invariant: exactly one seat (the orchestrator) may hold the Agent tool.
    # A second Agent-holding seat is a second uncontrolled dispatch point - the exact escape the
    # guard-agent-spawn hook and the roster design exist to prevent. Checked here because a hand
    # edit to a roster file would otherwise ship silently.
    agents_dir = args.target / ".claude" / "agents"
    if agents_dir.is_dir():
        import re as _re
        spawners = []
        for f in sorted(agents_dir.glob("*.md")):
            head = f.read_text(encoding="utf-8", errors="replace")[:2000]
            m = _re.search(r"^tools:\s*(.+)$", head, _re.MULTILINE)
            if m and _re.search(r"(^|[,\s])Agent(,|\s|$)", m.group(1)):
                spawners.append(f.stem)
        if len(spawners) > 1:
            print(f"\nFAIL: {len(spawners)} agents hold the Agent tool: {', '.join(spawners)}.")
            print("Only the orchestrator may spawn. Remove Agent from the others' tools: line.")
            return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ScaffoldError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

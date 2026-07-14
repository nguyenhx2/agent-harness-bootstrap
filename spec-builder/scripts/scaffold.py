#!/usr/bin/env python3
"""Deterministic scaffolder for harness-bootstrap.

Copies asset files into a target repo, substituting {{VARS}} and resolving
conditional blocks. Never overwrites an existing file unless --force: existing
files are reported as KEEP (identical) or CONFLICT (differs), which is what
brownfield reconciliation needs.

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
  - "subst": false copies bytes verbatim (use for anything containing literal braces).
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
    if need_all and not set(need_all).issubset(flags):
        return False
    if need_any and not (set(need_any) & flags):
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
    manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]

    target = args.target.resolve()
    target.mkdir(parents=True, exist_ok=True)

    added: list[str] = []
    kept: list[str] = []
    conflicts: list[str] = []
    skipped: list[str] = []
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
    show("CONFLICT (exists and differs — not written)" if not args.force
         else "OVERWRITTEN (--force)", conflicts)
    if skipped:
        print(f"\nSKIPPED by flags ({len(skipped)}): {', '.join(sorted(skipped)[:8])}"
              f"{' ...' if len(skipped) > 8 else ''}")

    if all_missing:
        print("\nUNRESOLVED VARIABLES — placeholders were left in place:")
        for src_rel, keys in sorted(all_missing.items()):
            print(f"  {src_rel}: {', '.join(sorted(keys))}")

    print(
        f"\nSummary: {len(added)} written, {len(kept)} kept, "
        f"{len(conflicts)} conflict, {len(skipped)} skipped by flags."
    )

    if conflicts and not args.force:
        print(
            "\nCONFLICTS are not an error. Brownfield rule: reconcile them by hand\n"
            "(keep-adapt-add-flag) — never clobber content the user wrote. Re-run with\n"
            "--force only for files you have decided to replace."
        )
    if all_missing:
        print("\nFAIL: unresolved variables. Add them to vars.json and re-run.")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ScaffoldError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

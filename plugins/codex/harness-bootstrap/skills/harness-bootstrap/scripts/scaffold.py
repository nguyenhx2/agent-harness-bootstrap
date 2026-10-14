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
  Purpose profiles are flags too - purpose_code, purpose_research, purpose_strategy,
  purpose_docs - and combine ("flags": ["purpose_code", "purpose_docs", ...]). Naming none
  means purpose_code (see PURPOSE_FLAGS), so a vars.json written before profiles existed
  scaffolds exactly what it always did.

Per-module CLAUDE.md (optional "modules" key in vars.json):
    "modules": [{"path": "src/billing", "owner": "billing-dev",
                 "invariants": "- amounts are integer cents", "commands": "- npm test -- billing"}]
  Each entry renders assets/root/module-CLAUDE.md into <path>/CLAUDE.md - loaded by Claude Code
  only when it reads files there, so module guidance costs nothing in other sessions. An existing
  CLAUDE.md at that path is never overwritten, not even with --force, and a rendered file over
  MODULE_CLAUDE_MAX_LINES fails the run before anything is written.

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
#
# target_cursor / target_codex record which OTHER tools the harness must run in.
# There is deliberately no target_claude: the harness is GENERATED for Claude Code
# and the other two are ports of that output, so "Cursor only" is not a state this
# scaffolder can produce. They gate nothing in the manifest on purpose - what they
# buy is persistence. Intake used to ask which tools to port to and throw the
# answer away, so /harness-update's re-port step had nothing to consult and had to
# re-derive it from the tree - which no longer works, because Cursor reads
# .claude/ and CLAUDE.md natively.
KNOWN_FLAGS = {
    "ui", "db", "db_engineer", "db_seeder", "ai", "audit", "tdd", "ddd",
    "light", "unit", "e2e", "tests", "deploy_ask", "long", "solo_review",
    "windows", "posix", "terse", "rtk", "hooks_strict", "pr_cli", "target_cursor",
    "target_codex", "purpose_code", "purpose_research", "purpose_strategy", "purpose_docs",
    "merge_gate",
}

# Purpose profiles. A profile is an ordinary flag, so it gates manifest entries and template blocks
# with no second mechanism, and they combine (`purpose_code` + `purpose_docs`). A vars.json naming
# no profile gets `purpose_code`: every harness scaffolded before profiles existed was a code
# harness, and re-running /harness-update on one must not quietly drop its dev, test and review
# seats.
PURPOSE_FLAGS = ("purpose_code", "purpose_research", "purpose_strategy", "purpose_docs")
# Flags that describe code: a stack, a test suite, a methodology, a code review gate, the merge
# seat. On a repo with no `purpose_code` they would field seats with nothing to work on, so they
# are refused rather than ignored. `ui` is not here: a docs repo can have a brand and a site.
CODE_ONLY = {"db", "db_engineer", "db_seeder", "ai", "tdd", "ddd", "light", "unit", "e2e",
             "tests", "solo_review", "merge_gate"}
# Derived, never written in vars.json: `checker` is set whenever a non-code purpose is, because
# every non-code purpose shares the one read-only `checker` seat. Deriving it keeps "is a checker
# fielded" a single question for the manifest and the templates instead of an OR over three flags.
DERIVED_FLAGS = {"checker"}


def effective_flags(flags: set[str]) -> set[str]:
    """-> the flag set the scaffolder acts on: the given flags plus the derived ones."""
    out = set(flags)
    if not out & set(PURPOSE_FLAGS):
        out.add("purpose_code")
    if out & {"purpose_research", "purpose_strategy", "purpose_docs"}:
        out.add("checker")
    return out

# A per-module CLAUDE.md is read whenever a file in that module is, so it is paid for on every
# such read. It carries the owner, the scope, local invariants and local commands - nothing the
# root files already say - and this budget keeps it that small.
MODULE_CLAUDE_MAX_LINES = 40


def module_problems(modules: object) -> list[str]:
    """-> problems with the vars.json "modules" list itself (shape and path safety)."""
    if modules is None:
        return []
    if not isinstance(modules, list):
        return ['"modules" must be a list of {"path", "owner", ...} objects']
    out: list[str] = []
    for i, m in enumerate(modules):
        path = str(m.get("path", "")).replace("\\", "/").strip("/") if isinstance(m, dict) else ""
        if not path or not m.get("owner"):
            out.append(f"modules[{i}] needs a non-empty \"path\" and \"owner\"")
        elif path.startswith(("/", "~")) or ":" in path or ".." in path.split("/") \
                or path.split("/")[0] in (".claude", ".git", "docs"):
            out.append(f"modules[{i}].path `{path}` must be a relative module path inside the repo, "
                       "outside .claude/, .git/ and docs/")
    return out


def render_module_claude(template: str, module: dict, flags: set[str]) -> str:
    path = str(module["path"]).replace("\\", "/").strip("/")
    values = {
        "MODULE_NAME": str(module.get("name") or path.rsplit("/", 1)[-1]),
        "MODULE_PATH": path + "/",
        "MODULE_OWNER": str(module["owner"]),
        "MODULE_INVARIANTS": str(module.get("invariants") or "- None recorded yet. Add one when a "
                                 "rule holds here and nowhere else."),
        "MODULE_COMMANDS": str(module.get("commands") or "- The root commands apply unchanged."),
    }
    body, _ = substitute(resolve_blocks(template, flags), values, "module-CLAUDE.md")
    return body


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


def validate_flags(raw: set[str]) -> list[str]:
    """-> list of human-readable problems; empty means the flag set is sane.

    `raw` is the set as written in vars.json. Derived flags are computed here, so a check that
    depends on the default purpose sees it, and a derived flag written by hand is refused.
    """
    problems: list[str] = []
    written = sorted(raw & DERIVED_FLAGS)
    if written:
        problems.append(f"{', '.join(written)} is derived (from the purpose flags) and must not "
                        "be written in vars.json.")
    flags = effective_flags(raw - DERIVED_FLAGS)
    unknown = sorted(flags - KNOWN_FLAGS - DERIVED_FLAGS)
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
    if "purpose_code" not in flags:
        stray = sorted(flags & CODE_ONLY)
        if stray:
            problems.append(f"{', '.join(stray)} describe code, but the purpose set "
                            f"({', '.join(sorted(flags & set(PURPOSE_FLAGS)))}) has no "
                            "'purpose_code'. Add 'purpose_code' for a mixed repo, or drop them.")
    return problems


def same_content(existing: bytes, payload: bytes) -> bool:
    """True when an installed file already says what the asset says, whatever the line endings.

    This decides KEPT vs CONFLICT, and a byte comparison gets it wrong in the one situation that
    matters most: updating an existing harness to a newer skill version. `.gitattributes` checks
    this repo's text out NATIVE, so a skill cloned on Windows holds CRLF while the same skill in
    WSL, in CI, or in a zip holds LF. Bootstrap from one and update from the other and every single
    text asset differs by a byte per line - the run reports a wall of conflicts, none of them real,
    and the seven files that DID change are buried in it. A reconciliation queue nobody can read is
    a reconciliation queue nobody works.

    Only newlines are forgiven. A file the user edited still conflicts, and binary assets are
    compared byte for byte: a decode failure means "not text", where one differing byte is a real
    difference.
    """
    if existing == payload:
        return True
    try:
        return (existing.decode("utf-8").replace("\r\n", "\n")
                == payload.decode("utf-8").replace("\r\n", "\n"))
    except UnicodeDecodeError:
        return False


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
    raw_flags: set[str] = {f.lower() for f in cfg.get("flags", [])}

    problems = validate_flags(raw_flags)
    if problems:
        print("FAIL: invalid flag set in vars.json:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    flags: set[str] = effective_flags(raw_flags)

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

    pending: list[tuple[pathlib.Path, bytes, bool]] = []
    added: list[str] = []
    kept: list[str] = []
    conflicts: list[str] = []
    merged: list[str] = []
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
            if same_content(existing, payload):
                kept.append(dest_rel)
                continue
            if dest_rel.replace("\\", "/") == ".claude/settings.json" and not args.force:
                # A settings.json the user edited is never replaced, but a hook this skill version
                # ships must still get registered, or /harness-update installs a hook nothing
                # calls. Registrations are ADDED; nothing the user wrote is changed or removed.
                stems = {d.rsplit("/", 1)[-1].rsplit(".", 1)[0] for d in disabled_dests
                         if d.startswith(".claude/hooks/")}
                result = merge_hook_registrations(existing, payload, stems)
                if result is not None:
                    new_bytes, added_regs = result
                    pending.append((dest, new_bytes, False))
                    merged.append(f"{dest_rel}: registered {', '.join(added_regs)}")
            conflicts.append(dest_rel)
            if not args.force:
                continue

        pending.append((dest, payload, bool(entry.get("exec"))))
        added.append(dest_rel)

    # ---- per-module CLAUDE.md ------------------------------------------------
    module_list = cfg.get("modules")
    problems = module_problems(module_list)
    module_written: list[str] = []
    module_kept: list[str] = []
    template_path = assets / "root" / "module-CLAUDE.md"
    if module_list and not problems and template_path.is_file() and not args.only:
        template = template_path.read_text(encoding="utf-8")
        for m in module_list:
            rel = str(m["path"]).replace("\\", "/").strip("/") + "/CLAUDE.md"
            dest = target / rel
            if dest.exists():
                module_kept.append(rel)  # never overwritten: it may be the team's own
                continue
            body = render_module_claude(template, m, flags)
            n = len(body.splitlines())
            if n > MODULE_CLAUDE_MAX_LINES:
                problems.append(f"{rel} renders to {n} lines, over the {MODULE_CLAUDE_MAX_LINES}-"
                                "line budget - move detail into a path-scoped rule")
                continue
            pending.append((dest, body.encode("utf-8"), False))
            module_written.append(rel)
            added.append(rel)
    if problems:
        print("FAIL: per-module CLAUDE.md:", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        print("Nothing was written.", file=sys.stderr)
        return 1

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
    show("MODULE CLAUDE.md KEPT (exists - never overwritten)", module_kept)
    show("CONFLICT (exists and differs - not written)" if not args.force
         else "OVERWRITTEN (--force)", conflicts)
    show("DISABLED (respected - listed in .claude/disabled.json, not re-added)",
         disabled_skips)
    show("WOULD MERGE" if args.dry_run else "MERGED (hook registrations added, nothing removed)",
         merged)
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
        print("Nothing was written: the target is untouched, so a failed run cannot leave a "
              "half-built harness or a settings.json with a raw placeholder in it.")
        return 1

    if not args.dry_run:
        for dest, payload, is_exec in pending:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            if is_exec:
                dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Spawn-boundary invariant: exactly one seat (the orchestrator) may hold the Agent tool.
    # A second Agent-holding seat is a second uncontrolled dispatch point - the exact escape the
    # guard-agent-spawn hook and the roster design exist to prevent. Checked here because a hand
    # edit to a roster file would otherwise ship silently.
    agents_dir = args.target / ".claude" / "agents"
    if agents_dir.is_dir():
        import re as _re
        spawners = []
        for f in sorted(agents_dir.glob("*.md")):
            head = f.read_text(encoding="utf-8", errors="replace")[:4000]
            if holds_agent(tools_value(head)):
                spawners.append(f.stem)
        if len(spawners) > 1:
            print(f"\nFAIL: {len(spawners)} agents hold the Agent tool: {', '.join(spawners)}.")
            print("Only the orchestrator may spawn. Remove Agent from the others' tools: line.")
            return 1
    # Wiring invariant. Three separate defects shipped with the same shape: a control that is
    # INSTALLED but not WIRED. A Cursor adapter that pointed at the wrong hook flavor, a task
    # board directory no hook could find, and an audit-mode hook nothing registered. Each was
    # invisible because every test asked "is the control present", never "is it connected".
    problems = wiring_problems(args.target)
    if problems:
        print("\nFAIL: controls are installed but not wired:")
        for line in problems:
            print(f"  {line}")
        print("An unwired control looks like protection and provides none.")
        return 1
    # Integration check: every link between the parts resolves - seats named by commands and
    # tables, cited rules, hook registrations, tiers, skills, tools, purpose. Same script the
    # harness ships as .claude/scripts/harness-check.py, run from the skill's own copy.
    checker = assets / "scripts" / "harness-check.py"
    if not args.dry_run and not args.only and checker.is_file():
        import subprocess as _sp
        r = _sp.run([sys.executable, str(checker), "--target", str(target), "--stage", "scaffold"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("\n" + (r.stdout.strip() if r.returncode else r.stdout.strip().splitlines()[-1]))
        if r.returncode:
            print("\nFAIL: harness-check found links that do not resolve (file:line and the fix "
                  "are above). The files are written; fix the links before relying on them.")
            return 1
    return 0


def tools_value(head: str) -> str:
    """The `tools:` frontmatter value, inline or YAML block form, as one flat string.

    `tools: Read, Agent` and a block list of `- Agent` are both valid frontmatter, and reading
    only the inline form let a second Agent-holding seat ship undetected.
    """
    import re as _re
    m = _re.search(r"^tools:[ \t]*(.*)$", head, _re.MULTILINE)
    if not m:
        return ""
    value = m.group(1).strip()
    if value:
        return value
    out = []
    for line in head[m.end():].splitlines():
        if not line.strip():
            continue
        if _re.match(r"^[ \t]+-[ \t]*(.+)$", line):
            out.append(_re.match(r"^[ \t]+-[ \t]*(.+)$", line).group(1).strip())
            continue
        break
    return ", ".join(out)


def _hook_stems(groups: object) -> set[str]:
    """Hook script stems named anywhere in one event's list of matcher groups."""
    import re as _re
    out: set[str] = set()
    for g in groups if isinstance(groups, list) else []:
        for h in (g.get("hooks") if isinstance(g, dict) else None) or []:
            cmd = h.get("command", "") if isinstance(h, dict) else ""
            out.update(_re.findall(r"hooks/([A-Za-z0-9_-]+)\.(?:sh|ps1)", str(cmd)))
    return out


def merge_hook_registrations(existing: bytes, payload: bytes,
                             disabled: set[str]) -> tuple[bytes, list[str]] | None:
    """-> (merged settings.json, the registrations added), or None when there is nothing to add.

    Adds each hook the rendered asset registers and the installed file does not, keyed by
    (event, hook script): a hook the user registered under a different matcher, runner or timeout
    counts as present and is left exactly as they wrote it. Nothing is removed or reordered, a hook
    quarantined in disabled.json is never re-registered, and a second run finds nothing to add -
    so this is safe to run on every update. An unparseable file on either side is left alone.
    """
    try:
        cur = json.loads(existing.decode("utf-8"))
        new = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(cur, dict) or not isinstance(new, dict):
        return None
    new_hooks = new.get("hooks")
    if not isinstance(new_hooks, dict):
        return None
    cur_hooks = cur.setdefault("hooks", {})
    if not isinstance(cur_hooks, dict):
        return None
    added: list[str] = []
    for event, groups in new_hooks.items():
        have = _hook_stems(cur_hooks.get(event))
        for g in groups if isinstance(groups, list) else []:
            if not isinstance(g, dict):
                continue
            missing = []
            for h in g.get("hooks") or []:
                stems = _hook_stems([{"hooks": [h]}])
                if stems and not stems & (have | disabled):
                    missing.append(h)
                    have |= stems
            if not missing:
                continue
            target_groups = cur_hooks.setdefault(event, [])
            if not isinstance(target_groups, list):
                continue
            same = next((x for x in target_groups if isinstance(x, dict)
                         and x.get("matcher") == g.get("matcher")
                         and isinstance(x.get("hooks"), list)), None)
            if same is None:
                same = {k: v for k, v in g.items() if k != "hooks"}
                same["hooks"] = []
                target_groups.append(same)
            same["hooks"].extend(missing)
            added += [f"{event}:{s}" for h in missing for s in sorted(_hook_stems([{"hooks": [h]}]))]
    if not added:
        return None
    nl = "\r\n" if b"\r\n" in existing else "\n"
    text = json.dumps(cur, indent=2, ensure_ascii=False) + "\n"
    return text.replace("\n", nl).encode("utf-8"), added


def holds_agent(tools: str) -> bool:
    """True when a tools value grants Agent, bare or in the `Agent(a, b)` allowlist form."""
    import re as _re
    return bool(_re.search(r"(^|[,\s\[\"\'])Agent([,\s\]\"\'(]|$)", tools))


def wiring_problems(target: pathlib.Path) -> list[str]:
    """-> human-readable problems where an installed control is not connected to anything."""
    import json as _json
    out: list[str] = []
    claude = target / ".claude"
    hooks_dir = claude / "hooks"
    settings = claude / "settings.json"

    if hooks_dir.is_dir() and settings.is_file():
        try:
            blob = settings.read_text(encoding="utf-8", errors="replace")
            _json.loads(blob)
        except (OSError, ValueError):
            out.append("settings.json is not valid JSON, so no hook is registered at all")
            blob = ""
        if blob:
            installed = {f.stem for f in hooks_dir.iterdir()
                         if f.suffix in (".sh", ".ps1") and f.is_file()}
            for name in sorted(installed):
                if f"hooks/{name}." not in blob:
                    out.append(f"hook {name} is installed but never registered in settings.json")

    # Directories the shipped guards key off. guard-agent-spawn refuses a write dispatch when the
    # board is absent, which is only safe because the board is always created.
    for rel in ("docs/tasks/active", "docs/tasks/pending"):
        if not (target / rel).is_dir():
            out.append(f"{rel}/ is missing, and a shipped hook keys off it")
    # Seat wiring is checked by harness-check, which runs at the end of every scaffold.
    return out


# The seat checks - tools, maxTurns, model and effort, the single spawner, read-only review seats,
# memory on a review seat, the tier table, cited rules and named seats - live in ONE place:
# assets/scripts/harness-check.py, which the harness also ships. This wrapper asks it for exactly
# those checks, so the scaffold and the shipped checker can never disagree about a seat.
SEAT_CHECKS = {"seat-frontmatter", "review-readonly", "tier-table", "cite-missing", "agent-ref"}


def seat_problems(target: pathlib.Path) -> list[str]:
    """-> the seat findings harness-check reports for `target`, one line each (file:line message)."""
    import importlib.util as _ilu
    checker = Path(__file__).resolve().parent.parent / "assets" / "scripts" / "harness-check.py"
    spec = _ilu.spec_from_file_location("_harness_check", checker)
    if spec is None or spec.loader is None:
        return [f"harness-check not found at {checker} - the seat checks cannot run"]
    hc = _ilu.module_from_spec(spec)
    spec.loader.exec_module(hc)
    return [f"{f.file}:{f.line} {f.message}" for f in hc.run(Path(target), "scaffold")
            if f.check in SEAT_CHECKS]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ScaffoldError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

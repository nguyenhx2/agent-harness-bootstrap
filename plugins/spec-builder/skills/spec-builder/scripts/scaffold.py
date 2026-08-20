#!/usr/bin/env python3
"""Deterministic scaffolder for spec-builder.

Twin fork of harness-bootstrap/scripts/scaffold.py - same engine, separate
manifest. A fix to the engine belongs in both files.

Copies the spec section templates into a target repo, substituting {{VARS}} and
resolving conditional blocks. Never overwrites an existing file unless --force:
existing files are reported as KEPT (identical) or CONFLICT (differs), which is
what reconciliation on an existing spec set needs.

Sections are SELECTIVE, and the selection has to be a recorded decision before
anything is written: see the section-selection gate below.

Stdlib only. No dependencies.

Usage:
    python scaffold.py --target <repo> --vars vars.json [--dry-run] [--force]
    python scaffold.py --target <repo> --vars vars.json --only specs/
    python scaffold.py --target <repo> --vars vars.json --module BLG:billing --module CAT:catalog

vars.json shape:
    {
      "vars":  { "PROJECT_NAME": "acme", "PROJECT_SLUG": "acme",
                 "PROJECT_PURPOSE": "...", "DOC_OWNER": "..." },
      "flags": ["ai", "ui", "db", "flows", "access", "integration",
                "assumptions", "feasibility", "design", "stakeholders"]
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


# The closed set this skill actually understands. Every one is consumed by a manifest `when`
# or by an {{#IF_}} block in a template. Without this check a typo silently dropped a whole
# spec section and still exited 0, which is the same failure the harness twin was hardened
# against.
KNOWN_FLAGS = {"access", "ai", "db", "design", "feasibility", "flows",
               "integration", "stakeholders", "ui"}


def validate_flags(flags: set[str]) -> list[str]:
    """-> list of human-readable problems; empty means the flag set is sane."""
    unknown = sorted(flags - KNOWN_FLAGS)
    if not unknown:
        return []
    return [f"unknown flag(s): {', '.join(unknown)}. "
            f"Valid flags: {', '.join(sorted(KNOWN_FLAGS))}"]


# ---------------------------------------------------------------- section-selection gate
# Sections are selective. Which optional ones a project gets is a JUDGEMENT, and this
# scaffolder refuses to act on an unrecorded one. The decision lives in the target repo at
# docs/specs/.sections.json, written during elicitation, before any section is scaffolded:
#
#     {
#       "version": 1,
#       "selected": {"02-stakeholders": "the transcript names five stakeholder groups"},
#       "excluded": {"10-ui-ux-wireframes": "batch service, the source shows no screens"},
#       "decided_by": "elicitation"          // or "user-explicit"
#     }
#
# The rules, all enforced below:
#   - core sections (README, 01, 03, 05, 07, 11, 13) appear in NEITHER map: they are not
#     decisions, so a reason for them would be theatre;
#   - every OPTIONAL section the manifest knows appears in EXACTLY ONE map - no silent
#     omissions, because an omission is exactly the unrecorded decision this gate exists
#     to catch;
#   - every reason is non-empty and grounded in the source material or in a choice the
#     user made outright;
#   - "selected" and vars.json's flags say the same thing, since the flags are what
#     actually decide the files on disk.
#
# Why a file and not a paragraph: reference/elicitation.md has specified the setup batch
# (one AskUserQuestion, multi-select, core fixed and not offered) since v1.8.0, and a real
# run skipped it and scaffolded all fourteen sections flat. Every empty section shipped
# that way erodes trust in the filled ones, and the user never got asked. A rule that
# lives only in instructions is skippable; the repo's answer is a mechanism that refuses.
SECTIONS_DIR = "docs/specs"
SECTIONS_STATE = f"{SECTIONS_DIR}/.sections.json"
DECIDED_BY = {"elicitation", "user-explicit"}


def section_map(manifest: list[dict]) -> tuple[dict[str, set[str]], list[str]]:
    """Split the manifest's docs/specs/ entries into optional and core.

    -> ({section key: the flags that gate it}, [core section keys]). A section's key is
    its filename stem, which is the name .sections.json uses: derived from the manifest,
    never a second hand-maintained list that could disagree with it.
    """
    optional: dict[str, set[str]] = {}
    core: list[str] = []
    for entry in manifest:
        dest = str(entry["dest"]).replace("\\", "/")
        if not dest.startswith(SECTIONS_DIR + "/"):
            continue
        key = Path(dest).stem
        gates = set(entry.get("when") or []) | set(entry.get("when_any") or [])
        if gates:
            optional[key] = gates
        else:
            core.append(key)
    return optional, sorted(core)


def check_selection(target: Path, optional: dict[str, set[str]], core: list[str],
                    flags: set[str]) -> list[str]:
    """-> list of human-readable problems; empty means the selection may be scaffolded."""
    state = target / SECTIONS_STATE
    if not state.is_file():
        return [f"{SECTIONS_STATE} is missing: the section selection was never recorded."]
    try:
        doc = json.loads(state.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return [f"{SECTIONS_STATE} is not readable JSON: {e}"]
    if not isinstance(doc, dict):
        return [f"{SECTIONS_STATE} must be a JSON object, not {type(doc).__name__}."]

    problems: list[str] = []
    selected = doc.get("selected")
    excluded = doc.get("excluded")
    for name, m in (("selected", selected), ("excluded", excluded)):
        if not isinstance(m, dict):
            problems.append(f'{SECTIONS_STATE}: "{name}" must be an object mapping '
                            f"section -> reason.")
    if problems:
        return problems
    decided = doc.get("decided_by")
    if decided not in DECIDED_BY:
        problems.append(f'{SECTIONS_STATE}: "decided_by" is {decided!r}; it must be one '
                        f"of {', '.join(sorted(DECIDED_BY))}.")

    known = set(optional)
    for name, m in (("selected", selected), ("excluded", excluded)):
        for key, reason in sorted(m.items()):
            if key in core:
                problems.append(f'{SECTIONS_STATE}: "{name}" lists the core section '
                                f"`{key}`. Core sections are installed always and are "
                                f"not decisions - remove it.")
            elif key not in known:
                problems.append(f'{SECTIONS_STATE}: "{name}" lists `{key}`, which is not '
                                f"an optional section in this manifest. Known: "
                                f"{', '.join(sorted(known))}.")
            if not isinstance(reason, str) or not reason.strip():
                problems.append(f'{SECTIONS_STATE}: `{key}` in "{name}" has no reason. '
                                f"Every decision carries a one-line reason grounded in "
                                f"the source material or in the user's explicit choice.")

    for key in sorted(known):
        in_sel, in_exc = key in selected, key in excluded
        if in_sel and in_exc:
            problems.append(f"{SECTIONS_STATE}: `{key}` is in both selected and excluded. "
                            f"Each optional section belongs to exactly one.")
        elif not in_sel and not in_exc:
            problems.append(f"{SECTIONS_STATE}: `{key}` is in neither selected nor "
                            f"excluded. A section nobody decided about is the failure this "
                            f"gate exists to catch - decide it, with a reason.")

    # The flags are what actually put files on disk, so a disagreement between them and the
    # recorded decision means one of the two is a lie, and there is no safe way to guess which.
    for key in sorted(known):
        gate = optional[key]
        have = gate & flags
        if key in selected and not have:
            problems.append(f"vars.json disagrees with the selection: `{key}` is selected "
                            f"but none of its flag(s) {', '.join(sorted(gate))} is set, so "
                            f"the scaffolder would skip it.")
        if key in excluded and have:
            problems.append(f"vars.json disagrees with the selection: `{key}` is excluded "
                            f"but flag(s) {', '.join(sorted(have))} are set, so the "
                            f"scaffolder would write it anyway.")
    return problems


def refuse_selection(target: Path, problems: list[str],
                     optional: dict[str, set[str]]) -> None:
    print("FAIL: the section selection is not recorded, so nothing was written.",
          file=sys.stderr)
    for p in problems:
        print(f"  {p}", file=sys.stderr)
    print(
        f"\nWhat to produce, before re-running:\n"
        f"  {(target / SECTIONS_STATE).as_posix()}\n"
        f'  {{"version": 1,\n'
        f'   "selected": {{"<section>": "<one-line reason from the source material>"}},\n'
        f'   "excluded": {{"<section>": "<one-line reason>"}},\n'
        f'   "decided_by": "elicitation"}}   // or "user-explicit"\n'
        f"\nEvery one of these optional sections goes in exactly one map, with a reason:\n"
        f"  {', '.join(sorted(optional))}\n"
        f"Core sections go in neither. `selected` must match vars.json's flags "
        f"({'; '.join(f'{k} -> {", ".join(sorted(v))}' for k, v in sorted(optional.items()))}).\n"
        f"\nHow the decision is reached: reference/elicitation.md, the setup batch - one\n"
        f"AskUserQuestion, multi-select, core fixed and not offered, each optional section\n"
        f"pre-selected only where the source material shows it is real.",
        file=sys.stderr)


# ---------------------------------------------------------------------------- module folders
# A spec set that covers more than one product module puts each module's OWN sections under
# docs/specs/modules/<folder>/ and leaves the cross-cutting ones at the root. Which sections are
# module-owned is a property of what they describe, not of the manifest, so it is stated here:
# 05/07/08/09/10 describe one module's behaviour, data, interfaces and screens; the README index,
# 01, 03, 11 and 13 describe the product. 12 ships at the root by default and is moved by hand
# when the buildability risk belongs to one module alone (writing-rules.md, "Module folders").
#
# The IDs inside a module folder carry the module's code (FR-BLG-01), because the docs graph is
# flat: two modules that each define a bare FR-01 collapse into one node. The scaffolder exposes
# {{MODULE_CODE}} and {{MODULE_NAME}} so a template can say so in the module's own terms.
MODULE_SECTIONS = {
    "05-functional-requirements",
    "07-non-functional-requirements",
    "08-data-model",
    "09-integration-interface",
    "10-ui-ux-wireframes",
}
MODULES_DIR = f"{SECTIONS_DIR}/modules"
MODULE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,3}$")     # 2-4 chars, first a letter
MODULE_FOLDER_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_modules(specs: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """`CODE:folder` strings -> ([(code, folder)], problems). Order is preserved."""
    modules: list[tuple[str, str]] = []
    problems: list[str] = []
    for spec in specs:
        code, sep, folder = spec.partition(":")
        if not sep or not folder:
            problems.append(f"--module {spec!r}: expected CODE:folder-name, e.g. BLG:billing.")
            continue
        if not MODULE_CODE_RE.match(code):
            problems.append(f"--module {spec!r}: `{code}` is not a module code. Codes are 2-4 "
                            f"uppercase [A-Z0-9] with a letter first (BLG, CAT, PAY2) - the "
                            f"same shape the ID segment and the docs-graph regex accept.")
            continue
        if not MODULE_FOLDER_RE.match(folder):
            problems.append(f"--module {spec!r}: `{folder}` is not a folder name. Use lowercase "
                            f"letters, digits, and hyphens.")
            continue
        for seen_code, seen_folder in modules:
            if seen_code == code:
                problems.append(f"--module {spec!r}: code `{code}` was already given for "
                                f"`{seen_folder}`. One code, one module - a shared code makes "
                                f"two modules' IDs collide, which is what the code prevents.")
            if seen_folder == folder:
                problems.append(f"--module {spec!r}: folder `{folder}` was already given for "
                                f"code `{seen_code}`.")
        modules.append((code, folder))
    return modules, problems


def dest_plan(dest_rel: str, modules: list[tuple[str, str]]) -> list[tuple[str, dict[str, str]]]:
    """One manifest dest -> the paths to write, each with its extra template variables.

    Without --module, and for every cross-cutting section, that is the dest unchanged and no
    extra variables. A module-owned section becomes one copy per module under modules/<folder>/.
    """
    if not modules:
        return [(dest_rel, {})]
    prefix = SECTIONS_DIR + "/"
    if not dest_rel.startswith(prefix) or "/" in dest_rel[len(prefix):]:
        return [(dest_rel, {})]                       # not a top-level docs/specs/ section
    if Path(dest_rel).stem not in MODULE_SECTIONS:
        return [(dest_rel, {})]
    name = Path(dest_rel).name
    return [(f"{MODULES_DIR}/{folder}/{name}",
             {"MODULE_CODE": code, "MODULE_NAME": folder})
            for code, folder in modules]


def modularize(text: str, code: str) -> str:
    """Seed a module copy's sample IDs with the module's code, and re-root its links.

    A freshly scaffolded module set otherwise reproduces the exact hazard the module segment
    exists to prevent: every module's copy of 05 carries the template's bare `FR-01`, so two
    unfilled modules collide in the docs graph until an author renumbers by hand. And the
    templates' relative links (`04-business-flows.md`, `12-technical-feasibility.md`) point at
    ROOT sections, which from `modules/<folder>/` is two directories up - left as-is they are
    dead links in every module copy.

    Only the prefixes DEFINED in module-owned sections are seeded (FR, UC, US, INT, SCR, and
    NFR's category form). BF, DS, DT, SH, OI, AS, CO, DP and R are defined in root sections and
    stay bare - prefixing them would invent IDs that nothing defines. HTML comments are left
    untouched: they are template guidance that describes both forms, and injecting the code
    there would garble the explanation of the flat form.
    """
    stashed: list[str] = []

    def stash(m: "re.Match[str]") -> str:
        stashed.append(m.group(0))
        return f"\x00C{len(stashed) - 1}\x00"

    text = re.sub(r"<!--.*?-->", stash, text, flags=re.S)
    # Bare numeric form only, so the transform cannot double-inject an already-seeded ID.
    text = re.sub(r"\b(FR|UC|US|INT|SCR)-(\d{1,5})\b", rf"\1-{code}-\2", text)
    text = re.sub(r"\b(NFR)-([A-Z]{2,4})-(\d{1,5})\b", rf"\1-{code}-\2-\3", text)
    # Anchors are the lowercase twin of the same IDs ({#fr-01}, (#fr-01), ...md#fr-01).
    text = re.sub(r"#(fr|uc|us|int|scr)-(\d{1,5})\b", rf"#\1-{code.lower()}-\2", text)

    def reroot(m: "re.Match[str]") -> str:
        target = m.group(2)
        stem = target.split("#", 1)[0]
        stem = stem[:-3] if stem.endswith(".md") else stem
        if stem not in MODULE_SECTIONS:
            return m.group(1) + "../../" + target
        return m.group(0)

    # Markdown links to sibling section files: module-owned targets stay siblings (the module
    # folder holds its own copy), cross-cutting targets live at the spec root, two levels up.
    text = re.sub(r"(\]\()((?:README|\d\d-)[A-Za-z0-9-]*\.md(?:#[A-Za-z0-9-]+)?)(?=\))",
                  reroot, text)
    for i, c in enumerate(stashed):
        text = text.replace(f"\x00C{i}\x00", c)
    return text


def wanted(entry: dict, flags: set[str]) -> bool:
    need_all = entry.get("when") or []
    need_any = entry.get("when_any") or []
    if need_all and not set(need_all).issubset(flags):
        return False
    if need_any and not (set(need_any) & flags):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold the spec section set into a repo.")
    ap.add_argument("--target", required=True, type=Path, help="repo root to write into")
    ap.add_argument("--vars", required=True, type=Path, help="path to vars.json")
    ap.add_argument("--assets", type=Path, default=None, help="assets dir (default: ../assets)")
    ap.add_argument("--only", default=None, help="only process entries whose src starts with this")
    ap.add_argument("--module", action="append", default=[], metavar="CODE:folder",
                    help="repeatable: scaffold the module-owned sections (05, 07, 08, 09, 10) "
                         "into docs/specs/modules/<folder>/, once per module. CODE is the ID "
                         "segment those sections' IDs carry (BLG -> FR-BLG-01)")
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
    flag_problems = validate_flags(flags)
    if flag_problems:
        for problem in flag_problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1

    modules, module_problems = parse_modules(args.module)
    if module_problems:
        for problem in module_problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]

    target = args.target.resolve()

    # The gate runs before target.mkdir and before a single byte is written, and it covers
    # --dry-run too: a dry run reports what a real run would install, so it has to be
    # answering for the same recorded decision. Non-section assets (the slash commands) are
    # not section decisions - a run scoped away from docs/specs/ passes through untouched.
    optional_sections, core_sections = section_map(manifest)
    sections_in_scope = any(
        (not args.only or str(e["src"]).startswith(args.only))
        and str(e["dest"]).replace("\\", "/").startswith(SECTIONS_DIR + "/")
        for e in manifest
    )
    if sections_in_scope:
        problems = check_selection(target, optional_sections, core_sections, flags)
        if problems:
            refuse_selection(target, problems, optional_sections)
            return 1

    target.mkdir(parents=True, exist_ok=True)

    added: list[str] = []
    kept: list[str] = []
    conflicts: list[str] = []
    skipped: list[str] = []
    all_missing: dict[str, set[str]] = {}

    # This skill writes into .claude/commands/, the same namespace harness-toggle.py
    # quarantines. Without this, `/harness-toggle disable command/spec-ingest` was undone by
    # the next spec-builder run, silently. Only rules, commands and hooks inside their own
    # .claude/ directory may be honored: a ledger entry naming a root file must never
    # withhold an asset from a scaffold.
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
                    print(f"  [warn] disabled.json entry ignored (kind `{kind}`, from "
                          f"`{frm}`): only rules, commands, and hooks inside their own "
                          ".claude/ directories can be disabled.", file=sys.stderr)
                    continue
                disabled_dests.add(frm)
        except (json.JSONDecodeError, TypeError, AttributeError):
            print(f"FAIL: {dj} is unreadable - fix or delete it before re-running (a corrupt "
                  "ledger must not resurrect disabled controls).", file=sys.stderr)
            return 1

    disabled_skips: list[str] = []

    for entry in manifest:
        src_rel = entry["src"]
        if args.only and not src_rel.startswith(args.only):
            continue
        if not wanted(entry, flags):
            skipped.append(src_rel)
            continue
        if entry["dest"].replace("\\", "/") in disabled_dests:
            disabled_skips.append(entry["dest"])
            continue

        src = assets / src_rel
        if not src.is_file():
            raise ScaffoldError(f"manifest points at a missing asset: {src}")

        dest_rel = entry["dest"]
        dest_rel, _ = substitute(dest_rel, variables, src_rel)  # dest may be parameterised
        do_subst = entry.get("subst", True)

        # One manifest entry can land in several places: a module-owned section is written once
        # per --module. Without --module this is the single unchanged dest it always was.
        for dest_rel, module_vars in dest_plan(dest_rel.replace("\\", "/"), modules):
            dest = target / dest_rel

            if do_subst:
                raw = src.read_text(encoding="utf-8")
                body = resolve_blocks(raw, flags)
                body, missing = substitute(body, {**variables, **module_vars}, src_rel)
                if missing:
                    all_missing.setdefault(src_rel, set()).update(missing)
                if module_vars:
                    body = modularize(body, module_vars["MODULE_CODE"])
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
    show("DISABLED (respected - listed in .claude/disabled.json, not re-added)", disabled_skips)
    show("CONFLICT (exists and differs - not written)" if not args.force
         else "OVERWRITTEN (--force)", conflicts)
    if modules:
        print("\nMODULE FORM - the module-owned sections were written once per module:")
        for code, folder in modules:
            print(f"  {code} -> {MODULES_DIR}/{folder}/   (its IDs carry -{code}-: FR-{code}-01)")
        print(f"  cross-cutting sections stayed at {SECTIONS_DIR}/. Declare the code -> folder "
              f"map in {SECTIONS_DIR}/README.md.")
    if skipped:
        print(f"\nSKIPPED by flags ({len(skipped)}): {', '.join(sorted(skipped)[:8])}"
              f"{' ...' if len(skipped) > 8 else ''}")

    if all_missing:
        print("\nUNRESOLVED VARIABLES - placeholders were left in place:")
        for src_rel, keys in sorted(all_missing.items()):
            print(f"  {src_rel}: {', '.join(sorted(keys))}")

    print(
        f"\nSummary: {len(added)} written, {len(kept)} kept, "
        f"{len(conflicts)} conflict, {len(skipped)} skipped by flags, "
        f"{len(disabled_skips)} disabled."
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
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ScaffoldError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

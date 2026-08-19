#!/usr/bin/env python3
"""Prove spec-builder's section-selection gate refuses, on real runs of the real scaffolder.

Since v1.8.0 the spec sections are selective: a core seven always, eight more only when the
source material shows they are real. Which optional ones a project gets was specified in
reference/elicitation.md as a setup batch - one AskUserQuestion, multi-select, core fixed and
not offered - and in a real run the model skipped the batch entirely and scaffolded all
fourteen sections flat. Nobody was asked, and every empty section shipped that way erodes
trust in the filled ones. The rule lived only in prose, and prose is skippable.

So the decision became an artifact the scaffolder demands: <target>/docs/specs/.sections.json,
one reason per optional section, agreeing with vars.json's flags. This file exists to prove
that demand is real, because a gate nobody exercises is indistinguishable from no gate:

  1. no .sections.json                 -> refuses, writes nothing
  2. complete and consistent           -> scaffolds, and the sections on disk are exactly
                                          core + selected
  3. a selected section with no reason -> refuses
  4. flags contradicting "selected"    -> refuses
  5. a section in neither map          -> refuses
  6. --module BLG:billing, valid       -> scaffolds, and the module-owned sections land under
                                          modules/billing/ while the cross-cutting ones stay at
                                          the root, each written exactly once

Every case runs the shipped scaffold.py in a throwaway directory, so what is checked is the
behaviour a user gets, not a re-implementation of it. Each refusal must fire for ITS OWN
reason - a marker string from its own branch - because a gate that refuses everything with
one message would pass a test that only counts exit codes, and would be just as broken. The
run exits 1 with DEAD CHECK if any refusal branch stays silent, and equally if case 2 is
refused: a gate that never accepts is a gate nobody will keep.

    python scripts/check_sections.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "spec-builder"
SCAFFOLD = SKILL / "scripts" / "scaffold.py"

# The four variables every spec template substitutes. An unresolved {{VAR}} is its own
# non-zero exit, which would make the accept case pass or fail for the wrong reason.
VARS = {
    "PROJECT_NAME": "GateFixture",
    "PROJECT_SLUG": "gate_fixture",
    "PROJECT_PURPOSE": "a throwaway target for the section-selection gate",
    "DOC_OWNER": "check_sections.py",
}


def load_scaffold():
    """The shipped scaffolder as a module - its own constants, never a second copy of them."""
    sys.path.insert(0, str(SKILL / "scripts"))
    import scaffold  # noqa: E402

    return scaffold


def manifest_sections() -> tuple[dict[str, set[str]], list[str]]:
    """(optional section -> gating flags, core sections), read with the scaffolder's own
    splitter so this check cannot drift from what a real run installs."""
    manifest = json.loads((SKILL / "assets" / "manifest.json")
                          .read_text(encoding="utf-8"))["files"]
    return load_scaffold().section_map(manifest)


def write_json(path: pathlib.Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8", newline="\n")


def run_scaffold(target: pathlib.Path, flags: list[str],
                 extra: list[str] | None = None) -> subprocess.CompletedProcess:
    vars_path = target.parent / "vars.json"
    write_json(vars_path, {"vars": VARS, "flags": flags})
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), "--target", str(target), "--vars", str(vars_path),
         *(extra or [])],
        capture_output=True, text=True, cwd=ROOT)


def sections_on_disk(target: pathlib.Path) -> set[str]:
    d = target / "docs" / "specs"
    if not d.is_dir():
        return set()
    return {p.stem for p in d.iterdir()
            if (p.suffix == ".md" or p.is_dir()) and p.name != "modules"}


def module_sections_on_disk(target: pathlib.Path, folder: str) -> set[str]:
    d = target / "docs" / "specs" / "modules" / folder
    if not d.is_dir():
        return set()
    return {p.stem for p in d.iterdir() if p.suffix == ".md" or p.is_dir()}


def case(name: str, selection: dict | None, flags: list[str],
         extra: list[str] | None = None,
         inspect=None) -> tuple[int, str, set[str], object]:
    """Run one fixture end to end -> (returncode, stderr+stdout, root sections, inspect(target))."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="check_sections_"))
    try:
        target = tmp / "repo"
        target.mkdir()
        if selection is not None:
            write_json(target / "docs" / "specs" / ".sections.json", selection)
        r = run_scaffold(target, flags, extra)
        return (r.returncode, (r.stderr or "") + (r.stdout or ""),
                sections_on_disk(target), inspect(target) if inspect else None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    optional, core = manifest_sections()
    print(f"  manifest: {len(core)} core section(s), {len(optional)} optional")
    print(f"    core      {', '.join(core)}")
    print(f"    optional  {', '.join(f'{k} <- {"/".join(sorted(v))}'
                                     for k, v in sorted(optional.items()))}")

    # The accepted selection: two optional sections in, the rest out, every one with a
    # reason. `ai` is a content flag that gates no section file; it rides along to prove the
    # gate judges section flags only and does not trip over the others.
    chosen = ["02-stakeholders", "08-data-model"]
    chosen = [k for k in chosen if k in optional] or sorted(optional)[:2]
    good = {
        "version": 1,
        "selected": {k: "the source material names it outright" for k in chosen},
        "excluded": {k: "the source shows nothing of the kind"
                     for k in sorted(optional) if k not in chosen},
        "decided_by": "elicitation",
    }
    good_flags = sorted({f for k in chosen for f in optional[k]} | {"ai"})

    def mutate(**kw) -> dict:
        d = json.loads(json.dumps(good))
        d.update(kw)
        return d

    empty_reason = mutate(selected={k: ("" if i == 0 else "reason")
                                    for i, k in enumerate(chosen)})
    omitted = mutate(excluded={k: v for k, v in good["excluded"].items()
                               if k != sorted(good["excluded"])[0]})
    dropped = sorted(good["excluded"])[0]

    bad = 0

    # ---- case 1: no artifact at all -------------------------------------------------
    rc, out, wrote, _ = case("absent", None, good_flags)
    absent_fired = rc != 0 and ".sections.json is missing" in out
    print("\n  1. no .sections.json")
    print(f"    {'ok  ' if absent_fired else 'FAIL'} refused (exit {rc}) naming the "
          f"missing artifact")
    print(f"    {'ok  ' if not wrote else 'FAIL'} wrote nothing "
          f"({len(wrote)} section(s) on disk)")
    bad += (not absent_fired) + bool(wrote)

    # ---- case 2: the accept path ----------------------------------------------------
    rc, out, wrote, _ = case("good", good, good_flags)
    want = set(core) | set(chosen)
    print("\n  2. complete and consistent")
    print(f"    {'ok  ' if rc == 0 else 'FAIL'} scaffolded (exit {rc})")
    print(f"    {'ok  ' if wrote == want else 'FAIL'} sections on disk == core + selected")
    if wrote != want:
        print(f"      wanted   {', '.join(sorted(want))}")
        print(f"      got      {', '.join(sorted(wrote)) or '(none)'}")
    accept_fired = rc == 0 and wrote == want
    bad += not accept_fired

    # ---- case 3: a selected section with an empty reason ----------------------------
    rc, out, wrote, _ = case("empty-reason", empty_reason, good_flags)
    reason_fired = rc != 0 and "has no reason" in out
    print("\n  3. a selected section with an empty reason")
    print(f"    {'ok  ' if reason_fired else 'FAIL'} refused (exit {rc}) naming the "
          f"missing reason")
    print(f"    {'ok  ' if not wrote else 'FAIL'} wrote nothing")
    bad += (not reason_fired) + bool(wrote)

    # ---- case 4: flags contradicting the recorded selection -------------------------
    # Selection unchanged, one selected section's flag removed: the scaffolder would have
    # skipped a section the record says was chosen.
    starved = [f for f in good_flags if f not in optional[chosen[0]]]
    rc, out, wrote, _ = case("flag-mismatch", good, starved)
    flag_fired = rc != 0 and "vars.json disagrees with the selection" in out
    print("\n  4. vars.json flags contradicting \"selected\"")
    print(f"    {'ok  ' if flag_fired else 'FAIL'} refused (exit {rc}) naming the "
          f"disagreement")
    print(f"    {'ok  ' if not wrote else 'FAIL'} wrote nothing")
    bad += (not flag_fired) + bool(wrote)

    # ---- case 5: an optional section in neither map ---------------------------------
    rc, out, wrote, _ = case("omitted", omitted, good_flags)
    omit_fired = rc != 0 and f"`{dropped}` is in neither" in out
    print("\n  5. an optional section in neither map")
    print(f"    {'ok  ' if omit_fired else 'FAIL'} refused (exit {rc}) naming `{dropped}`")
    print(f"    {'ok  ' if not wrote else 'FAIL'} wrote nothing")
    bad += (not omit_fired) + bool(wrote)

    # ---- case 6: module form ---------------------------------------------------------
    # Same recorded selection, same flags: the module axis is orthogonal to it. Selection is
    # still per SECTION - a selected section is scaffolded for EVERY named module - so what
    # has to be proved here is placement, not a second decision: module-owned sections under
    # modules/billing/, cross-cutting ones at the root, and neither set appearing twice.
    scaffold = load_scaffold()
    module_owned = scaffold.MODULE_SECTIONS
    want_module = (set(core) | set(chosen)) & module_owned
    want_root = (set(core) | set(chosen)) - module_owned
    rc, out, wrote, in_module = case("module", good, good_flags,
                                     extra=["--module", "BLG:billing"],
                                     inspect=lambda t: module_sections_on_disk(t, "billing"))
    placed = in_module == want_module and wrote == want_root
    print("\n  6. module form (--module BLG:billing)")
    print(f"    {'ok  ' if rc == 0 else 'FAIL'} scaffolded (exit {rc})")
    print(f"    {'ok  ' if in_module == want_module else 'FAIL'} modules/billing/ holds the "
          f"module-owned selected sections")
    print(f"    {'ok  ' if wrote == want_root else 'FAIL'} the root holds the cross-cutting "
          f"ones, and none of the module-owned ones")
    if not placed:
        print(f"      wanted in modules/billing/  {', '.join(sorted(want_module))}")
        print(f"      got                         {', '.join(sorted(in_module)) or '(none)'}")
        print(f"      wanted at the root          {', '.join(sorted(want_root))}")
        print(f"      got                         {', '.join(sorted(wrote)) or '(none)'}")
    module_fired = rc == 0 and placed
    bad += not module_fired

    # The same placement predicate, on a flat run: modules/billing/ must be EMPTY there. This
    # is what makes case 6 falsifiable - an assertion that holds with and without --module
    # would prove nothing about --module, and would pass a scaffolder that ignored the flag.
    _rc, _out, _wrote, flat_module = case("module-control", good, good_flags,
                                          inspect=lambda t: module_sections_on_disk(t, "billing"))
    control_fired = not flat_module
    print(f"    {'ok  ' if control_fired else 'FAIL'} without --module the same folder is "
          f"empty ({', '.join(sorted(flat_module)) or 'empty'}) - the assertion can fail")
    bad += not control_fired

    # ---- self-test -------------------------------------------------------------------
    # Each refusal branch has to fire for its own reason, and the accept path has to
    # accept. A branch that stays silent is a gate the model can walk straight past, and it
    # looks identical to a passing check from the outside.
    dead = [name for name, fired in (
        ("missing artifact", absent_fired),
        ("empty reason", reason_fired),
        ("flag/selection disagreement", flag_fired),
        ("undecided section", omit_fired),
        ("accepts a valid selection", accept_fired),
        ("places module-owned sections under modules/<folder>/", module_fired),
        ("the module placement assertion is falsifiable (flat control)", control_fired),
    ) if not fired]
    if dead:
        print("\n  DEAD CHECK - the gate did not exercise these branches:")
        for d in dead:
            print(f"    {d}")
        print("  A branch that cannot fire is a rule that is not enforced.")
        return 1
    print("\n  self-test: every refusal branch fired for its own reason, and the valid "
          "selection was accepted.")

    if bad:
        print(f"\n  {bad} problem(s). The section-selection gate is not holding.")
        return 1
    print("  the section-selection gate holds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

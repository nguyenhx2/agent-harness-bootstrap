#!/usr/bin/env python3
"""Gate the requirement-ID table against the docs-graph regex that is supposed to recognise it.

`spec-builder/reference/writing-rules.md` carries the authoring table of requirement-ID prefixes
(`FR-nn`, `NFR-XXX-nn`, `BR-xx`, ...). `harness-bootstrap/assets/scripts/docs-graph.py` carries a
second, independent statement of the same set: the `_ID_CORE` regex that decides which IDs the
traceability graph can even see. writing-rules.md says of the table: "when a prefix is added here,
add it ... in harness-bootstrap's `docs-graph.py` ID regex in the same change - the graph cannot
trace an ID it does not scan for." That sentence was the entire enforcement mechanism. Nothing
checked it, and a change that widens `_ID_CORE` is coming.

The failure this lets through is silent both ways:
  - a prefix added to the table but not to the regex: those IDs are invisible to the docs graph,
    with no error, no orphan entry, nothing - the graph just never mentions them.
  - a prefix added to the regex without a table row: docs-graph.py starts scanning for an ID
    scheme spec-builder never documented, which either matches noise or nothing.

Both directions are checked here, against the SAME table rows and the SAME regex text the two
source files actually contain - parsed out of them, never retyped by hand.

    python scripts/check_id_table.py

Exit 0 = every table prefix is matched by the regex and every regex member has a table row (modulo
the documented EXCEPTIONS below). Exit 1 = the two have drifted, or the SELF-TEST proves this
checker itself cannot detect drift (a "DEAD CHECK", per this repo's check-script convention).
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WRITING_RULES = ROOT / "spec-builder/reference/writing-rules.md"
DOCS_GRAPH = ROOT / "harness-bootstrap/assets/scripts/docs-graph.py"

# Prefixes that legitimately appear in docs-graph.py's _ID_CORE but have no row in
# spec-builder's writing-rules.md table. Verified, not assumed, before being added here:
#   - ADR: architecture decision records. Defined by harness-bootstrap's OWN docs conventions
#     (docs/adr/, referenced from harness-bootstrap templates), not by spec-builder's spec set.
#     Confirmed absent from the writing-rules.md table (searched the table text for "ADR" - no row).
#   - TASK: task files under docs/tasks/, likewise a harness-bootstrap docs convention, not a
#     spec-builder requirement type. Confirmed absent from the writing-rules.md table.
#   - R (risk) is deliberately NOT here: `R-xx` IS a real writing-rules.md table row ("Risk"), so
#     exempting it would hide a genuine desync instead of documenting a real exception. Checked
#     first, specifically because the obvious reading of "R" as "reference-only" is wrong here.
EXCEPTIONS = {
    "ADR": "harness-side ID (architecture decision record) - defined by harness-bootstrap's own "
           "docs conventions, not spec-builder's ID table",
    "TASK": "harness-side ID (task file) - defined by harness-bootstrap's own docs conventions, "
            "not spec-builder's ID table",
}


def parse_table(text: str) -> list[tuple[str, str, str]]:
    """Pull (raw_pattern, bare_prefix, sample_id) out of the writing-rules.md ID table.

    Scoped to the '## IDs and anchors' section specifically, not the whole file: other sections
    use backticks for code examples too, and matching those would fabricate prefixes nobody wrote.
    Fails loudly if the section or its rows cannot be found, rather than silently checking zero
    prefixes and reporting a clean pass on an empty set.
    """
    m = re.search(r"## IDs and anchors\n(.*?)\n##[ \t]", text, re.S)
    if not m:
        sys.exit(
            "FAIL  writing-rules.md: '## IDs and anchors' section (or the heading that follows "
            "it) was not found - update check_id_table.py's section anchor; the sync gate cannot "
            "see the table at all right now."
        )
    section = m.group(1)
    raw_patterns = re.findall(r"^\|\s*`([^`]+)`\s*\|", section, re.M)
    if not raw_patterns:
        sys.exit(
            "FAIL  writing-rules.md: the IDs and anchors table has no backticked prefix rows - "
            "update check_id_table.py's row pattern; the sync gate cannot see the table at all "
            "right now."
        )
    entries = []
    for raw in raw_patterns:
        parts = raw.split("-")
        bare = parts[0]
        if len(parts) == 2:
            # FR-nn, UC-xx, R-xx, ... -> a plain "PREFIX-nn" pattern.
            sample = f"{bare}-01"
        elif len(parts) == 3:
            # NFR-XXX-nn: the middle segment is a category placeholder (writing-rules.md spells
            # out PERF/SEC/REL/USE/SCA/MNT for NFR). SEC stands in as one concrete category so the
            # sample is a real, fully-formed ID rather than the literal placeholder text.
            sample = f"{bare}-SEC-01"
        else:
            sys.exit(
                f"FAIL  writing-rules.md: prefix pattern `{raw}` has an unexpected shape (not "
                "2 or 3 '-'-separated segments) - teach parse_table() this new shape before "
                "trusting the check."
            )
        entries.append((raw, bare, sample))
    return entries


def extract_id_core(text: str) -> str:
    """Pull the _ID_CORE pattern text out of docs-graph.py's own source.

    Reads and regex-matches the assignment line rather than importing the module, so this check
    has no dependency on docs-graph.py's other imports or side effects. Fails loudly if the
    assignment line is gone or reshaped - never silently treats a missing regex as an empty one.
    """
    m = re.search(r'^_ID_CORE\s*=\s*r"(.*)"\s*$', text, re.M)
    if not m:
        sys.exit(
            "FAIL  docs-graph.py: no line of the form _ID_CORE = r\"...\" was found - update "
            "check_id_table.py's extraction; the sync gate cannot see the regex at all right now."
        )
    return m.group(1)


def alternation_members(id_core: str) -> list[str]:
    """Split the outer (?: A|B|C )-\\d{1,5} alternation into its raw member strings.

    Paren-depth aware, because NFR's member nests its own optional group
    (NFR(?:-[A-Z]{2,4})?) - a naive split on '|' would cut that group in half.
    """
    if not id_core.startswith("(?:"):
        sys.exit(
            f"FAIL  docs-graph.py: _ID_CORE does not start with the expected '(?:' alternation - "
            f"got {id_core!r}. Update alternation_members() for the new shape."
        )
    depth = 0
    end = None
    for i, ch in enumerate(id_core):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        sys.exit(
            f"FAIL  docs-graph.py: unbalanced parentheses while parsing _ID_CORE - got {id_core!r}."
        )
    body = id_core[3:end]
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "|" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def bare_prefix_of_member(member: str) -> str:
    m = re.match(r"^[A-Za-z]+", member)
    if not m:
        sys.exit(
            f"FAIL  docs-graph.py: regex alternative `{member}` has no leading letters to read a "
            "prefix from - update bare_prefix_of_member()."
        )
    return m.group(0)


def check_direction_a(entries: list[tuple[str, str, str]], id_core: str) -> list[str]:
    """Every table prefix's sample ID must be matched IN FULL by the regex."""
    problems = []
    for raw, _bare, sample in entries:
        if re.fullmatch(id_core, sample) is None:
            problems.append(
                f"writing-rules.md table prefix `{raw}` (sample `{sample}`) is NOT matched by "
                f"docs-graph.py's _ID_CORE"
            )
    return problems


def check_direction_b(
    members: list[tuple[str, str]], table_bare_prefixes: set[str], exceptions: dict[str, str]
) -> list[str]:
    """Every alternation member must correspond to a table row, except a documented exception."""
    problems = []
    for raw_member, bare in members:
        if bare in table_bare_prefixes or bare in exceptions:
            continue
        problems.append(
            f"docs-graph.py's _ID_CORE alternates on `{bare}` (from `{raw_member}`), which has "
            f"no row in writing-rules.md's IDs table and no EXCEPTIONS entry"
        )
    return problems


# ---------------------------------------------------------------------------------------------
# Self-test fixtures: synthetic table text + synthetic docs-graph.py text, run through the exact
# same parse_table / extract_id_core / alternation_members / check_direction_* functions used on
# the real files. Never the real prefixes, so a self-test failure can never be confused with a
# real desync.
# ---------------------------------------------------------------------------------------------

_SYNTH_TABLE_BOTH = """
## IDs and anchors

| Prefix | Meaning | Anchor form |
|--------|---------|-------------|
| `ZZ-nn` | Synthetic requirement | - |
| `YY-XXX-nn` | Synthetic categorised requirement | - |

## Next section
"""

_SYNTH_TABLE_ONLY_ZZ = """
## IDs and anchors

| Prefix | Meaning | Anchor form |
|--------|---------|-------------|
| `ZZ-nn` | Synthetic requirement | - |

## Next section
"""

_SYNTH_DOCS_GRAPH_BOTH = r'''
_ID_CORE = r"(?:YY(?:-[A-Z]{2,4})?|ZZ)-\d{1,5}"
'''

_SYNTH_DOCS_GRAPH_MISSING_ZZ = r'''
_ID_CORE = r"(?:YY(?:-[A-Z]{2,4})?)-\d{1,5}"
'''


def self_test() -> list[str]:
    """Prove each detector branch can actually fire, on synthetic input, before trusting it on
    the real files. A pattern or comparison that never fires looks identical to a clean pass -
    that is exactly the failure mode this repo's check scripts exist to rule out."""
    dead: list[str] = []

    entries_both = parse_table(_SYNTH_TABLE_BOTH)
    id_core_both = extract_id_core(_SYNTH_DOCS_GRAPH_BOTH)
    members_both = [(m, bare_prefix_of_member(m)) for m in alternation_members(id_core_both)]
    table_bare_both = {bare for _raw, bare, _sample in entries_both}

    # (a) clean pass: table {YY, ZZ} vs regex {YY, ZZ} - both directions must report nothing.
    probs_a_clean = check_direction_a(entries_both, id_core_both)
    probs_b_clean = check_direction_b(members_both, table_bare_both, {})
    if probs_a_clean or probs_b_clean:
        dead.append(
            "self-test (a) clean pass: matched synthetic table+regex produced problem(s) "
            f"{probs_a_clean + probs_b_clean!r} - a clean pair must report nothing"
        )

    # (b) a table prefix the regex misses: same table (has ZZ), regex missing ZZ entirely.
    id_core_missing_zz = extract_id_core(_SYNTH_DOCS_GRAPH_MISSING_ZZ)
    probs_a_missing = check_direction_a(entries_both, id_core_missing_zz)
    if not probs_a_missing:
        dead.append(
            "DEAD CHECK - direction A (table prefix missing from regex): a table prefix the "
            "regex cannot match produced NO problem, so this branch can never fail"
        )

    # (c) a regex member the table lacks: regex has {YY, ZZ}, table has only ZZ.
    entries_only_zz = parse_table(_SYNTH_TABLE_ONLY_ZZ)
    table_bare_only_zz = {bare for _raw, bare, _sample in entries_only_zz}
    probs_b_missing = check_direction_b(members_both, table_bare_only_zz, {})
    if not probs_b_missing:
        dead.append(
            "DEAD CHECK - direction B (regex member missing from table): a regex member with no "
            "table row produced NO problem, so this branch can never fail"
        )

    return dead


def main() -> int:
    print("  self-test (synthetic table + synthetic regex, every branch must fire):")
    dead = self_test()
    if dead:
        print("\n  DEAD CHECK - this checker cannot be trusted on the real files:")
        for d in dead:
            print(f"    {d}")
        return 1
    print("    ok    clean pass, missing-from-regex, and missing-from-table all fire correctly")

    if not WRITING_RULES.is_file():
        sys.exit(f"FAIL  {WRITING_RULES} does not exist")
    if not DOCS_GRAPH.is_file():
        sys.exit(f"FAIL  {DOCS_GRAPH} does not exist")

    table_text = WRITING_RULES.read_text(encoding="utf-8")
    graph_text = DOCS_GRAPH.read_text(encoding="utf-8")

    entries = parse_table(table_text)
    id_core = extract_id_core(graph_text)
    members = [(m, bare_prefix_of_member(m)) for m in alternation_members(id_core)]
    table_bare = {bare for _raw, bare, _sample in entries}

    wr_rel = WRITING_RULES.relative_to(ROOT).as_posix()
    dg_rel = DOCS_GRAPH.relative_to(ROOT).as_posix()

    print(f"\n  direction A - every {wr_rel} table prefix must be matched by {dg_rel}'s _ID_CORE:")
    probs_a = check_direction_a(entries, id_core)
    for raw, _bare, sample in entries:
        if not any(raw in p for p in probs_a):
            print(f"    ok    `{raw}` (sample `{sample}`) matched")
    for p in probs_a:
        print(f"    FAIL  {wr_rel}: {p}")

    print(f"\n  direction B - every {dg_rel} alternation member must have a {wr_rel} table row "
          "(or a documented exception):")
    probs_b = check_direction_b(members, table_bare, EXCEPTIONS)
    for raw_member, bare in members:
        if bare in table_bare:
            print(f"    ok    `{bare}` (from `{raw_member}`) has a table row")
        elif bare in EXCEPTIONS:
            print(f"    ok    `{bare}` (from `{raw_member}`) is EXCEPTED - {EXCEPTIONS[bare]}")
    for p in probs_b:
        print(f"    FAIL  {dg_rel}: {p}")

    problems = probs_a + probs_b
    if problems:
        print(f"\n  {len(problems)} mismatch(es) between the ID table and the docs-graph regex.")
        print("  Fix whichever side is behind: add the missing table row, or widen/narrow "
              "_ID_CORE, in the same change.")
        return 1

    print("\n  the ID table and the docs-graph regex agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

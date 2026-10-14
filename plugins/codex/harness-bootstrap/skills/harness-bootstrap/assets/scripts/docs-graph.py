#!/usr/bin/env python3
"""Check the DOCS traceability graph: which documents define which IDs, and who references whom.

The documentation twin of code-graph.py: the code map answers "may this module import that one",
this answers "which spec section, requirement, ADR and task talk about the same thing, and which
IDs nothing else ever mentions". Stdlib only.

Output:
  .claude/state/docs-graph.json    machine-readable: docs, ids (defined_in, mentioned_in), edges,
                                   orphan_ids. Query it (or grep) for "who references FR-12".
  stdout                           the counts and the orphan-ID list - the only part a reader acts on.

It writes no Markdown and no picture. A mermaid rendering of every reference edge grows with the
square of a real spec tree and costs an agent tens of thousands of tokens to read, while the orphan
list is the part anyone acts on - so that is what is printed.

An edge A -> B means document A mentions an ID that document B defines (defines = B holds the
ID's heading or table row, or failing that the most occurrences). An ID mentioned once and
referenced nowhere is an orphan: unstarted work, or a dead reference.

Usage:
  python .claude/scripts/docs-graph.py             # build the JSON, print orphans
  python .claude/scripts/docs-graph.py --check     # same, exit 1 if any orphan exists
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict

DOC_DIRS = ("docs",)
SKIP_PARTS = {"node_modules", ".git"}
# Skip the generated maps (docs-graph.md is no longer written, but older installs carry one),
# not the whole directory that holds them. Excluding
# docs/context/ also excluded business-rules.md, which is where every BR-NN is defined, so the
# graph attributed each BR to whichever other doc happened to mention it and the real definer
# never appeared at all.
SKIP_FILES = {"code-graph.md", "docs-graph.md"}
# The ID shape, left to right:
#   PREFIX            the alternation below; NFR carries its own optional CATEGORY segment
#                     inside its alternative (NFR-SEC-01), which is why NFR is written first
#   (?:-MODULE)?      one optional module segment, 2-4 chars [A-Z0-9] with a letter first, open
#                     to EVERY prefix: FR-BLG-01, UC-PAY-03, NFR-BLG-SEC-01 (module, then
#                     category - that order, per writing-rules.md)
#   -\d{1,5}          the number, which is what anchors the whole match: it is why a plain
#                     capitalised phrase like FR-THE-BEST matches nothing, and why the module
#                     segment cannot swallow the number (a segment must start with a letter)
# A repo that never adopted modules is unaffected - the flat form FR-01 stays valid forever.
# Keep in sync with spec-builder/reference/writing-rules.md's ID table; scripts/check_id_table.py
# gates the two against each other, module segment included.
_ID_CORE = r"(?:NFR(?:-[A-Z][A-Z0-9]{1,3})?|FR|BR|US|UC|OI|AS|ADR|TASK|DP|CO|INT|SCR|BF|SH|DS|DT|R)(?:-[A-Z][A-Z0-9]{1,3})?-\d{1,5}"
ID_RE = re.compile(r"\b" + _ID_CORE + r"\b")
DEFINING_HINT = re.compile(r"^\s*(?:#{1,6}\s.*|\|\s*)?\b(?P<id>" + _ID_CORE + r")\b")


def doc_files(root: pathlib.Path) -> list[pathlib.Path]:
    out = []
    for d in DOC_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            if set(p.relative_to(root).parts) & SKIP_PARTS:
                continue
            if p.name in SKIP_FILES:
                continue
            out.append(p)
    return out


def build(root: pathlib.Path) -> dict:
    files = doc_files(root)
    mentions: dict[str, dict[str, int]] = defaultdict(dict)   # id -> {doc: count}
    definers: dict[str, str] = {}                              # id -> doc that defines it
    define_score: dict[str, dict[str, int]] = defaultdict(dict)

    for f in files:
        rel = f.relative_to(root).as_posix()
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in ID_RE.finditer(text):
            full = m.group(0)
            mentions[full][rel] = mentions[full].get(rel, 0) + 1
        for line in text.splitlines():
            dm = DEFINING_HINT.match(line)
            if dm and (line.lstrip().startswith("#") or line.lstrip().startswith("|")):
                full = dm.group("id")
                define_score[full][rel] = define_score[full].get(rel, 0) + 2

    for full, docs in mentions.items():
        scored = {d: docs[d] + define_score.get(full, {}).get(d, 0) for d in docs}
        definers[full] = max(scored, key=lambda d: (scored[d], -len(d)))

    edges: dict[tuple[str, str], int] = defaultdict(int)
    for full, docs in mentions.items():
        home = definers[full]
        for d in docs:
            if d != home:
                edges[(d, home)] += 1

    orphans = sorted(full for full, docs in mentions.items()
                     if len(docs) == 1 and sum(docs.values()) <= 1)

    return {
        "docs": sorted({d for docs in mentions.values() for d in docs} | {f.relative_to(root).as_posix() for f in files}),
        # No generated_at here. These outputs are tracked in git and are prompt-cache
        # prefix content: one volatile byte cold-misses the cache on every later run and
        # turns every docs edit into a timestamp-only diff.
        "ids": {full: {"defined_in": definers[full], "mentioned_in": sorted(docs)}
                for full, docs in sorted(mentions.items())},
        "edges": [{"from": a, "to": b, "refs": n} for (a, b), n in sorted(edges.items())],
        "orphan_ids": orphans,
    }


def write_outputs(root: pathlib.Path, graph: dict) -> None:
    state = root / ".claude" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "docs-graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--check", action="store_true", help="exit 1 if orphan IDs exist")
    args = ap.parse_args()
    root = args.target.resolve()
    graph = build(root)
    write_outputs(root, graph)
    print(f"docs-graph: {len(graph['docs'])} docs, {len(graph['ids'])} IDs, "
          f"{len(graph['edges'])} edges, {len(graph['orphan_ids'])} orphan(s) "
          f"-> .claude/state/docs-graph.json")
    for i in graph["orphan_ids"]:
        print(f"  orphan {i}  (only in {graph['ids'][i]['defined_in']})")
    if args.check and graph["orphan_ids"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

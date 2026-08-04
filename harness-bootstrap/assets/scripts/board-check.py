#!/usr/bin/env python3
"""Validate the task board: frontmatter enums and dependency cycles.

Stdlib only, no install step - same discipline as `.claude/scripts/code-graph.py`. Scans
`docs/tasks/**/*.md` (excluding the board index and any README) for the frontmatter fields the
state machine in `docs/templates/TASK.md` depends on, and reports every violation rather than
stopping at the first one:

  - `status`   must be one of the five canonical states: Planned, Active, Blocked, Pending, Done.
  - `attempts` must be an integer 0-3 (the anti-loop cap in task-control.md).
  - `priority` must be one of P0, P1, P2.
  - `human_gate` may appear only on a task whose `status` is Blocked - it marks "needs a human
    decision", not an ordinary blocker, and on any other status it is a contradiction.
  - `deps`     every named TASK-NNN must resolve to a real task file, and the deps graph across
    every task file on the board must be acyclic - a cycle means no task in it can ever start.

Exits 1 with a findings list on any violation, 0 with a clean bill otherwise. `/board-audit` runs
this first: its own sweeps assume well-formed frontmatter, and a malformed board makes them
unreliable in ways that look like false negatives.

Usage:
    python .claude/scripts/board-check.py [--target <repo>]
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

VALID_STATUS = {"Planned", "Active", "Blocked", "Pending", "Done"}
VALID_PRIORITY = {"P0", "P1", "P2"}
SKIP_NAMES = {"master-plan.md", "README.md"}

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
TASK_CODE = re.compile(r"TASK-\d+")


def task_files(root: pathlib.Path) -> list[pathlib.Path]:
    tasks_dir = root / "docs" / "tasks"
    if not tasks_dir.is_dir():
        return []
    return [p for p in sorted(tasks_dir.rglob("*.md")) if p.name not in SKIP_NAMES]


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER.match(text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if km:
            fm[km.group(1)] = km.group(2).strip()
    return fm


def task_code(path: pathlib.Path, fm: dict[str, str]) -> str:
    m = TASK_CODE.match(path.stem)
    if m:
        return m.group(0)
    tm = TASK_CODE.search(fm.get("title", ""))
    return tm.group(0) if tm else path.stem


def parse_deps(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw or raw == "-":
        return []
    return TASK_CODE.findall(raw)


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """DFS cycle detection with a recursion-safe explicit understanding: WHITE = unseen,
    GRAY = on the current path, BLACK = fully explored. A back-edge to a GRAY node is a cycle."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    cycles: list[list[str]] = []
    stack: list[str] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph.get(node, []):
            if nxt not in color:
                continue  # dangling dep, reported separately below
            if color[nxt] == GRAY:
                i = stack.index(nxt)
                cycles.append(stack[i:] + [nxt])
            elif color[nxt] == WHITE:
                visit(nxt)
        stack.pop()
        color[node] = BLACK

    for n in list(graph):
        if color[n] == WHITE:
            visit(n)
    return cycles


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    args = ap.parse_args()
    root = args.target.resolve()

    files = task_files(root)
    findings: list[str] = []
    graph: dict[str, list[str]] = {}
    codes: dict[str, pathlib.Path] = {}
    records: list[tuple[str, str, dict[str, str]]] = []

    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        code = task_code(p, fm)
        rel = p.relative_to(root).as_posix()
        codes[code] = p
        records.append((rel, code, fm))

    for rel, code, fm in records:
        status = fm.get("status")
        if status is not None and status not in VALID_STATUS:
            findings.append(f"{rel}: status '{status}' is not one of {sorted(VALID_STATUS)}")

        attempts = fm.get("attempts")
        if attempts is not None and (not re.fullmatch(r"\d+", attempts) or not (0 <= int(attempts) <= 3)):
            findings.append(f"{rel}: attempts '{attempts}' is not an integer 0-3")

        priority = fm.get("priority")
        if priority is not None and priority not in VALID_PRIORITY:
            findings.append(f"{rel}: priority '{priority}' is not one of {sorted(VALID_PRIORITY)}")

        human_gate = fm.get("human_gate")
        if human_gate and human_gate not in ("", "-") and status != "Blocked":
            findings.append(
                f"{rel}: human_gate is set but status is '{status}', not Blocked - human_gate "
                "only marks a Blocked task that needs a human decision"
            )

        graph[code] = parse_deps(fm.get("deps", ""))

    known_codes = set(codes)
    for rel, code, _fm in records:
        for d in graph.get(code, []):
            if d not in known_codes:
                findings.append(f"{rel}: deps names {d}, which has no task file on the board")

    for cycle in find_cycles(graph):
        findings.append(f"dependency cycle: {' -> '.join(cycle)}")

    if findings:
        print(f"board-check: {len(findings)} finding(s)")
        for f in findings:
            print(f"  - {f}")
        return 1

    print(f"board-check: {len(files)} task file(s), board clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

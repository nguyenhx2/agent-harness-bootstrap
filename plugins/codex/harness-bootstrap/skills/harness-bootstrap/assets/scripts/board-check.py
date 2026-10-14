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
  - drift      the folder a file sits in matches its `status:` (Planned/Active/Blocked in active/,
    Pending in pending/, Done in done/), its row in `docs/tasks/master-plan.md` carries the same
    status, every task file has a row and every row has a file. `/board-audit` used to have a model
    read every file to find this; it is deterministic, so it is checked here.

Exits 1 with a findings list on any violation, 0 with a clean bill otherwise. `/board-audit` runs
this first: its own sweeps assume well-formed frontmatter, and a malformed board makes them
unreliable in ways that look like false negatives.

Usage:
    python .claude/scripts/board-check.py [--target <repo>]
    python .claude/scripts/board-check.py --self-test
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

VALID_STATUS = {"Planned", "Active", "Blocked", "Pending", "Done"}
VALID_PRIORITY = {"P0", "P1", "P2"}
SKIP_NAMES = {"master-plan.md", "README.md"}
SKIP_DIRS = {"log"}  # docs/tasks/log/ holds archived session logs (task.py), not task files
FOLDER = {"Planned": "active", "Active": "active", "Blocked": "active",
          "Pending": "pending", "Done": "done"}
ROW = re.compile(r"^\|\s*(TASK-\d+)\s*\|")

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
TASK_CODE = re.compile(r"TASK-\d+")


def task_files(root: pathlib.Path) -> list[pathlib.Path]:
    tasks_dir = root / "docs" / "tasks"
    if not tasks_dir.is_dir():
        return []
    return [p for p in sorted(tasks_dir.rglob("*.md"))
            if p.name not in SKIP_NAMES
            and not SKIP_DIRS & set(p.relative_to(tasks_dir).parts[:-1])]


def board_rows(root: pathlib.Path) -> dict[str, str] | None:
    """TASK code -> the Status cell of its master-plan row. A `<placeholder>` title is the
    template's example row, not a task. None when there is no board file at all."""
    index = root / "docs" / "tasks" / "master-plan.md"
    if not index.is_file():
        return None
    rows: dict[str, str] = {}
    for line in index.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) > 1 and cells[1].startswith("<"):
            continue
        rows[m.group(1)] = cells[-1]
    return rows


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


def check(root: pathlib.Path) -> tuple[int, list[str]]:
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

    rows = board_rows(root)
    for rel, code, fm in records:
        status = fm.get("status")
        folder = pathlib.PurePosixPath(rel).parent.name
        if status in FOLDER and folder in FOLDER.values() and FOLDER[status] != folder:
            findings.append(f"{rel}: status {status} belongs in docs/tasks/{FOLDER[status]}/, "
                            f"not {folder}/")
        if rows is None or not TASK_CODE.fullmatch(code):
            continue
        if code not in rows:
            findings.append(f"{rel}: {code} has no row in docs/tasks/master-plan.md")
        elif status is not None and rows[code] != status:
            findings.append(f"{rel}: status {status} but the master-plan row says {rows[code]}")
    for code in sorted(set(rows or {}) - set(codes)):
        findings.append(f"docs/tasks/master-plan.md: row {code} has no task file")
    return len(files), findings


def self_test() -> list[str]:
    """Each detector must fire on a board built to trip it, and stay quiet on a clean one."""
    import tempfile
    dead: list[str] = []

    def task(code: str, status: str, extra: str = "") -> str:
        return (f"---\ntitle: \"{code}: t\"\nstatus: {status}\ndeps: -\nattempts: 0\n"
                f"priority: P1\n{extra}---\n\n# {code}\n")

    clean = {"active/TASK-001-a.md": task("TASK-001", "Active"),
             "done/TASK-002-b.md": task("TASK-002", "Done")}
    board = ("## Task index\n\n| Task | Title | Status |\n|---|---|---|\n"
             "| TASK-001 | a | Active |\n| TASK-002 | b | Done |\n")
    cyc_a = task("TASK-001", "Active").replace("deps: -", "deps: TASK-002")
    cyc_b = task("TASK-002", "Done").replace("deps: -", "deps: TASK-001")
    cases = {
        "clean board": ({}, None, 0),
        "bad status enum": ({"active/TASK-001-a.md": task("TASK-001", "Doing")}, None, 1),
        "attempts over the cap": ({"active/TASK-001-a.md": task("TASK-001", "Active").replace(
            "attempts: 0", "attempts: 4")}, None, 1),
        "bad priority": ({"active/TASK-001-a.md": task("TASK-001", "Active").replace(
            "priority: P1", "priority: P7")}, None, 1),
        "human_gate on a non-Blocked task": ({"active/TASK-001-a.md": task(
            "TASK-001", "Active", "human_gate: pricing\n")}, None, 1),
        "dangling dependency": ({"active/TASK-001-a.md": task("TASK-001", "Active").replace(
            "deps: -", "deps: TASK-404")}, None, 1),
        "dependency cycle": ({"active/TASK-001-a.md": cyc_a, "done/TASK-002-b.md": cyc_b},
                             None, 1),
        "file in the wrong folder": ({"active/TASK-002-b.md": task("TASK-002", "Done"),
                                      "done/TASK-002-b.md": None}, None, 1),
        "row disagrees with file": ({}, board.replace("| a | Active |", "| a | Planned |"), 1),
        "row with no file": ({}, board + "| TASK-009 | ghost | Active |\n", 1),
        "file with no row": ({"active/TASK-003-c.md": task("TASK-003", "Planned")}, None, 1),
        "template placeholder row": ({}, board + "| TASK-003 | <first task> | Planned |\n", 0),
        # Front matter that would be a finding if the archive were scanned as a task file.
        "log archive is not a task": ({"log/log-TASK-001.md": "---\nstatus: Archived\n---\n"},
                                      None, 0),
    }
    for name, (over, brd, want) in cases.items():
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            files = dict(clean)
            files.update(over)
            for rel, body in files.items():
                if body is None:
                    continue
                f = root / "docs" / "tasks" / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(body, encoding="utf-8")
            (root / "docs/tasks/master-plan.md").write_text(brd or board, encoding="utf-8")
            _n, findings = check(root)
            if bool(findings) != bool(want):
                dead.append(f"{name}: expected {'findings' if want else 'clean'}, got "
                            f"{findings or 'clean'}")
    return dead


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        dead = self_test()
        for d in dead:
            print(f"board-check self-test: DEAD - {d}")
        print("board-check self-test: " + ("FAILED" if dead else "ok"))
        return 1 if dead else 0

    n, findings = check(args.target.resolve())
    if findings:
        print(f"board-check: {len(findings)} finding(s)")
        for f in findings:
            print(f"  - {f}")
        return 1

    print(f"board-check: {n} task file(s), board clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

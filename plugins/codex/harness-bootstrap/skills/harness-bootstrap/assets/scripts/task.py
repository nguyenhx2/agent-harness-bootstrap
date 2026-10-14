#!/usr/bin/env python3
"""The task board CLI: every state change in one command, so the file, its folder and its board row
can never disagree.

Stdlib only, no install step - same discipline as `board-check.py`. A status change used to be four
hand edits (frontmatter, folder, board row, session-log row) plus a read-back, and the step most
often skipped was the one that mattered: a merge or a forgotten edit left the board saying one
thing and the file another. Here one command does all of it, then re-reads the board row and
fails loudly if the write did not land.

    task.py new "<title>" --owner <agent> --requested-by "<what was asked>" \
        --criterion "<observable outcome>" --criterion "<another>" \
        [--goal ...] [--deps TASK-001,TASK-002] [--priority P1] [--phase 1] [--fr FR-03] \
        [--files "src/billing/**"]
    task.py move <TASK-NNN> <Planned|Active|Blocked|Pending|Done> [--note "..."] [--who <agent>]
        [--human-gate "<reason>"]           Blocked, Pending and Done require --note (the blocker
                                            and who clears it / why parked / the result).
    task.py attempt <TASK-NNN> --reason <infra|scope|env> --note "..." [--who <agent>]
    task.py log <TASK-NNN> "<what was done>" "<result>" [--who <agent>]
    task.py gate <TASK-NNN> <gate> <pass|fail> [--files <path>]...
                                            record a gate result in the verify ledger and the log
    task.py checkpoint <TASK-NNN> [--next "..."] [--green [SHA]] [--question "..."]... [--clear-questions]
    task.py resume [TASK-NNN]              the compact state /task-resume reads instead of the log
    task.py list [state]
    task.py check                          board-check.py: enums, deps, and board-vs-file drift
    task.py --self-test

Session logs are bounded: the task file keeps the newest LOG_KEEP rows and folds older ones into
docs/tasks/log/log-TASK-NNN.md, leaving one pointer row. The archive is committed - it is still
the evidence - but it is no longer loaded every time the task is resumed.

Exit codes: 0 ok, 1 refused or verification failed, 2 usage error.
"""
from __future__ import annotations

import argparse
import datetime
import os
import pathlib
import re
import subprocess
import sys
import tempfile

# Importing a sibling script must not leave bytecode in .claude/scripts/: a stray .pyc there
# is an untracked file, and verify-plan.py would ask for a review of it.
sys.dont_write_bytecode = True

STATES = ("Planned", "Active", "Blocked", "Pending", "Done")
FOLDER = {"Planned": "active", "Active": "active", "Blocked": "active",
          "Pending": "pending", "Done": "done"}
NOTE_REQUIRED = {"Blocked", "Pending", "Done"}
PRIORITIES = ("P0", "P1", "P2")
ATTEMPT_CAP = 3
LOG_KEEP = 20          # session-log rows kept in the task file; older rows go to the archive
RESUME_LOG_ROWS = 5    # rows `resume` prints

# Same refusals as the guard-task-scope hook, because this command writes the file through Python,
# where no Edit|Write hook sees it. The CLI must not become the way around the gate.
LABELS = {"user", "the user", "agent", "orchestrator", "claude", "assistant"}
PLACEHOLDERS = {"", "-", "tbd", "todo", "n/a"}

TASK_RE = re.compile(r"^TASK-\d+$")
ROW_RE = re.compile(r"^\|\s*(TASK-\d+)\s*\|")
LOG_HEADING = "## Session log"
CHECKPOINT_HEADING = "## Checkpoint"
POINTER_MARK = "earlier rows archived to "


class Refused(Exception):
    """A request the board's rules do not allow. Exit 1 with the message."""


# ------------------------------------------------------------------------------------- file io

def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def write_atomic(p: pathlib.Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".task-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, p)


def today() -> str:
    return datetime.date.today().isoformat()


def cell(s: str) -> str:
    """A value safe inside one markdown table cell."""
    return " ".join(s.replace("|", "/").split())


# ----------------------------------------------------------------------------------- the board

class Board:
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.tasks = root / "docs" / "tasks"
        self.index = self.tasks / "master-plan.md"
        self.template = root / "docs" / "templates" / "TASK.md"
        self.archive = self.tasks / "log"

    # -- lookup
    def files(self) -> list[pathlib.Path]:
        out = []
        for folder in ("active", "pending", "done"):
            d = self.tasks / folder
            if d.is_dir():
                out += sorted(d.glob("TASK-*.md"))
        return out

    def find(self, code: str) -> pathlib.Path:
        if not TASK_RE.match(code):
            raise Refused(f"'{code}' is not a task code (TASK-NNN)")
        hits = [p for p in self.files() if re.match(rf"^{re.escape(code)}(-|\.md$)", p.name)]
        if not hits:
            raise Refused(f"{code}: no task file in docs/tasks/active, pending or done")
        if len(hits) > 1:
            raise Refused(f"{code}: {len(hits)} files claim this code: "
                          + ", ".join(self.rel(h) for h in hits) + " - fix the collision first")
        return hits[0]

    def rel(self, p: pathlib.Path) -> str:
        return p.relative_to(self.root).as_posix()

    # -- board rows
    def rows(self) -> dict[str, list[str]]:
        """TASK code -> the row's cells, for real rows only (a `<placeholder>` title is skipped)."""
        if not self.index.is_file():
            return {}
        out = {}
        for line in read(self.index).splitlines():
            m = ROW_RE.match(line)
            if not m:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[1].startswith("<"):
                continue
            out[m.group(1)] = cells
        return out

    def row_status(self, code: str) -> str | None:
        cells = self.rows().get(code)
        return cells[-1] if cells else None

    def set_row_status(self, code: str, status: str) -> None:
        text = read(self.index)
        lines, hit = text.split("\n"), False
        for i, line in enumerate(lines):
            m = ROW_RE.match(line)
            if m and m.group(1) == code:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                cells[-1] = status
                lines[i] = "| " + " | ".join(cells) + " |"
                hit = True
        if not hit:
            raise Refused(f"{code}: no row in {self.rel(self.index)} - the board does not know "
                          "this task; add its row before changing its status")
        write_atomic(self.index, "\n".join(lines))

    def add_row(self, cells: list[str]) -> None:
        if not self.index.is_file():
            raise Refused(f"{self.rel(self.index)} is missing - the board is not scaffolded here")
        lines = read(self.index).split("\n")
        row = "| " + " | ".join(cell(c) for c in cells) + " |"
        start = next((i for i, l in enumerate(lines) if l.strip().lower() == "## task index"), None)
        if start is None:
            raise Refused(f"{self.rel(self.index)} has no '## Task index' table")
        last = None
        for i in range(start + 1, len(lines)):
            s = lines[i].strip()
            if s.startswith("|"):
                last = i
            elif last is not None:
                break
        if last is None:
            raise Refused(f"{self.rel(self.index)}: the task index has no table header")
        # Replace the template's placeholder row rather than leaving it above the first real one.
        for i in range(start + 1, last + 1):
            cells_i = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if ROW_RE.match(lines[i]) and len(cells_i) > 1 and cells_i[1].startswith("<"):
                lines[i] = row
                break
        else:
            lines.insert(last + 1, row)
        write_atomic(self.index, "\n".join(lines))

    def next_code(self) -> str:
        nums = [int(m.group(1)) for p in self.files()
                if (m := re.match(r"^TASK-(\d+)", p.name))]
        nums += [int(c.split("-")[1]) for c in self.rows()]
        return f"TASK-{(max(nums) if nums else 0) + 1:03d}"


# ------------------------------------------------------------------------------- task file text

def fm_span(text: str) -> tuple[int, int]:
    if not text.startswith("---\n"):
        raise Refused("task file has no frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise Refused("task file frontmatter is not closed")
    return 4, end


def fm_get(text: str, key: str) -> str | None:
    a, b = fm_span(text)
    m = re.search(rf"(?m)^{key}:[ \t]*(.*)$", text[a:b])
    return m.group(1).strip() if m else None


def fm_set(text: str, key: str, value: str | None, after: str = "deps") -> str:
    """Set, insert (after `after:`) or, with value None, remove a frontmatter key."""
    a, b = fm_span(text)
    head, body = text[a:b], text[b:]
    pat = re.compile(rf"(?m)^{key}:.*$\n?")
    if value is None:
        head = pat.sub("", head)
    elif pat.search(head):
        head = pat.sub(f"{key}: {value}\n", head, count=1)
        head = head.rstrip("\n") if not text[a:b].endswith("\n") else head
    else:
        m = re.search(rf"(?m)^{after}:.*$", head)
        pos = m.end() if m else len(head)
        head = head[:pos] + f"\n{key}: {value}" + head[pos:]
    return text[:a] + head.rstrip("\n") + body


def section(text: str, heading: str) -> tuple[int, int] | None:
    """Character span of a `## heading` section body (to the next `## ` or the end)."""
    m = re.search(rf"(?m)^{re.escape(heading)}[ \t]*$", text)
    if not m:
        return None
    nxt = re.search(r"(?m)^## ", text[m.end():])
    return m.end(), (m.end() + nxt.start()) if nxt else len(text)


def log_rows(text: str) -> tuple[list[str], tuple[int, int] | None, int]:
    """(data rows, span of the row block, index of the first data line) of the session log."""
    span = section(text, LOG_HEADING)
    if not span:
        return [], None, 0
    body = text[span[0]:span[1]]
    lines = body.split("\n")
    table = [i for i, l in enumerate(lines) if l.strip().startswith("|")]
    if len(table) < 2:
        return [], span, 0
    data = [lines[i] for i in table[2:] if lines[i].strip().strip("|").replace("|", "").strip()]
    return data, span, table[0]


def set_log_rows(text: str, rows: list[str]) -> str:
    _old, span, _ = log_rows(text)
    if span is None:
        raise Refused(f"task file has no '{LOG_HEADING}' section")
    body = text[span[0]:span[1]]
    lines = body.split("\n")
    table = [i for i, l in enumerate(lines) if l.strip().startswith("|")]
    if len(table) < 2:
        raise Refused("the session log has no table header")
    header = lines[table[0]:table[1] + 1]
    new = lines[:table[0]] + header + rows + lines[table[-1] + 1:]
    return text[:span[0]] + "\n".join(new) + text[span[1]:]


def append_log(board: Board, path: pathlib.Path, text: str, who: str, what: str,
               result: str) -> str:
    rows, _, _ = log_rows(text)
    rows.append(f"| {today()} | {cell(who)} | {cell(what)} | {cell(result)} |")
    pointer = [r for r in rows if POINTER_MARK in r]
    rest = [r for r in rows if POINTER_MARK not in r]
    if len(rest) > LOG_KEEP:
        code = re.match(r"^(TASK-\d+)", path.name).group(1)
        arc = board.archive / f"log-{code}.md"
        old, rest = rest[:-LOG_KEEP], rest[-LOG_KEEP:]
        prior = 0
        if arc.is_file():
            arc_text = read(arc)
            prior = sum(1 for l in arc_text.splitlines() if l.startswith("| 2") or
                        re.match(r"^\| \d{4}-", l))
        else:
            arc_text = (f"# {code} - archived session log\n\n"
                        f"Rows folded out of `{board.rel(path).replace(path.parent.name + '/', '<state>/')}`"
                        " by `task.py`, oldest first. Still the record: a gate logged here was "
                        "run.\n\n| Date | Who | What was done | Result |\n|------|-----|---------"
                        "------|--------|\n")
        write_atomic(arc, arc_text.rstrip("\n") + "\n" + "\n".join(old) + "\n")
        total = prior + len(old)
        pointer = [f"| {today()} | task.py | {total} {POINTER_MARK}"
                   f"{board.rel(arc)} | - |"]
    return set_log_rows(text, pointer + rest)


def checkpoint_lines(text: str) -> dict[str, str]:
    span = section(text, CHECKPOINT_HEADING)
    out = {}
    if span:
        for l in text[span[0]:span[1]].splitlines():
            m = re.match(r"^- (Next step|Last green commit|Open questions):\s*(.*)$", l)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def set_checkpoint(text: str, values: dict[str, str]) -> str:
    keys = ("Next step", "Last green commit", "Open questions")
    cur = checkpoint_lines(text)
    cur.update(values)
    block = "\n".join(f"- {k}: {cur.get(k) or '-'}" for k in keys)
    span = section(text, CHECKPOINT_HEADING)
    if span is None:
        # Older task files predate the section: put it right before the session log.
        log = section(text, LOG_HEADING)
        at = text.rfind(LOG_HEADING, 0, log[0]) if log else len(text)
        intro = ("\n\n<!-- Rewritten, never appended: where this task stands now. "
                 "/task-resume reads this instead of the whole log. -->\n\n")
        return text[:at] + CHECKPOINT_HEADING + intro + block + "\n\n" + text[at:]
    body = text[span[0]:span[1]]
    kept = [l for l in body.split("\n")
            if not re.match(r"^- (Next step|Last green commit|Open questions):", l)]
    # Re-insert the block where the first checkpoint line was, or after the comment.
    while kept and not kept[-1].strip():
        kept.pop()
    return text[:span[0]] + "\n".join(kept) + "\n\n" + block + "\n\n" + text[span[1]:].lstrip("\n")


def git(root: pathlib.Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


# ------------------------------------------------------------------------------------ commands

def move_file(board: Board, path: pathlib.Path, text: str, status: str) -> pathlib.Path:
    """Write `text` at the folder `status` lives in, then flip the row and verify it.
    The old file is removed only after the board row reads back correctly."""
    dest = board.tasks / FOLDER[status] / path.name
    code = re.match(r"^(TASK-\d+)", path.name).group(1)
    before = read(path)
    write_atomic(dest, text)
    try:
        board.set_row_status(code, status)
        if board.row_status(code) != status:
            raise Refused(f"{code}: the board row did not read back as {status}")
    except Exception:
        if dest != path:
            dest.unlink(missing_ok=True)
        write_atomic(path, before)
        raise
    if dest != path:
        path.unlink()
    return dest


def cmd_new(board: Board, a: argparse.Namespace) -> int:
    req = a.requested_by.strip().strip("\"'")
    if req.startswith("<") or req.lower() in PLACEHOLDERS:
        raise Refused("--requested-by is empty or a placeholder. Record what the user asked for, "
                      "or the issue it came from.")
    if req.lower() in LABELS:
        raise Refused(f"--requested-by '{req}' is a label, not a record. Write what was actually "
                      "asked for - an agent cannot approve its own task.")
    crit = [c.strip() for c in (a.criterion or []) if c.strip() and not c.strip().startswith("<")]
    if len(crit) < 2:
        raise Refused(f"{len(crit)} real acceptance criteria; a task needs at least 2. Work with "
                      "nothing observable to satisfy is a step inside a task, or a change small "
                      "enough to just make.")
    if a.priority not in PRIORITIES:
        raise Refused(f"--priority must be one of {', '.join(PRIORITIES)}")
    if not board.template.is_file():
        raise Refused(f"{board.rel(board.template)} is missing")
    deps = a.deps or "-"
    for d in re.split(r"[,\s]+", deps):
        if d and d != "-":
            board.find(d)  # every dependency must already exist
    code = board.next_code()
    slug = re.sub(r"[^a-z0-9]+", "-", a.title.lower()).strip("-")[:40] or "task"
    path = board.tasks / "active" / f"{code}-{slug}.md"
    t = read(board.template)
    # The template's frontmatter comments document the fields once; copied into every task file
    # they are read again on every resume. The file keeps the fields, the template keeps the docs.
    a0, b0 = fm_span(t)
    kept = [ln for ln in t[a0:b0].split("\n") if not ln.lstrip().startswith("#")]
    t = t[:a0] + "\n".join(kept) + t[b0:]
    title = cell(a.title).replace('"', "'")
    t = t.replace('title: "TASK-NNN: <short title>"', f'title: "{code}: {title}"')
    t = t.replace("# TASK-NNN: <short title>", f"# {code}: {title}")
    for key, val in (("status", "Planned"), ("fr", a.fr or "-"), ("requested_by", '"' + req.replace('"', "'") + '"'),
                     ("owner", a.owner), ("deps", deps), ("attempts", "0"),
                     ("priority", a.priority), ("phase", a.phase or "-"),
                     ("created", today())):
        t = fm_set(t, key, cell(val) if key == "requested_by" else cell(val).replace('"', "'"))
    t = t.replace("<One sentence describing the desired outcome.>", cell(a.goal or a.title))
    if a.files:
        t = re.sub(r"(?m)^- Related files and modules:.*$",
                   f"- Related files and modules: {cell(a.files)}", t)
    lines = "\n".join(f"- [ ] {cell(c)}" for c in crit)
    t = re.sub(r"(?m)^- \[ \] <criterion[^\n]*$", lambda _m: lines, t, count=1)
    if "- [ ] " + cell(crit[0]) not in t:
        raise Refused("the template has no '- [ ] <criterion ...>' line to fill")
    t = append_log(board, path, t, a.who, "Task created and registered on the board", "Planned")
    write_atomic(path, t)
    try:
        board.add_row([code, a.title, a.owner, deps, a.priority, a.phase or "-", "Planned"])
        if board.row_status(code) != "Planned":
            raise Refused(f"{code}: the board row did not read back")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    print(code)
    print(f"  {board.rel(path)}  (board row verified)")
    if a.fr and a.fr != "-":
        refresh_spec_index(board)
    return 0


def refresh_spec_index(board: Board) -> None:
    """docs/specs/index.json lists each FR's linked tasks, so a new task on an FR makes it stale.
    Regenerate it with spec-check.py when this repo has one (spec-builder ships it)."""
    script = pathlib.Path(__file__).resolve().parent / "spec-check.py"
    if not script.is_file() or not (board.root / "docs" / "specs").is_dir():
        return
    r = subprocess.run([sys.executable, str(script), "--target", str(board.root), "--write"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print("  docs/specs/index.json and confirmation.md regenerated (spec-check.py --write)")
    else:
        print("  spec-check.py --write reported problems - the task is registered, the spec "
              "needs attention:\n" + "\n".join("    " + l for l in
                                                (r.stdout + r.stderr).strip().splitlines()[-8:]))


def cmd_move(board: Board, a: argparse.Namespace) -> int:
    status = a.state.capitalize()
    if status not in STATES:
        raise Refused(f"state must be one of {', '.join(STATES)}")
    path = board.find(a.code)
    text = read(path)
    cur = fm_get(text, "status")
    if cur == status:
        raise Refused(f"{a.code} is already {status}")
    if status in NOTE_REQUIRED and not (a.note or "").strip():
        need = {"Blocked": "what blocks it and who can clear it",
                "Pending": "why it is parked", "Done": "the result: commit, PR, what shipped"}
        raise Refused(f"{status} needs --note: {need[status]}")
    if a.human_gate and status != "Blocked":
        raise Refused("--human-gate marks a Blocked task that needs a human decision; "
                      f"it cannot be set on {status}")
    if status == "Done":
        open_crit = re.findall(r"(?m)^- \[ \] (?!<)(.+)$", text[slice(*section(text, "## Acceptance criteria") or (0, 0))])
        if open_crit and not a.force:
            raise Refused(f"{len(open_crit)} acceptance criteria are still unchecked - tick the "
                          "ones that are met, or pass --force and say in --note why the rest "
                          "do not apply")
    text = fm_set(text, "status", status, after="title")
    text = fm_set(text, "human_gate", a.human_gate if status == "Blocked" and a.human_gate else None)
    what = f"Status {cur} -> {status}" + (f": {a.note.strip()}" if a.note else "")
    text = append_log(board, path, text, a.who, what, status)
    dest = move_file(board, path, text, status)
    print(f"{a.code}: {cur} -> {status}  ({board.rel(dest)}, board row verified)")
    return 0


def cmd_attempt(board: Board, a: argparse.Namespace) -> int:
    path = board.find(a.code)
    text = read(path)
    n = int(fm_get(text, "attempts") or 0)
    if a.reason == "infra":
        text = append_log(board, path, text, a.who, f"Attempt {n} failed (infra): {a.note}",
                          "re-dispatch with the same brief")
        write_atomic(path, text)
        print(f"{a.code}: infra failure logged; attempts stays {n}")
        return 0
    if a.reason == "env":
        a2 = argparse.Namespace(code=a.code, state="Blocked", who=a.who, human_gate=None,
                                force=False, note=f"env - {a.note}")
        return cmd_move(board, a2)
    n += 1
    text = fm_set(text, "attempts", str(min(n, ATTEMPT_CAP)))
    text = append_log(board, path, text, a.who, f"Attempt {n} failed (scope): {a.note}",
                      "next brief must change" if n < ATTEMPT_CAP else "cap reached")
    write_atomic(path, text)
    if n >= ATTEMPT_CAP:
        a2 = argparse.Namespace(code=a.code, state="Blocked", who=a.who, human_gate=None,
                                force=False, note=f"attempt cap {ATTEMPT_CAP} reached - escalate "
                                                  "to the user with what was tried")
        return cmd_move(board, a2)
    print(f"{a.code}: attempts {n} of {ATTEMPT_CAP}; the next brief must say what changed")
    return 0


def cmd_log(board: Board, a: argparse.Namespace) -> int:
    path = board.find(a.code)
    write_atomic(path, append_log(board, path, read(path), a.who, a.what, a.result))
    print(f"{a.code}: logged")
    return 0


def verify_plan():
    """verify-plan.py beside this script, imported - it owns the verification ledger."""
    import importlib.util
    f = pathlib.Path(__file__).resolve().parent / "verify-plan.py"
    if not f.is_file():
        return None
    spec = importlib.util.spec_from_file_location("verify_plan", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ledger_record(board: Board, gate: str, result: str, code: str,
                  files: list[str] | None = None) -> str:
    """Record a gate result in .claude/state/verify-ledger.jsonl -> "ledger line N", or ""."""
    vp = verify_plan()
    if vp is None:
        return ""
    vmap = {}
    vf = board.root / ".claude" / "verify-map.json"
    if vf.is_file():
        try:
            import json
            vmap = json.loads(vf.read_text(encoding="utf-8"))
        except ValueError:
            vmap = {}
    if files is None:
        files = vp.gate_files(board.root, vmap, gate, code, vp.default_base(board.root))
    return f"ledger line {vp.record(board.root, gate, result, code, files)}"


GATES = ("full-suite", "tests-scoped", "e2e", "code-review", "security-review", "spec-check",
         "content-check", "spec-validate")


def cmd_gate(board: Board, a: argparse.Namespace) -> int:
    """One step for a gate result: the ledger line (so the next run of that gate on the same
    content is skipped) and the session-log row (so the gate counts as passed)."""
    path = board.find(a.code)
    where = ledger_record(board, a.gate, a.result, a.code, a.files)
    text = append_log(board, path, read(path), a.who,
                      f"{a.gate}: {a.result}" + (f" - {a.note}" if a.note else ""),
                      where or a.result)
    write_atomic(path, text)
    print(f"{a.code}: {a.gate} {a.result}" + (f" ({where})" if where else ""))
    return 0


def cmd_checkpoint(board: Board, a: argparse.Namespace) -> int:
    path = board.find(a.code)
    text = read(path)
    values: dict[str, str] = {}
    if a.next is not None:
        values["Next step"] = cell(a.next)
    if a.green is not None:
        sha = a.green if a.green != "HEAD" else (git(board.root, "rev-parse", "--short", "HEAD")
                                                 or "")
        if not sha:
            raise Refused("--green with no SHA needs git; pass the commit explicitly")
        values["Last green commit"] = cell(sha)
        ledger_record(board, "full-suite", "pass", a.code)
    qs = [] if a.clear_questions else [
        q for q in (checkpoint_lines(text).get("Open questions", "-") or "-").split("; ")
        if q and q != "-"]
    qs += [cell(q) for q in (a.question or [])]
    if a.clear_questions or a.question:
        values["Open questions"] = "; ".join(qs) or "-"
    if not values:
        raise Refused("nothing to record: pass --next, --green, --question or --clear-questions")
    write_atomic(path, set_checkpoint(text, values))
    print(f"{a.code}: checkpoint updated")
    return 0


def cmd_resume(board: Board, a: argparse.Namespace) -> int:
    if not a.code:
        rows = []
        for p in board.files():
            t = read(p)
            st = fm_get(t, "status")
            if st in ("Planned", "Active", "Blocked"):
                code = re.match(r"^(TASK-\d+)", p.name).group(1)
                gate = fm_get(t, "human_gate")
                rows.append((0 if gate else 1, code, st, fm_get(t, "priority") or "-",
                             fm_get(t, "owner") or "-", gate or ""))
        if not rows:
            print("no unfinished tasks")
        for _, code, st, pr, owner, gate in sorted(rows):
            print(f"{code}  {st:<8} {pr}  {owner}" + (f"  HUMAN GATE: {gate}" if gate else ""))
        return 0
    path = board.find(a.code)
    t = read(path)
    st = fm_get(t, "status")
    row = board.row_status(a.code)
    print(f"{a.code}  {(fm_get(t, 'title') or '').strip(chr(34))}")
    print(f"  file      {board.rel(path)}")
    print(f"  status    {st}  (board row: {row or 'MISSING'})"
          + ("" if row == st else "  <- DRIFT: reconcile before working"))
    for k in ("owner", "deps", "priority", "attempts", "human_gate"):
        v = fm_get(t, k)
        if v:
            print(f"  {k:<9} {v}")
    cp = checkpoint_lines(t)
    head = git(board.root, "rev-parse", "--short", "HEAD")
    for k in ("Next step", "Last green commit", "Open questions"):
        print(f"  {k.lower():<17} {cp.get(k) or '-'}")
    green = cp.get("Last green commit", "-")
    if head:
        same = green not in ("", "-") and (head.startswith(green) or green.startswith(head))
        dirty = git(board.root, "status", "--porcelain")
        print(f"  HEAD      {head}" + ("  = last green commit: cite it, do not re-run the suite"
                                       if same and not dirty else ""))
        if dirty:
            print(f"  worktree  {len(dirty.splitlines())} uncommitted path(s) - inspect, never "
                  "stash or discard")
    span = section(t, "## Acceptance criteria")
    crit = re.findall(r"(?m)^- \[([ xX])\] (?!<)(.+)$", t[span[0]:span[1]]) if span else []
    open_ = [c for mark, c in crit if mark == " "]
    print(f"  criteria  {len(crit) - len(open_)} of {len(crit)} met")
    for c in open_:
        print(f"    [ ] {c}")
    rows, _, _ = log_rows(t)
    print(f"  last {min(RESUME_LOG_ROWS, len(rows))} of {len(rows)} log rows:")
    for r in rows[-RESUME_LOG_ROWS:]:
        print(f"    {r}")
    return 0


def cmd_list(board: Board, a: argparse.Namespace) -> int:
    want = a.state.capitalize() if a.state else None
    for code, cells in sorted(board.rows().items()):
        if want is None or cells[-1] == want:
            print("| " + " | ".join(cells) + " |")
    return 0


def cmd_check(board: Board, _a: argparse.Namespace) -> int:
    here = pathlib.Path(__file__).resolve().parent / "board-check.py"
    if not here.is_file():
        raise Refused("board-check.py is not next to task.py")
    return subprocess.run([sys.executable, str(here), "--target", str(board.root)]).returncode


# ----------------------------------------------------------------------------------- self-test

TEMPLATE = """---
title: "TASK-NNN: <short title>"
status: Planned
fr: <FR-NN, or "-">
requested_by: <what the user asked for>
owner: <agent>
deps: <TASK-NNN, or "-">
# human_gate: <reason>
attempts: 0
priority: <P0 | P1 | P2>
phase: <phase>
created: <YYYY-MM-DD>
---

# TASK-NNN: <short title>

## Goal

<One sentence describing the desired outcome.>

## Inputs and context

- Related files and modules: <paths>

## Acceptance criteria

- [ ] <criterion, tracking the FR acceptance criteria>

## Checkpoint

- Next step: -
- Last green commit: -
- Open questions: -

## Session log

| Date | Who | What was done | Result |
|------|-----|---------------|--------|
| | | | |

## Result
"""

INDEX = """# Master plan

## Task index

| Task | Title | Owner | Deps | Priority | Phase | Status |
|------|-------|-------|------|----------|-------|--------|
| TASK-001 | <first task> | <owner agent> | - | P0 | 1 | Planned |
"""


def self_test() -> list[str]:
    """Each check breaks if the behaviour it names is removed - mutation-tested, not decorative."""
    dead: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / "docs/templates").mkdir(parents=True)
        (root / "docs/tasks/active").mkdir(parents=True)
        (root / "docs/templates/TASK.md").write_text(TEMPLATE, encoding="utf-8")
        (root / "docs/tasks/master-plan.md").write_text(INDEX, encoding="utf-8")
        b = Board(root)
        p = build_parser()

        def run(*argv: str) -> int:
            a = p.parse_args(list(argv))
            try:
                import io, contextlib
                with contextlib.redirect_stdout(io.StringIO()):
                    return a.fn(b, a)
            except Refused:
                return 1

        if run("new", "x", "--owner", "dev", "--requested-by", "user",
               "--criterion", "a", "--criterion", "b") != 1:
            dead.append("new accepted requested_by 'user' - the guard-task-scope bar is gone")
        if run("new", "x", "--owner", "dev", "--requested-by", "split billing",
               "--criterion", "only one") != 1:
            dead.append("new accepted a single acceptance criterion")
        if run("new", "Split billing", "--owner", "dev", "--requested-by", "user: split billing",
               "--criterion", "invoices render", "--criterion", "totals match") != 0:
            dead.append("new refused a valid task")
        f = b.find("TASK-001")
        rows = b.rows()
        if "TASK-001" not in rows or "<first task>" in read(b.index):
            dead.append("new did not replace the placeholder board row")
        if fm_get(read(f), "status") != "Planned" or "- [ ] totals match" not in read(f):
            dead.append("new did not fill status or the criteria")
        if run("move", "TASK-001", "Blocked") != 1:
            dead.append("move to Blocked without --note was allowed")
        run("move", "TASK-001", "Active")
        if b.row_status("TASK-001") != "Active" or fm_get(read(b.find("TASK-001")), "status") != "Active":
            dead.append("move did not flip both the row and the frontmatter")
        run("move", "TASK-001", "Pending", "--note", "waiting on the quarter")
        f = b.find("TASK-001")
        if f.parent.name != "pending" or b.row_status("TASK-001") != "Pending":
            dead.append("move to Pending did not move the file to pending/ with its row")
        run("move", "TASK-001", "Blocked", "--note", "needs a pricing call", "--human-gate",
            "pricing decision")
        f = b.find("TASK-001")
        if fm_get(read(f), "human_gate") != "pricing decision" or f.parent.name != "active":
            dead.append("Blocked with --human-gate did not record the gate in active/")
        run("move", "TASK-001", "Active")
        if fm_get(read(b.find("TASK-001")), "human_gate") is not None:
            dead.append("leaving Blocked did not clear human_gate")
        if run("move", "TASK-001", "Done", "--note", "PR 1") != 1:
            dead.append("Done was allowed with unchecked acceptance criteria")
        for _ in range(ATTEMPT_CAP):
            run("attempt", "TASK-001", "--reason", "scope", "--note", "brief too vague")
        if fm_get(read(b.find("TASK-001")), "status") != "Blocked":
            dead.append(f"{ATTEMPT_CAP} scope failures did not block the task")
        run("move", "TASK-001", "Active")
        run("checkpoint", "TASK-001", "--next", "wire totals", "--green", "abc1234",
            "--question", "rounding mode?")
        cp = checkpoint_lines(read(b.find("TASK-001")))
        if cp.get("Next step") != "wire totals" or cp.get("Last green commit") != "abc1234" \
                or cp.get("Open questions") != "rounding mode?":
            dead.append(f"checkpoint did not record its fields: {cp}")
        for i in range(LOG_KEEP + 5):
            run("log", "TASK-001", f"step {i}", "ok")
        rows_now, _, _ = log_rows(read(b.find("TASK-001")))
        arc = root / "docs/tasks/log/log-TASK-001.md"
        if len(rows_now) > LOG_KEEP + 1 or not arc.is_file():
            dead.append(f"the session log was not bounded ({len(rows_now)} rows, archive "
                        f"{'present' if arc.is_file() else 'missing'})")
        elif POINTER_MARK not in rows_now[0]:
            dead.append("the bounded log has no pointer row to its archive")
        # A gate result lands in the ledger AND the session log, in one step.
        (root / "src").mkdir(exist_ok=True)
        (root / "src/a.ts").write_text("x\n", encoding="utf-8")
        run("gate", "TASK-001", "code-review", "pass", "--files", "src/a.ts")
        led = root / ".claude/state/verify-ledger.jsonl"
        if not led.is_file() or '"code-review"' not in led.read_text(encoding="utf-8"):
            dead.append("gate did not write the verification ledger")
        if "code-review: pass" not in read(b.find("TASK-001")):
            dead.append("gate did not log the result in the session log")
        # Importing verify-plan.py must not leave a .pyc beside the scripts: an untracked .pyc in
        # .claude/scripts/ is classed as code, and every later diff would demand a review.
        here = pathlib.Path(__file__).resolve().parent
        if (here / "verify-plan.py").is_file():
            import shutil
            import subprocess as sp
            scripts = root / "scripts-copy"
            scripts.mkdir()
            for f in ("task.py", "verify-plan.py"):
                shutil.copy(here / f, scripts / f)
            sp.run([sys.executable, str(scripts / "task.py"), "--target", str(root), "gate",
                    "TASK-001", "code-review", "pass", "--files", "src/a.ts"],
                   capture_output=True, text=True)
            if (scripts / "__pycache__").exists():
                dead.append("importing verify-plan.py wrote bytecode beside the scripts")
        # Drift: a hand edit of the row must be caught by resume.
        b.set_row_status("TASK-001", "Planned")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_resume(b, argparse.Namespace(code="TASK-001"))
        if "DRIFT" not in buf.getvalue():
            dead.append("resume did not flag a board row that disagrees with the file")
    return dead


# ---------------------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="task.py", description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    sub = ap.add_subparsers(dest="cmd")

    def who(sp):
        sp.add_argument("--who", default="orchestrator", help="the agent writing the row")

    s = sub.add_parser("new")
    s.add_argument("title")
    s.add_argument("--owner", required=True)
    s.add_argument("--requested-by", required=True)
    s.add_argument("--criterion", action="append")
    s.add_argument("--goal")
    s.add_argument("--deps")
    s.add_argument("--priority", default="P1")
    s.add_argument("--phase")
    s.add_argument("--fr")
    s.add_argument("--files")
    who(s)
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("move")
    s.add_argument("code")
    s.add_argument("state")
    s.add_argument("--note")
    s.add_argument("--human-gate")
    s.add_argument("--force", action="store_true", help="Done with unchecked criteria")
    who(s)
    s.set_defaults(fn=cmd_move)

    s = sub.add_parser("attempt")
    s.add_argument("code")
    s.add_argument("--reason", required=True, choices=("infra", "scope", "env"))
    s.add_argument("--note", required=True)
    who(s)
    s.set_defaults(fn=cmd_attempt)

    s = sub.add_parser("log")
    s.add_argument("code")
    s.add_argument("what")
    s.add_argument("result")
    who(s)
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser("gate")
    s.add_argument("code")
    s.add_argument("gate", choices=GATES)
    s.add_argument("result", choices=("pass", "fail"))
    s.add_argument("--note")
    s.add_argument("--files", nargs="*", help="the paths it covered (default: what verify-plan "
                                               "assigns the gate for the current diff)")
    who(s)
    s.set_defaults(fn=cmd_gate)

    s = sub.add_parser("checkpoint")
    s.add_argument("code")
    s.add_argument("--next")
    s.add_argument("--green", nargs="?", const="HEAD")
    s.add_argument("--question", action="append")
    s.add_argument("--clear-questions", action="store_true")
    s.set_defaults(fn=cmd_checkpoint)

    s = sub.add_parser("resume")
    s.add_argument("code", nargs="?")
    s.set_defaults(fn=cmd_resume)

    s = sub.add_parser("list")
    s.add_argument("state", nargs="?")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("check")
    s.set_defaults(fn=cmd_check)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--self-test"]:
        dead = self_test()
        for d in dead:
            print(f"task.py self-test: DEAD - {d}")
        print("task.py self-test: " + ("FAILED" if dead else "ok"))
        return 1 if dead else 0
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    try:
        return a.fn(Board(a.target.resolve()), a)
    except Refused as e:
        print(f"task.py: REFUSED - {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

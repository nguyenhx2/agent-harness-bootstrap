#!/usr/bin/env python3
"""spec-check: keep a spec set readable by its two readers.

A person (a PO, a client, a reviewer) confirms the spec from ONE page; an agent acts on it from ONE
small JSON file instead of reading every section. Both are generated from the spec, never written
by hand, and this script proves they still say what the spec says.

    docs/specs/confirmation.md   the one-page sheet a person answers: each FR in plain words, its
                                 acceptance criteria, its open issues, and a Decision column
                                 (yes / no / change). Only the reply columns are human-owned; they
                                 survive every regeneration, keyed by ID.
    docs/specs/index.json        what an agent reads first: per FR its title, priority, status,
                                 criteria count and IDs, open issues, linked tasks, and the file and
                                 anchor to open when it needs the full text.

Checks (each an error, exit 1):
    dup-id          an FR, BR, UC, US, AS, OI, CO or DP is defined twice
    anchor          an FR heading lacks its {#fr-nn} anchor, or the anchor is not the ID
    priority        an FR has no **Priority**, or it is not Must / Should / Could / Won't
    status          an FR has no **Status**, or it is not Draft / Confirmed / Withdrawn / Superseded
    no-criteria     a live FR has no acceptance criterion
    negative-case   a live FR has only one criterion, so its negative case is missing
    criterion-id    a criterion has no AC-nn.n ID, a duplicate one, or one numbered for another FR
    criterion-form  a criterion is not "Given ..., when ..., then ..." or "Done when ..."
    undefined-ref   an FR or OI is mentioned but defined nowhere
    owner           an open issue has no owner
    task-ref        a task file names an FR the spec does not define
    decision        a reply in the sheet is not yes / no / change
    stale           confirmation.md or index.json is missing or no longer matches the spec

Warnings (printed, exit 0): a sheet decision that has not been folded back into 05 yet, a
Confirmed FR still blocked by an open issue.

The keywords Given / when / then / Done when stay English whatever the prose language - they are
structure, like the table headers; the clauses between them are in the user's language.

Stdlib only. No timestamps in either generated file: both are prompt-cache prefix content.

Usage:
    python .claude/scripts/spec-check.py                    check (runs the self-test first)
    python .claude/scripts/spec-check.py --write            regenerate both files, then check
    python .claude/scripts/spec-check.py --write --lang ja  sheet headings in Japanese (kept after)
    python .claude/scripts/spec-check.py --target <repo>    a repo other than the current directory
    python .claude/scripts/spec-check.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SPECS = "docs/specs"
SHEET = "confirmation.md"
INDEX = "index.json"
TASK_DIRS = ("docs/tasks/active", "docs/tasks/pending", "docs/tasks/done")

MOD = r"(?:[A-Z][A-Z0-9]{1,3}-)?"
FR_ID = rf"FR-{MOD}\d{{1,5}}"
FR_HEAD = re.compile(rf"^##\s+(?P<id>{FR_ID})\b(?P<rest>.*)$")
ANCHOR = re.compile(r"\{#(?P<a>[A-Za-z0-9-]+)\}\s*$")
FR_MENTION = re.compile(rf"(?<![A-Za-z0-9-])(?P<id>{FR_ID})(?![0-9])")
OI_MENTION = re.compile(rf"(?<![A-Za-z0-9-])(?P<id>OI-{MOD}\d{{1,5}})(?![0-9])")
FIELD = re.compile(r"^\*\*(?P<k>Priority|Status)\*\*\s*:\s*(?P<v>.*?)\s*$")
AC_ITEM = re.compile(r"^\s*-\s+(?:\[(?P<box>[ xX])\]\s*)?(?P<body>.*)$")
AC_ID = re.compile(rf"^(?P<id>AC-{MOD}(?P<num>\d{{1,5}})\.(?P<n>\d{{1,3}}))\b[.:]?\s*(?P<text>.*)$")
GWT = re.compile(r"^Given\b.+?\bwhen\b.+?\bthen\b\s*\S", re.I | re.S)
DONE_WHEN = re.compile(r"^Done when\b\s*\S", re.I)
DEF_ROW = re.compile(rf"^(?P<id>(?:BR|UC|US|AS|OI|CO|DP)-{MOD}\d{{1,5}})\b")
TASK_FILE = re.compile(r"^(TASK-\d+)")

PRIORITIES = {"must": "Must", "should": "Should", "could": "Could", "won't": "Won't",
              "wont": "Won't"}
STATUSES = {"draft": "Draft", "confirmed": "Confirmed", "withdrawn": "Withdrawn",
            "superseded": "Superseded"}
RETIRED = {"Withdrawn", "Superseded"}
# The summary-table column that carries each FR's plain-words line: "Requirement" in the full
# shape, the purpose's own noun in a light contract.
STATEMENT_HEADS = {"requirement", "question", "decision", "deliverable"}
REPLIES = {"": "", "yes": "yes", "y": "yes", "no": "no", "n": "no", "change": "change",
           "はい": "yes", "いいえ": "no", "変更": "change"}

LABELS = {
    "en": {
        "title": "Confirmation sheet",
        "desc": "One page to confirm the spec. Generated from it by spec-check.py.",
        "how": ("Read each requirement and its acceptance criteria, then write **yes**, **no** or "
                "**change** in Decision, with a comment for anything but yes. Answer the open "
                "questions and confirm the assumptions below. Only the Decision, Comment, Answer "
                "and Confirmed columns are yours: every other cell is rewritten from the spec."),
        "reqs": "Requirements",
        "req_head": ["ID", "Requirement", "Priority", "Acceptance criteria", "Open issues",
                     "Decision", "Comment"],
        "ois": "Open questions",
        "oi_head": ["ID", "Question", "Blocks", "Owner", "Needed by", "Answer"],
        "ass": "Assumptions to confirm",
        "as_head": ["ID", "Assumption", "Impact if false", "Owner", "Confirmed", "Comment"],
        "none": "None.",
        "retired": "Withdrawn or superseded, not for confirmation",
    },
    "ja": {
        "title": "確認シート",
        "desc": "仕様を1ページで確認するためのシート。spec-check.py が仕様から生成します。",
        "how": ("各要件と受け入れ基準を読み、Decision 欄に **yes**、**no**、**change** のいずれかを"
                "記入してください (はい / いいえ / 変更 も可)。yes 以外にはコメントを添えてください。"
                "下の未解決の質問に回答し、前提を確認してください。記入できるのは Decision、"
                "Comment、Answer、Confirmed の各列だけです。それ以外のセルは仕様から再生成されます。"),
        "reqs": "要件",
        "req_head": ["ID", "要件", "優先度", "受け入れ基準", "未解決事項", "Decision", "Comment"],
        "ois": "未解決の質問",
        "oi_head": ["ID", "質問", "影響する要件", "担当", "期限", "Answer"],
        "ass": "確認が必要な前提",
        "as_head": ["ID", "前提", "誤りだった場合の影響", "担当", "Confirmed", "Comment"],
        "none": "なし。",
        "retired": "取り下げ済み・置き換え済み (確認対象外)",
    },
}
LANG_MARK = re.compile(r"<!-- spec-check: generated, lang=(?P<lang>[a-z]{2})")


@dataclass
class Criterion:
    id: str
    text: str
    form: str


@dataclass
class FR:
    id: str
    title: str
    file: str
    anchor: str
    line: int
    priority: str = ""
    status: str = ""
    statement: str = ""
    criteria: list[Criterion] = field(default_factory=list)
    open_issues: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    body: str = ""


@dataclass
class Report:
    errors: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def err(self, code: str, msg: str) -> None:
        self.errors.append((code, msg))

    def codes(self) -> set[str]:
        return {c for c, _ in self.errors}


# ------------------------------------------------------------------------------ reading
def blank_out(text: str) -> str:
    """HTML comments and fenced code are guidance or examples, never content. Keep line count."""
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    out, fenced = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else line)
    return "\n".join(out)


def split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """-> [(header cells, [row cells])] for every pipe table in the text."""
    lines = text.split("\n")
    found, i = [], 0
    while i < len(lines) - 1:
        if lines[i].strip().startswith("|") and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            head = split_row(lines[i])
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(split_row(lines[j]))
                j += 1
            found.append((head, rows))
            i = j
        else:
            i += 1
    return found


def col(head: list[str], name: str, default: int) -> int:
    for k, h in enumerate(head):
        if h.strip().lower() == name:
            return k
    return default


def cell(row: list[str], k: int) -> str:
    return row[k] if 0 <= k < len(row) else ""


def spec_files(root: Path) -> list[Path]:
    base = root / SPECS
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.md") if p.name != SHEET)


def section_of(path: Path) -> str:
    """'05' for 05-functional-requirements.md and for anything inside 05-functional-requirements/."""
    for part in reversed(path.parts):
        m = re.match(r"^(\d\d)-", part)
        if m:
            return m.group(1)
    return ""


def fr_sort_key(fr_id: str) -> tuple[str, int]:
    m = re.match(r"^FR-(?:([A-Z][A-Z0-9]{1,3})-)?(\d+)$", fr_id)
    return ((m.group(1) or "") if m else "", int(m.group(2)) if m else 0)


def read_spec(root: Path, rep: Report) -> dict:
    files = spec_files(root)
    if not files:
        rep.err("undefined-ref", f"{SPECS}/ holds no spec files under {root}")
    frs: dict[str, FR] = {}
    statements: dict[str, str] = {}
    defined: dict[str, list[str]] = {}
    ois: dict[str, dict] = {}
    assumptions: dict[str, dict] = {}
    mentions: list[tuple[str, str, str]] = []          # (kind, id, where)

    for path in files:
        rel = path.relative_to(root).as_posix()
        text = blank_out(path.read_text(encoding="utf-8"))
        sec = section_of(path.relative_to(root / SPECS))
        lines = text.split("\n")

        for n, line in enumerate(lines, 1):
            line = re.sub(r"`[^`]*`", "", line)        # inline code is an example, not a mention
            for m in FR_MENTION.finditer(line):
                mentions.append(("FR", m.group("id"), f"{rel}:{n}"))
            for m in OI_MENTION.finditer(line):
                mentions.append(("OI", m.group("id"), f"{rel}:{n}"))

        # Definitions in tables: only in the section that owns the prefix, so a mention in a
        # cross-reference table elsewhere is never mistaken for a second definition.
        owns = {"05": ("BR", "UC", "US"), "11": ("AS", "OI", "CO", "DP")}.get(sec, ())
        for head, rows in tables(text):
            low = [h.lower() for h in head]
            for row in rows:
                first = re.sub(r"\s*\{#[^}]*\}", "", cell(row, 0))
                m = DEF_ROW.match(first)
                if m and m.group("id").split("-")[0] in owns and first == m.group("id"):
                    defined.setdefault(m.group("id"), []).append(rel)
                    oid = m.group("id")
                    if oid.startswith("OI-"):
                        resolved = "resolution" in low
                        ois[oid] = {
                            "id": oid,
                            "question": cell(row, col(low, "question", 1)),
                            "blocks": "" if resolved else cell(row, col(low, "blocks", 2)),
                            "owner": "" if resolved else cell(row, col(low, "owner", 3)),
                            "needed_by": "" if resolved else cell(row, col(low, "needed by", 4)),
                            "status": "Resolved" if resolved
                                      else cell(row, col(low, "status", 5)) or "Open",
                        }
                    elif oid.startswith("AS-"):
                        assumptions[oid] = {
                            "id": oid,
                            "assumption": cell(row, col(low, "assumption", 1)),
                            "impact": cell(row, col(low, "impact if false", 3)),
                            "owner": cell(row, col(low, "owner", 4)),
                            "confirmed": cell(row, col(low, "confirmed", 5)),
                        }
                # The one-line statement in 05's summary table is the plain-words line.
                said = next((k for k, h in enumerate(low) if h in STATEMENT_HEADS), -1)
                if sec == "05" and said > 0:
                    sm = re.match(rf"^\[?(?P<id>{FR_ID})\]?", cell(row, 0))
                    if sm:
                        statements.setdefault(sm.group("id"), cell(row, said))

        if sec != "05":
            continue
        current: FR | None = None
        sub = ""
        for n, line in enumerate(lines, 1):
            hm = FR_HEAD.match(line)
            if hm:
                rest = hm.group("rest").strip()
                am = ANCHOR.search(rest)
                title = ANCHOR.sub("", rest).strip()
                fid = hm.group("id")
                current = FR(fid, title, rel, am.group("a") if am else "", n)
                sub = ""
                if fid in frs:
                    rep.err("dup-id", f"{fid} is defined twice: {frs[fid].file}:{frs[fid].line} "
                                      f"and {rel}:{n}")
                    current = None
                    continue
                if not am or am.group("a") != fid.lower():
                    rep.err("anchor", f"{rel}:{n} {fid} needs the anchor {{#{fid.lower()}}} "
                                      f"at the end of its heading")
                frs[fid] = current
                continue
            if line.startswith("## "):
                current = None
                continue
            if current is None:
                continue
            current.body += line + "\n"
            if line.startswith("### "):
                sub = line[4:].strip().lower()
                continue
            fm = FIELD.match(line)
            if fm:
                setattr(current, fm.group("k").lower(), fm.group("v"))
                continue
            if sub == "acceptance criteria":
                im = AC_ITEM.match(line)
                if not im or not im.group("body").strip():
                    continue
                body = im.group("body").strip()
                am2 = AC_ID.match(body)
                if not am2:
                    rep.err("criterion-id", f"{rel}:{n} {current.id} has a criterion with no "
                                            f"AC-nn.n ID: {body[:60]!r}")
                    continue
                num = fr_sort_key(current.id)[1]
                if int(am2.group("num")) != num:
                    rep.err("criterion-id", f"{rel}:{n} {am2.group('id')} sits under "
                                            f"{current.id}; number it AC-{num:02d}.n")
                if any(c.id == am2.group("id") for c in current.criteria):
                    rep.err("criterion-id", f"{rel}:{n} {am2.group('id')} appears twice")
                text_ = am2.group("text").strip()
                form = "gwt" if GWT.match(text_) else "done-when" if DONE_WHEN.match(text_) else ""
                if not form:
                    rep.err("criterion-form", f"{rel}:{n} {am2.group('id')} is not checkable as "
                                              f"written - use 'Given ..., when ..., then ...' or "
                                              f"'Done when ...'")
                current.criteria.append(Criterion(am2.group("id"), text_, form or "free"))

    for fid, places in sorted(defined.items()):
        if len(places) > 1:
            rep.err("dup-id", f"{fid} is defined {len(places)} times ({', '.join(places)})")

    for fr in frs.values():
        fr.statement = statements.get(fr.id, "") or fr.title
        p = PRIORITIES.get(fr.priority.strip().lower())
        if not p:
            rep.err("priority", f"{fr.file}:{fr.line} {fr.id} **Priority** is "
                                f"{fr.priority or 'missing'!r}; use Must, Should, Could or Won't")
        fr.priority = p or fr.priority
        s = STATUSES.get(fr.status.strip().lower())
        if not s:
            rep.err("status", f"{fr.file}:{fr.line} {fr.id} **Status** is "
                              f"{fr.status or 'missing'!r}; use Draft, Confirmed, Withdrawn or "
                              f"Superseded")
        fr.status = s or fr.status
        if fr.status not in RETIRED:
            if not fr.criteria:
                rep.err("no-criteria", f"{fr.file}:{fr.line} {fr.id} has no acceptance "
                                       f"criterion - it cannot be implemented or confirmed")
            elif len(fr.criteria) == 1:
                rep.err("negative-case", f"{fr.file}:{fr.line} {fr.id} has one criterion; add "
                                         f"the negative case (what must NOT happen, or the error "
                                         f"the user sees)")

    for kind, mid, where in mentions:
        if kind == "FR" and mid not in frs:
            rep.err("undefined-ref", f"{where} names {mid}, which no FR heading defines")
        if kind == "OI" and mid not in ois:
            rep.err("undefined-ref", f"{where} names {mid}, which section 11 does not define")

    for oid, oi in sorted(ois.items()):
        if oi["status"].lower() in ("resolved", "closed"):
            continue
        owner = oi["owner"].strip()
        if not owner or owner.lower() in ("tbd", "-"):
            rep.err("owner", f"{oid} has no owner - an open issue nobody owns is a wish")
        for m in FR_MENTION.finditer(oi["blocks"]):
            if m.group("id") in frs and oid not in frs[m.group("id")].open_issues:
                frs[m.group("id")].open_issues.append(oid)
    for fr in frs.values():
        for m in OI_MENTION.finditer(fr.body):
            oid = m.group("id")
            live = oid in ois and ois[oid]["status"].lower() not in ("resolved", "closed")
            if live and oid not in fr.open_issues:
                fr.open_issues.append(oid)
        fr.open_issues.sort(key=lambda x: int(x.rsplit("-", 1)[1]))

    return {"frs": frs, "ois": ois, "assumptions": assumptions}


def read_tasks(root: Path, frs: dict[str, FR], rep: Report) -> None:
    for d in TASK_DIRS:
        folder = root / d
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("TASK-*.md")):
            tm = TASK_FILE.match(p.name)
            text = p.read_text(encoding="utf-8")
            fm = re.match(r"^---\n(.*?)\n---", text.replace("\r\n", "\n"), re.S)
            if not (tm and fm):
                continue
            line = next((ln for ln in fm.group(1).split("\n") if ln.startswith("fr:")), "")
            for m in FR_MENTION.finditer(line):
                fid = m.group("id")
                if fid not in frs:
                    rep.err("task-ref", f"{d}/{p.name} names {fid}, which the spec does not "
                                        f"define")
                elif tm.group(1) not in frs[fid].tasks:
                    frs[fid].tasks.append(tm.group(1))


def read_replies(sheet: Path, rep: Report) -> tuple[str, dict[str, list[str]]]:
    """The human-owned cells of an existing sheet, keyed by ID: (lang, {id: [reply cells]})."""
    if not sheet.is_file():
        return "", {}
    text = sheet.read_text(encoding="utf-8")
    lm = LANG_MARK.search(text)
    replies: dict[str, list[str]] = {}
    for head, rows in tables(text):
        width = len(head)
        for row in rows:
            rid = re.sub(r"[\[\]]|\(.*?\)", "", cell(row, 0)).strip()
            if not re.match(rf"^(?:FR|OI|AS)-{MOD}\d{{1,5}}$", rid):
                continue
            # FR rows end in Decision + Comment, AS rows in Confirmed + Comment, OI rows in Answer.
            keep = 1 if rid.startswith("OI-") else 2
            row = (row + [""] * width)[:width]
            replies[rid] = row[-keep:]
    for rid, cells in replies.items():
        if rid.startswith(("FR-", "AS-")) and cells[0].strip().lower() not in REPLIES:
            rep.err("decision", f"{SPECS}/{SHEET}: {rid} reads {cells[0]!r}; write yes, no or "
                                f"change (or はい, いいえ, 変更)")
    return (lm.group("lang") if lm else ""), replies


# --------------------------------------------------------------------------- generating
def esc(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def render(spec: dict, replies: dict[str, list[str]], lang: str) -> tuple[str, str]:
    L = LABELS[lang]
    frs = sorted(spec["frs"].values(), key=lambda f: fr_sort_key(f.id))
    live = [f for f in frs if f.status not in RETIRED]
    ois = [o for o in sorted(spec["ois"].values(), key=lambda o: o["id"])
           if o["status"].lower() not in ("resolved", "closed")]
    ass = sorted(spec["assumptions"].values(), key=lambda a: a["id"])

    def table(head: list[str], rows: list[list[str]]) -> list[str]:
        out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
        out += ["| " + " | ".join(r) + " |" for r in rows]
        return out

    md = ["---", f'title: "{L["title"]}"', f'description: "{L["desc"]}"',
          "tags: [specs, confirmation]", "---", "",
          f"<!-- spec-check: generated, lang={lang}. Regenerate with "
          f"`python .claude/scripts/spec-check.py --write`; never edit a spec cell here. -->", "",
          f"# {L['title']}", "", L["how"], "", f"## {L['reqs']}", ""]
    rows = []
    for f in live:
        crit = "<br>".join(esc(f"{c.id} {c.text}") for c in f.criteria) or "-"
        r = (replies.get(f.id, []) + ["", ""])[:2]
        rows.append([f"[{f.id}]({Path(f.file).relative_to(SPECS).as_posix()}#{f.anchor})",
                     esc(f.statement), f.priority, crit, ", ".join(f.open_issues) or "-",
                     esc(r[0]), esc(r[1])])
    md += table(L["req_head"], rows) if rows else [L["none"]]
    md += ["", f"## {L['ois']}", ""]
    rows = [[o["id"], esc(o["question"]), esc(o["blocks"]) or "-", esc(o["owner"]),
             esc(o["needed_by"]) or "-", esc((replies.get(o["id"]) or [""])[-1])] for o in ois]
    md += table(L["oi_head"], rows) if rows else [L["none"]]
    md += ["", f"## {L['ass']}", ""]
    rows = []
    for a in ass:
        r = (replies.get(a["id"], []) + ["", ""])[:2]
        rows.append([a["id"], esc(a["assumption"]), esc(a["impact"]), esc(a["owner"]),
                     esc(r[0]), esc(r[1])])
    md += table(L["as_head"], rows) if rows else [L["none"]]
    retired = [f for f in frs if f.status in RETIRED]
    if retired:
        md += ["", f"{L['retired']}: " + ", ".join(f"{f.id} ({f.status})" for f in retired)]
    sheet = "\n".join(md) + "\n"

    index = {
        "schema": 1,
        "about": "Generated by spec-check.py from docs/specs/. Read this before any section; "
                 "open a section only at the file and anchor of the FR you act on.",
        "frs": [{
            "id": f.id, "title": f.title, "statement": f.statement, "priority": f.priority,
            "status": f.status,
            "decision": REPLIES.get((replies.get(f.id) or [""])[0].strip().lower(), ""),
            "criteria": len(f.criteria), "criteria_ids": [c.id for c in f.criteria],
            "criteria_form": sorted({c.form for c in f.criteria}),
            "open_issues": f.open_issues, "tasks": sorted(f.tasks),
            "file": f.file, "anchor": f.anchor,
        } for f in frs],
        "open_issues": [{"id": o["id"], "question": o["question"], "owner": o["owner"],
                         "needed_by": o["needed_by"], "status": o["status"],
                         "blocks": [m.group("id") for m in FR_MENTION.finditer(o["blocks"])]}
                        for o in ois],
        "assumptions": [{"id": a["id"], "assumption": a["assumption"],
                         "confirmed": a["confirmed"]} for a in ass],
    }
    return sheet, json.dumps(index, indent=1, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------------------- running
def run(root: Path, write: bool, lang: str | None) -> Report:
    rep = Report()
    spec = read_spec(root, rep)
    read_tasks(root, spec["frs"], rep)
    sheet_p, index_p = root / SPECS / SHEET, root / SPECS / INDEX
    old_lang, replies = read_replies(sheet_p, rep)
    lang = lang or old_lang or "en"
    sheet, index = render(spec, replies, lang)

    for fr in spec["frs"].values():
        decision = REPLIES.get((replies.get(fr.id) or [""])[0].strip().lower(), "")
        if decision == "yes" and fr.status == "Draft":
            rep.warnings.append(f"{fr.id} was confirmed in the sheet; set **Status**: Confirmed "
                                f"in 05 and add a revision row")
        elif decision in ("no", "change"):
            rep.warnings.append(f"{fr.id} came back '{decision}' - fold the comment in with "
                                f"/spec-ingest before implementing it")
        if fr.status == "Confirmed" and fr.open_issues:
            rep.warnings.append(f"{fr.id} is Confirmed but still blocked by "
                                f"{', '.join(fr.open_issues)}")

    if write and (root / SPECS).is_dir():
        sheet_p.write_bytes(sheet.encode("utf-8"))
        index_p.write_bytes(index.encode("utf-8"))
    for p, want in ((sheet_p, sheet), (index_p, index)):
        if not p.is_file():
            rep.err("stale", f"{SPECS}/{p.name} is missing - run spec-check.py --write")
        elif p.read_bytes() != want.encode("utf-8"):
            rep.err("stale", f"{SPECS}/{p.name} no longer matches the spec - run "
                             f"spec-check.py --write and review the diff")
    return rep


# ----------------------------------------------------------------------------- self-test
FIXTURE_05 = """---
title: "Functional requirements"
---

# Functional requirements

<!-- FR-99 in a comment is guidance, never a mention. -->

## Summary

| ID | Requirement | Priority (MoSCoW) | Actor |
|----|-------------|-------------------|-------|
| [FR-01](#fr-01) | Approvers can reject a request with a reason | Must | approver |
| [FR-02](#fr-02) | Requesters see the status of their requests | Should | requester |

## FR-01 Reject a request {#fr-01}

**Priority**: Must
**Status**: Draft
**Actor**: approver

### Business rules

| ID | Rule | Source |
|----|------|--------|
| BR-01 | A rejection needs a reason | policy |

### Acceptance criteria

- [ ] AC-01.1 Given a pending request, when the approver rejects it with a reason, then its status is Rejected.
- [ ] AC-01.2 Given a pending request, when the approver rejects it with no reason, then the rejection is refused.

### Dependencies

- Blocked by: [OI-01](11-assumptions-constraints.md#oi-01)

## FR-02 Show status {#fr-02}

**Priority**: Should
**Status**: Confirmed

### Acceptance criteria

- [ ] AC-02.1 Done when the requester's list shows the status of every request they own.
- [ ] AC-02.2 Given another user's request, when the requester opens its URL, then access is denied.

## Use cases

| ID | Use case | Actor | Precondition | Main success scenario | Serves |
|----|----------|-------|--------------|-----------------------|--------|
| UC-01 | Reject | approver | pending | rejects | [FR-01](#fr-01) |
"""

FIXTURE_11 = """---
title: "Assumptions and constraints"
---

## Assumptions

| ID | Assumption | Why we are assuming it | Impact if false | Owner | Confirmed |
|----|-----------|------------------------|-----------------|-------|-----------|
| AS-01 | One approver per request | implied | the flow changes | PO | No |

## Open issues

| ID | Question | Blocks | Owner | Needed by | Status |
|----|----------|--------|-------|-----------|--------|
| OI-01 {#oi-01} | Is a reason mandatory for every rejection? | [FR-01](05-functional-requirements.md#fr-01) | PO | sprint 2 | Open |

### Resolved issues

| ID | Question | Resolution | Decided by |
|----|----------|-----------|------------|
| OI-00 | Email or in-app? | in-app | PO |
"""

FIXTURE_TASK = """---
title: "TASK-001: reject"
status: Active
fr: FR-01
---
"""


def _fixture(base: Path) -> Path:
    root = base / "repo"
    (root / SPECS).mkdir(parents=True)
    (root / "docs/tasks/active").mkdir(parents=True)
    (root / SPECS / "05-functional-requirements.md").write_text(FIXTURE_05, encoding="utf-8")
    (root / SPECS / "11-assumptions-constraints.md").write_text(FIXTURE_11, encoding="utf-8")
    (root / "docs/tasks/active/TASK-001-reject.md").write_text(FIXTURE_TASK, encoding="utf-8")
    return root


def self_test() -> list[str]:
    """Every detector must fire on a planted defect, and the clean fixture must pass."""
    failures: list[str] = []
    f05 = "docs/specs/05-functional-requirements.md"
    f11 = "docs/specs/11-assumptions-constraints.md"
    mutations = {
        "dup-id": (f05, "## FR-02 Show status {#fr-02}", "## FR-01 Show status {#fr-01}"),
        "dup-id (table row)": (f11, "| OI-00 | Email", "| OI-01 | Email"),
        "anchor": (f05, "## FR-02 Show status {#fr-02}", "## FR-02 Show status"),
        "priority": (f05, "**Priority**: Should", "**Priority**: High"),
        "status": (f05, "**Status**: Confirmed", "**Status**: Approved"),
        "no-criteria": (f05, "- [ ] AC-02.1 Done when the requester's list shows the status "
                             "of every request they own.\n- [ ] AC-02.2 Given another user's "
                             "request, when the requester opens its URL, then access is denied.\n",
                        ""),
        "negative-case": (f05, "- [ ] AC-02.2 Given another user's request, when the requester "
                               "opens its URL, then access is denied.\n", ""),
        "criterion-id": (f05, "AC-02.2 Given", "AC-03.2 Given"),
        "criterion-form": (f05, "AC-01.1 Given a pending request, when",
                           "AC-01.1 The approver can reject, when"),
        "undefined-ref": (f05, "| [FR-02](#fr-02) | Requesters", "| [FR-07](#fr-07) | Requesters"),
        "owner": (f11, "[FR-01](05-functional-requirements.md#fr-01) | PO |",
                  "[FR-01](05-functional-requirements.md#fr-01) |  |"),
        "task-ref": ("docs/tasks/active/TASK-001-reject.md", "fr: FR-01", "fr: FR-09"),
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = _fixture(Path(tmp))
        rep = run(root, write=True, lang="en")
        if rep.errors:
            failures.append(f"clean fixture reports {rep.errors}")
        idx = json.loads((root / SPECS / INDEX).read_text(encoding="utf-8"))
        fr1 = idx["frs"][0]
        if (fr1["criteria"], fr1["open_issues"], fr1["tasks"]) != (2, ["OI-01"], ["TASK-001"]):
            failures.append(f"index row for FR-01 is wrong: {fr1}")
        if idx["frs"][1]["criteria_form"] != ["done-when", "gwt"]:
            failures.append("criterion forms are not recorded")

        # A human reply survives regeneration and reaches the index.
        sheet = root / SPECS / SHEET
        text = sheet.read_text(encoding="utf-8")
        row = next(ln for ln in text.split("\n") if ln.startswith("| [FR-02]"))
        if not row.endswith("|  |  |"):
            failures.append(f"sheet row has no empty reply cells: {row}")
        sheet.write_text(text.replace(row, row[:-len("|  |  |")] + "| yes | fine |"),
                         encoding="utf-8")
        _, replies = read_replies(sheet, Report())
        if replies.get("FR-02", [""])[0] != "yes":
            failures.append(f"reply not parsed back: {replies.get('FR-02')}")
        run(root, write=True, lang=None)
        idx = json.loads((root / SPECS / INDEX).read_text(encoding="utf-8"))
        if idx["frs"][1]["decision"] != "yes":
            failures.append("a sheet decision did not survive regeneration")

        # The sheet follows the spec: a changed statement makes it stale until --write.
        p = root / f05
        p.write_text(p.read_text(encoding="utf-8").replace("Approvers can reject",
                                                           "Approvers may reject"), "utf-8")
        if "stale" not in run(root, write=False, lang=None).codes():
            failures.append("stale: an edited spec did not make the sheet stale")
        run(root, write=True, lang=None)

        sheet.write_text(sheet.read_text(encoding="utf-8").replace("| yes |", "| maybe |"),
                         encoding="utf-8")
        if "decision" not in run(root, write=False, lang=None).codes():
            failures.append("decision: an invalid reply was accepted")

    with tempfile.TemporaryDirectory() as tmp:
        if "stale" not in run(_fixture(Path(tmp)), write=False, lang="en").codes():
            failures.append("stale: a spec set with no sheet and no index passed")

    for label, (rel, old, new) in mutations.items():
        code = label.split()[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture(Path(tmp))
            p = root / rel
            src = p.read_text(encoding="utf-8")
            if old not in src:
                failures.append(f"{label}: mutation anchor not found in fixture")
                continue
            p.write_text(src.replace(old, new, 1), encoding="utf-8")
            got = run(root, write=True, lang="en").codes()
            if code not in got:
                failures.append(f"{label}: planted defect not detected (got {sorted(got)})")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description="Check a spec set and keep its confirmation sheet "
                                             "and agent index in sync with it.")
    ap.add_argument("--target", type=Path, default=Path("."), help="repo root (default: .)")
    ap.add_argument("--write", action="store_true",
                    help="regenerate docs/specs/confirmation.md and index.json, then check")
    ap.add_argument("--lang", choices=sorted(LABELS), default=None,
                    help="sheet heading language; kept on later runs once chosen")
    ap.add_argument("--self-test", action="store_true", help="run only the self-test")
    args = ap.parse_args()

    failures = self_test()
    if failures:
        print("spec-check: SELF-TEST FAILED - the checker cannot be trusted:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 2
    print("spec-check: self-test ok (every detector fires, clean fixture passes)")
    if args.self_test:
        return 0

    rep = run(args.target.resolve(), args.write, args.lang)
    for w in rep.warnings:
        print(f"  warn  {w}")
    for code, msg in rep.errors:
        print(f"  FAIL  [{code}] {msg}")
    print(f"spec-check: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)"
          + (" - confirmation.md and index.json written" if args.write else ""))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())

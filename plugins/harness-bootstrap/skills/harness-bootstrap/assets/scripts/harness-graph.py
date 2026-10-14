#!/usr/bin/env python3
"""Scan .claude/ and emit the canonical machine-readable harness graph.

Output: .claude/state/harness-graph.json - schema version 1, documented in
docs/HARNESS-GRAPH-SCHEMA.md at the skill repo (and summarized here):

  { "version": 1,
    "nodes": [ {"id", "type", "label", "file"?, "disabled", "synthetic"?, "meta"?} ],
    "edges": [ {"from", "to", "type", "refs"?} ] }

Node types (closed set):  agent | rule | command | hook | settings | script |
                          module | task | gate | human | skill | instruction
Edge types (closed enum): gates | triggers | enforces | reviews | owns | spawns |
                          runs | invokes | escalates | references | uses |
                          briefs | cites | imports | routes | delegates |
                          sources | refers

The file is DETERMINISTIC: nodes and edges are sorted, keys are sorted, and it
carries no timestamp - two runs over the same tree are byte-identical, so the
graph-stale hook can regenerate it on every harness edit without dirtying bytes.

This scanner is the single source of truth for harness wiring. graph-html.py
renders this JSON; external tools (for example a native viewer) read the same
file. Anything that mutates .claude/ outside Edit/Write hooks (scaffold re-runs,
toggle scripts) must re-run this scanner itself.

Usage:
  python .claude/scripts/harness-graph.py [--target <repo>] [--html] [--quiet]

  --html   after writing the JSON, re-render docs/context/harness-graph.html by
           loading graph-html.py from the same directory
  --quiet  print nothing on success

Stdlib only. Never fails the caller for a malformed input file: unreadable
settings.json or code-graph.json just narrows the graph.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

# Importing a sibling script must not leave bytecode in .claude/scripts/: a stray .pyc there
# is an untracked file, and verify-plan.py would ask for a review of it.
sys.dont_write_bytecode = True

NODE_TYPES = ("agent", "rule", "command", "hook", "settings", "script",
              "module", "task", "gate", "human", "skill", "instruction")
EDGE_TYPES = ("gates", "triggers", "enforces", "reviews", "owns", "spawns",
              "runs", "invokes", "escalates", "references", "uses",
              "briefs", "cites", "imports", "routes", "delegates",
              "sources", "refers")

# The instruction files: the contract each AI coding tool reads, and the only
# nodes that live OUTSIDE .claude/. This table is the twin of
# `instruction::FILES` in tools/harness-view/src/instruction.rs and has to stay
# equal to it - scripts/check_graph_parity.py compares the two scanners byte for
# byte, so a path added on one side only surfaces there as a diff.
#
# Every path is sourced, and the source travels into the node so a reader can
# tell a documented fact from a guess. Nothing here was invented: what could not
# be confirmed from this repository or from a first-party vendor page is recorded
# as a note (see the Kiro note on AGENTS.md), never as a path.
#
#   (key, path, ext, tools, source, verified, note)
#   ext == "" means `path` IS the file; otherwise `path` is a directory of them.
INSTRUCTION_FILES = (
    ("agents", "AGENTS.md", "",
     ("Claude Code", "Codex", "Cursor", "Antigravity"),
     "docs/tools/claude-code.md; docs/tools/codex.md; docs/tools/cursor.md; "
     "antigravity.google/docs/cli/best-practices", True,
     "Kiro is deliberately absent from this list: no first-party Kiro page confirms that it "
     "reads AGENTS.md, so the claim is unverified and is not made here. Kiro's documented "
     "instruction surface is .kiro/steering/."),
    ("claude", "CLAUDE.md", "", ("Claude Code",),
     "docs/tools/claude-code.md; harness-bootstrap/assets/root/CLAUDE.md", True,
     "A thin @AGENTS.md import plus the Claude-only surface; it is not a second contract."),
    ("gemini", "GEMINI.md", "", ("Antigravity",),
     "antigravity.google/docs/cli/best-practices", True,
     "Antigravity accepts either GEMINI.md or AGENTS.md at the workspace root."),
    ("cursor-rules", ".cursor/rules", ".mdc", ("Cursor",),
     "harness-bootstrap/scripts/port.py (port_cursor_rules); docs/tools/cursor.md", True,
     "Written by the porter, one per .claude/rules/*.md. No `paths:` becomes alwaysApply: "
     "true; `paths: [glob]` becomes globs:."),
    ("kiro-steering", ".kiro/steering", ".md", ("Kiro",),
     "kiro.dev/docs/steering", True,
     "Workspace steering files. This repository does not port to Kiro, so these are "
     "hand-written where they exist."),
    ("antigravity-rules", ".agents/rules", ".md", ("Antigravity",),
     "antigravity.google/docs/rules-workflows", True,
     "Workspace rules, at the workspace or git root. Global rules live in ~/.gemini/GEMINI.md, "
     "outside any repository, so they are not scannable."),
    ("antigravity-rules-legacy", ".agent/rules", ".md", ("Antigravity",),
     "antigravity.google/docs/rules-workflows (documented back-compat path)", True,
     "The superseded location, still read for backward compatibility."),
)

# A leaf file name inside one of the directory-shaped entries above. The same
# character class the write path enforces, so a name this scanner turns into a
# node is a name the editor can address.
INSTRUCTION_NAME_RE = re.compile(r"^(?!\.)(?!.*\.\.)[A-Za-z0-9_.-]+$")

# ---------------------------------------------------------------- content refs
# Twin of tools/harness-view/src/refs.rs; read that file's header for the why.
# A name counts only when it is written as a name on purpose: a `.claude/...`
# path or a bare file name, a `/command`, an exact `code span` or **bold** span,
# or a bare HYPHENATED slug. A single dictionary word in prose never counts.
# Written as character loops rather than regexes so it matches the Rust
# tokenizer exactly; the parity check compares the two byte for byte.

def _ascii_alnum(c: str) -> bool:
    return c.isascii() and c.isalnum()


def _word_char(c: str) -> bool:
    return _ascii_alnum(c) or c in "_-./"


def _slug_char(c: str) -> bool:
    return _ascii_alnum(c) or c in "_-"


def _strip_ext(s: str, exts) -> str | None:
    for e in exts:
        if s.endswith(e) and len(s) > len(e):
            return s[:-len(e)]
    return None


def _runs(text: str, keep) -> list[str]:
    out, cur = [], []
    for c in text + " ":
        if keep(c):
            cur.append(c)
        elif cur:
            out.append("".join(cur))
            cur = []
    return out


def _by_name(inv: dict, name: str, with_rules: bool) -> str | None:
    # Commands are left out: a command is written /name, and a skill-backed
    # command often shares its skill's name, so the bare word means the skill.
    for kind in ("agent", "skill", "hook"):
        if name in inv[kind]:
            return kind
    if with_rules and name in inv["rule"]:
        return "rule"
    return None


_PATH_DIRS = {"agents": ("agent", (".md",)), "rules": ("rule", (".md",)),
              "commands": ("command", (".md",)), "skills": ("skill", None),
              "hooks": ("hook", (".sh", ".ps1")),
              "scripts": ("script", (".py", ".sh", ".ps1"))}


def _path_refs(word: str, inv: dict, out: set) -> None:
    segs = word.split("/")
    for i in range(len(segs) - 1):
        # Anchored at .claude/ or at the start of the word: .cursor/rules/x.md
        # and a skill's private scripts/ folder are other trees.
        if i != 0 and segs[i - 1] != ".claude":
            continue
        spec = _PATH_DIRS.get(segs[i])
        if not spec:
            continue
        kind, exts = spec
        name = segs[i + 1] if exts is None else _strip_ext(segs[i + 1], exts)
        if name and name in inv[kind]:
            out.add((kind, name))
    # A word that is ONE file name, possibly behind a leading slash
    # ($(dirname "$0")/_lib.sh tokenizes to /_lib.sh), or a /command.
    parts = [x for x in segs if x]
    if len(parts) == 1:
        f = parts[0]
        n = _strip_ext(f, (".sh", ".ps1"))
        if n and n in inv["hook"]:
            out.add(("hook", n))
        n = _strip_ext(f, (".py", ".sh", ".ps1"))
        if n and n in inv["script"]:
            out.add(("script", n))
        if len(segs) == 2 and segs[0] == "" and f in inv["command"]:
            out.add(("command", f))


def _marked_spans(line: str) -> list[str]:
    out = []
    for delim in ("`", "**"):
        rest = line
        while True:
            a = rest.find(delim)
            if a < 0:
                break
            after = rest[a + len(delim):]
            b = after.find(delim)
            if b < 0:
                break
            out.append(after[:b].strip())
            rest = after[b + len(delim):]
    return out


def references(text: str, inv: dict) -> set:
    """Every harness item `text` references, as (kind, name)."""
    norm = text.replace("\\", "/")
    out: set = set()
    for w in _runs(norm, _word_char):
        _path_refs(w.rstrip("."), inv, out)
    for line in _lines(norm):
        for span in _marked_spans(line):
            kind = _by_name(inv, span, True)
            if kind:
                out.add((kind, span))
    for w in _runs(norm, _slug_char):
        w = w.strip("-")
        if "-" in w:
            kind = _by_name(inv, w, False)
            if kind:
                out.add((kind, w))
    return out


def edge_type(frm: str, to: str) -> str:
    """The edge a reference becomes, named by what the two ends are."""
    if frm == "hook" and to == "rule":
        return "enforces"
    if frm == "hook" and to == "hook":
        return "sources"
    if to == "script":
        return "runs"
    if frm == "hook":
        return "refers"
    if frm == "instruction" and to == "agent":
        return "briefs"
    if to == "rule":
        return "cites"
    if to == "skill":
        return "uses"
    if frm == "rule" and to == "agent":
        return "refers"
    if to == "agent":
        return "delegates"
    if to == "command":
        return "invokes"
    return "refers"


_PREFIX = {"command": "cmd"}

# Seats that gate the merge request by name (edge agent -reviews-> gate:merge-request).
# Twin of REVIEWERS in scan.rs; is_review_seat() adds the role suffixes.
REVIEWERS = ("code-reviewer", "merge-manager", "reviewer", "security-reviewer",
             "spec-guardian")

# Events whose hook gates a tool call: exit 2 stops the call or refuses the
# permission. Twin of TOOL_GATE_EVENTS in scan.rs.
TOOL_GATE_EVENTS = ("PreToolUse", "PermissionRequest")

# The state folders of an orchestrator-kit task board, in board order.
BOARD_STATES = ("pending", "active", "completed", "canceled")

# ------------------------------------------------------------- Rust string twins
# The parity gate compares this scanner with harness-view byte for byte, so the
# string primitives below mirror Rust's rather than Python's: `str::trim` knows a
# narrower whitespace set than `str.strip`, `str::lines` splits on "\n" only,
# and `read_to_string` neither translates newlines nor survives invalid UTF-8.

_WS = ("\t\n\x0b\x0c\r \x85\xa0        "
       "        　")


def _trim(s: str) -> str:
    return s.strip(_WS)


def _blen(s: str) -> int:
    return len(s.encode("utf-8"))


def _lines(text: str) -> list[str]:
    """Rust `str::lines`: split on LF, drop the CR of a CRLF, no empty last line."""
    if not text:
        return []
    parts = text.split("\n")
    last = parts.pop()
    out = [p[:-1] if p.endswith("\r") else p for p in parts]
    if last:
        out.append(last)
    return out


def _get(v, key):
    """serde_json `Value::get`: a key of an object, None for anything else."""
    return v.get(key) if isinstance(v, dict) else None


def _str(v) -> str | None:
    return v if isinstance(v, str) else None


def _i64(v) -> int | None:
    if isinstance(v, int) and not isinstance(v, bool) and -2**63 <= v < 2**63:
        return v
    return None


def _no_constant(_name):
    raise ValueError("not JSON")


def _load_json(text: str):
    """Parse like serde_json: NaN and Infinity are not JSON. None when unreadable."""
    try:
        return json.loads(text, parse_constant=_no_constant)
    except (ValueError, TypeError, RecursionError):
        return None


def read_text(p: pathlib.Path) -> str:
    """The file as Rust's read_to_string sees it: raw UTF-8, else empty."""
    try:
        return p.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def strip_comment(s: str) -> str:
    """Drop a trailing YAML comment: `Done # Active | Blocked` -> `Done`.

    A `#` only opens a comment when whitespace precedes it, so `P0#1` survives.
    Real task files keep the template's enum comment on the line, and without
    this the status reads as "Done # Active | Blocked | Pending | Done".
    """
    if s[:1] in ('"', "'"):
        return s
    for i, ch in enumerate(s):
        if ch == "#" and (i == 0 or s[i - 1] in " \t\n\x0c\r"):
            return s[:i].rstrip(_WS)
    return s


def unquote(s: str) -> str:
    """Strip one matched pair of surrounding quotes."""
    t = _trim(s)
    if len(t) >= 2 and t[0] in "\"'" and t[-1] == t[0]:
        return t[1:-1]
    return t


def split_top(s: str) -> list[str]:
    """Split on commas outside parentheses, brackets and quotes, so
    `Agent(researcher, writer), Read` is two tools and not three fragments."""
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    quote = None
    for c in s:
        if quote is not None:
            if c == quote:
                quote = None
            cur.append(c)
            continue
        if c in "\"'":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth <= 0:
            out.append(_trim("".join(cur)))
            cur = []
            continue
        cur.append(c)
    if _trim("".join(cur)):
        out.append(_trim("".join(cur)))
    return out


def as_list(v) -> list[str]:
    """`Read, Write, Bash(git commit:*)` or a YAML list -> list of strings."""
    if isinstance(v, list):
        return [unquote(x) for x in v if isinstance(x, str)]
    if isinstance(v, str):
        inner = _trim(v).lstrip("[").rstrip("]")
        return [p for p in (unquote(x) for x in split_top(inner)) if p]
    return []


def frontmatter(text: str) -> dict:
    """Flat `key: value` pairs and block lists, top level only. Twin of scan.rs."""
    out: dict = {}
    # A file saved by a Windows editor can start with a UTF-8 BOM.
    text = text.removeprefix("﻿")
    lines = _lines(text)
    if not lines or _trim(lines[0]) != "---":
        return out
    cur_key = None
    cur_list: list[str] = []
    for line in lines[1:]:
        if _trim(line) == "---":
            break
        trimmed = line.lstrip(_WS)
        if trimmed.startswith("- ") and cur_key is not None:
            cur_list.append(_trim(trimmed[2:]))
            continue
        if cur_key is not None:
            if cur_list:
                out[cur_key] = cur_list
                cur_list = []
            cur_key = None
        if line.startswith((" ", "\t")):
            continue
        idx = line.find(":")
        if idx >= 0:
            key, val = _trim(line[:idx]), _trim(line[idx + 1:])
            if not key:
                continue
            if not val:
                cur_key = key
            else:
                out[key] = val
    if cur_key is not None and cur_list:
        out[cur_key] = cur_list
    return out


def cap(s: str, n: int) -> str:
    s = _trim(s)
    return s[:n] + "..." if len(s) > n else s


def description(fm: dict) -> str | None:
    """Frontmatter `description:`, trimmed and capped at 300 chars.

    The viewer shows this in its sidebar, so a runaway value must not push the
    rest of the panel off screen; the full text is one Preview click away.
    """
    raw = fm.get("description")
    if not isinstance(raw, str):
        return None
    d = _trim(unquote(raw))
    if not d:
        return None
    return d[:300] + "..." if len(d) > 300 else d


# ------------------------------------------------------- nested frontmatter
# Claude Code's subagent format nests three fields - `hooks:`, `mcpServers:` and
# `experimental:` - which the flat reader cannot see. Twin of frontmatter_tree()
# in scan.rs: maps and lists by indentation, scalars as strings, a `[a, b]` flow
# list as a list. Indents are counted in UTF-8 bytes, as Rust counts them.

def frontmatter_tree(text: str) -> dict:
    text = text.removeprefix("﻿")
    raw = _lines(text)
    if not raw or _trim(raw[0]) != "---":
        return {}
    lines: list[tuple[int, str]] = []
    for line in raw[1:]:
        if _trim(line) == "---":
            break
        t = line.rstrip(_WS)
        body = t.lstrip(_WS)
        if not body or body.startswith("#"):
            continue
        lines.append((_blen(t) - _blen(body), body))
    v = _yaml_block(lines, [0], 0)
    return v if isinstance(v, dict) else {}


def _yaml_scalar(s: str):
    t = strip_comment(_trim(s))
    if len(t) >= 2 and t.startswith("[") and t.endswith("]"):
        return [x for x in (unquote(p) for p in split_top(t[1:-1])) if x]
    single = t.startswith("'")
    u = unquote(t)
    return u.replace("''", "'") if single else u


def _yaml_kv(s: str):
    """`key: rest` when the line opens a mapping entry, else None."""
    if s[:1] in ('"', "'", "[", "{"):
        return None
    idx = s.find(": ")
    if idx < 0:
        if not s.endswith(":"):
            return None
        idx = len(s) - 1
    key = _trim(s[:idx])
    if not key or " " in key:
        return None
    return unquote(key), _trim(s[idx + 1:])


def _is_item(body: str) -> bool:
    return body == "-" or body.startswith("- ")


def _yaml_block(lines, i, indent):
    if i[0] >= len(lines):
        return None
    ind0, first = lines[i[0]]
    indent = max(ind0, indent)
    if _is_item(first):
        arr = []
        while i[0] < len(lines):
            ind, body = lines[i[0]]
            if ind != indent or not _is_item(body):
                break
            rest = body[1:].lstrip(_WS)
            col = indent + _blen(body) - _blen(rest)
            i[0] += 1
            if not rest:
                if i[0] < len(lines) and lines[i[0]][0] > indent:
                    arr.append(_yaml_block(lines, i, lines[i[0]][0]))
                else:
                    arr.append(None)
                continue
            kv = _yaml_kv(rest)
            if kv:
                # `- key: value` opens a map whose later keys sit at `col`
                m = {kv[0]: _yaml_value(lines, i, col, kv[1])}
                if i[0] < len(lines) and lines[i[0]][0] == col:
                    more = _yaml_block(lines, i, col)
                    if isinstance(more, dict):
                        m.update(more)
                arr.append(m)
            else:
                arr.append(_yaml_scalar(rest))
        return arr
    m = {}
    while i[0] < len(lines):
        ind, body = lines[i[0]]
        if ind != indent or _is_item(body):
            break
        i[0] += 1
        kv = _yaml_kv(body)
        if kv:
            m[kv[0]] = _yaml_value(lines, i, indent, kv[1])
    return m


def _yaml_value(lines, i, indent, inline):
    """The value after `key:` - inline, a block scalar, or a nested block."""
    if inline in ("|", ">", "|-", ">-", "|+", ">+"):
        parts = []
        while i[0] < len(lines) and lines[i[0]][0] > indent:
            parts.append(lines[i[0]][1])
            i[0] += 1
        return ("\n" if inline.startswith("|") else " ").join(parts)
    if inline:
        return _yaml_scalar(inline)
    if i[0] < len(lines):
        n, b = lines[i[0]]
        if n > indent:
            return _yaml_block(lines, i, n)
        # YAML lets a list sit at its key's own indent
        if n == indent and _is_item(b):
            return _yaml_block(lines, i, indent)
    return None


# ------------------------------------------------------------- hooks

def hook_name_from_command(cmd: str) -> str | None:
    """The `.claude/hooks/<name>` a registration runs. The `hooks/<name>.sh` (or
    `.ps1`) occurrence wins over any other `hooks/` in the line; failing that,
    the last occurrence."""
    norm = cmd.replace("\\", "/")
    last = None
    start = 0
    while True:
        i = norm.find("hooks/", start)
        if i < 0:
            return last
        at = i + len("hooks/")
        j = at
        while j < len(norm) and (_ascii_alnum(norm[j]) or norm[j] in "-_"):
            j += 1
        name = norm[at:j]
        if name:
            if norm.startswith(".sh", j) or norm.startswith(".ps1", j):
                return name
            last = name
        start = at


class HookReg:
    """One hook registration, from settings.json or from a seat's frontmatter."""

    __slots__ = ("source", "event", "matcher", "command", "hook")

    def __init__(self, source, event, matcher, command, hook):
        self.source, self.event, self.matcher = source, event, matcher
        self.command, self.hook = command, hook

    def summary(self) -> str:
        target = self.hook if self.hook is not None else cap(self.command, 120)
        if self.matcher in ("*", ""):
            return f"{self.event} -> {target}"
        return f"{self.event} {self.matcher} -> {target}"


def hook_regs(source: str, hooks) -> list[HookReg]:
    """Every registration in a `hooks:` value - settings.json's and a subagent
    frontmatter's share one shape: event -> [{matcher, hooks: [{type, command}]}]."""
    out: list[HookReg] = []
    if not isinstance(hooks, dict):
        return out
    for event, groups in hooks.items():
        for group in groups if isinstance(groups, list) else []:
            matcher = _str(_get(group, "matcher"))
            matcher = "*" if matcher is None else matcher
            inner = _get(group, "hooks")
            for h in inner if isinstance(inner, list) else []:
                ty = _str(_get(h, "type"))
                ty = "command" if ty is None else ty
                cmd = _str(_get(h, "command"))
                if cmd is not None:
                    command = cmd
                else:
                    body = next((x for x in (_str(_get(h, "prompt")), _str(_get(h, "url")))
                                 if x is not None), "")
                    command = f"{ty}: {body}"
                out.append(HookReg(source, event, matcher, command,
                                   hook_name_from_command(cmd) if cmd is not None else None))
    return out


# ------------------------------------------------------------- seats

def is_review_seat(name: str) -> bool:
    """A seat whose job is to judge work rather than produce it: the scaffolder's
    names, `editor`, `checker`, or a name ending in a reviewing role."""
    return (name in REVIEWERS or name in ("editor", "checker")
            or name.endswith(("reviewer", "-checker", "auditor", "critic", "verifier")))


def spawn_targets(tools: list[str]) -> list[str] | None:
    """The seats an `Agent(a, b)` (or legacy `Task(a, b)`) grant names; None when
    the tool list grants spawning without naming anyone, or not at all."""
    out: list[str] = []
    named = False
    for t in tools:
        for head in ("Agent(", "Task("):
            if t.startswith(head) and t.endswith(")") and len(t) > len(head):
                named = True
                out.extend(x for x in (unquote(p) for p in split_top(t[len(head):-1])) if x)
    return sorted(set(out)) if named else None


def agent_meta_extra(stem: str, fm: dict, tree: dict, meta: dict) -> None:
    """The subagent frontmatter fields beyond model/effort/maxTurns/tools/description
    (code.claude.com/docs/en/sub-agents, "Supported frontmatter fields"), each only
    when the file sets it. Twin of agent_meta_extra() in scan.rs."""
    def flat(k):
        v = fm.get(k)
        return unquote(strip_comment(v)) if isinstance(v, str) else None

    n = flat("name")
    # Claude Code dispatches by `name:`, not by the file name. Say so when they differ.
    if n and n != stem:
        meta["name"] = n
    for k in ("permissionMode", "memory", "isolation", "color"):
        v = flat(k)
        if v:
            meta[k] = v
    for k in ("background", "omitClaudeMd"):
        v = flat(k)
        if v == "true":
            meta[k] = True
        elif v == "false":
            meta[k] = False
        elif v:
            meta[k] = v
    p = tree.get("initialPrompt")
    if isinstance(p, str) and _trim(p):
        meta["initialPrompt"] = cap(p, 300)
    for k in ("disallowedTools", "skills"):
        if k in fm:
            lst = as_list(fm[k])
            if lst:
                meta[k] = lst
    # mcpServers: a list of server names, inline definitions keyed by name, or both
    servers: list[str] = []
    ms = tree.get("mcpServers")
    if isinstance(ms, list):
        for x in ms:
            if isinstance(x, str):
                servers.append(x)
            elif isinstance(x, dict):
                servers.extend(x.keys())
    elif isinstance(ms, dict):
        servers.extend(ms.keys())
    elif isinstance(ms, str):
        servers.extend(as_list(ms))
    if servers:
        meta["mcpServers"] = servers
    if "hooks" in tree:
        regs = [r.summary() for r in hook_regs("", tree["hooks"])]
        if regs:
            meta["hooks"] = regs
    ttl = _str(_get(tree.get("experimental"), "cacheTtl"))
    if ttl is None:
        ttl = flat("experimental.cacheTtl")
    if ttl:
        meta["cacheTtl"] = ttl
    if isinstance(meta.get("tools"), list):
        t = spawn_targets([x for x in meta["tools"] if isinstance(x, str)])
        if t is not None:
            meta["spawns"] = t


def skill_decl_value(line: str) -> str | None:
    """The value of a line that declares skills for a seat, e.g. "Skills to load
    when relevant: webapp-testing." /skill-wire records a wire as an entry under
    the seat's "Skills available" section, so a declaration line is the only
    trustworthy signal. Matching a bare skill name anywhere in an agent file
    invents wiring: five of ost's agents contain the word "performance" while
    the skill of that name is wired to no seat."""
    lower = line.lower()
    kw = lower.find("skill")
    colon = line.find(":")
    if kw < 0 or colon < 0 or colon < kw:
        return None
    between = lower[kw:colon]
    if not any(m in between for m in ("available", "to load", "in use", "when relevant")):
        return None
    return line[colon + 1:]


def slug_tokens(text: str) -> list[str]:
    """Slug-shaped tokens, trailing punctuation dropped: " webapp-testing." yields
    "webapp-testing", not "webapp-testing."."""
    out = []
    for w in _runs(text, lambda c: _ascii_alnum(c) or c in "_-."):
        i, j = 0, len(w)
        while i < j and not _ascii_alnum(w[i]):
            i += 1
        while j > i and not _ascii_alnum(w[j - 1]):
            j -= 1
        if i < j:
            out.append(w[i:j])
    return out


def md_stems(d: pathlib.Path) -> list[str]:
    """Stems of the `.md` entries in a directory, README excluded, sorted."""
    try:
        entries = list(d.iterdir())
    except OSError:
        return []
    return sorted(p.stem for p in entries if p.suffix == ".md" and p.stem != "README")


def _names(d: pathlib.Path) -> list[str]:
    try:
        return sorted(p.name for p in d.iterdir())
    except OSError:
        return []


def load_disabled(claude: pathlib.Path) -> set[str]:
    """'<kind>/<name>' keys listed in .claude/disabled.json (absent = empty)."""
    out: set[str] = set()
    data = _load_json(read_text(claude / "disabled.json"))
    entries = _get(data, "disabled")
    for e in entries if isinstance(entries, list) else []:
        k, n = _str(_get(e, "kind")), _str(_get(e, "name"))
        if k is not None and n is not None:
            out.add(f"{k}/{n}")
    return out


# ------------------------------------------------------------- task board

def board_dir(root: pathlib.Path, settings) -> str | None:
    """`env.TASK_BOARD_DIR` from settings.json when it is a relative path inside
    the repo, else `.agent-base/tasks`; None when that directory does not exist."""
    pick = ".agent-base/tasks"
    d = _str(_get(_get(settings, "env"), "TASK_BOARD_DIR"))
    if d is not None:
        d = d.replace("\\", "/").strip("/")
        if d and ":" not in d and not any(s in ("..", "") for s in d.split("/")):
            pick = d
    return pick if (root / pick).is_dir() else None


def board_index(path: pathlib.Path) -> dict[str, dict]:
    """TASKS.md rows keyed by TASK id: | ID | task | agent | state | deps | mission |."""
    out: dict[str, dict] = {}
    for line in _lines(read_text(path)):
        t = _trim(line)
        if not t.startswith("|"):
            continue
        cells = [_trim(c) for c in t.strip("|").split("|")]
        rid = cells[0] if cells else ""
        if not rid.startswith("TASK-") or _blen(rid) < 6:
            continue

        def cell(i):
            return cells[i] if i < len(cells) and cells[i] != "-" else ""
        out[rid] = {"title": cell(1), "owner": cell(2), "state": cell(3), "deps": cell(4)}
    return dict(sorted(out.items()))


def task_id(stem: str) -> str:
    """`TASK-007-fix-login` -> `TASK-007`: the id task.sh keys the index by."""
    if not stem.startswith("TASK-"):
        return stem
    digits = ""
    for c in stem[5:]:
        if not ("0" <= c <= "9"):
            break
        digits += c
    return f"TASK-{digits}" if digits else stem


def walk_tasks(d: pathlib.Path, root: pathlib.Path, out: list) -> None:
    """Every TASK-*.md below `d`, depth first in name order, as (stem, relpath)."""
    for name in _names(d):
        p = d / name
        if p.is_dir():
            walk_tasks(p, root, out)
        elif name.startswith("TASK-") and name.endswith(".md"):
            stem = name
            while stem.endswith(".md"):
                stem = stem[:-3]
            out.append((stem, p.relative_to(root).as_posix()))


def _cells(line: str) -> list[str]:
    t = _trim(line)
    if not t.startswith("|"):
        return []
    return [_trim(_trim(c).strip("*")) for c in t.strip("|").split("|")]


def _is_separator(line: str) -> bool:
    c = _cells(line)
    return bool(c) and all(x and set(x) <= set("-:") for x in c)


def tier_rows(text: str) -> list[dict]:
    """The 'How much process a change gets' table v1.18.0 put into AGENTS.md.

    Matched by what its columns MEAN - a first column called Tier beside one that
    names who runs the change - and not by the heading above it, which is prose
    and can be reworded without the table changing at all. Twin of
    `instruction::tier_rows` in the Rust scanner.
    """
    lines = _lines(text)
    for i, line in enumerate(lines):
        head = _cells(line)
        if len(head) < 3:
            continue
        lower = [c.lower() for c in head]
        english = lower[0] == "tier" and any("who runs" in c for c in lower)
        # The same table in another language - orchestrator-kit writes it as
        # `| 区分 | 変更の内容 | 誰が行うか |` - is recognised by its rows: the tier
        # names are identifiers and stay English whatever the prose around them.
        named_rows = 0
        for raw in lines[i + 1:]:
            if _is_separator(raw):
                continue
            c = _cells(raw)
            if len(c) < 3:
                break
            if c[0] in ("Direct", "Standard", "Guarded"):
                named_rows += 1
        if not english and named_rows < 2:
            continue
        who_at = next((j for j, c in enumerate(lower) if "who runs" in c or "誰" in c), 2)
        change_at = next((j for j, c in enumerate(lower)
                          if "change" in c or "変更" in c), 1)
        adds_at = next((j for j, c in enumerate(lower) if "adds" in c), 3)
        out: list[dict] = []
        for raw in lines[i + 1:]:
            if _is_separator(raw):
                continue
            c = _cells(raw)
            if len(c) < 3:
                break
            pick = lambda idx: c[idx] if idx < len(c) else ""   # noqa: E731
            if not pick(0):
                break
            out.append({"tier": pick(0), "change": pick(change_at),
                        "who": pick(who_at), "adds": pick(adds_at)})
        return out
    return []


# Contracts that may also appear in SUBDIRECTORIES, each copy governing its own subtree. Claude Code
# reads the CLAUDE.md for the directory being worked in, so a repo with src/api/CLAUDE.md is
# governed by four contracts and a scanner that reports one is quietly wrong. Mirrors the `nested`
# flag on `instruction::Spec`.
NESTED_KEYS = ("agents", "claude")
NEST_MAX_DEPTH = 8
NEST_MAX_FILES = 200
NEST_SKIP = {"node_modules", "target", "dist", "build", "vendor", "__pycache__", "venv", ".venv"}


def nested_copies(root: pathlib.Path, file_name: str) -> list[str]:
    """Every copy of `file_name` BELOW `root`, repo-relative and sorted.

    Breadth-first with an explicit queue so the depth cap is the cap. Directory symlinks are not
    followed: one pointing up the tree walks the repo again under a second set of names, one
    pointing out puts a stranger's file in this graph. The root copy is excluded - the caller has
    already added it, and twice would be two nodes for one file.
    """
    out: list[str] = []
    queue: list[tuple[pathlib.Path, str, int]] = [(root, "", 0)]
    while queue:
        d, prefix, depth = queue.pop()
        if depth >= NEST_MAX_DEPTH or len(out) >= NEST_MAX_FILES:
            continue
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            name = e.name
            if e.is_symlink():
                continue
            if e.is_dir():
                if name.startswith(".") or name in NEST_SKIP:
                    continue
                queue.append((e, name if not prefix else f"{prefix}/{name}", depth + 1))
            elif name == file_name and prefix and len(out) < NEST_MAX_FILES:
                out.append(f"{prefix}/{name}")
    return sorted(out)


def instruction_files(root: pathlib.Path):
    """-> [(entry, name, repo-relative path)] for every one that exists.

    A path that is absent is simply not a node: the graph reports what a
    repository HAS, and a node for a file nobody wrote would be a placeholder
    pretending to be a fact.
    """
    found = []
    for entry in INSTRUCTION_FILES:
        key, path, ext = entry[0], entry[1], entry[2]
        if not ext:
            if (root / path).is_file():
                found.append((entry, "", path))
            if key in NESTED_KEYS:
                for rel in nested_copies(root, path):
                    found.append((entry, rel, rel))
            continue
        d = root / path
        if not d.is_dir():
            continue
        stems = sorted(p.name[:-len(ext)] for p in d.iterdir()
                       if p.is_file() and p.name.endswith(ext)
                       and INSTRUCTION_NAME_RE.match(p.name[:-len(ext)] or "."))
        for stem in stems:
            found.append((entry, stem, f"{path}/{stem}{ext}"))
    return found


def build(root: pathlib.Path) -> dict:
    """The harness graph. A line-for-line twin of `scan()` in scan.rs: the parity
    gate compares the two outputs byte for byte, so the order of reads and the
    shape of every node follow the Rust side."""
    claude = root / ".claude"
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str, int]] = set()
    listed = load_disabled(claude)

    # agents: both trees, because a seat parked under disabled/agents still
    # belongs in the graph, greyed out
    agent_names: list[str] = []
    agent_regs: list[HookReg] = []
    for dir_tail, dis in ((".claude/agents", False), (".claude/disabled/agents", True)):
        for name in md_stems(root / dir_tail):
            text = read_text(root / dir_tail / f"{name}.md")
            fm = frontmatter(text)
            meta: dict = {}
            for key in ("model", "effort"):
                if isinstance(fm.get(key), str):
                    meta[key] = fm[key]
            for key in ("maxTurns", "max-turns"):
                v = fm.get(key)
                if isinstance(v, str) and re.fullmatch(r"[+-]?[0-9]+", v):
                    n = int(v)
                    if -2**63 <= n < 2**63:
                        meta["maxTurns"] = n
            for key in ("tools", "allowed-tools"):
                if key in fm:
                    lst = as_list(fm[key])
                    if lst:
                        meta["tools"] = lst
                        break
            d = description(fm)
            if d:
                meta["description"] = d
            tree = frontmatter_tree(text)
            agent_meta_extra(name, fm, tree, meta)
            if not dis and "hooks" in tree:
                agent_regs.extend(hook_regs(f"agent:{name}", tree["hooks"]))
            nodes[f"agent:{name}"] = {"id": f"agent:{name}", "type": "agent", "label": name,
                                      "file": f"{dir_tail}/{name}.md", "disabled": dis,
                                      "meta": meta}
            if not dis:
                agent_names.append(name)

    # rules, commands: active tree plus the disabled/ quarantine tree. Only
    # unconditional rules in the ACTIVE tree gate; only active commands are invoked.
    gating_rules: list[str] = []
    active_commands: list[str] = []
    for kind, sub, prefix in (("rule", "rules", "rule"), ("command", "commands", "cmd")):
        for dir_tail, dir_disabled in ((f".claude/{sub}", False),
                                       (f".claude/disabled/{sub}", True)):
            for name in md_stems(root / dir_tail):
                file = f"{dir_tail}/{name}.md"
                nid = f"{prefix}:{name}"
                node = {"id": nid, "type": kind,
                        "label": f"/{name}" if kind == "command" else name, "file": file,
                        # disabled.json ORs into the flag for rules and hooks only
                        "disabled": dir_disabled or (kind == "rule" and f"rule/{name}" in listed)}
                fm = frontmatter(read_text(root / file))
                if kind == "rule":
                    meta = {}
                    scoped = False
                    if "paths" in fm:
                        paths = as_list(fm["paths"])[:8]
                        scoped = bool(paths)
                        meta["scoped"] = scoped
                        if scoped:
                            meta["paths"] = paths
                    else:
                        meta["scoped"] = False
                    d = description(fm)
                    if d:
                        meta["description"] = d
                    node["meta"] = meta
                    if not dir_disabled and not scoped:
                        gating_rules.append(nid)
                else:
                    d = description(fm)
                    if d:
                        node["meta"] = {"description": d}
                    if not dir_disabled:
                        active_commands.append(nid)
                nodes[nid] = node

    # hooks: one node per name, across both flavors and the quarantine. Disabled
    # only when ALL its flavor files are quarantined; the representative file is
    # the .sh if present, an active flavor beating a disabled one.
    hook_variants: dict[str, list[tuple[str, bool]]] = {}
    for dir_tail, disabled in ((".claude/hooks", False), (".claude/disabled/hooks", True)):
        for fname in _names(root / dir_tail):
            stem, dot, ext = fname.rpartition(".")
            if not dot or ext not in ("sh", "ps1"):
                continue
            hook_variants.setdefault(stem, []).append((f"{dir_tail}/{fname}", disabled))
    hook_files: dict[str, tuple[str, bool]] = {}
    for stem in sorted(hook_variants):
        files = hook_variants[stem]
        all_disabled = all(d for _, d in files)
        files = sorted(files, key=lambda fd: (not fd[0].endswith(".sh"), fd[1], fd[0]))
        hook_files[stem] = (files[0][0], all_disabled or f"hook/{stem}" in listed)

    # settings.json: which hooks are registered, and under what
    settings_path = claude / "settings.json"
    have_settings = settings_path.is_file()
    settings_v = _load_json(read_text(settings_path)) if have_settings else None
    settings_regs = hook_regs("settings", _get(settings_v, "hooks"))
    if have_settings:
        node = {"id": "settings", "type": "settings", "label": "settings.json",
                "file": ".claude/settings.json", "disabled": False,
                "edit": {"key": "settings", "name": ""}}
        # Registrations that run no file in .claude/hooks/: an inline command, a
        # Python hook, a prompt or http hook. They fire all the same.
        other = [r.summary() for r in settings_regs
                 if r.hook is None or r.hook not in hook_files]
        if other:
            node["meta"] = {"otherHooks": other}
        nodes["settings"] = node

    for name, (file, disabled) in hook_files.items():
        hid = f"hook:{name}"
        regs = [r for r in settings_regs + agent_regs if r.hook == name]
        meta = {"registered": bool(regs)}
        if regs:
            meta["event"] = regs[0].event
            meta["matcher"] = regs[0].matcher
            meta["blocking"] = any(r.event in TOOL_GATE_EVENTS for r in regs)
        # Registered more than once: list every one, because the first alone
        # under-reports what the hook guards.
        seen: list[str] = []
        for r in regs:
            s = r.event if r.matcher == "*" else f"{r.event} {r.matcher}"
            if s not in seen:
                seen.append(s)
        if len(seen) > 1:
            meta["events"] = seen
        # A hook a seat registers in its own frontmatter fires only while that
        # seat runs. `scope` names the seats; absent means session-wide.
        scope = sorted({r.source[len("agent:"):] for r in regs
                        if r.source.startswith("agent:")})
        if scope:
            for a in scope:
                edges.add((f"agent:{a}", hid, "triggers", 0))
            if not any(r.source == "settings" for r in regs):
                meta["scope"] = scope
        nodes[hid] = {"id": hid, "type": "hook", "label": name, "file": file,
                      "disabled": disabled, "meta": meta}
        if have_settings and any(r.source == "settings" for r in regs):
            edges.add(("settings", hid, "triggers", 0))

    # scripts: every .py, .sh and .ps1 under .claude/scripts/. One node per name;
    # when two flavors share a name the .py wins, then the .sh.
    scripts_dir = claude / "scripts"
    files = [n for n in _names(scripts_dir) if (scripts_dir / n).is_file()]
    by_stem: dict[str, str] = {}
    for ext in ("py", "sh", "ps1"):
        for f in files:
            if f.endswith(f".{ext}") and len(f) > len(ext) + 1:
                by_stem.setdefault(f[:-len(ext) - 1], f)
    for name, fname in by_stem.items():
        nodes[f"script:{name}"] = {"id": f"script:{name}", "type": "script", "label": fname,
                                   "disabled": False, "file": f".claude/scripts/{fname}"}

    # synthetic flow anchors
    nodes["gate:merge-request"] = {"id": "gate:merge-request", "type": "gate",
                                   "label": "Merge request", "disabled": False,
                                   "synthetic": True}
    nodes["human"] = {"id": "human", "type": "human", "label": "Human",
                      "disabled": False, "synthetic": True}

    # modules from code-graph.json (best effort, absence is fine). Valid JSON of
    # the wrong shape narrows the graph; it never fails the caller.
    module_names: list[str] = []
    cg = claude / "state" / "code-graph.json"
    g = _load_json(read_text(cg)) if cg.is_file() else None
    mods = _get(g, "modules")
    for name, info in (mods.items() if isinstance(mods, dict) else []):
        # code-graph.json stores files as a path array; a bare count is tolerated
        raw = _get(info, "files")
        count = len(raw) if isinstance(raw, list) else (_i64(raw) or 0)
        owner = _str(_get(info, "owner"))
        owner = "-" if owner is None else owner
        if owner != "-" and f"agent:{owner}" in nodes:
            edges.add((f"agent:{owner}", f"mod:{name}", "owns", 0))
        nodes[f"mod:{name}"] = {"id": f"mod:{name}", "type": "module", "label": name,
                                "disabled": False, "meta": {"files": count, "owner": owner}}
        module_names.append(name)
    raw_edges = _get(g, "edges")
    for e in raw_edges if isinstance(raw_edges, list) else []:
        # an edge is a [from, to] pair or a {"from", "to", "refs"} object
        if isinstance(e, list):
            frm = _str(e[0]) if len(e) > 0 else None
            to = _str(e[1]) if len(e) > 1 else None
        else:
            frm, to = _str(_get(e, "from")), _str(_get(e, "to"))
        if frm is not None and to is not None \
                and f"mod:{frm}" in nodes and f"mod:{to}" in nodes:
            refs = _i64(_get(e, "refs"))
            edges.add((f"mod:{frm}", f"mod:{to}", "references", 1 if refs is None else refs))

    # tasks: every TASK-*.md under docs/tasks/** is a node by contract, and so is
    # every one on an orchestrator-kit board: <board>/{pending,active,completed,
    # canceled}/TASK-NNN[-slug].md plus a TASKS.md index. The folder IS the state.
    task_files: list = []
    walk_tasks(root / "docs" / "tasks", root, task_files)
    task_files.sort()
    board = board_dir(root, settings_v)
    board_files: list = []
    if board is not None and not board.startswith("docs/tasks"):
        walk_tasks(root / board, root, board_files)
        board_files.sort()
    index = board_index(root / board / "TASKS.md") if board is not None else {}
    has_index = board is not None and (root / board / "TASKS.md").is_file()
    indexed_seen: set[str] = set()
    for stem, relpath, on_board in ([(s, r, False) for s, r in task_files]
                                    + [(s, r, True) for s, r in board_files]):
        body = read_text(root / relpath)
        fm = frontmatter(body)
        # task.sh writes `agent:` and `depends_on:` where the docs/tasks
        # templates write `owner:` and `deps:`; same fields, other spelling.
        for canon, alias in (("owner", "agent"), ("deps", "depends_on")):
            if canon not in fm and alias in fm:
                fm[canon] = fm[alias]
        meta = {}
        for key in ("title", "status", "fr", "owner", "deps", "priority", "phase"):
            if isinstance(fm.get(key), str):
                v = unquote(strip_comment(fm[key]))
                # task.sh writes `-` for "none"; on its board that is no value at all
                if v and (not on_board or v != "-"):
                    meta[key] = v
        if on_board:
            folder = pathlib.PurePosixPath(relpath).parent.name
            if folder in BOARD_STATES:
                meta.setdefault("status", folder)
                # task.sh check, restated: folder, `status:` and the index row must
                # agree. Record what disagrees rather than pick a winner.
                drift = []
                if meta["status"] != folder:
                    drift.append(f"status: {meta['status']} but the file is in {folder}/")
                tid = task_id(stem)
                row = index.get(tid)
                if row is not None:
                    if row["state"] != folder:
                        drift.append(f"TASKS.md says {row['state']} but the file is in {folder}/")
                elif has_index:
                    drift.append("no row in TASKS.md")
                indexed_seen.add(tid)
                if drift:
                    meta["drift"] = drift
            for key in ("mission", "attempts"):
                if isinstance(fm.get(key), str):
                    v = unquote(strip_comment(fm[key]))
                    if v and v != "-":
                        meta[key] = v
            meta["board"] = board
        node = {"id": f"task:{stem}", "type": "task", "label": stem, "disabled": False,
                "file": relpath}
        if meta:
            node["meta"] = meta
        nodes[f"task:{stem}"] = node
        # agent -owns-> task, only when the named seat exists. Real boards co-own
        # a task as "frontend-ui-dev+platform-dev": one edge per named seat.
        if isinstance(fm.get("owner"), str):
            for one in unquote(strip_comment(fm["owner"])).split("+"):
                one = _trim(one)
                if one and one in agent_names:
                    edges.add((f"agent:{one}", f"task:{stem}", "owns", 0))
        for m in module_names:
            if m in body:
                edges.add((f"task:{stem}", f"mod:{m}", "references", 0))
    # A TASKS.md row whose file is in no state folder: the index promises work the
    # board cannot show. It still gets a node, so the gap is visible.
    for tid, row in index.items():
        if tid in indexed_seen or f"task:{tid}" in nodes:
            continue
        meta = {k: row[src] for k, src in (("title", "title"), ("owner", "owner"),
                                           ("status", "state"), ("deps", "deps")) if row[src]}
        meta["board"] = board
        meta["drift"] = ["in TASKS.md but no file in any state folder"]
        nodes[f"task:{tid}"] = {"id": f"task:{tid}", "type": "task", "label": tid,
                                "disabled": False, "meta": meta}
        for one in row["owner"].split("+"):
            one = _trim(one)
            if one and one in agent_names:
                edges.add((f"agent:{one}", f"task:{tid}", "owns", 0))

    for rule_id in gating_rules:
        for agent in agent_names:
            edges.add((rule_id, f"agent:{agent}", "gates", 0))

    # skills: .claude/skills/<slug>/SKILL.md. A skill's own agents and scripts are
    # internal to it, not roster seats, so they are meta rather than nodes.
    skill_names: set[str] = set()
    skills_dir = claude / "skills"
    for name in _names(skills_dir):
        sd = skills_dir / name
        sm = sd / "SKILL.md"
        if not sd.is_dir() or not sm.is_file():
            continue
        meta = {}
        d = description(frontmatter(read_text(sm)))
        if d:
            meta["description"] = d
        for extra in ("agents", "scripts"):
            try:
                n = sum(1 for _ in (sd / extra).iterdir())
            except OSError:
                n = 0
            if n:
                meta[f"own_{extra}"] = n
        nodes[f"skill:{name}"] = {"id": f"skill:{name}", "type": "skill", "label": name,
                                  "file": f".claude/skills/{name}/SKILL.md",
                                  "disabled": False, "meta": meta}
        skill_names.add(name)
    # agent -uses-> skill, from the declaration line, and only for an installed skill
    for dir_tail in (".claude/agents", ".claude/disabled/agents"):
        for name in md_stems(root / dir_tail):
            for line in _lines(read_text(root / dir_tail / f"{name}.md")):
                val = skill_decl_value(line)
                if val is None:
                    continue
                for tok in slug_tokens(val):
                    if tok in skill_names:
                        edges.add((f"agent:{name}", f"skill:{tok}", "uses", 0))

    # instruction files: AGENTS.md, CLAUDE.md and the per-tool equivalents. The
    # only nodes outside .claude/, and the point of them: they are the contract
    # every seat is told to obey.
    instr_found = instruction_files(root)
    agent_tier: dict[str, str] = {}
    rule_names = [n["label"] for n in nodes.values()
                  if n["type"] == "rule" and not n["disabled"]]
    for entry, name, relpath in instr_found:
        key, path, ext, tools, source, verified, note = entry
        nid = f"instr:{key}" if not name else f"instr:{key}/{name}"
        text = read_text(root / relpath)
        imeta: dict = {"tools": list(tools), "source": source, "verified": verified}
        if note:
            imeta["note"] = note
        # Size travels with the node so `assess` can tell a per-folder contract that
        # governs a subtree from one that only looks like it does.
        imeta["bytes"] = _blen(text)
        node = {"id": nid, "type": "instruction", "label": relpath, "file": relpath,
                "disabled": False, "meta": imeta, "edit": {"key": key, "name": name}}
        rows = tier_rows(text)
        if rows:
            for row in rows:
                # A tier row that NAMES a seat routes to it. The Direct and Standard
                # rows say "the owning agent" and name nobody, so they route to nobody.
                for tok in slug_tokens(row["who"]):
                    if tok in agent_names:
                        agent_tier[tok] = row["tier"]
                        edges.add((nid, f"agent:{tok}", "routes", 0))
            node["tiers"] = rows
        nodes[nid] = node
        # CLAUDE.md is a thin `@AGENTS.md` import, and saying so in the graph is
        # what stops a reader treating it as a second, competing contract.
        for other, other_name, other_rel in instr_found:
            if other_name or other_rel == relpath:
                continue
            if f"@{other_rel}" in text:
                edges.add((nid, f"instr:{other[0]}", "imports", 0))
        # A rule the contract points at by its path; "testing" in prose does not count.
        norm = text.replace("\\", "/")
        for r in rule_names:
            if f"rules/{r}.md" in norm:
                edges.add((nid, f"rule:{r}", "cites", 0))
        # A seat the contract briefs, by exact slug token.
        tokens = set(slug_tokens(text))
        for a in agent_names:
            if a in tokens:
                edges.add((nid, f"agent:{a}", "briefs", 0))
    for a, tier in agent_tier.items():
        n = nodes.get(f"agent:{a}")
        if n is not None:
            n.setdefault("meta", {})["tier"] = tier

    # Edges read out of the files themselves - what each agent, rule, command,
    # hook, skill and instruction file names. Twin of content_edges() in scan.rs.
    inv: dict[str, set] = {k: set() for k in ("agent", "skill", "rule", "command",
                                              "hook", "script")}
    for nid, n in nodes.items():
        if n["type"] in inv and ":" in nid:
            inv[n["type"]].add(nid.split(":", 1)[1])
    for nid, n in list(nodes.items()):
        kind = n["type"]
        if kind not in ("agent", "rule", "command", "hook", "skill", "instruction") \
                or "file" not in n:
            continue
        text = read_text(root / n["file"])
        for to_kind, name in references(text, inv):
            to = f"{_PREFIX.get(to_kind, to_kind)}:{name}"
            if to != nid:
                edges.add((nid, to, edge_type(kind, to_kind), 0))
        # Claude Code's own subagent field: `skills:` preloads those skills
        # into the seat, which is a wire whatever the names look like.
        if kind == "agent" and "skills" in (fm := frontmatter(text)):
            for sk in as_list(fm["skills"]):
                if sk in inv["skill"]:
                    edges.add((nid, f"skill:{sk}", "uses", 0))
    # A hook nothing registers but another hook sources is a library, not a
    # hook that was switched off.
    for (_f, t, ty, _r) in list(edges):
        if ty == "sources":
            m = nodes.get(t, {}).get("meta")
            if isinstance(m, dict) and m.get("registered") is False:
                m["library"] = True

    # Who can start whom. `Agent(a, b)` in a seat's tools names exactly who it may
    # spawn; the orchestrator, or any seat holding a bare `Agent`, can spawn every
    # other seat on the roster.
    for agent in agent_names:
        m = nodes.get(f"agent:{agent}", {}).get("meta") or {}
        named = m.get("spawns") if isinstance(m.get("spawns"), list) else None
        tools = m.get("tools") if isinstance(m.get("tools"), list) else []
        bare = any(t in ("Agent", "Task") for t in tools)
        if named is not None:
            targets = [a for a in agent_names if a in named]
        elif agent == "orchestrator" or bare:
            targets = list(agent_names)
        else:
            targets = []
        for t in targets:
            if t != agent:
                edges.add((f"agent:{agent}", f"agent:{t}", "spawns", 0))
    # orchestrator-kit's spawn-guard.sh admits, besides the roster, the built-in
    # agents listed one per line in .claude/hooks/spawn-allowlist. Built-ins are
    # not nodes, so the list rides on the seat whose guard reads it.
    allow_path = claude / "hooks" / "spawn-allowlist"
    if allow_path.is_file():
        allow = [x for x in (_trim(ln.split("#", 1)[0]) for ln in _lines(read_text(allow_path)))
                 if x]
        readers = sorted({r.source[len("agent:"):] for r in agent_regs
                          if r.hook in hook_files and r.source.startswith("agent:")
                          and "spawn-allowlist" in read_text(root / hook_files[r.hook][0])})
        seats = readers or [a for a in agent_names if a == "orchestrator"]
        for s in seats:
            m = nodes.get(f"agent:{s}", {}).get("meta")
            if isinstance(m, dict):
                m["spawnAllowlist"] = allow
    for r in agent_names:
        # active seats only - a parked agent file reviews nothing
        if is_review_seat(r):
            edges.add((f"agent:{r}", "gate:merge-request", "reviews", 0))
    edges.add(("gate:merge-request", "human", "escalates", 0))
    for cmd_id in active_commands:
        edges.add(("human", cmd_id, "invokes", 0))
    # Every ".claude/scripts/<name>.py" a command names counts, whether or not the
    # script exists yet - the dangling edge records the broken wiring. The
    # ".claude/" prefix is required: a skill's own "<skill>/scripts/x.py" is not
    # an installed script.
    needle = ".claude/scripts/"
    for cmd_id in [i for i, n in nodes.items() if n["type"] == "command"]:
        norm = read_text(root / nodes[cmd_id]["file"]).replace("\\", "/")
        start = 0
        while True:
            i = norm.find(needle, start)
            if i < 0:
                break
            at = i + len(needle)
            j = at
            while j < len(norm) and (_ascii_alnum(norm[j]) or norm[j] in "-_"):
                j += 1
            name = norm[at:j]
            start = at + max(len(name), 1)
            if name and norm.startswith(".py", min(start, len(norm))):
                edges.add((cmd_id, f"script:{name}", "runs", 0))

    edge_list = [{"from": f, "to": t, "type": ty, **({"refs": r} if r > 0 else {})}
                 for (f, t, ty, r) in sorted(edges)]
    return {"version": 1,
            "nodes": [nodes[k] for k in sorted(nodes)],
            "edges": edge_list}


def main() -> int:
    argv = sys.argv[1:]
    root = pathlib.Path(argv[argv.index("--target") + 1]).resolve() \
        if "--target" in argv else pathlib.Path(".").resolve()
    quiet = "--quiet" in argv

    if not (root / ".claude").is_dir():
        if not quiet:
            print("harness-graph: no .claude/ directory here - nothing to scan")
        return 1

    graph = build(root)
    out = root / ".claude" / "state" / "harness-graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" is load-bearing, not style. Without it write_text uses the platform default,
    # so this scanner emitted CRLF on Windows while harness-view emitted LF for the same repo -
    # identical content, different bytes, and the schema's promise is that the two agree BYTE
    # for byte. It also stops a generated JSON file from churning every diff on a mixed team.
    # ensure_ascii=False for the same reason: harness-view writes UTF-8 as is, so escaping a
    # Japanese description here made the two scanners disagree on every non-ASCII repo while
    # the ASCII-only fixture kept passing.
    out.write_text(json.dumps(graph, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    if not quiet:
        print(f"harness-graph: {len(graph['nodes'])} nodes, "
              f"{len(graph['edges'])} edges -> {out.relative_to(root).as_posix()}")

    if "--html" in argv:
        # graph-html.py has a hyphen in its name, so import it by path.
        import importlib.util
        gh = pathlib.Path(__file__).with_name("graph-html.py")
        if gh.is_file():
            spec = importlib.util.spec_from_file_location("graph_html", gh)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            res = mod.harness_graph(root)
            if res and not quiet:
                print(f"harness-graph: wrote {res}")
        elif not quiet:
            print("harness-graph: graph-html.py not found beside this script - JSON only")
    return 0


if __name__ == "__main__":
    sys.exit(main())

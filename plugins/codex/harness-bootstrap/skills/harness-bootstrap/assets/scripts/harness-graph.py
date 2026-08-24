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
                          briefs | cites | imports | routes

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

NODE_TYPES = ("agent", "rule", "command", "hook", "settings", "script",
              "module", "task", "gate", "human", "skill", "instruction")
EDGE_TYPES = ("gates", "triggers", "enforces", "reviews", "owns", "spawns",
              "runs", "invokes", "escalates", "references", "uses",
              "briefs", "cites", "imports", "routes")

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

# A wired skill is recorded in the SEAT's body: /skill-wire adds "a new entry
# under the seat's Skills available section". A declaration line is therefore the
# only trustworthy signal. Matching a bare skill name anywhere in an agent file
# invents wiring: five of ost's agents contain the word "performance"
# ("performance budgets", "performance NFRs") while the skill of that name is
# wired to no seat at all.
SKILL_DECL_RE = re.compile(
    r"^[^\n]*\bskills?\b[^\n:]*(?:available|to load|in use|when relevant)[^\n:]*:(.+)$",
    re.I | re.M)
SKILL_TOKEN_RE = re.compile(r"[A-Za-z0-9][\w.-]*[A-Za-z0-9]|[A-Za-z0-9]")

# Which rule each hook exists to enforce. This relationship lives in prose
# (hooks/README.md, the rules themselves); the table makes it machine-readable.
# graph-stale is informational and enforces nothing.
ENFORCES = {
    "protect-secrets": "security-privacy",
    "check-commit-msg": "conventional-commits",
    "guard-main-commit": "conventional-commits",
    "protect-adr": "docs-workflow",
    "specs-reminder": "docs-workflow",
    "guard-agent-scope": "agent-guardrails",
    "guard-agent-spawn": "agent-guardrails",
    "agent-history": "task-tracking",
    "protect-repos": "security-privacy",
}

# Seats that gate the merge request (edge agent -reviews-> gate:merge-request).
REVIEW_SEATS = {"code-reviewer", "security-reviewer", "spec-guardian",
                "reviewer", "merge-manager"}


def read_text(p: pathlib.Path, limit: int | None = None) -> str:
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
        return t[:limit] if limit else t
    except OSError:
        return ""


def frontmatter_field(head: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*(.+?)\s*$", head, re.M)
    return m.group(1) if m else None


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s.strip()


def frontmatter_list(head: str, key: str) -> list[str]:
    """A frontmatter value that may be written inline or as a YAML block list.

    `tools: Read, Edit` and

        tools:
          - Read
          - Edit

    are both legal and both appear in real agent files. frontmatter_field cannot read the
    second: its `\\s*` crosses the newline, so it returned the single item "- Read" with the
    dash still attached, while the Rust scanner returned all three. The schema promises the
    two scanners agree byte for byte, so this is a parity break, not a cosmetic one.
    """
    m = re.search(rf"^{key}:[ \t]*(.*)$", head, re.M)
    if not m:
        return []
    inline = m.group(1).strip()
    if inline:
        inline = inline.strip().lstrip("[").rstrip("]")
        return [p for p in (_unquote(x) for x in inline.split(",")) if p]
    out: list[str] = []
    for line in head[m.end():].splitlines():
        if not line.strip():
            continue
        stripped = line.lstrip()
        if not stripped.startswith("- "):
            break
        out.append(_unquote(stripped[2:]))
    return out


def strip_comment(s: str) -> str:
    """Drop a trailing YAML comment: `Done # Active | Blocked` -> `Done`.

    A `#` only opens a comment when whitespace precedes it, so `P0#1` survives.
    Real task files keep the template's enum comment on the line, and without
    this the status reads as "Done # Active | Blocked | Pending | Done".
    """
    if s[:1] in ('"', "'"):
        return s
    for i, ch in enumerate(s):
        if ch == "#" and (i == 0 or s[i - 1].isspace()):
            return s[:i].rstrip()
    return s


def unquote(s: str) -> str:
    """Strip one matched pair of surrounding quotes."""
    t = s.strip()
    if len(t) >= 2 and t[0] in "\"'" and t[-1] == t[0]:
        return t[1:-1]
    return t


def frontmatter_block(text: str) -> str:
    """The leading `---` fenced block, or "" when the file has none.

    Read the BLOCK, not the first N bytes: a `description:` line in the prose
    body is not frontmatter, and a long value can sit past any byte cap. The
    Rust twin parses the block the same way, and the two must agree exactly.
    """
    if not text.startswith("---"):
        return ""
    rest = text[3:]
    end = rest.find("\n---")
    return rest[:end] if end != -1 else rest


def description_field(text: str) -> str | None:
    """Frontmatter `description:`, trimmed and capped at 300 chars.

    The viewer shows this in its sidebar, so a runaway value must not push the
    rest of the panel off screen; the full text is one Preview click away.
    """
    raw = frontmatter_field(frontmatter_block(text), "description")
    if not raw:
        return None
    d = unquote(raw).strip()
    if not d:
        return None
    return d[:300] + "..." if len(d) > 300 else d


def load_disabled(claude: pathlib.Path) -> dict[str, dict]:
    """-> {'<kind>/<name>': entry} from .claude/disabled.json (absent = empty)."""
    out: dict[str, dict] = {}
    f = claude / "disabled.json"
    if f.is_file():
        try:
            data = json.loads(read_text(f))
            for e in data.get("disabled", []):
                if isinstance(e, dict) and e.get("kind") and e.get("name"):
                    out[f"{e['kind']}/{e['name']}"] = e
        # AttributeError/KeyError too: a file that is VALID JSON but the wrong shape (a
        # list where a dict belongs, a dict missing 'edges') raises neither of the two
        # errors this used to catch, so the docstring's "never fails the caller" was
        # false for exactly the hand-edited state files most likely to be wrong.
        except (json.JSONDecodeError, TypeError, AttributeError, KeyError):
            data = {}
        if not isinstance(data, dict):
            data = {}
    return out


def hook_registrations(claude: pathlib.Path) -> dict[str, dict]:
    """-> {hook stem: {'event','matcher'}} parsed from settings.json.

    A settings.json that is still a template (unresolved conditionals) simply
    parses as nothing - every hook then reports registered false, which is the
    honest answer for an unscaffolded tree.
    """
    reg: dict[str, dict] = {}
    f = claude / "settings.json"
    if not f.is_file():
        return reg
    try:
        data = json.loads(read_text(f))
    except (json.JSONDecodeError, TypeError, AttributeError, KeyError):
        return reg
    if not isinstance(data, dict):
        return reg
    for event, groups in (data.get("hooks") or {}).items():
        if not isinstance(groups, list):
            continue
        for g in groups:
            matcher = g.get("matcher", "*") if isinstance(g, dict) else "*"
            for h in (g.get("hooks") or []) if isinstance(g, dict) else []:
                cmd = h.get("command", "") if isinstance(h, dict) else ""
                m = re.search(r"hooks/([\w-]+)\.(?:sh|ps1)", cmd)
                if m and m.group(1) not in reg:
                    reg[m.group(1)] = {"event": event, "matcher": matcher}
    return reg


def _cells(line: str) -> list[str]:
    t = line.strip()
    if not t.startswith("|"):
        return []
    return [c.strip().strip("*").strip() for c in t.strip("|").split("|")]


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
    lines = text.splitlines()
    for i, line in enumerate(lines):
        head = _cells(line)
        if len(head) < 3:
            continue
        lower = [c.lower() for c in head]
        if lower[0] != "tier" or not any("who runs" in c for c in lower):
            continue
        who_at = next((j for j, c in enumerate(lower) if "who runs" in c), 2)
        change_at = next((j for j, c in enumerate(lower) if "change" in c), 1)
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
    claude = root / ".claude"
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str, int]] = set()

    def add_node(id_: str, type_: str, label: str, file: str | None = None,
                 disabled: bool = False, synthetic: bool = False,
                 meta: dict | None = None, edit: dict | None = None,
                 tiers: list | None = None) -> None:
        n: dict = {"id": id_, "type": type_, "label": label, "disabled": disabled}
        if file:
            n["file"] = file
        if synthetic:
            n["synthetic"] = True
        if meta:
            n["meta"] = meta
        # The write path takes a key and a bare name, never a path. A node that
        # carries these is one the viewer's editor may address; a node without
        # them is read-only, and that is the whole permission model.
        if edit is not None:
            n["edit"] = edit
        if tiers:
            n["tiers"] = tiers
        nodes[id_] = n

    def add_edge(frm: str, to: str, type_: str, refs: int = 0) -> None:
        edges.add((frm, to, type_, refs))

    def rel(p: pathlib.Path) -> str:
        return p.relative_to(root).as_posix()

    disabled_entries = load_disabled(claude)

    # settings (no meta by contract: id/type/label/file/disabled only). It does
    # carry `edit`, because the viewer edits it through the same key-and-name
    # write path the instruction files use.
    if (claude / "settings.json").is_file():
        add_node("settings", "settings", "settings.json",
                 file=".claude/settings.json",
                 edit={"key": "settings", "name": ""})

    # agents (active + disabled are both nodes; disabled agents are not a
    # supported toggle, but a file parked there still deserves visibility)
    agent_dirs = [(claude / "agents", False), (claude / "disabled" / "agents", True)]
    agents: list[str] = []
    for d, dis in agent_dirs:
        for a in sorted(d.glob("*.md")) if d.is_dir() else []:
            head = read_text(a, 700)
            meta: dict = {"model": frontmatter_field(head, "model") or "inherit"}
            eff = frontmatter_field(head, "effort")
            if eff:
                meta["effort"] = eff
            mt = frontmatter_field(head, "maxTurns")
            if mt and mt.isdigit():
                meta["maxTurns"] = int(mt)
            # `tools` first, then `allowed-tools`, first non-empty wins - the same order and
            # the same fallback the Rust scanner uses.
            for key in ("tools", "allowed-tools"):
                tools = frontmatter_list(head, key)
                if tools:
                    meta["tools"] = tools
                    break
            desc = description_field(read_text(a))
            if desc:
                meta["description"] = desc
            add_node(f"agent:{a.stem}", "agent", a.stem, file=rel(a),
                     disabled=dis, meta=meta)
            if not dis:
                agents.append(a.stem)
    # skills: .claude/skills/<slug>/SKILL.md. A skill may carry its own agents
    # and scripts, but those are internal to the skill and are NOT roster seats,
    # so they are recorded as meta rather than drawn as harness nodes.
    skills_dir = claude / "skills"
    skills: set[str] = set()
    for sd in sorted(skills_dir.iterdir()) if skills_dir.is_dir() else []:
        sm = sd / "SKILL.md"
        if not sd.is_dir() or not sm.is_file():
            continue
        skills.add(sd.name)
        smeta: dict = {}
        sdesc = description_field(read_text(sm))
        if sdesc:
            smeta["description"] = sdesc
        for extra in ("agents", "scripts"):
            n = len(list((sd / extra).glob("*"))) if (sd / extra).is_dir() else 0
            if n:
                smeta["own_" + extra] = n
        add_node(f"skill:{sd.name}", "skill", sd.name, file=rel(sm), meta=smeta)

    # agent -uses-> skill, from the declaration line only, and only when the
    # skill is actually installed: an edge to a node that does not exist would
    # dangle in every viewer. A seat declaring a skill that is NOT installed is
    # reported by the assessment, which reads the seat files directly.
    for d, dis in agent_dirs:
        for a in sorted(d.glob("*.md")) if d.is_dir() else []:
            for decl in SKILL_DECL_RE.findall(read_text(a)):
                for tok in SKILL_TOKEN_RE.findall(decl):
                    if tok in skills:
                        add_edge(f"agent:{a.stem}", f"skill:{tok}", "uses")

    if "orchestrator" in agents:
        for name in agents:
            if name != "orchestrator":
                add_edge("agent:orchestrator", f"agent:{name}", "spawns")

    # rules
    for d, dis in [(claude / "rules", False), (claude / "disabled" / "rules", True)]:
        for rl in sorted(d.glob("*.md")) if d.is_dir() else []:
            head = read_text(rl, 400)
            scoped = head.startswith("---") and "paths:" in head[3:].split("---", 1)[0]
            meta = {"scoped": bool(scoped)}
            if scoped:
                pm = re.findall(r"^\s*-\s*['\"]?([^'\"\n]+?)['\"]?\s*$",
                                head.split("paths:", 1)[1].split("---", 1)[0], re.M)
                if pm:
                    meta["paths"] = pm[:8]
            desc = description_field(read_text(rl))
            if desc:
                meta["description"] = desc
            entry = disabled_entries.get(f"rule/{rl.stem}")
            add_node(f"rule:{rl.stem}", "rule", rl.stem, file=rel(rl),
                     disabled=dis or bool(entry), meta=meta)
            if not dis and not scoped:
                for name in agents:
                    add_edge(f"rule:{rl.stem}", f"agent:{name}", "gates")

    # scripts: complete inventory of .claude/scripts/*.py by contract, whether or
    # not any command references them
    scripts_dir = claude / "scripts"
    for sp in sorted(scripts_dir.glob("*.py")) if scripts_dir.is_dir() else []:
        add_node(f"script:{sp.stem}", "script", sp.name, file=rel(sp))

    # commands (+ a runs edge for EVERY .claude/scripts/<name>.py reference)
    for d, dis in [(claude / "commands", False), (claude / "disabled" / "commands", True)]:
        for c in sorted(d.glob("*.md")) if d.is_dir() else []:
            body = read_text(c)
            cmeta = {}
            desc = description_field(body)
            if desc:
                cmeta["description"] = desc
            add_node(f"cmd:{c.stem}", "command", "/" + c.stem, file=rel(c), disabled=dis,
                     meta=cmeta or None)
            for s in sorted(set(re.findall(r"\.claude/scripts/([\w-]+)\.py", body))):
                # nodes are the on-disk inventory; a reference to a script that
                # does not exist stays a dangling edge (the viewers tolerate it)
                add_edge(f"cmd:{c.stem}", f"script:{s}", "runs")
            if not dis:
                add_edge("human", f"cmd:{c.stem}", "invokes")

    # hooks (a hook is one seat with up to two flavor files)
    reg = hook_registrations(claude)
    hook_files: dict[str, list[pathlib.Path]] = {}
    for d, dis in [(claude / "hooks", False), (claude / "disabled" / "hooks", True)]:
        if not d.is_dir():
            continue
        for hf in sorted(list(d.glob("*.sh")) + list(d.glob("*.ps1"))):
            hook_files.setdefault(hf.stem, []).append(hf)
    for stem in sorted(hook_files):
        files = hook_files[stem]
        dis = all("disabled" in f.parts for f in files)
        # File tie-break by contract: the .sh flavor if present, else the .ps1;
        # an active flavor beats a disabled one at equal extension.
        files = sorted(files, key=lambda f: (f.suffix != ".sh",
                                             "disabled" in f.parts, f.name))
        r = reg.get(stem)
        meta = {"registered": bool(r)}
        if r:
            meta["event"] = r["event"]
            meta["matcher"] = r["matcher"]
            meta["blocking"] = r["event"] == "PreToolUse"
        entry = disabled_entries.get(f"hook/{stem}")
        add_node(f"hook:{stem}", "hook", stem, file=rel(files[0]),
                 disabled=dis or bool(entry), meta=meta)
        if r and "settings" in nodes:
            add_edge("settings", f"hook:{stem}", "triggers")
        target_rule = ENFORCES.get(stem)
        if target_rule and f"rule:{target_rule}" in nodes:
            add_edge(f"hook:{stem}", f"rule:{target_rule}", "enforces")

    # synthetic flow nodes
    add_node("gate:merge-request", "gate", "Merge request", synthetic=True)
    add_node("human", "human", "Human", synthetic=True)
    add_edge("gate:merge-request", "human", "escalates")
    for name in sorted(REVIEW_SEATS & set(agents)):
        add_edge(f"agent:{name}", "gate:merge-request", "reviews")

    # code modules (from code-graph.py) + ownership
    cg = claude / "state" / "code-graph.json"
    if cg.is_file():
        try:
            g = json.loads(read_text(cg))
        # AttributeError/KeyError too: a file that is VALID JSON but the wrong shape (a
        # list where a dict belongs, a dict missing 'edges') raises neither of the two
        # errors this used to catch, so the docstring's "never fails the caller" was
        # false for exactly the hand-edited state files most likely to be wrong.
        except (json.JSONDecodeError, TypeError, AttributeError, KeyError):
            g = {}
        # Valid JSON of the wrong SHAPE is the common case for a hand-edited state file, and it
        # raises nothing at parse time. Normalise here so every .get() below is safe.
        if not isinstance(g, dict):
            g = {}
        mods = g.get("modules")
        for mod, info in (mods if isinstance(mods, dict) else {}).items():
            # Element shape is as untrusted as container shape: a JSON file can be a valid dict
            # whose values are strings. Skip what is not usable rather than crashing the caller.
            if not isinstance(info, dict):
                continue
            owner = info.get("owner", "-") or "-"
            # code-graph.json stores files as a path array; a bare COUNT is tolerated for
            # forward compatibility. The Rust twin already did this and the Python side did
            # not, so a graph carrying a count crashed this scanner with "object of type
            # 'int' has no len()" while harness-view scanned it happily - a parity break that
            # showed up as a crash rather than a diff.
            raw_files = info.get("files", [])
            files = len(raw_files) if isinstance(raw_files, (list, tuple)) else (
                raw_files if isinstance(raw_files, int) else 0)
            add_node(f"mod:{mod}", "module", mod,
                     meta={"files": files, "owner": owner})
            if owner != "-" and f"agent:{owner}" in nodes:
                add_edge(f"agent:{owner}", f"mod:{mod}", "owns")
        raw_edges = g.get("edges")
        for e in (raw_edges if isinstance(raw_edges, list) else []):
            # code-graph.json writes an edge either as a [from, to] pair or as a
            # {"from":..., "to":..., "refs":...} object. The Rust twin accepted both and this
            # side accepted only the object, so a pair-shaped graph produced FEWER edges here
            # than in harness-view - a silent parity break, and the schema's whole promise is
            # that the two scanners agree byte for byte.
            if isinstance(e, (list, tuple)):
                frm = e[0] if len(e) > 0 else None
                to = e[1] if len(e) > 1 else None
                refs = 1
            elif isinstance(e, dict):
                frm, to = e.get("from"), e.get("to")
                raw_refs = e.get("refs", 1)
                refs = raw_refs if isinstance(raw_refs, int) else 1
            else:
                continue
            if not (isinstance(frm, str) and isinstance(to, str)):
                continue
            f_, t_ = f"mod:{frm}", f"mod:{to}"
            if f_ in nodes and t_ in nodes:
                add_edge(f_, t_, "references", refs)

    # tasks: EVERY TASK-*.md under docs/tasks/** is a node by contract;
    # references edges only where the body names a module path
    tasks_dir = root / "docs" / "tasks"
    if tasks_dir.is_dir():
        mod_names = [(n["label"], n["label"].split("/")[-1])
                     for n in nodes.values() if n["type"] == "module"]
        for t in sorted(tasks_dir.rglob("TASK-*.md")):
            body = read_text(t)
            fm = frontmatter_block(body)
            # The board fields, in the order the task template declares them.
            # This is what makes a task readable without opening the file.
            tmeta = {}
            for key in ("title", "status", "fr", "owner", "deps", "priority", "phase"):
                v = frontmatter_field(fm, key)
                if v:
                    v = unquote(strip_comment(v)).strip()
                    if v:
                        tmeta[key] = v
            add_node(f"task:{t.stem}", "task", t.stem, file=rel(t), meta=tmeta or None)
            # agent -owns-> task, the same edge type an agent uses for a module.
            # Emitted only when the named seat exists: a task owned by a retired
            # agent would otherwise anchor to nothing. (Contrast `runs`, which is
            # deliberately allowed to dangle - a command naming a missing script
            # is itself the finding.)
            # Real boards co-own a task as "frontend-ui-dev+platform-dev", so
            # each named seat gets its own edge. Dropping the pair entirely
            # would leave a task that HAS owners looking unowned.
            for one in (tmeta.get("owner") or "").split("+"):
                one = one.strip()
                if one and one in agents:
                    add_edge(f"agent:{one}", f"task:{t.stem}", "owns")
            for m in [m for m, base in mod_names if base and base in body]:
                add_edge(f"task:{t.stem}", f"mod:{m}", "references")

    # instruction files: AGENTS.md, CLAUDE.md and the per-tool equivalents. The
    # only nodes outside .claude/, and the point of them: they are the contract
    # every seat is told to obey, so a graph that stopped at the .claude/
    # boundary drew every enforcement mechanism and none of the thing enforced.
    instr_found = instruction_files(root)
    instr_ids = {e[0]: f"instr:{e[0]}" for e, name, _ in instr_found if not name}
    rule_labels = [n["label"] for n in nodes.values()
                   if n["type"] == "rule" and not n["disabled"]]
    agent_tier: dict[str, str] = {}
    for entry, name, relpath in instr_found:
        key, path, ext, tools, source, verified, note = entry
        nid = f"instr:{key}" if not name else f"instr:{key}/{name}"
        text = read_text(root / relpath)
        imeta: dict = {"tools": list(tools), "source": source, "verified": verified}
        if note:
            imeta["note"] = note
        # Size travels with the node so `assess` can tell a per-folder contract that governs a
        # subtree from one that only looks like it does. Counted from the text already read for
        # the tier parse below, so it costs nothing extra. Twin of the same line in scan.rs.
        # From the BYTES on disk, not from `text`: read_text normalises CRLF to LF, so a file
        # checked out natively on Windows would be counted three bytes short per line and the two
        # scanners would disagree on every one. That is the same native-checkout trap that has bitten
        # this repo in the plugin tree, the scaffolder and the step fixtures.
        try:
            imeta["bytes"] = (root / relpath).stat().st_size
        except OSError:
            imeta["bytes"] = len(text.encode("utf-8"))
        rows = tier_rows(text)
        for row in rows:
            # A tier row that NAMES a seat routes to it. The Direct and Standard
            # rows say "the owning agent" and name nobody, so they route to
            # nobody: guessing which seats they mean is exactly the invention
            # the table exists to replace.
            for tok in SKILL_TOKEN_RE.findall(row["who"]):
                if tok in agents:
                    agent_tier[tok] = row["tier"]
                    add_edge(nid, f"agent:{tok}", "routes")
        add_node(nid, "instruction", relpath, file=relpath, meta=imeta,
                 edit={"key": key, "name": name}, tiers=rows or None)
        # CLAUDE.md says @AGENTS.md, and saying so in the graph is what stops a
        # reader treating it as a second, competing contract.
        for other_key, other_id in instr_ids.items():
            if other_id == nid:
                continue
            other_rel = next(r for e, n2, r in instr_found
                             if e[0] == other_key and not n2)
            if f"@{other_rel}" in text:
                add_edge(nid, other_id, "imports")
        # A rule the contract actually points at, matched by the path it cites
        # rather than by the bare word: "testing" appears in prose everywhere,
        # `.claude/rules/testing.md` does not.
        norm = text.replace("\\", "/")
        for r in rule_labels:
            if f"rules/{r}.md" in norm:
                add_edge(nid, f"rule:{r}", "cites")
        # A seat the contract briefs. Agent names are slugs, so a token match is
        # exact; a substring match would brief every seat whose name happens to
        # sit inside another word.
        tokens = set(SKILL_TOKEN_RE.findall(text))
        for a in agents:
            if a in tokens:
                add_edge(nid, f"agent:{a}", "briefs")
    for a, tier in agent_tier.items():
        n = nodes.get(f"agent:{a}")
        if n is not None:
            n.setdefault("meta", {})["tier"] = tier

    edge_list = [{"from": f, "to": t, "type": ty, **({"refs": r} if r else {})}
                 for (f, t, ty, r) in edges
                 if f in nodes and (t in nodes or ty == "runs")]
    edge_list.sort(key=lambda e: (e["from"], e["to"], e["type"]))
    return {"version": 1,
            "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
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
    out.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n",
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

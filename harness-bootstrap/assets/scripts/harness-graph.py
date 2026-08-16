#!/usr/bin/env python3
"""Scan .claude/ and emit the canonical machine-readable harness graph.

Output: .claude/state/harness-graph.json - schema version 1, documented in
docs/HARNESS-GRAPH-SCHEMA.md at the skill repo (and summarized here):

  { "version": 1,
    "nodes": [ {"id", "type", "label", "file"?, "disabled", "synthetic"?, "meta"?} ],
    "edges": [ {"from", "to", "type", "refs"?} ] }

Node types (closed set):  agent | rule | command | hook | settings | script |
                          module | task | gate | human
Edge types (closed enum): gates | triggers | enforces | reviews | owns | spawns |
                          runs | invokes | escalates | references

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
              "module", "task", "gate", "human", "skill")
EDGE_TYPES = ("gates", "triggers", "enforces", "reviews", "owns", "spawns",
              "runs", "invokes", "escalates", "references", "uses")

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


def build(root: pathlib.Path) -> dict:
    claude = root / ".claude"
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str, int]] = set()

    def add_node(id_: str, type_: str, label: str, file: str | None = None,
                 disabled: bool = False, synthetic: bool = False,
                 meta: dict | None = None) -> None:
        n: dict = {"id": id_, "type": type_, "label": label, "disabled": disabled}
        if file:
            n["file"] = file
        if synthetic:
            n["synthetic"] = True
        if meta:
            n["meta"] = meta
        nodes[id_] = n

    def add_edge(frm: str, to: str, type_: str, refs: int = 0) -> None:
        edges.add((frm, to, type_, refs))

    def rel(p: pathlib.Path) -> str:
        return p.relative_to(root).as_posix()

    disabled_entries = load_disabled(claude)

    # settings (no meta by contract: id/type/label/file/disabled only)
    if (claude / "settings.json").is_file():
        add_node("settings", "settings", "settings.json",
                 file=".claude/settings.json")

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
            tools = frontmatter_field(head, "tools")
            if tools:
                meta["tools"] = [t.strip() for t in tools.split(",") if t.strip()]
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
            add_node(f"mod:{mod}", "module", mod,
                     meta={"files": len(info.get("files", [])), "owner": owner})
            if owner != "-" and f"agent:{owner}" in nodes:
                add_edge(f"agent:{owner}", f"mod:{mod}", "owns")
        raw_edges = g.get("edges")
        for e in (raw_edges if isinstance(raw_edges, list) else []):
            if not isinstance(e, dict):
                continue
            f_, t_ = f"mod:{e.get('from')}", f"mod:{e.get('to')}"
            if f_ in nodes and t_ in nodes:
                add_edge(f_, t_, "references", int(e.get("refs", 1)))

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
    out.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
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

#!/usr/bin/env python3
"""Build the repo's code knowledge graph: modules, files, and the import edges between them.

Stdlib only, no install step, so it runs anywhere the harness runs. External graph tools
(a GitNexus or codegraph MCP server, an LSP index) can produce richer graphs; this script is
the portable floor that is always present, and its JSON is the format agents can rely on.

Outputs, from the repo root:
  .claude/state/code-graph.json   machine-readable: modules, files, edges
  docs/context/code-graph.md      agent-readable: mermaid module graph + fan-in/fan-out table

Edges are best-effort STATIC import extraction (regex per language, intra-repo references only).
A missing edge means the extractor did not see it, not that the dependency does not exist -
treat the graph as a map, not as proof of isolation.

Usage:
  python .claude/scripts/code-graph.py            # build from cwd
  python .claude/scripts/code-graph.py --check    # exit 1 if the graph is stale (source newer)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

SKIP_DIRS = {".git", "node_modules", "dist", "build", "vendor", "target", ".venv", "venv",
             "__pycache__", ".claude", ".cursor", ".codex", "coverage", ".next", "out"}

# extension -> list of regexes whose first non-None group is the imported reference
IMPORT_RES: dict[str, list[re.Pattern]] = {
    ".py":  [re.compile(r"^\s*from\s+([\w\.]+)\s+import", re.M),
             re.compile(r"^\s*import\s+([\w\.]+)", re.M)],
    ".js":  [re.compile(r"""from\s+['"]([^'"]+)['"]"""),
             re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")],
    ".go":  [re.compile(r'^\s*"([\w\./-]+)"\s*$', re.M),
             re.compile(r'^\s*import\s+"([\w\./-]+)"', re.M)],
    ".java": [re.compile(r"^import\s+(?:static\s+)?([\w\.]+);", re.M)],
    ".cs":  [re.compile(r"^using\s+([\w\.]+);", re.M)],
    ".rb":  [re.compile(r"""require(?:_relative)?\s+['"]([^'"]+)['"]""")],
    ".php": [re.compile(r"^use\s+([\w\\]+);", re.M)],
    ".rs":  [re.compile(r"^use\s+([\w:]+)", re.M)],
}
for alias, base in (
    (".ts", ".js"), (".tsx", ".js"), (".jsx", ".js"), (".mjs", ".js"), (".cjs", ".js"),
):
    IMPORT_RES[alias] = IMPORT_RES[base]

SOURCE_EXTS = set(IMPORT_RES)


def source_files(root: pathlib.Path) -> list[pathlib.Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in SOURCE_EXTS \
                and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS):
            out.append(p)
    return out


def module_of(rel: pathlib.PurePosixPath) -> str:
    """Module = the first meaningful path segment. src/auth/x.py -> auth; scripts/x.py -> scripts."""
    parts = rel.parts
    if parts[0] in ("src", "app", "lib", "pkg", "packages", "apps") and len(parts) > 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0] if len(parts) > 1 else "(root)"


def imports_of(path: pathlib.Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    found: set[str] = set()
    for rx in IMPORT_RES[path.suffix]:
        found.update(m for m in rx.findall(text) if m)
    return found


def resolve_edges(root: pathlib.Path, files: list[pathlib.Path]) -> dict[tuple[str, str], int]:
    """Map raw import strings back to repo files; keep only intra-repo, cross-module edges."""
    rels = [pathlib.PurePosixPath(f.relative_to(root).as_posix()) for f in files]
    mods = {r: module_of(r) for r in rels}
    # index by stem-ish keys an import string might use
    by_key: dict[str, set[str]] = {}
    for r in rels:
        dotted = ".".join(r.with_suffix("").parts)
        slashed = r.with_suffix("").as_posix()
        for key in (dotted, slashed, r.stem):
            by_key.setdefault(key, set()).add(mods[r])
    edges: dict[tuple[str, str], int] = {}
    for f, r in zip(files, rels):
        src_mod = mods[r]
        for imp in imports_of(f):
            key = imp.lstrip("./").replace("\\", "/").replace("::", ".")
            key = key[2:] if key.startswith("@/") else key
            targets = by_key.get(key) or by_key.get(key.replace("/", ".")) \
                or by_key.get(key.rsplit(".", 1)[0], set()) or by_key.get(key.rsplit("/", 1)[-1], set())
            for dst_mod in targets:
                if dst_mod != src_mod:
                    edges[(src_mod, dst_mod)] = edges.get((src_mod, dst_mod), 0) + 1
    return edges


def owners(root: pathlib.Path) -> dict[str, str]:
    """Best-effort: match 'Owns <paths>' in .claude/agents/*.md descriptions to module prefixes."""
    out: dict[str, str] = {}
    for a in sorted((root / ".claude" / "agents").glob("*.md")) if (root / ".claude" / "agents").exists() else []:
        head = a.read_text(encoding="utf-8", errors="replace")[:600]
        m = re.search(r"Owns\s+([^\.\n]+)", head)
        if m:
            for chunk in re.split(r"[,;]", m.group(1)):
                out[chunk.strip().rstrip("/*").rstrip("/")] = a.stem
    return out


def build(root: pathlib.Path) -> dict:
    files = source_files(root)
    rels = [pathlib.PurePosixPath(f.relative_to(root).as_posix()) for f in files]
    mods: dict[str, list[str]] = {}
    for r in rels:
        mods.setdefault(module_of(r), []).append(str(r))
    edges = resolve_edges(root, files)
    own = owners(root)

    def owner_of(mod: str) -> str:
        for prefix, agent in own.items():
            if mod == prefix or mod.startswith(prefix.rstrip("/") + "/") or prefix.endswith(mod):
                return agent
        return "-"

    return {
        # No generated_at here. These outputs are tracked in git and are prompt-cache
        # prefix content: one volatile byte cold-misses the cache on every later run and
        # turns every docs edit into a timestamp-only diff.
        "modules": {m: {"files": fs, "owner": owner_of(m)} for m, fs in sorted(mods.items())},
        "edges": [{"from": a, "to": b, "refs": n} for (a, b), n in sorted(edges.items())],
    }


def write_outputs(root: pathlib.Path, graph: dict) -> None:
    state = root / ".claude" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "code-graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    (state / "code-graph.stale").unlink(missing_ok=True)

    fan_out: dict[str, int] = {}
    fan_in: dict[str, int] = {}
    for e in graph["edges"]:
        fan_out[e["from"]] = fan_out.get(e["from"], 0) + e["refs"]
        fan_in[e["to"]] = fan_in.get(e["to"], 0) + e["refs"]

    def nid(m: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]", "_", m)

    lines = [
        "# Code graph", "",
        "Generated by `.claude/scripts/code-graph.py`. Do not edit by",
        "hand - regenerate with `/code-graph`. Import edges are best-effort static extraction:",
        "a missing edge is absence of evidence, not evidence of isolation.", "",
        "```mermaid", "flowchart LR",
    ]
    for m in graph["modules"]:
        lines.append(f'  {nid(m)}["{m}"]')
    for e in graph["edges"]:
        lines.append(f'  {nid(e["from"])} -->|{e["refs"]}| {nid(e["to"])}')
    lines += ["```", "", "| Module | Files | Fan-out | Fan-in | Owner |", "|---|---|---|---|---|"]
    for m, info in graph["modules"].items():
        lines.append(f"| `{m}` | {len(info['files'])} | {fan_out.get(m, 0)} | "
                     f"{fan_in.get(m, 0)} | {info['owner']} |")
    lines += [
        "",
        "High fan-in means many modules depend on it: a change there needs the widest review.",
        "A cross-module edge that surprises you is either a missing interface or a boundary",
        "violation - check `.claude/rules/ddd.md` if the DDD discipline is active.", "",
    ]
    ctx = root / "docs" / "context"
    ctx.mkdir(parents=True, exist_ok=True)
    (ctx / "code-graph.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the stale marker exists or the graph has never been built")
    args = ap.parse_args()
    root = args.target.resolve()

    if args.check:
        j = root / ".claude" / "state" / "code-graph.json"
        stale = root / ".claude" / "state" / "code-graph.stale"
        if not j.exists():
            print("code-graph: never built. Run /code-graph.")
            return 1
        if stale.exists():
            n = len(stale.read_text(encoding="utf-8", errors="replace").splitlines())
            print(f"code-graph: STALE - {n} source edit(s) since the last build. Run /code-graph.")
            return 1
        print("code-graph: up to date.")
        return 0

    graph = build(root)
    write_outputs(root, graph)
    print(f"code-graph: {len(graph['modules'])} modules, {len(graph['edges'])} edges "
          f"-> .claude/state/code-graph.json + docs/context/code-graph.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

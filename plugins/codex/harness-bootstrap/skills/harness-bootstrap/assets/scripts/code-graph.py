#!/usr/bin/env python3
"""Build the repo's module-boundary map and flag a NEW cross-module import edge.

The question this answers is the one the dev-agent brief asks before a change: "does this import
cross a module line that nobody agreed to?". It does not draw a picture. Stdlib only.

Outputs, from the repo root:
  docs/context/code-graph.md      COMMITTED. One row per module: owner, the modules it depends
                                  on, the modules that depend on it. This list IS the set of
                                  allowed cross-module edges - a new edge shows up as a diff line
                                  in review, and --check / --file compare the code against it.
  .claude/state/code-graph.json   machine state (gitignored): modules -> files + owner, edges with
                                  reference counts. Read by guard-agent-scope, /new-task and the
                                  harness-graph scanner; the shape is a contract, keep it.

Edges come from static import extraction that RESOLVES each import to a repo path: relative
specifiers by path, workspace packages by their manifest name (package.json, go.mod, Cargo.toml),
Python modules by the file that exists. Nothing is matched by bare file name - that is what made
the previous extractor report an edge between every pair of modules in a monorepo full of
index.ts files. What still escapes it: imports built at runtime, path aliases other than `@/` and
`~/`, C# `using` (a namespace is not a path). A missing edge is absence of evidence.

Usage:
  python .claude/scripts/code-graph.py                 # rebuild both outputs
  python .claude/scripts/code-graph.py --check         # exit 1 if the code has an edge the map lacks
  python .claude/scripts/code-graph.py --file PATH     # new edges introduced by one file
  python .claude/scripts/code-graph.py --file PATH --hook   # same, as PostToolUse JSON (graph-stale)
  python .claude/scripts/code-graph.py --self-test     # prove the detector can fire
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import posixpath
import re
import sys

SKIP_DIRS = {".git", "node_modules", "dist", "build", "vendor", "target", ".venv", "venv",
             "__pycache__", ".claude", ".cursor", ".codex", "coverage", ".next", "out"}
JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
SOURCE_EXTS = set(JS_EXTS) | {".py", ".go", ".java", ".cs", ".rb", ".php", ".rs"}
MAP_MD = "docs/context/code-graph.md"
STATE_JSON = ".claude/state/code-graph.json"
FLAGGED = ".claude/state/code-graph.flagged"

JS_RES = [re.compile(r"""\bfrom\s*['"]([^'"\n]+)['"]"""),
          re.compile(r"""\bimport\s*['"]([^'"\n]+)['"]"""),
          re.compile(r"""\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""),
          re.compile(r"""\brequire\s*\(\s*['"]([^'"\n]+)['"]\s*\)""")]
PY_FROM = re.compile(r"^[ \t]*from[ \t]+(\.*[\w\.]*)[ \t]+import[ \t]+\(?([\w\., \t]+)", re.M)
PY_IMPORT = re.compile(r"^[ \t]*import[ \t]+([\w\.]+(?:[ \t]*,[ \t]*[\w\.]+)*)", re.M)
GO_BLOCK = re.compile(r"^import\s*\(([^)]*)\)", re.M)
GO_ONE = re.compile(r'^import\s+(?:[\w\.]+\s+)?"([^"]+)"', re.M)
GO_STR = re.compile(r'"([^"]+)"')
RS_USE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:use|extern\s+crate)\s+([\w]+)", re.M)
JAVA_IMPORT = re.compile(r"^import\s+(static\s+)?([\w\.]+)\s*;", re.M)
PHP_USE = re.compile(r"^use\s+([\w\\]+)", re.M)
RB_REQ = re.compile(r"""^\s*require(_relative)?\s*\(?\s*['"]([^'"]+)['"]""", re.M)


def module_of(rel: str) -> str:
    """Module = the first meaningful path segment. src/auth/x.py -> src/auth; scripts/x.py -> scripts."""
    parts = rel.split("/")
    if parts[0] in ("src", "app", "lib", "pkg", "packages", "apps") and len(parts) > 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0] if len(parts) > 1 else "(root)"


class Repo:
    """One walk of the tree: source files, their directories, and workspace package names."""

    def __init__(self, root: pathlib.Path):
        self.root = root
        self.files: list[str] = []
        self.dirs: set[str] = {""}
        self.manifest_dirs: set[str] = set()
        self.packages: dict[str, str] = {}      # import name -> repo-relative dir
        self.go_mods: dict[str, str] = {}       # go module path -> repo-relative dir
        for cur, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            rel_dir = pathlib.Path(cur).relative_to(root).as_posix()
            rel_dir = "" if rel_dir == "." else rel_dir
            self.dirs.add(rel_dir)
            for name in sorted(filenames):
                rel = f"{rel_dir}/{name}" if rel_dir else name
                if pathlib.PurePosixPath(name).suffix in SOURCE_EXTS:
                    self.files.append(rel)
                if name in ("package.json", "tsconfig.json", "go.mod", "Cargo.toml"):
                    self.manifest_dirs.add(rel_dir)
                    self._read_manifest(pathlib.Path(cur) / name, rel_dir)
        self.file_set = set(self.files)
        self._suffix: dict[str, str] | None = None

    def _read_manifest(self, path: pathlib.Path, rel_dir: str) -> None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        if path.name == "package.json":
            try:
                name = json.loads(text).get("name")
            except (json.JSONDecodeError, AttributeError):
                name = None
            if isinstance(name, str) and name:
                self.packages[name] = rel_dir
        elif path.name == "go.mod":
            m = re.search(r"^module\s+(\S+)", text, re.M)
            if m:
                self.go_mods[m.group(1)] = rel_dir
        elif path.name == "Cargo.toml":
            m = re.search(r'^\[package\][^\[]*?^name\s*=\s*"([^"]+)"', text, re.M | re.S)
            if m:
                self.packages[m.group(1).replace("-", "_")] = rel_dir

    def by_suffix(self, suffix: str) -> str | None:
        if self._suffix is None:
            self._suffix = {}
            for f in self.files:
                parts = f.split("/")
                for i in range(len(parts)):
                    self._suffix.setdefault("/".join(parts[i:]), f)
        return self._suffix.get(suffix)

    def module_of_dir(self, rel_dir: str) -> str:
        return module_of(f"{rel_dir}/_" if rel_dir else "_")

    def js_target(self, base: str) -> str | None:
        """A resolved JS path -> the repo path it names (file, index file, or the bare path)."""
        if base.startswith(".."):
            return None
        for cand in [base] + [base + e for e in JS_EXTS] + [f"{base}/index{e}" for e in JS_EXTS]:
            if cand in self.file_set:
                return cand
        return f"{base}/_" if base in self.dirs else base

    def pkg_root(self, rel: str) -> str:
        d = posixpath.dirname(rel)
        while True:
            if d in self.manifest_dirs or not d:
                return d
            d = posixpath.dirname(d)

    def py_target(self, dotted: list[str], bases: list[str]) -> str | None:
        for base in bases:
            for k in range(len(dotted), 0, -1):
                p = posixpath.join(base, *dotted[:k]) if base else "/".join(dotted[:k])
                if p + ".py" in self.file_set:
                    return p + ".py"
                if p in self.dirs:
                    return p + "/__init__.py"
        return None


def targets(repo: Repo, rel: str) -> list[tuple[str, str]]:
    """Every intra-repo path the file at `rel` imports, as (target path, import text)."""
    try:
        text = (repo.root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    ext = posixpath.splitext(rel)[1]
    here = posixpath.dirname(rel)
    out: list[tuple[str, str]] = []

    def add(t: str | None, spec: str) -> None:
        if t:
            out.append((t, spec))

    if ext in JS_EXTS:
        for rx in JS_RES:
            for spec in rx.findall(text):
                if spec.startswith("."):
                    add(repo.js_target(posixpath.normpath(posixpath.join(here, spec))), spec)
                elif spec.startswith(("@/", "~/")):
                    root = repo.pkg_root(rel)
                    src = posixpath.join(root, "src") if root else "src"
                    base = src if src in repo.dirs else root
                    add(repo.js_target(posixpath.normpath(posixpath.join(base, spec[2:]))), spec)
                else:
                    parts = spec.split("/")
                    name = "/".join(parts[:2]) if spec.startswith("@") else parts[0]
                    if name in repo.packages:
                        add(f"{repo.packages[name]}/_" if repo.packages[name] else "_", spec)
    elif ext == ".py":
        for mod, names in PY_FROM.findall(text):
            dots = len(mod) - len(mod.lstrip("."))
            dotted = [p for p in mod.lstrip(".").split(".") if p]
            if dots:
                base = here
                for _ in range(dots - 1):
                    base = posixpath.dirname(base)
                subs = [n.strip().split(" ")[0] for n in names.split(",") if n.strip()]
                for n in subs or [""]:
                    add(repo.py_target(dotted + ([n] if n else []), [base]) or
                        repo.py_target(dotted, [base]), mod)
            else:
                add(repo.py_target(dotted, [here, "", "src"]), mod)
        for group in PY_IMPORT.findall(text):
            for mod in group.split(","):
                mod = mod.strip()
                add(repo.py_target(mod.split("."), [here, "", "src"]), mod)
    elif ext == ".go":
        specs = GO_ONE.findall(text)
        for block in GO_BLOCK.findall(text):
            specs += GO_STR.findall(block)
        for spec in specs:
            for mod_path, d in repo.go_mods.items():
                if spec == mod_path or spec.startswith(mod_path + "/"):
                    rest = spec[len(mod_path):].lstrip("/")
                    add(posixpath.join(d, rest, "_") if d or rest else "_", spec)
    elif ext == ".rs":
        for name in RS_USE.findall(text):
            if name not in ("crate", "self", "super", "std", "core", "alloc") and name in repo.packages:
                add(f"{repo.packages[name]}/_", name)
    elif ext == ".java":
        for static, dotted in JAVA_IMPORT.findall(text):
            parts = dotted.split(".")
            if static:
                parts = parts[:-1]
            add(repo.by_suffix("/".join(parts) + ".java"), dotted)
    elif ext == ".php":
        for ns in PHP_USE.findall(text):
            add(repo.by_suffix(ns.replace("\\", "/") + ".php"), ns)
    elif ext == ".rb":
        for rel_flag, spec in RB_REQ.findall(text):
            spec = spec if spec.endswith(".rb") else spec + ".rb"
            if rel_flag:
                t = posixpath.normpath(posixpath.join(here, spec))
                add(t if t in repo.file_set else None, spec)
            else:
                add(repo.by_suffix("lib/" + spec), spec)
    return out


def file_edges(repo: Repo, rel: str) -> dict[tuple[str, str], str]:
    """Cross-module edges one file creates -> the import text that created it."""
    src = module_of(rel)
    found: dict[tuple[str, str], str] = {}
    for tgt, spec in targets(repo, rel):
        dst = module_of(tgt)
        if dst != src:
            found.setdefault((src, dst), spec)
    return found


def owners(root: pathlib.Path) -> dict[str, str]:
    """Best-effort: match 'Owns <paths>' in .claude/agents/*.md descriptions to module prefixes."""
    out: dict[str, str] = {}
    agents = root / ".claude" / "agents"
    for a in sorted(agents.glob("*.md")) if agents.exists() else []:
        head = a.read_text(encoding="utf-8", errors="replace")[:600]
        m = re.search(r"Owns\s+([^\.\n]+)", head)
        if m:
            for chunk in re.split(r"[,;]", m.group(1)):
                out[chunk.strip().rstrip("/*").rstrip("/")] = a.stem
    return out


def build(root: pathlib.Path, repo: Repo | None = None) -> dict:
    repo = repo or Repo(root)
    mods: dict[str, list[str]] = {}
    edges: dict[tuple[str, str], int] = {}
    for rel in repo.files:
        mods.setdefault(module_of(rel), []).append(rel)
        src = module_of(rel)
        for tgt, _spec in targets(repo, rel):
            dst = module_of(tgt)
            if dst != src:
                edges[(src, dst)] = edges.get((src, dst), 0) + 1
    own = owners(root)

    def owner_of(mod: str) -> str:
        for prefix, agent in own.items():
            if mod == prefix or mod.startswith(prefix.rstrip("/") + "/") or prefix.endswith(mod):
                return agent
        return "-"

    return {
        # No generated_at here: generated files carry no timestamp (prompt-cache prefix content,
        # and a timestamp turns every rebuild into a diff).
        "modules": {m: {"files": fs, "owner": owner_of(m)} for m, fs in sorted(mods.items())},
        "edges": [{"from": a, "to": b, "refs": n} for (a, b), n in sorted(edges.items())],
    }


def render_md(graph: dict) -> str:
    deps: dict[str, list[str]] = {m: [] for m in graph["modules"]}
    used: dict[str, list[str]] = {m: [] for m in graph["modules"]}
    for e in graph["edges"]:
        deps.setdefault(e["from"], []).append(e["to"])
        used.setdefault(e["to"], []).append(e["from"])

    def cell(xs: list[str]) -> str:
        return ", ".join(f"`{x}`" for x in sorted(xs)) or "-"

    lines = [
        "# Code graph - module boundaries", "",
        "Generated by `.claude/scripts/code-graph.py`; regenerate with `/code-graph`, never by hand.",
        "Each row lists the cross-module imports the code has today. Treat that list as the ALLOWED",
        "set: `code-graph.py --check` fails when the code imports across a module line not listed",
        "here, and the `graph-stale` hook names such an edge on the edit that adds it. A new row",
        "entry in a diff of this file is an interface decision for review, not noise.", "",
        "| Module | Owner | Depends on | Used by |", "|---|---|---|---|",
    ]
    for m, info in graph["modules"].items():
        lines.append(f"| `{m}` | {info['owner']} | {cell(deps.get(m, []))} | {cell(used.get(m, []))} |")
    return "\n".join(lines) + "\n"


ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|[^|]*\|([^|]*)\|[^|]*\|\s*$")


def baseline(root: pathlib.Path) -> set[tuple[str, str]] | None:
    """The allowed edges: the committed map first, the machine JSON as fallback."""
    md = root / MAP_MD
    if md.is_file():
        out: set[tuple[str, str]] = set()
        for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
            m = ROW.match(line)
            if m:
                out.update((m.group(1), d) for d in re.findall(r"`([^`]+)`", m.group(2)))
        return out
    js = root / STATE_JSON
    if js.is_file():
        try:
            g = json.loads(js.read_text(encoding="utf-8"))
            return {(e["from"], e["to"]) for e in g.get("edges", [])
                    if isinstance(e, dict) and "from" in e and "to" in e}
        except (json.JSONDecodeError, OSError, AttributeError, TypeError):
            return None
    return None


def write_outputs(root: pathlib.Path, graph: dict) -> None:
    state = root / ".claude" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (root / STATE_JSON).write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    # A rebuild accepts whatever the code does now; the review of that is the diff of the map.
    (root / FLAGGED).unlink(missing_ok=True)
    (state / "code-graph.stale").unlink(missing_ok=True)   # pre-v1.20 staleness log
    md = root / MAP_MD
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(render_md(graph), encoding="utf-8", newline="\n")


def new_edges(root: pathlib.Path, repo: Repo, allowed: set[tuple[str, str]]) -> dict:
    """Every edge in the code that the allowed set lacks -> (example file, import text)."""
    found: dict[tuple[str, str], tuple[str, str]] = {}
    for rel in repo.files:
        for edge, spec in file_edges(repo, rel).items():
            if edge not in allowed:
                found.setdefault(edge, (rel, spec))
    return found


def check_file(root: pathlib.Path, path: str, hook: bool) -> int:
    """New edges from ONE file, each reported once until the next rebuild. Never fails."""
    allowed = baseline(root)
    if allowed is None:
        return 0
    p = pathlib.Path(path)
    p = p if p.is_absolute() else root / p
    try:
        rel = p.resolve().relative_to(root).as_posix()
    except ValueError:
        return 0
    if pathlib.PurePosixPath(rel).suffix not in SOURCE_EXTS or \
            set(rel.split("/")[:-1]) & SKIP_DIRS:
        return 0
    repo = Repo(root)
    if rel not in repo.file_set:
        repo.files.append(rel)
        repo.file_set.add(rel)
    fresh = {e: s for e, s in file_edges(repo, rel).items() if e not in allowed}
    flagged_path = root / FLAGGED
    try:
        seen = set(flagged_path.read_text(encoding="utf-8").splitlines())
    except OSError:
        seen = set()
    report = {e: s for e, s in fresh.items() if f"{e[0]} -> {e[1]}" not in seen}
    if not report:
        return 0
    try:
        flagged_path.parent.mkdir(parents=True, exist_ok=True)
        with flagged_path.open("a", encoding="utf-8") as fh:
            fh.writelines(f"{a} -> {b}\n" for a, b in sorted(report))
    except OSError:
        pass
    named = "; ".join(f"`{a}` -> `{b}` (import '{s}')" for (a, b), s in sorted(report.items()))
    msg = (f"{rel} adds a cross-module import the boundary map ({MAP_MD}) does not list: {named}. "
           "A new module edge is an interface decision, not a convenience. If it is intended, say "
           "so in your report so review can accept it (/code-graph records it); if not, reach the "
           "module through its published interface instead.")
    if hook:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": msg}}))
    else:
        print(msg)
    return 0


def self_test() -> list[str]:
    """Build a fixture monorepo and prove each detector fires. Returns the dead ones."""
    import contextlib
    import io
    import tempfile
    dead: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)

        def w(rel: str, text: str) -> None:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")

        w("apps/web/package.json", '{"name": "@x/web"}')
        w("apps/web/src/index.ts", "import { ui } from '@x/ui';\nimport { h } from './helpers';\n")
        w("apps/web/src/helpers.ts", "export const h = 1;\n")
        w("packages/ui/package.json", '{"name": "@x/ui"}')
        w("packages/ui/src/index.ts", "import { t } from './tokens';\nexport const ui = t;\n")
        w("packages/ui/src/tokens.ts", "export const t = 1;\n")
        w("packages/core/package.json", '{"name": "@x/core"}')
        w("packages/core/src/index.ts", "export const core = 1;\n")
        w("packages/core/src/theme.ts", "import { t } from '../../ui/src/tokens';\n")
        w("src/billing/invoice.py", "from src.auth import session\nimport os\nfrom . import tax\n")
        w("src/billing/tax.py", "RATE = 1\n")
        w("src/auth/session.py", "import json\n")
        g = build(root)
        got = {(e["from"], e["to"]) for e in g["edges"]}
        want = {("apps/web", "packages/ui"), ("packages/core", "packages/ui"),
                ("src/billing", "src/auth")}
        if not want <= got:
            dead.append(f"resolver: expected edges {sorted(want - got)} missing")
        # Every package has an index.ts: a bare-file-name matcher links them all to each other.
        if got - want:
            dead.append(f"resolver: false edges {sorted(got - want)} (bare-name matching?)")
        write_outputs(root, g)
        if baseline(root) != got:
            dead.append("baseline: the committed map does not round-trip its own edges")
        w("packages/ui/src/bad.ts", "import { core } from '@x/core';\n")
        fresh = new_edges(root, Repo(root), baseline(root) or set())
        if ("packages/ui", "packages/core") not in fresh:
            dead.append("--check: a new cross-module edge was not reported")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            check_file(root, "packages/ui/src/bad.ts", hook=True)
        if "packages/core" not in buf.getvalue():
            dead.append("--file: the hook path did not name the new edge")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            check_file(root, "packages/ui/src/bad.ts", hook=True)
        if buf.getvalue():
            dead.append("--file: a second edit of the same edge repeated the reminder")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            check_file(root, "apps/web/src/index.ts", hook=True)
        if buf.getvalue():
            dead.append("--file: an already-allowed edge was reported as new")
    return dead


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the code imports across a module line the map does not list")
    ap.add_argument("--file", help="report new edges introduced by this one file (never fails)")
    ap.add_argument("--hook", action="store_true", help="with --file: emit PostToolUse JSON")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    root = args.target.resolve()

    if args.self_test:
        dead = self_test()
        for d in dead:
            print(f"code-graph self-test: DEAD - {d}")
        print("code-graph self-test: " + ("FAILED" if dead else "ok"))
        return 1 if dead else 0

    if args.file:
        try:
            return check_file(root, args.file, args.hook)
        except Exception:   # a hook helper must never fail the edit it reports on
            return 0

    if args.check:
        allowed = baseline(root)
        if allowed is None:
            print(f"code-graph: never built ({MAP_MD} missing). Run /code-graph.")
            return 1
        fresh = new_edges(root, Repo(root), allowed)
        for (a, b), (rel, spec) in sorted(fresh.items()):
            print(f"code-graph: NEW edge {a} -> {b}  ({rel}: '{spec}')")
        if fresh:
            print(f"code-graph: {len(fresh)} cross-module edge(s) not in {MAP_MD}. Accept with "
                  "/code-graph after review, or remove the import.")
            return 1
        print("code-graph: every cross-module import is in the map.")
        return 0

    graph = build(root)
    write_outputs(root, graph)
    print(f"code-graph: {len(graph['modules'])} modules, {len(graph['edges'])} edges "
          f"-> {MAP_MD} + {STATE_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

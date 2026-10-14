---
description: Build or refresh the module-boundary map - which modules may import which - and check the code against it. A new cross-module import is an interface decision; this is where it gets accepted.
allowed-tools: Read, Grep, Glob, Bash(python:*), Bash(python3:*), Bash(git diff:*), Bash(git status)
---

Maintain the repo's module-boundary map. It answers one question deterministically: does the code
import across a module line that nobody agreed to?

What exists:

- `docs/context/code-graph.md` - COMMITTED. One row per module: owner, the modules it depends on,
  the modules that depend on it. That list is the set of ALLOWED cross-module edges.
- `.claude/state/code-graph.json` - machine state (gitignored): modules, files per module, edges
  with reference counts, module owner. `guard-agent-scope`, `/new-task` and the harness graph
  read it.

What keeps it honest, without anyone reading it:

- The `graph-stale` hook runs `code-graph.py --file` on every source edit and names, once, any
  cross-module import that the map does not list - on the edit that adds it.
- `python .claude/scripts/code-graph.py --check` exits 1 when the code has an edge the map lacks.
  Run it in review or CI.

Procedure:

1. Check first: `python .claude/scripts/code-graph.py --check`. Clean and the map exists: say so,
   stop.
2. Each NEW edge it lists is a decision, not a refresh. Find the import it names, then either
   remove it (reach the module through its published interface) or accept it. Accepting is
   rebuilding: `python .claude/scripts/code-graph.py`. Then refresh the wiring graph:
   `python .claude/scripts/harness-graph.py --html` (module owners feed into it).
3. Report what the rebuild changed (`git diff docs/context/code-graph.md`): every added module or
   edge, by name. That diff is what review approves.

How agents use it:

- The **orchestrator** reads the target module's row before dispatch: its "Used by" list is the
  blast radius the brief names and the review includes.
- A **dev agent** does not need to read it: the hook speaks up when an edit crosses a line the map
  does not list, and the agent then stops and reports instead of shipping the edge.
- `/board-audit` treats a failing `--check` as a finding.

Limits, stated honestly: edges are static imports resolved to repo paths - relative paths,
workspace package names (`package.json`, `go.mod`, `Cargo.toml`), Python modules that exist on
disk, and the `@/` and `~/` aliases. Imports assembled at runtime, other path aliases and C#
`using` are not seen. A missing edge is absence of evidence, not evidence of isolation; for "who
uses this symbol", grep is still the tool.

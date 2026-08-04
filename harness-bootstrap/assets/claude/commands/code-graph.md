---
description: Build or refresh the code knowledge graph - modules, files, and import edges - that agents consult before any cross-module change. Also reports staleness.
allowed-tools: Read, Grep, Glob, Bash(python:*), Bash(python3:*), Bash(git diff:*), Bash(git status)
---

Maintain the repo's code knowledge graph. The graph is how an agent answers "what depends on the
thing I am about to change" without reading the whole tree.

What exists:

- `.claude/state/code-graph.json` - machine-readable: modules, files per module, import edges with
  reference counts, module owner (matched from the roster's scopes).
- `docs/context/code-graph.md` - agent-readable: a mermaid module graph plus a fan-in/fan-out
  table. This is the file to read before dispatching or accepting a cross-module task.
- `.claude/state/code-graph.stale` - the invalidation log. The `graph-stale` hook appends every
  source-file edit here, so a non-empty file means the graph lags the code.

Procedure:

1. Check first: `python .claude/scripts/code-graph.py --check`. Up to date: say so, stop.
2. Rebuild: `python .claude/scripts/code-graph.py`. This rewrites both outputs and clears the
   stale log. Show the module/edge counts from its output.
3. Read the regenerated `docs/context/code-graph.md` and report anything structural that CHANGED
   since the last build (`git diff docs/context/code-graph.md`): a new cross-module edge, a module
   whose fan-in jumped, a module that appeared or vanished. A new surprise edge is either a missing
   interface or a boundary violation - name it, do not shrug at it.

How agents use it (this is the point of the graph):

- The **orchestrator** checks the target module's fan-in before dispatch: high fan-in means the
  task brief must name the dependents, and review must include them.
- A **dev agent** consults the graph before accepting a change that touches an edge, and refuses
  cross-module edits as ever - the graph shows why the refusal matters.
- `/board-audit` treats a stale graph as a finding.

Limits, stated honestly: edges come from static regex import extraction (stdlib only, no install).
A richer index - a GitNexus or codegraph MCP server, an LSP - can replace the extraction, but keep
writing the same two output files: the file contract, not the extractor, is what agents depend on.

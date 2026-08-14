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
2. Rebuild with the recorded engine (builtin: `python .claude/scripts/code-graph.py`; external:
   the MCP tool, writing the same files). This rewrites both outputs and clears the stale log.
   Show the module/edge counts. Then refresh the canonical wiring graph and the HTML exports:
   `python .claude/scripts/harness-graph.py` (module owners feed into it), then
   `python .claude/scripts/graph-html.py`.
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

Two graphs, two purposes: this command maps DEPENDENCY (what breaks if I change this module);
`/docs-graph` maps TRACEABILITY (which documents talk about the same requirement). Run both;
`graph-html.py` exports both as self-contained interactive HTML
(`docs/context/harness-graph.html` + `docs/context/specs-graph.html`). The harness page renders
from `.claude/state/harness-graph.json`, the canonical machine-readable wiring file written by
`harness-graph.py` - the `graph-stale` hook regenerates it automatically whenever a harness file
(agent, rule, command, hook, settings) is edited, so it is normally already fresh.

Engine choice - ask the user once and record it in `docs/context/tool-changelog.md`:

- **builtin** (default): the stdlib regex extractor in `.claude/scripts/code-graph.py`. Zero
  install, runs anywhere the harness runs, best-effort static edges.
- **GitNexus / codegraph**: if a GitNexus or codegraph MCP server (or comparable code-index tool)
  is available in this session, it may replace the extraction - richer call-level edges, real
  symbol resolution. The contract does not change: whatever engine runs, it must write the same
  `.claude/state/code-graph.json` shape and `docs/context/code-graph.md`, because the files, not
  the extractor, are what agents and hooks depend on. If the tool is unavailable mid-project, the
  builtin engine takes back over on the next `/code-graph` run - degraded edges, same files.

Limits, stated honestly: builtin edges are static regex extraction - a missing edge is absence of
evidence, not evidence of isolation. An external engine narrows that gap; it does not remove it.

# harness-view

A standalone, deterministic analyzer for a repo that ran the `harness-bootstrap`
skill. It reads `.claude/` (agents, rules, commands, hooks, settings), the task
board and the code graph, and shows how everything is wired together. No AI
involved - it only reads files and reports relationships.

The skill's own HTML output (`docs/context/harness-graph.html`) needs nothing
but Python and a browser; this tool is the power version: a native binary with
a live-refreshing UI, file watching, and safe runtime toggles.

## Install

```
cargo install --path tools/harness-view
```

Prebuilt binaries, when attached to a GitHub Release, are optional - the source
is the contract.

## Commands

```
harness-view scan  [path] [-o out.json]   # write .claude/state/harness-graph.json
harness-view serve [path] [--port 7420]   # local web UI at http://127.0.0.1:7420/
harness-view watch [path]                 # rebuild the graph on .claude/ or docs/ changes
```

- `scan` emits the graph described in [SCHEMA.md](SCHEMA.md) (schema version 1,
  shared with the skill's Python scanner). Output is byte-stable: sorted nodes,
  sorted edges, sorted keys, no timestamps.
- `serve` renders two views of the same graph: **Flow** (layered left to right:
  rules -> hooks and settings -> agents -> merge-request gate -> human ->
  commands, with edge-type labels) and **Graph** (force-directed). The legend
  toggles node types; modules, tasks and scripts are hidden by default. Every
  request to `/graph.json` re-scans, so the page is always current; an optional
  10 second auto-refresh keeps it live.
- `watch` uses OS file notifications and rewrites
  `.claude/state/harness-graph.json` on every change burst (500 ms debounce).
  Events under `.claude/state/` are ignored so the rebuild never re-triggers
  itself.

## Runtime toggles

The details panel of `serve` can disable or enable rules, commands and hooks.
It uses the same contract as the harness's `/harness-toggle` command:

- rules and commands move between `.claude/<kind>/X.md` and
  `.claude/disabled/<kind>/X.md`;
- hooks also have their `settings.json` registration objects removed and stored
  verbatim (with position) in `.claude/disabled.json`, so enabling restores the
  registration exactly where it was;
- `.claude/disabled.json` is the committed record: atomic writes, sorted keys,
  no dates.

Safety model: **agents are never toggleable** (roster changes go through
`/harness-update`), and HARD-protected controls - the `protect-secrets` and
`guard-agent-spawn` hooks, the `security-privacy` and `agent-guardrails` rules,
and the `/review-changes` command - are refused here with HTTP 403. Disabling
one of those requires the `/harness-toggle` command, where the user must type
the confirmation phrase themselves.

## Development

```
cargo test          # scanner fixtures, determinism, toggle round trips
cargo build --release
```

Dependencies are deliberately small and auditable: `serde_json`, `tiny_http`,
`notify`.

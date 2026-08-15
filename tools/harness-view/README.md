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
  10 second auto-refresh keeps it live. Clicking a node traces its connected
  subgraph: the node, its neighbours, and the edges between any two of them are
  drawn with a marching dash while everything unrelated fades back. Hooks carry
  a `PRE`/`POST`/`STOP` badge for the event they fire on, blocking hooks in
  red; tasks carry their board status; a disabled item is dashed, red-bordered
  and struck through. A third **Master plan** tab appears only when the repo has
  `docs/tasks/master-plan.md`.
- The path box in the header re-points the viewer at any repo with a `.claude/`
  folder, so one running server can inspect several projects. Recent paths are
  remembered in the browser, never on disk.
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
`/harness-update`). HARD-protected controls - the `protect-secrets` and
`guard-agent-spawn` hooks, the `security-privacy` and `agent-guardrails` rules,
and the `/review-changes` command - are refused here with HTTP 403; disabling
one of those requires the `/harness-toggle` command, where the user must type
the confirmation phrase themselves. SOFT-protected controls - the
`guard-main-commit`, `check-commit-msg` and `protect-adr` hooks and the
`ai-governance` rule - refuse with HTTP 409 until the request carries
`confirm_soft: true`; the UI asks for that confirmation explicitly.

### The endpoint

`POST /toggle` with a JSON body:

```json
{"kind": "rule|command|hook", "name": "<bare name>", "enable": false,
 "reason": "optional", "confirm_soft": false}
```

The endpoint only accepts same-origin browser requests: a request with a
foreign `Origin` or a `Sec-Fetch-Site` other than `same-origin`/`none`, or
without `Content-Type: application/json`, is refused with 403. This stops a
page open in another tab from silently mutating `.claude/` while `serve` runs.

### Reading a file

`GET /file?root=<repo>&path=<repo-relative path>` backs the sidebar's Preview
and the Master plan tab. It is read-only and deliberately narrow:

- only `.claude/` and `docs/` are readable - nothing else in the repo is served
- both sides are canonicalized and the result must still sit inside the root,
  so `..`, an absolute path, and a symlink pointing out of the tree are all
  refused by the same check rather than by pattern-matching the string
- the body is capped at 256 KB and truncated with a visible marker
- it is always `text/plain` with `X-Content-Type-Options: nosniff`, never
  `text/html`, and the page renders it with `textContent`
- the same same-origin rules as `/toggle` apply

## Development

```
cargo test          # scanner fixtures, determinism, toggle round trips
cargo build --release
```

Dependencies are deliberately small and auditable: `serde_json`, `tiny_http`,
`notify`.

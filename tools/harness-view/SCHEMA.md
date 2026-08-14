# harness-graph.json - schema version 1

Written to `.claude/state/harness-graph.json` by both this tool (`harness-view
scan`) and the skill's Python scanner (`.claude/scripts/harness-graph.py`).
Byte-stable: sorted keys, nodes sorted by id, edges sorted by (from, to, type),
two-space indent, trailing newline, never a timestamp.

```json
{
  "version": 1,
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

## Nodes

`id` is `<prefix>:<name>`; prefixes per type: `agent:`, `rule:`, `cmd:`,
`hook:`, `script:`, `mod:`, `task:`, plus the singletons `settings`,
`gate:merge-request`, `human`.

| type | id example | fields |
|---|---|---|
| agent | `agent:code-reviewer` | `label`, `file`, `disabled`, `meta` (`model`, `effort`, `maxTurns`, `tools`) |
| rule | `rule:testing` | `file`, `disabled`, `meta` (`scoped`, `paths` when scoped) |
| command | `cmd:deploy` | `file`, `disabled` |
| hook | `hook:protect-secrets` | `label`, `file` (.sh flavor preferred), `disabled`, `meta` (`registered`, `event`, `matcher`, `blocking`) |
| settings | `settings` | `file` (present only when settings.json exists) |
| script | `script:code-graph` | `file` |
| module | `mod:src/app` | `meta` (`files`, `owner`) from code-graph.json |
| task | `task:TASK-042` | `file` (capped at 60 tasks) |
| gate | `gate:merge-request` | `synthetic: true` |
| human | `human` | `synthetic: true` |

Items found under `.claude/disabled/{rules,commands,hooks}/` still appear as
nodes, with `disabled: true` and `file` pointing at the quarantine path.

## Edges

`{"from": id, "to": id, "type": <enum>}`. The type enum is closed:

| type | meaning |
|---|---|
| `triggers` | settings.json registration fires the hook |
| `enforces` | the hook mechanically enforces the rule (static table) |
| `gates` | an unconditional (non-path-scoped) rule applies to the agent |
| `spawns` | the orchestrator dispatches the agent |
| `reviews` | a reviewer seat gates the merge request |
| `escalates` | the merge-request gate ends at the human |
| `invokes` | commands are human entry points |
| `runs` | the command executes the script |
| `owns` | the agent owns the module (code-graph owner) |
| `references` | module imports module; task mentions module |

## disabled.json (toggle record)

```json
{
  "version": 1,
  "disabled": [
    {"kind": "rule", "name": "performance", "from": ".claude/rules/performance.md",
     "reason": "noisy during prototype phase"},
    {"kind": "hook", "name": "specs-reminder", "from": ".claude/hooks/specs-reminder.sh",
     "reason": "...",
     "registration": [{"event": "PostToolUse", "matcher": "Edit|Write", "index": 0,
                       "hook": {"type": "command", "command": "bash .claude/hooks/specs-reminder.sh"}}]}
  ]
}
```

`registration[].index` records the matcher group's position inside the event
array so enabling restores `settings.json` byte-exactly. Entries are sorted by
`kind/name`. The file is committed; it must never contain a date.

## Versioning

`version` increments only on a breaking shape change. Consumers must reject a
larger major version rather than guess.

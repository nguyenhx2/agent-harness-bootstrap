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

**Every node carries `label` and `disabled`** (false when not applicable).
Label forms: commands are `/<name>`, the synthetic gate is `Merge request`,
the human node is `Human`, settings is `settings.json`, scripts are
`<name>.py`, modules are the module path, everything else the bare name.

| type | id example | additional fields |
|---|---|---|
| agent | `agent:code-reviewer` | `file`, `meta` (`model`, `effort`, `maxTurns`, `tools`) |
| rule | `rule:testing` | `file`, `meta` (`scoped`, `paths` when scoped; glob values unquoted) |
| command | `cmd:deploy` | `file` |
| hook | `hook:protect-secrets` | `file` (the .sh flavor when both exist, else the .ps1), `meta` (`registered`, `event`, `matcher`, `blocking`) |
| settings | `settings` | `file`; no meta (present only when settings.json exists) |
| script | `script:code-graph` | `file` (every `*.py` under `.claude/scripts/`) |
| module | `mod:src/app` | `meta` with BOTH `files` (count) and `owner` (agent name or `-`) |
| task | `task:TASK-042` | `file` (every `TASK-*.md` under `docs/tasks/**`) |
| gate | `gate:merge-request` | `synthetic: true` |
| human | `human` | `synthetic: true` |

Items found under `.claude/disabled/{rules,commands,hooks}/` still appear as
nodes, with `disabled: true` and `file` pointing at the quarantine path.

## Edges

`{"from": id, "to": id, "type": <enum>, "refs"?: int}`. `refs` appears only on
module-to-module `references` edges, carrying the import count from
code-graph.json. The type enum is closed:

| type | meaning |
|---|---|
| `triggers` | settings.json registration fires the hook |
| `enforces` | the hook mechanically enforces the rule (static table) |
| `gates` | an unconditional (non-path-scoped) rule applies to the agent |
| `spawns` | the orchestrator dispatches the agent |
| `reviews` | a reviewer seat gates the merge request |
| `escalates` | the merge-request gate ends at the human |
| `invokes` | commands are human entry points |
| `runs` | the command references the script; one edge per referenced `.claude/scripts/*.py`, so a command may run several |
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
     "registration": [{"event": "PostToolUse", "matcher": "Edit|Write",
                       "group_index": 0, "hook_index": 0,
                       "hook": {"command": "bash .claude/hooks/specs-reminder.sh", "type": "command"}}]}
  ]
}
```

`registration[].group_index` records the matcher group's position inside the
event array and `hook_index` the hook object's position inside the group, so
enabling restores `settings.json` byte-exactly (the same shape
harness-toggle.py writes - the two tools share one record). Entries are sorted
by `kind/name`. The file is committed; it must never contain a date. Note the
`hook` object is stored with sorted keys because the whole file is written
canonically; `settings.json` itself is always written with its key order
preserved.

## Versioning

`version` increments only on a breaking shape change. Consumers must reject a
larger major version rather than guess.

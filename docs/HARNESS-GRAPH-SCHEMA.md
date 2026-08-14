# harness-graph.json - schema contract (version 1)

`.claude/state/harness-graph.json` is the canonical, machine-readable description of a
harnessed repo's control plane: every agent, rule, command, hook, script, code module, and
active task, plus the typed relationships between them. It is written by
`.claude/scripts/harness-graph.py`, rendered by `graph-html.py`
(`docs/context/harness-graph.html`, Flow and Graph views), and consumed by external tools
such as the `harness-view` native viewer. Anything that reads this file must tolerate unknown
extra keys; anything that writes it must preserve the guarantees below.

## Guarantees

- **Deterministic**: nodes sorted by `id`, edges sorted by `(from, to, type)`, JSON keys
  sorted, 2-space indent, trailing newline, no timestamps. Two scans of the same tree are
  byte-identical.
- **Closed enums**: node `type` and edge `type` only ever use the values listed here.
  A `version` bump accompanies any addition.
- **Self-contained**: ids are stable strings derived from file stems, never array indexes.

## Top level

```json
{ "version": 1, "nodes": [ ... ], "edges": [ ... ] }
```

## Nodes

| Field | Type | Notes |
|---|---|---|
| `id` | string | `<prefix>:<name>` - prefixes: `agent:` `rule:` `cmd:` `hook:` `script:` `mod:` `task:` `gate:`; plus the bare ids `settings` and `human` |
| `type` | enum | `agent` `rule` `command` `hook` `settings` `script` `module` `task` `gate` `human` |
| `label` | string | ALWAYS present. Commands are `/<name>`; the synthetic nodes are `Merge request` and `Human`; settings is `settings.json`; scripts are `<name>.py`; modules are the module path; everything else the bare name |
| `file` | string? | repo-relative path, absent for synthetic and module nodes. When a hook has both flavors, `file` points at the `.sh` if present, else the `.ps1` (an active flavor beats a disabled one at equal extension) |
| `disabled` | bool | ALWAYS present; `false` when not applicable. True when the item sits under `.claude/disabled/` or is listed in `.claude/disabled.json` |
| `synthetic` | bool? | true only on `gate:merge-request` and `human` (Flow-view anchors, no file) |
| `meta` | object? | per-type extras, see below |

`meta` by type:

- `agent`: `model` (string, `inherit` when unset), `effort`?, `maxTurns`? (int), `tools`? (string list)
- `rule`: `scoped` (bool - has `paths:` frontmatter), `paths`? (first globs, max 8, values
  unquoted - surrounding single/double quotes from the frontmatter are stripped)
- `hook`: `registered` (bool - appears in settings.json hook arrays), `event`?, `matcher`?,
  `blocking`? (true when `event == "PreToolUse"`)
- `module`: `files` (int) AND `owner` (agent name from code-graph.json, `"-"` when unowned)
- `settings`: no meta - the settings node carries `id`/`type`/`label`/`file`/`disabled` only

Inventory rules:

- **Scripts**: EVERY `*.py` under `.claude/scripts/` is a node, referenced by a command or not.
  Nodes are strictly the on-disk inventory: a script referenced by a command but missing on
  disk gets NO node - the `runs` edge is kept dangling on purpose, and the HTML viewer renders
  the missing endpoint as a greyed "(missing)" stub so the broken reference is diagnosable.
- **Tasks**: EVERY `TASK-*.md` under `docs/tasks/**` is a node; `references` edges are added
  only where the task body names a module path.

## Edges

| Field | Type | Notes |
|---|---|---|
| `from`, `to` | string | node ids; every edge endpoint exists in `nodes` |
| `type` | enum | see table below |
| `refs` | int? | reference count, only on module-to-module edges |

| Edge type | Meaning | Typical direction |
|---|---|---|
| `gates` | an unconditional rule constrains an agent | rule -> agent |
| `triggers` | settings.json registration fires a hook | settings -> hook |
| `enforces` | a hook mechanically enforces a rule | hook -> rule |
| `reviews` | a review seat gates the merge request | agent -> gate:merge-request |
| `escalates` | the gate hands the decision to a person | gate:merge-request -> human |
| `invokes` | a human runs a slash command | human -> command |
| `runs` | a command executes a script - one edge per distinct `.claude/scripts/<name>.py` referenced in the command body | command -> script |
| `spawns` | the orchestrator can dispatch a seat | agent:orchestrator -> agent |
| `owns` | a dev agent owns a code module | agent -> module |
| `references` | module imports module, or a task names a module | module -> module, task -> module |

## Inputs the scanner merges

- `.claude/{agents,rules,commands}/**.md`, `.claude/hooks/*.{sh,ps1}`, `.claude/settings.json`
- `.claude/disabled/**` and `.claude/disabled.json` (runtime toggle state; absent = nothing disabled)
- `.claude/state/code-graph.json` (module nodes, owners, import edges) - optional
- `docs/tasks/**/TASK-*.md` (every task file becomes a node) - optional

## Freshness

The `graph-stale` PostToolUse hook regenerates this file (and the HTML) on every edit to a
harness file. Mutations that bypass Edit/Write hooks - scaffold re-runs, toggle scripts,
external tools - must re-run `python .claude/scripts/harness-graph.py --html` themselves.

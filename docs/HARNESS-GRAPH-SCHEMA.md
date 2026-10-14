# harness-graph.json - schema contract (version 1)

**English** · [日本語](HARNESS-GRAPH-SCHEMA.ja.md)

`.claude/state/harness-graph.json` is the canonical, machine-readable description of a
harnessed repo's control plane: every agent, rule, command, hook, script, code module, and
active task, plus the typed relationships between them. It is written by
`.claude/scripts/harness-graph.py` or, byte for byte the same, by `harness-view scan`
(`scripts/check_graph_parity.py` holds the two to that), rendered by `graph-html.py`
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
| `id` | string | `<prefix>:<name>` - prefixes: `agent:` `rule:` `cmd:` `hook:` `script:` `mod:` `task:` `gate:` `skill:` `instr:`; plus the bare ids `settings` and `human` |
| `type` | enum | `agent` `rule` `command` `hook` `settings` `script` `module` `task` `gate` `human` `skill` `instruction` |
| `label` | string | ALWAYS present. Commands are `/<name>`; the synthetic nodes are `Merge request` and `Human`; settings is `settings.json`; scripts are `<name>.py`; modules are the module path; everything else the bare name |
| `file` | string? | repo-relative path, absent for synthetic and module nodes. When a hook has both flavors, `file` points at the `.sh` if present, else the `.ps1` (an active flavor beats a disabled one at equal extension) |
| `disabled` | bool | ALWAYS present; `false` when not applicable. True when the item sits under `.claude/disabled/` or is listed in `.claude/disabled.json` |
| `synthetic` | bool? | true only on `gate:merge-request` and `human` (Flow-view anchors, no file) |
| `meta` | object? | per-type extras, see below |

`meta` by type:

- `agent`: `model`? (absent when unset; the runtime reads that as inherit), `effort`?,
  `maxTurns`? (int), `tools`? (string list, split on commas outside parentheses, so
  `Agent(a, b)` stays one entry), `description`? (frontmatter `description:`, trimmed, capped
  at 300 chars). Every other subagent frontmatter field is carried when set -
  `permissionMode`, `memory`, `isolation`, `color`, `background`, `omitClaudeMd`,
  `disallowedTools`, `skills`, `mcpServers`, `hooks`, `initialPrompt`, `cacheTtl`, `name` (only
  when it differs from the file name) - plus `spawns` (the names inside `Agent(...)`),
  `spawnAllowlist` (the lines of `.claude/hooks/spawn-allowlist`) and `tier`. The forms are in
  `tools/harness-view/SCHEMA.md` ("Agent meta"). A UTF-8 BOM before the opening `---` is ignored.
- `rule`: `scoped` (bool - has `paths:` frontmatter), `paths`? (first globs, max 8, values
  unquoted - surrounding single/double quotes from the frontmatter are stripped), `description`?
- `command`: `description`? only (same rule as the agent one)
- `hook`: `registered` (bool - registered by settings.json or by a seat's own frontmatter
  `hooks:`), `event`? and `matcher`? (the first registration, settings.json first), `events`?
  (every distinct `"<Event> <matcher>"`, when there is more than one), `scope`? (the seats that
  register it, when settings.json does not - it fires only while that seat runs),
  `blocking`? (true when any registration is on `PreToolUse` or `PermissionRequest`, the
  events that gate a tool call), `library`? (true when the hook is not
  registered but a registered hook sources it, like a shared `_lib.sh`; it is a helper, not a
  hook that was switched off)
- `task`: `title`? `status`? `fr`? `owner`? `deps`? `priority`? `phase`? - the board fields from
  the task frontmatter. A trailing YAML comment is stripped, so the template's
  `status: Done # Active | Blocked | Pending | Done` reads as `Done`. Tasks on an
  orchestrator-kit board also carry `mission`?, `attempts`?, `board` and `drift`? - see "Task
  board" in `tools/harness-view/SCHEMA.md`.
- `module`: `files` (int) AND `owner` (agent name from code-graph.json, `"-"` when unowned)
- `skill`: `description`? (frontmatter `description:`, same rule as the agent one), `own_agents`? (int) and `own_scripts`? (int) when the skill ships its own `agents/` or `scripts/` directory. Those files are internal to the skill and are deliberately NOT emitted as harness nodes: they are not roster seats.
- `instruction`: `tools` (the tools that read the file), `source` (where that is documented),
  `verified` (bool - whether it is sourced at all) and `note`?; `tiers`? (the "How much process a
  change gets" table, parsed out of whichever instruction file states it) and `edit`? (what the
  viewer may write) sit beside `meta`. The set is a closed, sourced allow-list: `AGENTS.md`,
  `CLAUDE.md`, `GEMINI.md`, `.cursor/rules/*.mdc`, `.kiro/steering/*.md` and the Antigravity rule
  folders. Every per-folder copy of `AGENTS.md` or `CLAUDE.md` below the root (a module's own
  `CLAUDE.md`) is a node too, as `instr:claude/<repo-relative path>`. Fields and evidence:
  "Instruction files" in `tools/harness-view/SCHEMA.md`.
- `settings`: `otherHooks`? only - the registrations that run no `.claude/hooks/` script (an
  inline command, a prompt or http hook), each as `"<Event> [<matcher>] -> <command>"`

Inventory rules:

- **Scripts**: EVERY `*.py`, `*.sh` and `*.ps1` under `.claude/scripts/` is a node, referenced
  or not. One node per name; when two flavors share a name the `.py` wins, then the `.sh`. The
  label is the file name.
  Nodes are strictly the on-disk inventory: a script referenced by a command but missing on
  disk gets NO node - the `runs` edge is kept dangling on purpose, and the HTML viewer renders
  the missing endpoint as a greyed "(missing)" stub so the broken reference is diagnosable.
- **Skills**: EVERY `.claude/skills/<slug>/SKILL.md` is a node. Only INSTALLED skills get an
  edge; a seat declaring a skill that is not installed is reported by `harness-view assess`
  (`skill-wire-missing`), which reads the seat files directly.
- **Tasks**: EVERY `TASK-*.md` under `docs/tasks/**`, and under the task board
  (`.agent-base/tasks/`, or `env.TASK_BOARD_DIR` in settings.json), is a node; a `TASKS.md`
  row with no file is a node without `file`; `references` edges are added
  only where the task body names a module path.

## Content references

Most edges are read out of the files themselves. Every agent, rule, command, hook, skill
(`SKILL.md`) and instruction file is scanned for references to the other harness items, and
each reference becomes an edge. There is no table of hook or rule names inside the scanner:
a hook enforces the rule its own text names, not the rule a list says it should.

A name counts only when it is written as a name on purpose:

| Form | Example | Resolves to |
|---|---|---|
| a harness path | `.claude/rules/layering.md`, `.claude/skills/docs-sync/SKILL.md`, `.claude/scripts/check-env.sh` | that rule, skill, script, agent, command or hook |
| a bare file name, as the whole word | `. "$(dirname "$0")/_lib.sh"` | a hook or script of that name |
| a slash form | `/review` | a command |
| a code or bold span, exact | `` `endpoint-scaffold` ``, `**docs-sync**` | an agent, skill, hook or rule |
| a bare hyphenated slug | `security-privacy-reviewer` | an agent, skill or hook |
| frontmatter `skills:` | `skills: [pdf, docx]` on an agent | each listed skill |

A single dictionary word in prose never counts. That rule is load-bearing: five agents in
one real harness contain the word "performance" ("performance budgets") while the skill of
that name is wired to no seat, so word matching would invent five wires. A path is a harness
path only when its directory sits right after `.claude/` or opens the word, so
`.cursor/rules/x.md` and a skill's private `scripts/` folder resolve to nothing. A bare name
resolves to one kind, agent before skill before hook (before rule, in a span); commands are
reached only by `/name` or a path, because a skill-backed command often shares its skill's
name. A reference resolves only to a node that exists, and a file never references itself.

The edge type is named by what the two ends are:

| From | To | Edge |
|---|---|---|
| hook | rule | `enforces` |
| hook | hook | `sources` |
| any | script | `runs` |
| hook | agent, skill, command | `refers` |
| instruction | agent | `briefs` |
| any | rule | `cites` |
| any | skill | `uses` |
| rule | agent | `refers` |
| command, agent, skill | agent | `delegates` |
| any | command | `invokes` |

## Edges

| Field | Type | Notes |
|---|---|---|
| `from`, `to` | string | node ids; every edge endpoint exists in `nodes` |
| `type` | enum | see table below |
| `refs` | int? | reference count, only on module-to-module edges |

| Edge type | Meaning | Typical direction |
|---|---|---|
| `gates` | an unconditional rule constrains an agent | rule -> agent |
| `triggers` | settings.json, or a seat's own frontmatter, registers a hook | settings -> hook, agent -> hook |
| `enforces` | a hook names the rule it enforces | hook -> rule |
| `reviews` | a review seat gates the merge request: the scaffolder's reviewer names, `checker`, `editor`, or a name ending `reviewer`, `-checker`, `auditor`, `critic` or `verifier` | agent -> gate:merge-request |
| `escalates` | the gate hands the decision to a person | gate:merge-request -> human |
| `invokes` | a human runs a slash command, or a file points at one | human -> command, any -> command |
| `runs` | a file executes a script; from a command, every `.claude/scripts/<name>.py` it references counts even when the file is missing | any -> script |
| `spawns` | a seat can start another: exactly the seats `Agent(a, b)` names, else every other seat for `orchestrator` or a bare `Agent`/`Task` grant | agent -> agent |
| `owns` | a dev agent owns a code module, or owns a task (its `owner:` frontmatter) | agent -> module, agent -> task |
| `references` | module imports module, or a task names a module | module -> module, task -> module |
| `uses` | a file names a skill it reaches for | agent, command, rule, skill, instruction -> skill |
| `cites` | a file points at a rule | any -> rule |
| `briefs` | an instruction file names a seat | instruction -> agent |
| `imports` | an instruction file `@`-imports another | instruction -> instruction |
| `routes` | a routing-tier row names the seat that runs it | instruction -> agent |
| `delegates` | a file hands work to a seat (a command starts it, an agent passes to it) | command, agent, skill -> agent |
| `sources` | a hook loads a shared helper | hook -> hook |
| `refers` | any other named reference | hook -> any, rule -> agent |

## Assessment

`harness-view assess --json` (and `GET /assess`) grades this graph and is a different document from
it: findings with rule ids, evidence (`file:line`), a fix, a worklist that orders the rules by value,
and a `since` block that diffs two assessments. Its shape is in "Assessment" in
`tools/harness-view/SCHEMA.md` and every rule in `tools/harness-view/RUBRIC.md`.

## Inputs the scanner merges

- `.claude/{agents,rules,commands}/**.md`, `.claude/hooks/*.{sh,ps1}`, `.claude/settings.json`
- the instruction files above, from the repo root and below
- `.claude/disabled/**` and `.claude/disabled.json` (runtime toggle state; absent = nothing disabled)
- `.claude/state/code-graph.json` (module nodes, owners, import edges) - optional
- `docs/tasks/**/TASK-*.md` (every task file becomes a node) - optional
- the task board: `<board>/{pending,active,completed,canceled}/TASK-*.md` and `<board>/TASKS.md` - optional
- `.claude/hooks/spawn-allowlist` (built-in agents a spawn guard admits) - optional

## Freshness

The `graph-stale` PostToolUse hook regenerates this file (and the HTML) on every edit to a
harness file. Mutations that bypass Edit/Write hooks - scaffold re-runs, toggle scripts,
external tools - must re-run `python .claude/scripts/harness-graph.py --html` themselves.

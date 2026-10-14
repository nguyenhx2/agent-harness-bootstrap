# harness-graph.json - schema version 1

**English** · [日本語](SCHEMA.ja.md)

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
`hook:`, `script:`, `mod:`, `task:`, `instr:`, plus the singletons `settings`,
`gate:merge-request`, `human`.

**Every node carries `label` and `disabled`** (false when not applicable).
Label forms: commands are `/<name>`, the synthetic gate is `Merge request`,
the human node is `Human`, settings is `settings.json`, scripts are
`<name>.py`, modules are the module path, everything else the bare name.

| type | id example | additional fields |
|---|---|---|
| agent | `agent:code-reviewer` | `file`, `meta` (`model`, `effort`, `maxTurns`, `tools`, `description`; see [Agent meta](#agent-meta) for the rest) |
| rule | `rule:testing` | `file`, `meta` (`scoped`, `paths` when scoped and unquoted, `description`) |
| command | `cmd:deploy` | `file` |
| hook | `hook:protect-secrets` | `file` (the .sh flavor when both exist, else the .ps1), `meta` (`registered`, `event`, `matcher`, `blocking`, `library` when unregistered and sourced by another hook; `events`, `scope` - see [Hook meta](#hook-meta)) |
| settings | `settings` | `file`, `edit`; `meta.otherHooks` only when a registration runs no `.claude/hooks/` script (present only when settings.json exists) |
| instruction | `instr:agents`, `instr:cursor-rules/testing` | `file`, `edit`, `meta` (`tools`, `source`, `verified`, `note`), `tiers` when the file carries a routing table |
| script | `script:code-graph` | `file` (every `*.py`, `*.sh`, `*.ps1` under `.claude/scripts/`; label is the file name) |
| module | `mod:src/app` | `meta` with BOTH `files` (count) and `owner` (agent name or `-`) |
| task | `task:TASK-042` | `file` (every `TASK-*.md` under `docs/tasks/**`, and under the [task board](#task-board)), `meta` (`title`, `status`, `fr`, `owner`, `deps`, `priority`, `phase` when the frontmatter carries them) |
| gate | `gate:merge-request` | `synthetic: true` |
| human | `human` | `synthetic: true` |

Items found under `.claude/disabled/{rules,commands,hooks}/` still appear as
nodes, with `disabled: true` and `file` pointing at the quarantine path.

### Agent meta

Beyond the five above, every field of Claude Code's subagent frontmatter
(code.claude.com/docs/en/sub-agents, "Supported frontmatter fields") is carried
when the file sets it, flattened so a viewer can print it without knowing it:

| key | form |
|---|---|
| `permissionMode`, `memory`, `isolation`, `color` | string |
| `background`, `omitClaudeMd` | bool (`true`/`false`), else the raw string |
| `disallowedTools`, `skills` | list |
| `mcpServers` | list of server names (a string item, or the key of an inline definition) |
| `hooks` | list of `"<Event> [<matcher>] -> <hook name or command>"`, one per registration |
| `initialPrompt` | string, capped at 300 characters |
| `cacheTtl` | `experimental.cacheTtl` |
| `name` | only when `name:` differs from the file name - Claude Code dispatches by `name:` |
| `spawns` | the names inside `Agent(a, b)` (or `Task(...)`) in `tools`, built-ins included |
| `spawnAllowlist` | the lines of `.claude/hooks/spawn-allowlist`, on the seat whose frontmatter hook reads that file (else on `orchestrator`) |

`tools` is split on commas outside parentheses, so `Agent(a, b)` stays one entry.
A UTF-8 BOM before the opening `---` is ignored.

### Hook meta

A hook is registered by settings.json or by a seat's own frontmatter `hooks:`.
`event` and `matcher` are the first registration (settings.json first);
`events` lists every distinct `"<Event> <matcher>"` when there is more than one.
`blocking` is true when any registration is on `PreToolUse` or
`PermissionRequest`, the events whose exit 2 stops a tool call. `scope` lists the
seats that register it when settings.json does not: such a hook fires only while
that seat runs.

### Task board

orchestrator-kit's board: `TASK_BOARD_DIR` from settings.json `env` when it is a
relative path inside the repo, else `.agent-base/tasks`, when the directory
exists. Task files sit in `pending/`, `active/`, `completed/` or `canceled/`, and
`TASKS.md` indexes them (`| ID | task | agent | state | deps | mission |`).

For board tasks, `status` falls back to the folder, `owner` to `agent:` and
`deps` to `depends_on:`; a `-` value is dropped; `mission`, `attempts` and
`board` (the board path) are added. `drift` lists every disagreement between the
folder, `status:` and the `TASKS.md` row - what `task.sh check` would fail on. A
`TASKS.md` row with no file becomes a task node with no `file` and a `drift`
entry saying so.

### Instruction files

The only nodes that live outside `.claude/`. They are the contract each AI
coding tool reads, so the set is a closed, sourced allow-list rather than a
scan of the repository root - `instruction::FILES` in
`tools/harness-view/src/instruction.rs` and `INSTRUCTION_FILES` in
`harness-graph.py`, which must stay equal (`scripts/check_graph_parity.py`).

| key | path | read by | evidence |
|---|---|---|---|
| `agents` | `AGENTS.md` | Claude Code, Codex, Cursor, Antigravity | `docs/tools/*.md` in this repo; antigravity.google/docs/cli/best-practices |
| `claude` | `CLAUDE.md` | Claude Code | `docs/tools/claude-code.md` |
| `gemini` | `GEMINI.md` | Antigravity | antigravity.google/docs/cli/best-practices |
| `cursor-rules` | `.cursor/rules/*.mdc` | Cursor | `harness-bootstrap/scripts/port.py`, `docs/tools/cursor.md` |
| `kiro-steering` | `.kiro/steering/*.md` | Kiro | kiro.dev/docs/steering |
| `antigravity-rules` | `.agents/rules/*.md` | Antigravity | antigravity.google/docs/rules-workflows |
| `antigravity-rules-legacy` | `.agent/rules/*.md` | Antigravity | same page, documented back-compat path |

Each node's `meta.source` carries that evidence and `meta.verified` says
whether it is sourced at all, so a reader can tell a documented fact from a
guess. Whether Kiro also reads `AGENTS.md` is **unverified** - no first-party
page states it - so the claim is not made; it is recorded in the `note` on the
`agents` entry instead. A global instruction file outside the repository
(`~/.gemini/GEMINI.md`, `~/.codex/AGENTS.md`) is not scannable and is not a node.

`tiers` is the "How much process a change gets" table (v1.18.0), parsed out of
whichever instruction file states it: an array of
`{"tier", "change", "who", "adds"}` in file order. The table is found by its
`Tier` / `Who runs it` header, or - when translated, as orchestrator-kit's
`| 区分 | 変更の内容 | 誰が行うか |` is - by two or more rows named `Direct`,
`Standard` or `Guarded`. Any agent the `who` column
names also gets `meta.tier` and a `routes` edge. The Direct and Standard rows
say "the owning agent" and name nobody, so they route to nobody.

### `edit`

`{"key": <table key>, "name": <bare leaf name or "">}`, present only on nodes
the viewer may write: the instruction files and `settings`. It is what
`POST /instruction` accepts - a key from the fixed table plus a bare name -
because an endpoint that took a path would need containment, and one that takes
neither has no traversal to contain.

## Edges

`{"from": id, "to": id, "type": <enum>, "refs"?: int}`. `refs` appears only on
module-to-module `references` edges, carrying the import count from
code-graph.json. The type enum is closed:

| type | meaning |
|---|---|
| `triggers` | settings.json registration fires the hook; from an agent, the seat's own frontmatter registers it |
| `enforces` | the hook's own text names the rule |
| `gates` | an unconditional (non-path-scoped) rule applies to the agent |
| `spawns` | the seat can start the agent: exactly the seats `Agent(a, b)` names, else every other seat for `orchestrator` or a bare `Agent`/`Task` grant |
| `reviews` | a review seat gates the merge request: the scaffolder's reviewer names, any name ending `reviewer`, `-checker`, `auditor`, `critic` or `verifier`, and `checker` and `editor` |
| `escalates` | the merge-request gate ends at the human |
| `invokes` | commands are human entry points |
| `runs` | a file references the script; from a command, every `.claude/scripts/<name>.py` counts even when missing, so the dangling edge is the finding |
| `owns` | the agent owns the module (code-graph owner), or owns the task (its `owner:` frontmatter). A co-owned task written `a+b` emits one edge per named seat; a seat that has no agent node emits none. |
| `references` | module imports module; task mentions module |
| `briefs` | an instruction file names the agent |
| `cites` | an instruction file points at the rule by its `.claude/rules/<name>.md` path |
| `imports` | an instruction file `@`-imports another (`CLAUDE.md` -> `AGENTS.md`) |
| `routes` | a routing-tier row names the agent that runs that tier |
| `uses` | a file names a skill |
| `delegates` | a command, agent or skill hands work to an agent |
| `sources` | a hook loads a shared helper hook (`_lib.sh`) |
| `refers` | any other named reference (hook -> agent/skill/command, rule -> agent) |

`invokes`, `cites` and `runs` are also emitted from any file that names a command, rule or
script. Everything content-derived follows the rules in `docs/HARNESS-GRAPH-SCHEMA.md`
("Content references"), implemented by `src/refs.rs` and its twin `references()` in
`harness-graph.py`: a path, a `/command`, an exact code or bold span, or a hyphenated slug
counts; a single word in prose never does.

### Parity

`scripts/check_graph_parity.py` runs both scanners on `tests/fixture`,
`tests/kit-fixture` (every subagent field, seat-registered hooks, the task
board), a generated edge-case tree and two fresh scaffolds, and fails on any
byte of difference. Every field on this page is emitted by both.

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

## Assessment (`assess --json`, `GET /assess`)

Written by `harness-view` only; no timestamp. Every text field has a `_ja` twin.

| key | shape |
|---|---|
| `version` | 1 |
| `root` | the repository, slash-separated |
| `purposes` | `{"list": ["code", "research", ...], "source": "vars.json" \| "roster" \| "default" \| "given", "rules_not_applied": [rubric ids]}` |
| `counts` | `{"high", "medium", "low", "info"}` |
| `scores` | `{"overall", "categories": {<name>: {"score", "findings", "penalty", "label_ja", "derivation": [{"rubric", "count", "weight", "points"}]}}, "method", "not_measured"}` |
| `worklist` | rules with findings, best value first: `{"rubric", "check", "severity", "category", "title", "full", "fix", "names", "count", "effort", "points", "priority", "one_click", "overall_after", "gain", "keys"}` |
| `statistics` | node, edge, model, status, rule and hook counts |
| `findings` | worst first: `{"rubric", "check", "category", "severity", "weight", "effort", "title", "why", "fix", "node", "file", "line", "evidence", "key", "action"?}` |
| `since` | only with a previous assessment: `{"fixed", "new", "unchanged", "overall": {"from", "to"}, "categories", "graph"?}` |

- `evidence` is `file:line`. For a missing frontmatter key the line is the
  closing `---`, where the key belongs.
- `priority` is `points * 6 / effort`, where `points` is weight times count; `6`
  keeps efforts 1, 2 and 3 integral. `overall_after` is the overall score with
  that rule's findings gone.
- `key` identifies a finding across two runs (`check|node|name|extra`); `since`
  matches on it. `since.graph` (server only) lists `nodes_added`,
  `nodes_removed`, `edges_added` and `edges_removed`.
- `action` is `{"endpoint": "agent", "label", "label_ja", "body"}`: a request for
  `POST /agent` as it stands. It is present only when the agent editor accepts
  every value in `body`.

The weights, efforts and texts are in [RUBRIC.md](RUBRIC.md), generated from
`src/rubric.rs`. `GET /rubric` serves the same table as JSON.

## Versioning

`version` increments only on a breaking shape change. Consumers must reject a
larger major version rather than guess.

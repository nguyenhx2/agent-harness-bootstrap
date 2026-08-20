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
`hook:`, `script:`, `mod:`, `task:`, `instr:`, plus the singletons `settings`,
`gate:merge-request`, `human`.

**Every node carries `label` and `disabled`** (false when not applicable).
Label forms: commands are `/<name>`, the synthetic gate is `Merge request`,
the human node is `Human`, settings is `settings.json`, scripts are
`<name>.py`, modules are the module path, everything else the bare name.

| type | id example | additional fields |
|---|---|---|
| agent | `agent:code-reviewer` | `file`, `meta` (`model`, `effort`, `maxTurns`, `tools`, `description`) |
| rule | `rule:testing` | `file`, `meta` (`scoped`, `paths` when scoped and unquoted, `description`) |
| command | `cmd:deploy` | `file` |
| hook | `hook:protect-secrets` | `file` (the .sh flavor when both exist, else the .ps1), `meta` (`registered`, `event`, `matcher`, `blocking`) |
| settings | `settings` | `file`, `edit`; no meta (present only when settings.json exists) |
| instruction | `instr:agents`, `instr:cursor-rules/testing` | `file`, `edit`, `meta` (`tools`, `source`, `verified`, `note`), `tiers` when the file carries a routing table |
| script | `script:code-graph` | `file` (every `*.py` under `.claude/scripts/`) |
| module | `mod:src/app` | `meta` with BOTH `files` (count) and `owner` (agent name or `-`) |
| task | `task:TASK-042` | `file` (every `TASK-*.md` under `docs/tasks/**`), `meta` (`title`, `status`, `fr`, `owner`, `deps`, `priority`, `phase` when the frontmatter carries them) |
| gate | `gate:merge-request` | `synthetic: true` |
| human | `human` | `synthetic: true` |

Items found under `.claude/disabled/{rules,commands,hooks}/` still appear as
nodes, with `disabled: true` and `file` pointing at the quarantine path.

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
`{"tier", "change", "who", "adds"}` in file order. Any agent the `who` column
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
| `triggers` | settings.json registration fires the hook |
| `enforces` | the hook mechanically enforces the rule (static table) |
| `gates` | an unconditional (non-path-scoped) rule applies to the agent |
| `spawns` | the orchestrator dispatches the agent |
| `reviews` | a reviewer seat gates the merge request |
| `escalates` | the merge-request gate ends at the human |
| `invokes` | commands are human entry points |
| `runs` | the command references the script; one edge per referenced `.claude/scripts/*.py`, so a command may run several |
| `owns` | the agent owns the module (code-graph owner), or owns the task (its `owner:` frontmatter). A co-owned task written `a+b` emits one edge per named seat; a seat that has no agent node emits none. |
| `references` | module imports module; task mentions module |
| `briefs` | an instruction file names the agent |
| `cites` | an instruction file points at the rule by its `.claude/rules/<name>.md` path |
| `imports` | an instruction file `@`-imports another (`CLAUDE.md` -> `AGENTS.md`) |
| `routes` | a routing-tier row names the agent that runs that tier |

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

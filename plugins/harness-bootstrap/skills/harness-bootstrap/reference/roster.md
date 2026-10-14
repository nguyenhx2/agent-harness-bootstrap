# Roster - which agents to field, and how to configure each one

Decides the formation ("đội hình") and its per-agent configuration. The reasoning behind the
`model:` and `effort:` columns is in [`cost-model.md`](cost-model.md) - read it before deviating.
Agent bodies live in `assets/claude/agents/`; the scaffolder copies them, so you set the roster, not
the prose. The chosen roster must appear 1:1 in the orchestrator's routing table and the AGENTS.md
roster table: no orphan agents, no unrouted work.

## Purpose profiles - which seats a repo gets

The first intake question is what the repo is FOR. One or more of these flags; none means
`purpose_code`, which is the roster every earlier version of this skill produced.

| Purpose | Seats (beyond `orchestrator`) | Verification | What it never gets |
|---|---|---|---|
| `purpose_code` | dev agent(s), the review gate, `spec-guardian`, `ba-analyst`, `debugger`, `devops`, + `qa-test` (`tests`), DB seats (`db*`), `merge-manager` (`merge_gate`) | tests, code + security review, `/secret-scan` at the branch boundary | - |
| `purpose_research` | `researcher`, `checker` | every claim traced to a source that says it; primary over secondary; dates current | unit tests, code or security review |
| `purpose_strategy` | `strategist`, `researcher` (evidence for the matrix), `checker` | assumptions that flip the recommendation, genuinely distinct options, criteria fixed before scoring | unit tests, code or security review |
| `purpose_docs` | `writer`, `checker` | accuracy against the source, links and anchors, one fact in one place, house style | unit tests, code or security review |

Purposes combine: `purpose_code` + `purpose_docs` adds `writer` and `checker` beside the code
roster; `checker` then covers the non-code deliverables while the code review gate keeps the code.
**One `checker` serves every non-code purpose** - its body carries one section per purpose,
resolved at scaffold time - so a research + strategy + docs repo has five seats, not eight. The
code-only flags (`db*`, `ai`, `tdd`, `ddd`, `light`, `unit`, `e2e`, `tests`, `solo_review`,
`merge_gate`) are refused without `purpose_code` rather than fielding seats with nothing to do.

## The allocation table

Every generated agent carries `model:`, `effort:`, `tools:` and `maxTurns:` explicitly - unset
`model:` means `inherit`, which silently bills mechanical work at the caller's tier, and
`scaffold.py` refuses a seat missing any of them.

| Agent | model | effort | tools | maxTurns | Why |
|---|---|---|---|---|---|
| `orchestrator` | `opus` | `high` | `Read, Grep, Glob, Bash, Write, Edit, Agent, AskUserQuestion, TaskCreate, TaskUpdate, TaskList, TaskOutput` | 60 | Plans, decomposes, judges results. Highest-leverage seat. Write/Edit is for the board only - it never does a seat's work |
| `debugger` | `opus` | `xhigh` | `Read, Grep, Glob, Bash` | 30 | Root-cause under incomplete information is the hardest single-agent task on the roster, and it is low-volume. The one seat that earns `xhigh` unconditionally. Read-only: it diagnoses, the owner fixes |
| `code-reviewer` | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | The safety net. Read-only forever - a reviewer that edits code has become a dev agent and lost its independence |
| `security-reviewer` | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | Secrets/PII/authz gate. Read-only |
| `reviewer` (flag `solo_review`) | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | The merged code+security gate for preset S: one pass, both lenses. Replaces the two seats above; never fielded alongside them |
| `merge-manager` (flag `merge_gate`) | `opus` | `medium` | `Read, Grep, Glob, Bash` | 20 | A gate, not an author: it checks a fixed list, so `medium`. Fielded only with the strict gate below |
| `<domain>-dev` / `app-dev` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | 60 | Implementation against locked criteria; a third attempt escalates effort ([`cost-model.md`](cost-model.md)). Raise to `high` or `xhigh` for a known-hard refactor, not by default |
| `frontend-ui-dev` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | 60 | As above, scoped to UI |
| `data-modeler` | `sonnet` | `high` | `Read, Write, Edit, Grep, Glob, Bash` | 40 | Schema design follows the ERD; judgment is bounded by the data dictionary |
| `db-engineer` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | 40 | Operations, not design. Forward migrations only |
| `qa-test` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | 40 | Tests map to stated acceptance criteria - a settled contract, so `medium` suffices |
| `spec-guardian` | `sonnet` | `medium` | `Read, Grep, Glob` | 15 | Checks a diff against written criteria. Read-only, no Bash - it has nothing to run |
| `ba-analyst` | `sonnet` | `high` | `Read, Write, Edit, Grep, Glob` | 40 | Prose quality matters; writes only inside `docs/` |
| `devops` | `sonnet` | `medium` | `Read, Grep, Glob, Bash` | 40 | Pipelines and environments. Never edits CI to skip a check |
| `researcher` (`purpose_research`, `purpose_strategy` or `long`) | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, WebSearch, WebFetch` | 40 | Gathers sources and writes a cited synthesis under `docs/`. Under `purpose_code` it also evaluates libraries, providers and approaches against the project's constraints |
| `strategist` (`purpose_strategy` or `long`) | `opus` | `high` | `Read, Write, Edit, Grep, Glob` | 30 | Frames a decision, scores distinct options, writes the memo. A judgment call under incomplete information, hence `opus`. It writes the memo it produces, so the decision lands as a file, not a chat message |
| `writer` (`purpose_docs`) | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob` | 40 | Documentation from a stated source. Writing to a settled source is `medium` work |
| `checker` (any non-code purpose) | `opus` | `high` | `Read, Grep, Glob, WebFetch, WebSearch` | 25 | The non-code review gate: sources, red team, or docs accuracy. Read-only, like every reviewer |
| `history-tracker` | `haiku` | `low` | `Read, Grep, Glob, Bash` | 10 | Summarizes an append-only archive. High volume, no judgment |
| `db-seeder` | `haiku` | `low` | `Read, Write, Edit, Grep, Glob, Bash` | 15 | Runs a deterministic script against a schema. Synthetic data only, local/dev targets only |
| `<repo>-auditor` (audit mode) | `opus` | `high` | `Read, Grep, Glob, Bash` | 30 | Manual analysis that must catch what the scanners miss. Same role as a reviewer |
| `perf-reviewer` (audit mode) | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | As above, for performance |
| `sast-runner` (audit mode) | `haiku` | `low` | `Read, Grep, Glob, Bash` | 15 | Runs a pinned scanner suite and normalizes output. Explicitly never judges severity |

## Frontmatter, field by field - what each seat sets and why

Claude Code accepts more fields than `model`, `effort` and `tools`
([sub-agents reference](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields)).
Each is used where it earns its place and deliberately left out elsewhere:

| Field | Where it is set | Why there, and not elsewhere |
|---|---|---|
| `disallowedTools: Edit, Write, NotebookEdit` | every read-only seat: the reviewers, `spec-guardian` (also `Bash`), `debugger`, `merge-manager`, `devops`, `history-tracker`, `checker` | Belt and braces beside `tools:`, so a later `/agent-permissions` grant cannot quietly turn a judge into an author. Writers omit it: their `tools:` allowlist already excludes what they do not hold |
| `Agent` in `tools:` | `orchestrator` only | The single dispatch point. `scaffold.py` refuses a second seat holding `Agent`, bare or as `Agent(a, b)`. The `Agent(a, b)` allowlist form is not used: it binds only when the orchestrator runs as the main thread, is ignored in a subagent, and would be a second roster list to keep in sync - `guard-agent-spawn` already enforces the roster |
| `memory: project` | `researcher`, `writer`, the dev agents | Seats that get better at THIS repo across sessions: reliable sources, house style, a module's pitfalls. Never on a read-only seat - memory grants Write and Edit, and `scaffold.py` refuses it on a review seat. Never task state: that lives on the board |
| `permissionMode: dontAsk` | the code review seats, `spec-guardian`, `history-tracker` | A gate must not stall on a prompt mid-review; what it needs is pre-approved, and anything else is denied rather than asked. Every other seat inherits the session's mode, which is the human's dial (`/harness-tune`). `bypassPermissions` is refused on any seat |
| `omitClaudeMd: true` | the review seats, `spec-guardian`, `history-tracker`, `checker` | Seats that take everything from their brief and the rules they cite: skipping `CLAUDE.md` and `AGENTS.md` saves about 200 lines of context per dispatch. Older Claude Code ignores the field |
| `initialPrompt` | `orchestrator` | Applies only when it runs as the main session (`claude --agent orchestrator`): the session opens on the board restore instead of a blank prompt |
| `experimental.cacheTtl: 1h` | `orchestrator` | It waits on children longer than the default 5-minute cache window, so its long prefix is otherwise re-written after every child returns |
| `isolation: worktree` | none in frontmatter | It branches from the default branch, not the caller's HEAD, and would put every Direct fix on a side branch. The orchestrator asks for it per dispatch (`isolation: "worktree"` on the Agent call) when parallel writers would collide |
| `skills:` | none by default | A preload injects the whole skill on every dispatch. `/skill-wire` adds one to the seat that always needs it, once the skill is installed and reviewed |
| `hooks:` | none by default | Hooks that bind every seat live in `settings.json`. An agent-scoped hook is the right home for a rule that binds one seat - limiting the orchestrator's writes to the board is the obvious candidate - once such a hook script ships |
| `mcpServers`, `background` | unset | MCP access is granted per project through `/agent-permissions`; `background` would hide a seat the caller is waiting on |

Any agent not in this table - a new `<domain>-dev`, a project-specific one-off - is classified with
the decision rule in [`cost-model.md`](cost-model.md), not guessed by analogy to the closest-sounding
name. Record the pick in `docs/context/tool-changelog.md`.

### Tool grants: the two rules that matter

- **Reviewers never get `Edit` or `Write`.** Not "usually don't" - never. It is what makes their
  finding trustworthy, and the quality gate checks it.
- **Never omit `tools:`.** Omitting inherits everything, including every MCP server on the machine -
  thousands of tokens of tool schema on every request, for tools the agent will never call. If the
  project has MCP servers an agent shouldn't touch, add `disallowedTools`.

## Tiers - what to field

### Tier 0 - core (every `purpose_code` project, no exceptions)

| Agent | Why it is unconditional |
|---|---|
| `orchestrator` | The entry point that makes the base *operate* under orchestration. Without it the roster is a folder of files |
| `code-reviewer` | The review gate |
| `security-reviewer` | Secrets/data gate. On a tiny project the two reviewer seats merge into one `reviewer` (flag `solo_review`) - but the security **checklist** never disappears |
| `spec-guardian` | Requirement-drift check, before and after every feature |
| At least ONE dev agent | Someone has to write code. Minimum viable: a single `app-dev` owning all of `src/` |

### Tier 1 - standard delivery (accept by default, decline consciously)

`qa-test` (any logic worth testing - i.e. almost always) · `debugger` (a test suite or CI exists) ·
`ba-analyst` (specs live in the repo) · `devops` (a CI pipeline or a hosting target exists).
`merge-manager` is fielded only with flag `merge_gate` and the gate below; without it the human
merges, which is the right default for almost every team.

### Tier 2 - conditional by stack

`frontend-ui-dev` (project has UI) · `data-modeler` (flag `db` alone), then `db-engineer` (flag
`db_engineer`) and `db-seeder` (flag `db_seeder`) - start with `data-modeler` and add the flags when
migrations and seeding become real work; intake Q19 asks exactly this ·
a shared-layer agent such as `llm-integration-dev` (an external provider layer that *multiple* domains
call - shared layers get an owner so ownership is unambiguous) · one `<domain>-dev` per feature domain.

### Tier 3 - planning and audit (multi-week projects; flag `long`)

`strategist` + `researcher` (structured decisions feeding ADRs, with cited evidence) ·
`history-tracker` (curates the run archive written by the `agent-history` hook). The same two seats
are the base of the strategy and research purposes, so one pair serves both the code planning work
and the non-code purposes.
In a code repo they ship only when the `long` flag is set - the
roster-shape question in intake asks for the project horizon; a short project pays for these seats
without using them.

## Presets

Pick the closest, then adjust with the tiers.

- **S - script / CLI / library, single domain (5-6 ACTIVE seats).** `orchestrator`, `app-dev`,
  `qa-test` (if tests are chosen), `reviewer` (the merged gate, flag `solo_review` - the
  recommended shape here; split reviewers remain the alternative), `spec-guardian`. **This is the
  floor** - below it the Guarded flow has missing seats. Honesty note: a code repo also installs
  `debugger`, `ba-analyst` and `devops`; on preset S they receive no routing missions until the
  project grows into them.
- **M - web/API app with a DB (9-12).** Tier 0 + `qa-test`, `debugger`, `ba-analyst`, `devops`,
  + `frontend-ui-dev` (if UI) + `data-modeler` (+ `db_engineer`/`db_seeder` flags as DB work grows)
  + 1-3 `<domain>-dev`. Split reviewers recommended.
- **L - AI product / multi-domain platform (14+).** Preset M + a shared provider-layer agent + one dev
  agent per FR cluster + the `long` flag (the planning pair + `history-tracker`). This is the preset
  that sets `long` by default.

## Deriving the dev-agent lineup

**Brownfield:** from the module mapping in the Inventory Report. Every module has exactly one owning
dev agent; every dev agent's scope names real paths that exist.

**Greenfield with specs:** cluster the FR list into feature domains - FRs sharing data entities, a
pipeline stage, or an external provider belong to one domain. One dev agent per cluster, scoped to the
*planned* module path (`src/lib/<domain>/`). The scaffold and the agent scope get defined together, so
the first `/implement-fr` already has an owner and a place to put the code.

**Greenfield with no specs:** field Preset S with a single `app-dev` scoped to `src/`, plus a
registered P1 task "split `app-dev` by domain once modules emerge". Do **not** invent speculative
domain agents for code that does not exist - a scope matching nothing real is noise in the routing
table and tokens in every dispatch.

**When the specs carry a module axis** (`docs/specs/modules/<module>/` exists), the module's dev
agent owns that folder as well as its code paths: its `scope` lists both, and the orchestrator
routes every spec question about that module to it rather than to `ba-analyst` generically. The
spec module code is also what its FR IDs carry (`FR-BLG-01`), so the agent's `description:` FR
list, the routing table, and the folder name all say the same thing. A module folder with no owning
dev agent is the same defect as a code module with none.

Each module also gets a small `CLAUDE.md` of its own (the `modules` list in `vars.json`, rendered
from `assets/root/module-CLAUDE.md`): its owner seat, its scope, and the invariants and commands that
hold only there. That is where module-specific guidance goes instead of the root files.

Rule of thumb: a dev agent owns something describable in one sentence ("the scoring engine"). More
than ~5 dev agents at bootstrap is speculative splitting; fewer than one per 2-3 FRs on a large
product produces a future grab-bag.

## `merge-manager` - the optional delegated merge gate (flag `merge_gate`)

Field it when parallel dev agents produce a steady stream of PRs and manual merging is the
bottleneck; skip it on a solo or low-volume project. What makes it safe:

- **Read-only on product code, plus Bash.** It runs git and CI queries and it merges. Never authors.
- **A merge passes only if ALL hold:** CI green (polled to a terminal state, not presumed) · no
  conflict with the *live* mainline tip · the required reviews verified in the task file's session
  log, not claimed in the PR body · the secret scan clean on the diff · the diff touches no rule
  file, agent file, hook, settings file, or Accepted ADR - a governance-file diff escalates to the
  owner, never self-merged.
- **Dispatched only by the orchestrator, one PR at a time, serialized.** Never two merges in flight
  against the same mainline.
- **Never touches a branch with a live worktree**, and never merges a change it authored (it authors
  nothing).

## Roster completeness check

Before finishing, verify the formation can actually play the Guarded flow - every seat filled
by exactly one agent. The table is the code flow; a non-code repo's flow is the brief, the producer
(`researcher` / `strategist` / `writer`), `checker`, and the `orchestrator` - nothing else. A seat here is a seat the flow can call when it needs it, not a seat every
change must pass through:

| Flow step | Seat | Filled by |
|---|---|---|
| Lock scope + criteria | requirement gate | `spec-guardian` |
| Implement (per the chosen methodology) | owner | the `<domain>-dev` for that FR |
| Tests | quality | `qa-test` (or manual verification when testing was declined - say so) |
| Review diff | code gate | `code-reviewer` (or `reviewer` under `solo_review`) |
| Review secrets/data | security gate | `security-reviewer` (or `reviewer` under `solo_review`) |
| Open PR/MR, CI | pipeline | `devops` (or the dev agent on Preset S - say so) |
| Failure diagnosis | root cause | `debugger` (or the user - say so) |
| Decide + record | planning | `strategist`/`researcher` → ADR (or the user) |
| Route, supervise, record | control | `orchestrator` |

If a seat is intentionally unfilled, AGENTS.md must name who covers it instead. An unnamed seat is how
gates get silently skipped.

## Growth path

- **Split a dev agent** when its scope spans two domains changing for different reasons. Splitting =
  new agent file + routing-table row + AGENTS.md roster row + moved module ownership, in one MR.
- **Add the planning pair** at the first contested technical decision - "we argued about a library
  in chat" should have been a `/brainstorm` → ADR.
- **Never grow reviewers' tools.** See above.
- Batch roster changes rather than trickling them: every `tools:` change invalidates that agent's
  prompt cache ([`cost-model.md`](cost-model.md)).

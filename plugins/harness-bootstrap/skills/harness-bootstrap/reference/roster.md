# Roster - which agents to field, and how to configure each one

Decides the formation ("đội hình") and its per-agent configuration. The reasoning behind the
`model:` and `effort:` columns is in [`cost-model.md`](cost-model.md) - read it before deviating.
Agent bodies live in `assets/claude/agents/`; the scaffolder copies them, so you set the roster, not
the prose. The chosen roster must appear 1:1 in the orchestrator's routing table and the AGENTS.md
roster table: no orphan agents, no unrouted work.

## The allocation table

Every generated agent carries `model:` and `effort:` explicitly - unset `model:` means `inherit`,
which silently bills mechanical work at the caller's tier.

| Agent | model | effort | tools | maxTurns | Why |
|---|---|---|---|---|---|
| `orchestrator` | `opus` | `high` | `Read, Grep, Glob, Bash, Write, Edit, Agent, TaskCreate, TaskUpdate, TaskList, TaskOutput` | - | Plans, decomposes, judges results. Highest-leverage seat. Write/Edit is for `docs/` and `.claude/` only - it never authors product code |
| `debugger` | `opus` | `xhigh` | `Read, Grep, Glob, Bash` | 30 | Root-cause under incomplete information is the hardest single-agent task on the roster, and it is low-volume. The one seat that earns `xhigh` unconditionally. Read-only: it diagnoses, the owner fixes |
| `code-reviewer` | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | The safety net. Read-only forever - a reviewer that edits code has become a dev agent and lost its independence |
| `security-reviewer` | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | Secrets/PII/authz gate. Read-only |
| `reviewer` (flag `solo_review`) | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | The merged code+security gate for preset S: one pass, both lenses. Replaces the two seats above; never fielded alongside them |
| `merge-manager` (installed unconditionally; ACTIVE only with the strict gate below) | `opus` | `high` | `Read, Grep, Glob, Bash` | 20 | A gate, not an author. Only field it with the strict gate below |
| `<domain>-dev` / `app-dev` | `sonnet` | `high` | `Read, Write, Edit, Grep, Glob, Bash` | - | Implementation against a settled spec. Raise to `xhigh` for a known-hard refactor, not by default |
| `frontend-ui-dev` | `sonnet` | `high` | `Read, Write, Edit, Grep, Glob, Bash` | - | As above, scoped to UI |
| `data-modeler` | `sonnet` | `high` | `Read, Write, Edit, Grep, Glob, Bash` | - | Schema design follows the ERD; judgment is bounded by the data dictionary |
| `db-engineer` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | - | Operations, not design. Forward migrations only |
| `qa-test` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | - | Tests map 1:1 to stated acceptance criteria - a settled contract, so `medium` suffices |
| `spec-guardian` | `sonnet` | `medium` | `Read, Grep, Glob` | 15 | Checks a diff against written criteria. Read-only, no Bash - it has nothing to run |
| `ba-analyst` | `sonnet` | `high` | `Read, Write, Edit, Grep, Glob` | - | Prose quality matters; writes only inside `docs/` |
| `devops` | `sonnet` | `medium` | `Read, Grep, Glob, Bash` | - | Pipelines and environments. Never edits CI to skip a check |
| `brainstormer` | `sonnet` | `high` | `Read, Grep, Glob, WebSearch, WebFetch` | 20 | Diverges, scores a trade-off matrix, recommends. Read-only on code |
| `tech-researcher` | `sonnet` | `medium` | `Read, Grep, Glob, Bash, WebSearch, WebFetch` | 20 | Cited evidence against project constraints. Never sends project data to external services |
| `history-tracker` | `haiku` | `low` | `Read, Grep, Glob, Bash` | 10 | Summarizes an append-only archive. High volume, no judgment |
| `db-seeder` | `haiku` | `low` | `Read, Write, Edit, Grep, Glob, Bash` | 15 | Runs a deterministic script against a schema. Synthetic data only, local/dev targets only |
| `<repo>-auditor` (audit mode) | `opus` | `high` | `Read, Grep, Glob, Bash` | 30 | Manual analysis that must catch what the scanners miss. Same role as a reviewer |
| `perf-reviewer` (audit mode) | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | As above, for performance |
| `sast-runner` (audit mode) | `haiku` | `low` | `Read, Grep, Glob, Bash` | 15 | Runs a pinned scanner suite and normalizes output. Explicitly never judges severity |

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

### Tier 0 - core (every project, no exceptions)

| Agent | Why it is unconditional |
|---|---|
| `orchestrator` | The entry point that makes the base *operate* under orchestration. Without it the roster is a folder of files |
| `code-reviewer` | The review gate |
| `security-reviewer` | Secrets/data gate. On a tiny project the two reviewer seats merge into one `reviewer` (flag `solo_review`) - but the security **checklist** never disappears |
| `spec-guardian` | Requirement-drift check, before and after every feature |
| At least ONE dev agent | Someone has to write code. Minimum viable: a single `app-dev` owning all of `src/` |

### Tier 1 - standard delivery (accept by default, decline consciously)

`qa-test` (any logic worth testing - i.e. almost always) · `debugger` (a test suite or CI exists) ·
`ba-analyst` (specs live in the repo) · `devops` (a CI pipeline or a hosting target exists) ·
`merge-manager` (its seat file always installs; route merges to it only with the gate below,
otherwise the human merges and the seat stays idle).

### Tier 2 - conditional by stack

`frontend-ui-dev` (project has UI) · `data-modeler` (flag `db` alone), then `db-engineer` (flag
`db_engineer`) and `db-seeder` (flag `db_seeder`) - start with `data-modeler` and add the flags when
migrations and seeding become real work; intake Q19 asks exactly this ·
a shared-layer agent such as `llm-integration-dev` (an external provider layer that *multiple* domains
call - shared layers get an owner so ownership is unambiguous) · one `<domain>-dev` per feature domain.

### Tier 3 - planning and audit (multi-week projects; flag `long`)

`brainstormer` + `tech-researcher` (structured decisions feeding ADRs) · `history-tracker` (curates the
run archive written by the `agent-history` hook). Shipped only when the `long` flag is set - the
roster-shape question in intake asks for the project horizon; a short project pays for these seats
without using them.

## Presets

Pick the closest, then adjust with the tiers.

- **S - script / CLI / library, single domain (5-6 ACTIVE seats).** `orchestrator`, `app-dev`,
  `qa-test` (if tests are chosen), `reviewer` (the merged gate, flag `solo_review` - the
  recommended shape here; split reviewers remain the alternative), `spec-guardian`. **This is the
  floor** - below it the standard feature flow has missing seats. Honesty note: the manifest also
  installs `debugger`, `ba-analyst`, `devops`, and `merge-manager` unconditionally; on preset S
  they simply receive no routing missions until the project grows into them.
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

Rule of thumb: a dev agent owns something describable in one sentence ("the scoring engine"). More
than ~5 dev agents at bootstrap is speculative splitting; fewer than one per 2-3 FRs on a large
product produces a future grab-bag.

## `merge-manager` - the optional delegated merge gate

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

Before finishing, verify the formation can actually play the standard feature flow - every seat filled
by exactly one agent:

| Flow step | Seat | Filled by |
|---|---|---|
| Lock scope + criteria | requirement gate | `spec-guardian` |
| Implement (per the chosen methodology) | owner | the `<domain>-dev` for that FR |
| Tests | quality | `qa-test` (or manual verification when testing was declined - say so) |
| Review diff | code gate | `code-reviewer` (or `reviewer` under `solo_review`) |
| Review secrets/data | security gate | `security-reviewer` (or `reviewer` under `solo_review`) |
| Open PR/MR, CI | pipeline | `devops` (or the dev agent on Preset S - say so) |
| Failure diagnosis | root cause | `debugger` (or the user - say so) |
| Decide + record | planning | `brainstormer`/`tech-researcher` → ADR (or the user) |
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

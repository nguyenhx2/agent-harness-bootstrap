# Roster - which agents to field, and how to configure each one

Decides the formation ("đội hình") and each seat's configuration; the scaffolder copies the agent
bodies. Why the `model:`/`effort:` columns: [`cost-model.md`](cost-model.md). The roster appears 1:1
in the AGENTS.md roster and routing tables: no orphan seats, no unrouted work.

**What the roster is for.** The main session does the work at every tier, inside one repository
and one domain - auth and schema included. A single agent loop with skills matched or beat routing
work to writing seats in every case an external benchmark measured (CHANGELOG, 1.23.0), at a
fraction of the cost and wall time. So the seats that earn a dispatch by default are the ones that earn their
context: the **read-only reviewers** (required on Guarded changes), **readers that return a
summary** (`debugger`, `researcher`, `spec-guardian`, `history-tracker`), and **independent
parallel batches**. A writing seat (`<domain>-dev`, `qa-test`, `ba-analyst`, `data-modeler`,
`writer`, ...) still ships: its scope is the ownership map, its module `CLAUDE.md` carries what it
knows to the main session, and it is dispatched only when the user names it or the opt-in
`orchestrator` runs a multi-domain mission.

## Purpose profiles - which seats a repo gets

One or more purpose flags (intake Q0); none means `purpose_code`.

| Purpose | Seats (beyond `orchestrator`) | Verification | What it never gets |
|---|---|---|---|
| `purpose_code` | dev agent(s), the review gate, `spec-guardian`, `ba-analyst`, `debugger`, `devops`, + `qa-test` (`tests`), DB seats (`db*`), `merge-manager` (`merge_gate`) | tests, code + security review, `/secret-scan` at the branch boundary | - |
| `purpose_research` | `researcher`, `checker` | every claim traced to a source that says it; primary over secondary; dates current | unit tests, code or security review |
| `purpose_strategy` | `strategist`, `researcher` (evidence for the matrix), `checker` | assumptions that flip the recommendation, genuinely distinct options, criteria fixed before scoring | unit tests, code or security review |
| `purpose_docs` | `writer`, `checker` | accuracy against the source, links and anchors, one fact in one place, house style | unit tests, code or security review |

Purposes combine: `purpose_code` + `purpose_docs` adds `writer` and `checker`, which covers the
non-code deliverables while the code review gate keeps the code. **One `checker` serves every
non-code purpose** (one body section per purpose), so research + strategy + docs is five seats, not
eight. Code-only flags are refused without `purpose_code`.

## The allocation table

Every seat carries `model:`, `effort:`, `tools:` and `maxTurns:`; `scaffold.py` refuses a seat
missing any of them.

| Agent | model | effort | tools | maxTurns | Why |
|---|---|---|---|---|---|
| `orchestrator` | `opus` | `high` | `Read, Grep, Glob, Bash, Write, Edit, Agent, AskUserQuestion, TaskCreate, TaskUpdate, TaskList, TaskOutput` | 60 | Opt-in: plans, decomposes and judges a mission across several domains or repositories, only when the user asks for it. Write/Edit is for the board only - it never does a seat's work |
| `debugger` | `opus` | `xhigh` | `Read, Grep, Glob, Bash` | 30 | Root-cause under incomplete information: the hardest, lowest-volume task, so the one seat on `xhigh`. Read-only: it diagnoses, the owner fixes |
| `code-reviewer` | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | The safety net. Read-only forever - a reviewer that edits has lost its independence |
| `security-reviewer` | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | Secrets/PII/authz gate. Read-only |
| `reviewer` (flag `solo_review`) | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | The merged code+security gate for preset S. Replaces the two seats above |
| `merge-manager` (flag `merge_gate`) | `opus` | `medium` | `Read, Grep, Glob, Bash` | 20 | A gate checking a fixed list, so `medium`. See the merge gate below |
| `<domain>-dev` / `app-dev` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | 60 | Implementation against locked criteria; a third attempt escalates effort ([`cost-model.md`](cost-model.md)). Raise to `high` or `xhigh` for a known-hard refactor, not by default |
| `frontend-ui-dev` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | 60 | As above, scoped to UI |
| `data-modeler` | `sonnet` | `high` | `Read, Write, Edit, Grep, Glob, Bash` | 40 | Schema design follows the ERD; judgment is bounded by the data dictionary |
| `db-engineer` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | 40 | Operations, not design. Forward migrations only |
| `qa-test` | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, Bash` | 40 | Tests map to stated acceptance criteria - a settled contract, so `medium` suffices |
| `spec-guardian` | `sonnet` | `medium` | `Read, Grep, Glob` | 15 | Checks a diff against written criteria. Read-only, no Bash - it has nothing to run |
| `ba-analyst` | `sonnet` | `high` | `Read, Write, Edit, Grep, Glob` | 40 | Prose quality matters; writes only inside `docs/` |
| `devops` | `sonnet` | `medium` | `Read, Grep, Glob, Bash` | 40 | Pipelines and environments. Never edits CI to skip a check |
| `researcher` (`purpose_research`, `purpose_strategy` or `long`) | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob, WebSearch, WebFetch` | 40 | Cited synthesis under `docs/`; under `purpose_code` also evaluates libraries and providers against the constraints |
| `strategist` (`purpose_strategy` or `long`) | `opus` | `high` | `Read, Write, Edit, Grep, Glob` | 30 | Frames a decision, scores distinct options, writes the memo as a file. Judgment under incomplete information, hence `opus` |
| `writer` (`purpose_docs`) | `sonnet` | `medium` | `Read, Write, Edit, Grep, Glob` | 40 | Documentation from a stated source. Writing to a settled source is `medium` work |
| `checker` (any non-code purpose) | `opus` | `high` | `Read, Grep, Glob, WebFetch, WebSearch` | 25 | The non-code review gate: sources, red team, or docs accuracy. Read-only, like every reviewer |
| `history-tracker` | `haiku` | `low` | `Read, Grep, Glob, Bash` | 10 | Summarizes an append-only archive. High volume, no judgment |
| `db-seeder` | `haiku` | `low` | `Read, Write, Edit, Grep, Glob, Bash` | 15 | Runs a deterministic script against a schema. Synthetic data only, local/dev targets only |
| `<repo>-auditor` (audit mode) | `opus` | `high` | `Read, Grep, Glob, Bash` | 30 | Manual analysis that must catch what the scanners miss. Same role as a reviewer |
| `perf-reviewer` (audit mode) | `opus` | `high` | `Read, Grep, Glob, Bash` | 25 | As above, for performance |
| `sast-runner` (audit mode) | `haiku` | `low` | `Read, Grep, Glob, Bash` | 15 | Runs a pinned scanner suite and normalizes output. Explicitly never judges severity |

## Frontmatter, field by field - what each seat sets and why

Each further field ([sub-agents reference](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields))
is set only where it earns its place:

| Field | Where it is set | Why there, and not elsewhere |
|---|---|---|
| `disallowedTools: Edit, Write, NotebookEdit` | every read-only seat: the reviewers, `spec-guardian` (also `Bash`), `debugger`, `merge-manager`, `devops`, `history-tracker`, `checker` | Beside `tools:`, so a later `/agent-permissions` grant cannot turn a judge into an author. Writers omit it |
| `Agent` in `tools:` | `orchestrator` only | The single dispatch point; `scaffold.py` refuses a second holder, bare or as `Agent(a, b)`. The allowlist form is unused: ignored in a subagent, and `guard-agent-spawn` already enforces the roster |
| `memory: project` | `researcher`, `writer`, the dev agents | Seats that improve at THIS repo across sessions (sources, house style, a module's pitfalls). Never on a read-only seat - memory grants Write and Edit, and `scaffold.py` refuses it. Never task state |
| `permissionMode: dontAsk` | the code review seats, `spec-guardian`, `history-tracker` | A gate must not stall on a prompt; anything not pre-approved is denied. Other seats inherit the session's mode (`/harness-tune`). `bypassPermissions` is refused on any seat |
| `omitClaudeMd: true` | the review seats, `spec-guardian`, `history-tracker`, `checker` | Seats that take everything from their brief and cited rules skip `CLAUDE.md` and `AGENTS.md` on every dispatch. Older Claude Code ignores the field |
| `initialPrompt` | `orchestrator` | Applies only if a user starts a session as it: the session opens on the board restore instead of a blank prompt. Not recommended - an always-orchestrator session paid the full planning and dispatch cost even for a one-line fix (CHANGELOG, 1.23.0) |
| `experimental.cacheTtl: 1h` | `orchestrator` | It waits on children past the 5-minute cache window; otherwise its prefix is re-written after every child |
| `isolation: worktree` | none in frontmatter | It branches from the default branch, not HEAD. The orchestrator sets it per dispatch when parallel writers would collide |
| `skills:` | none by default | A preload injects the whole skill on every dispatch. `/skill-wire` adds one where a seat always needs it |
| `hooks:` | none by default | Hooks for every seat live in `settings.json`; an agent-scoped hook is for a rule binding one seat |
| `mcpServers`, `background` | unset | MCP access is granted per project through `/agent-permissions`; `background` would hide a seat the caller is waiting on |

Classify a seat not in the allocation table with the decision rule in
[`cost-model.md`](cost-model.md), never by analogy to a similar name, and record the pick in
`docs/context/tool-changelog.md`.

### Tool grants: the two rules that matter

- **Reviewers never get `Edit` or `Write`.** It is what makes their findings trustworthy.
- **Never omit `tools:`.** Omitting inherits every MCP server on the machine, schema and all, on
  every request. Use `disallowedTools` for servers a seat should not touch.

## Tiers - what to field

### Tier 0 - core (every `purpose_code` project, no exceptions)

| Agent | Why it is unconditional |
|---|---|
| `code-reviewer` | The review gate - the independent read-only review a Guarded change requires |
| `security-reviewer` | Secrets/data gate. On a tiny project the two reviewer seats merge into one `reviewer` (flag `solo_review`) - but the security **checklist** never disappears |
| `spec-guardian` | Requirement-drift check, before and after every feature |
| At least ONE dev agent | The ownership map: every module has one owner, and the owner's scope and module `CLAUDE.md` are what the main session follows there. Minimum viable: a single `app-dev` owning all of `src/` |
| `orchestrator` | Installed so a user can opt into it for a multi-domain mission. Nothing routes to it |

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
`history-tracker` (curates the run archive written by the `agent-history` hook). The same pair is
the base of the strategy and research purposes. In a code repo they ship only with `long` (intake's
roster-shape question); a short project would pay for seats it never uses.

## Presets

Pick the closest, then adjust with the tiers.

- **S - script / CLI / library, single domain (5-6 ACTIVE seats).** `orchestrator`, `app-dev`,
  `qa-test` (if tests are chosen), `reviewer` (the merged gate, flag `solo_review` - the
  recommended shape here; split reviewers remain the alternative), `spec-guardian`. **This is the
  floor** - below it the Guarded gate has missing seats. A code repo also installs `debugger`,
  `ba-analyst` and `devops`; on preset S they get no routing until the project grows into them.
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
pipeline stage, or an external provider are one domain. One dev agent per cluster, scoped to the
*planned* module path (`src/lib/<domain>/`), so the first `/implement-fr` already has an owner.

**Greenfield with no specs:** Preset S with a single `app-dev` scoped to `src/`, plus a registered P1
task "split `app-dev` by domain once modules emerge". Never invent domain agents for code that does
not exist.

**When the specs carry a module axis** (`docs/specs/modules/<module>/` exists), the module's dev
agent owns that folder as well as its code paths, and spec questions about the module route to it,
not to `ba-analyst`. Its `description:` FR list (`FR-BLG-01`), the routing table and the folder name
use the same module code. A module folder with no owner is the same defect as a code module with
none.

Each module also gets its own `CLAUDE.md` (the `modules` list in `vars.json`): owner, scope, local
invariants and commands.

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

Every seat of the Guarded gate is filled by exactly one agent. The table is the code flow; a
non-code flow is the brief, the main session drafting (with `researcher` / `strategist` / `writer`
on the roster), and `checker`. A seat is one the flow can call, not one every change passes
through:

| Flow step | Seat | Filled by |
|---|---|---|
| Lock scope + criteria | requirement gate | `spec-guardian` |
| Implement (per the chosen methodology) | owner | the main session, following the owning `<domain>-dev`'s scope and module `CLAUDE.md` |
| Tests | quality | the main session, in the same change (or manual verification when testing was declined - say so) |
| Review diff | code gate | `code-reviewer` (or `reviewer` under `solo_review`) |
| Review secrets/data | security gate | `security-reviewer` (or `reviewer` under `solo_review`) |
| Open PR/MR, CI | pipeline | `devops` (or the dev agent on Preset S - say so) |
| Failure diagnosis | root cause | `debugger` (or the user - say so) |
| Decide + record | planning | `strategist`/`researcher` → ADR (or the user) |
| Route, supervise, record | control | the main session (the `orchestrator` only on a multi-domain mission the user opted into) |

An intentionally unfilled seat is named in AGENTS.md with who covers it; an unnamed one is a gate
silently skipped.

## Growth path

- **Split a dev agent** when its scope spans two domains changing for different reasons. Splitting =
  new agent file + routing-table row + AGENTS.md roster row + moved module ownership, in one MR.
- **Add the planning pair** at the first contested technical decision - "we argued about a library
  in chat" should have been a `/brainstorm` → ADR.
- **Never grow reviewers' tools.**
- Batch roster changes: every `tools:` change invalidates that seat's prompt cache.

# Team roster - which agents to field (project-bootstrap)

Reference for the `project-bootstrap` skill: the standard agent formation ("doi hinh"), preset
rosters per project type, and how to derive the dev-agent lineup when the project is COMPLETELY
NEW (no code, maybe no specs). Skeleton bodies for every agent named here live in
`templates/agents-pack.md`. The chosen roster must end up 1:1 in the orchestrator routing table
and in the CLAUDE.md agent table - no orphan agents, no unrouted work.

## Table of contents

- [Tiers - core vs conditional](#tiers---core-vs-conditional)
- [Preset formations by project type](#preset-formations-by-project-type)
- [Greenfield derivation - a completely new project](#greenfield-derivation---a-completely-new-project)
- [Growth path - when to split or add an agent](#growth-path---when-to-split-or-add-an-agent)
- [Roster completeness check](#roster-completeness-check)

## Tiers - core vs conditional

### Tier 0 - core (EVERY project, no exceptions)

| Agent | Why it is unconditional |
|-------|-------------------------|
| `orchestrator` | The entry point that makes the base operate under orchestration; without it the roster is just files |
| `code-reviewer` | Review gate layer 4; read-only |
| `security-reviewer` | Secrets/data gate; read-only. On tiny projects it may be merged with code-reviewer into one reviewer agent, but the security CHECKLIST never disappears |
| `spec-guardian` | Requirement-drift check before and after every feature; read-only |
| At least ONE dev agent | Someone has to write code. Minimum viable: a single `app-dev` owning all of `src/` |

### Tier 1 - standard delivery (accept by default, decline consciously)

| Agent | Add when |
|-------|----------|
| `qa-test` | The project has any logic worth testing (i.e. almost always; Batch D question 10) |
| `debugger` | CI or a test suite exists (read-only root-cause analysis, owner implements the fix) |
| `ba-analyst` | Specs/PRDs live in the repo (i.e. whenever the docs tree is used as designed) |
| `devops` | There is a CI pipeline or a hosting target |
| `merge-manager` | You want the human OUT of the merge loop and PR volume justifies it - but ONLY with the strict gate below. Read-only on product code: it merges branches, it never authors them |

### Tier 2 - conditional by stack (from intake batches)

| Agent | Condition |
|-------|-----------|
| `frontend-ui-dev` | Project has UI (Batch F) |
| `data-modeler`, `db-engineer`, `db-seeder` | Project has a database (Batch E). Small DB footprint: start with `data-modeler` only and add the other two when migrations/seeding become real work |
| `llm-integration-dev` (or equivalent shared-layer agent) | An external provider layer that MULTIPLE domains call (LLM gateway, payment, search); shared layers get their own owner so ownership is unambiguous |
| One `<domain>-dev` per feature domain | From the module mapping (brownfield) or FR clustering (greenfield - see below) |

### Tier 3 - planning and audit (recommended for multi-week projects)

| Agent | Why |
|-------|-----|
| `brainstormer` + `tech-researcher` | Structured decisions feeding ADRs; pairs with `/brainstorm` |
| `history-tracker` | Curates the agent-run archive written by the `agent-history` hook; the audit trail of orchestration |

## `merge-manager` - the optional delegated merge gate

Delegating merge authority to a dedicated agent successfully removes the human from the merge loop,
but ONLY because it carries a strict, non-negotiable gate. Field it when parallel dev agents produce
a steady stream of PRs and manual merging is the bottleneck; skip it on a solo or low-volume
project. What makes it safe:

- **Read-only on product code plus Bash** (`Read, Grep, Glob, Bash`) - it runs git and CI queries
  and merges; it never edits product code. It is not a dev agent.
- **A merge passes ONLY if ALL hold**: CI green (not pending), no conflict with the live mainline
  tip, the required reviews actually RAN (verified in the task file's session log, not claimed in
  the PR body), the secret scan is clean on the diff, and the diff touches NO rule file, agent file,
  hook, settings file, or Accepted ADR. A diff touching any of those governance files escalates to
  the owner (see "Self-governing changes" in [`guardrails-hooks.md`](guardrails-hooks.md)).
- **Dispatched ONLY by the orchestrator, one PR at a time, serialized** - never invoked directly,
  never two merges in flight against the same mainline (that is how work is silently dropped). The
  orchestrator owns and sequences the merge queue (see "Merging and conflict resolution" in
  [`task-control.md`](task-control.md)).
- **Never touches a branch with a live worktree**, and **never merges a change it authored** (it
  authors nothing).

## Preset formations by project type

Pick the closest preset, then adjust with the tiers above. Numbers are the full roster count.

### Preset S - script/CLI/library, single domain (5-6 agents)

`orchestrator`, `app-dev`, `qa-test`, `code-reviewer`, `security-reviewer` (or one merged
reviewer), `spec-guardian`. No DB trio, no frontend, docs tree can be slim (specs + tasks +
context). This is the FLOOR - never go below it, or the standard feature flow
(spec check -> TDD -> review) has missing seats.

### Preset M - web/API app with DB (9-12 agents)

Tier 0 + `qa-test`, `debugger`, `ba-analyst`, `devops` + `frontend-ui-dev` (if UI) +
`data-modeler` (+ `db-engineer`, `db-seeder` as DB work grows) + 1-3 `<domain>-dev`.

### Preset L - AI product / multi-domain platform (14+ agents; this reference repo's shape)

Preset M + `llm-integration-dev` (shared LLM layer), one dev agent per FR cluster
(parser/scoring/interview/kms in the reference), `brainstormer` + `tech-researcher`,
`history-tracker`, optionally a combined `qa-security-reviewer` for pre-release passes.
`human-in-the-loop.md` rule mandatory; every dev agent's body carries the untrusted-data clause.

## Greenfield derivation - a completely new project

A brand-new repo has no modules to map, so the dev-agent lineup comes from REQUIREMENTS, not code:

1. **Specs exist** (or the user runs `spec-builder` first - always offer, Batch A question 3):
   cluster the FR list into feature domains - FRs that share data entities, a pipeline stage, or
   an external provider belong to one domain. One dev agent per cluster, named after the domain
   (`<domain>-dev`), its scope declared as the PLANNED module path (e.g. `src/lib/<domain>/`).
   The scaffold and the agent scope are defined together, so the first `/implement-fr` already has
   an owner and a place to put code.
2. **No specs and the user declines spec-builder**: field Preset S with a single `app-dev` whose
   scope is `src/` entire, plus a registered P1 task "split app-dev by domain once modules
   emerge". Do NOT invent speculative domain agents for code that does not exist - an agent whose
   scope matches nothing real is noise in the routing table.
3. Either way the orchestrator, reviewers, and the task loop are generated in full from day one -
   they do not depend on code existing. Seed `master-plan.md` Phase 1 with the project's first
   real milestones (from specs, or "write specs" itself as TASK-001) so the orchestrator's first
   session-start scan finds work.

Rule of thumb for cluster size: a dev agent should own something a person could describe in one
sentence ("the scoring engine", "the ingestion pipeline"). More than ~5 dev agents at bootstrap
time is a sign of speculative splitting; fewer than 1 per 2-3 FRs on a large product is a sign of
a future grab-bag.

## Growth path - when to split or add an agent

- **Split a dev agent** when its scope spans two domains that change for different reasons, or
  when two missions keep colliding on the same agent. Splitting = new agent file + routing-table
  row + CLAUDE.md roster row + moving module ownership, in one MR.
- **Add `db-engineer`/`db-seeder`** when migrations need operational care (baselines, tuning) or
  demo/dev data becomes a recurring need.
- **Add the planning pair** at the first contested technical decision (the trigger is "we argued
  about a library in chat" - that argument should have been a `/brainstorm` -> ADR).
- **Never grow reviewers' tools**: reviewers stay read-only forever; a reviewer that edits code
  has become a dev agent and lost its independence.
- Roster changes are recorded in `docs/context/tool-changelog.md` and the routing table in the
  same change.

## Roster completeness check

Before finishing the bootstrap, verify the formation can actually play the standard feature flow -
every seat filled by exactly one agent:

| Flow step | Seat | Filled by |
|-----------|------|-----------|
| Lock scope + criteria | requirement gate | `spec-guardian` |
| Implement (TDD) | owner | the `<domain>-dev` for that FR |
| Tests | quality | `qa-test` (or the dev agent itself if declined - state so) |
| Review diff | code gate | `code-reviewer` |
| Review secrets/data | security gate | `security-reviewer` |
| Open MR/PR, CI | pipeline | `devops` (or the dev agent on Preset S - state so) |
| Failure diagnosis | root cause | `debugger` (or user - state so) |
| Decide + record decisions | planning | `brainstormer`/`tech-researcher` -> ADR (or user) |
| Route, supervise, record | control | `orchestrator` |

If a seat is intentionally unfilled (declined in intake), the CLAUDE.md flow description must say
who covers it instead - an unnamed seat is how gates get silently skipped.

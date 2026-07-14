# The `.claude/` surface and docs tree (project-bootstrap)

Reference for the `project-bootstrap` skill: what files to scaffold for the standard AI-agent
operating structure, and how they wire together into an ORCHESTRATED system. Every asset has a
bundled template pack under `templates/` - generate from the packs, parameterized by the intake
answers and (brownfield) the codebase-analysis mapping tables. When the user supplies a reference
repository, prefer copying its battle-tested files and adapt; the packs are the fallback and the
completeness checklist either way.

## Table of contents

- [Docs tree](#docs-tree)
- [The `.claude/` folder](#the-claude-folder)
- [Rules to create](#rules-to-create)
- [Agents to create](#agents-to-create)
- [Commands to create](#commands-to-create)
- [Orchestration wiring](#orchestration-wiring)
- [Skills to copy](#skills-to-copy)
- [Root files](#root-files)
- [Skill discovery](#skill-discovery)

## Docs tree

Structure: `templates/docs-tree.md`. Content skeletons for every file (docs/README, master-plan,
pending/README, the four context files, TASK/PRD/ADR templates, architecture skeletons):
`templates/docs-pack.md`. Notes:

- `docs/specs/` belongs to the `spec-builder` skill - never hand-invent the 13 sections; if specs
  do not exist, offer to run spec-builder first (Batch A question 3).
- Brownfield: `system-overview.md` draws the ACTUAL architecture found in analysis; big decisions
  already baked into the code are recorded retroactively as Accepted ADRs so the protect-adr hook
  guards them; master-plan Phase 1 is seeded with the migration backlog.

## The `.claude/` folder

Structure: `templates/claude-tree.md`. Assets: `settings.json` from
`templates/settings.json.template` (adapt allow/deny to the ACTUAL stack commands), `rules/` from
`templates/rules-pack.md`, `agents/` from `templates/agents-pack.md`, `commands/` from
`templates/commands-pack.md`, `hooks/` from `templates/hooks-pack.md`, plus `skills/` (see skill
discovery) and gitignored `state/history/`.

## Rules to create

From `templates/rules-pack.md`: always `00-overview.md`, `tech-stack.md`, `coding-standards.md`,
`testing.md`, `git-workflow.md` (platform-specific per Batch C), `conventional-commits.md`
(project scope list from the module mapping), `agent-guardrails.md` (NEVER skip - see
`reference/guardrails-hooks.md`), `security-privacy.md` (strictness per Batch D data-sensitivity),
`docs-workflow.md`, `task-tracking.md`. Conditional: `data-model.md` (DB), `frontend.md` +
`design-system.md` (UI - enumerate the ACTUAL primitives; brand assets from Batch F go into
`frontend.md` as a MANDATORY section), `human-in-the-loop.md` (AI product), one rule per infra
target, one language rule when user-facing strings are in an accented language.

Brownfield rule-writing discipline: state conventions the code OBSERVES; where the code deviates
from the target, write the target and register the cleanup as a backlog task - a rule that
pretends the code already complies is worse than no rule.

## Agents to create

The formation is decided FIRST via `reference/team-roster.md` (Tier 0 core always; preset S/M/L by
project type; brownfield dev agents from the module mapping, greenfield from FR clustering or a
single `app-dev`). Then generate each selected agent from `templates/agents-pack.md` - the
orchestrator sample there is complete (full 6-phase lifecycle + routing-table pattern; it links to
`reference/task-control.md` for the canonical loop, never re-describes it). Reviewer trio
(`code-reviewer`, `security-reviewer`, `spec-guardian`) is read-only. Conditional agents
(`frontend-ui-dev`, `qa-test`, the DB trio with its division of labor, `devops`, the planning
pair, `history-tracker`) follow the roster tiers and intake batches D/E.

Every agent body must name: the rules it obeys, the docs it reads, its write scope, the skills it
loads. Reviewers get NO Edit/Write tools. Every agent's frontmatter also carries an explicit
`model:` (`opus`/`sonnet`/`haiku`) per `reference/model-allocation.md` - never leave it unset, or
the agent silently inherits the caller's (usually most expensive) model.

## Commands to create

From `templates/commands-pack.md`. Core: `/implement-fr`, `/review-mr` or `/review-pr` (platform
naming, gated by `/secret-scan`), `/secret-scan`, `/new-task`, `/task-resume`, `/brainstorm`,
`/new-adr`, `/new-spec-section`, `/sync-context`. Conditional: `/test` (qa-test), `/db-migration`
+ `/seed-db` (DB), `/deploy-<hosting>` (GATED), `/scaffold-feature`, plus domain commands per
feature area.

## Orchestration wiring

The generated base must OPERATE under orchestration, not merely contain the files. Verify these
connections exist (they are the difference between a folder of markdown and a working system):

1. **Routing closure**: the orchestrator routing table lists every agent with its write scope;
   every module from the analysis has exactly one owning agent; no orphan agents, no orphan
   modules.
2. **Entry points declared**: CLAUDE.md names the orchestrator as the default entry point for
   multi-step work and states the standard feature flow (spec-guardian -> specialist TDD ->
   qa-test -> reviewers -> {{PR/MR}}); `/implement-fr` encodes the same flow.
3. **State loop closed**: orchestrator session-start scan (grep Active/Blocked) -> task files ->
   `/task-resume` -> session logs -> dual-location status sync -> done/. The canonical procedure
   lives in `reference/task-control.md`; `orchestrator.md` and `rules/task-tracking.md` LINK to it.
4. **Gates in the path**: quality gates (test -> review -> secret-scan) are steps inside
   `/implement-fr` and the orchestrator's supervise phase - not optional side commands.
5. **Work to route**: master-plan has at least one registered task (brownfield: the migration
   backlog) so the first orchestrator session has real state to restore.

Smoke-test after generation: run the SKILL.md step-7 loop (create task, register, log, resume).

## Skills to copy

From the reference repo or marketplace when applicable: `db-seed` (adapt the entity list to the
project's ERD), `tdd`, framework best-practices, `webapp-testing`. Brand assets from Batch F go
into `rules/frontend.md`, not into a skill.

## Root files

From `templates/root-files-pack.md`: `CLAUDE.md` (under ~80 lines; overview, principles, docs map,
task-tracking pointer, agent roster + flow, commands, git identity, hooks), `AGENTS.md` (mirror
for other tools + the enforcement-gap warning: no settings/hooks layers there, so behavioral rules
and review gates are mandatory self-compliance), `README.md` (human-facing: what/why, architecture,
layout, how AI agents operate the repo, getting started, contributing). English only.

## Skill discovery

Search for skills matching the project's stack and install the relevant ones into
`.claude/skills/` (use the `find-skills` skill or the skills marketplace). Typical picks: tdd,
framework best-practices, DB best-practices, webapp-testing, frontend-design. Record installs in
`docs/context/tool-changelog.md`.

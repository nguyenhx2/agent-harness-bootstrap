---
name: project-bootstrap
description: Bootstraps or standardizes the full AI-agent workspace for any project - analyzes the existing source first, then generates/reconciles the complete .claude folder (agents incl. orchestrator, rules, commands, hooks, skills, settings.json), the standardized docs tree (specs/requirements/architecture/tasks/context/templates), CLAUDE.md + AGENTS.md + README.md, and relevant skills - so the repo runs under orchestrator-driven task control. Use when the user asks to "set up base", "thiet lap base coding", "chuan hoa claude folder", "chuan hoa source thanh claude ready", "khoi tao workspace cho AI agents", or starts/adopts a project that should follow the standard structure.
---

# Project bootstrap

Sets up the standard AI-agent operating structure for a project, Claude Code first (other tools via
AGENTS.md). The skill is **self-contained**: every asset it generates has a bundled template under
`templates/` (settings.json, hooks, agents, rules, commands, root files, docs). A user-supplied
reference repository is OPTIONAL enrichment - when one is given, prefer copying its battle-tested
files and adapt; when none is given, generate everything from the bundled packs.

This SKILL.md is the navigation layer. Detailed procedures live in `reference/`; copyable assets
live in `templates/`. Read each file when you reach that step - do not improvise a step that has a
reference doc.

## Three modes - decide first

| Mode | When | What changes |
|------|------|--------------|
| **Greenfield** | Empty or near-empty repo | Generate the full structure from intake answers |
| **Brownfield (standardize existing source)** | Repo already has code, and possibly a partial `.claude`/docs | Run codebase analysis FIRST (`reference/codebase-analysis.md`), derive most intake answers from evidence, then RECONCILE - never clobber - the existing setup into the standard shape |
| **Audit / assessment** | The repo(s) are ANALYSED but never MODIFIED by agents - e.g. a read-only security/performance audit, possibly over multiple product repos under one workspace root | Build a CONTROL PLANE (root `.claude` + `docs/`) beside the untouched source: agents are read-only on product code (enforced, not just stated), findings are registered as tasks, and the USER applies fixes. Gates of the mode: verify the standards baseline (WebSearch, dated) BEFORE any finding is written, and read-only enforcement tested. Follow [reference/audit-mode.md](reference/audit-mode.md); copyable assets in [templates/audit-pack.md](templates/audit-pack.md) |

Mode selection rule: if the repo(s) will be analysed but never modified by the agents (the user -
not an agent - applies any fixes), you are in AUDIT mode, even though plenty of source code
exists. Otherwise, if the repo contains any source code, you are in brownfield mode. The defining
property of brownfield mode: **the questionnaire confirms findings instead of asking from zero**,
and every generated agent/rule/command is grounded in what the code actually contains (real module
paths, real frameworks, real scripts, real risky operations). Audit mode inherits that grounding
discipline - analysis runs on every repo - but flips the write assumption: dev agents become
auditors, and guardrails must make product source technically read-only.

## Procedure

In AUDIT mode, follow the same numbered steps but apply the substitutions defined in
[reference/audit-mode.md](reference/audit-mode.md): analysis runs per repo, the roster becomes
auditors + reviewers (no implementer), the guardrails add read-only enforcement on product source,
and findings feed the task loop. The docs tree and the task-control loop are unchanged. This mode
BUILDS the audit scaffolding only - RUNNING the audit afterwards is the job of the sibling
`security-audit` skill (see "Division of labor" in `reference/audit-mode.md`).

0. **Codebase analysis (brownfield: MANDATORY, greenfield: skip)** - follow
   [reference/codebase-analysis.md](reference/codebase-analysis.md). Produce the Inventory Report
   (stack, modules, conventions, risky operations, existing `.claude`/docs assets, gaps vs the
   standard) and present it to the user before anything else. The report's mapping tables
   (modules -> dev agents, conventions -> rules, risky ops -> deny/hooks) directly parameterize
   steps 2-4.
1. **Run the intake questionnaire** (MANDATORY, thoroughness over speed) - see
   [reference/intake-questionnaire.md](reference/intake-questionnaire.md). In brownfield mode,
   pre-fill every answer the analysis produced and only ASK about gaps and choices the code cannot
   decide (docs language, commit identity, data sensitivity, gated actions). Ask in ordered batches
   (max 4 per call). Then echo back a one-screen setup plan (what will be created, what will be
   kept, what will be modified) and get confirmation before generating anything.
2. **Pick the team roster ("doi hinh")** - see
   [reference/team-roster.md](reference/team-roster.md): Tier 0 core (orchestrator, reviewer trio,
   at least one dev agent) is unconditional; choose the preset (S/M/L) matching the project type;
   brownfield derives dev agents from the module mapping, greenfield from FR clustering (or a
   single `app-dev` when no specs exist yet). Then **scaffold the `.claude/` surface and docs
   tree** - see [reference/claude-surface.md](reference/claude-surface.md). Directory scaffolds:
   [templates/claude-tree.md](templates/claude-tree.md) and
   [templates/docs-tree.md](templates/docs-tree.md). Asset packs:
   - `templates/settings.json.template` - permissions allow/deny + hook registration.
   - `templates/agents-pack.md` - complete orchestrator sample, dev-agent pattern, reviewers,
     qa-test, DB trio, devops, debugger, history-tracker, planning pair, optional `merge-manager`
     (delegated merge authority behind a strict gate). Every generated agent gets an explicit
     `model:` in its frontmatter per [reference/model-allocation.md](reference/model-allocation.md)
     - cheap generation, expensive verification; never leave it unset.
   - `templates/rules-pack.md` - the full rule set skeletons (00-overview first).
   - `templates/commands-pack.md` - the core command set skeletons.
   - `templates/root-files-pack.md` - CLAUDE.md, AGENTS.md, README.md skeletons.
   - `templates/docs-pack.md` - docs/README, master-plan, context files, TASK/PRD/ADR templates.
   - `templates/audit-pack.md` - AUDIT MODE ONLY: `<repo>-auditor`/`sast-runner`/`perf-reviewer`
     bodies, the `protect-repos` hook, `/security-scan` + `/triage-findings` commands, the
     finding-file template, and the read-only-on-source settings.json deny fragment.
   In brownfield mode apply the reconciliation rules from `reference/codebase-analysis.md`
   (keep-adapt-add-flag; never silently delete user content).
3. **Install the guardrails and hooks** (NEVER skip) - see
   [reference/guardrails-hooks.md](reference/guardrails-hooks.md); full scripts in
   [templates/hooks-pack.md](templates/hooks-pack.md) (PowerShell + bash variants, six hooks
   including `agent-history`). Generate the flavor matching the detected dev OS (see "OS-aware
   generation" below). Test each hook with a sample JSON payload before declaring done. Audit mode
   adds a seventh hook, `protect-repos`, and hardens `protect-secrets` (no `.env.example`
   allowlist) - see [reference/audit-mode.md](reference/audit-mode.md).
4. **Generate `.env.example`** - see [reference/env-config.md](reference/env-config.md); scaffold in
   [templates/env-example.template](templates/env-example.template). Brownfield: derive the variable
   list from the actual config reads found during analysis (process.env/os.environ/etc.), never
   from guesswork.
5. **Wire up orchestration and task tracking** - this is what makes the base "run under
   orchestration", not just a folder of files:
   - The orchestrator's routing table lists EVERY generated agent with its module scope (from the
     analysis mapping), and every dev agent names its owning modules, rules, and skills.
   - The canonical analyze/decompose/register/lifecycle loop is
     [reference/task-control.md](reference/task-control.md); `orchestrator.md` and
     `rules/task-tracking.md` LINK to it rather than duplicate it.
   - `docs/tasks/master-plan.md` is created with the index table; in brownfield mode seed it with
     a Phase 1 backlog derived from the analysis gap list (each gap = one registered task), so the
     orchestrator has real work to route on its first session.
   - `CLAUDE.md` names the orchestrator as the default entry point for multi-step work and states
     the standard feature flow (spec check -> specialist TDD -> qa -> reviewers -> MR).
6. **Discover and install relevant skills** - see the "Skill discovery" section in
   [reference/claude-surface.md](reference/claude-surface.md). Record installs in
   `docs/context/tool-changelog.md`.
7. **Verify** - run the quality gate below, then smoke-test the operating loop end-to-end:
   create one real task file from the template, register it in master-plan, append a session-log
   row, and run `/task-resume` on it.

## Common vs project-specific assets (reuse discipline)

The generated base splits into two kinds of assets. Keep the distinction sharp - it is what makes
this skill applicable to ANY project:

**COMMON (copy near-verbatim; only trivial placeholders like branch name or docs paths):** the six
hooks and their registration block; the settings.json deny core (force push, rm -rf, secret-read
globs); rules `agent-guardrails.md`, `task-tracking.md`, `docs-workflow.md`, `human-in-the-loop.md`
and the format/no-AI-attribution parts of `conventional-commits.md`; commands `/new-task`,
`/task-resume`, `/secret-scan`, `/sync-context`, `/new-adr`; the TASK/PRD/ADR templates and the
docs tree shape; the orchestrator lifecycle (sections 1-6). These encode process, not domain - do
NOT inject project specifics into them, so they stay diff-comparable across projects and can be
upgraded by re-running the bootstrap.

**PROJECT-SPECIFIC (parameterized from intake + analysis):** `tech-stack.md`, `coding-standards.md`
conventions, `data-model.md` entities, `frontend.md`/`design-system.md` primitives and brand
assets, `git-workflow.md` platform/identity, the commit scope list, the settings.json allow list
and stack-specific deny rules (DB reset command, deploy command), the orchestrator ROUTING TABLE,
every dev agent's scope, `.env.example` groups, hosting/language rules, domain commands.

When in doubt: if the sentence would be true in a different company's repo, it belongs to a common
asset; if it names a module, provider, or brand, it is project-specific and must come from a
`{{...}}` placeholder, never be invented.

## OS-aware generation (MANDATORY check)

Detect the dev OS BEFORE generating hooks and settings - wrong-flavor hooks fail silently and the
guardrails never fire:

- Detect from the running environment (platform info, shell, path separators; confirm in the setup
  plan echo). Do not assume.
- **Windows** -> PowerShell hooks (`.ps1`), registered as
  `powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/<name>.ps1`. Use
  `-cmatch`/`-cnotmatch` for case-sensitive checks.
- **macOS/Linux** -> bash hooks (`.sh`), registered as `bash .claude/hooks/<name>.sh`; `chmod +x`;
  LF line endings; note the `jq` dependency (or inline a python/node JSON parse if jq is not
  guaranteed).
- **Mixed-OS team**: settings.json is committed and shared, so one flavor will break for part of
  the team. Prefer portable hooks in the project's own runtime (e.g. Node `.mjs` registered as
  `node .claude/hooks/<name>.mjs` for a JS project) - port the pack scripts' logic 1:1; otherwise
  pick the majority OS and document the gap in `hooks/README.md`.
- Scripts and commands referenced in docs (test/lint invocations) must match the OS shell too.

## Task tracking in markdown (context-compaction survival)

Task state lives in committed markdown files under `docs/tasks/` (no database): `master-plan.md`
(phased plan + index table of every task: owner agent, deps, priority, phase, status) + one file per
task `active/TASK-NNN-<slug>.md` from the TASK template (moved to `done/` when finished, or to
`pending/` when intentionally deferred), holding goal, scope, orchestration notes, checklist,
acceptance criteria, and an AI session log table. The full analyze/create/control loop - including
crash recovery and single-instance discipline after abnormal termination (a silently stalled
instance counts as crashed and is resumed from file state) - is documented in
`reference/task-control.md`. Scaffold:

- Rule `task-tracking.md`: implementation agents create/update the task file at task start, append
  concise session-log rows (date, agent, what was done, result) and decision notes during work, and
  re-read master-plan + the task file before continuing any task in a new or compacted session - the
  task files, not conversation memory, are the source of truth. Files are committed: no secrets, no
  real PII, no full prompt dumps.
- Command `/task-resume`: grep `status: Active|Blocked` in `active/` to list unfinished tasks,
  rebuild context from master-plan + task file, verify the working tree before continuing.
- Orchestrator step: at session start, scan `active/` frontmatter for unfinished tasks and route
  them back to the owning agent.
- Status transitions update both the task file frontmatter and the master-plan Status column; on
  Done fill the results section and move the file to `done/`.

## Installation levels

- Project level: everything above, committed to the repo.
- Global level (`~/.claude/skills/`): install `spec-builder` and `project-bootstrap` themselves so
  any future project can bootstrap; never put project-specific rules/agents globally.

## Quality gate before finishing

Structure completeness:

- [ ] `.claude/` contains ALL of: `settings.json`, `rules/` (00-overview first), `agents/`,
      `commands/`, `hooks/` (+README), `skills/`; `docs/` contains ALL of: `README.md`, `specs/`,
      `requirements/`, `architecture/` (system-overview + decisions/ + api-contracts/), `tasks/`
      (master-plan + active/ + pending/ + done/), `context/` (glossary, business-rules,
      known-issues, tool-changelog), `templates/` (TASK/PRD/ADR).
- [ ] Every path referenced by agents/commands/rules exists; no references to agents that were not
      created; orchestrator routing table covers every agent (no orphan agents).
- [ ] Roster completeness: every seat of the standard feature flow is filled by exactly one agent
      per the check table in `reference/team-roster.md`; intentionally unfilled seats are named in
      CLAUDE.md (who covers them instead).
- [ ] Genericity: common assets contain no project/domain/brand specifics (they must be reusable
      verbatim in another repo); every project specific came from a `{{...}}` placeholder or an
      analysis finding, never invented.
- [ ] OS check done: hook flavor + settings.json registration lines match the detected dev OS;
      hooks actually execute on this machine (the payload test ran here, not hypothetically).
- [ ] Every generated agent's frontmatter carries an explicit `model:` (never unset), assigned per
      [reference/model-allocation.md](reference/model-allocation.md): `opus` for
      planning/root-cause/review-gate seats, `sonnet` for implementation against a settled spec,
      `haiku` for mechanical/low-judgment work.

Grounding (brownfield):

- [ ] Inventory Report was produced and confirmed; every dev agent's scope names real module paths;
      every rule's conventions match observed code (or the deviation is flagged as a registered
      task, not silently "fixed").
- [ ] Pre-existing `.claude`/docs content was reconciled per keep-adapt-add-flag; nothing the user
      wrote was deleted without explicit approval.
- [ ] master-plan.md carries the migration backlog (one task per gap) so orchestration has work.

Process:

- [ ] Every questionnaire batch was asked or explicitly inferred with stated defaults, and the
      setup plan was confirmed by the user before generation.
- [ ] `CLAUDE.md`, `AGENTS.md`, `README.md`, `.claude/rules/00-overview.md` agree with each other
      (same principles, same paths); all agent-facing files are in English.
- [ ] Task tracking smoke-tested end-to-end (create task file, register in master-plan, append
      session-log row, `/task-resume` it).
- [ ] Platform-specific bits (CLI, PR/MR wording, CI file, default branch) match the git platform
      answer everywhere, including command NAMES.

Safety:

- [ ] All four guardrail layers present: settings.json deny rules, hooks, `agent-guardrails.md`,
      review commands (`/review-mr` or `/review-pr` gated by `/secret-scan`).
- [ ] settings.json denies destructive ops (force push, rm -rf, direct prod deploy, secret reads,
      DB reset) adapted to the ACTUAL stack found in analysis.
- [ ] Hooks tested with sample JSON payloads (block case exits 2, pass case exits 0).
- [ ] `.env.example` exists, covers every integration in the tech-stack rule (and nothing more),
      placeholders only, every var commented with its consumer and per-environment source.
- [ ] AUDIT MODE ONLY: the standards table carries a `verified:` date from THIS bootstrap run
      (WebSearch-confirmed versions, not memory); every requirement ID cites its standard version;
      `protect-repos` tested on BOTH sides - an in-repo write payload exits 2, AND a write to
      `docs/findings/<lowercased-repo-name>/x.md` exits 0 (case-insensitive path matching is the
      trap; see `reference/audit-mode.md`).

Handoff:

- [ ] Summary to user: what was created/kept/changed, agents available, the orchestration flow in
      one diagram, and the suggested next step (run `spec-builder` if no specs, else
      `/task-resume` or `/implement-fr`).

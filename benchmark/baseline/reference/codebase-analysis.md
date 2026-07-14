# Codebase analysis - standardizing an existing source (project-bootstrap)

Reference for the `project-bootstrap` skill, brownfield mode. Goal: analyze the current source and
produce an evidence-based **Inventory Report** whose mapping tables parameterize the entire
bootstrap - so the generated base describes THIS codebase, not a generic project, and the repo ends
up operating under orchestrator-driven task control.

Run this BEFORE the intake questionnaire. Never generate a single file before the report is
confirmed by the user.

## Table of contents

- [Phase A - Discover](#phase-a---discover)
- [Phase B - Inventory Report](#phase-b---inventory-report)
- [Phase C - Mapping tables](#phase-c---mapping-tables)
- [Phase D - Gap analysis vs the standard base](#phase-d---gap-analysis-vs-the-standard-base)
- [Reconciliation rules (keep-adapt-add-flag)](#reconciliation-rules-keep-adapt-add-flag)
- [Migration backlog](#migration-backlog)

## Phase A - Discover

Sweep the repo read-only (Glob/Grep/Read; dispatch an Explore agent for large repos). Collect
evidence for each dimension - record file paths as proof, never guess:

1. **Stack**: manifest files (`package.json`, `pyproject.toml`, `go.mod`, `*.csproj`, `Gemfile`,
   `pom.xml`/`build.gradle`, `composer.json`) -> language, framework, test runner, lint/format
   tools, pinned versions. Lockfile -> package manager.
2. **Layout and modules**: top-level and second-level source dirs (`src/*`, `app/*`, `lib/*`,
   `packages/*` for monorepos). For each module: purpose (from names, index files, README
   fragments), rough size (file count), and inbound/outbound dependencies where cheap to see.
3. **Data layer**: ORM/schema files (`prisma/schema.prisma`, `models/`, `migrations/`,
   `alembic/`, `*.sql`), DB engine from connection strings in config *names* (never read `.env*`
   values - use `.env.example`, `docker-compose.yml`, CI files). Entities list from the schema.
4. **Async/infra**: queue/worker code, docker/compose files, IaC, hosting config
   (`railway.json`, `vercel.json`, `fly.toml`, k8s manifests), CI pipelines
   (`.gitlab-ci.yml`, `.github/workflows/`), Dockerfiles.
5. **External integrations**: SDK imports and HTTP clients (LLM gateways, storage, auth/SSO,
   email, payment, search). For each: which module calls it, is it wrapped or scattered.
6. **Configuration surface**: grep `process.env.` / `os.environ` / `getenv` / framework config ->
   the real variable list for `.env.example`. Compare with any existing `.env.example`.
7. **Conventions in force** (observed, not aspirational): naming (camelCase/snake_case), TS
   strictness, error-handling style, UI primitives/design tokens (a `components/ui/` dir? a token
   file?), i18n and language of user-facing strings, comment language, test layout and coverage
   config, commit-subject style from `git log --format=%s -40`.
8. **Risky operations available in the repo**: scripts or docs mentioning force push, db reset/
   push, mass delete, prod deploy commands, secret files present. These drive settings.json deny
   rules and hooks.
9. **Existing agent surface**: `.claude/` (settings, rules, agents, commands, hooks, skills),
   `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.github/copilot-instructions.md`, docs tree. Note
   what exists, what is stale (references to files that no longer exist), what conflicts with the
   standard.
10. **Git reality**: default branch, branch naming in `git branch -a`, hosting platform from
    `git remote -v` (cloud vs self-hosted from the hostname), existing PR/MR conventions.

## Phase B - Inventory Report

Present ONE report to the user (this is the deliverable of the analysis; keep it to ~2 screens):

```markdown
# Inventory Report - <repo>

## Stack (evidence-based)
| Dimension | Finding | Evidence |
|-----------|---------|----------|
| Language/framework | ... | package.json:... |
| DB/ORM | ... | prisma/schema.prisma |
| Queue/worker | ... | src/worker/ |
| Hosting/CI | ... | .gitlab-ci.yml |
| Test | ... | vitest.config.ts |

## Modules
| Module | Path | Purpose | Size | Proposed owner agent |
|--------|------|---------|------|----------------------|

## Integrations
| Provider | Wrapped in | Called from |
|----------|-----------|-------------|

## Conventions observed
- ... (each with a file example)

## Risky operations found
- ... (each -> proposed deny rule or hook)

## Existing agent surface
- what exists / stale / conflicting

## Gaps vs standard base
- ... (numbered; becomes the migration backlog)
```

Get explicit confirmation (or corrections) before moving on. Corrections override findings.

**The Inventory Report is a hypothesis, not ground truth.** It is evidence-seeded but produced by
a fast survey; the deep work that follows (implementation, review, or an audit) is expected to
VALIDATE it - and sometimes to invert it: a control the report assumed present may prove entirely
absent, size or performance estimates may be off by 2x, a known issue may escalate (e.g. P2 -> P0)
once its real blast radius is seen. Contradicting the report later is a SUCCESS of the process,
not a failure. Let evidence win: update the master-plan, the severity, and the report itself when
findings overturn an assumption - never argue the evidence back into agreement with the report.

## Phase C - Mapping tables

Turn confirmed findings into generation parameters:

### Modules -> dev agents

One dev agent per cohesive feature domain, NOT per directory. Merge tiny related modules; split a
grab-bag `lib/` by domain. Every agent gets: the module paths it owns (write scope), the rules it
must obey, the docs it reads, the skills to load. Cross-cutting layers that everything calls (an
LLM client, an integrations dir) get their own agent so ownership is unambiguous. UI gets ONE
frontend agent regardless of page count. The result feeds `agents-pack.md` skeletons and the
orchestrator routing table - the routing table must cover every agent and every module (no orphan
modules, no orphan agents).

### Conventions -> rules

Write `rules/coding-standards.md`, `frontend.md`/`design-system.md` (if UI), `data-model.md`
(if DB), `testing.md` from the OBSERVED conventions. Where observation contradicts good practice
(e.g. no strict mode, hardcoded colors), do NOT write the rule as if the code already complies:
write the target rule and register the cleanup as a migration-backlog task. Where the codebase has
a real design system (ui primitives + tokens), enumerate the actual primitives in the rule and make
reviewer enforcement explicit (block raw elements/hardcoded values).

### Risky ops -> gates and hooks

Every risky operation found in Phase A maps to: a settings.json deny rule (stack-specific: e.g.
`prisma migrate reset` vs `rails db:reset` vs `alembic downgrade`), a hook check
(`protect-secrets` command patterns), or a gated command (`/deploy-*`). Secrets files present in
the repo extend the Read-deny globs.

### Integrations -> env + mocking policy

Each integration produces: a commented group in `.env.example`, a "mock in tests" line in
`testing.md`, and (if it handles sensitive data) a paragraph in `security-privacy.md`.

## Phase D - Gap analysis vs the standard base

Diff the existing surface against the full standard tree (`templates/claude-tree.md` +
`templates/docs-tree.md`). Classify every item:

| Class | Meaning | Action |
|-------|---------|--------|
| MISSING | Standard asset absent | Generate from the template pack |
| PRESENT-OK | Exists and matches the standard's intent | Keep as-is (maybe link it) |
| PRESENT-DRIFT | Exists but stale/incomplete/conflicting | Adapt in place, preserving user content |
| EXTRA | Exists but not in the standard | Keep and register in 00-overview/CLAUDE.md maps (the standard is a floor, not a ceiling) |

## Reconciliation rules (keep-adapt-add-flag)

Brownfield generation NEVER clobbers:

1. **Keep**: never delete or rewrite-from-scratch a file the user authored. Existing rules/agents
   with real content are adapted, not replaced.
2. **Adapt**: when a standard file exists with drift, edit minimally - add the missing sections,
   fix broken paths, align frontmatter - and say what changed.
3. **Add**: generate missing assets from the packs, parameterized by the mapping tables.
4. **Flag**: genuine conflicts (e.g. an existing hook that contradicts the standard guardrails, a
   CLAUDE.md that permits force-push) are surfaced to the user as decisions, never silently
   resolved either way.

Also: do not reformat or "fix" product source code during bootstrap. Convention violations found in
`src/` become backlog tasks; the bootstrap only touches the agent surface (`.claude/`, `docs/`,
root instruction files, `.env.example`, CI stub).

## Migration backlog

Every Phase D gap and every convention deviation becomes a registered task:

- Create `docs/tasks/master-plan.md` with a "Phase 1 - standardization" section.
- One `TASK-NNN` row per gap (owner = the agent that owns that concern; priority P0 for guardrail
  gaps, P1 for convention drift, P2 for nice-to-haves).
- Create task files for the P0 items immediately (from `docs/templates/TASK.md.template`).

This is what makes the result "operate under orchestration" on day one: the orchestrator's
session-start scan finds real Active tasks with owners, instead of an empty tracker.

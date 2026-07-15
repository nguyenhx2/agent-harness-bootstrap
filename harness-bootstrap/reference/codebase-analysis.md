# Codebase analysis - deriving the harness from the source that exists

Brownfield and audit mode. Analyze the current source and produce an evidence-based **Inventory
Report** whose mapping tables parameterize the whole bootstrap - so the generated harness describes
THIS codebase, not a generic project.

Run this BEFORE the intake questionnaire. Never generate a file before the report is confirmed.

## Phase A - discover

Sweep the repo read-only (Glob/Grep/Read; dispatch an `Explore` agent on a large tree). Record a file
path as proof for every finding - never guess:

1. **Stack** - manifests (`package.json`, `pyproject.toml`, `go.mod`, `*.csproj`, `pom.xml`) →
   language, framework, test runner, lint/format tools, pinned versions. Lockfile → package manager.
   The scripts block → the real test/lint/build/deploy commands.
2. **Layout and modules** - source dirs one and two levels deep (`src/*`, `app/*`, `lib/*`,
   `packages/*`). Per module: purpose, rough size, and the dependencies visible cheaply.
3. **Data layer** - ORM and schema files (`schema.prisma`, `models/`, `migrations/`, `*.sql`); the DB
   engine from connection-string *names* in `.env.example`, compose, or CI - never read `.env*`
   values. Entities from the schema.
4. **Async and infra** - queue/worker code, docker/compose, IaC, hosting config, CI pipelines.
5. **External integrations** - SDK imports and HTTP clients (LLM gateways, storage, auth/SSO, email,
   payment, search). For each: which module calls it, and whether it is wrapped or scattered.
6. **Configuration surface** - grep `process.env.` / `os.environ` / `getenv` → the real variable list
   for `.env.example`. Diff against any existing one.
7. **Conventions in force** (observed, not aspirational) - naming, type strictness, error handling, UI
   primitives and design tokens (is there a `components/ui/`? a token file?), i18n and the language of
   user-facing strings, comment language, test layout, commit-subject style from
   `git log --format=%s -40`.
8. **Risky operations present** - scripts or docs mentioning force push, DB reset, mass delete, prod
   deploy; secret files on disk. These drive the deny rules and the hooks.
9. **Existing agent surface** - `.claude/`, `CLAUDE.md`, `AGENTS.md`, other tools' instruction files,
   the docs tree. What exists, what is stale (references to files that no longer exist), what conflicts
   with the standard.
10. **Git reality** - default branch, branch naming, hosting platform from `git remote -v` (cloud vs
    self-hosted, from the hostname), existing PR/MR conventions.

## Phase B - the Inventory Report

Present ONE report, about two screens:

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

## Flags and globs (feeds vars.json)
- flags: ...
- {{SOURCE_GLOBS}} / {{UI_GLOBS}} / {{DB_GLOBS}} / {{TEST_GLOBS}}: ...

## Gaps vs standard
- ... (numbered; becomes the migration backlog)
```

Get explicit confirmation or corrections before moving on. Corrections override findings.

**The report is a hypothesis, not ground truth.** It is evidence-seeded but produced by a fast
survey; the deep work that follows is expected to VALIDATE it and sometimes to invert it - a control
assumed present may prove entirely absent, a severity may escalate once its real blast radius is
seen. Contradicting the report later is a success of the process. Let evidence win: update the
master-plan, the severity, and the report itself, and never argue the evidence back into agreement.

## Phase C - flags and globs

The analysis emits two things the scaffolder cannot infer and the user should not have to type. Both
are load-bearing: **path-scoped rules are the harness's main recurring token saving**
([`cost-model.md`](cost-model.md)), and a rule scoped to a path that does not exist never loads at
all - a silently dead guardrail.

**Flags** - set from evidence, confirmed at intake:

| Flag | Set when the analysis finds |
|---|---|
| `ui` | A rendering layer: components, pages/routes, templates, a design-token or CSS-framework config |
| `db` | A schema, an ORM, or migrations |
| `ai` | An LLM/model provider SDK whose output reaches users or drives a decision |
| `audit` | Set by mode, not by evidence - agents will never write to the source |
| `windows` / `posix` | The dev OS (detected, then confirmed) |

**Glob sets** - derived from the ACTUAL tree, never from a framework's idealized layout. Verify each
matches at least one real file before writing it into `vars.json`; a glob that matches nothing is a
bug the scaffolder cannot catch for you.

| Var | Scopes the rule | Typical shape (confirm against the tree) |
|---|---|---|
| `{{SOURCE_GLOBS}}` | `coding-standards`, `code-quality`, `performance` | `src/**/*.{ts,tsx}` - every module path from A.2 |
| `{{UI_GLOBS}}` | `frontend` (flag `ui`) | `src/components/**`, `src/app/**/*.tsx` |
| `{{DB_GLOBS}}` | `data-model` (flag `db`) | `prisma/**`, `src/db/**`, `**/migrations/**` |
| `{{TEST_GLOBS}}` | `testing` | `**/*.{test,spec}.*`, `tests/**`, `e2e/**` |

A monorepo takes the union across packages (`packages/*/src/**`), not a per-package rule set. Where the
code has no separation - one flat directory - say so and scope to the directory rather than inventing a
structure the code does not have.

## Phase D - mapping tables

**Modules → dev agents.** One dev agent per cohesive feature domain, NOT per directory. Merge tiny
related modules; split a grab-bag `lib/` by domain. A cross-cutting layer that everything calls (an LLM
client, an integrations dir) gets its own owner, so ownership is unambiguous. UI gets ONE frontend agent
regardless of page count. Feeds `{{MODULE_PATHS}}`, `{{ROUTING_TABLE}}`, and the roster
([`roster.md`](roster.md)) - the routing table must cover every agent and every module: no orphan
modules, no orphan agents.

**Conventions → rules.** Write `coding-standards`, `frontend`, `data-model`, `testing` from the OBSERVED
conventions. Where observation contradicts good practice (no strict mode, hardcoded colors), do NOT
write the rule as though the code already complied: write the target rule and register the cleanup as a
backlog task. Where a real design system exists, enumerate its actual primitives and make reviewer
enforcement explicit.

**Risky ops → gates and hooks.** Each maps to a settings.json deny rule (stack-specific:
`{{DB_RESET_PATTERN}}` is the real command, never a guess), a hook check, or a gated command. Secret
files found in the repo extend the Read-deny globs.

**Integrations → env and mocking policy.** Each produces a commented group in `.env.example`, a "mock in
tests" line in `testing.md`, and - if it handles sensitive data - a paragraph in `security-privacy.md`.

## Phase E - reconcile against the standard

Diff the existing surface against what `../scripts/scaffold.py` would install. Classify every item;
the class IS the action. Generation never clobbers.

| Class | Meaning | Action |
|---|---|---|
| MISSING | Standard asset absent | **Add** - the scaffolder writes it, parameterized by the mapping tables |
| PRESENT-OK | Exists and matches the standard's intent | **Keep** as-is. The scaffolder reports it as `KEPT` |
| PRESENT-DRIFT | Exists but stale, incomplete, or partly conflicting | **Adapt** in place: add the missing sections, fix broken paths, align frontmatter - minimal edits, preserving user content, and say what changed. This is the scaffolder's `CONFLICT` queue |
| CONFLICT | Contradicts a standard guardrail (a hook that permits force-push, a rule that allows prod writes) | **Flag** to the user as a decision. Never silently resolved either way |
| EXTRA | Exists, not in the standard, not harmful | **Keep and register** in `00-overview.md` / `AGENTS.md`. The standard is a floor, not a ceiling |

Never delete or rewrite-from-scratch a file the user authored. And do not reformat or "fix" product
source during bootstrap: convention violations in `src/` become backlog tasks. The bootstrap touches
only the agent surface - `.claude/`, `docs/`, the root instruction files, `.env.example`, the CI stub.

## Phase F - migration backlog

Every gap and every convention deviation becomes a registered task, so orchestration has real work on
day one instead of an empty board:

- `docs/tasks/master-plan.md` gets a "Phase 1 - standardization" section.
- One `TASK-NNN` row per gap. Owner = the agent that owns that concern. P0 for guardrail gaps, P1 for
  convention drift, P2 for nice-to-haves.
- Create the task files for the P0 items immediately, from `docs/templates/TASK.md`. They
  start at status `Planned` - see [`task-control.md`](task-control.md).

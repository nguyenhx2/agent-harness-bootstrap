# Intake — the questions the code cannot answer

The questionnaire is mandatory. Thoroughness beats speed: a wrong answer here is baked into every
generated file. Ask with `AskUserQuestion` in **ordered batches, max 4 questions per call**. Never
assume an answer silently — if the user skips one, state the default you will use and why.

After the questionnaire, echo back a **one-screen setup plan** — what will be created, kept, and
modified, plus the roster with each agent's model and effort — and get confirmation before writing
anything.

**Brownfield and audit: analysis first, questions second.** Run
[`codebase-analysis.md`](codebase-analysis.md) BEFORE this questionnaire. It answers most of Batch B
(stack, DB, queue, integrations, environments) and parts of Batch C (platform, default branch,
observed commit style) from evidence. Present each finding as the default and ask only for
confirmation or correction — do not re-ask from zero. Always still ASK what code cannot decide: docs
language, whether specs exist, commit identity, data sensitivity, agent/seed acceptance, branding,
and the effort profile.

## Batch A — project identity

1. Project name, domain, one-line purpose.
2. **Documentation language** for `docs/` content (Vietnamese / Japanese / English / other).
   Regardless of the answer, ALL agent-facing files (`CLAUDE.md`, `AGENTS.md`, `.claude/*`) are
   English; codes, enums, and filenames are always English.
3. Do specs already exist? If not, offer to run the `spec-builder` skill first — the rest of the
   bootstrap is better with FRs in hand.

## Batch B — tech stack

4. Language / framework (or "TBD via ADR" placeholders).
5. **Database + ORM** (e.g. PostgreSQL + Prisma / MySQL / MongoDB / none). Drives the `db` flag,
   `rules/data-model.md`, `/db-migration`, and the DB agents in Batch E.
6. Async/queue layer, external providers (LLM gateway? OCR? storage?), hosting target. An LLM
   provider whose output reaches users sets the `ai` flag.
7. **Environments and configuration** — which environments exist (local / dev / staging /
   production), where secrets live per environment (`.env.local` for dev; platform variables for
   prod), and any auth/SSO providers. Drives `.env.example`.
8. **Dev OS** — AUTO-DETECT from the running environment (platform, shell, path separators) and ask
   the user to confirm rather than asking cold; also ask whether the team is mixed-OS. Sets the
   `windows` / `posix` flag, which gates the hook flavor and the settings registration lines. Get it
   wrong and the guardrails never fire, silently.

## Batch C — git and CI

9. **Git hosting platform** — GitHub / GitLab, **cloud or self-hosted (ask which!)** / Bitbucket /
   none yet. Drives the CLI (`gh` / `glab`), PR-vs-MR terminology everywhere including command NAMES
   (`/review-mr` vs `/review-pr`), and the CI file. For self-hosted GitLab also capture the instance
   hostname (`glab auth login --hostname <host>`) and that CI secrets are masked + protected
   variables.
10. **Commit identity** — the exact name/email registered on THAT platform or instance. A wrong email
    means misattributed commits.
11. Default branch name and branch naming convention (default: `main`, `feat/fix/chore/...`). Feeds
    the `guard-main-commit` hook.
12. **Commit message convention** — Conventional Commits is the default. Confirm the type list
    (default: feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert) and define the
    PROJECT-SPECIFIC scope list from the feature areas in Batch A/B: one scope per module or FR area,
    plus `specs`, `agents`, `infra`. Subject limit 72 chars, imperative lowercase.

## Batch D — quality and safety

13. **Test agent** — a dedicated `qa-test` agent (unit + e2e)? Which frameworks (default Vitest +
    Playwright; pytest etc. per stack), and the test/lint/build commands as actually run. If declined,
    skip the agent and `/test` but keep `rules/testing.md`.
14. **Data sensitivity** — does the system handle PII or regulated data? Drives how strict
    `security-privacy.md`, the `/secret-scan` PII patterns, and the synthetic-data rule must be.
15. Is it an AI product (LLM-generated output shown to users)? If yes, set the `ai` flag: the
    human-in-the-loop and prompt-injection guardrails come with it.
16. **Effort profile** — how should the roster be tuned for cost vs depth? One question, three
    answers:
    - **Default** (recommended) — the per-agent allocation in [`roster.md`](roster.md) as written.
    - **Economy** — step the non-gate seats down one effort level and keep mechanical seats at
      `haiku`+`low`. Never steps down the review, debug, or orchestration gates.
    - **Thorough** — raise the dev seats to `xhigh` for a known-hard codebase; the gates stay at
      their table values.

    Do not restate the allocation here — [`cost-model.md`](cost-model.md) explains why each seat sits
    where it does, and the chosen profile is recorded in `docs/context/tool-changelog.md`.

## Batch E — database operations and seed data

Ask only if Batch B has a DB.

17. Which DB agents to create: `data-modeler` (schema design — recommended whenever there is a
    schema), `db-engineer` (apply/troubleshoot migrations, query and index tuning, local docker env),
    `db-seeder` + `/seed-db` (synthetic data for dev/demo/test).
18. If seeding: which environments are seed targets (local docker / shared dev / staging), the
    default seed scope (entities + volumes), the locale mix for generated data, and confirm the
    synthetic-only policy — real user data never enters seeds, production is never a seed target.
19. The real destructive DB command for this stack (`prisma migrate reset` / `rails db:reset` /
    `alembic downgrade`). It becomes a settings.json deny rule, so a generic guess is worthless.

## Batch F — branding and frontend

Ask only if the project has UI or document output (sets the `ui` flag).

20. Official brand assets (logo files, dark-vs-light variants), fonts, palette. Recorded in
    `rules/frontend.md` as a mandatory section: variant-per-background, self-hosted under
    `public/brand/`, aspect ratio and clear space, alt text.
21. Icon/emoji policy (default: no emoji, SVG icons) and accessibility target (default WCAG 2.1 AA).

## Batch G — audit mode only

Ask only when agents will never modify the source. See [`audit-mode.md`](audit-mode.md).

22. Which repos are in scope and where they sit relative to the workspace root; which standards apply
    per repo; the scanner strategy (host / Docker / config-only — Docker is the default); the
    severity scale; and who applies fixes.

## Intake answers to `vars.json`

The scaffolder (`../scripts/scaffold.py`) consumes `vars.json`. Every question above lands in exactly
one variable or flag; the remaining variables come from the analysis, not from the user.

| Answer | Goes to |
|---|---|
| 1 project name, domain, purpose | `{{PROJECT_NAME}}`, `{{DOMAIN}}`, `{{DOMAIN_DESCRIPTION}}` |
| 2 docs language | no var — sets the language of authored `docs/` prose only |
| 3 specs exist | `{{FR_LIST}}` (from the specs, if any); otherwise the `spec-builder` handoff |
| 4 language/framework | `{{SOURCE_GLOBS}}` shape; `tech-stack.md` body |
| 5 database + ORM | flag `db`, `{{ORM}}`, `{{DB_GLOBS}}` |
| 6 providers / hosting | flag `ai` (if LLM output reaches users), `{{HOSTING}}` |
| 7 environments and secrets | `.env.example` groups (authored, not templated) |
| 8 dev OS | flag `windows` or `posix` → `{{HOOK_RUNNER}}`, `{{HOOK_EXT}}` |
| 9 git platform | `{{PR_OR_MR}}`, `{{CI_PLATFORM}}` |
| 10 commit identity | no var — `git config` on the target repo |
| 11 default branch | `{{DEFAULT_BRANCH}}` |
| 12 commit convention | `{{COMMIT_TYPES}}`, `{{COMMIT_SCOPES}}` |
| 13 test agent + commands | `{{UNIT_FRAMEWORK}}`, `{{E2E_FRAMEWORK}}`, `{{TEST_CMD}}`, `{{LINT_CMD}}`, `{{BUILD_CMD}}`, `{{COVERAGE_TARGET}}`, `{{TEST_GLOBS}}` |
| 14 data sensitivity | `{{PII_OR_DATA}}` |
| 15 AI product | flag `ai` |
| 16 effort profile | no var — the roster allocation; record the choice in `docs/context/tool-changelog.md` |
| 17 DB agents | roster seats (`data-modeler`, `db-engineer`, `db-seeder`) |
| 18 seed policy | `/seed-db` and `db-seeder` scope |
| 19 destructive DB command | `{{DB_RESET_CMD}}`, `{{DB_RESET_PATTERN}}` |
| 20-21 branding, a11y | flag `ui`, `{{UI_GLOBS}}`; `rules/frontend.md` body |
| 22 audit scope | flag `audit`, `{{WORKSPACE_ROOT}}`, `{{REPO_DIR_LIST}}` |
| — deploy command (from analysis or Q6) | `{{DEPLOY_CMD}}` |
| — module paths, routing, dev agents | `{{MODULE_PATHS}}`, `{{ROUTING_TABLE}}`, `{{DEV_AGENT_NAME}}` — from the analysis |

Flags are exactly: `ui`, `db`, `ai`, `audit`, and exactly one of `windows` / `posix`.

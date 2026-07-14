# Intake questionnaire (project-bootstrap)

Reference for the `project-bootstrap` skill. The questionnaire is MANDATORY - thoroughness over
speed. Getting the answers right matters more than starting fast. Use AskUserQuestion in **ordered
batches** (max 4 questions per call); never assume an answer silently - if the user skips one, state
the default you will use and why. After the questionnaire, **echo back a one-screen setup plan and
get confirmation before generating anything**.

**Brownfield mode (repo has code): analysis answers first, questions second.** Run
`reference/codebase-analysis.md` BEFORE this questionnaire; it answers most of Batch B (stack, DB,
queue, integrations, environments) and parts of Batch C (platform, default branch, observed commit
style) from evidence. For every pre-answered item, present the finding as the default and ask only
for confirmation or correction - do not re-ask from zero. Always still ASK the questions the code
cannot decide: docs language (A2), specs existence (A3), commit identity (C8), data sensitivity
(D11), agent/seed acceptance (D10, E13-14), branding (F). Batch letters below stay the same in both
modes.

## Table of contents

- [Batch A - Project identity](#batch-a---project-identity)
- [Batch B - Tech stack](#batch-b---tech-stack)
- [Batch C - Git and CI](#batch-c---git-and-ci)
- [Batch D - Quality and safety](#batch-d---quality-and-safety)
- [Batch E - Database operations and seed data](#batch-e---database-operations-and-seed-data)
- [Batch F - Branding and frontend](#batch-f---branding-and-frontend)

## Batch A - Project identity

1. Project name, domain, one-line purpose.
2. **Documentation language** for `docs/` content (Vietnamese / Japanese / English / other).
   Regardless of the answer, ALL agent-facing files (CLAUDE.md, AGENTS.md, README.md, `.claude/*`)
   are English; codes/enums/filenames always English.
3. Do specs already exist? If not, offer to run the `spec-builder` skill first - the rest of the
   bootstrap is better with FRs in hand.

## Batch B - Tech stack

4. Language/framework (or "TBD via ADR" placeholders).
5. **Database + ORM** (e.g. PostgreSQL + Prisma / MySQL / MongoDB / none). Drives
   `rules/data-model.md`, the `/db-migration` command, and the database agent set in Batch E.
6. Async/queue layer, external providers (LLM gateway? OCR? storage?), hosting target (drives the
   infra rule + deploy gating).
6b. **Environments and configuration** - which environments exist (local / dev / staging /
   production), where secrets live per environment (e.g. `.env.local` for dev, platform variables -
   Railway/GitLab CI/K8s secrets - for prod), and any auth/SSO providers. Drives the `.env.example`
   generated per `reference/env-config.md`.
6c. **Dev OS** - AUTO-DETECT from the running environment (platform, shell, path separators) and
   confirm rather than ask cold; also ask whether the team is mixed-OS. Drives the hook flavor
   (PowerShell vs bash vs portable Node) and the settings.json registration lines - see
   "OS-aware generation" in SKILL.md.

## Batch C - Git and CI

7. **Git hosting platform** - GitHub / GitLab **cloud or self-hosted/self-managed (ask which!)** /
   Bitbucket / none yet. Drives CLI (`gh`/`glab`/`bb`), PR-vs-MR terminology everywhere including
   command NAMES (`/review-mr` vs `/review-pr`), and the CI file (`.github/workflows/ci.yml` /
   `.gitlab-ci.yml` / `bitbucket-pipelines.yml`: lint + unit + e2e + build on every PR/MR; deploy
   job `when: manual`, commented until secrets exist).
   - GitLab self-hosted specifics: instance hostname; document `glab auth login --hostname <host>`;
     CI secrets in GitLab CI/CD variables (masked + protected); standard CI images for self-managed
     runners.
8. **Commit identity** - the exact name/email registered on THAT platform/instance (wrong email =
   misattributed commits).
9. Default branch name and branch naming convention (default: `main`, `feat/fix/chore/...`) - feeds
   the `guard-main-commit` hook.
9b. **Commit message convention** - Conventional Commits is the default (rule
   `conventional-commits.md` + `check-commit-msg` hook). Confirm the type list (default:
   feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert) and define the PROJECT-SPECIFIC
   scope list from the feature areas in Batch A/B (one scope per module/FR area, plus `specs`,
   `agents`, `infra`); subject limit 72 chars, imperative lowercase.

## Batch D - Quality and safety

10. **Test agent** - dedicated `qa-test` agent (unit + e2e)? Which frameworks (default Vitest +
    Playwright; pytest etc. per stack). If declined, skip the agent and `/test` but keep
    `rules/testing.md` minimal.
11. **Data sensitivity** - does the system handle PII/regulated data? Drives how strict
    `security-privacy.md`, `/secret-scan` PII patterns, and the synthetic-data rule must be.
12. Is it an AI product (LLM-generated output shown to users)? If yes, include
    `human-in-the-loop.md` and prompt-injection guardrails.

## Batch E - Database operations and seed data

Ask only if Batch B has a DB.

13. Which DB agents to create: `data-modeler` (schema design - recommended whenever there is a
    schema), `db-engineer` (operations: apply/troubleshoot migrations, query/index tuning,
    integrity, local docker env), `db-seeder` + `db-seed` skill + `/seed-db` command (ready-made
    synthetic data for dev/demo/test).
14. If seeding: which environments exist (local docker / shared dev / staging), default seed scope
    (entities + volumes), locale mix for generated data, and confirm the synthetic-only policy
    (real user/candidate data never enters seeds; production is never a seed target).

## Batch F - Branding and frontend

Ask only if the project has UI/document output.

15. Official brand assets (logo URLs/files, dark-vs-light variants - e.g. a white logo for dark
    backgrounds, a color logo for light backgrounds), fonts, palette. Record in `rules/frontend.md`
    as a MANDATORY section (variant-per-background rule, self-host in `public/brand/`, aspect
    ratio/clear space, alt text).
16. Icon/emoji policy (default: no emoji, SVG icons via heroicons) and accessibility target
    (default WCAG 2.1 AA).

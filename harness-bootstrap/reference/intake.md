# Intake - the questions the code cannot answer

The questionnaire is mandatory. Thoroughness beats speed: a wrong answer here is baked into every
generated file. Ask with `AskUserQuestion` in **ordered batches, max 4 questions per call**. Never
assume an answer silently - if the user skips one, state the default you will use and why.

After the questionnaire, echo back a **one-screen setup plan** - what will be created, kept, and
modified, plus the roster with each agent's model and effort - and get confirmation before writing
anything.

**Brownfield and audit: analysis first, questions second.** Run
[`codebase-analysis.md`](codebase-analysis.md) BEFORE this questionnaire. It answers most of Batch B
(stack, DB, queue, integrations, environments) and parts of Batch C (platform, default branch,
observed commit style) from evidence. Present each finding as the default and ask only for
confirmation or correction - do not re-ask from zero. Always still ASK what code cannot decide: docs
language, whether specs exist, commit identity, data sensitivity, agent/seed acceptance, branding,
and the effort profile.

## Batch A - project identity

1. Project name, domain, one-line purpose.
2. **Documentation language** for `docs/` content (Vietnamese / Japanese / English / other).
   Regardless of the answer, ALL agent-facing files (`CLAUDE.md`, `AGENTS.md`, `.claude/*`) are
   English; codes, enums, and filenames are always English.
3. Do specs already exist? If not, offer to run the `spec-builder` skill first - the rest of the
   bootstrap is better with FRs in hand.

**Target AI tools.** Detect which tools the repo already uses - `.claude/` or `CLAUDE.md` (Claude
Code, always the primary), `.cursor/` or `.cursorrules` (Cursor), `.codex/` (Codex), and a shared
`AGENTS.md` (Cursor and Codex both read it). Present the detection as the default, then ask (multi-
select) which tools the harness must run in. The answer sets whether step 8 ports the scaffolded
harness with `scripts/port.py --tool cursor|codex|all`. Detection only pre-fills the default: a team
may want Cursor support before any `.cursor/` exists. This drives the port step, not a scaffold
variable.

## Batch B - tech stack

4. Language / framework (or "TBD via ADR" placeholders).
5. **Database + ORM** (e.g. PostgreSQL + Prisma / MySQL / MongoDB / none). Drives the `db` flag,
   `rules/data-model.md`, `/db-migration`, and the DB agents in Batch E.
6. Async/queue layer, external providers (LLM gateway? OCR? storage?), hosting target. An LLM
   provider whose output reaches users sets the `ai` flag.
7. **Environments and configuration** - which environments exist (local / dev / staging /
   production), where secrets live per environment (`.env.local` for dev; platform variables for
   prod), and any auth/SSO providers. Drives `.env.example`.
8. **Dev OS** - AUTO-DETECT from the running environment (platform, shell, path separators) and ask
   the user to confirm rather than asking cold; also ask whether the team is mixed-OS. Sets the
   `windows` / `posix` flag, which gates the hook flavor and the settings registration lines. Get it
   wrong and the guardrails never fire, silently.

## Batch C - git and CI

9. **Git hosting platform** - GitHub / GitLab, **cloud or self-hosted (ask which!)** / Bitbucket /
   none yet. Drives the CLI (`gh` / `glab`), PR-vs-MR terminology everywhere including command NAMES
   (`/review-mr` vs `/review-pr`), and the CI file. For self-hosted GitLab also capture the instance
   hostname (`glab auth login --hostname <host>`) and that CI secrets are masked + protected
   variables.
10. **Commit identity** - the exact name/email registered on THAT platform or instance. A wrong email
    means misattributed commits.
11. Default branch name and branch naming convention (default: `main`, `feat/fix/chore/...`). Feeds
    the `guard-main-commit` hook.
12. **Commit message convention** - Conventional Commits is the default. Confirm the type list
    (default: feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert) and define the
    PROJECT-SPECIFIC scope list from the feature areas in Batch A/B: one scope per module or FR area,
    plus `specs`, `agents`, `infra`. Subject limit 72 chars, imperative lowercase.

## Batch D - quality and safety

13. **Test agent** - a dedicated `qa-test` agent (unit + e2e)? Which frameworks (default Vitest +
    Playwright; pytest etc. per stack), and the test/lint/build commands as actually run. If declined,
    skip the agent and `/test` but keep `rules/testing.md`.
14. **Development methodology** - how should the dev seats be disciplined? One question, three
    answers; the choice becomes flags the scaffolder wires through every affected asset, so it is
    consistent across agents, rules, and commands from the first dispatch:
    - **TDD** (default, flag `tdd`) - red/green/refactor; `rules/testing.md` and `/implement-fr`
      carry the tests-first contract.
    - **DDD** (flag `ddd`) - `rules/ddd.md` lands: the spec glossary becomes the ubiquitous
      language, each dev agent's scope is treated as a bounded context, aggregate-root discipline
      applies. Tests still ship in the same change, but are not required to come first.
    - **TDD + DDD** (both flags) - both rules land and compose; this is the strictest posture.
15. **Data sensitivity** - does the system handle PII or regulated data? Drives how strict
    `security-privacy.md`, the `/secret-scan` PII patterns, and the synthetic-data rule must be.
16. Is it an AI product (LLM-generated output shown to users)? If yes, set the `ai` flag: the
    human-in-the-loop and prompt-injection guardrails come with it.
17. **Effort profile** - how should the roster be tuned for cost vs depth? One question, three
    answers:
    - **Default** (recommended) - the per-agent allocation in [`roster.md`](roster.md) as written.
    - **Economy** - step the non-gate seats down one effort level and keep mechanical seats at
      `haiku`+`low`. Never steps down the review, debug, or orchestration gates.
    - **Thorough** - raise the dev seats to `xhigh` for a known-hard codebase; the gates stay at
      their table values.

    Do not restate the allocation here - [`cost-model.md`](cost-model.md) explains why each seat sits
    where it does, and the chosen profile is recorded in `docs/context/tool-changelog.md`.
18. **Control level** - how much may agents do without a human in the loop? Ask the deployment
    question explicitly; it is the one teams regret guessing:
    - **Deployment rights** - three answers:
      - **Human-only** (default) - `{{DEPLOY_CMD}}` sits in `permissions.deny`; `/deploy` prepares
        and verifies but a human runs the command. No flag.
      - **Agent, with approval** (flag `deploy_ask`) - `{{DEPLOY_CMD}}` moves from `deny` to `ask`:
        the agent can initiate a deploy but every invocation stops for an explicit yes.
      - **Agent, non-prod only** - keep the production command in `deny` and put the staging
        command in `allow`; needs the two commands to actually differ, so confirm both.
    - **Destructive commands** - confirm the deny list covers this stack's real reset/force
      commands (Q21 already collects the DB one); ask if there are others (infra teardown, queue
      purge).
    - Note that every dial here can be changed after bootstrap with `/harness-tune` - the answer
      sets the starting posture, not a permanent one.

## Batch E - database operations and seed data

Ask only if Batch B has a DB.

19. Which DB agents to create: `data-modeler` (schema design - recommended whenever there is a
    schema), `db-engineer` (apply/troubleshoot migrations, query and index tuning, local docker env),
    `db-seeder` + `/seed-db` (synthetic data for dev/demo/test).
20. If seeding: which environments are seed targets (local docker / shared dev / staging), the
    default seed scope (entities + volumes), the locale mix for generated data, and confirm the
    synthetic-only policy - real user data never enters seeds, production is never a seed target.
21. The real destructive DB command for this stack (`prisma migrate reset` / `rails db:reset` /
    `alembic downgrade`). It becomes a settings.json deny rule, so a generic guess is worthless.

## Batch F - branding and frontend

Ask only if the project has UI or document output (sets the `ui` flag).

22. Official brand assets (logo files, dark-vs-light variants), fonts, palette. Recorded in
    `rules/frontend.md` as a mandatory section: variant-per-background, self-hosted under
    `public/brand/`, aspect ratio and clear space, alt text.
23. Icon/emoji policy (default: no emoji, SVG icons) and accessibility target (default WCAG 2.1 AA).

## Batch G - audit mode only

Ask only when agents will never modify the source. See [`audit-mode.md`](audit-mode.md).

24. Which repos are in scope and where they sit relative to the workspace root; which standards apply
    per repo; the scanner strategy (host / Docker / config-only - Docker is the default); the
    severity scale; and who applies fixes.

## Batch H - governance (model sovereignty and IP)

Always asked. **Never guess an answer in this batch and never generate a default** - every answer is
a policy position only the org can hold, and a plausible-looking invented one is worse than a blank,
because it will be believed. If the user does not know, say so in the file and register a task; do
not fill it in for them.

25. **Model sovereignty** - for each data class the project actually handles (Public / Internal /
    Confidential / Restricted), which model or provider may process it? Self-hosted, a specific
    vendor under contract, or none. **"None" is a valid and common answer for Restricted** - it means
    that work is not delegated to an agent at all. Fills `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`,
    `{{MODEL_CONFIDENTIAL}}`, `{{MODEL_RESTRICTED}}`.
26. **Residency** - which region or boundary must processing stay inside (`{{DATA_RESIDENCY}}`)?
27. **Dependency licences** - which licence families are allowed, and which are denied
    (`{{ALLOWED_LICENCES}}`, `{{DENIED_LICENCES}}`)? Typical starting point, to CONFIRM not assume:
    allow MIT / BSD / Apache-2.0 / ISC; deny GPL / AGPL / SSPL / BSL / Commons Clause in a
    proprietary product. Also: who owns agent-authored code, in one sentence
    (`{{IP_OWNERSHIP_STATEMENT}}`).
28. **Gated actions and the incident path** - which production actions may an agent or an in-product
    model never take unsupervised (`{{GATED_ACTIONS}}`), and who is notified when a shipped AI
    feature does something wrong (`{{INCIDENT_CONTACT}}`)?

## Intake answers to `vars.json`

The scaffolder (`../scripts/scaffold.py`) consumes `vars.json`. Every question above lands in exactly
one variable or flag; the remaining variables come from the analysis, not from the user.

| Answer | Goes to |
|---|---|
| 1 project name, domain, purpose | `{{PROJECT_NAME}}`, `{{DOMAIN}}`, `{{DOMAIN_DESCRIPTION}}` |
| 2 docs language | no var - sets the language of authored `docs/` prose only |
| 3 specs exist | `{{FR_LIST}}` (from the specs, if any); otherwise the `spec-builder` handoff |
| target AI tools (Batch A) | no var - drives whether step 8 ports to Cursor / Codex via `port.py` |
| 4 language/framework | `{{SOURCE_GLOBS}}` shape; `tech-stack.md` body |
| 5 database + ORM | flag `db`, `{{ORM}}`, `{{DB_GLOBS}}` |
| 6 providers / hosting | flag `ai` (if LLM output reaches users), `{{HOSTING}}` |
| 7 environments and secrets | `.env.example` groups (authored, not templated) |
| 8 dev OS | flag `windows` or `posix` → `{{HOOK_RUNNER}}`, `{{HOOK_EXT}}` |
| 9 git platform | `{{PR_OR_MR}}`, `{{CI_PLATFORM}}` |
| 10 commit identity | no var - `git config` on the target repo |
| 11 default branch | `{{DEFAULT_BRANCH}}` |
| 12 commit convention | `{{COMMIT_TYPES}}`, `{{COMMIT_SCOPES}}` |
| 13 test agent + commands | `{{UNIT_FRAMEWORK}}`, `{{E2E_FRAMEWORK}}`, `{{TEST_CMD}}`, `{{LINT_CMD}}`, `{{BUILD_CMD}}`, `{{COVERAGE_TARGET}}`, `{{TEST_GLOBS}}` |
| 14 methodology | flag `tdd` and/or `ddd` - gates `rules/ddd.md` and the tests-first blocks in `testing.md`, `/implement-fr`, `qa-test`, dev agents |
| 15 data sensitivity | `{{PII_OR_DATA}}` |
| 16 AI product | flag `ai` |
| 17 effort profile | no var - the roster allocation; record the choice in `docs/context/tool-changelog.md` |
| 18 control level | flag `deploy_ask` (deploy in `ask` instead of `deny`); extra deny entries for stack-specific destructive commands |
| 19 DB agents | roster seats (`data-modeler`, `db-engineer`, `db-seeder`) |
| 20 seed policy | `/seed-db` and `db-seeder` scope |
| 21 destructive DB command | `{{DB_RESET_CMD}}`, `{{DB_RESET_PATTERN}}` |
| 22-23 branding, a11y | flag `ui`, `{{UI_GLOBS}}`; `rules/frontend.md` body |
| 24 audit scope | flag `audit`, `{{WORKSPACE_ROOT}}`, `{{REPO_DIR_LIST}}` |
| 25 model sovereignty | `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`, `{{MODEL_CONFIDENTIAL}}`, `{{MODEL_RESTRICTED}}` |
| 26 residency | `{{DATA_RESIDENCY}}` |
| 27 licences + ownership | `{{ALLOWED_LICENCES}}`, `{{DENIED_LICENCES}}`, `{{IP_OWNERSHIP_STATEMENT}}` |
| 28 gated actions + incident path | `{{GATED_ACTIONS}}`, `{{INCIDENT_CONTACT}}` |
| - dependency manifests (from analysis) | `{{DEP_MANIFEST_GLOBS}}` |
| - deploy command (from analysis or Q6) | `{{DEPLOY_CMD}}` |
| - module paths, routing, dev agents | `{{MODULE_PATHS}}`, `{{ROUTING_TABLE}}`, `{{DEV_AGENT_NAME}}` - from the analysis |

Flags are exactly: `ui`, `db`, `ai`, `audit`, `tdd`, `ddd`, `deploy_ask`, and exactly one of
`windows` / `posix`. `tdd` is on unless the user chose DDD-only; `tdd` and `ddd` may be combined.

### Restricted data paths (asked whenever any class above is Restricted)

**Q: Where does Restricted data live in this repo, as glob patterns?**

This is the question that turns the classification table from advice into enforcement. The answers
become `permissions.deny` entries on `Read(...)`, so agents cannot obtain the data at all -- and what
an agent cannot read, it cannot send to any provider.

- Format the answer as ready-to-paste JSON array entries, each ending with a comma, for
  `{{RESTRICTED_DENIES}}`. For example:
  `"Read(data/restricted/**)",` and `"Read(**/*.phi.json)",`
- If the repo holds no Restricted data, that is a normal answer. Use the convention placeholder
  `"Read(**/.restricted/**)",` so the slot is valid JSON and the convention exists for later.
- **Never guess this.** A wrong glob here is a control that looks present and is not. If the user
  does not know, that itself is a finding: record it in `docs/context/known-issues.md` and say the
  classification table is advisory until it is answered.

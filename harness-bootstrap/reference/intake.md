# Intake - the questions the code cannot answer

The questionnaire is mandatory. Thoroughness beats speed: a wrong answer here is baked into every
generated file. After the questionnaire, echo back a **one-screen setup plan** - what will be created,
kept, and modified, plus the roster with each agent's model and effort - and get confirmation before
writing anything.

## Asking mechanics, and the express path

Tags below: **AQ** = `AskUserQuestion` (closed choice, max 4 options, recommended option first labeled
`"(Recommended)"`, up to 4 questions batched per call); **chat** = free-text question in conversation;
**CONFIRM (source: X)** = [`codebase-analysis.md`](codebase-analysis.md) already answered it in
brownfield/audit - present the finding as the default, get a one-line correct-or-confirm, never a fresh
interview. Never assume an answer silently - if skipped, state the default you will use and why.

**Express intake ("use defaults"):** ask only what has **no safe default** - project identity (Q1), the
deployment-rights half of Q15, and all of Batch H (Q21-24, absolute and unaffected by express mode).
Everything else silently takes the default already stated in its question below (the CONFIRM finding
where analysis ran, the labeled "Recommended" option otherwise); print the assumed defaults as one table
for confirmation before writing anything - one pass, not one prompt per row. Batch G (audit mode) is
never eligible for express intake - scope cannot be guessed.

## Batch A - project identity

1. **[chat]** Project name, domain, one-line purpose. Brownfield: a manifest's `name` field or the repo
   directory is a candidate to suggest, never to assume silently.
2. **[AQ]** **Documentation language** for `docs/` content (Vietnamese / Japanese / English / other -
   max 4 options). Regardless of the answer, ALL agent-facing files (`CLAUDE.md`, `AGENTS.md`,
   `.claude/*`) are English; codes, enums, and filenames are always English.
3. **[CONFIRM - presence of `docs/specs/`]** Do specs already exist? If not, invoke `spec-builder` via
   the `Skill` tool first (state the handoff in words if unavailable) - the bootstrap is better with FRs.

**Target AI tools - [AQ, multi-select].** Detect which tools the repo already uses - `.claude/`/
`CLAUDE.md` (Claude Code, always primary), `.cursor/`/`.cursorrules` (Cursor), `.codex/` (Codex), a
shared `AGENTS.md` (read by both) - as the default, then ask which tools the harness must run in (sets
whether step 8 ports via `scripts/port.py --tool cursor|codex|all`); a team may want Cursor support
before any `.cursor/` exists.

## Batch B - tech stack

4. **[CONFIRM - manifests/lockfiles]** Language / framework (or "TBD via ADR" placeholders).
5. **[CONFIRM - schema/ORM config files]** **Database + ORM** (e.g. PostgreSQL + Prisma / MySQL /
   MongoDB / none). Drives the `db` flag, `rules/data-model.md`, `/db-migration`, and the DB agents in
   Batch E.
6. **[CONFIRM queue/integrations - analysis; chat for hosting if no deploy config found]** Async/queue
   layer, external providers (LLM gateway? OCR? storage?), hosting target. An LLM provider whose output
   reaches users sets the `ai` flag.
7. **[CONFIRM - `.env*` + CI config; chat for auth/SSO if not evident]** **Environments and
   configuration** - which environments exist (local / dev / staging / production), where secrets live
   per environment, and any auth/SSO providers. Drives `.env.example`.
8. **[AQ, auto-detected value first]** **Dev OS** - AUTO-DETECT from the running environment (platform,
   shell, path separators) and confirm rather than asking cold; also ask if the team is mixed-OS. Sets
   the `windows`/`posix` flag, gating hook flavor and settings registration lines - get it wrong and the
   guardrails never fire, silently.

## Batch C - git and CI

9. **[CONFIRM - `git remote -v` + `git config user.name`/`user.email`]** **Git platform and commit
   identity.** Platform: GitHub / GitLab, cloud or self-hosted (ask which!) / Bitbucket / none yet -
   drives the CLI (`gh`/`glab`), PR-vs-MR terminology everywhere including command NAMES (`/review-mr`
   vs `/review-pr`), and the CI file. Self-hosted GitLab: also capture the instance hostname and that CI
   secrets are masked + protected. Identity: name/email registered on THAT platform - confirm it, a
   wrong email means misattributed commits.
10. **[CONFIRM - `git symbolic-ref`/remote HEAD + `git log`; chat for the scope list]** **Default
    branch and commit convention.** Branch: default `main`, naming `feat/fix/chore/...` - feeds
    `guard-main-commit`. Convention: Conventional Commits is default - confirm the type list
    (feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert) and define the PROJECT-SPECIFIC scope
    list from the feature areas in Batch A/B: one per module or FR area, plus `specs`, `agents`,
    `infra`. Subject limit 72 chars, imperative lowercase.

## Batch D - quality and safety

11. **[AQ for the agent decision; CONFIRM frameworks/commands - test config/`package.json` scripts]**
    **Test agent** - a dedicated `qa-test` agent (unit + e2e)? Which frameworks (default Vitest +
    Playwright; pytest etc. per stack), and the test/lint/build commands as actually run. If declined,
    skip the agent and `/test` but keep `rules/testing.md`.
12. **[AQ, 3 options, "TDD + DDD (Recommended)" first]** **Development methodology** - how should the
    dev seats be disciplined?
    - **TDD + DDD (Recommended)** (flags `tdd` + `ddd`) - red/green/refactor AND `rules/ddd.md`: the
      spec glossary becomes the ubiquitous language, each dev agent's scope is a bounded context,
      aggregate-root discipline applies. The two compose; this is the shipped posture.
    - **TDD only** (flag `tdd`) - the tests-first contract without the domain-modeling discipline; for
      projects with no meaningful domain layer (scripts, pipelines, pure infra).
    - **DDD only** (flag `ddd`) - domain discipline with tests in the same change, not required first;
      choose deliberately, it weakens the red/green proof.
13. **[AQ, two sub-parts, one call]** **Data sensitivity and AI product.** Does the system handle PII or
    regulated data (drives how strict `security-privacy.md`, the `/secret-scan` PII patterns, and the
    synthetic-data rule must be)? Is it an AI product, LLM-generated output shown to users (sets the `ai`
    flag: human-in-the-loop and prompt-injection guardrails come with it)?
14. **[AQ, 3 options, "Default (Recommended)" first]** **Effort profile** - how should the roster be
    tuned for cost vs depth?
    - **Default (Recommended)** - the per-agent allocation in [`roster.md`](roster.md) as written.
    - **Economy** - step the non-gate seats down one effort level and keep mechanical seats at
      `haiku`+`low`. Never steps down the review, debug, or orchestration gates.
    - **Thorough** - raise the dev seats to `xhigh` for a known-hard codebase; the gates stay at their
      table values.

    Do not restate the allocation here - [`cost-model.md`](cost-model.md) explains why each seat sits
    where it does, and the chosen profile is recorded in `docs/context/tool-changelog.md`.
15. **[AQ for deploy rights - no safe default even in express intake; chat for destructive commands, DB
    one CONFIRMED from Q17]** **Control level** - how much may agents do without a human in the loop?
    - **Deployment rights** - three answers:
      - **Human-only (Recommended)** - `{{DEPLOY_CMD}}` sits in `permissions.deny`; `/deploy` prepares
        and verifies but a human runs the command. No flag.
      - **Agent, with approval** (flag `deploy_ask`) - `{{DEPLOY_CMD}}` moves from `deny` to `ask`: the
        agent can initiate a deploy but every invocation stops for an explicit yes.
      - **Agent, non-prod only** - keep the production command in `deny` and put the staging command in
        `allow`; needs the two commands to actually differ, so confirm both.
    - **Destructive commands** - confirm the deny list covers this stack's real reset/force commands
      (Q17 already collects the DB one); ask if there are others (infra teardown, queue purge).
    - Every dial here can be changed after bootstrap with `/harness-tune` - the answer sets the starting
      posture, not a permanent one.

## Batch E - database operations and seed data

Ask only if Batch B has a DB.

16. **[AQ multi-select for the agent set; chat for seed sub-parts if `db-seeder` is chosen]** **DB
    agents and seed policy.** Which DB agents: `data-modeler` (schema design - recommended whenever
    there is a schema), `db-engineer` (apply/troubleshoot migrations, query and index tuning, local
    docker env), `db-seeder` + `/seed-db` (synthetic data for dev/demo/test). If chosen: seed-target
    environments (local docker / shared dev / staging), default seed scope (entities + volumes), locale
    mix, and confirm the synthetic-only policy - real data never enters seeds, prod is never a target.
17. **[CONFIRM if the ORM from Q5 has a known reset convention; chat otherwise, never guess]** The real
    destructive DB command for this stack (`prisma migrate reset` / `rails db:reset` / `alembic
    downgrade`). It becomes a settings.json deny rule, so a wrong guess is worthless.

## Batch F - branding and frontend

Ask only if the project has UI or document output (sets the `ui` flag).

18. **[chat; CONFIRM existence - `public/brand/` or similar, if already present]** Official brand assets
    (logo files, dark-vs-light variants), fonts, palette. Recorded in `rules/frontend.md`: variant-per-
    background, self-hosted under `public/brand/`, aspect ratio and clear space, alt text.
19. **[AQ, recommended defaults first]** Icon/emoji policy (default: no emoji, SVG icons) and
    accessibility target (default WCAG 2.1 AA).

## Batch G - audit mode only

Ask only when agents will never modify the source. See [`audit-mode.md`](audit-mode.md). Not eligible
for express intake - scope cannot be defaulted.

20. **[chat for repo list/standards; AQ for scanner strategy, "Docker (Recommended)" first]** Which
    repos are in scope, relative to the workspace root; standards per repo; the scanner strategy (host /
    Docker / config-only); the severity scale; and who applies fixes.

## Batch H - governance (model sovereignty and IP)

Always asked, in full, even in express intake. **Never guess an answer here and never generate a
default** - every answer is a policy position only the org can hold, and a plausible-looking invented one
is worse than a blank, because it will be believed. If the user does not know, say so and register a
task; do not fill it in for them. All four are **[chat]** - open text, not an enumerable choice.

21. **Model sovereignty** - for each data class the project actually handles (Public / Internal /
    Confidential / Restricted), which model or provider may process it? Self-hosted, a specific vendor
    under contract, or none. **"None" is a valid and common answer for Restricted** - it means that work
    is not delegated to an agent at all. Fills `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`,
    `{{MODEL_CONFIDENTIAL}}`, `{{MODEL_RESTRICTED}}`.
22. **Residency** - which region or boundary must processing stay inside (`{{DATA_RESIDENCY}}`)?
23. **Dependency licences** - which licence families are allowed, and which are denied
    (`{{ALLOWED_LICENCES}}`, `{{DENIED_LICENCES}}`)? Typical starting point, to CONFIRM not assume:
    allow MIT / BSD / Apache-2.0 / ISC; deny GPL / AGPL / SSPL / BSL / Commons Clause in a proprietary
    product. Also: who owns agent-authored code, in one sentence (`{{IP_OWNERSHIP_STATEMENT}}`).
24. **Gated actions and the incident path** - which production actions may an agent or an in-product
    model never take unsupervised (`{{GATED_ACTIONS}}`), and who is notified when a shipped AI feature
    does something wrong (`{{INCIDENT_CONTACT}}`)?

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
| 9 git platform + commit identity | `{{PR_OR_MR}}`, `{{CI_PLATFORM}}`; identity: no var (`git config`) |
| 10 default branch + commit convention | `{{DEFAULT_BRANCH}}`; `{{COMMIT_TYPES}}`, `{{COMMIT_SCOPES}}` |
| 11 test agent + frameworks + commands | `{{UNIT_FRAMEWORK}}`, `{{E2E_FRAMEWORK}}`, `{{TEST_CMD}}`, `{{LINT_CMD}}`, `{{BUILD_CMD}}`, `{{COVERAGE_TARGET}}`, `{{TEST_GLOBS}}` |
| 12 methodology | flag `tdd` and/or `ddd` - gates `rules/ddd.md` and the tests-first blocks in `testing.md`, `/implement-fr`, `qa-test`, dev agents |
| 13 data sensitivity + AI product | `{{PII_OR_DATA}}`; flag `ai` |
| 14 effort profile | no var - the roster allocation; record the choice in `docs/context/tool-changelog.md` |
| 15 control level | flag `deploy_ask` (deploy in `ask` instead of `deny`); extra deny entries for stack-specific destructive commands |
| 16 DB agents + seed policy | roster seats (`data-modeler`, `db-engineer`, `db-seeder`); `/seed-db` and `db-seeder` scope |
| 17 destructive DB command | `{{DB_RESET_CMD}}`, `{{DB_RESET_PATTERN}}` |
| 18-19 branding, icons, a11y | flag `ui`, `{{UI_GLOBS}}`; `rules/frontend.md` body |
| 20 audit scope | flag `audit`, `{{WORKSPACE_ROOT}}`, `{{REPO_DIR_LIST}}` |
| 21 model sovereignty | `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`, `{{MODEL_CONFIDENTIAL}}`, `{{MODEL_RESTRICTED}}` |
| 22 residency | `{{DATA_RESIDENCY}}` |
| 23 licences + ownership | `{{ALLOWED_LICENCES}}`, `{{DENIED_LICENCES}}`, `{{IP_OWNERSHIP_STATEMENT}}` |
| 24 gated actions + incident path | `{{GATED_ACTIONS}}`, `{{INCIDENT_CONTACT}}` |
| - dependency manifests (from analysis) | `{{DEP_MANIFEST_GLOBS}}` |
| - deploy command (from analysis or Q6) | `{{DEPLOY_CMD}}` |
| - module paths, routing, dev agents | `{{MODULE_PATHS}}`, `{{ROUTING_TABLE}}`, `{{DEV_AGENT_NAME}}` - from the analysis |

Flags are exactly: `ui`, `db`, `ai`, `audit`, `tdd`, `ddd`, `deploy_ask`, and exactly one of
`windows` / `posix`. `tdd` and `ddd` are BOTH on by default; drop one only when the user explicitly picks a single methodology.

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

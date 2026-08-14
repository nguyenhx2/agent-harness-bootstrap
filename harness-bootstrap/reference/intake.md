# Intake - the questions the code cannot answer

The questionnaire is mandatory - a wrong answer here is baked into every generated file. After it, echo
back a **one-screen setup plan** - what will be created, kept, and modified, plus the roster with each
agent's model and effort - and get confirmation before writing anything.

## Asking mechanics, and the express path

Tags below: **AQ** = `AskUserQuestion` (closed choice, max 4 options, recommended option first labeled
`"(Recommended)"`, up to 4 questions batched per call); **chat** = free-text question in conversation;
**CONFIRM (source: X)** = [`codebase-analysis.md`](codebase-analysis.md) already answered it in
brownfield/audit - present the finding as default, get a one-line correct-or-confirm, not a fresh
interview. Never assume an answer silently - if skipped, state the default you will use and why.

**Express intake ("use defaults"):** ask only what has **no safe default** - project identity (Q1), the
deployment-rights half of Q18, and all of Batch H (Q24-27, absolute and unaffected by express mode).
Everything else silently takes the default already stated in its question (the CONFIRM finding where
analysis ran, the labeled "Recommended" option otherwise); print the assumed defaults as one table for
confirmation before writing anything - one pass, not one prompt per row. Batch G (audit mode) is never
eligible for express intake - scope cannot be guessed.

## Batch A - project identity

1. **[chat]** Project name, domain, one-line purpose. Brownfield: a manifest's `name` field or the repo
   directory is a candidate to suggest, never to assume silently.
2. **[AQ]** **Documentation language** for `docs/` content (Vietnamese / Japanese / English / other -
   max 4 options). Regardless, ALL agent-facing files (`CLAUDE.md`, `AGENTS.md`, `.claude/*`) are
   English; codes, enums, and filenames are always English.
3. **[CONFIRM - presence of `docs/specs/`]** Do specs already exist? If not, invoke `spec-builder` via
   the `Skill` tool first (state the handoff if unavailable) - the bootstrap is better with FRs.

**Target AI tools - [AQ, multi-select].** Detect which tools the repo already uses - `.claude/`/
`CLAUDE.md` (Claude Code, always primary), `.cursor/`/`.cursorrules` (Cursor), `.codex/` (Codex), a
shared `AGENTS.md` (both) - as the default, then ask which the harness must run in (sets whether step 8
ports via `scripts/port.py --tool cursor|codex|all`); a team may want Cursor support before `.cursor/`
exists.

## Batch B - tech stack

4. **[CONFIRM - manifests/lockfiles]** Language / framework (or "TBD via ADR"). Greenfield: propose
   from [`tech-presets.md`](tech-presets.md), not a memorized version - check the real registry (`npm
   view <pkg> version`, `pip index versions <pkg>`, `gh api .../releases/latest`) and record the version
   plus check date in `docs/context/tech-stack.md`. Brownfield: analysis overrides the preset; a
   contradiction is a migration-backlog proposal, not a silent swap.
5. **[CONFIRM - schema/ORM config files]** **Database + ORM** (e.g. PostgreSQL + Prisma / MySQL /
   MongoDB / none). Drives `db`, `rules/data-model.md`, `/db-migration`, and Batch E's DB agents.
6. **[CONFIRM queue/integrations - analysis; chat for hosting if no deploy config; chat for
   fallback/update-cadence]** Async/queue layer, external providers (LLM gateway? OCR? storage?),
   hosting target. An LLM provider whose output reaches users sets `ai`. Per load-bearing integration:
   the fallback when down (documented / queued retry / hard failure) and the update cadence
   (Dependabot/Renovate or manual). If Q15 named SOC2, ISO 27001, or PCI-DSS, confirm any SBOM
   requirement.
7. **[AQ - single-locale default, no follow-up; chat sub-parts if multi-locale]** **Product
   internationalization.** Does the product (not `docs/`, see Q2) serve more than one user-facing
   language? If yes: locales, RTL need, timezone/currency/date convention, DB character set. No var -
   authored into `tech-stack.md`/`coding-standards.md` and `data-modeler`'s notes in `data-model.md`.
8. **[CONFIRM - `.env*` + CI config; chat for auth/SSO if not evident]** **Environments and
   configuration** - which environments exist (local / dev / staging / production), who owns each, where
   secrets live per environment, and any auth/SSO providers. Drives `.env.example`.
9. **[AQ, 3 options, "RBAC (Recommended)" first; chat sub-parts if multi-tenant]** **Authorization
   model and tenancy.** RBAC (role-based) / ABAC (access depends on record attributes) / ownership-only
   (no roles, own data only). If multi-tenant: isolation strategy (row-level tenant column /
   schema-per-tenant / DB-per-tenant) and any break-glass admin path - who, and is it logged. No var -
   feeds `data-model.md`'s entity notes; a break-glass path becomes a `settings.json` entry, authored
   like Q18's.
10. **[AQ, auto-detected value first]** **Dev OS** - AUTO-DETECT from the environment (platform, shell,
    path separators) and confirm rather than ask cold; also ask if the team is mixed-OS. Sets
    `windows`/`posix`, gating hook flavor and settings lines - get it wrong and guardrails never fire,
    silently.

## Batch C - git and CI

11. **[CONFIRM - `git remote -v` + `git config user.name`/`user.email`; chat for the bot sub-part]**
    **Git platform and commit identity.** Platform: GitHub / GitLab, cloud or self-hosted (ask which!) /
    Bitbucket / none - drives the CLI (`gh`/`glab`), PR-vs-MR wording, and the CI file. Self-hosted
    GitLab: capture the instance hostname and that CI secrets are masked + protected. Identity: name/
    email on THAT platform - confirm it, a wrong email misattributes commits. Also: does a bot already
    hold commit/merge rights on the default branch (Dependabot, Renovate, auto-merge)? No var - recorded
    in `known-issues.md`, and as a `merge-manager` exception if that agent is fielded.
12. **[CONFIRM - `git symbolic-ref`/remote HEAD + `git log`; chat for the scope list]** **Default
    branch and commit convention.** Branch: default `main`, naming `feat/fix/chore/...` - feeds
    `guard-main-commit`. Convention: Conventional Commits is default - confirm the type list
    (feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert) and the PROJECT-SPECIFIC scope list
    from Batch A/B's feature areas: one per module or FR area, plus `specs`, `agents`, `infra`. Subject
    limit 72 chars, imperative lowercase.

## Batch D - quality and safety

13. **[AQ for the agent decision; CONFIRM frameworks/commands - test config/`package.json` scripts]**
    **Test agent** - a dedicated `qa-test` agent (unit + e2e)? Which frameworks (default Vitest +
    Playwright; pytest etc. per stack), and the actual test/lint/build commands. If declined, skip the
    agent and `/test` but keep `rules/testing.md`.
14. **[AQ, 3 options, "DDD (Recommended)" first]** **Development methodology** - how should the
    dev seats be disciplined?
    - **DDD (Recommended)** (flag `ddd`) - `rules/ddd.md`: the spec glossary becomes the ubiquitous
      language, each dev agent's scope is a bounded context, aggregate-root discipline applies.
      Tests ship in the same change as the implementation, proving the acceptance criteria - they
      are not required to come first, which keeps delivery speed.
    - **TDD** (flag `tdd`) - red/green/refactor, tests strictly first. Stronger proof discipline,
      measurably slower delivery; pick it when correctness pressure outweighs pace.
    - **TDD + DDD** (both flags) - both disciplines at once. The strictest and slowest posture; the
      two can pull against each other (test-first pacing vs model-first design), so choose this
      deliberately, not as a default.
15. **[AQ, 3 sub-parts, one call; chat for lifecycle follow-up if a regime is named]** **Data
    sensitivity, compliance regime, and AI product.**
    - PII or regulated data (sets how strict `security-privacy.md`, `/secret-scan`'s PII patterns, and
      the synthetic-data rule must be)? -> `{{PII_OR_DATA}}`.
    - Compliance regime, if any (multi-select, 4 named + "other"): GDPR/CCPA, HIPAA/PCI-DSS, SOC2/ISO
      27001, or - common for this practice's client base - Japan's APPI (個人情報保護法) and Vietnam's
      Decree 13. "None identified" is valid.
    - AI product, LLM output shown to users (sets `ai`: human-in-the-loop and prompt-injection
      guardrails)?

    If a regime was named: ask (chat, never defaulted) retention period per class, deletion/erasure
    support, and backup/restore expectation (RPO/RTO, or "none defined"). No var - authored into
    `security-privacy.md`'s "Retention and egress" practice, or `known-issues.md` if unknown; record
    "no regime" too, so the gap stays visible.
16. **[AQ, 3 options, "Default (Recommended)" first]** **Effort profile** - how should the roster be
    tuned for cost vs depth?
    - **Default (Recommended)** - the per-agent allocation in [`roster.md`](roster.md) as written.
    - **Economy** - step the non-gate seats down one effort level and keep mechanical seats at
      `haiku`+`low`. Never steps down the review, debug, or orchestration gates.
    - **Thorough** - raise the dev seats to `xhigh` for a known-hard codebase; the gates stay at their
      table values.

    Full allocation and reasoning: [`cost-model.md`](cost-model.md). Record the chosen profile in
    `docs/context/tool-changelog.md`.
    **[AQ, 4 options, batched with Q16]** **Agent-run history detail** - how much of each finished
    subagent run does the `agent-history` hook archive under `.claude/state/history/`?
    - **summary (Recommended)** - per-run file, prompt/response truncated to 1500 chars, newest 200
      kept. Enough for `/board-audit`'s unlogged-completion sweep without unbounded disk growth.
    - **full** - whole prompt and final response per run. Note: PII in prompts lands on disk.
    - **minimal** - one index line per run, no per-run files.
    - **off** - no archive; the unlogged-completion sweep loses its evidence source.
    Sets `{{HISTORY_LEVEL}}` and `{{HISTORY_KEEP}}` (200 for summary/full, 0 for minimal/off).
    Changed later with `/harness-tune` dial 6.
17. **[chat]** **Operations posture.** Uptime/availability target ("best effort" is honest);
    observability stack (logs/metrics/traces); feature-flag mechanism; incident severity ladder - who is
    paged, at what severity; a cloud/infra budget ceiling bounding `devops`'s recommendations, if any. No
    var - feeds `tech-stack.md`; broadens `{{INCIDENT_CONTACT}}` (Q27) to any production incident.
18. **[AQ for deploy rights - no safe default even in express intake; chat for destructive commands, DB
    one CONFIRMED from Q20]** **Control level** - how much may agents do without a human in the loop?
    - **Deployment rights** - three answers:
      - **Human-only (Recommended)** - `{{DEPLOY_CMD}}` sits in `permissions.deny`; `/deploy` prepares
        and verifies but a human runs the command. No flag.
      - **Agent, with approval** (flag `deploy_ask`) - `{{DEPLOY_CMD}}` moves from `deny` to `ask`: the
        agent can initiate a deploy but every invocation stops for an explicit yes. Confirm the
        approver's normal availability/timezone - an unanswered `ask` gate is a stall, not a control.
      - **Agent, non-prod only** - keep the production command in `deny` and put the staging command in
        `allow`; needs the two commands to actually differ, so confirm both.
    - **Destructive commands** - confirm the deny list covers this stack's real reset/force commands
      (Q20 already collects the DB one); ask if there are others (infra teardown, queue purge).
    - Every dial here can be changed after bootstrap with `/harness-tune` - the answer sets the starting
      posture, not a permanent one.

## Batch E - database operations and seed data

Ask only if Batch B has a DB.

19. **[AQ multi-select for the agent set; chat for seed sub-parts if `db-seeder` is chosen]** **DB
    agents and seed policy.** Which DB agents: `data-modeler` (schema design - recommended whenever a
    schema exists), `db-engineer` (apply/troubleshoot migrations, query/index tuning, local docker env),
    `db-seeder` + `/seed-db` (synthetic data for dev/demo/test). If chosen: seed-target environments
    (local docker / shared dev / staging), default seed scope (entities + volumes), locale mix, and the
    synthetic-only policy - real data never enters seeds, prod is never a target.
20. **[CONFIRM if the ORM from Q5 has a known reset convention; chat otherwise, never guess]** The real
    destructive DB command for this stack (`prisma migrate reset` / `rails db:reset` / `alembic
    downgrade`). It becomes a settings.json deny rule, so a wrong guess is worthless.

## Batch F - branding and frontend

Ask only if the project has UI or document output (`ui` flag).

21. **[chat; CONFIRM existence - `public/brand/` or similar, if already present]** Official brand assets
    (logo files, dark-vs-light variants), fonts, palette. Recorded in `rules/frontend.md`: variant per
    background, self-hosted under `public/brand/`, aspect ratio, clear space, alt text.
22. **[AQ, recommended defaults first]** Icon/emoji policy (default: no emoji, SVG icons) and
    accessibility target (default WCAG 2.1 AA).

## Batch G - audit mode only

Ask only when agents never modify source. See [`audit-mode.md`](audit-mode.md). Not eligible for
express intake - scope cannot be defaulted.

23. **[chat for repo list/standards; AQ for scanner strategy, "Docker (Recommended)" first]** Which
    repos are in scope, relative to the workspace root; standards per repo; the scanner strategy (host /
    Docker / config-only); the severity scale; and who applies fixes.

## Batch H - governance (model sovereignty and IP)

Always asked, in full, even in express intake. **Never guess an answer here and never generate a
default** - every answer is a policy position only the org can hold, and a plausible-looking invented one
is worse than a blank, because it will be believed. If the user does not know, say so and register a
task; do not fill it in for them. All four are **[chat]** - open text, not an enumerable choice.

24. **Model sovereignty** - for each data class the project actually handles (Public / Internal /
    Confidential / Restricted), which model or provider may process it? Self-hosted, a specific vendor
    under contract, or none. **"None" is a valid and common answer for Restricted** - it means that work
    is not delegated to an agent at all. Fills `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`,
    `{{MODEL_CONFIDENTIAL}}`, `{{MODEL_RESTRICTED}}`.
25. **Residency** - which region or boundary must processing stay inside (`{{DATA_RESIDENCY}}`)?
26. **Dependency licences** - which licence families are allowed, and which are denied
    (`{{ALLOWED_LICENCES}}`, `{{DENIED_LICENCES}}`)? Typical starting point, to CONFIRM not assume:
    allow MIT / BSD / Apache-2.0 / ISC; deny GPL / AGPL / SSPL / BSL / Commons Clause in a proprietary
    product. Also: who owns agent-authored code, in one sentence (`{{IP_OWNERSHIP_STATEMENT}}`).
27. **Gated actions and the incident path** - which production actions may an agent or an in-product
    model never take unsupervised (`{{GATED_ACTIONS}}`), and who is notified when something goes wrong
    in production - a shipped AI feature (`ai-governance.md`) or any other production incident Q17's
    severity ladder describes (`{{INCIDENT_CONTACT}}`)? One contact answers both; if the org runs a
    narrower AI-specific escalation path, name both explicitly.

## Intake answers to `vars.json`

The scaffolder (`../scripts/scaffold.py`) consumes `vars.json`. Every question above lands in exactly
one variable or flag; the remaining variables come from the analysis, not from the user.

| Answer | Goes to |
|---|---|
| 1 project name, domain, purpose | `{{PROJECT_NAME}}`, `{{DOMAIN}}`, `{{DOMAIN_DESCRIPTION}}` |
| 2 docs language | no var - sets the language of authored `docs/` prose only |
| 3 specs exist | `{{FR_LIST}}` (from the specs, if any); otherwise the `spec-builder` handoff |
| target AI tools (Batch A) | no var - drives whether step 8 ports to Cursor / Codex via `port.py` |
| 4 language/framework | `{{SOURCE_GLOBS}}` shape; `tech-stack.md` body; version checked at bootstrap per [`tech-presets.md`](tech-presets.md), never recalled from memory |
| 5 database + ORM | flag `db`, `{{ORM}}`, `{{DB_GLOBS}}` |
| 6 providers / hosting / fallback / update cadence | flag `ai`, `{{HOSTING}}`; fallback/cadence - no var, into `tech-stack.md` and `testing.md`'s provider-wrapper practice |
| 7 product internationalization | no var - into `tech-stack.md`/`coding-standards.md`; DB character-set choice in `data-model.md` |
| 8 environments, ownership, and configuration | `.env.example` groups (authored, not templated) |
| 9 authorization model and tenancy | no var - into `data-model.md`'s entity notes; a break-glass path becomes a `settings.json` entry |
| 10 dev OS | flag `windows` or `posix` → `{{HOOK_RUNNER}}`, `{{HOOK_EXT}}` |
| 11 git platform + commit identity + CI bots | `{{PR_OR_MR}}`, `{{CI_PLATFORM}}`; identity: no var; bot answer: no var, `known-issues.md` + merge-manager exception if fielded |
| 12 default branch + commit convention | `{{DEFAULT_BRANCH}}`; `{{COMMIT_TYPES}}`, `{{COMMIT_SCOPES}}` |
| 13 test agent + frameworks + commands | `{{UNIT_FRAMEWORK}}`, `{{E2E_FRAMEWORK}}`, `{{TEST_CMD}}`, `{{LINT_CMD}}`, `{{BUILD_CMD}}`, `{{COVERAGE_TARGET}}`, `{{TEST_GLOBS}}` |
| 14 methodology | flag `tdd` and/or `ddd` - gates `rules/ddd.md` and the tests-first blocks in `testing.md`, `/implement-fr`, `qa-test`, dev agents |
| 15 data sensitivity + compliance regime + lifecycle + AI product | `{{PII_OR_DATA}}`; flag `ai`; regime/lifecycle - no var, into `security-privacy.md`'s "Retention and egress" practice or `known-issues.md` if unknown |
| 16 effort profile | no var - the roster allocation; record the choice in `docs/context/tool-changelog.md` |
| agent history detail (asked with Q16) | `{{HISTORY_LEVEL}}`, `{{HISTORY_KEEP}}` - written to `.claude/state/history-level`, read by the `agent-history` hook |
| 17 operations posture | no var - into `tech-stack.md`; broadens `{{INCIDENT_CONTACT}}` (set at Q27) |
| 18 control level | flag `deploy_ask`; extra deny entries for stack-specific destructive commands; approver-availability - no var, informs whether `deploy_ask` is realistic |
| 19 DB agents + seed policy | roster seats (`data-modeler`, `db-engineer`, `db-seeder`); `/seed-db` and `db-seeder` scope |
| 20 destructive DB command | `{{DB_RESET_CMD}}`, `{{DB_RESET_PATTERN}}` |
| 21-22 branding, icons, a11y | flag `ui`, `{{UI_GLOBS}}`; `rules/frontend.md` body |
| 23 audit scope | flag `audit`, `{{WORKSPACE_ROOT}}`, `{{REPO_DIR_LIST}}` |
| 24 model sovereignty | `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`, `{{MODEL_CONFIDENTIAL}}`, `{{MODEL_RESTRICTED}}` |
| 25 residency | `{{DATA_RESIDENCY}}` |
| 26 licences + ownership | `{{ALLOWED_LICENCES}}`, `{{DENIED_LICENCES}}`, `{{IP_OWNERSHIP_STATEMENT}}` |
| 27 gated actions + incident path | `{{GATED_ACTIONS}}`, `{{INCIDENT_CONTACT}}` (now any production incident, not only a shipped AI feature's) |
| - dependency manifests (from analysis) | `{{DEP_MANIFEST_GLOBS}}` |
| - deploy command (from analysis or Q6) | `{{DEPLOY_CMD}}` |
| - glossary seed rows (from spec section 03 when spec-builder hands off; `-` if none) | `{{GLOSSARY_SEED}}` |
| - module paths, routing, dev agents | `{{MODULE_PATHS}}`, `{{ROUTING_TABLE}}`, `{{DEV_AGENT_NAME}}` - from the analysis |

Flags are exactly: `ui`, `db`, `ai`, `audit`, `tdd`, `ddd`, `deploy_ask`, and exactly one of
`windows`/`posix`. `ddd` is the default methodology; `tdd` is opt-in (alone or combined) - never assumed.

### Restricted data paths (asked whenever any class above is Restricted)

**Q: Where does Restricted data live in this repo, as glob patterns?**

This is the question that turns the classification table from advice into enforcement: the answers
become `permissions.deny` entries on `Read(...)`, so agents cannot obtain the data - and what an agent
cannot read, it cannot send to any provider.

- Format as ready-to-paste JSON array entries, each ending with a comma, for `{{RESTRICTED_DENIES}}`,
  e.g. `"Read(data/restricted/**)",` and `"Read(**/*.phi.json)",`.
- No Restricted data in the repo is a normal answer - use the convention placeholder
  `"Read(**/.restricted/**)",` so the slot stays valid JSON.
- **Never guess this.** A wrong glob is a control that looks present and is not. If the user does not
  know, record it in `docs/context/known-issues.md` and say the classification table is advisory until
  answered.

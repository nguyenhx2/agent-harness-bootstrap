# Intake - the questions the code cannot answer

The questionnaire is mandatory - a wrong answer here is baked into every generated file. After it, echo
back a **one-screen setup plan** - what will be created, kept, and modified, plus the roster with each
agent's model and effort - and get confirmation before writing anything.

**Solo developer or small project? Offer the express path first** (next section) - it asks only the
questions with no safe default and confirms the rest as one table, which is usually the right trade
below preset M.

## Ask in the user's language

**Infer the language from how the user wrote to you, and ask every question in it.** Not just the
documents it produces - the question text, the option labels, and the option descriptions. Someone
who opened in Vietnamese is interviewed in Vietnamese; someone who opened in Japanese, in Japanese.
Default to English only when the input is genuinely too short or too mixed to tell, and never
interrogate a person in a language they did not choose to write in.

This is separate from Q2. Q2 sets the language of the `docs/` prose the harness will author later
and is a deliberate project decision; the language of the interview itself is never a question,
it is inferred. The two can differ: a Vietnamese team may well choose English docs, and asking them
in English to find that out is the wrong order.

Two things stay English regardless, because they are identifiers rather than prose: flag names and
`{{VAR}}` names as they appear in `vars.json`, and every agent-facing file (`CLAUDE.md`,
`AGENTS.md`, `.claude/*`). Translate the question, not the value it records.

## Asking mechanics, and the express path

Tags: **AQ** = `AskUserQuestion` (closed choice, max 4 options, recommended first labeled
`"(Recommended)"`, up to 4 questions batched per call); **chat** = free-text in conversation;
**CONFIRM (source: X)** = [`codebase-analysis.md`](codebase-analysis.md) already answered it in
brownfield/audit - present the finding as default, get a one-line correct-or-confirm. Never assume
an answer silently - if skipped, state the default you will use and why.

**Express intake ("use defaults"):** ask only what has **no safe default** - project identity (Q1),
the deployment-rights half of Q18, and all of Batch H (Q24-27, absolute and unaffected by express
mode). Everything else takes the default its question states (the CONFIRM finding where analysis
ran, the labeled "Recommended" option otherwise); print the assumed defaults as ONE table for
confirmation before writing anything. Batch G (audit mode) is never express - scope cannot be
guessed.

**Every skipped question must still yield a value.** Express mode changes who supplies the answer,
never whether there is one: a question with no CONFIRM finding and no "(Recommended)" option has no
express default, and skipping it leaves its `{{VAR}}` unset. The scaffolder writes the whole tree
and only then fails on the unresolved variable, so the cost lands at the very end. Before scaffolding
in express mode, check the vars table below and confirm every row has a value.

## Batch A - project identity

1. **[chat]** Project name, domain, one-line purpose. Brownfield: a manifest's `name` field or the repo
   directory is a candidate to suggest, never to assume silently.
2. **[AQ, the inferred interview language first, labeled "(Recommended)"]** **Documentation
   language** for `docs/` content (Vietnamese / Japanese / English / other - max 4 options). ALL
   agent-facing files (`CLAUDE.md`, `AGENTS.md`, `.claude/*`) plus codes, enums, and filenames stay
   English. The scaffolded `docs/README.md` records the choice so later agents author docs prose in
   it without re-asking.

   Recommend the language the user is writing in (the one you inferred above) - it is the best
   available guess and it gives express intake a defined default. **This question must always
   resolve to a value**, including in express mode: `{{DOC_LANGUAGE}}` has no default in the
   scaffolder, so an unset one fails the run AFTER the files are written, which is the worst place
   to fail.
3. **[CONFIRM - presence of `docs/specs/`]** Do specs already exist? If not, invoke `spec-builder` via
   the `Skill` tool first (state the handoff if unavailable) - the bootstrap is better with FRs.

**Target AI tools - [AQ, multi-select].** Detect which tools the repo already uses - `.claude/`/
`CLAUDE.md` (Claude Code, always primary), `.cursor/`/`.cursorrules` (Cursor), `.codex/` (Codex), a
shared `AGENTS.md` (both) - as the default, then ask which the harness must run in (sets whether
step 8 ports via `port.py`); a team may want Cursor support before `.cursor/` exists.

## Batch B - tech stack

4. **[CONFIRM - manifests/lockfiles]** Language / framework (or "TBD via ADR"). Greenfield: propose
   from [`tech-presets.md`](tech-presets.md) - check the real registry per its currency rule and
   record version + check date in `docs/context/tech-stack.md`. Brownfield: analysis overrides the
   preset; a contradiction is a migration-backlog proposal, not a silent swap.
5. **[CONFIRM - schema/ORM config files]** **Database + ORM** (e.g. PostgreSQL + Prisma / MySQL /
   MongoDB / none). Drives `db`, `rules/data-model.md`, `/db-migration`, and Batch E's DB agents.
6. **[CONFIRM queue/integrations - analysis; chat for hosting if no deploy config; chat for
   fallback/update-cadence]** Async/queue layer, external providers (LLM gateway? OCR? storage?),
   hosting target. An LLM provider whose output reaches users sets `ai`. Per load-bearing
   integration: the fallback when down (documented / queued retry / hard failure) and the update
   cadence (Dependabot/Renovate or manual). If Q15 named SOC2, ISO 27001, or PCI-DSS, confirm any
   SBOM requirement.
7. **[AQ - single-locale default, no follow-up; chat sub-parts if multi-locale]** **Product
   internationalization.** Does the product (not `docs/`, see Q2) serve more than one user-facing
   language? If yes: locales, RTL need, timezone/currency/date convention, DB character set. No var -
   authored into `tech-stack.md`/`coding-standards.md` and `data-modeler`'s notes in `data-model.md`.
8. **[CONFIRM - `.env*` + CI config; chat for auth/SSO if not evident]** **Environments and
   configuration** - which environments exist (local / dev / staging / production), who owns each, where
   secrets live per environment, and any auth/SSO providers. Drives `.env.example`.
9. **[AQ, 3 options, "RBAC (Recommended)" first; chat sub-parts if multi-tenant]** **Authorization
   model and tenancy.** RBAC (role-based) / ABAC (record-attribute based) / ownership-only (no
   roles, own data only). If multi-tenant: isolation strategy (row-level tenant column /
   schema-per-tenant / DB-per-tenant) and any break-glass admin path - who, and is it logged. No
   var - feeds `data-model.md`'s entity notes; a break-glass path becomes a `settings.json` entry.
10. **[AQ, auto-detected value first]** **Dev OS** - AUTO-DETECT from the environment (platform, shell,
    path separators) and confirm rather than ask cold; also ask if the team is mixed-OS. Sets
    `windows`/`posix`, gating hook flavor and settings lines - get it wrong and guardrails never fire,
    silently.

## Batch C - git and CI

11. **[CONFIRM - pass 10 of [`codebase-analysis.md`](codebase-analysis.md); chat for the bot sub-part]**
    **Git platform, review tooling, and commit identity.** Platform: GitHub / GitLab, cloud or
    self-hosted (ask which!) / Bitbucket / none. Self-hosted GitLab: capture the hostname and that CI
    secrets are masked + protected. Identity: name/email on THAT platform - a wrong email misattributes
    commits. Also: does a bot hold commit/merge rights on the default branch (Dependabot, Renovate,
    auto-merge)? No var - into `known-issues.md`, and a `merge-manager` exception if that agent is
    fielded.

    **Confirm the platform whenever pass 10 was not conclusive, and confirm the CLI always.** Detection
    is evidence, not permission: a repo can host on GitHub while the team opens every PR in the browser.
    The answer sets how every seat is told to open and merge a change, so a wrong guess here is a
    workflow the team does not use.

    | Answer | `{{GIT_PLATFORM}}` | `{{PR_OR_MR}}` | `{{PR_CLI}}` | `{{CI_STATUS_CMD}}` | flag |
    |---|---|---|---|---|---|
    | GitHub, `gh` installed and authenticated | `GitHub` | `PR` | `gh pr` | `gh pr checks` | `pr_cli` |
    | GitLab, `glab` installed and authenticated | `GitLab` | `MR` | `glab mr` | `glab ci status` | `pr_cli` |
    | Bitbucket | `Bitbucket` | `PR` | `-` | `-` | none |
    | Platform, but no CLI (absent, logged out, or the team prefers the browser) | the platform | `PR`/`MR` | `-` | `-` | none |
    | No platform, local git only | `none` | `PR` | `-` | `-` | none |

    `{{PR_CLI}}` is a command PREFIX: `gh pr` and `glab mr` both take `create`, `list`, `view` and
    `merge` after it, so one variable covers four operations. CI status has a different shape, hence
    its own variable.

    **Bitbucket has no first-party CLI of this shape** - `gh` and `glab` are vendor-published,
    Atlassian ships no equivalent, and the community wrappers are unmaintained. Do not invent a
    `bb pr create`. The no-CLI path is a real workflow, not a degraded one: push the branch and hand
    the human the "create a pull request" URL that all three platforms print on first push. Do not
    route around it with `curl` against the REST API - that needs an app password, and a seat holding
    a platform credential is what `protect-secrets` and the deny rules exist to prevent.
12. **[CONFIRM - `git symbolic-ref`/remote HEAD + `git log`; chat for the scope list]** **Default
    branch and commit convention.** Branch: default `main`, naming `feat/fix/chore/...` - feeds
    `guard-main-commit`. Convention: Conventional Commits is default - confirm the type list
    (feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert) and the PROJECT-SPECIFIC scope list
    from Batch A/B's feature areas: one per module or FR area, plus `specs`, `agents`, `infra`. Subject
    limit 72 chars, imperative lowercase.

## Batch D - quality and safety

**Roster shape - [AQ, 3 questions, one call, asked alongside the roster/preset step].** The user, not
the preset table, decides how heavy the agent team is. Echo the resulting roster afterwards.
- **Project horizon** - Short and focused (Recommended below preset L) / Long-term, multi-week (flag
  `long`: adds `brainstormer` + `tech-researcher` for decision work and `history-tracker` to curate
  the run archive - seats that only pay off on a project long enough to forget its own decisions).
- **Role granularity** - Split reviewers (Recommended for M/L: `code-reviewer` + `security-reviewer`,
  two independent passes catch more) / One merged `reviewer` (flag `solo_review`: one pass, both
  lenses - the lean choice for preset S and solo work).
- **Priority** - Speed / Balanced / Highest quality. Not a flag: steers the Q16 effort profile
  (Speed -> Economy, Highest quality -> Thorough) and how aggressively the roster is trimmed.
  Cross-reference, do not re-ask Q16.

13. **[AQ for what to automate; CONFIRM frameworks/commands - test config/`package.json` scripts]**
    **Testing.** First, what should agents automate?
    - **Unit + e2e (Recommended for products)** - flags `unit`, `e2e`, `tests`.
    - **Unit only** - flags `unit`, `tests`.
    - **E2e only** - flags `e2e`, `tests`; critical user journeys, no unit layer.
    - **None** - no flags: no `qa-test`, `/test`, or `rules/testing.md`; acceptance criteria are
      verified by hand and the session log records how. Honest for prototypes; revisit via
      `/harness-update`.
    Then, only for the selected kinds, frameworks and commands: suggest per stack from
    [`tech-presets.md`](tech-presets.md) (Vitest + Playwright for Vite-based JS/TS, Jest where
    already invested, pytest for Python - never one framework as universal), and CONFIRM the real
    test/lint/build commands from the repo's scripts.
14. **[AQ, "DDD (Recommended)" first; the TDD options are OFFERED ONLY IF Q13 chose a test kind]**
    **Development methodology** - how should the dev seats be disciplined? Purpose and cost of each,
    honestly.

    **Gate this question on Q13.** If Q13 answered "None", drop both TDD options from the list and
    offer only DDD and Lightweight, saying why in one line: test-first discipline cannot be applied
    to a project that automates no tests. The scaffolder enforces this (`tdd` requires `tests`) and
    fails the whole run, so offering the combination here is a dead end the user cannot escape
    without hand-editing `vars.json`. If the user wants TDD, that is a reason to go back and change
    Q13, not a reason to set both flags.
    - **DDD (Recommended)** (flag `ddd`) - `rules/ddd.md`: the spec glossary becomes the ubiquitous
      language, each dev agent's scope a bounded context, aggregate-root discipline applies. Tests
      ship in the same change, proving the acceptance criteria - not required first, which keeps
      delivery speed. Best default for products with a real domain.
    - **TDD** (flag `tdd`) - red/green/refactor, tests strictly first. Slower delivery, and be
      clear-eyed about what the order buys inside an agent loop: when the same agent writes the
      test, runs it red, and then writes the code, a red test proves it ran, not that it failed for
      the right reason. Published experiments comparing the two workflows found no advantage for
      test-first, and found tests that computed their expected value from the implementation in
      BOTH arms. Pick it when a human reviews each failing test before implementation, or when an
      external mandate requires test-first. Not because it is the stricter-sounding option.
    - **TDD + DDD** (both flags) - the strictest and slowest posture; the two can pull against each
      other (test-first pacing vs model-first design), so choose it deliberately, never as default.
    - **Lightweight** (flag `light`) - no methodology rule installed; small commits, working
      software first, minimal ceremony. The review gate and guardrail hooks stay - lightweight
      loosens process, never safety. For prototypes, spikes, and solo velocity.
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
    support, and backup/restore expectation (RPO/RTO, or "none defined"). No var - into
    `security-privacy.md`'s "Retention and egress", or `known-issues.md` if unknown; record "no
    regime" too, so the gap stays visible.
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
    observability stack (logs/metrics/traces); feature-flag mechanism; incident severity ladder -
    who is paged, at what severity; any cloud/infra budget ceiling bounding `devops`'s
    recommendations. No var - feeds `tech-stack.md`; broadens `{{INCIDENT_CONTACT}}` (Q27).
18. **[AQ for deploy rights - no safe default even in express intake; chat for destructive commands, DB
    one CONFIRMED from Q20]** **Control level** - how much may agents do without a human in the loop?
    - **Deployment rights** - three answers:
      - **Human-only (Recommended)** - `{{DEPLOY_CMD}}` sits in `permissions.deny`; `/deploy`
        prepares and verifies but a human runs the command. No flag.
      - **Agent, with approval** (flag `deploy_ask`) - `{{DEPLOY_CMD}}` moves from `deny` to `ask`:
        every invocation stops for an explicit yes. Confirm the approver's normal availability/
        timezone - an unanswered `ask` gate is a stall, not a control.
      - **Agent, non-prod only** - production command stays in `deny`, staging command goes in
        `allow`; the two commands must actually differ, so confirm both.
    - **Destructive commands** - confirm the deny list covers this stack's real reset/force commands
      (Q20 collects the DB one); ask if there are others (infra teardown, queue purge).
    - Every dial here is changeable later with `/harness-tune` - a starting posture, not a permanent
      one.
**Optional add-ons - [AQ, multi-select, both default OFF].** Two independent opt-ins that
    wrap other people's work. Both are credited in the README, both ship off unless chosen, and
    either can be turned off later with `/harness-toggle` rather than a re-scaffold. Offer them,
    do not assume them - and state the cost, because neither is free.
    - **Terser answers** (flag `terse`) - ships `rules/output-style.md`, adapted from the
      MIT-licensed `i-have-adhd` ruleset: answers lead with the next action instead of a preamble,
      multi-step work gets numbered, lists stay short. Be honest about the trade: this SPENDS
      context rather than saving it, roughly 1,700 tokens per session, to make what comes back
      easier to act on. It cannot be path-scoped because it shapes every answer, so it is a
      7th always-loaded rule.
    - **Smaller command output** (flag `rtk`) - ships `hooks/rtk-rewrite.{sh,ps1}`, a wrapper
      around the Apache-2.0 `rtk` binary that rewrites a Bash command into a form whose output is
      smaller (`git log -30` measured at 17,653 chars to 6,380). The binary is NOT bundled: the
      user installs it themselves and the hook stays silent when it is absent, so choosing this
      never breaks a machine that lacks it. The wrapper refuses to hand rtk any command our own
      guards inspect. Mention that rtk has a telemetry endpoint compiled in, off by default, and
      that the generated `settings.json` sets `RTK_TELEMETRY_DISABLED=1` as a second lock.

## Batch E - database operations and seed data

Ask only if Batch B has a DB.

19. **[AQ multi-select for the agent set; chat for seed sub-parts if `db-seeder` is chosen]** **DB
    agents and seed policy.** Which DB agents: `data-modeler` (schema design - the `db` flag alone
    ships only this seat), `db-engineer` (migrations, query/index tuning, local docker - flag
    `db_engineer`), `db-seeder` + `/seed-db` (synthetic data for dev/demo/test - flag `db_seeder`).
    Start with `data-modeler` alone unless migration or seed work already exists. If seeding is
    chosen: seed-target environments (local docker / shared dev / staging), default seed scope
    (entities + volumes), locale mix, and the synthetic-only policy - real data never enters seeds,
    prod is never a target.
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
default** - each is a policy position only the org can hold, and a plausible invented one is worse
than a blank, because it will be believed. If the user does not know, say so and register a task. All
four are **[chat]** - open text, not an enumerable choice.

24. **Model sovereignty** - per data class the project actually handles (Public / Internal /
    Confidential / Restricted), which model or provider may process it? Self-hosted, a specific
    vendor under contract, or none. **"None" is a valid and common answer for Restricted** - that
    work is simply not delegated to an agent. Fills `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`,
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

The scaffolder (`../scripts/scaffold.py`) consumes `vars.json`. Every question lands in exactly one
variable or flag; the remaining variables come from the analysis.

| Answer | Goes to |
|---|---|
| 1 project name, domain, purpose | `{{PROJECT_NAME}}`, `{{PROJECT_SLUG}}` (kebab-case of the name, used in `.env.example`), `{{DOMAIN}}`, `{{DOMAIN_DESCRIPTION}}` |
| 2 docs language | `{{DOC_LANGUAGE}}` - recorded in `docs/README.md`; authored `docs/` prose only |
| 3 specs exist | `{{FR_LIST}}` (from the specs, if any); otherwise the `spec-builder` handoff |
| target AI tools (Batch A) | no var - drives whether step 8 ports to Cursor / Codex via `port.py` |
| 4 language/framework | `{{SOURCE_GLOBS}}` shape; `tech-stack.md` body; version per [`tech-presets.md`](tech-presets.md), never from memory |
| 5 database + ORM | flag `db`, `{{ORM}}`, `{{DB_GLOBS}}` |
| 6 providers / hosting / fallback / update cadence | flag `ai`, `{{HOSTING}}`; fallback/cadence - no var, into `tech-stack.md` and `testing.md`'s provider-wrapper practice |
| 7 product internationalization | no var - into `tech-stack.md`/`coding-standards.md`; DB character-set choice in `data-model.md` |
| 8 environments, ownership, and configuration | `.env.example` groups (authored, not templated) |
| 9 authorization model and tenancy | no var - into `data-model.md`'s entity notes; a break-glass path becomes a `settings.json` entry |
| 10 dev OS | flag `windows` or `posix`; `{{HOOK_RUNNER}}`/`{{HOOK_EXT}}` are DERIVED from the flag by the scaffolder - do not set them in vars.json |
| 11 git platform + review tooling + commit identity + CI bots | `{{PR_OR_MR}}`, `{{CI_PLATFORM}}`, `{{GIT_PLATFORM}}`, `{{PR_CLI}}`, `{{CI_STATUS_CMD}}`; flag `pr_cli` when a CLI was chosen; identity: no var; bot answer: no var, `known-issues.md` + merge-manager exception if fielded. `{{PR_CLI}}` and `{{CI_STATUS_CMD}}` take `-` on the no-CLI path and MUST still be set - the scaffolder fails on an unresolved variable |
| 12 default branch + commit convention | `{{DEFAULT_BRANCH}}`; `{{COMMIT_TYPES}}`, `{{COMMIT_SCOPES}}` |
| roster shape (asked with the preset step) | flags `long`, `solo_review`; priority answer steers Q16; `{{AGENT_ROSTER_TABLE}}` (the confirmed roster, rendered as the AGENTS.md table) |
| 13 testing choice + frameworks + commands | flags `unit`, `e2e`, `tests`; `{{UNIT_FRAMEWORK}}`, `{{E2E_FRAMEWORK}}`, `{{TEST_CMD}}`, `{{LINT_CMD}}`, `{{BUILD_CMD}}`, `{{COVERAGE_TARGET}}`, `{{TEST_GLOBS}}` (framework vars only for selected kinds; unselected take `-`) |
| 14 methodology | flags `tdd`/`ddd`/`light` - `ddd` ships `rules/ddd.md` plus the bounded-context blocks in `/implement-fr` and the dev agents; `tdd` ships NO file, only the tests-first blocks in `testing.md`, `00-overview.md`, `/implement-fr`, `qa-test`, `AGENTS.md`. What a test is FOR is unconditional (`rules/testing.md`), because the tautology it prevents is not an ordering problem |
| 15 data sensitivity + compliance regime + lifecycle + AI product | `{{PII_OR_DATA}}`; flag `ai`; regime/lifecycle - no var, into `security-privacy.md` or `known-issues.md` |
| 16 effort profile | no var - the roster allocation; record the choice in `docs/context/tool-changelog.md` |
| agent history detail (asked with Q16) | `{{HISTORY_LEVEL}}`, `{{HISTORY_KEEP}}` - written to `.claude/state/history-level`, read by the `agent-history` hook. `HISTORY_KEEP` counts per-run files to retain; `0` means never prune (minimal/off write no per-run files, so 0 is their natural value) |
| 17 operations posture | no var - into `tech-stack.md`; broadens `{{INCIDENT_CONTACT}}` (set at Q27) |
| 18 control level | flag `deploy_ask`; extra deny entries for stack-specific destructive commands |
| optional add-ons (asked at the end of Batch D) | flags `terse` (ships `rules/output-style.md`) and `rtk` (ships `hooks/rtk-rewrite.{sh,ps1}` and sets `RTK_TELEMETRY_DISABLED=1` in settings.json). No vars. Both default OFF and are removable later with `/harness-toggle` |
| 19 DB agents + seed policy | flags `db_engineer`, `db_seeder` (with `db`, gate their seats and `/seed-db`); seed scope |
| 20 destructive DB command | `{{DB_RESET_CMD}}`, `{{DB_RESET_PATTERN}}` |
| 21-22 branding, icons, a11y | flag `ui`, `{{UI_GLOBS}}`; `rules/frontend.md` body |
| 23 audit scope | flag `audit`, `{{WORKSPACE_ROOT}}`, `{{REPO_DIR_LIST}}` |
| 24 model sovereignty | `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`, `{{MODEL_CONFIDENTIAL}}`, `{{MODEL_RESTRICTED}}` |
| 25 residency | `{{DATA_RESIDENCY}}` |
| 26 licences + ownership | `{{ALLOWED_LICENCES}}`, `{{DENIED_LICENCES}}`, `{{IP_OWNERSHIP_STATEMENT}}` |
| 27 gated actions + incident path | `{{GATED_ACTIONS}}`, `{{INCIDENT_CONTACT}}` (any production incident) |
| - dependency manifests (from analysis) | `{{DEP_MANIFEST_GLOBS}}` - EVERY manifest and lockfile the analysis actually found, per the ecosystem table in [`codebase-analysis.md`](codebase-analysis.md) pass 1, not just the first one. It path-scopes `rules/ip-compliance.md`; a glob that matches nothing means the licence rule never loads |
| - deploy command (from analysis or Q6) | `{{DEPLOY_CMD}}` |
| - glossary seed rows (from spec section 03 when spec-builder hands off; `-` if none) | `{{GLOSSARY_SEED}}` |
| - module paths, routing, dev agents | `{{MODULE_PATHS}}`, `{{ROUTING_TABLE}}`, `{{DEV_AGENT_NAME}}` - from the analysis |

Flags are exactly: `ui`, `db`, `db_engineer`, `db_seeder`, `ai`, `audit`, `tdd`, `ddd`, `light`,
`unit`, `e2e`, `tests`, `deploy_ask`, `long`, `solo_review`, `terse`, `rtk`, `pr_cli`, and exactly
one of `windows`/`posix`.
`ddd` is the default methodology; `tdd` is opt-in and `light` replaces both - never assumed. `tests`
is derived: set it whenever `unit` or `e2e` is set, never alone.

### Restricted data paths (asked whenever any class above is Restricted)

**Q: Where does Restricted data live in this repo, as glob patterns?**

This question turns the classification table from advice into enforcement: the answers become
`permissions.deny` entries on `Read(...)` - what an agent cannot read, it cannot send to any
provider.

- Format as ready-to-paste JSON array entries, each ending with a comma, for `{{RESTRICTED_DENIES}}`,
  e.g. `"Read(data/restricted/**)",` and `"Read(**/*.phi.json)",`.
- No Restricted data in the repo is a normal answer - use the convention placeholder
  `"Read(**/.restricted/**)",` so the slot stays valid JSON.
- **Never guess this.** A wrong glob is a control that looks present and is not. If the user does not
  know, record it in `docs/context/known-issues.md` and say the table is advisory until answered.

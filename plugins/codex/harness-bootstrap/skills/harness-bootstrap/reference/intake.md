# Intake - the questions the code cannot answer

Mandatory: a wrong answer is baked into every generated file. Afterwards echo a **one-screen setup
plan** - created, kept, modified, and the roster with each seat's model and effort - and get
confirmation before writing anything. Solo developer or below preset M: offer the express path first.

## Ask in the user's language

**Infer the language from how the user wrote to you, and ask every question in it** - question
text, option labels and option descriptions. Default to English only when the input is too short or
too mixed to tell. The interview language is inferred, never asked; it is separate from Q2, which
sets the language of the `docs/` prose and may differ.

Flag names, `{{VAR}}` names and every agent-facing file (`CLAUDE.md`, `AGENTS.md`, `.claude/*`) stay
English. Translate the question, not the value it records.

## Asking mechanics, and the express path

Tags: **AQ** = `AskUserQuestion` (closed choice, max 4 options, recommended first labeled
`"(Recommended)"`, up to 4 questions batched per call); **chat** = free-text in conversation;
**CONFIRM (source: X)** = [`codebase-analysis.md`](codebase-analysis.md) already answered it in
brownfield/audit - present the finding as default, get a one-line correct-or-confirm. Never assume
silently - if skipped, state the default you will use and why.

**Express intake ("use defaults"):** ask only what has **no safe default** - project identity (Q1),
the deployment-rights half of Q18, and all of Batch H (Q24-27). Everything else takes its stated
default (the CONFIRM finding, else the "Recommended" option); print the assumed defaults as ONE table
for confirmation before writing anything. Batch G (audit mode) is never express.

**Every skipped question must still yield a value.** Express mode changes who supplies the answer,
never whether there is one: a question with no CONFIRM finding and no "(Recommended)" option has no
express default, and its `{{VAR}}` stays unset - the scaffolder then fails after writing the tree.
Before scaffolding in express mode, confirm every row of the vars table below has a value.

## The initialisation questionnaire - two calls, pre-answered

The closed choices that shape the harness are asked as ONE questionnaire of at most two
`AskUserQuestion` calls, each with at most 4 questions of 2 to 4 options. Build every option list
from the analysis: the option the evidence supports goes first, labelled "(Recommended)", its
description quoting the evidence ("`playwright.config.ts` and 41 `*.spec.ts` files found"). **A
question the analysis settled with strong evidence is not asked** - it becomes a row in the plan echo.

**Call 1 - the shape of the harness**

| # | Question | Options (2-4), evidence-ordered | Sets |
|---|---|---|---|
| 1 | **Purpose** (multi-select) - what does this repo produce? | Code / Research / Strategy / Documentation - pass 0 pre-selects | `purpose_*` - see Q0 below |
| 2 | **Team shape** | code: Lean (one merged reviewer) / Standard (split reviewers) / Long-running (+ `strategist`, `researcher`, `history-tracker`) / High-throughput (Long-running + `merge-manager`). Non-code: Lean / Long-running | `solo_review`, `long`, `merge_gate` - replaces horizon, granularity and merging below |
| 3 | **Hook strictness** | Standard / Strict | `hooks_strict` - see Batch D |
| 4 | **Verification appetite** | code: Unit + e2e / Unit only / E2e only / None (Q13). Non-code: check every finished deliverable / check only what leaves the repo | `tests`, `unit`, `e2e`; non-code: recorded in `tool-changelog.md` |

Recommend from evidence: one module and one contributor is Lean; more than three modules or a CI
matrix is Standard; several ADRs or a roadmap is Long-running; more than a few open PRs a day is
High-throughput. Testing follows the test config found; with none, Unit + e2e for a product, None
for a prototype.

**Call 2 - policy, skills and only what Call 1 left open**

| # | Question | Options | Sets |
|---|---|---|---|
| 5 | **Deployment rights** (code repos with a deploy command; never defaulted) | Human-only / Agent with approval / Agent, non-prod only | `deploy_ask` - Q18 |
| 6 | **Methodology** (code repos; TDD options only when Call 1 chose a test kind) | DDD / TDD / TDD + DDD / Lightweight | `ddd`, `tdd`, `light` - Q14 |
| 7 | **Skills** (multi-select; skipped in audit mode) | Search and wire skills for these seats / Create a project skill for a recurring workflow (`/new-skill` after the scaffold) / Skip for now | runs step 2.5 of `SKILL.md`; nothing installs without a per-skill tick |
| 8 | **Effort profile** | Default / Economy / Thorough - Call 1's team shape picks the recommendation | Q16 |

A non-code repo drops 5 and 6, so its whole questionnaire is six questions. A third call is used
only for what detection could not settle and the user must decide: the DB seats (Q19), data
sensitivity (Q15), the optional add-ons. Agent-history detail, the doc language and the target
tools take their recommended values and appear in the plan echo, where one word changes them.

Free text never goes through `AskUserQuestion`: project identity, the commit identity, and all of
Batch H stay in chat.

## Q0 - what the repo is for (always first)

**[AQ, multi-select; CONFIRM in brownfield - pass 0 of [`codebase-analysis.md`](codebase-analysis.md)]**
Which of these does this repository exist to produce? One or more.

| Answer | flag | Seats it adds | Verification it adds |
|---|---|---|---|
| **Code (Recommended when the repo has source)** | `purpose_code` | the code roster ([`roster.md`](roster.md)) | tests, code + security review |
| **Research** - answers to questions, with evidence | `purpose_research` | `researcher`, `checker` | citations and sources |
| **Strategy** - decisions, options, recommendations | `purpose_strategy` | `strategist`, `researcher`, `checker` | assumptions and options |
| **Documentation** - a documentation set as the product | `purpose_docs` | `writer`, `checker` | accuracy, links, style |

No answer means `purpose_code` (the express default when source exists); a repo with no source is
asked, never defaulted. **The answer gates the interview:** without `purpose_code`, skip Batch B
except Q10, skip Q13-14, Batch E and the DB half of Q18, and set no code-only flag (`db*`, `ai`,
`tdd`, `ddd`, `light`, `unit`, `e2e`, `tests`, `solo_review`, `merge_gate`) - the scaffolder refuses
them. Their variables still need a value: `-` for every meaningless command, framework and glob
(`{{TEST_CMD}}`, `{{UNIT_FRAMEWORK}}`, `{{ORM}}`, `{{SOURCE_GLOBS}}`...), the docs lint or build
command in `{{LINT_CMD}}` / `{{BUILD_CMD}}` when one exists.

## Batch A - project identity

1. **[chat]** Project name, domain, one-line purpose. Brownfield: suggest a manifest's `name` or the
   repo directory, never assume it silently.
2. **[AQ, the inferred interview language first, labeled "(Recommended)"]** **Documentation
   language** for `docs/` content (Vietnamese / Japanese / English / other). Agent-facing files,
   codes, enums and filenames stay English. `docs/README.md` records the choice. **Always resolves to
   a value**, express included: `{{DOC_LANGUAGE}}` has no scaffolder default.
3. **[CONFIRM - presence of `docs/specs/`]** Do specs already exist? If not, invoke `spec-builder` via
   the `Skill` tool first (state the handoff if unavailable). **Hand it the confirmed `purpose_*`
   flags as settled**, so it writes them into its own `vars.json` and never asks again: without
   `purpose_code` it scaffolds the light contract (README, 05, 11, 13), with it the full set. When
   spec-builder ran first, read its `vars.json` flags and treat Q0 as answered - confirm in the plan.

**Q3a - Target AI tools - [AQ, multi-select; CONFIRM - pass 9 of
[`codebase-analysis.md`](codebase-analysis.md)].** Which tools must this harness run in? Decides
whether step 8 ports via `port.py`, and is **recorded**, so `/harness-update` re-ports without asking.

**Pre-select only the Strong rows of pass 9's evidence table, and always confirm.** Detection is
evidence, not permission. A Weak or None finding pre-selects nothing (Cursor reads `.claude/` and
`CLAUDE.md` natively, so a `.claude/` directory proves nothing).

| Answer | flags | `{{TARGET_TOOLS}}` | Step 8 runs |
|---|---|---|---|
| Claude Code only | none | `Claude Code` | nothing - no port step |
| Claude Code + Cursor | `target_cursor` | `Claude Code, Cursor` | `port.py --tool cursor` |
| Claude Code + Codex | `target_codex` | `Claude Code, Codex` | `port.py --tool codex` |
| All three | `target_cursor` + `target_codex` | `Claude Code, Cursor, Codex` | `port.py --tool all` |

Claude Code is always a target and has no flag: the harness is generated for it and the others are
ports, so "Cursor only" cannot be produced. Changing targets later is a `vars.json` edit plus
`/harness-update`. **Always resolves to a value**: `{{TARGET_TOOLS}}` has no scaffolder default; the
express default is the first row.

**State the losses now, at the point of choosing:**
- `maxTurns` has **no equivalent in either tool** - the circuit breaker on a looping agent is lost.
- Per-seat `tools:` allowlists have **none either**; Cursor's `readonly` covers only the reviewer case.
- Codex has **no path-scoped rules** - only nested `AGENTS.md`. The 7 unconditional rules survive as
  prose; the 10 path-scoped ones become advice someone has to ask for.
- `guard-agent-spawn` ports to neither; the roster becomes rules text, not an enforced control.
- Cursor's ADR guard fires **after** the edit; Codex routes edits through `apply_patch`, so its ADR
  guard is best-effort.

Prerequisite: Codex loads a project-local `.codex/` only when the project is trusted, and
non-managed hooks need a hash-pinned review through `/hooks`; until then the ported guards are inert.

## Batch B - tech stack

4. **[CONFIRM - manifests/lockfiles]** Language / framework (or "TBD via ADR"). Greenfield: propose
   from [`tech-presets.md`](tech-presets.md) under its currency rule. Brownfield: the analysis wins
   (tech-presets.md, "Greenfield vs brownfield").
5. **[CONFIRM - schema/ORM config files]** **Database + ORM** (e.g. PostgreSQL + Prisma / MySQL /
   MongoDB / none).
6. **[CONFIRM queue/integrations - analysis; chat for hosting, fallback and update cadence]**
   Async/queue layer, external providers (LLM gateway? OCR? storage?), hosting target. Per
   load-bearing integration: the fallback when down (documented / queued retry / hard failure) and
   the update cadence (Dependabot/Renovate or manual). If Q15 named SOC2, ISO 27001 or PCI-DSS,
   confirm any SBOM requirement.
7. **[AQ - single-locale default, no follow-up; chat sub-parts if multi-locale]** **Product
   internationalization.** Does the product (not `docs/`, see Q2) serve more than one user-facing
   language? If yes: locales, RTL need, timezone/currency/date convention, DB character set.
8. **[CONFIRM - `.env*` + CI config; chat for auth/SSO if not evident]** **Environments and
   configuration** - which environments exist (local / dev / staging / production), who owns each,
   where secrets live per environment, and any auth/SSO providers.
9. **[AQ, 3 options, "RBAC (Recommended)" first; chat sub-parts if multi-tenant]** **Authorization
   model and tenancy.** RBAC (role-based) / ABAC (record-attribute based) / ownership-only (no
   roles, own data only). If multi-tenant: isolation strategy (row-level tenant column /
   schema-per-tenant / DB-per-tenant) and any break-glass admin path - who, and is it logged.
10. **[AQ, auto-detected value first]** **Dev OS** - auto-detect (platform, shell, path separators)
    and confirm; ask whether the team is mixed-OS. Sets `windows`/`posix` (SKILL.md step 3).

## Batch C - git and CI

11. **[CONFIRM - pass 10 of [`codebase-analysis.md`](codebase-analysis.md); chat for the bot sub-part]**
    **Git platform, review tooling, and commit identity.** Platform: GitHub / GitLab, cloud or
    self-hosted (ask which!) / Bitbucket / none. Self-hosted GitLab: capture the hostname and that CI
    secrets are masked + protected. Identity: name/email on THAT platform. Also: does a bot hold
    commit/merge rights on the default branch (Dependabot, Renovate, auto-merge)?

    **Confirm the platform whenever pass 10 was not conclusive, and always confirm the CLI** - a repo
    can host on GitHub while the team opens every PR in the browser.

    | Answer | `{{GIT_PLATFORM}}` | `{{PR_OR_MR}}` | `{{PR_CLI}}` | `{{CI_STATUS_CMD}}` | flag |
    |---|---|---|---|---|---|
    | GitHub, `gh` installed and authenticated | `GitHub` | `PR` | `gh pr` | `gh pr checks` | `pr_cli` |
    | GitLab, `glab` installed and authenticated | `GitLab` | `MR` | `glab mr` | `glab ci status` | `pr_cli` |
    | Bitbucket | `Bitbucket` | `PR` | `-` | `-` | none |
    | Platform, but no CLI (absent, logged out, or the team prefers the browser) | the platform | `PR`/`MR` | `-` | `-` | none |
    | No platform, local git only | `none` | `PR` | `-` | `-` | none |

    `{{PR_CLI}}` is a command PREFIX (`create`, `list`, `view`, `merge` follow it); CI status has its
    own variable.

    **Bitbucket has no first-party CLI of this shape** - never invent a `bb pr create`. The no-CLI path
    is a real workflow: push the branch and hand the human the "create a pull request" URL the push
    prints. Never route around it with `curl` against the REST API - a seat holding a platform
    credential is what `protect-secrets` and the deny rules prevent.
12. **[CONFIRM - `git symbolic-ref`/remote HEAD + `git log`; chat for the scope list]** **Default
    branch and commit convention.** Branch: default `main`, naming `feat/fix/chore/...` - feeds
    `guard-main-commit`. Convention: Conventional Commits is default - confirm the type list
    (feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert) and the PROJECT-SPECIFIC scope list
    from Batch A/B's feature areas: one per module or FR area, plus `specs`, `agents`, `infra`. Subject
    limit 72 chars, imperative lowercase.

## Batch D - quality and safety

**Roster shape - [AQ, asked as Call 1's "Team shape" and "Hook strictness"].** What those options
set (not asked one by one); echo the resulting roster afterwards:
- **Project horizon** - Short (Recommended below preset L) / Long-term, multi-week (flag `long`:
  adds `strategist` + `researcher` and `history-tracker`).
- **Role granularity** (code only) - Split reviewers (Recommended for M/L: `code-reviewer` +
  `security-reviewer`) / One merged `reviewer` (flag `solo_review`, for preset S and solo work).
- **Merging** (code only) - The human merges (Recommended) / A delegated `merge-manager` (flag
  `merge_gate`: a steady stream of parallel PRs, with the strict gate in `roster.md`).
- **Hook strictness** - Standard (Recommended) / Strict (flag `hooks_strict`: also blocks large or
  binary commits, uploads to hosts outside `.claude/hooks/egress-allowlist`, unpinned dependency
  installs, pasted secrets, mid-session settings changes that weaken the harness, and a "done" with
  no evidence). The destructive-command guard (`rm -rf` on the repo, force push to a protected
  branch, `git reset --hard`, a remote DROP) ships in both.
- **Priority** - Speed / Balanced / Highest quality. Not a flag: steers Q16 (Speed -> Economy,
  Highest quality -> Thorough) and roster trimming. Do not re-ask Q16.

13. **[AQ for what to automate; CONFIRM frameworks/commands - test config/`package.json` scripts]**
    **Testing.** First, what should agents automate?
    - **Unit + e2e (Recommended for products)** - flags `unit`, `e2e`, `tests`.
    - **Unit only** - flags `unit`, `tests`.
    - **E2e only** - flags `e2e`, `tests`; critical user journeys, no unit layer.
    - **None** - no flags: no `qa-test`, `/test`, or `rules/testing.md`; criteria are verified by
      hand and the session log records how. Honest for prototypes.
    Then, for the selected kinds only, suggest frameworks per stack from
    [`tech-presets.md`](tech-presets.md) and CONFIRM the real test/lint/build commands from the
    repo's scripts.
14. **[AQ, "DDD (Recommended)" first; the TDD options ONLY IF Q13 chose a test kind]**
    **Development methodology.** If Q13 answered "None", offer only DDD and Lightweight and say why:
    the scaffolder refuses `tdd` without `tests`. Wanting TDD means revisiting Q13.
    - **DDD (Recommended)** (flag `ddd`) - `rules/ddd.md`: the spec glossary is the ubiquitous
      language, each dev scope a bounded context, aggregate-root discipline. Tests ship in the same
      change, not first. Best default for products with a real domain.
    - **TDD** (flag `tdd`) - red/green/refactor, tests strictly first, slower delivery. In an agent
      loop a red test written by the same agent proves it ran, not that it failed for the right
      reason; published comparisons found no advantage for test-first. Pick it when a human reviews
      each failing test first, or an external mandate requires it.
    - **TDD + DDD** (both flags) - the strictest and slowest; choose deliberately, never as default.
    - **Lightweight** (flag `light`) - no methodology rule; small commits, minimal ceremony. The
      review gate and guardrail hooks stay. For prototypes, spikes and solo velocity.
15. **[AQ, 3 sub-parts, one call; chat for lifecycle follow-up if a regime is named]** **Data
    sensitivity, compliance regime, and AI product.**
    - PII or regulated data (sets the strictness of `security-privacy.md`, `/secret-scan`'s PII
      patterns and the synthetic-data rule)?
    - Compliance regime, if any (multi-select, 4 named + "other"): GDPR/CCPA, HIPAA/PCI-DSS, SOC2/ISO
      27001, Japan's APPI (個人情報保護法) and Vietnam's Decree 13. "None identified" is valid.
    - AI product, LLM output shown to users (human-in-the-loop and prompt-injection guardrails)?

    If a regime was named: ask (chat, never defaulted) retention period per class, deletion/erasure
    support, and backup/restore expectation (RPO/RTO, or "none defined"). Record "no regime" too.
16. **[AQ, 3 options, "Default (Recommended)" first]** **Effort profile** - cost vs depth.
    - **Default (Recommended)** - the allocation in [`roster.md`](roster.md) as written.
    - **Economy** - non-gate seats one effort level down, mechanical seats at `haiku`+`low`. Never
      the review, debug or orchestration gates.
    - **Thorough** - dev seats at `xhigh` for a known-hard codebase; gates unchanged.

    **[AQ, 4 options, batched with Q16]** **Agent-run history detail** - how much of each finished
    subagent run the `agent-history` hook archives under `.claude/state/history/`:
    - **summary (Recommended)** - per-run file, prompt/response truncated to 1500 chars, newest 200
      kept.
    - **full** - whole prompt and final response per run. Note: PII in prompts lands on disk.
    - **minimal** - one index line per run, no per-run files.
    - **off** - no archive; the unlogged-completion sweep loses its evidence source.
    Changed later with `/harness-tune` dial 6.
17. **[chat]** **Operations posture.** Uptime target ("best effort" is honest); observability stack;
    feature-flag mechanism; incident severity ladder - who is paged, at what severity; any
    cloud/infra budget ceiling bounding `devops`'s recommendations.
18. **[AQ for deploy rights - no safe default even in express intake; chat for destructive commands, DB
    one CONFIRMED from Q20]** **Control level** - how much may agents do without a human in the loop?
    - **Deployment rights** - three answers:
      - **Human-only (Recommended)** - `{{DEPLOY_CMD}}` sits in `permissions.deny`; `/deploy`
        prepares and verifies but a human runs the command. No flag.
      - **Agent, with approval** (flag `deploy_ask`) - `{{DEPLOY_CMD}}` moves from `deny` to `ask`.
        Confirm the approver's availability - an unanswered `ask` gate is a stall.
      - **Agent, non-prod only** - production command stays in `deny`, staging command goes in
        `allow`; the two commands must actually differ, so confirm both.
    - **Destructive commands** - confirm the deny list covers this stack's real reset/force commands
      (Q20 collects the DB one); ask if there are others (infra teardown, queue purge).
    - Every dial here is changeable later with `/harness-tune`.
**Optional add-ons - [AQ, multi-select, both default OFF].** Two opt-ins wrapping other people's
    work, credited in the README, removable later with `/harness-toggle`. State the cost of each:
    - **Terser answers** (flag `terse`) - ships `rules/output-style.md`, adapted from the
      MIT-licensed `i-have-adhd` ruleset: answers lead with the next action, multi-step work is
      numbered, lists stay short. It SPENDS context, roughly 1,700 tokens per session, as a 7th
      always-loaded rule (it shapes every answer, so it cannot be path-scoped).
    - **Smaller command output** (flag `rtk`) - ships `hooks/rtk-rewrite.{sh,ps1}`, a wrapper
      around the Apache-2.0 `rtk` binary that rewrites a Bash command so its output is smaller
      (`git log -30`: 17,653 chars to 6,380). The binary is NOT bundled; the hook stays silent
      without it. The wrapper never hands rtk a command our own guards inspect (`git commit`,
      `git push`, anything naming a `.env`). rtk has a telemetry endpoint compiled in, off by
      default; `settings.json` also sets `RTK_TELEMETRY_DISABLED=1`.

## Batch E - database operations and seed data

Ask only if Batch B has a DB.

19. **[AQ multi-select for the agent set; chat for seed sub-parts if `db-seeder` is chosen]** **DB
    agents and seed policy.** `data-modeler` (schema design; the `db` flag alone ships only this),
    `db-engineer` (migrations, query/index tuning, local docker), `db-seeder` + `/seed-db` (synthetic
    data). Start with `data-modeler` alone unless migration or seed work already exists. If seeding:
    target environments (local docker / shared dev / staging), default scope (entities + volumes),
    locale mix. Real data never enters seeds; prod is never a target.
20. **[CONFIRM if the ORM from Q5 has a known reset convention; chat otherwise, never guess]** The real
    destructive DB command for this stack (`prisma migrate reset` / `rails db:reset` / `alembic
    downgrade`). It becomes a settings.json deny rule; never guess it.

## Batch F - branding and frontend

Ask only if the project has UI or document output (`ui` flag).

21. **[chat; CONFIRM existence - `public/brand/` or similar, if already present]** Official brand assets
    (logo files, dark-vs-light variants), fonts, palette - variant per background, self-hosted under
    `public/brand/`, aspect ratio, clear space, alt text.
22. **[AQ, recommended defaults first]** Icon/emoji policy (default: no emoji, SVG icons) and
    accessibility target (default WCAG 2.1 AA).

## Batch G - audit mode only

Ask only when agents never modify source. See [`audit-mode.md`](audit-mode.md). Not eligible for
express intake - scope cannot be defaulted.

23. **[chat for repo list/standards; AQ for scanner strategy, "Docker (Recommended)" first]** Which
    repos are in scope, relative to the workspace root; standards per repo; the scanner strategy (host /
    Docker / config-only); the severity scale; and who applies fixes.

## Batch H - governance (model sovereignty and IP)

Always asked, in full, even in express intake. **Never guess or generate a default** - each is a
policy position only the org can hold, and an invented one will be believed. If the user does not
know, say so and register a task. All four are **[chat]**.

24. **Model sovereignty** - per data class the project handles (Public / Internal / Confidential /
    Restricted), which model or provider may process it: self-hosted, a vendor under contract, or
    none. **"None" is valid and common for Restricted** - that work is not delegated to an agent.
25. **Residency** - which region or boundary must processing stay inside?
26. **Dependency licences** - which licence families are allowed and denied? Starting point to
    CONFIRM, not assume: allow MIT / BSD / Apache-2.0 / ISC; deny GPL / AGPL / SSPL / BSL / Commons
    Clause in a proprietary product. Also: who owns agent-authored code, in one sentence.
27. **Gated actions and the incident path** - which production actions may an agent or an in-product
    model never take unsupervised, and who is notified when something goes wrong in production (a
    shipped AI feature or any incident Q17's ladder describes)? One contact answers both unless the
    org runs a narrower AI-specific path - then name both.

## Intake answers to `vars.json`

The scaffolder (`../scripts/scaffold.py`) consumes `vars.json`. Every question lands in exactly one
variable or flag; the remaining variables come from the analysis.

| Answer | Goes to |
|---|---|
| 0 what the repo is for | flags `purpose_code`, `purpose_research`, `purpose_strategy`, `purpose_docs` (none means `purpose_code`); `checker` is derived from the non-code ones and never written |
| 1 project name, domain, purpose | `{{PROJECT_NAME}}`, `{{PROJECT_SLUG}}` (kebab-case of the name, used in `.env.example`), `{{DOMAIN}}`, `{{DOMAIN_DESCRIPTION}}` |
| 2 docs language | `{{DOC_LANGUAGE}}` - recorded in `docs/README.md`; authored `docs/` prose only |
| 3 specs exist | `{{FR_LIST}}` (from the specs, if any); otherwise the `spec-builder` handoff |
| 3a target AI tools | flags `target_cursor`, `target_codex` (Claude Code has no flag); `{{TARGET_TOOLS}}`, recorded in `docs/context/tool-changelog.md`. Drives step 8, and `/harness-update` reads it instead of re-asking |
| 4 language/framework | `{{SOURCE_GLOBS}}` shape; `tech-stack.md` body; version per [`tech-presets.md`](tech-presets.md), never from memory |
| 5 database + ORM | flag `db`, `{{ORM}}`, `{{DB_GLOBS}}` |
| 6 providers / hosting / fallback / update cadence | `{{HOSTING}}`; fallback/cadence - no var, into `tech-stack.md` and `testing.md`'s provider-wrapper practice |
| 7 product internationalization | no var - into `tech-stack.md`/`coding-standards.md`; DB character-set choice in `data-model.md` |
| 8 environments, ownership, and configuration | `.env.example` groups (authored, not templated) |
| 9 authorization model and tenancy | no var - into `data-model.md`'s entity notes; a break-glass path becomes a `settings.json` entry |
| 10 dev OS | flag `windows` or `posix`; `{{HOOK_RUNNER}}`/`{{HOOK_EXT}}` are DERIVED from the flag by the scaffolder - do not set them in vars.json |
| 11 git platform + review tooling + commit identity + CI bots | `{{PR_OR_MR}}`, `{{CI_PLATFORM}}`, `{{GIT_PLATFORM}}`, `{{PR_CLI}}`, `{{CI_STATUS_CMD}}` (both `-` on the no-CLI path, never unset); flag `pr_cli` when a CLI was chosen; identity: no var; bot answer: `known-issues.md` + a merge-manager exception if fielded |
| 12 default branch + commit convention | `{{DEFAULT_BRANCH}}`; `{{COMMIT_TYPES}}`, `{{COMMIT_SCOPES}}` |
| roster shape (asked with the preset step) | flags `long`, `solo_review`, `merge_gate`; priority answer steers Q16; `{{AGENT_ROSTER_TABLE}}` (the confirmed roster, rendered as the AGENTS.md table) |
| 13 testing choice + frameworks + commands | flags `unit`, `e2e`, `tests`; `{{UNIT_FRAMEWORK}}`, `{{E2E_FRAMEWORK}}`, `{{TEST_CMD}}`, `{{LINT_CMD}}`, `{{BUILD_CMD}}`, `{{TEST_GLOBS}}` (framework vars only for selected kinds; unselected take `-`) |
| 14 methodology | flags `tdd`/`ddd`/`light` - `ddd` ships `rules/ddd.md` plus the bounded-context blocks in `/implement-fr` and the dev agents; `tdd` ships NO file, only the tests-first blocks in `testing.md`, `00-overview.md`, `/implement-fr`, `qa-test`, `AGENTS.md` |
| 15 data sensitivity + compliance regime + lifecycle + AI product | `{{PII_OR_DATA}}`; flag `ai`; regime/lifecycle - no var, into `security-privacy.md` or `known-issues.md` |
| 16 effort profile | no var - the roster allocation ([`cost-model.md`](cost-model.md) has the reasoning); record the choice in `docs/context/tool-changelog.md` |
| agent history detail (asked with Q16) | `{{HISTORY_LEVEL}}`, `{{HISTORY_KEEP}}` (200 for summary/full, 0 = never prune for minimal/off) - written to `.claude/state/history-level` |
| 17 operations posture | no var - into `tech-stack.md`; broadens `{{INCIDENT_CONTACT}}` (set at Q27) |
| 18 control level | flag `deploy_ask`; extra deny entries for stack-specific destructive commands; non-prod-only puts the staging command in `allow` |
| optional add-ons (asked at the end of Batch D) | flags `terse` (ships `rules/output-style.md`) and `rtk` (ships `hooks/rtk-rewrite.{sh,ps1}` and sets `RTK_TELEMETRY_DISABLED=1` in settings.json). No vars. Both default OFF and are removable later with `/harness-toggle` |
| 19 DB agents + seed policy | flags `db_engineer`, `db_seeder` (with `db`, gate their seats and `/seed-db`); seed scope |
| 20 destructive DB command | `{{DB_RESET_CMD}}`, `{{DB_RESET_PATTERN}}` (its deny rule ships only with `db`) |
| 21-22 branding, icons, a11y | flag `ui`, `{{UI_GLOBS}}`; `rules/frontend.md` body |
| 23 audit scope | flag `audit`, `{{WORKSPACE_ROOT}}`, `{{REPO_DIR_LIST}}` |
| 24 model sovereignty | `{{MODEL_PUBLIC}}`, `{{MODEL_INTERNAL}}`, `{{MODEL_CONFIDENTIAL}}`, `{{MODEL_RESTRICTED}}` |
| 25 residency | `{{DATA_RESIDENCY}}` |
| 26 licences + ownership | `{{ALLOWED_LICENCES}}`, `{{DENIED_LICENCES}}`, `{{IP_OWNERSHIP_STATEMENT}}` |
| 27 gated actions + incident path | `{{GATED_ACTIONS}}`, `{{INCIDENT_CONTACT}}` (any production incident) |
| - dependency manifests (from analysis) | `{{DEP_MANIFEST_GLOBS}}` - EVERY manifest and lockfile found (pass 1 of [`codebase-analysis.md`](codebase-analysis.md)). It path-scopes `rules/ip-compliance.md`; a glob matching nothing means the licence rule never loads |
| - deploy command (from analysis or Q6) | `{{DEPLOY_CMD}}` |
| - glossary seed rows (from spec section 03 when spec-builder hands off; `-` if none) | `{{GLOSSARY_SEED}}` |
| - module paths, routing, dev agents | `{{MODULE_PATHS}}`, `{{ROUTING_TABLE}}`, `{{DEV_AGENT_NAME}}` - from the analysis |
| - per-module guidance (from the analysis, no question) | the `modules` list in `vars.json`: one `{path, owner, invariants, commands}` per module or large directory, rendered into `<path>/CLAUDE.md` (40 lines at most) |

Flags are exactly: `purpose_code`, `purpose_research`, `purpose_strategy`, `purpose_docs`, `ui`,
`db`, `db_engineer`, `db_seeder`, `ai`, `audit`, `tdd`, `ddd`, `light`, `unit`, `e2e`, `tests`,
`deploy_ask`, `long`, `solo_review`, `merge_gate`, `hooks_strict`, `terse`, `rtk`, `pr_cli`, `target_cursor`,
`target_codex`, and exactly one of `windows`/`posix`. `checker` is derived, never written.
`ddd` is the default methodology; `tdd` is opt-in and `light` replaces both - never assumed. `tests`
is derived: set it whenever `unit` or `e2e` is set, never alone.

### Restricted data paths (asked whenever any class above is Restricted)

**Q: Where does Restricted data live in this repo, as glob patterns?**

The answers become `permissions.deny` entries on `Read(...)`: what an agent cannot read, it cannot
send to any provider.

- Format as ready-to-paste JSON array entries, each ending with a comma, for `{{RESTRICTED_DENIES}}`,
  e.g. `"Read(data/restricted/**)",` and `"Read(**/*.phi.json)",`.
- No Restricted data in the repo is a normal answer - use the convention placeholder
  `"Read(**/.restricted/**)",` so the slot stays valid JSON.
- **Never guess this** - a wrong glob is a control that looks present and is not. If unknown, record
  it in `docs/context/known-issues.md` and say the table is advisory until answered.

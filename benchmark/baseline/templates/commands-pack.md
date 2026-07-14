# Commands pack (project-bootstrap)

Skeletons for the standard slash commands under `.claude/commands/<name>.md`. Fill `{{...}}`;
rename `review-mr`/`review-pr` and use MR/PR wording per the git platform answer - command NAMES
are platform-specific. Generate the core set always; DB and deploy commands only when applicable;
add domain commands per feature (e.g. a "run the pipeline on a sample input" command per FR).

Frontmatter fields: `description` (one line, shown in the command list), optional `argument-hint`,
optional `allowed-tools` (least privilege for the command).

---

## implement-fr (core - the standard feature flow)

```markdown
---
description: Plan and implement a functional requirement end-to-end per acceptance criteria.
argument-hint: <FR-id> (e.g. FR-03)
---

Implement functional requirement **$1**.

1. Read FR $1 in `docs/specs/05-functional-requirements.md`: input/output, business rules,
   acceptance criteria, use case.
2. Use the `spec-guardian` agent to lock down the scope and criteria.
3. Assign the specialist agent per the `orchestrator` routing table: {{FR_ROUTING_SUMMARY}}.
   Implement using TDD (tests first, coordinate with `qa-test`).
4. Comply with `.claude/rules/` {{IF_AI_PRODUCT}}(especially human-in-the-loop).
5. Run `/test`. Then run `/review-{{PR_OR_MR_SLUG}}`.
6. Do NOT deploy. Summarize the acceptance criteria that have been met.
```

## review-mr / review-pr (core - the review gate)

```markdown
---
description: Run code review + security review on the current diff.
allowed-tools: Bash(git diff:*), Bash(git status), Bash(git log:*)
---

Review the current changes before opening/merging a {{PR_OR_MR}}.

1. Get the diff: `git diff` (and `git diff --staged`).
2. Run `/secret-scan` - any real secret/{{PII_OR_DATA}} in the diff is a blocker; stop until
   removed and rotated.
3. Assign `code-reviewer`: coding standards + rules + commit messages on the branch
   (`git log origin/{{DEFAULT_BRANCH}}..HEAD --format=%s`) against `conventional-commits.md`.
4. Assign `security-reviewer`: {{PII_OR_DATA}}, secrets, guardrails, NFR-SEC.
5. Assign `spec-guardian`: verify acceptance criteria are met.
6. Aggregate findings by severity (blocker / should fix / suggestion). Do NOT merge, do NOT deploy.
```

## secret-scan (core - NEVER skip)

```markdown
---
description: Scan for secrets and {{PII_OR_DATA}} in the current changes before commit/{{PR_OR_MR}}.
allowed-tools: Bash(git diff:*), Bash(git status), Grep, Read
---

Scan the diff for: key/token patterns (sk-, AKIA, AIza, ghp_, glpat-, xox, JWT-shaped strings,
BEGIN PRIVATE KEY, hardcoded password=/api_key=), forbidden files (.env*, *.pem, *.key,
service-account JSON), and real-looking {{PII_OR_DATA}} in fixtures/seeds. Report file:line +
pattern TYPE only - never print the matched secret value. Any hit = blocker.
```

## new-task / task-resume (core - task control)

```markdown
---
description: Create a TASK from the template in docs/tasks.
argument-hint: <short-title>
---

1. Determine the next TASK-NNN (sequential across active/, pending/, done/).
2. Copy `docs/templates/TASK.md.template` to `docs/tasks/active/TASK-NNN-<slug>.md`; fill title,
   goal, owner agent, deps, priority, phase, created date, acceptance criteria; status: Active.
3. Add the row to the index table in `docs/tasks/master-plan.md`.
4. Append the first session-log row (task created and registered).
```

```markdown
---
description: Resume a task from its markdown task file (after compaction or in a new session).
argument-hint: <TASK-NNN> (omit to list all unfinished tasks)
---

1. If no argument: `grep -l "status: Active\|status: Blocked" docs/tasks/active/*.md` and list them.
2. Read `docs/tasks/master-plan.md` (position, deps, priority) and the task file (session log,
   decisions, blockers). Trust the files over conversation memory.
3. Verify the working tree (`git status` / `git diff`) - files record intent, the tree records
   reality. Then continue from the recorded state and keep logging.
```

## brainstorm / new-adr / new-spec-section / sync-context (core - decisions and docs)

```markdown
---
description: Run a structured brainstorming session on a decision or feature idea.
argument-hint: <topic>
---
Dispatch `brainstormer` (with `tech-researcher` for evidence): frame the decision, 3-5 options,
trade-off matrix, recommendation. User decides; stack-affecting outcome -> /new-adr; product
outcome -> PRD update.
```

```markdown
---
description: Create an Architecture Decision Record from the template.
argument-hint: <decision-title>
---
Next ADR-NNN from `docs/architecture/decisions/`; copy `docs/templates/ADR.md.template`; fill
context/decision/options/consequences (100% English); status Proposed until the user accepts;
Accepted ADRs are immutable (hook-enforced) - changes need a new ADR that supersedes.
```

```markdown
---
description: Scaffold a new BA documentation section following the project's standard structure.
---
Use the `ba-analyst` agent and the spec-builder skill conventions; log requirement changes in
`docs/specs/13-revision-history.md`.
```

```markdown
---
description: Update docs/context (business-rules, known-issues, tool-changelog) per recent changes.
---
Review the recent diff/merges; update `docs/context/business-rules.md` (behavior changes),
`known-issues.md` (new/fixed issues), `tool-changelog.md` (dependency/tool changes),
`domain-glossary.md` (new terms). Concise, dated entries.
```

## test (if qa-test accepted)

```markdown
---
description: Run unit + e2e tests.
allowed-tools: Bash({{TEST_CMD}}:*), Bash({{E2E_CMD}}:*)
---
Run {{TEST_CMD}} then {{E2E_CMD}}. All providers mocked - no real API calls. Report failures with
the owning agent for each.
```

## db-migration / seed-db (if DB)

```markdown
---
description: Generate a migration from schema changes, following the ERD/data dictionary.
---
1. Diff the schema against `docs/specs/08-data-model.md`; update the dictionary if the design is new.
2. Generate the migration ({{MIGRATE_DEV_CMD}}, LOCAL dev DB only).
3. Review the SQL: no DROP, no NOT-NULL-without-default, no data loss (else flag to the user).
4. Sync the seed script in the same {{PR_OR_MR}}. NEVER run reset/push against a shared DB.
```

```markdown
---
description: Seed the local/dev database with deterministic synthetic data per the ERD.
---
Dispatch `db-seeder` with the db-seed skill. Local/dev only; synthetic only; idempotent upserts;
verify row counts after.
```

## deploy-<hosting> (if hosting; GATED)

```markdown
---
description: Deploy to {{HOSTING}} (GATED - only after the {{PR_OR_MR}} has been reviewed and approved).
---
PRECONDITIONS (verify, refuse if unmet): {{PR_OR_MR}} approved and merged; pipeline green; env
vars present; migration status clean. Then: run forward migrations ({{MIGRATE_DEPLOY_CMD}}),
deploy via {{DEPLOY_MECHANISM}}, verify health endpoint, log the deploy in
`docs/context/tool-changelog.md`. NO automatic deploys - this command runs only on explicit user
request after approval.
```

## scaffold-feature (optional convenience)

```markdown
---
description: Create a skeleton for a feature module (handler + lib + component + test).
argument-hint: <feature-slug>
---
Create, following coding-standards structure: the route handler (validate + call lib only), the
lib module ({{LIB_DIR}}/<slug>/), {{IF_UI}}the component (from design-system primitives), and a
failing test naming the acceptance criteria. Register the owner agent mapping if a new domain.
```

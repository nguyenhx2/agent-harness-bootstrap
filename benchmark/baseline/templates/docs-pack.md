# Docs pack (project-bootstrap)

Skeletons for the docs tree content: `docs/README.md`, `docs/tasks/master-plan.md`, the context
files, and the three file templates (TASK/PRD/ADR) that go into `docs/templates/`. Docs prose is
written in `{{DOCS_LANGUAGE}}` EXCEPT: task files, master-plan, and ADRs are 100% English
(avoids language-quality defects in tracking files and keeps decision records portable);
codes/enums/filenames always English.

---

## docs/README.md (the index)

```markdown
# Docs - {{PROJECT_NAME}}

Documentation designed for both humans and AI agents. Read levels per folder:

| Folder | Read level | Content |
|--------|-----------|---------|
| specs/ | ALWAYS | 13-section BA analysis - source of truth for requirements (FRs, NFRs, ERD, access control) |
| requirements/ | ALWAYS | PRD - one file per feature/epic, detailing an FR for the sprint |
| architecture/decisions/ | ALWAYS | ADRs - immutable once Accepted |
| architecture/system-overview.md | ALWAYS | High-level architecture (Mermaid) |
| architecture/api-contracts/ | ON-DEMAND | API schema per domain; update when endpoints change |
| tasks/active/ + pending/ + done/ | MANUAL | Task files + AI session log |
| context/ | ON-DEMAND | AI long-term memory: domain-glossary, business-rules, known-issues, tool-changelog |
| templates/ | MANUAL | Templates for new TASK / PRD / ADR files |

## Standard flow
1. New requirement -> update specs/ (BA) -> create/update the PRD in requirements/.
2. Major technical decision -> ADR in architecture/decisions/ (/new-adr).
3. Sprint work -> TASK in tasks/active/ (/new-task) -> agents work and log sessions.
4. Done -> move the task to tasks/done/, update context/ (/sync-context).

Agent contract: see CLAUDE.md (repo root) and .claude/rules/.
```

## docs/tasks/master-plan.md

```markdown
---
title: "Master plan - {{PROJECT_NAME}}"
---

# Master plan

<!-- 100% English (see .claude/rules/task-tracking.md). -->

## Phases

| Phase | Goal | Status |
|-------|------|--------|
| 1 | {{PHASE_1_GOAL}} | Active |

## Task index

| Task | Title | Owner | Deps | Priority | Phase | Status |
|------|-------|-------|------|----------|-------|--------|
| TASK-001 | {{FIRST_TASK}} | {{OWNER}} | - | P0 | 1 | Active |

<!-- Update the Status column on EVERY task status change; it must always agree with the task
file's frontmatter. Brownfield bootstrap: seed Phase 1 with the migration backlog from the
codebase-analysis gap list. -->
```

## docs/tasks/pending/README.md

```markdown
# Pending tasks

Tasks intentionally deferred ("to do later") or descoped on request - paused with a recorded
reason, NOT abandoned. Distinct from Blocked (short-term wait). Moved back to active/ when
resumed. The orchestrator's session-start scan skips this folder; resume explicitly.
```

## docs/context/ - four files

- `domain-glossary.md` - table: term / definition / synonyms. Seed with domain terms found during
  codebase analysis (entity names, status enums, role names).
- `business-rules.md` - numbered rules (BR-NN) with source (FR/decision) and date; updated via
  /sync-context whenever behavior-affecting logic changes.
- `known-issues.md` - table: issue / workaround / status / discovered date.
- `tool-changelog.md` - dated log of dependency/tool/infra changes (what, why, verification).
  Brownfield: first entry = the bootstrap itself.

## docs/templates/TASK.md.template

```markdown
---
title: "TASK-NNN: <Short title>"
status: Active # Active | Blocked | Pending | Done
fr: FR-XX
owner: <agent>
deps: <TASK-NNN, ... or "-">
priority: <P0 | P1 | P2>
phase: <phase number in docs/tasks/master-plan.md or "-">
created: YYYY-MM-DD
tags: [task]
---

<!-- TASK FILES ARE WRITTEN 100% IN ENGLISH (see .claude/rules/task-tracking.md). -->

# TASK-NNN: <Short title>

## Goal
<One sentence describing the desired outcome.>

## Inputs / context
- Related FR: [FR-XX](../../specs/05-functional-requirements.md#fr-xx)
- Related PRD: <link>
- Related files/modules:

## To do
- [ ]

## Test scenarios / acceptance
- [ ] <Track the FR acceptance criteria>

## Session log (AI session log)

| Date | Who | What was done | Result |
|------|-----|---------------|--------|
| | | | |

## Result
<Fill when moving to Done; link the {{PR_OR_MR}}/commit. Then move the file to docs/tasks/done/.>
```

## docs/templates/ADR.md.template

```markdown
---
title: "ADR-NNN: <Decision title>"
status: Proposed # Proposed | Accepted | Deprecated | Superseded by ADR-MMM
date: YYYY-MM-DD
deciders: []
tags: [adr, architecture]
---

<!-- ADRs ARE WRITTEN 100% IN ENGLISH (see .claude/rules/docs-workflow.md). -->

# ADR-NNN: <Decision title>

## Context
<The problem to decide; constraints; forces at play.>

## Decision
<The chosen decision, stated briefly and decisively.>

## Options considered

| Option | Pros | Cons |
|--------|------|------|
| A (chosen) | | |
| B | | |

## Consequences
- Positive:
- Negative / trade-off:
- Follow-up work:

## References
- <Link to related spec / PRD / document>
```

## docs/templates/PRD.md.template

(Prose in {{DOCS_LANGUAGE}}; structure below shown in English - translate headings when the docs
language differs.)

```markdown
---
title: "PRD: <Feature name>"
sidebar_label: "PRD-FR-XX"
description: "Product Requirements Document for <feature>."
status: Draft
tags: [prd, requirements]
---

# PRD: <Feature name> (FR-XX)

> Source requirement: [FR-XX](../specs/05-functional-requirements.md#fr-xx)

## 1. Context and problem
## 2. Goals and success metrics
## 3. Scope (in / out)
## 4. Detailed requirements
| ID | Requirement | Priority | Acceptance criteria |
|----|-------------|----------|---------------------|
| FR-XX.1 | | Must | |
## 5. User flow (Mermaid)
## 6. Technical constraints
## 7. Open questions
## 8. References
```

## docs/architecture skeletons

- `system-overview.md` - one Mermaid diagram (services, data stores, external providers, queue)
  + a stack table + data-flow notes. Brownfield: draw the ACTUAL architecture found in analysis.
- `decisions/README.md` - ADR index table (ADR / title / status / date) + "immutable once
  Accepted" note. Brownfield with prior big decisions already made in code: record them
  retroactively as Accepted ADRs (e.g. ADR-001 tech stack) so the immutability hook protects them.
- `api-contracts/README.md` - conventions: one file per domain, updated in the same {{PR_OR_MR}}
  as the endpoint change.
- `specs/` - leave empty except a README pointing at the spec-builder skill when specs do not
  exist yet; NEVER hand-invent the 13 sections here.
```

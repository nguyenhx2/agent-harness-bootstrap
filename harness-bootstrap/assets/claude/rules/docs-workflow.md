---
paths:
  - "docs/**"
---

# Docs workflow

Applies when reading or writing anything under `docs/`.

## Where things live

| Path | Holds | Who writes it |
|------|-------|---------------|
| `docs/specs/` | Requirements, acceptance criteria, the data model. The contract. | Analyst role, reviewed by the owner |
| `docs/architecture/` | Architecture notes and ADRs - one decision per ADR. | Whoever made the decision |
| `docs/tasks/` | The master plan board and one file per task (task-tracking.md). | Every agent, as it works |
| `docs/context/` | Living project context: business rules, tool changelog, conventions. | Whoever changes the thing being described |
| `docs/templates/` | The templates new documents are created FROM. | Rarely, and deliberately |

## Rules

- **No new doc structures outside this map.** A document that does not fit an existing directory is
  a signal to discuss, not a reason to invent `docs/misc/`. Scattered docs are unfindable docs, and
  unfindable docs get rewritten from scratch by the next agent.
- **New files start from the template** in `docs/templates/`. The template is the single source of
  the shape.
- **The specs are the contract.** Code that disagrees with a spec is either a bug or an
  undocumented decision; find out which, and fix the one that is wrong. Never quietly diverge.
- **Change the doc in the same pull request as the code.** A business-rule change updates
  `docs/context/business-rules.md`; an architectural decision gets an ADR; a schema change updates
  the data dictionary (data-model.md). A documentation debt registered as a follow-up task is a
  documentation debt that never gets paid.
- **An accepted ADR is immutable.** Supersede it with a new ADR that references it; do not edit the
  decision after the fact. The hook enforces this, and it enforces it from the on-disk status, so
  land every other edit BEFORE the commit that flips the status to accepted.

## Writing conventions

- Task files and ADRs are English, always. Codes, enum values, and identifiers are English.
- Sentence-case headings. No emoji. No em dash (write "-"). Lists use `-`.
- Diagrams are Mermaid in the markdown, not an image nobody can edit.
- Links between documents are relative paths, so they survive being moved or read on a mirror.
- No secrets and no real personal data in any document, including task session logs
  (agent-guardrails.md).

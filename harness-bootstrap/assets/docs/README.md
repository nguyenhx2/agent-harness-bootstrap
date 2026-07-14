# Docs - {{PROJECT_NAME}}

Documentation written for humans and AI agents alike. Each folder has a read level: how often an
agent is expected to open it.

| Folder | Read level | Content |
|--------|-----------|---------|
| `specs/` | Always | The BA analysis: source of truth for requirements (FRs, NFRs, data model, access control) |
| `requirements/` | Always | PRDs, one per feature or epic, detailing an FR for the sprint |
| `architecture/system-overview.md` | Always | High-level architecture diagram and stack table |
| `architecture/decisions/` | Always | ADRs, immutable once Accepted |
| `architecture/api-contracts/` | On demand | API schema per domain, updated in the same {{PR_OR_MR}} as the endpoint change |
| `tasks/` | Every session | The master-plan board, the task files, and their session logs |
| `context/` | On demand | Long-term memory: glossary, business rules, known issues, tool changelog |
| `templates/` | Manual | Templates for new TASK, PRD, and ADR files |

## Standard flow

1. A new requirement updates `specs/`, then gets a PRD in `requirements/`.
2. A significant technical decision becomes an ADR in `architecture/decisions/` (`/new-adr`).
3. Work becomes a task in `tasks/active/` (`/new-task`). Agents work it and log every session.
4. A finished task moves to `tasks/done/`, and what was learned lands in `context/`
   (`/sync-context`).

## Task states

A task is in exactly one of five states: `Planned`, `Active`, `Blocked`, `Pending`, `Done`. They
are defined in the frontmatter of `templates/TASK.md`, which is the single source of truth for the
state machine. The task file's `status:` and its row in `tasks/master-plan.md` must always agree.

## Conventions

- Task files and ADRs are written 100% in English. Tracking files and decision records have to stay
  portable and unambiguous.
- Codes, enums, IDs, and filenames are always English.
- New files come from `templates/`. No parallel documentation structures outside these folders.
- Requirement changes are logged in `specs/13-revision-history.md`.
- No secret values, credentials, or real customer data in any file here. Documentation is committed
  and read by everyone.

The agent contract lives in `AGENTS.md` at the repository root; the enforceable detail lives in
`.claude/rules/`.

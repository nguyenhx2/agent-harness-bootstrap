---
title: "Master plan - {{PROJECT_NAME}}"
---

# Master plan

<!-- Written 100% in English (see .claude/rules/task-tracking.md). -->

The board. Every task in the project has exactly one row here, and that row's Status must always
equal the `status:` in the task file's frontmatter. The five valid states are defined in
`docs/templates/TASK.md`: `Planned | Active | Blocked | Pending | Done`.

## Phases

| Phase | Goal | Status |
|-------|------|--------|
| 1 | <phase goal> | Active |

## Task index

| Task | Title | Owner | Deps | Priority | Phase | Status |
|------|-------|-------|------|----------|-------|--------|
| TASK-001 | <first task> | <owner agent> | - | P0 | 1 | Planned |

<!-- Update the Status column on EVERY status change, in the same change as the task file. -->

<!-- This is the most conflict-prone file in the repository: every task branch edits one row of it,
     so the rows collide constantly, and a merge that resolves the collision by taking one side
     reverts a status flip with no error at all. After every merge, re-read this board and confirm
     that each task file's frontmatter status still equals its row here, and that the files in
     docs/tasks/done/ and the Done rows agree one-to-one. When two branches each add a row, the
     resolution is both rows, never one side of the file. -->

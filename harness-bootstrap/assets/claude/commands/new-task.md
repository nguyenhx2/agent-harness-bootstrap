---
description: Create a task file from the template and register it on the master plan.
argument-hint: <short-title>
---

Create a task for **$1**. If $1 is empty, ask for the title and stop.

1. Determine the next TASK-NNN, sequential across `docs/tasks/active/`, `docs/tasks/pending/`, and
   `docs/tasks/done/`. The board allocates the number; never reuse one, and never overwrite an
   existing task file on a collision.
2. Copy `docs/templates/TASK.md` to `docs/tasks/active/TASK-NNN-<slug>.md` and fill: title, goal,
   owner agent, dependencies, priority, phase, created date, and acceptance criteria. Acceptance
   criteria are observable and testable outcomes, not process steps.
3. Set `status: Planned`. The task becomes `Active` only when an agent is actually dispatched to
   it. The five states are defined in the frontmatter of `docs/templates/TASK.md`:
   `Planned | Active | Blocked | Pending | Done`.
4. Add the row to the task index in `docs/tasks/master-plan.md`. Read the row back after writing
   it: a board write can fail silently while the task file lands.
5. Append the first session-log row to the task file, recording that it was created and registered.

One task is one independently executable and verifiable unit of work. If two sub-goals need
different owner agents or produce different artifacts, they are two tasks.

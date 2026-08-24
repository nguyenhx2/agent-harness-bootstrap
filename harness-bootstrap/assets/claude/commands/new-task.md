---
description: Create a task file from the template and register it on the master plan.
argument-hint: <short-title>
---

Create a task for **$1**. If $1 is empty, ask for the title and stop.

**First, check that this earns a task at all.** `.claude/rules/task-tracking.md` sets the bar; the
two questions that matter here:

- **Did the user ask for this?** A task is agreed work. If this came out of something you noticed
  while doing something else, stop: finish what you were given and report the finding. The user
  decides whether it becomes a task. Do not register it and mention it afterwards.
- **Is it bigger than the paperwork?** A typo, a rename, a one-line fix and a step inside work
  already registered are not tasks. Make the change, or write one line in the report.

If either answer is no, say so and stop without creating anything. Refusing to open a task is a
normal outcome of this command, not a failure of it.

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
6. If `.claude/state/code-graph.json` exists, seed a `**Relevant modules:**` line under "Inputs and
   context" in the task file: find the module(s) whose `owner` field (in the graph) matches this
   task's owner agent, then list them plus every module with a direct edge INTO them (its `"to"`
   equal to the owner's module - the direct dependents, i.e. what else the graph says would be
   affected by a change there). This gives the dispatch brief a blast-radius hint before any code is
   touched. If the graph does not exist yet, skip this step silently - a task file with no seeded
   line is not an error, just ungraphed.

One task is one independently executable and verifiable unit of work. If two sub-goals need
different owner agents or produce different artifacts, they are two tasks.

That rule splits; it does not multiply. It applies to work that already earned a task, and is not a
reason to turn one agreed piece of work into six registered ones. Fewer, real tasks beat a board
that is technically complete and practically unreadable.

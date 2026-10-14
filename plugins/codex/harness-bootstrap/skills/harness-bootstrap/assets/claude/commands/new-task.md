---
description: Create a task file from the template and register it on the master plan, after the user confirms it should exist.
argument-hint: <short-title>
allowed-tools: Read, Write, Edit, Grep, Glob, AskUserQuestion, Bash(python:*), Bash(python3:*)
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

**Then ASK, and wait.** Unless the user's own message in this conversation already asked for this
task, put the proposal to them with `AskUserQuestion` before writing anything: what the task would
be, why it is worth its own row rather than being part of work already registered, and who would
own it. Create it only on an explicit yes.

This is the same discipline `/harness-toggle` uses for a protected control: a confirmation is
relayed only when the user gave it themselves, in this conversation. An agent deciding on the
user's behalf that they would probably approve is exactly the thing that fills a board with rows
nobody agreed to - and it is not something a hook can catch, because a fabricated `requested_by`
looks identical to a real one. This step is the actual gate; `guard-task-scope` only enforces that
the claim is written down.

1. Register it with one command - it allocates the next TASK-NNN, fills the template into
   `docs/tasks/active/`, adds and verifies the board row, and logs the first row:

   ```
   python .claude/scripts/task.py new "<title>" --owner <seat> \
     --requested-by "<the user's words, or the issue>" \
     --criterion "<observable outcome>" --criterion "<another>" \
     [--goal "..."] [--deps TASK-NNN,...] [--priority P0|P1|P2] [--phase N] [--fr FR-NN] \
     [--files "<paths the work may touch>"]
   ```

   With `--fr`, the task links to an FR: name the criterion IDs (`AC-nn.n`) instead of copying their
   text, and `task.py` re-runs `.claude/scripts/spec-check.py --write` (when the repo has it), so
   `docs/specs/index.json` lists the new task and never goes stale.

   `--requested-by` records what was asked for - not `user`, not an agent name. Criteria are
   observable outcomes, not process steps; fewer than two is refused, like `guard-task-scope`
   refuses it. The task stays `Planned` until an agent is actually dispatched
   (`task.py move TASK-NNN Active`).
2. If `.claude/state/code-graph.json` exists, seed a `**Relevant modules:**` line under "Inputs and
   context" in the task file: find the module(s) whose `owner` field (in the graph) matches this
   task's owner agent, then list them plus every module with a direct edge INTO them (its `"to"`
   equal to the owner's module - the direct dependents, i.e. what else the graph says would be
   affected by a change there). This gives the dispatch brief a blast-radius hint before any code is
   touched. If the graph does not exist yet, skip this step silently - a task file with no seeded
   line is not an error, just ungraphed.

One task is one independently shippable and verifiable unit of work. Needing two seats does not
make it two tasks: name a lead `owner:` and list the other seats as steps in its plan. Split only
when the parts can ship, and be verified, on their own.

That rule splits; it does not multiply. It applies to work that already earned a task, and is not a
reason to turn one agreed piece of work into six registered ones. Fewer, real tasks beat a board
that is technically complete and practically unreadable.

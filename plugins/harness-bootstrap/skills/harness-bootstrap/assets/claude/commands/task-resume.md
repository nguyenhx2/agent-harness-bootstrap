---
description: Resume a task from its task file after a compaction or in a new session.
argument-hint: <TASK-NNN> (omit to list every unfinished task)
allowed-tools: Bash(git status), Bash(git diff:*), Bash(git log:*), Read, Grep, Edit
---

Resume task **$1**.

If $1 is empty, do not resume anything: list every unfinished task instead. Search
`docs/tasks/active/` for `status: Planned`, `status: Active`, and `status: Blocked`, and report
them with their master-plan rows, priorities, and blockers.

1. Read `docs/tasks/master-plan.md` for the task's position, dependencies, and priority.
2. Read the task file end to end: session log, decisions, blockers, acceptance criteria.
3. Trust the files over conversation memory. The conversation may have been compacted; the files
   were committed.
4. Verify the working tree with `git status`, `git diff`, and `git log`. The files record intent,
   the tree records reality. When they disagree, reconcile before continuing: inspect uncommitted
   work and drive it to completion or escalate it. Never stash, discard, or clobber it.
5. Continue from the recorded state, appending a session-log row after every meaningful unit of
   work. Any status change is written in the task file AND the master-plan row together.

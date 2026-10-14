---
description: Resume a task from its checkpoint after a compaction or in a new session.
argument-hint: <TASK-NNN> (omit to list every unfinished task)
allowed-tools: Bash(git status), Bash(git diff:*), Bash(git log:*), Bash(python:*), Bash(python3:*), Read, Grep
---

Resume task **$1**.

1. Run `python .claude/scripts/task.py resume $1`. With no task code it lists every unfinished
   task, human gates first - report that list and stop. With one, it prints the board row, the
   checkpoint (next step, last green commit, open questions), the open acceptance criteria, the
   last few session-log rows, and whether HEAD and the working tree match the checkpoint.
2. Trust that over conversation memory. Read more of the task file only for what the digest does
   not answer - not the whole log by default.
3. If it reports DRIFT, or uncommitted paths, reconcile first: `task.py check` names the
   disagreement; inspect uncommitted work and drive it to completion or escalate it. Never stash,
   discard, or clobber it.
4. Continue from the checkpoint's next step. Log each completed unit (`task.py log`), change
   status only with `task.py move`, and rewrite the checkpoint before you stop.

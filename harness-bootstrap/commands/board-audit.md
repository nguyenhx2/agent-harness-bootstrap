---
description: Find orphaned, stale, and loop-suspect work - Active tasks nobody is driving, finished subagent runs nobody logged, worktrees and branches the board does not know about.
allowed-tools: Read, Grep, Glob, Bash(git worktree list), Bash(git branch:*), Bash(git log:*), Bash(ls:*), Bash(python:*), Bash(python3:*)
---

Audit the board against reality in the repo you are currently in. Read-only: report, never fix
silently.

**Preflight.** This needs `docs/tasks/` and, for the first sweep, `.claude/scripts/board-check.py`.
If `docs/tasks/` is missing, stop: there is no board here. If only the script is missing, say so
and run the sweeps below without it, flagging that frontmatter validity was not checked.

Run `python .claude/scripts/board-check.py` FIRST, before any sweep below. It checks
every task file's frontmatter enums, `deps:` cycles, and drift - folder vs `status:`, file vs
board row, rows with no file - so no sweep below re-reads files to find those. A non-zero exit
means the board is malformed: report its findings verbatim before continuing.

Then run these sweeps and report each finding as `WHAT | WHERE | SUGGESTED ACTION`:

1. **Stale Active.** Every `docs/tasks/active/*.md` with `status: Active` whose last session-log
   row is older than the rest of the board's activity, or whose owner has no `.claude/state/history/`
   entry since that row. An Active task nobody is driving is an orphan wearing a live status.
2. **Unlogged completions.** Every file in `.claude/state/history/` newer than the last session-log
   row of the task its prompt names. That run finished; nobody collected it. Quote the task code and
   the archive filename.
3. **Board drift.** Covered by `board-check.py` above; do not re-derive it by reading files.
4. **Attempt-cap breaches.** Any task with `attempts:` of 3 or more still marked `Active` - by the
   repo's task-control rule it must be `Blocked` with an escalation note.
5. **Unknown worktrees and branches.** `git worktree list` and `git branch --list` entries no
   Active/Planned task references. Work is happening (or died) outside the board.
6. **Blocked with no unblocker.** `status: Blocked` files whose notes name no owner or condition
   that would unblock them - those never resurface on their own.
7. **Unreviewed module edge.** `python .claude/scripts/code-graph.py --check` exits 1: the code
   imports across a module line that `docs/context/code-graph.md` does not list. Name each edge it
   prints. Fix is a decision per edge - remove the import, or accept it with `/harness-bootstrap:code-graph` - never
   ignoring it.

End with a one-line verdict: `BOARD CLEAN` or `N findings - board needs reconciliation`, and if
findings exist, the single next action that clears the most of them.

Fix nothing yourself. The orchestrator (or the user) reconciles; this command only sees.

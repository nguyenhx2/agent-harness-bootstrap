---
description: Find orphaned, stale, and loop-suspect work - Active tasks nobody is driving, finished subagent runs nobody logged, worktrees and branches the board does not know about.
allowed-tools: Read, Grep, Glob, Bash(git worktree list), Bash(git branch:*), Bash(git log:*), Bash(ls:*), Bash(python:*), Bash(python3:*)
---

Audit the board against reality. Read-only: report, never fix silently.

Run `python .claude/scripts/board-check.py` FIRST, before any sweep below. It validates every
task file's frontmatter enums (`status`, `attempts`, `priority`, `human_gate`) and detects
dependency cycles in `deps:` chains, stdlib only. A non-zero exit means the board itself is
malformed - report its findings list verbatim before continuing, because the sweeps below assume
well-formed frontmatter and are unreliable against a board that fails this check.

Then run these sweeps and report each finding as `WHAT | WHERE | SUGGESTED ACTION`:

1. **Stale Active.** Every `docs/tasks/active/*.md` with `status: Active` whose last session-log
   row is older than the rest of the board's activity, or whose owner has no `.claude/state/history/`
   entry since that row. An Active task nobody is driving is an orphan wearing a live status.
2. **Unlogged completions.** Every file in `.claude/state/history/` newer than the last session-log
   row of the task its prompt names. That run finished; nobody collected it. Quote the task code and
   the archive filename.
3. **Board drift.** Tasks whose frontmatter `status:` disagrees with their master-plan row, files in
   `active/` marked Done or Pending, files in `done/` not marked Done.
4. **Attempt-cap breaches.** Any task with `attempts:` of 3 or more still marked `Active` - by
   task-control.md it must be `Blocked` with an escalation note.
5. **Unknown worktrees and branches.** `git worktree list` and `git branch --list` entries no
   Active/Planned task references. Work is happening (or died) outside the board.
6. **Blocked with no unblocker.** `status: Blocked` files whose notes name no owner or condition
   that would unblock them - those never resurface on their own.

7. **Stale code graph.** `.claude/state/code-graph.stale` is non-empty, or
   `python .claude/scripts/code-graph.py --check` exits 1: dispatch decisions are being made on an
   outdated module map. Fix is `/code-graph`, not ignoring it.

End with a one-line verdict: `BOARD CLEAN` or `N findings - board needs reconciliation`, and if
findings exist, the single next action that clears the most of them.

Fix nothing yourself. The orchestrator (or the user) reconciles; this command only sees.

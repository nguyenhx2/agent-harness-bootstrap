# Task tracking

Loaded in every session, deliberately: an agent that forgets where state lives will invent it.

## Task files are the source of truth

This covers registered work - {{#IF_PURPOSE_CODE}}an FR through `/implement-fr`, {{/IF_PURPOSE_CODE}}work that must survive a compacted
session, a mission the orchestrator runs, and anything the user asked to track. Other work, at any
tier of the `AGENTS.md` table, has no task file: its record is the commit, the gate results and the
report. The conversation is not the record; it gets compacted.

- `docs/tasks/master-plan.md` - the board, one row per task.
- `docs/tasks/active/`, `pending/`, `done/` - one file per task: scope, acceptance criteria,
  checkpoint, session log. The five states and which folder each lives in are defined once, in
  `docs/templates/TASK.md`.

## One command changes state

`python .claude/scripts/task.py` is the only way task state changes. Each subcommand writes the
frontmatter, the folder, the board row and the session-log row together and reads the row back.
Never hand-edit a `status:` field or a Status cell.

| When | Command |
|---|---|
| Register agreed work | `task.py new "<title>" --owner <seat> --requested-by "<what was asked>" --criterion "..." --criterion "..."` |
| Start, block, park, finish | `task.py move TASK-NNN Active` / `Blocked --note "<blocker, who clears it>" [--human-gate "<decision>"]` / `Pending --note "<why>"` / `Done --note "<commit or PR>"` |
| A failed dispatch | `task.py attempt TASK-NNN --reason infra\|scope\|env --note "..."` - counts toward the cap, blocks at it |
| A completed unit of work | `task.py log TASK-NNN "<what>" "<result>"` |
| Before you stop or hand off | `task.py checkpoint TASK-NNN --next "..." [--green] [--question "..."]` |
| Resume, or see the board | `task.py resume [TASK-NNN]`, `task.py check` |

Log one row per completed unit - a dispatch outcome, a gate run, a decision, a status change - not
per tool call. One line: what was done and the result. Older rows archive to `docs/tasks/log/`.
**A gate counts as passed only when a log row records the run**; anything else is a claim.

## What earns a task, and who decides

A task is work the USER asked for, and tasks are FEW AND LARGE: a feature, an investigation, a
migration.

- **Executing a task never creates more tasks.** Steps belong in the task file's plan.
- **The user agrees, directly.** If their own message did not ask for it, `/new-task` asks with
  `AskUserQuestion` and waits for an explicit yes from the person.
- **The file records it.** `requested_by:` carries their words or the issue, not `user` or an agent
  name; `task.py new` and `guard-task-scope` refuse a task without it or with fewer than two criteria.
- **No agent opens a task on its own, subagents included.** What you discover goes in your report.

| Below the bar, so not a task | What to do with it |
|---|---|
| A typo, a rename, a one-line fix | Make it in the change you are already writing |
| A "we should probably also..." | One line in the report, or `docs/context/known-issues.md` |
| A step inside registered work | A step in that task's plan |
| A refactor nobody asked for | Say what you would change and why, and stop |

Unsure whether it earns a task? It does not. Ask. The one exception is a discovery that BLOCKS the
task in hand: `move` it to `Blocked`, name what would unblock it, escalate.

## After compaction or an abnormal end

Run `/task-resume TASK-NNN` before anything else. It prints the checkpoint, the open criteria and
the last log rows, and flags drift between the file, the board and git. Trust that over memory;
reconcile drift before new work starts.

Task files are committed text: reference requirement IDs rather than restating them, and match
their length to what the next reader needs - no summary sections, no restated plans.

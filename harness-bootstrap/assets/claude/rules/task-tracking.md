# Task tracking

Loaded in every session, deliberately: an agent that forgets where state lives will invent it.

## Task files are the source of truth

This covers registered work - Guarded changes, and anything the user asked to track. Inline, Direct
and Standard work in the `AGENTS.md` tier table has no task file by design: its record is the
commit and the report, and nothing below requires one for it.

The conversation is not the record. Context gets compacted, sessions end, agents are replaced
mid-flight. What survives is what is written down:

- `docs/tasks/master-plan.md` - the board. One row per task: ID, title, owner, status, branch.
- `docs/tasks/active/`, `docs/tasks/pending/`, `docs/tasks/done/` - one markdown file per task,
  holding its scope, acceptance criteria, plan, and session log.

Status lives in two places (the board row and the task file) and they must agree. Every status
write is verified by reading the row back after writing it - a write nobody confirmed is a wish.

## The five states

Defined canonically in `docs/templates/TASK.md`. These are the only valid values of `status:`, in the
task file and in the board row alike.

| State | Meaning | File lives in |
|-------|---------|---------------|
| Planned | Registered on the board, scoped, not started. | `active/` |
| Active | In progress. Exactly one owner. | `active/` |
| Blocked | Started, cannot proceed. The blocker and who can clear it are named. | `active/` |
| Pending | **Deliberately parked**, with the reason recorded. Not the same as Planned. | `pending/` |
| Done | Complete and verified. The result is recorded. | `done/` |

`Planned` and `Pending` are easy to confuse and must not be. Planned means "queued, nobody has started
yet"; Pending means "we consciously decided to stop working on this". A Planned task file stays in
`active/` precisely so the orchestrator's session-start scan can see it - a new task filed under
`pending/` would be invisible to the scan and would never be picked up.

## What earns a task, and who decides

A task is work the USER asked for, and tasks are FEW AND LARGE: a feature, an investigation, a
migration. Ten rows for one agreed piece of work is noise with IDs on it.

- **Executing a task never creates more tasks.** Steps belong in the task file's plan section.
- **The user agrees, directly.** If their own message did not ask for it, `/new-task` asks with
  `AskUserQuestion` and waits for an explicit yes - from the person, not an agent guessing and not
  a subagent telling its dispatcher.
- **The file records it.** `requested_by:` carries their words or the issue. A bare `user` is a
  label, and an agent name is refused: an agent cannot approve its own task. `guard-task-scope`
  blocks a file without it, or with fewer than two real acceptance criteria. The hook cannot prove
  the user agreed; it makes a fabricated answer a visible lie instead of an invisible omission.
- **No agent opens a task on its own, subagents included.** What you discover - a bug elsewhere, a
  stale doc, a rule that could be tighter - goes in your report. The user decides.

| Below the bar, so not a task | What to do with it |
|---|---|
| A typo, a rename, a one-line fix | Make it in the change you are already writing |
| A "we should probably also..." | One line in the report, or `docs/context/known-issues.md` |
| A step inside registered work | A step in that task's plan |
| A refactor nobody asked for | Say what you would change and why, and stop |

Above the bar: it needs its own acceptance criteria, outlives this session, or must be scheduled
against other work. The one exception is a discovery that BLOCKS the task in hand: set it
`Blocked`, name what would unblock it, escalate. Unsure whether it earns a task? It does not. Ask.

## Workflow

- **At registration**: create the task file from the template in `active/` with `status: Planned`, and
  add its row to the board. Registered work does not begin before its task file exists.
- **At task start**: flip the file and the board row to `Active`, and name the owner and the branch.
- **During work**: append one row per completed unit - a dispatch's verified outcome, a gate run, a
  decision, a status change - as it happens, not at the end of the session. Not per tool call and
  not per edit: a row nobody will read is tokens spent twice, once to write and once to load. The
  log is the evidence a gate ran.
- **A gate counts as passed only when the task file's session log records the run.** A claim in a
  chat message, a PR description, or an agent's final report is a claim, not a fact. Verify against
  git state and the log.
- **At status change**: update both the file location and the board row, in the same step, then
  re-read the row.
- **To park a task**: set `Pending`, record *why* in the task file, and move it to `pending/`. Parking
  is a decision and it gets written down; a task that quietly stops being worked on is not Pending, it
  is abandoned.
- **At close-out**: set `Done`, record the result, move the file to `done/`, flip the board row, prune
  the task's worktree, and delete the merged branch.

## After compaction or an abnormal end

Context loss is routine; treat recovery as routine too. On resume, before doing anything else:

1. Re-read `docs/tasks/master-plan.md` and the task file for the task in hand. Do not proceed on
   remembered state.
2. Reconcile the board against git: list worktrees and branches, compare with the rows. A branch
   with no row, or an Active row with no branch, is drift and gets fixed before new work starts.
3. After every merge and at close-out, audit that the `done/` files and the board rows agree 1:1.
   A merge can silently revert a status flip made on another branch.

## Writing task files

- English, always, including the session log.
- No secrets, no credentials, no real personal data - a task file is committed text (see
  agent-guardrails.md).
- Reference the requirement and the task ID rather than restating them; the specs are the spec.

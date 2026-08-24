# Task tracking

Loaded in every session, deliberately: an agent that forgets where state lives will invent it.

## Task files are the source of truth

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

A task is work the USER asked for, and tasks are FEW AND LARGE. A feature to build, an
investigation to run, a migration to carry out - that scale. Ten rows for one agreed piece of work
is not a plan, it is noise with IDs on it.

**Executing a task never creates more tasks.** If carrying out TASK-014 leaves you wanting six new
rows, the answer is that those are steps in TASK-014, and the task file has a plan section for
steps. Splitting them out does not make the work more tracked, it makes the board unreadable and
hides what the user actually approved.

**A task needs the user's agreement, and it is asked for directly.** If the user's own message did
not ask for this task, `/new-task` puts it to them with `AskUserQuestion` and waits for an explicit
yes before anything is written. Not an agent deciding they would probably approve, and not a
subagent telling its dispatcher - the person. This is the same rule `/harness-toggle` applies to a
protected control: a confirmation counts only when the user gave it themselves, in this
conversation.

That step is the real gate, and it is worth being clear why: a hook cannot tell a fabricated
`requested_by` from a true one. What the hook does is make the claim exist in writing.

**The file records the agreement.** Every task file carries
`requested_by:` naming what was asked for - their words, or the issue it came from. `user` on its
own is a label, not a record, and an agent name is refused outright: an agent cannot approve its
own task. `guard-task-scope` blocks a task file without it, and one with fewer than two real
acceptance criteria. The hook cannot prove the user actually agreed - nothing can - but it makes
the claim explicit in the file that outlives the session, so a fabricated answer is a visible lie
rather than an invisible omission.

**No agent opens a task on its own - and that includes every subagent.** Only work the user agreed
to becomes a row. A subagent that finds something reports it to whoever dispatched it; it does not
register it, and the dispatcher does not register it either without asking. The board records agreed
work; it is not a notebook of everything an agent noticed on the way past.

**Work you discover does not register itself.** Find a bug in another module, a stale doc, a rule
that should be tighter - finish the task you have and REPORT it. The user decides whether it becomes
a task. A board that fills with work nobody asked for stops being a plan, and the agreed work gets
lost in it.

**Below the bar it is not a task.** Do it, or say it in the report:

| Not a task | What to do with it |
|---|---|
| Smaller than the paperwork - a typo, a rename, a one-line fix | Make it, in the change you are already writing |
| A "we should probably also..." | One line in the report, or `docs/context/known-issues.md` |
| A step INSIDE work already registered | It is a step. The task file has a plan section for it |
| Something you can finish before the task file would be read | Finish it |
| A refactor nobody asked for | Say what you would change and why, and stop |

**Above the bar**: it needs its own acceptance criteria, it outlives this session and someone picks
it up cold, or it must be scheduled against other work.

**One exception**, narrow: a discovery that BLOCKS the task in hand. Set that task `Blocked`, name
what would unblock it, escalate. That is reporting agreed work cannot proceed, not opening new work.

If you are unsure whether something earns a task, it does not. Ask.

## Workflow

- **At registration**: create the task file from the template in `active/` with `status: Planned`, and
  add its row to the board. No work begins before the task file exists.
- **At task start**: flip the file and the board row to `Active`, and name the owner and the branch.
- **During work**: append a row to the task file's session log after every tool-call batch that
  changed files, not at the end of the session - what was done, what was decided, what ran and what
  it returned. Concise. The log is the evidence a gate ran.
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

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

## Workflow

- **At registration**: create the task file from the template in `active/` with `status: Planned`, and
  add its row to the board. No work begins before the task file exists.
- **At task start**: flip the file and the board row to `Active`, and name the owner and the branch.
- **During work**: append a row to the task file's session log as work happens - what was done,
  what was decided, what ran and what it returned. Concise. The log is the evidence a gate ran.
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

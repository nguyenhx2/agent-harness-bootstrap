# Task control - the orchestrator's analyze / decompose / register / drive loop

The procedure and the canonical state machine. `.claude/rules/task-tracking.md` (loaded every
session) says WHERE state lives; the orchestrator and that rule link here and never restate it.

## The state machine (canonical - defined here, once)

Five states, no others. There is no `Registered` state: registered but not started is **Planned**.

| State | Meaning | Lives in |
|---|---|---|
| `Planned` | Registered on the board and scoped, not started | `docs/tasks/active/` |
| `Active` | In progress. Exactly one owner | `docs/tasks/active/` |
| `Blocked` | Started, cannot proceed. The reason and the unblocker are recorded | `docs/tasks/active/` |
| `Pending` | Deliberately parked - a conscious decision to defer, not an obstacle | `docs/tasks/pending/` |
| `Done` | Complete, results recorded | `docs/tasks/done/` |

**A `Planned` task file lives in `active/`, not `pending/`.** The session-start scan reads
`active/` ("on the work queue"); a new task filed under `pending/` is never picked up.

Status lives in **two** places that must agree: the task file's frontmatter `status:` and the Status
column of its row in `docs/tasks/master-plan.md`. Change both in one step with
`python .claude/scripts/task.py move TASK-NNN <state>`: it rewrites `status:`, moves the file, flips
the board row, logs the change, and reads the row back. `Blocked` wants to move and cannot;
`Pending` could move and has been told not to.

## Phase 1 - analyze the requirement

Before creating any task:

1. Read `docs/tasks/master-plan.md` for the phase, existing tasks and open dependencies. Unfinished
   work (`Active` or `Blocked`) beats new missions.
2. Map the requirement to the project's functional requirements where they exist; one mission may
   span several.
3. Identify scope: which agents, which modules, which decisions are open. **Open decisions block
   planning** - dispatch the decision seats (`strategist`, after `researcher` for evidence, where
   fielded) BEFORE implementation tasks, and record stack-affecting outcomes in an ADR first. A
   decision resting on an UNMEASURED assumption gets a timeboxed measurement spike first.
4. Dispatch `spec-guardian` to verify scope and acceptance criteria before any implementation task.
5. Escalate to the owner - never decide silently - on an owner-only trigger: a spec or ADR
   amendment, a new data-egress path, a change to rules/agents/hooks/settings or an Accepted ADR, a
   release, or one requirement that can only be met by violating another (the owner makes that trade).

## Phase 2 - decompose into tasks

For each unit that is independently executable and verifiable:

- A one-sentence goal.
- Explicit acceptance criteria - observable outcomes, not process steps.
- One owner agent (per the routing table).
- Dependencies: which `TASK-NNN` must be `Done` first.
- Priority: P0 (blocks everything), P1 (important, not blocking), P2 (nice-to-have).
- A phase number consistent with `master-plan.md`.

Two sub-goals with different owners or different verifiable artifacts are different tasks. Never
bundle unrelated work.

## Phase 3 - register and create the task file

1. `/new-task` runs `task.py new`: allocates the code, fills the template (title, goal, owner, deps,
   priority, phase, `requested_by`, at least two acceptance criteria), adds the board row at
   `Planned`, logs the first row, and verifies it. It refuses what `guard-task-scope` refuses.
2. Task files are committed and ship in the same PR/MR as the work they describe.

## Phase 4 - drive the lifecycle

**During work:**

- After every meaningful unit: `task.py log TASK-NNN "<what>" "<result>"` - one line, the outcome.
  Older rows move to `docs/tasks/log/log-TASK-NNN.md`, still committed.
- Before stopping, handing off, or after a green suite: `task.py checkpoint TASK-NNN --next "..."
  [--green] [--question "..."]`. Three lines - next step, last green commit, open questions -
  rewritten, never appended; the resume protocol reads it first.
- A decision: one bullet under the task file's orchestration-notes, with its rationale.
- A blocker: `task.py move TASK-NNN Blocked --note "<what is missing, who can unblock it>"`. If it
  needs a human DECISION (a policy call, a requirement trade-off, a Phase 1 owner-only trigger), add
  `--human-gate "<reason>"` so the board separates "waiting on a human" from a technical block.
- Cleared: `task.py move TASK-NNN Active` removes `human_gate` and logs the change.
- An environment workaround (a compiler wrapper, a sandbox blocking loopback, a flag avoiding an
  OOM): record the WORKAROUND, not just the symptom, in `docs/context/known-issues.md` the first time.
- Frontmatter enums (`status`, `attempts`, `priority`, `human_gate`), `deps:` cycles, and drift
  between folder, `status:` and board row are machine-checked by `python .claude/scripts/board-check.py`
  (also `task.py check`; exits 1 on any violation). `/board-audit` runs it before its own sweeps.

**Attempt discipline (the anti-loop rule).** Record a failed dispatch with
`task.py attempt TASK-NNN --reason infra|scope|env --note "..."`: `scope` increments `attempts:` and
blocks at the cap, `env` blocks at once, `infra` only logs. A failed attempt may be re-dispatched
ONCE to the same agent, with a brief that states what changed - an identical brief is a loop and is
never sent. At `attempts: 3` the task goes `Blocked` in both places with what was tried, and the
orchestrator escalates to the user. No exceptions.

**Spend capability before the user's attention.** Attempt three may raise the seat's tier: dispatch
once at a higher `effort:` (or, for a genuinely hard problem, the next model up) with a brief saying
what the two previous attempts got wrong. It is still attempt three; if it fails the task goes
`Blocked`. Record the tier change in the session row - a seat that repeatedly needs it is a roster
fact (`reference/cost-model.md`). Never escalate tier as the FIRST response to a failure.

**No placeholders in a dispatched task.** Criteria containing "TBD", "etc.", or a file list ending
"and related files" are not ready: name the files and criteria, or leave the task Pending.

**Failure-reason taxonomy.** Every failed dispatch logs exactly one `attempt-reason`:

- `infra` - the tooling failed, not the plan (flaky runner, crashed subprocess, network blip).
  Re-dispatch with the SAME brief is allowed.
- `scope` - the brief was insufficient or wrong. Re-dispatch needs a CHANGED brief and counts toward
  the `attempts: 3` cap.
- `env` - the environment cannot do the work (an uninstallable dependency, a denied permission, a
  platform mismatch). Escalate immediately, without retrying or incrementing `attempts:`.

**Resume protocol (every session start).** Before continuing a task in a new or compacted session,
run `/task-resume TASK-NNN` (`task.py resume`: board row, checkpoint, open criteria, last log rows,
drift against git). Read further only for what that does not answer. Trust files over memory, and
the working tree over both. Then reconcile the subagent archive: a `.claude/state/history/` entry
newer than a task's last session-log row is a finished run nobody logged - log it before dispatching.

**Quality gates before `Done`.** `/review-changes TASK-NNN` once, on the finished branch: it runs
`verify-plan.py`, which picks the gates from the diff's paths - the secret scan always; code review,
security review, test layers and the spec check only when the diff touches what each guards - then
the PR/MR is opened. Never skip a required gate or add an unrequired one without a reason; each skip
is in the plan's `log:` row. A gate passed ONLY when the session log records the run.

## Phase 5 - close out

1. Fill the task file's Result section: the PR/MR or commit SHA, what was delivered, follow-ups - no
   restated plan, no log summary.
2. `task.py move TASK-NNN Done --note "PR #NN"`: status, folder, board row and final log row in one
   step. It refuses while criteria are unchecked, unless `--force` with a reason.
3. **Clean up git**: remove the task's worktree, delete the merged branch locally and on the remote
   (`git push origin --delete`), then `git fetch --prune`.
4. **Clean up the environment outside the repo**, which `git status` never shows: out-of-repo build
   outputs (redirected build/target dirs, often gigabytes), large blobs fetched to ad-hoc locations
   (models, datasets, fixtures), throwaway wrappers, logs, diffs and extracted dependency trees.
   **Whoever redirects output out of the repo cleans that location.** Legitimate outputs (build,
   coverage, caches) belong in `.gitignore` - add a missing ignore now. This is **gated**: enumerate
   the paths, confirm each is agent-created scratch - never user data, never the live repo - then
   delete. On Windows, where a blanket `rm -rf` may be denied, use the native remove on enumerated
   paths.
5. Final summary: tasks completed (with codes), test and review status, open follow-ups and where
   their history lives.
6. Business-rule or tool changes discovered along the way: `/sync-context`.
7. If this ends the whole MISSION (no `Active` or `Blocked` tasks left in scope), write the
   completion marker and terminate - see below.

## Crash recovery and single-instance discipline

**Only ONE orchestrator instance drives a project at a time.** A crashed instance can auto-resume,
so a replacement verifies the previous one is actually terminated and reconciles before dispatching.

**Reconciliation, before the first dispatch after a crash or session loss:**

1. Compare `git worktree list`, `git branch -a` and `git log` against the board and task files.
2. Classify every in-flight branch or worktree: merged (clean up) - complete but unmerged (re-run
   the gates, then merge) - abandoned mid-work (inspect the diff; adopt or redo).
3. Remove orphaned locked worktrees and stale branches the crashed instance left.
4. Log the incident in the affected task files.

**Committed files and git state beat any agent's report.** A report can name branches or work that
do not exist.

**Silent stalls are crashes.** Never block open-ended on a background child. Every wait has a
deadline (about ten minutes): read the child's output artifact, then proceed or report the blocker
upward. A supervisor treats prolonged silence as a crash and resumes from file state.

**Completed missions leave a marker; crashed ones do not.** Close-out sets the master-plan phase to a
terminal state and logs a final `MISSION COMPLETE` row, then the instance terminates instead of
idling:

- No marker + silent = crashed mid-flight: resume from file state.
- Marker + silent = finished: do NOT resume or re-dispatch; stopping it is cleanup.

**Validate the mission brief on spawn.** Its task codes may belong to other `Active` tasks, HEAD may
be past its stated SHA, the checkout may hold another session's uncommitted work. Check git and the
board before registering or dispatching - **the board allocates task IDs, never the brief.** On a
code collision, renumber the NEW tasks; never overwrite an `Active` task file. Uncommitted work is
driven to completion or escalated - never stashed, discarded or clobbered. On conflicting premises,
stop and ask.

**Verify every board write.** `task.py` reads its rows back; a hand edit is read back by hand. At
close-out, `docs/tasks/done/` and the `Done` board rows agree 1:1.

**Another active writer.** Commits on the mainline or branches and worktrees you did not create mean
another instance is alive. Confirm with git, then settle merge ownership EXPLICITLY - one side hands
off or stands down, recorded in the affected task files.

**Isolation is verified, not assumed.** Before parallel dispatch, confirm with `git worktree list`
and each agent's working directory that isolation took effect. Prefer explicit `git worktree add`;
when in doubt, serialize.

## Merging and conflict resolution

The dangerous merge is not one that errors but one that SUCCEEDS and silently **drops** commits.
`merge-manager`, if fielded, carries these rules; otherwise the orchestrator applies them.

**One merger, serialized.** One actor merges to the mainline, one branch at a time, each merge
recomputed against the CURRENT tip. The orchestrator SEQUENCES the queue so PRs touching the same
file - above all the master-plan board - land in a non-colliding order. A branch behind the queue
rebases first and logs it; the merger never rebases a branch with a live worktree. **The agent that
authored a change never merges it.**

**CI must be GREEN, not pending.** Poll to a terminal state, keep working while waiting, and never
end the turn on a pending pipeline.

**Diff with three dots.** `git diff <mainline>...<branch>` (merge-base to tip), never `..`: two-dot
on a stale branch reports mainline commits as deletions by the branch.

**Union, do not pick a side.** When two branches append to the same list, table, board or barrel
export, keep BOTH. `--ours` / `--theirs` on a whole file is banned except for regenerable lockfiles
(reset to the mainline copy and regenerate).

**Prove nothing was dropped.** After a conflict, the merged test count is >= the sum of both sides'.
A `git mv` can stage a pure rename and drop the content edits to that file - check moved-and-edited
files kept their edits.

**Post-merge board audit, after EVERY merge.** Re-pull and confirm each task file's `status:` equals
its board row, and `Done` files and `Done` rows agree 1:1 - a one-sided conflict resolution reverts a
status flip with no error.

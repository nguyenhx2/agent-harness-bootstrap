# Task control - the orchestrator's analyze / decompose / register / drive loop

The procedure that makes a generated harness *operate* rather than merely exist. The generated
`.claude/rules/task-tracking.md` (loaded every session) states WHERE state lives and that it must be
written down; this file is the procedure and the canonical state machine. The orchestrator and the
rule LINK here; they do not restate it.

## The state machine (canonical - defined here, once)

Five states. No others exist. In particular there is no `Registered` state: a task that has been
registered but not started is **Planned**.

| State | Meaning | Lives in |
|---|---|---|
| `Planned` | Registered on the board and scoped, not started | `docs/tasks/active/` |
| `Active` | In progress. Exactly one owner | `docs/tasks/active/` |
| `Blocked` | Started, cannot proceed. The reason and the unblocker are recorded | `docs/tasks/active/` |
| `Pending` | Deliberately parked - a conscious decision to defer, not an obstacle | `docs/tasks/pending/` |
| `Done` | Complete, results recorded | `docs/tasks/done/` |

**A `Planned` task file lives in `active/`, not `pending/`.** The session-start scan reads
`docs/tasks/active/` - "on the work queue", not "being worked right now". A new task filed under
`pending/` is hidden from that scan and never picked up; `pending/` means *parked*, deliberately out
of sight.

Status lives in **two** places and they must always agree:

- the task file's frontmatter `status:` field, and
- the Status column of that task's row in `docs/tasks/master-plan.md`.

Every status change writes both, in the same step. `Blocked` and `Pending` are not synonyms: a
blocked task wants to move and cannot; a pending task could move and has been told not to.

## Phase 1 - analyze the requirement

Before creating any task:

1. Read `docs/tasks/master-plan.md` for the current phase, existing tasks, and open dependencies.
   Unfinished work (`Active` or `Blocked`) beats new missions.
2. Map the incoming requirement to the project's functional requirements where they exist. One
   mission may span several.
3. Identify scope boundaries: which agents, which modules, which decisions are still open. **Open
   decisions block planning** - dispatch the decision agents (`brainstormer` with `tech-researcher`
   for evidence, where fielded) BEFORE creating implementation tasks, and capture stack-affecting
   outcomes in an ADR first. A decision resting on an UNMEASURED assumption gets a timeboxed
   measurement spike first: a measured result routinely overturns a plausible guess.
4. Dispatch `spec-guardian` to verify scope and acceptance criteria before any implementation task
   starts.
5. Escalate to the owner - never decide silently - when the mission hits an owner-only trigger: a
   spec or ADR amendment, a new data-egress path, a change to rules/agents/hooks/settings or an
   Accepted ADR, a release, or any case where satisfying one requirement would violate another. A
   requirement-vs-requirement trade (a latency budget only reachable by dropping a required feature)
   is made by the owner, never by the orchestrator.

## Phase 2 - decompose into tasks

For each unit of work that is independently executable and verifiable:

- A one-sentence goal.
- Explicit acceptance criteria - observable, testable outcomes, not process steps.
- One owner agent (route per the orchestrator's routing table).
- Dependencies: which `TASK-NNN` must be `Done` first.
- Priority: P0 (blocks everything), P1 (important, not blocking), P2 (nice-to-have).
- A phase number consistent with `master-plan.md`.

Rule of thumb: if two sub-goals need different owner agents, or produce different verifiable
artifacts, they are different tasks. Never bundle unrelated work into one task.

## Phase 3 - register and create the task file

1. Create the task file from `docs/templates/TASK.md` via `/new-task`. Fill in title, goal,
   owner, deps, priority, phase, created date, acceptance criteria. Frontmatter starts at
   `status: Planned`.
2. Add the row to the index table in `docs/tasks/master-plan.md`: TASK code, title, owner, deps,
   priority, phase, status. Status starts `Planned`, flipping to `Active` on dispatch.
3. Append the first session-log row immediately:
   `| <date> | orchestrator | Task created and registered in master-plan | Planned |`
4. Task files are committed. They travel with the code: task-file updates ship in the same PR/MR as
   the work they describe.

## Phase 4 - drive the lifecycle

**During work:**

- After every meaningful unit of work, append a row to the task file's session-log table: Date,
  Agent, What was done, Result.
- When a decision is made, add a bullet under the task file's orchestration-notes with the decision
  and its rationale.
- When a blocker appears: set `Blocked` in BOTH locations and record what is missing and who can
  unblock it, in the session log and the notes. If it needs a human DECISION rather than more agent
  work - a policy call, a requirement trade-off, an owner-only trigger from Phase 1 - also write
  `human_gate: <reason>` in the frontmatter, so the board tells "waiting on a human" apart from a
  technical block. `board-check.py` rejects `human_gate` on any task not `Blocked`.
- When it clears: back to `Active` in BOTH locations, remove `human_gate` if it was set, with a
  session-log row noting the resolution.
- When an environment workaround is discovered (a compiler wrapper, a sandbox blocking loopback, a
  parallelism flag avoiding an OOM): record it in `docs/context/known-issues.md` the FIRST time,
  capturing the WORKAROUND, not just the symptom - otherwise every agent rediscovers the same gotcha.
- Frontmatter enums (`status`, `attempts`, `priority`, `human_gate`) and `deps:` cycles are
  machine-checked: `python .claude/scripts/board-check.py` (stdlib) exits 1 with findings on any
  violation. `/board-audit` runs it before its own sweeps - a malformed board makes them unreliable.

**Attempt discipline (the anti-loop rule).** Every dispatch increments the task's `attempts:`
frontmatter field and is logged with that number. A failed attempt may be re-dispatched ONCE to the
same agent, and the new brief must state what changed - an identical brief is a loop, not a retry,
and is never sent. At `attempts: 3` the task goes `Blocked` in both places with a record of what was
tried, and the orchestrator escalates to the user. No exceptions: what three briefs could not land, a
fourth will not fix.

**Spend capability before spending the user's attention.** The third attempt is the one place the
orchestrator may raise the seat's tier rather than only its brief: dispatch once at a higher
`effort:` (or, for a genuinely hard problem, the next model up) with a brief stating what the two
previous attempts got wrong. This does NOT add an attempt - it is attempt three, done better; if it
fails the task still goes `Blocked`. Record the tier change in the session row - a seat that
repeatedly needs escalation is a roster fact worth acting on (`reference/cost-model.md`). Escalation
is never the FIRST response to a failure: a wrong brief costs the same at any tier.

**No placeholders in a dispatched task.** A task whose acceptance criteria contain "TBD", "etc.",
or a file list ending in "and related files" is not ready to dispatch - the agent will fill the gap
with an invention, and the reviewer will have nothing to check it against. Name the files, name the
criteria, or leave the task Pending until you can.

**Failure-reason taxonomy.** Every failed dispatch is logged in the task's session row with an
`attempt-reason`, exactly one of:

- `infra` - the tooling failed, not the plan (flaky runner, crashed subprocess, network blip). May
  be re-dispatched with the SAME brief - the anti-loop rule does not apply; nothing about the brief
  was wrong.
- `scope` - the brief was insufficient or wrong. Governed by the anti-loop rule: re-dispatch needs a
  CHANGED brief, and the attempt counts toward the `attempts: 3` cap.
- `env` - the environment cannot do the work (a dependency the agent cannot install, a denied
  permission, a platform mismatch). Escalate immediately, without retrying or incrementing
  `attempts:` - no brief fixes an environment the agent cannot change.

**Resume protocol (mandatory at every session start).** Before continuing any task in a new or
compacted session, run `/task-resume TASK-NNN`: read `master-plan.md` for position and deps, then
the task file's session log and orchestration-notes. Trust files over conversation memory, and
verify the working tree (`git status` / `git diff`) - files record intent, the tree records reality.
Then reconcile the subagent archive: a `.claude/state/history/` entry newer than a task's last
session-log row is a finished run nobody logged - log it before dispatching anything new.

**Quality gates before `Done`.** `qa-test` (tests green, where fielded) → `code-reviewer` +
`security-reviewer` in parallel (or the merged `reviewer`) → `/secret-scan` → PR/MR opened. Never
skip a gate. Report a gate as passed ONLY when the task file's session log records the run: "done" /
"passed" / "merged" is a CLAIM to verify against git and the task file, never a fact - orchestrators
have reported "all gates green" over a log with no reviewer rows. Verify every claim before acting.

## Phase 5 - close out

1. Fill the task file's Outcome section: the PR/MR or commit SHA, what was delivered, follow-ups.
2. Set `status: Done` in the frontmatter AND in the `master-plan.md` row.
3. Append the final session-log row: `| <date> | orchestrator | Task closed out | Done - PR #NN |`
4. Move the file from `docs/tasks/active/` to `docs/tasks/done/`.
5. **Clean up git**: remove the task's worktree, delete the merged branch locally and on the remote
   (`git push origin --delete`), then `git fetch --prune` - long missions silently accumulate stale
   worktrees and branches.
6. **Clean up the environment.** `git status` never shows the debris agents leave *outside* the
   repo, and step 5 never catches it. Sweep for and delete: out-of-repo build outputs (redirected
   build/target dirs in sibling or scratch paths - often gigabytes), large blobs fetched to ad-hoc
   locations (models, datasets, fixtures - the app re-downloads to its real cache on demand), and
   throwaway wrappers, logs, diffs, and extracted dependency trees. Standing rule: **whoever
   redirects output out of the repo cleans that location at close-out.** Legitimate outputs (build,
   coverage, caches) belong in `.gitignore`; if an agent worked around a missing ignore, add it now.
   Deleting outside version control is irreversible, so this is **gated**: enumerate the paths,
   confirm each is genuinely agent-created scratch - never user data, never the live repo - and only
   then delete. On Windows a blanket `rm -rf` may be denied by the guardrails; use the native remove
   on explicitly enumerated paths.
7. Deliver a final summary: tasks completed (with codes), test and review status, open follow-ups and
   where their history lives.
8. Business-rule or tool changes discovered along the way → `/sync-context`.
9. If this close-out ends the whole MISSION (no `Active` or `Blocked` tasks left in scope), write the
   completion marker and terminate - see below.

## Crash recovery and single-instance discipline

**Only ONE orchestrator instance may drive a project at a time.** A crashed instance can auto-resume
later, so a replacement must verify the previous one is actually terminated - not presumed dead -
and reconcile state before dispatching. Two live orchestrators mean duplicate dispatches and
conflicting merges.

**Reconciliation, mandatory before the first dispatch after a crash or session loss:**

1. Compare git reality against the recorded plan: `git worktree list`, `git branch -a`, `git log`,
   cross-checked against the board and the task files.
2. Classify every in-flight branch or worktree: already merged (clean up) · complete but unmerged
   (re-run the gates, then merge) · abandoned mid-work (inspect the diff; adopt or redo).
3. Remove orphaned locked worktrees and stale branches left by the crashed instance.
4. Log the incident in the affected task files' session logs - the audit trail stays honest.

**Trust ordering: committed files and git state OVER any agent's final report.** A status report can
reference branches or work that do not exist. Verify every claim against git facts.

**Silent stalls are crashes.** Never block open-ended on a background child. Every wait has a
deadline: poll the child's output artifact, and past a sane bound (about ten minutes)
poll-and-proceed or report the blocker upward. Going silent equals crashing, and supervisors treat
prolonged silence that way: presume a crash and resume from file state - which works, by design.

**Completed missions leave a marker; crashed ones do not.** Close-out writes a durable marker - the
master-plan phase set to a terminal state plus a final `MISSION COMPLETE` session-log row - then the
instance terminates instead of idling. The two silent states become a file check, not a guess:

- No marker + silent = crashed mid-flight → resume from file state.
- Marker present + silent = finished → do NOT resume, do NOT re-dispatch. Nothing is in flight, and
  stopping that instance is cleanup, not interruption: all state already lives in committed files.

**Validate the mission brief on spawn.** Brief premises go stale: its task codes may already belong
to other `Active` tasks, HEAD may be ahead of the SHA it states, the checkout may carry another
session's uncommitted work. Validate against git and the board before registering or dispatching -
**the board allocates task IDs, never the brief.** On a code collision, renumber the NEW tasks;
never overwrite an `Active` task file. Uncommitted work in the tree is inspected and driven to
completion or escalated - never stashed, discarded, or clobbered. When premises conflict, stop and
ask rather than reconcile destructively.

**Verify every board write.** A registration or status write can silently fail even while the work
ships. After every board write, read the row back; at close-out at the latest, audit that
`docs/tasks/done/` and the `Done` board rows agree 1:1.

**Another active writer.** Commits you did not make on the mainline, or branches and worktrees you
did not create, mean another instance is alive. Verify with git facts, then renegotiate merge
ownership EXPLICITLY: one side hands off or stands down, recorded in the affected task files.
Ownership is never assumed by both sides.

**Isolation is verified, not assumed.** An isolation flag can silently fail and leave parallel agents
sharing one checkout, corrupting each other's runs. Before parallel dispatch, confirm it took effect:
`git worktree list`, and check each agent's working directory. Prefer explicit `git worktree add`;
when in doubt, serialize.

## Merging and conflict resolution

Merging is where parallel work is silently lost. The dangerous failure is NOT a merge that errors -
it is one that SUCCEEDS and quietly **drops** someone's commits. Treat every merge as a verification
step, not a mechanical one. If `merge-manager` is fielded it carries these rules; otherwise the
orchestrator merges and applies them itself.

**One merger, serialized.** One actor merges to the mainline, one branch at a time, each merge
recomputed against the CURRENT mainline tip - two merges computed against the same base is how work
gets dropped without an error. The orchestrator owns the merge queue and SEQUENCES it so PRs touching
the same file - above all the master-plan board - land in a non-colliding order: avoiding a conflict
beats resolving one. A branch behind the queue rebases first and says so in its session log; the
merger never rebases a branch with a live worktree - that branch belongs to its dev agent. **The
agent that authored a change never merges it.**

**CI must be GREEN, not pending.** Never merge on a presumed-green pipeline; poll to a terminal
state. Waiting for CI is not a reason to end the turn - poll in a loop and keep working; ending the
turn stalls the mission until a human pokes it.

**Diff with three dots, never two.** Inspect a PR with `git diff <mainline>...<branch>` (merge-base
to branch tip), never `..` (tip to tip): two-dot on a stale branch shows mainline commits gained
after the fork as if the BRANCH had deleted them - false "this PR removes X" findings that block
good work.

**Union, do not pick a side.** When two branches each append to the same list, table, board, or barrel
export, the resolution is almost always BOTH additions. `--ours` / `--theirs` on a whole file is banned
except for regenerable lockfiles (reset to the mainline copy and regenerate).

**Prove nothing was dropped.** After resolving a conflict, the merged test count must be >= the sum of
both sides' counts. A `git mv` can stage a pure rename and silently drop the content edits made to the
same file in the same change - verify that a moved-and-edited file kept its edits.

**Post-merge board audit, required after EVERY merge.** The master-plan board is the most
conflict-prone file in the repo: every task PR edits one row, and a merge that resolves a collision
by taking one side reverts a status flip with NO error. After every merge, re-pull and confirm each
task file's frontmatter status equals its board row, and `Done` files and `Done` rows agree 1:1.

# Task control — the orchestrator's analyze / decompose / register / drive loop

The procedure that makes a generated harness *operate* rather than merely exist. The generated
project carries the enforceable version of this as `.claude/rules/task-tracking.md`, which loads in
every session; that rule states WHERE state lives and that it must be written down. This file is the
procedure and the canonical state machine. The orchestrator and the rule LINK here; they do not
restate it.

## The state machine (canonical — defined here, once)

Five states. No others exist. In particular there is no `Registered` state: a task that has been
registered but not started is **Planned**.

| State | Meaning | Lives in |
|---|---|---|
| `Planned` | Registered on the board and scoped, not started | `docs/tasks/active/` |
| `Active` | In progress. Exactly one owner | `docs/tasks/active/` |
| `Blocked` | Started, cannot proceed. The reason and the unblocker are recorded | `docs/tasks/active/` |
| `Pending` | Deliberately parked — a conscious decision to defer, not an obstacle | `docs/tasks/pending/` |
| `Done` | Complete, results recorded | `docs/tasks/done/` |

**A `Planned` task file lives in `active/`, not `pending/`.** This looks wrong and is not. The
orchestrator's session-start scan reads `docs/tasks/active/` — that directory means "on the work
queue", not "being worked right now". Filing a newly-registered task under `pending/` would hide it
from the scan, and it would never be picked up. `pending/` means *parked*, and parked work is
deliberately out of sight.

Status lives in **two** places and they must always agree:

- the task file's frontmatter `status:` field, and
- the Status column of that task's row in `docs/tasks/master-plan.md`.

Every status change writes both, in the same step. `Blocked` and `Pending` are not synonyms: a
blocked task wants to move and cannot; a pending task could move and has been told not to.

## Phase 1 — analyze the requirement

Before creating any task:

1. Read `docs/tasks/master-plan.md` for the current phase, existing tasks, and open dependencies.
   Unfinished work (`Active` or `Blocked`) takes priority over new missions.
2. Map the incoming requirement to the project's functional requirements where they exist. One
   mission may span several.
3. Identify scope boundaries: which agents, which modules, which decisions are still open. **Open
   decisions block planning** — dispatch the decision agents (`brainstormer` with `tech-researcher`
   for evidence) BEFORE creating implementation tasks, and capture stack-affecting outcomes in an ADR
   first. When a decision rests on an UNMEASURED assumption, run a timeboxed measurement spike before
   committing: a measured result routinely overturns a plausible-sounding guess.
4. Dispatch `spec-guardian` to verify scope and acceptance criteria before any implementation task
   starts.
5. Escalate to the owner — never decide silently — when the mission hits an owner-only trigger: a
   spec or ADR amendment, a new data-egress path, a change to rules/agents/hooks/settings or an
   Accepted ADR, a release, or any case where satisfying one requirement would violate another. A
   requirement-vs-requirement trade (a latency budget only reachable by dropping a required feature)
   is made by the owner, never by the orchestrator.

## Phase 2 — decompose into tasks

For each unit of work that is independently executable and verifiable:

- A one-sentence goal.
- Explicit acceptance criteria — observable, testable outcomes, not process steps.
- One owner agent (route per the orchestrator's routing table).
- Dependencies: which `TASK-NNN` must be `Done` first.
- Priority: P0 (blocks everything), P1 (important, not blocking), P2 (nice-to-have).
- A phase number consistent with `master-plan.md`.

Rule of thumb: if two sub-goals need different owner agents, or produce different verifiable
artifacts, they are different tasks. Never bundle unrelated work into one task.

## Phase 3 — register and create the task file

1. Create the task file from `docs/templates/TASK.md.template` via `/new-task`. Fill in title, goal,
   owner, deps, priority, phase, created date, acceptance criteria. Frontmatter starts at
   `status: Planned`.
2. Add the row to the index table in `docs/tasks/master-plan.md`: TASK code, title, owner, deps,
   priority, phase, status. Status starts `Planned`; it flips to `Active` when the task is dispatched.
3. Append the first session-log row immediately:
   `| <date> | orchestrator | Task created and registered in master-plan | Planned |`
4. Task files are committed. They travel with the code: task-file updates ship in the same PR/MR as
   the work they describe.

## Phase 4 — drive the lifecycle

**During work:**

- After every meaningful unit of work, append a row to the task file's session-log table: Date,
  Agent, What was done, Result.
- When a decision is made, add a bullet under the task file's orchestration-notes with the decision
  and its rationale.
- When a blocker appears: set `Blocked` in BOTH locations and record what is missing and who can
  unblock it, in the session log and the notes.
- When it clears: back to `Active` in BOTH locations, with a session-log row noting the resolution.
- When an environment workaround is discovered (a compiler needing a specific wrapper, a sandbox that
  blocks loopback, a parallelism flag that avoids an OOM): record it in `docs/context/known-issues.md`
  the FIRST time it is found, capturing the WORKAROUND and not just the symptom. Otherwise every agent
  rediscovers the same gotcha.

**Resume protocol (mandatory at every session start).** Before continuing any task in a new or
compacted session, run `/task-resume TASK-NNN`: read `master-plan.md` for position and deps, then the
task file's session log and orchestration-notes. Trust the files over conversation memory, and verify
the working tree (`git status` / `git diff`) before continuing — files record intent, the tree records
reality.

**Quality gates before `Done`.** `qa-test` (tests green) → `code-reviewer` + `security-reviewer` in
parallel → `/secret-scan` → PR/MR opened. Never skip a gate. Report a gate as passed ONLY when the
task file's session log records the run: an agent's "done" / "passed" / "merged" is a CLAIM to verify
against git and the task file, never a fact. Orchestrators have reported "all gates green" over a log
holding no reviewer rows at all. The dispatcher verifies every claim before acting on it.

## Phase 5 — close out

1. Fill the task file's Outcome section: the PR/MR or commit SHA, what was delivered, follow-ups.
2. Set `status: Done` in the frontmatter AND in the `master-plan.md` row.
3. Append the final session-log row: `| <date> | orchestrator | Task closed out | Done - PR #NN |`
4. Move the file from `docs/tasks/active/` to `docs/tasks/done/`.
5. **Clean up git**: remove the task's worktree, delete the merged branch both locally and on the
   remote (`git push origin --delete`), then `git fetch --prune`. A long mission silently accumulates
   stale worktrees and merged branches.
6. **Clean up the environment.** `git status` never shows the debris agents leave *outside* the repo,
   and step 5 never catches it. Before declaring a mission done, sweep for and delete: out-of-repo
   build outputs (a redirected build/target dir in a sibling or scratch path — often gigabytes),
   large blobs fetched to ad-hoc locations (models, datasets, fixtures — the app re-downloads to its
   real cache on demand), and throwaway wrappers, logs, diffs, and extracted dependency trees.
   Standing rule: **whoever redirects output out of the repo cleans that location at close-out.**
   Anything the harness legitimately produces (build output, coverage, caches) belongs in
   `.gitignore`; if an agent had to work around a missing ignore, add it now.
   This step deletes real files outside version control and is irreversible, so it is **gated**:
   enumerate the paths, confirm each is genuinely agent-created scratch — never user data, never the
   live repo — and only then delete. On Windows a blanket `rm -rf` may be denied by the guardrails;
   use the native remove on explicitly enumerated paths.
7. Deliver a final summary: tasks completed (with codes), test and review status, open follow-ups and
   where their history lives.
8. Business-rule or tool changes discovered along the way → `/sync-context`.
9. If this close-out ends the whole MISSION (no `Active` or `Blocked` tasks left in scope), write the
   completion marker and terminate — see below.

## Crash recovery and single-instance discipline

**Only ONE orchestrator instance may drive a project at a time.** A crashed instance can auto-resume
later, so before a replacement dispatches anything it must verify the previous one is actually
terminated — not presumed dead — and reconcile state first. Two live orchestrators mean duplicate
dispatches and conflicting merges.

**Reconciliation, mandatory before the first dispatch after a crash or session loss:**

1. Compare git reality against the recorded plan: `git worktree list`, `git branch -a`, `git log`,
   cross-checked against the board and the task files.
2. Classify every in-flight branch or worktree: already merged (clean it up) · complete but unmerged
   (re-run the gates, then merge) · abandoned mid-work (inspect the diff; adopt it or redo the task).
3. Remove orphaned locked worktrees and stale branches left by the crashed instance.
4. Log the incident in the affected task files' session logs, so the audit trail stays honest.

**Trust ordering: committed files and git state OVER any agent's final report.** A status report can
reference branches or work that do not exist. Verify every claim against git facts.

**Silent stalls are crashes.** Never block open-ended on a background child's completion. Every wait
has a deadline: poll the child's output artifact, and if a wait exceeds a sane bound (about ten
minutes), poll-and-proceed or report the blocker upward. Going silent is a failure mode equal to
crashing. Supervisors treat prolonged silence the same way: presume the instance crashed and resume it
from file state — which works, by design.

**Completed missions leave a marker; crashed ones do not.** Close-out writes a durable marker — the
master-plan phase set to a terminal state plus a final `MISSION COMPLETE` session-log row — and then
the instance terminates instead of idling. This makes the two silent states distinguishable by a file
check rather than a guess:

- No marker + silent = crashed mid-flight → resume from file state.
- Marker present + silent = finished → do NOT resume, do NOT re-dispatch. Nothing is in flight, and
  stopping that instance is cleanup, not interruption: all state already lives in committed files.

**Validate the mission brief on spawn.** A brief's premises go stale: the task codes it names may
already belong to other `Active` tasks, HEAD may be ahead of the SHA it states, the checkout may carry
another session's uncommitted work. Before registering or dispatching anything, validate the brief
against git and the board — **the board allocates task IDs, never the brief.** On a code collision,
renumber the NEW tasks; never overwrite an `Active` task file. Uncommitted work found in the tree is
inspected and driven to completion or escalated — never stashed, discarded, or clobbered. When
premises conflict, stop and ask rather than reconcile destructively.

**Verify every board write.** A registration or status write can silently fail even while the work
ships and the task file exists. After every board write, read the row back. At close-out at the
latest, audit that `docs/tasks/done/` and the `Done` board rows agree 1:1.

**Another active writer.** Commits you did not make landing on the mainline, or branches and worktrees
you did not create, mean another instance is alive. Verify with git facts, then renegotiate merge
ownership EXPLICITLY: one side hands off or stands down, and the handoff is recorded in the affected
task files. Ownership is never assumed by both sides.

**Isolation is verified, not assumed.** An isolation flag can silently fail and leave parallel agents
sharing one checkout, corrupting each other's runs. Before parallel dispatch, confirm it took effect:
`git worktree list`, and check each agent's working directory. Prefer explicit `git worktree add`;
when in doubt, serialize.

## Merging and conflict resolution

Merging is where parallel work is silently lost. The dangerous failure is NOT a merge that errors — it
is one that SUCCEEDS and quietly **drops** someone's commits. This happens more than once on a long
mission, so treat every merge as a verification step, not a mechanical one. If `merge-manager` is
fielded it carries these rules; otherwise the orchestrator merges and applies them itself.

**One merger, serialized.** One actor merges to the mainline, one branch at a time, each merge
recomputed against the CURRENT mainline tip. Two merges computed against the same base is how work
gets dropped without an error. The orchestrator owns the merge queue and SEQUENCES it so that PRs
touching the same file — above all the master-plan board — land in a non-colliding order: avoiding a
conflict beats resolving one. A branch behind the queue rebases before it is merged and says so in its
session log; the merger never rebases a branch that has a live worktree — that branch belongs to its
dev agent. **The agent that authored a change never merges it.**

**CI must be GREEN, not pending.** Never merge on a presumed-green pipeline; poll it to a terminal
state. Waiting for CI is not a reason to end the turn — poll in a loop and keep working. Ending the
turn to wait stalls the whole mission until a human pokes it.

**Diff with three dots, never two.** Inspect a PR with `git diff <mainline>...<branch>` (merge-base to
branch tip), never `git diff <mainline>..<branch>` (tip to tip). Two-dot on a stale branch shows every
commit the mainline gained after the fork as if the BRANCH had deleted it — producing false "this PR
removes X" findings that block good work.

**Union, do not pick a side.** When two branches each append to the same list, table, board, or barrel
export, the resolution is almost always BOTH additions. `--ours` / `--theirs` on a whole file is banned
except for regenerable lockfiles (reset to the mainline copy and regenerate).

**Prove nothing was dropped.** After resolving a conflict, the merged test count must be >= the sum of
both sides' counts. A `git mv` can stage a pure rename and silently drop the content edits made to the
same file in the same change — verify that a moved-and-edited file kept its edits.

**Post-merge board audit, required after EVERY merge.** The master-plan board is the most
conflict-prone file in the repo: every task PR edits one row, so it collides constantly, and a merge
that resolves the collision by taking one side reverts a status flip with NO error. After every merge,
re-pull and confirm that each task file's frontmatter status equals its board row, and that the `Done`
files and `Done` rows still agree 1:1.

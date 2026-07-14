# Task control - orchestrator analyze/create/control procedure

## Table of contents

1. [Authority and hierarchy](#authority-and-hierarchy)
2. [The canonical loop](#the-canonical-loop)
   - [Phase 1 - Analyze the requirement](#phase-1---analyze-the-requirement)
   - [Phase 2 - Decompose into tasks](#phase-2---decompose-into-tasks)
   - [Phase 3 - Register and create task files](#phase-3---register-and-create-task-files)
   - [Phase 4 - Drive the lifecycle](#phase-4---drive-the-lifecycle)
   - [Phase 5 - Close out](#phase-5---close-out)
3. [Worked example - Active to Blocked to Done](#worked-example---active-to-blocked-to-done)
4. [Crash recovery and single-instance discipline](#crash-recovery-and-single-instance-discipline)
5. [Merging and conflict resolution](#merging-and-conflict-resolution)
6. [Promotion path](#promotion-path)

---

## Authority and hierarchy

**`../../../rules/task-tracking.md` is the ENFORCEABLE RULE.**
This document is the OPERATIONAL PROCEDURE that implements that rule.
On any conflict between this procedure and the rule, THE RULE WINS.
Read the rule file first before acting on any section here.

This document exists to consolidate the orchestrator's analyze/decompose/register/lifecycle loop in
one place, so that `orchestrator.md` and `task-tracking.md` can link here instead of each
re-describing the same steps. Do not add enforcement semantics here; add them to the rule file.

---

## The canonical loop

### Phase 1 - Analyze the requirement

Before creating any task:

1. Read `docs/tasks/master-plan.md` to understand the current phase, existing tasks, and open
   dependencies. Unfinished work (status: Active or Blocked) takes priority over new missions.
2. Map the incoming requirement to the project's functional requirements where they exist (e.g.
   FR-NN entries documented in the project's specs). A single mission may span multiple FRs.
3. Identify scope boundaries: which agents will be involved, which files or modules are affected,
   and which decisions are still open. Open decisions block planning - dispatch the appropriate
   decision agent (e.g. `brainstormer` with `tech-researcher` for evidence) BEFORE creating
   implementation tasks. Capture stack-affecting outcomes in an ADR before implementation starts.
   When a planning decision rests on an UNMEASURED assumption, run a measurement spike (a small,
   timeboxed experiment) before committing to the choice - a measured result routinely overturns a
   plausible-sounding guess and can reveal the real constraint (e.g. a capability limited along one
   dimension that no amount of tuning a different dimension can ever fix).
4. Dispatch `spec-guardian` to verify scope and acceptance criteria before any implementation
   task starts.
5. Escalate to the owner - never decide silently - when the mission hits an owner-only trigger:
   a spec or ADR amendment, a new data-egress path, a change that only an owner-gated merge can
   land (rules, agents, hooks, settings, or Accepted ADRs - see "Self-governing changes" in
   `guardrails-hooks.md`), a release, or any case where satisfying one requirement would
   violate another. A budget-vs-budget or requirement-vs-requirement conflict (e.g. a latency
   budget that can only be met by dropping an opt-in feature the spec requires) is traded by the
   owner, never silently by the orchestrator.

### Phase 2 - Decompose into tasks

For each unit of work that is independently executable and verifiable:

- Write a clear goal statement (one sentence).
- Define explicit acceptance criteria (observable, testable outcomes - not process steps).
- Assign an owner agent (single agent per task; route per the orchestrator routing table).
- Identify dependencies (which other TASK-NNN must be Done before this one can start).
- Assign priority: P0 (blocks everything), P1 (important but not blocking), P2 (nice-to-have).
- Assign a phase number consistent with `master-plan.md`.

Rule of thumb: if two sub-goals require different owner agents or produce different verifiable
artifacts, they are separate tasks. Never bundle unrelated work into one task.

### Phase 3 - Register and create task files

For every task identified in Phase 2:

1. Create the task file from the project template (`docs/templates/TASK.md.template`) using
   the `/new-task` command. Fill in: title, goal, owner, deps, priority, phase, created date,
   acceptance criteria. Set frontmatter `status: Active` when the task begins.
2. Add a row to the index table in `docs/tasks/master-plan.md` with columns: TASK code, title,
   owner agent, deps, priority, phase, status. Status starts as Planned until the task is
   dispatched, then Active.
3. Add a first session-log row to the task file immediately after creation:
   `| <date> | orchestrator | Task created and registered in master-plan | Planned |`
4. Task files are committed to the repo. They travel with the code: include task-file updates
   in the same MR as the work they describe.

### Phase 4 - Drive the lifecycle

The three states are Active, Blocked, and Done. Both locations must always agree:

- The task file frontmatter field `status:`.
- The Status column in `docs/tasks/master-plan.md` for the same TASK-NNN row.

**Mandatory actions during work:**

- After every meaningful unit of work: append a row to the task file's AI session log table
  with columns: Date, Agent, What was done, Result.
- When a decision is made: add a bullet under the orchestration-notes section of the task file
  recording the decision and its rationale.
- When a blocker is found: set status to Blocked in BOTH locations and record the blocker
  (what is missing, who can unblock it) in the session log and orchestration-notes.
- When a blocker is resolved: set status back to Active in BOTH locations and append a
  session-log row noting the resolution.
- When an environment workaround is discovered (a compiler needing a specific env wrapper, a
  sandbox that blocks loopback so certain tests only pass with it disabled, a parallelism flag that
  avoids an OOM): record it in `docs/context/known-issues.md` the FIRST time it is found, capturing
  the WORKAROUND and not just the symptom - otherwise every agent rediscovers the same gotcha.

**Agent resume protocol (mandatory at every session start):**
Before continuing any task in a new or compacted session, run `/task-resume TASK-NNN`:
read `docs/tasks/master-plan.md` for position and deps, then read the task file's session log
and orchestration-notes. Trust the files over conversation memory. Verify the working tree
(git status/diff) before continuing - files record intent, the tree records reality.

**Quality gates before Done:**
`qa-test` (tests green) -> `code-reviewer` + `security-reviewer` in parallel -> `/secret-scan`
-> MR opened via `/review-mr`. Never skip a gate. Report a gate as passed ONLY when the task file's
session log records the run - an agent's "done"/"passed"/"merged" is a CLAIM to verify against git
and the task file, never a fact (an orchestrator once reported "all gates green" when the log held
no reviewer rows at all; a reviewer once returned a confidently wrong finding). The dispatcher
verifies every such claim before acting on it.

### Phase 5 - Close out

When all acceptance criteria are met and quality gates have passed:

1. Fill the "Outcome" (or "Result") section of the task file: link the MR or commit SHA,
   note what was delivered and any follow-up items.
2. Set `status: Done` in the task file frontmatter AND update the Status column in
   `master-plan.md`.
3. Append a final session-log row:
   `| <date> | orchestrator | Task closed out | Done - MR #NN |`
4. Move the task file from `docs/tasks/active/` to `docs/tasks/done/`. Then clean up the task's git
   leftovers: remove its worktree and delete its merged branch - BOTH local and the remote branch
   (`git push origin --delete`), and `git fetch --prune` so stale remote-tracking refs go too. A long
   mission accumulates stale worktrees and merged branches that must be pruned explicitly or they pile
   up.
5. Deliver a final summary to the user: tasks completed (with TASK codes), test and review
   status, any open follow-up items and where their history lives.
6. Business-rule or tool changes discovered along the way -> `/sync-context`.
7. When this close-out ends the whole MISSION (no Active/Blocked tasks left in its scope), also
   write the mission-completion marker and terminate instead of idling - see "Completed missions
   leave a marker" under crash recovery below.
8. **Workspace cleanup - sweep the environment, not just git.** Agents leave debris OUTSIDE the
   repo that `git status` never shows and the per-task cleanup above never catches. Before declaring
   a mission done, sweep for and remove it:
   - **Out-of-repo build artifacts.** Agents that redirect `CARGO_TARGET_DIR` (or any build/output
     dir) to a scratch path to dodge worktree rebuilds leave whole target trees behind - often as
     sibling dirs next to the repo (e.g. a `<repo>-wt/` parent, or ad-hoc `D:\t14`-style folders).
     Each is easily gigabytes. Find and delete them. The rule for agents: whoever redirects output
     out of the repo cleans that location at task close-out.
   - **Downloaded large blobs.** Model files, datasets, or fixtures fetched to ad-hoc scratch
     locations (not the app's real, gitignored cache) are pure junk once the task is done - the app
     re-downloads to its proper cache on demand. Delete them; do not leave a stray multi-hundred-MB
     model blob in a temp folder.
   - **Throwaway wrappers and logs.** One-off build/run wrapper scripts, `*.log`, `*.diff`, extracted
     dependency source trees, and copied source files left in a scratchpad or beside the repo. Clear
     the scratchpad except anything an in-flight process still holds open.
   - Anything the bootstrap itself seeds as ignorable (build output, `models/`, coverage) belongs in
     `.gitignore`; if an agent had to work around a missing ignore, add it now so the debris cannot
     be committed next time.
   Note for the destructive step: environment cleanup deletes real files outside version control and
   is irreversible, so it is a gated action - enumerate what you will remove and confirm each path is
   genuinely agent-created scratch, never user data or the live repo, before deleting. On Windows,
   a blanket `rm -rf` may be denied by guardrails; use the platform's native remove
   (`Remove-Item -Recurse -Force`) on explicitly enumerated paths.

---

## Worked example - Active to Blocked to Done

This example uses a generic, synthetic task with no real candidate data or PII.

### Setup

Suppose the orchestrator receives the mission: "Add a health endpoint so the platform runner can
probe service liveness." It maps to no specific FR (infrastructure concern) and is assigned
TASK-200.

**master-plan.md row (initial):**

```
| TASK-200 | add health endpoint to web service | devops | - | P1 | 5 | Planned |
```

**Task file created** at `docs/tasks/active/TASK-200-add-health-endpoint.md`:

```markdown
---
title: "TASK-200: Add a health endpoint to the web service"
status: Planned
fr: "-"
owner: devops
deps: "-"
priority: P1
phase: 5
created: 2026-01-10
---

# TASK-200: Add a health endpoint to the web service

## Goal
Expose GET /health returning { status, version, commit, builtAt } so the Railway runner
can probe service liveness without touching application logic.

## Acceptance criteria
- [ ] GET /health returns HTTP 200 with JSON body { status: "ok", version, commit, builtAt }.
- [ ] version resolves from GIT_SHA env var, degrades to "unknown" when unset (never throws).
- [ ] Unit test covers the "GIT_SHA unset" degradation path.
- [ ] No secrets or PII in the response body.

## AI session log

| Date       | Agent        | What was done                             | Result  |
|------------|--------------|-------------------------------------------|---------|
| 2026-01-10 | orchestrator | Task created and registered in master-plan | Planned |
```

### Transition: Planned -> Active

The orchestrator dispatches `devops` to implement. It updates BOTH locations:

- Task file frontmatter: `status: Planned` -> `status: Active`
- master-plan.md Status column: `Planned` -> `Active`

Session-log row appended to the task file:

```
| 2026-01-10 | orchestrator | Dispatched devops to implement /health endpoint | Active |
```

### Mid-work session log (devops agent working)

```
| 2026-01-11 | devops | Created src/app/api/health/route.ts; resolves GIT_SHA with fallback | In progress |
| 2026-01-11 | devops | Added Vitest unit test for GIT_SHA-unset path; all tests green | In progress |
```

### Transition: Active -> Blocked

The `devops` agent finds that the CI runner is offline and cannot validate the pipeline step.

- Task file frontmatter: `status: Active` -> `status: Blocked`
- master-plan.md Status column: `Active` -> `Blocked`

Session-log row:

```
| 2026-01-12 | devops | CI runner #196 offline; pipeline cannot validate the build step | Blocked |
```

Orchestration-note added to the task file:

```
- Blocker 2026-01-12: CI runner offline. Unblocked by: starting Docker Desktop on
  the workstation or registering a spare runner in Settings -> CI/CD -> Runners.
```

### Transition: Blocked -> Active -> Done

The runner comes back online. The orchestrator re-dispatches `devops`.

- Task file frontmatter: `status: Blocked` -> `status: Active`
- master-plan.md Status column: `Blocked` -> `Active`

Session-log rows:

```
| 2026-01-13 | orchestrator | Runner back online; re-dispatching devops          | Active |
| 2026-01-13 | devops       | Pipeline green; /review-mr run; MR #42 opened     | Active |
| 2026-01-13 | orchestrator | MR #42 approved and merged; all acceptance criteria met | Done |
```

Outcome section filled:

```
## Outcome
MR !42 merged (commit abc1234). GET /health returns { status, version, commit, builtAt };
degrades gracefully when GIT_SHA is unset. Follow-up: set GIT_SHA as a Railway service
variable at deploy time (see railway.md "Provenance & audit").
```

Final state:

- Task file frontmatter: `status: Done`
- master-plan.md Status column: `Done`
- Task file moved from `docs/tasks/active/` to `docs/tasks/done/`.

**master-plan.md row (final):**

```
| TASK-200 | add health endpoint to web service | devops | - | P1 | 5 | Done |
```

---

## Crash recovery and single-instance discipline

Only ONE orchestrator instance may drive a project at a time. A crashed instance can auto-resume
later, so before a replacement instance dispatches anything it must verify the previous instance
is actually terminated - not merely presumed dead - and reconcile state first. Two live
orchestrators mean duplicate dispatches and conflicting merges.

**Reconciliation procedure (mandatory before the first dispatch after a crash or session loss):**

1. Compare git reality against the recorded plan: run `git worktree list`, `git branch -a`, and
   `git log`, then cross-check the results with the master-plan board and the task files.
2. Classify every in-flight branch/worktree as one of:
   - Already merged - clean up the branch/worktree.
   - Complete but unmerged - re-run the quality gates, then merge.
   - Abandoned mid-work - inspect the diff; adopt the work or redo the task.
3. Remove orphaned locked worktrees and stale branches left behind by the crashed instance.
4. Log the incident in the affected task files' session logs so the audit trail stays honest.

**Trust ordering:** committed files and git state OVER any agent's final report. A status report
can reference branches or work that do not exist; verify every claim with `git` facts (branch
exists, commits present, diff matches) before acting on it.

**Silent stalls are crashes.** Never block open-ended on a background child's completion
notification. Every wait has a deadline: poll the child's output artifact, and if a wait exceeds a
sane bound (about 10 minutes), either poll-and-proceed or report the blocker upward - going silent
is a failure mode equal to crashing. Supervisors treat prolonged silence the same way: presume the
instance crashed and resume it from file state, which works by design.

**Completed missions leave a marker; crashed missions do not.** The positive counterpart of the
rule above: mission close-out (the orchestrator's "Close out" step) writes a durable completion
marker - the master-plan phase/status set to a terminal state (`Complete`) plus a final
`MISSION COMPLETE` session-log row - and then the instance terminates instead of idling. This
makes the two silent states distinguishable by a file check, never a guess:

- **No marker + silent** = crashed mid-flight -> resume from file state (procedure above).
- **Marker present + silent** = done -> do NOT resume, do NOT re-dispatch; nothing is in flight.

For the supervisor or user: an idle orchestrator whose completion marker is present is finished -
stopping that instance is cleanup, not interruption, and loses nothing, because all state already
lives in the committed files.

**Validate the mission brief on spawn.** A brief's premises can be stale by the time an instance
starts: the task codes it names may already belong to other Active tasks, HEAD may be ahead of the
stated SHA, the checkout may carry another session's uncommitted work-in-progress. Before
registering or dispatching anything, validate the brief against git and the board - the board
allocates task IDs, never the brief. On a code collision, renumber the NEW tasks; never overwrite
Active task files. Uncommitted WIP found in the tree is inspected and driven to completion or
escalated - never stashed, discarded, or clobbered. When premises conflict, stop and ask the
dispatcher rather than reconcile destructively.

**Verify every board write.** A registration or status write to the master-plan can silently fail
even while the work ships and the task files exist. After every board write, read the row back to
confirm it landed. Periodically - at close-out at the latest - audit that `docs/tasks/done/` task
files and board rows agree 1:1.

**Another active writer.** Commits you did not make landing on the mainline, or branches/worktrees
you did not create, mean another instance is alive (a user can revive a stopped one directly).
Verify the overlap with git facts, then renegotiate merge ownership EXPLICITLY: one side hands off
or stands down, and the handoff is recorded in the affected task files. Ownership is never assumed
by both sides.

**Isolation is verified, not assumed.** A tool's isolation flag can silently fail and leave
parallel agents sharing one checkout, corrupting each other's runs. Before parallel dispatch,
confirm isolation took effect: run `git worktree list` and check each agent's working directory.
Prefer explicit `git worktree add`; when in doubt, serialize.

---

## Merging and conflict resolution

Merging is where parallel work is silently lost. The dangerous failure is NOT a merge that errors -
it is one that SUCCEEDS and quietly drops someone's commits. This happens more than once on a long
mission, so treat every merge as a verification step, not a mechanical one. If a `merge-manager`
agent is fielded, it carries these rules and the orchestrator dispatches it; otherwise the
orchestrator merges directly and applies them itself.

**One merger, serialized.** Only one actor merges to the mainline, one branch at a time, each merge
recomputed against the CURRENT mainline tip. Two merges computed against the same base is how work
gets dropped without an error. The orchestrator owns the merge queue and SEQUENCES it so that PRs
touching the same file (above all the master-plan board) land in a non-colliding order - avoiding a
conflict beats resolving one. A branch behind the queue rebases before it is merged, and the branch
tells the merger this via a session-log note; the merger never rebases a branch that has a live
worktree - that branch belongs to its dev agent, and a stale one is rebased by that agent, not the
merger. The agent that authored a change never merges it.

**CI must be GREEN, not pending.** Do not merge on a pending or presumed-green pipeline; poll it to
a terminal state first. Waiting for CI is not a reason to end the turn - poll in a loop and keep
working (see "Silent stalls are crashes" above); ending the turn to wait stalls the whole mission
until a human pokes it.

**Diff with three dots, never two.** Inspect a PR with `git diff <mainline>...<branch>` (merge-base
to branch tip), never `git diff <mainline>..<branch>` (tip to tip). Two-dot on a stale branch shows
every commit the mainline gained after the fork as if the BRANCH deleted it, producing false "this
PR removes X" findings that wrongly block good work - a real false-block.

**Union, do not pick a side.** When two branches each append to the same list, table, board, or
barrel export, the resolution is almost always BOTH additions, merged. `--ours`/`--theirs` on a
whole file is banned except for regenerable lockfiles (reset to the mainline copy and regenerate).

**Prove nothing was dropped.** After resolving a conflict, the merged test count must be >= the sum
of both sides' counts. A `git mv` can stage a pure rename and silently drop the content edits made
to the same file in the same change - verify a moved-and-edited file kept its edits.

**Post-merge board audit (required after EVERY merge).** The master-plan board is the single most
conflict-prone file: every task PR edits one row of it, so it collides constantly, and a merge that
resolves the collision by taking one side reverts a status flip with NO error. After every merge,
re-pull and confirm each task file's frontmatter status equals its board row, and that completed
task files and completed board rows agree 1:1.

---

## Promotion path

This document is currently Option A from ADR-021: a reference doc bundled inside the
`project-bootstrap` skill. It contains only prose and a worked example - no executable assets.

If the project later needs executable assets alongside this procedure - for example:
- A task-lint/verifier script that checks whether a task file has all required frontmatter fields.
- A scaffold-and-register script that creates a task file from the template AND adds the
  master-plan row in one command (beyond what `/new-task` does today).

...then promote this doc into a standalone `task-control` skill (ADR-021 Option B), mirroring
how the `db-seed` skill packages its templates and scripts in a dedicated directory alongside
its SKILL.md. At that point, update the pointer in `project-bootstrap/SKILL.md` step 5 to
reference the new skill, and update the links in `orchestrator.md` and `task-tracking.md`
accordingly.

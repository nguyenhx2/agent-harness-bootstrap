---
title: "TASK-NNN: <short title>"
status: Planned
# Canonical task state machine for this repository. These five states are the only valid values of
# `status:`, here and in the docs/tasks/master-plan.md board row. Every other file refers back to
# this definition rather than restating it.
#   Planned - registered on the board, not started
#   Active  - in progress
#   Blocked - cannot proceed; the reason and who can unblock it are recorded below
#   Pending - deliberately parked; the reason is recorded below; the file moves to docs/tasks/pending/
#   Done    - complete; the result is recorded below; the file moves to docs/tasks/done/
fr: <FR-NN, or "-">
# WHO ASKED FOR THIS. A task is work the user agreed to; no agent opens one on its own, and that
# includes every subagent (.claude/rules/task-tracking.md). Record what they actually said or the
# request it came from - "user: split the billing module", "issue #41" - so a reader six weeks
# later can tell agreed work from work that appeared. `user` alone is not an answer, and neither is
# an agent name: an agent cannot approve its own task. The guard-task-scope hook refuses a task
# file without it.
requested_by: <what the user asked for, or the issue/PR this came from>
owner: <agent>
deps: <TASK-NNN, TASK-NNN, or "-">
# Optional. Set only when status: Blocked AND the blocker needs a human DECISION rather than more
# agent work - a policy call, a requirement trade-off, an owner-only trigger. Value is the reason. board-check.py rejects human_gate on any status other than
# Blocked, and the orchestrator's session-start scan lists human_gate rows before ordinary
# Active/Blocked ones. Omit the field entirely on a task that has never needed it.
# human_gate: <reason>
# Dispatch attempts so far. The orchestrator increments this on every dispatch of this task and
# stops at 3: after two failed re-dispatches the task goes Blocked and escalates to the user
# (orchestrator.md, Supervise). This is the counter that makes "retry forever" impossible to do silently.
attempts: 0
priority: <P0 | P1 | P2>
phase: <phase number in docs/tasks/master-plan.md, or "-">
created: <YYYY-MM-DD>
tags: [task]
---

<!-- Task files are written 100% in English (see .claude/rules/task-tracking.md). -->

# TASK-NNN: <short title>

Change status with `python .claude/scripts/task.py move TASK-NNN <state>`: it writes the `status:`
field above, moves this file to its folder, flips the row in `docs/tasks/master-plan.md`, logs the
change and reads the row back. Never edit those by hand - that is how they come to disagree.

## Goal

<One sentence describing the desired outcome.>

## Inputs and context

- Related FR: [FR-NN](../../specs/05-functional-requirements.md#fr-nn)
- Related PRD: <link, or "-">
- Related files and modules: <paths>

## To do

- [ ] <step>

## Acceptance criteria

<!-- Observable, testable outcomes, not process steps. "Reviewed the code" is a process step;
     "GET /health returns 200 with a JSON body" is an acceptance criterion. -->

- [ ] <criterion, tracking the FR acceptance criteria>

## Decisions and blockers

<!-- One bullet per decision (what was chosen and why) and per blocker (what is missing, who can
     unblock it, and when it was raised). A blocker with no named unblocker is not yet understood. -->

- <decision or blocker>

## Checkpoint

<!-- Rewritten, never appended: where this task stands right now. /task-resume reads these three
     lines instead of the whole session log. Write them with
     `python .claude/scripts/task.py checkpoint TASK-NNN --next "..." --green --question "..."`. -->

- Next step: -
- Last green commit: -
- Open questions: -

## Session log

<!-- One row per completed unit: a dispatch outcome, a gate run, a decision, a status change. One
     line each - what was done and the result, not the reasoning. A gate counts as passed only when
     a row here records the run. `task.py` writes the rows and keeps only the newest here; older rows
     move to docs/tasks/log/, still committed, no longer loaded on resume. -->

| Date | Who | What was done | Result |
|------|-----|---------------|--------|
| | | | |

## Result

<Filled when the task moves to Done: what was delivered, the {{PR_OR_MR}} or commit, and any
follow-up items with where they now live. Then move this file to docs/tasks/done/.>

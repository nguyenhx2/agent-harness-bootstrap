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
owner: <agent>
deps: <TASK-NNN, TASK-NNN, or "-">
priority: <P0 | P1 | P2>
phase: <phase number in docs/tasks/master-plan.md, or "-">
created: <YYYY-MM-DD>
tags: [task]
---

<!-- Task files are written 100% in English (see .claude/rules/task-tracking.md). -->

# TASK-NNN: <short title>

A status change is written in BOTH places at once: the `status:` field above, and this task's row
in `docs/tasks/master-plan.md`. They must never disagree. Read the board row back after writing it:
a board write can fail silently while the task file lands.

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

## Session log

<!-- Append a row after every meaningful unit of work. A quality gate counts as passed only when a
     row here records the run: an agent's "done" or "passed" is a claim, and the log is the
     evidence. -->

| Date | Who | What was done | Result |
|------|-----|---------------|--------|
| | | | |

## Result

<Filled when the task moves to Done: what was delivered, the {{PR_OR_MR}} or commit, and any
follow-up items with where they now live. Then move this file to docs/tasks/done/.>

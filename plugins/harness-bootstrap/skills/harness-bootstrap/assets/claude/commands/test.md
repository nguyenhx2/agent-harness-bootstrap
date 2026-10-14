---
description: Run lint and the test layers this change needs, and report each failure with its owning agent.
allowed-tools: Bash({{TEST_CMD}}:*), Bash({{LINT_CMD}}:*), Bash(python:*), Bash(python3:*), Read, Grep, Glob
---

1. `python .claude/scripts/verify-plan.py` says which layers this diff needs. If it says a green
   run is already logged at HEAD, cite that run and stop.
2. Run `{{LINT_CMD}}`, then `{{TEST_CMD}}` ({{UNIT_FRAMEWORK}} for the unit suite). Run the
   {{E2E_FRAMEWORK}} end-to-end suite only for the critical flows the plan names, or when the user
   asks.
3. Every external provider is mocked. A test that makes a real network call is a defect, not a
   passing test: report it as a failure even when it is green.
4. Report each failure with the agent that owns the code per the routing table, and with the
   acceptance criterion it breaks.
5. Log the run (`task.py log`); when the full suite is green, `task.py checkpoint TASK-NNN --green`
   records the commit, so the same commit is never run twice.

Never edit a test to make it pass. A failing test is either a real defect in the code or a wrong
expectation, and deciding which one is the point of the exercise.

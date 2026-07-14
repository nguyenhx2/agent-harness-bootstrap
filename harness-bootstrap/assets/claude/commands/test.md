---
description: Run lint plus the unit and end-to-end suites, and report each failure with its owning agent.
allowed-tools: Bash({{TEST_CMD}}:*), Bash({{LINT_CMD}}:*), Read, Grep, Glob
---

1. Run `{{LINT_CMD}}`.
2. Run `{{TEST_CMD}}`: {{UNIT_FRAMEWORK}} for the unit suite, {{E2E_FRAMEWORK}} for the end-to-end
   suite.
3. Every external provider is mocked. A test that makes a real network call is a defect, not a
   passing test: report it as a failure even when it is green.
4. Coverage target: {{COVERAGE_TARGET}}. Report the actual figure and whether it regressed against
   {{DEFAULT_BRANCH}}.
5. Report each failure with the agent that owns the code per the routing table, and with the
   acceptance criterion it breaks.
6. Append the run to the task file session log. A quality gate counts as passed only when the
   session log records the run: a claim of "tests pass" with no logged run is unverified.

Never edit a test to make it pass. A failing test is either a real defect in the code or a wrong
expectation, and deciding which one is the point of the exercise.

---
# {{TEST_GLOBS}} and {{SOURCE_GLOBS}} each expand to one quoted glob per line
paths:
  - "{{TEST_GLOBS}}"
  - "{{SOURCE_GLOBS}}"
---

# Testing

How tests are written. How tests are REVIEWED is in code-quality.md, which also owns the severity
model used to grade a testing gap.

## Test-driven, for anything with behavior

Red, green, refactor. Write the failing test first, from the acceptance criteria of the requirement
the task names, then make it pass, then clean up.

- Business logic, handlers, and data transforms are always test-first.
- Pure presentation, generated code, and configuration are not - do not perform TDD theater on a
  file with no behavior.
- A test asserts the acceptance criterion in the requirement, not the implementation that happens
  to satisfy it. If a refactor that keeps behavior identical breaks the test, the test was wrong.

## Layers

| Layer | Scope | Rule |
|-------|-------|------|
| Unit | One module, no I/O | Fast, deterministic, no network, no clock, no filesystem unless that IS the unit |
| Integration | Module plus its real adapters (a test database, a local queue) | Real datastore, mocked external providers. Reset state between tests; never share a database with a person |
| End to end | A critical user flow through the running system | Reserve for flows whose breakage is unacceptable. Few, stable, and owned - a flaky e2e suite gets ignored, which is worse than not having one |

## Mock every external provider

- **No test makes a real call to an external API.** Not to a paid one, not to a free one, not "just
  the read endpoint", not in CI, not locally. Every provider is behind a wrapper module, and tests
  mock the wrapper.
- Real calls make the suite flaky, slow, and offline-hostile; they can mutate real data; and they
  leak credentials into the test environment, which then need to exist there.
- The mock encodes the provider's CONTRACT, including its failure modes: timeout, rate limit,
  malformed response, partial response. A mock that only ever returns the happy path tests nothing
  the code will actually face.
- Test data is synthetic and deterministic. No production dump, no real personal data, no real
  credentials - not even expired ones (agent-guardrails.md).

## Coverage

- Target for business logic: **{{COVERAGE_TARGET}}**. It is a floor, not a goal.
- Coverage percentage on its own means little. Coverage of a path that moves money, grants access,
  or mutates data is what matters, and those paths are covered before the number is discussed.
- A gap in a critical path is a finding regardless of the overall number; a gap in a getter is not.

## Before opening a pull request

Run the suite. Record the result in the task file's session log - a gate counts as passed only when
the log records the run (task-tracking.md). A red suite is never merged and never skipped in CI.

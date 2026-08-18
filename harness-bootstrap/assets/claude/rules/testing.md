---
# {{TEST_GLOBS}} and {{SOURCE_GLOBS}} each expand to one quoted glob per line
paths:
  - {{TEST_GLOBS}}
  - {{SOURCE_GLOBS}}
---

# Testing

How tests are written. How tests are REVIEWED is in code-quality.md, which also owns the severity
model used to grade a testing gap.

## What a test is for, and where its expected value comes from

A test exists to prove an acceptance criterion from the requirement. That decides the one thing
that is easy to get wrong when an agent writes the code and the tests in the same session:

- **The criterion is the oracle.** The expected value comes from the requirement. A test that
  computes what it expects by calling the code under test proves nothing, because it passes for
  whatever behavior the code has, including the wrong one.
- **The implementation is not evidence.** "I ran it and this is what it returned" is how a bug
  becomes a fixture. If the expected value cannot be stated from the criterion alone, the criterion
  is incomplete: that is a finding for spec-guardian, not a number to obtain by execution.
- **Name the criterion in the test.** A reviewer can then check the pair, rather than trusting an
  assertion whose origin is invisible.

This holds whichever order the test and the implementation are written in. Writing the test first
does not prevent a tautology - the same actor still writes both sides, and a test written first can
still be adjusted afterwards until it passes. Order is not the control here; the oracle is.

{{#IF_TDD}}
## Test-driven, for anything with behavior

Red, green, refactor. Write the failing test first, from the acceptance criteria of the requirement
the task names, then make it pass, then clean up.

- Business logic, handlers, and data transforms are always test-first.
{{/IF_TDD}}
{{^IF_TDD}}
## Tests prove the criteria

Every acceptance criterion of the requirement the task names has a test that proves it, written in
the same change as the implementation - never promised for later. A criterion with no test is not
done.

- Business logic, handlers, and data transforms always ship with their tests.
{{/IF_TDD}}
- Pure presentation, generated code, and configuration are not - do not perform coverage theater on
  a file with no behavior.
- A test asserts the acceptance criterion in the requirement, not the implementation that happens
  to satisfy it. If a refactor that keeps behavior identical breaks the test, the test was wrong.

## Layers

| Layer | Scope | Rule |
|-------|-------|------|
{{#IF_UNIT}}| Unit | One module, no I/O | Fast, deterministic, no network, no clock, no filesystem unless that IS the unit |
| Integration | Module plus its real adapters (a test database, a local queue) | Real datastore, mocked external providers. Reset state between tests; never share a database with a person |
{{/IF_UNIT}}{{#IF_E2E}}| End to end | A critical user flow through the running system | Reserve for flows whose breakage is unacceptable. Few, stable, and owned - a flaky e2e suite gets ignored, which is worse than not having one |
{{/IF_E2E}}
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

{{#IF_UNIT}}## Coverage

- Target for business logic: **{{COVERAGE_TARGET}}**. It is a floor, not a goal.
- Coverage percentage on its own means little. Coverage of a path that moves money, grants access,
  or mutates data is what matters, and those paths are covered before the number is discussed.
- A gap in a critical path is a finding regardless of the overall number; a gap in a getter is not.

{{/IF_UNIT}}## Before opening a pull request

Run the suite. Record the result in the task file's session log - a gate counts as passed only when
the log records the run (task-tracking.md). A red suite is never merged and never skipped in CI.

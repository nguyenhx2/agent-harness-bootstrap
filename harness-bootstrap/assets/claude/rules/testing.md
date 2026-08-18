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
## What earns a test

A test is a liability that pays rent by failing. Every acceptance criterion is pinned by at least
one test, shipped in the same change and never promised for later. One test may pin several
criteria; a criterion already pinned does not get a second.

Before writing one, all three must hold:

1. The expected value is stated by the criterion. If it can only be obtained by running the code,
   that is a spec gap for spec-guardian, not a number to record.
2. The test can fail for a real reason. A getter, a constructor, a config echo, or a call that
   only breaks when the framework breaks is not written.
3. No existing test would have to change for this criterion to break. If one would, the criterion
   is covered - name that test instead of adding another.

After it passes, it is kept only while it would fail on a plausible future change to this module.
A test that survives only by being renamed with its symbol is deleted in the change that makes it
redundant, and the session log names the test that now covers the criterion. **Deleting a
redundant test is normal work, not a regression.**
{{/IF_TDD}}
- Business logic, handlers, and data transforms always ship with their tests.
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
- The mock encodes the provider's CONTRACT. Cover the failure modes this code actually handles
  differently: a retry path needs a timeout case, a paginating reader needs a partial response. A
  failure mode the code treats identically to another does not need its own test.
- Test data is synthetic and deterministic. No production dump, no real personal data, no real
  credentials - not even expired ones (agent-guardrails.md).

## When there are many scenarios, review fixtures instead of assertions

For a subsystem with many variations of one flow, prefer one reviewed runner over many written
tests: keep the scenarios as data files holding the input and the approved output in a format a
human can scan, and have a single test execute every file. The test logic is reviewed once; after
that a new case is a new fixture, and a behavior change shows up as a diff a human reads rather
than an assertion a human decodes. A fixture a human approved is never re-baselined to make a
suite green - a changed approved output goes back to the human.

## Before opening a pull request

Run the suite. Record the result in the task file's session log - a gate counts as passed only when
the log records the run (task-tracking.md). A red suite is never merged and never skipped in CI.

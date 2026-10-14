---
description: Plan and implement a functional requirement end-to-end against its acceptance criteria.
argument-hint: <FR-id> (e.g. FR-03)
---

Implement functional requirement **$1**.

This is the Guarded flow from `AGENTS.md`: it locks scope, registers a task, and ends at the branch
gate. That is right for an FR and wrong for a one-module fix - if the work turns out to be Direct,
say so and hand it to the owning agent instead of running the ceremony around it.

A change that leaves every criterion's outcome unchanged needs no FR work at all; new behaviour
inside an FR already agreed needs one appended criterion, not this flow. Use it for a new promise:
one a stakeholder reading the confirmation sheet would see as different.

If $1 is empty, list the FRs in `docs/specs/index.json` with `status` Confirmed, `decision` yes,
no `open_issues` and no `tasks`, and ask which one to implement. Do not guess.

1. Read FR $1's entry in `docs/specs/index.json` first, then only its block at the entry's `file`
   and `anchor` - not the whole section - plus the matching PRD in `docs/requirements/` if one
   exists. Without an index (no `.claude/scripts/spec-check.py` here), read the FR in
   `docs/specs/05-functional-requirements.md`.

   **Stop unless the entry says `status` Confirmed and `decision` yes** - a Draft FR, or one the
   confirmation sheet (`docs/specs/confirmation.md`) does not answer "yes", is a promise nobody
   agreed to. Name what is missing and ask; do not implement around it. An entry with
   `open_issues` stops here too.
2. Dispatch `spec-guardian` to lock the scope and the acceptance criteria before any code is
   written. An FR with no observable acceptance criteria is not ready to implement: stop and
   escalate.
3. Register the work with `/new-task` (it starts `Planned`), then
   `python .claude/scripts/task.py move TASK-NNN Active` when implementation begins.
4. Assign the specialist agent per the routing table:

{{ROUTING_TABLE}}

5. Design before code. Before the first line{{#IF_TDD}} or the first test{{/IF_TDD}} is written, state in the task file: the modules and
   types this change introduces or alters, the contract of each new interface, the edge cases the
   acceptance criteria imply, and the failure modes. One revisable pass, not a document.

   This step is why the order is what it is. A design that emerges from the sum of many locally
   minimal decisions is rarely revisited, and the result is a feature shaped by whatever was
   convenient at each step instead of by its domain.

{{#IF_TESTS}}
{{#IF_TDD}}
6. Implement test-first: {{#IF_UNIT}}{{UNIT_FRAMEWORK}} for the business rules{{/IF_UNIT}}{{#IF_E2E}}{{#IF_UNIT}}, {{/IF_UNIT}}{{E2E_FRAMEWORK}} for the
   user-visible flow{{/IF_E2E}}. The test names the acceptance criterion it proves and fails before the
   implementation exists.
{{/IF_TDD}}
{{^IF_TDD}}
6. Implement against the locked acceptance criteria, and ship the proving tests in the same change:
   {{#IF_UNIT}}{{UNIT_FRAMEWORK}} for the business rules{{/IF_UNIT}}{{#IF_E2E}}{{#IF_UNIT}}, {{/IF_UNIT}}{{E2E_FRAMEWORK}} for the user-visible flow{{/IF_E2E}}. Each
   test names the criterion it proves.
{{/IF_TDD}}
{{/IF_TESTS}}
{{^IF_TESTS}}
6. Implement against the locked acceptance criteria. This project runs no automated test suite:
   record in the session log how each criterion was verified by hand, and name the command or
   screen used to prove it.
{{/IF_TESTS}}
{{#IF_DDD}}
   Keep the change inside the FR's bounded context. A new domain term enters
   `docs/context/glossary.md` before it enters the code (`.claude/rules/ddd.md`).
{{/IF_DDD}}
{{#IF_LIGHT}}
   Lightweight mode: no methodology ceremony beyond the acceptance criteria. Small commits,
   working software first - but the review gate below is never skipped.
{{/IF_LIGHT}}
7. Comply with `.claude/rules/`. The change is a proposal: a human reviews and decides.
8. When the whole FR is implemented - not after each step - run `/review-changes TASK-NNN` once.
   It runs {{#IF_TESTS}}the test layers, {{/IF_TESTS}}the reviews and the secret scan this diff needs; do not run {{#IF_TESTS}}`/test` or {{/IF_TESTS}}a
   reviewer separately first.
9. Do not deploy. Close with the evidence map - one line per criterion ID from the index entry
   (`AC-nn.n`): the test name, the command and its output, or the screen that proves it. A
   criterion with no evidence is not met; say so rather than close. Tick the met ones, write the
   checkpoint (`task.py checkpoint`), and report the map.

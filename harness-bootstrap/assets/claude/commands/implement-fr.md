---
description: Plan and implement a functional requirement end-to-end against its acceptance criteria.
argument-hint: <FR-id> (e.g. FR-03)
---

Implement functional requirement **$1**.

If $1 is empty, list the functional requirements that have no task yet and ask which one to
implement. Do not guess.

1. Read FR $1 in `docs/specs/05-functional-requirements.md`: inputs, outputs, business rules,
   acceptance criteria, use case. Read the matching PRD in `docs/requirements/` if one exists.
2. Dispatch `spec-guardian` to lock the scope and the acceptance criteria before any code is
   written. An FR with no observable acceptance criteria is not ready to implement: stop and
   escalate.
3. Register the work with `/new-task` (it starts at `status: Planned`), then set it to `Active`
   when implementation begins.
4. Assign the specialist agent per the routing table:

{{ROUTING_TABLE}}

5. Implement test-first: {{UNIT_FRAMEWORK}} for the business rules, {{E2E_FRAMEWORK}} for the
   user-visible flow. The test names the acceptance criterion it proves and fails before the
   implementation exists.
6. Comply with `.claude/rules/`. The change is a proposal: a human reviews and decides.
7. Run `/test`, then `/review-changes`.
8. Do not deploy. Append the session-log rows to the task file and report which acceptance
   criteria are now met and which are not.

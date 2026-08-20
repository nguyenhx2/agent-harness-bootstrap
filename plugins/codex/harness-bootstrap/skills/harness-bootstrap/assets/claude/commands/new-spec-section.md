---
description: Scaffold a specification section following the project's standard BA structure.
argument-hint: <section-number-or-name>
---

Scaffold specification section **$1**.

If $1 is empty, list which of the standard sections are missing from `docs/specs/` and ask which
one to write.

1. Dispatch the `ba-analyst` agent, following the spec-builder skill conventions and the existing
   numbering in `docs/specs/`. Do not invent a parallel structure.
2. Derive the content from the PRDs, the codebase, and the user's answers. Never hand-invent a
   requirement: an unanswered question is recorded as an open question, not filled with a plausible
   guess. A fabricated requirement is worse than a missing one, because it looks settled.
3. Cross-link: every functional requirement carries an ID, acceptance criteria, and the use case it
   serves. Downstream files (PRDs, tasks, findings) reference that ID.
4. Log the change in `docs/specs/13-revision-history.md`.

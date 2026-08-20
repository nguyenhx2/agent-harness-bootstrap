---
description: Create an Architecture Decision Record from the template.
argument-hint: <decision-title>
---

Create an ADR for **$1**. If $1 is empty, ask for the decision title and stop.

1. Determine the next ADR-NNN from `docs/architecture/decisions/`.
2. Copy `docs/templates/ADR.md` to `docs/architecture/decisions/ADR-NNN-<slug>.md`.
3. Fill context, decision, options considered, and consequences, including the negative ones. An
   ADR with no downside recorded is an advertisement, not a decision record.
4. Leave `status: Proposed`. Only the user flips it to `Accepted`.
5. Add the row to the ADR index in `docs/architecture/decisions/README.md`.

ADRs are written 100% in English so the decision record stays portable.

Accepted ADRs are immutable and the immutability is hook-enforced. A change of mind means a NEW ADR
that supersedes the old one; the old one is marked `Superseded by ADR-MMM` and keeps its text. Land
every other edit to the file BEFORE the accept flip: the hook reads the on-disk status, so the flip
itself passes and every edit after it is blocked.

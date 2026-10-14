# Trigger cases - spec-builder

Re-run whenever the skill's description changes. Each case states what should load, what must stay
quiet, and how the result is judged. `harness-bootstrap/assets/scripts/skill-check.py` requires all
six sections and every field below; whether the answers are good is this file's reader's call.

## positive-discovery

The skill should trigger.

- Request: "Turn these meeting notes into a requirements spec for the approval workflow - the client
  needs to sign it off next week."
- Repo state: `notes/kickoff.md` and a transcript; no `docs/specs/`.
- Expected skills: spec-builder
- Not expected: harness-bootstrap, docs-to-knowledge
- Success criteria: one batched question round, `.sections.json` recorded before the scaffold, every
  FR carries `AC-nn.n` criteria with a negative case, `spec-check.py` exits 0, and
  `docs/specs/confirmation.md` is handed over with the open issues listed.

## negative-discovery

A request that sounds close but belongs elsewhere. The skill must not trigger.

- Request: "Digest these vendor PDFs into a knowledge base we can search."
- Repo state: a `sources/` folder of PDFs; no `docs/specs/`.
- Expected skills: docs-to-knowledge
- Not expected: spec-builder
- Success criteria: no `docs/specs/` is created and no FR is written; the request is about knowledge,
  not about what a system must do.

## edge-case

The skill should trigger and cope with a repository that ships no code.

- Request: "We need a contract for this research repo - which questions we answer and when each one
  counts as done."
- Repo state: markdown notes and a `sources/` folder; harness-bootstrap's `vars.json` carries
  `purpose_research`.
- Expected skills: spec-builder
- Not expected: harness-bootstrap
- Success criteria: the light contract is scaffolded (README, 05, 11, 13 - no `.sections.json`
  asked for), each research question is an `FR-nn` with `Done when` criteria, and `spec-check.py`
  exits 0.

## conflict-composition

Several skills look relevant; routing must be explicit.

- Request: "Write the specs for this app, then set up the agents to build it."
- Repo state: an idea in chat, an empty repository.
- Expected skills: spec-builder leads; harness-bootstrap composes, invoked through the Skill tool at
  step 7 (hand off) with `FR_LIST` taken from 05 verbatim.
- Not expected: a second spec structure written by harness-bootstrap.
- Success criteria: spec-builder writes `docs/specs/` and `index.json`; harness-bootstrap's dev
  agents name the same FR IDs; neither skill writes the other's files.

## execution-quality

The skill measurably improves the result.

- Request: "Standardise our requirements doc so the PO can approve it and the agents can work from
  it."
- Repo state: one long `PRD.md` with numbered features, no criteria, and two "TBD" cells.
- Expected skills: spec-builder
- Not expected: none
- Success criteria: every feature becomes an FR with a stable ID and Given/when/then criteria; each
  TBD becomes an `OI-nn` with an owner; the PO gets one confirmation page instead of the full set;
  `spec-check.py` exits 0 with the sheet and index in step.
- Baseline (without the skill): a reformatted PRD with invented targets in the TBD cells, criteria
  in free prose that no test can name, and no single page the PO can answer.

## efficiency

The skill loads only what it needs.

- Request: "The client answered the confirmation sheet - fold their replies in."
- Repo state: a complete spec set with `confirmation.md` replies filled in (two yes, one change).
- Expected skills: spec-builder, through `/spec-ingest` for the change
- Not expected: harness-bootstrap
- Success criteria: no re-elicitation and no re-scaffold; `reference/source-routing.md` and
  `reference/ba-standards.md` stay unread; the two yes FRs move to Confirmed with one revision row,
  the change is ingested, and `spec-check.py --write` keeps every reply.

---
title: "Contract - {{PROJECT_NAME}}"
sidebar_label: "Overview"
description: "What {{PROJECT_NAME}} must deliver, and how each deliverable is accepted."
tags: [specs, contract, {{PROJECT_SLUG}}]
---

# Contract - {{PROJECT_NAME}}

{{PROJECT_PURPOSE}}

This is the light form of the spec set, for a repository whose product is not code:

{{#IF_PURPOSE_RESEARCH}}- **Research** - answers to stated questions, with evidence.
{{/IF_PURPOSE_RESEARCH}}{{#IF_PURPOSE_STRATEGY}}- **Strategy** - decisions, with the options and the criteria behind them.
{{/IF_PURPOSE_STRATEGY}}{{#IF_PURPOSE_DOCS}}- **Documentation** - a documentation set, scoped by audience and source of truth.
{{/IF_PURPOSE_DOCS}}
It keeps what makes a contract checkable - stable IDs, acceptance criteria,
flagged assumptions and open issues, a revision history - and drops the sections that only code
needs. Nothing here is invented: anything not stated by a stakeholder lives in
[11-assumptions-constraints.md](11-assumptions-constraints.md) as an open issue with an ID.

## Contents

| # | Section | What it answers |
|---|---------|-----------------|
| 05 | [Contract items](05-functional-requirements.md) | What must be delivered (FR-nn), and when each item counts as done |
| 11 | [Assumptions and constraints](11-assumptions-constraints.md) | What we assumed, what binds us, what is still open |
| 13 | [Revision history](13-revision-history.md) | What changed, when, and by whom |
| - | [Confirmation sheet](confirmation.md) | One page for the person who confirms the contract - generated |
| - | `index.json` | What an agent reads first - generated |

The items keep the `FR-nn` ID and live in `05-functional-requirements.md` on purpose: every tool
downstream (the task board's `fr:` field, the traceability graph, `spec-check.py`) already knows
that shape, so a question, a decision or a document is traced exactly like a requirement.

## ID schemes

| Prefix | Lives in | Example |
|--------|----------|---------|
| `FR-nn` | 05 | `FR-01`, anchored `{#fr-01}` - one contract item |
| `AC-nn.n` | 05 | `AC-01.2` - an acceptance criterion of `FR-01` |
| `AS-xx` | 11 | `AS-01` (assumption) |
| `OI-xx` | 11 | `OI-01` (open issue), anchored `{#oi-01}` |
| `CO-xx` | 11 | `CO-01` (constraint) |

IDs are stable. An item that is dropped keeps its ID and is marked Withdrawn; it is never reused.

## Growing out of the light form

If the repository starts shipping code, the light form is not migrated - the full set is scaffolded
beside it (`purpose_code` in `vars.json`) and these items are carried into its 05 under the same
IDs.

<!-- Authoring: no generated-on date here; these files are prompt-cache prefix content. -->

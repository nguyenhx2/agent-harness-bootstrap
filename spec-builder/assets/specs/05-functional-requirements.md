---
title: "Functional requirements"
sidebar_label: "05. Functional requirements"
description: "What {{PROJECT_NAME}} must do - FRs, business rules, use cases, and user stories."
tags: [specs, requirements, {{PROJECT_SLUG}}]
---

# Functional requirements

<!-- The centre of the spec set. Everything else links here.

     Two rules govern this file:
     1. Every FR is observable. "The system is user-friendly" is not a requirement; "the system
        rejects a submission with no approver and shows which field is missing" is.
     2. Never invent one. If the source material does not state it and does not clearly imply it,
        it does not appear here - it goes to 11-assumptions-constraints.md as an open issue with an
        ID. A plausible invented requirement is the most expensive error available, because every
        downstream document treats it as settled. -->

<!-- IDs: `FR-01` in a single-product spec set. If this file sits under `docs/specs/modules/<module>/`,
     every ID in it carries that module's code instead - `FR-BLG-01`, and `#fr-blg-01` in its
     anchor - because the traceability graph is flat and two modules' bare `FR-01`s merge into one
     node. A module scaffold arrives with these samples already seeded with the code; keep the
     discipline for every ID you add. See reference/writing-rules.md. -->

## Summary

| ID | Requirement | Priority (MoSCoW) | Actor |{{#IF_FLOWS}} Flow |{{/IF_FLOWS}}{{#IF_FEASIBILITY}} Feasibility |{{/IF_FEASIBILITY}}
|----|-------------|-------------------|-------|{{#IF_FLOWS}}------|{{/IF_FLOWS}}{{#IF_FEASIBILITY}}-------------|{{/IF_FEASIBILITY}}
| [FR-01](#fr-01) | <one-line statement> | Must | <role> |{{#IF_FLOWS}} [BF-01](04-business-flows.md) |{{/IF_FLOWS}}{{#IF_FEASIBILITY}} [12](12-technical-feasibility.md) |{{/IF_FEASIBILITY}}
| [FR-02](#fr-02) | <one-line statement> | Should | <role> |{{#IF_FLOWS}} [BF-01](04-business-flows.md) |{{/IF_FLOWS}}{{#IF_FEASIBILITY}} [12](12-technical-feasibility.md) |{{/IF_FEASIBILITY}}

<!-- MoSCoW: Must (the release is pointless without it), Should (painful to omit, possible to
     defer), Could (nice, first to be cut), Won't (explicitly out for this release - keep the row,
     it prevents the conversation happening again). Priority comes from the stakeholder, not from
     how interesting the requirement is to build. -->

## FR-01 <requirement name> {#fr-01}

**Priority**: Must
**Actor**: <role{{#IF_STAKEHOLDERS}} from [02](02-stakeholders.md){{/IF_STAKEHOLDERS}}>
**Trigger**: <what causes this to happen>

### Description

<!-- What the system does, in the business's language. Two to five sentences. Resist restating the
     UI - the screen belongs in section 10. -->

### Input and output

| | Detail |
|---|---|
| Input | <data, its source, and its format> |
| Validation | <what makes an input invalid, and what the user sees when it is> |
| Output | <what the system produces, and where it goes> |
| Persistence | <what is stored{{#IF_DB}} - entities in [08](08-data-model.md){{/IF_DB}}> |

{{#IF_AI}}
### What the model does vs what the human does

<!-- The single most-contested table in an AI project, and the one most often skipped. Fill it even
     when it feels obvious - "obvious" is where the disagreement hides. Where the source material
     does not settle the boundary, that is an open issue, not a decision you may make. -->

| Step | Performed by | Notes |
|------|--------------|-------|
| <step> | Model | <what it produces; how confident it must be to proceed> |
| <step> | Human | <who; what they see; what they can override> |
| <step> | Deterministic code | <the parts that must never be probabilistic> |

- Human review required before: <the actions that must not auto-execute>
- Model failure mode: <what the user sees when the model is wrong, empty, or unavailable>
- Untrusted content: <does user-supplied text reach the prompt? If yes, it is data, never
  instructions - see [NFR-SEC](07-non-functional-requirements.md#nfr-security)>
{{/IF_AI}}

### Business rules

| ID | Rule | Source |
|----|------|--------|
| BR-01 | <the rule, stated so it can be tested> | <who stated it: person, policy, regulation> |

<!-- A business rule with no source is a guess. Trace every one. Rules that apply across several
     FRs still get a single home here (or in docs/context/business-rules.md if the workspace has
     one) and are referenced, not copy-pasted. -->

### Acceptance criteria

<!-- Observable, testable, and written so a QA engineer who has never met the stakeholder can tell
     pass from fail. Given/When/Then is a good default. Include at least one negative case - the
     path where it goes wrong is part of the requirement, not an afterthought. -->

- [ ] AC-01.1 Given <precondition>, when <action>, then <observable outcome>.
- [ ] AC-01.2 Given <invalid precondition>, when <action>, then <the error the user sees>.

### Dependencies

- Depends on: <other FRs{{#IF_INTEGRATION}}, integrations from [09](09-integration-interface.md){{/IF_INTEGRATION}}, or nothing>
- Blocked by: <open issues from [11](11-assumptions-constraints.md), or nothing>

---

## FR-02 <requirement name> {#fr-02}

<!-- Copy the FR-01 block. Do not thin it out for "smaller" requirements - the missing acceptance
     criterion is always on the requirement everyone thought was small. -->

**Priority**: Should
**Actor**: <role>
**Trigger**: <trigger>

### Description

### Input and output

| | Detail |
|---|---|
| Input | |
| Validation | |
| Output | |
| Persistence | |

### Business rules

| ID | Rule | Source |
|----|------|--------|
| BR-02 | | |

### Acceptance criteria

- [ ] AC-02.1 Given <precondition>, when <action>, then <observable outcome>.

### Dependencies

---

## Use cases

<!-- The FR says what the system does; the use case says how an actor gets through it, including
     where it goes wrong. One use case may serve several FRs and vice versa - map both directions
     in the table below. -->

| ID | Use case | Actor | Precondition | Main success scenario | Serves |
|----|----------|-------|--------------|-----------------------|--------|
| UC-01 | <name> | <role> | <what must be true first> | <the happy path in one sentence> | [FR-01](#fr-01) |

### UC-01 <name>

**Actor**: <role>
**Precondition**: <state before>
**Postcondition**: <state after>

| # | Step |
|---|------|
| 1 | <actor does X> |
| 2 | <system responds Y> |

**Alternate flows**

| # | Condition | Behaviour |
|---|-----------|-----------|
| 1a | <the branch> | <what happens instead> |

**Exceptions**

| # | Condition | Behaviour |
|---|-----------|-----------|
| 1e | <failure> | <what the actor sees, and what state the data is left in> |

## User stories

<!-- The story is for planning, not for specification - it never carries a requirement that is not
     already an FR. If a story cannot point at an FR, either the FR is missing or the story is
     scope creep. Find out which; do not quietly add the FR. -->

| ID | Story | Priority | Serves | Estimate |
|----|-------|----------|--------|----------|
| US-01 | As a <role>, I want <capability>, so that <benefit>. | Must | [FR-01](#fr-01) | <points, or "not estimated"> |

## Traceability matrix

<!-- The check that makes this spec set worth writing. Every FR appears in every column, or the
     gap is deliberate and named. A blank cell is a question, not a formatting problem. -->

| FR |{{#IF_FLOWS}} Flow (04) |{{/IF_FLOWS}} Use case | User story |{{#IF_UI}} Screen (10) |{{/IF_UI}}{{#IF_DB}} Entities (08) |{{/IF_DB}}{{#IF_FEASIBILITY}} Feasibility (12) |{{/IF_FEASIBILITY}}
|----|{{#IF_FLOWS}}-----------|{{/IF_FLOWS}}----------|------------|{{#IF_UI}}-------------|{{/IF_UI}}{{#IF_DB}}---------------|{{/IF_DB}}{{#IF_FEASIBILITY}}------------------|{{/IF_FEASIBILITY}}
| [FR-01](#fr-01) |{{#IF_FLOWS}} BF-01 |{{/IF_FLOWS}} UC-01 | US-01 |{{#IF_UI}} [SCR-01](10-ui-ux-wireframes.md) |{{/IF_UI}}{{#IF_DB}} <entity> |{{/IF_DB}}{{#IF_FEASIBILITY}} [12](12-technical-feasibility.md) |{{/IF_FEASIBILITY}}

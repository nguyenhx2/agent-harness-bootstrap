---
title: "Technical feasibility"
sidebar_label: "12. Technical feasibility"
description: "Per-requirement feasibility, risks, and proof-of-concept recommendations for {{PROJECT_NAME}}."
tags: [specs, feasibility, risk, {{PROJECT_SLUG}}]
---

# Technical feasibility

<!-- The section that turns a wish list into a plan. Every FR in
     [05](05-functional-requirements.md) appears in the table below - no exceptions, and no FR is
     omitted because it is "obviously fine". The obvious ones are cheap to mark Yes; the omission
     is what hides the one that was not obvious.

     "Partial" and "No" are not failures of the BA. They are the most valuable output of this
     document, because they are cheap here and expensive in month four. -->

## Feasibility by requirement

| FR | Requirement | Feasible | Reason / dependency | Confidence | Mitigation |
|----|-------------|----------|---------------------|------------|------------|
| [FR-01](05-functional-requirements.md#fr-01) | <one line> | Yes | <the known-good path> | High | - |
| [FR-02](05-functional-requirements.md#fr-02) | <one line> | Partial | <what works, and what does not - name the specific blocker> | Medium | <the PoC, the fallback, or the scope cut> |
| [FR-03](05-functional-requirements.md#fr-03) | <one line> | No | <the hard blocker: a missing API, an unavailable dataset, a licence, a law> | High | <what would have to change; link the open issue> |

<!-- Feasible = can this be built to its acceptance criteria, within the constraints in
     [11](11-assumptions-constraints.md).
       Yes     - a known path exists; the team has done this or equivalent.
       Partial - it can be built, but not as specified, or not to the stated NFR target, or not
                 without something we do not yet have. Say which.
       No      - it cannot be built as specified. This is a scope conversation, and it happens now.
     Confidence is about the ASSESSMENT, not the requirement: Low confidence on a "Yes" means
     nobody has actually checked, and that is a risk in its own right. -->

## Technical approach

<!-- The shape of the solution, at the level that affects feasibility - not an architecture. If the
     stack is not decided, say so; do not default to what the last project used. That default,
     unwritten, is how a stack decision gets made by nobody. -->

| Layer | Approach | Decided | Notes |
|-------|----------|---------|-------|
| <frontend / backend / data / hosting / integration> | <the candidate> | Yes / No - [OI-nn](11-assumptions-constraints.md) | <what the choice buys, and what it costs> |

{{#IF_AI}}
## Model feasibility

<!-- The questions that decide whether the AI part of this works, asked before anyone builds it.
     Every row that cannot be answered from evidence is a PoC, not an assumption. -->

| Question | Answer | Evidence |
|----------|--------|----------|
| Does the required capability exist at acceptable quality today? | <yes / partial / unknown> | <a test on real data, or "not yet tested"> |
| What accuracy does the business need to accept the output? | <the threshold, from the stakeholder> | [FR-01](05-functional-requirements.md#fr-01) |
| How is quality measured, and against what ground truth? | <the eval set, and who builds it> | <who owns it> |
| Cost per operation at expected volume | <estimate, and the volume it assumes> | <per [NFR-SCA-01](07-non-functional-requirements.md#nfr-scalability)> |
| Latency at expected volume | <estimate> | <per [NFR-PERF-01](07-non-functional-requirements.md#nfr-performance)> |
| Provider data-retention terms compatible with our classification | <yes / no / unread> | [NFR-SEC-14](07-non-functional-requirements.md#nfr-security) |
| Behaviour when the model is wrong | <the fallback> | [FR-01](05-functional-requirements.md#fr-01) |

<!-- "The model can probably do this" is not evidence. A twenty-example test on real data, run this
     week, is - and it costs less than the meeting in which the question is debated. -->
{{/IF_AI}}

## Risks

| ID | Risk | Likelihood | Impact | Affects | Mitigation | Owner |
|----|------|------------|--------|---------|------------|-------|
| R-01 | <what could go wrong, stated as an event, not a worry> | High / Medium / Low | High / Medium / Low | [FR-01](05-functional-requirements.md#fr-01) | <the concrete action, with a date> | <role> |

<!-- A risk with no mitigation and no owner is a complaint. Either someone owns it or it is
     accepted - and an accepted risk is written down as accepted, by the person who accepted it. -->

## Proof-of-concept recommendations

<!-- Order them by how much uncertainty they remove per day spent. A PoC that would take three
     weeks to confirm something we could accept as a risk is not a PoC, it is a delay. -->

| # | PoC | Question it answers | Effort | Blocks |
|---|-----|---------------------|--------|--------|
| 1 | <the smallest thing that answers the question> | <the specific uncertainty, from the table above> | <days> | [FR-02](05-functional-requirements.md#fr-02) |

**Exit criteria**: <what result means "go", and what result means "change the requirement". Decide
this before the PoC runs, or the result will be interpreted by whoever wanted it most.>

## Effort indication

<!-- Only if asked for, and only as a range with its assumptions attached. A single number, once
     written, is a commitment - and it will be quoted back without the assumptions. -->

| Requirement group | Indicative effort | Assumes |
|-------------------|-------------------|---------|
| <group of FRs> | <range> | <team size, stack, availability of [INT-01](09-integration-interface.md)> |

## Coverage check

- [ ] Every FR in [05](05-functional-requirements.md) has a row above. Count them.
- [ ] Every "Partial" and every "No" names a specific blocker, not a general concern.
- [ ] Every "No" has a corresponding open issue in [11](11-assumptions-constraints.md).

---
title: "Assumptions and constraints"
sidebar_label: "11. Assumptions and constraints"
description: "What was assumed, what binds the design, and what is still open for {{PROJECT_NAME}}."
tags: [specs, assumptions, constraints, open-issues, {{PROJECT_SLUG}}]
---

# Assumptions and constraints

<!-- This file is the pressure-release valve for the whole spec set, and it only works if it is
     used. The rule the other twelve sections depend on:

       NEVER INVENT A REQUIREMENT.

     Anything the source material did not state and does not clearly imply comes here - as an
     assumption if you are proceeding on it, or as an open issue if you are not. It never gets
     written into 05 or 07 as though someone had decided it.

     The reason is economic. A missing requirement is visible: it stalls, someone asks, it gets
     answered. A plausible invented requirement is invisible: it gets estimated, built, tested
     against itself, and discovered in UAT by the one person who knew it was wrong. Every document
     downstream treats it as settled. It is the single most expensive error available to a BA. -->

## Assumptions

<!-- An assumption is something you are proceeding on WITHOUT confirmation, that would change the
     design if it were false. If it would not change anything, it is not worth recording; if it
     would, the impact column is the reason someone will read this table. -->

| ID | Assumption | Why we are assuming it | Impact if false | Owner | Confirmed |
|----|-----------|------------------------|-----------------|-------|-----------|
| AS-01 | <what we are taking as true> | <it was implied by X, or it is standard practice, and nobody has confirmed it> | <what breaks, and roughly what it costs> | <role who can confirm> | No |

<!-- "Confirmed" flips to Yes only when a named person said yes. It does not flip because the
     assumption seems increasingly likely, and it does not flip because the sprint started. -->

## Constraints

<!-- A constraint is imposed from outside and is not negotiable by the team. Distinguish it from a
     decision the team made - a decision belongs in an ADR, where it can be revisited. Filing a
     team decision here disguises it as immovable. -->

| ID | Constraint | Type | Source | Consequence for the design |
|----|-----------|------|--------|----------------------------|
| CO-01 | <the constraint> | Technical / Business / Legal / Time / Budget / Organisational | <policy, contract, regulation, or the person who set it> | <what it rules out> |

## Open issues

<!-- Questions that must be answered before the affected requirement can be built. Each has an
     owner (a person, not a team) and a needed-by date, or it will not be answered.

     An open issue with no owner is a wish. An open issue with no date is a wish with a deadline of
     "never". -->

| ID | Question | Blocks | Owner | Needed by | Status |
|----|----------|--------|-------|-----------|--------|
| OI-01 {#oi-01} | <the question, stated so it can be answered yes or no, or with a number> | [FR-01](05-functional-requirements.md#fr-01) | <named role> | <milestone or date> | Open |
| OI-02 {#oi-02} | <question> | [NFR-SEC-14](07-non-functional-requirements.md#nfr-security) | <named role> | <milestone> | Open |

### Resolved issues

<!-- Keep them. The resolution is the record of who decided what, and it is what stops the same
     question being reopened by the next person to join. -->

| ID | Question | Resolution | Decided by |
|----|----------|-----------|------------|
| OI-00 | <question> | <what was decided> | <who> |

## Dependencies

<!-- Things outside the team's control that the schedule depends on: another team's API, a licence
     purchase, a security review slot, a data migration from a system nobody maintains. -->

| ID | Dependency | Depends on (team or system) | Needed by | Risk if late |
|----|-----------|-----------------------------|-----------|--------------|
| DP-01 | <what we need> | <who provides it> | <milestone> | <what stalls> |

## What is explicitly NOT specified

<!-- Say the quiet part out loud. This list is read with relief by the engineer who was about to
     build something nobody asked for, and with alarm by the stakeholder who assumed it was
     included - and it is far better to cause that alarm now. -->

- <area the input did not cover at all, and which therefore has no requirements in this set>

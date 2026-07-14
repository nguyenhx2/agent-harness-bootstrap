---
title: "Stakeholders"
sidebar_label: "02. Stakeholders"
description: "Roles, interests, influence, and decision rights for {{PROJECT_NAME}}."
tags: [specs, stakeholders, {{PROJECT_SLUG}}]
---

# Stakeholders

<!-- Who cares about this system, what each of them wants from it, and - the part that saves the
     project - who is allowed to settle a disagreement. A spec with no named decider produces a
     requirement set that changes every time a new person reads it. -->

## Stakeholder map

| ID | Role | Represents | Interest in the system | Influence | Decision rights |
|----|------|-----------|------------------------|-----------|-----------------|
| SH-01 | {{DOC_OWNER}} | <team or function> | <what they need from it> | High / Medium / Low | <what they can decide alone> |
| SH-02 | <role> | <team or function> | <what they need from it> | High / Medium / Low | <what they can decide alone> |

<!-- Influence = how much their objection can change the plan, not seniority. The ops lead who can
     refuse to run the thing has high influence regardless of title. -->

## User groups

<!-- The people who will actually touch the system, distinguished from the people who sponsor it.
     Each group here should map to a role in 06-access-control.md - if a group has no role, either
     the role is missing or the group is not a user. -->

| Group | Size (approx.) | Technical comfort | Primary tasks | Role in [06](06-access-control.md) |
|-------|----------------|-------------------|---------------|-------------------------------------|
| <group> | <n, or "unknown - OI-nn"> | Low / Medium / High | <what they come to the system to do> | <role name> |

## Organisational context

<!-- Who proposed the project, which department owns the budget, which department owns the process
     being changed, and whether those are the same department (they usually are not - and that gap
     is a risk, so name it). -->

- Proposing department: <department>
- Budget owner: <role>
- Process owner: <role>
- Delivery team: <team>

## Escalation path

<!-- Where a blocked requirement goes. Fill this before the first disagreement, not after. -->

| Situation | Goes to |
|-----------|---------|
| Requirement conflict between user groups | <role> |
| Scope change with cost impact | <role> |
| Security or compliance objection | <role> |

## Communication and sign-off

| Artefact | Reviewed by | Approved by | Cadence |
|----------|-------------|-------------|---------|
| This specification set | <roles> | {{DOC_OWNER}} | <one-off / per release> |

## Open points

<!-- Any stakeholder you were told about but could not identify, and any group whose needs you are
     guessing at. Register each in 11-assumptions-constraints.md and link it - an unidentified
     decider is an open issue, not a blank row. -->

- <e.g. "No named owner for the approval step - see [OI-01](11-assumptions-constraints.md#oi-01)">

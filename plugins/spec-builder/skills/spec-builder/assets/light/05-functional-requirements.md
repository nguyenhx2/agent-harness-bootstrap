---
title: "Contract items"
sidebar_label: "05. Contract items"
description: "What {{PROJECT_NAME}} must deliver, and when each item counts as done."
tags: [specs, contract, {{PROJECT_SLUG}}]
---

# Contract items

<!-- The light contract. One block per thing this repository must deliver: a research question to
     answer, a decision to make, a document to write. The rules of the full spec set still hold:

     1. Never invent an item. A question nobody asked, a decision nobody owns, a page nobody needs
        goes to 11-assumptions-constraints.md as an open issue - not here.
     2. Every item is checkable. "Understand the market" cannot be accepted; "the synthesis names
        the three largest competitors by revenue, each with a primary source" can.

     The ID stays `FR-nn` and the file keeps this name so every tool downstream (the task board's
     `fr:` field, the traceability graph, spec-check.py) reads it unchanged. The heading says what
     the item is in the user's words. -->

## Summary

| ID | {{#IF_PURPOSE_RESEARCH}}Question{{/IF_PURPOSE_RESEARCH}}{{^IF_PURPOSE_RESEARCH}}{{#IF_PURPOSE_STRATEGY}}Decision{{/IF_PURPOSE_STRATEGY}}{{^IF_PURPOSE_STRATEGY}}Deliverable{{/IF_PURPOSE_STRATEGY}}{{/IF_PURPOSE_RESEARCH}} | Priority (MoSCoW) | Owner |
|----|----------|-------------------|-------|
{{#IF_PURPOSE_RESEARCH}}| [FR-01](#fr-01) | <the question in one plain sentence> | Must | <role> |
{{/IF_PURPOSE_RESEARCH}}{{#IF_PURPOSE_STRATEGY}}| [FR-02](#fr-02) | <the decision in one plain sentence> | Must | <role> |
{{/IF_PURPOSE_STRATEGY}}{{#IF_PURPOSE_DOCS}}| [FR-03](#fr-03) | <the deliverable in one plain sentence> | Must | <role> |
{{/IF_PURPOSE_DOCS}}
<!-- MoSCoW comes from the stakeholder, as in the full set. Won't rows stay: they stop the same
     request coming back. -->

{{#IF_PURPOSE_RESEARCH}}
## FR-01 <research question, as a question> {#fr-01}

**Priority**: Must
**Status**: Draft
**Owner**: <who needs the answer>

### What the answer is for

<!-- The decision or reader the answer serves. A question with no use for its answer is a reading
     list, and it has no point at which it is done. -->

### Scope

| | Detail |
|---|---|
| In scope | <period, region, population, sources that count> |
| Out of scope | <what a reader might expect and will not get> |
| Evidence standard | <primary sources only? how recent? how many independent sources per claim?> |

### Acceptance criteria

<!-- "Done when <observable check>." for a deliverable; Given/when/then when the answer must hold
     under a condition. One line each, AC-<FR number>.<n>. Include the negative case: what the
     synthesis must say when the evidence is missing or contradicts itself. -->

- [ ] AC-01.1 Done when the synthesis answers the question in one paragraph and every claim in it cites a source.
- [ ] AC-01.2 Given no primary source answers part of the question, when the synthesis is written, then that part is stated as unanswered with what would settle it.
{{/IF_PURPOSE_RESEARCH}}
{{#IF_PURPOSE_STRATEGY}}
## FR-02 <decision to make, as a choice> {#fr-02}

**Priority**: Must
**Status**: Draft
**Owner**: <who decides - one person>

### Decision brief

| | Detail |
|---|---|
| Decision needed by | <date or milestone> |
| Options in scope | <the options the decision-maker will consider; "to be found" is an open issue> |
| Criteria | <what the options are judged on, in priority order - stated by the decision-maker> |
| Out of scope | <options excluded up front, and who excluded them> |

### Acceptance criteria

<!-- The memo is accepted when it lets the owner decide - not when it agrees with anyone. -->

- [ ] AC-02.1 Done when the memo compares every option in scope against every criterion and states a recommendation with its reason.
- [ ] AC-02.2 Given an assumption the recommendation rests on, when the memo is reviewed, then that assumption is named with its impact if false.
{{/IF_PURPOSE_STRATEGY}}
{{#IF_PURPOSE_DOCS}}
## FR-03 <document or page set to deliver> {#fr-03}

**Priority**: Must
**Status**: Draft
**Owner**: <who accepts it>

### Docs scope

| | Detail |
|---|---|
| Audience | <who reads it, and what they already know> |
| Task it supports | <what the reader does with it> |
| Source of truth | <the code, system, or person each statement is checked against> |
| Out of scope | <topics deliberately left to another document> |

### Acceptance criteria

- [ ] AC-03.1 Done when a reader from the audience can complete the task using only this document.
- [ ] AC-03.2 Given a statement the source of truth does not confirm, when the document is checked, then the statement is removed or marked as unverified.
{{/IF_PURPOSE_DOCS}}

<!-- Copy a block per item. The samples are numbered by purpose (research 01, strategy 02, docs
     03) so a mixed repo gets one of each; before the first confirmation, renumber them to run from
     FR-01 without gaps. After that, IDs are stable: append, never renumber. -->

## Handling

<!-- Kept from the full set's mandatory security NFRs, at the size a non-code repo needs. Never
     blank: an unknown is `<unknown - OI-nn>` with the issue raised in 11. -->

| Question | Answer |
|----------|--------|
| Classification of the material in this repo | <public / internal / confidential / personal data> |
| Where material may be sent (search engines, model providers, clients) | <the rule> |
| Retention and deletion | <how long sources and drafts are kept> |

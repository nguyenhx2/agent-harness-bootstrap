---
title: "Revision history"
sidebar_label: "13. Revision history"
description: "Version history of the {{PROJECT_NAME}} specification set."
tags: [specs, history, {{PROJECT_SLUG}}]
---

# Revision history

<!-- One row per version of the SPEC SET, not per file edit - git already has the file edits. A row
     is added when the contract changes: a requirement added, removed, re-scoped, or re-prioritised,
     or an NFR target moved. Typo fixes do not get a row.

     Fill the date when you write the row, in YYYY-MM-DD. Do not backfill dates you do not know. -->

## Versions

| Version | Date | Author | Change summary | Approved by |
|---------|------|--------|----------------|-------------|
| 1.0 | <YYYY-MM-DD> | {{DOC_OWNER}} | Initial specification set. | <role> |

<!-- Versioning:
       1.0        - the first complete set, whatever state the open issues are in.
       1.x        - clarifications, added detail, resolved open issues. The contract does not move.
       2.0        - the contract moved: a requirement was added, dropped, or materially changed.
                    A major bump is a signal to everyone who estimated against the old set. -->

## Changes by section

<!-- Only for versions after 1.0. The point of this table is that a reader who last saw 1.2 can
     find, in one screen, what they now need to re-read. -->

| Version | Section | Change | Reason |
|---------|---------|--------|--------|
| <1.1> | [05](05-functional-requirements.md) | <what changed, naming the IDs> | <who asked, and why> |

## Requirement lifecycle

<!-- IDs are never reused. A withdrawn FR keeps its number and is recorded here - somewhere there is
     a task, a commit, or a test that still names it, and a recycled ID makes that reference lie. -->

| ID | Status | Version | Note |
|----|--------|---------|------|
| <FR-nn> | Withdrawn / Superseded | <version> | <why; and by what, if superseded> |

## Approval

| Version | Reviewed by | Approved by | Date |
|---------|-------------|-------------|------|
| 1.0 | <roles from [02](02-stakeholders.md)> | {{DOC_OWNER}} | <YYYY-MM-DD> |

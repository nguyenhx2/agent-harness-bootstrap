# Writing rules

The conventions every file under `docs/specs/` follows. They exist so that thirteen documents read
as one document, and so that a link written in month one still resolves in month nine.

## Output language

**Prose matches the user's language.** If the user works in Vietnamese, the descriptions, the
rationale, and the table cells are Vietnamese.

**Codes are always English.** Without exception:

- file names (`05-functional-requirements.md`, never a localised name)
- IDs and anchors (`FR-01`, `{#fr-01}`, `NFR-SEC-02`, `OI-03`)
- entity and field names (`Order.created_at`)
- enum and status values (`DRAFT`, `SUBMITTED`) - the *display label* may be localised, the *value*
  may not
- role names in the permission matrix (`role_approver`)
- section headings' anchor slugs

These end up in code, in a database, in a URL, and in a commit message. A mixed-language identifier
is a permanent tax on every developer who touches it, and it is paid forever.

Where a term has a business name in the user's language and a schema name in English, record both
in `03-glossary.md` - the business term as the term, the schema name as an alias.

## Frontmatter

Every file, no exceptions:

```yaml
---
title: "Functional requirements"
sidebar_label: "05. Functional requirements"
description: "What the system must do - FRs, business rules, use cases, and user stories."
tags: [specs, requirements, <project-slug>]
---
```

## IDs and anchors

| Prefix | Meaning | Anchor form |
|--------|---------|-------------|
| `FR-nn` | Functional requirement | `## FR-01 <name> {#fr-01}` |
| `NFR-XXX-nn` | Non-functional requirement, XXX = PERF/SEC/REL/USE/SCA/MNT | category anchor: `{#nfr-security}` |
| `UC-xx` | Use case | - |
| `US-xx` | User story | - |
| `BR-xx` | Business rule | - |
| `AS-xx` | Assumption | - |
| `OI-xx` | Open issue | `{#oi-01}` |
| `CO-xx` | Constraint | - |
| `DP-xx` | Dependency | - |
| `R-xx` | Risk | - |
| `BF-xx` | Business flow | - |
| `SCR-xx` | Screen | - |
| `INT-xx` | Integration | - |
| `SH-xx` | Stakeholder | - |

**IDs are stable and are never reused.** A withdrawn requirement keeps its number, is marked
withdrawn, and is recorded in `13-revision-history.md`. Somewhere there is a task, a commit, or a
test that still names it; a recycled ID makes that reference lie.

## Cross-references

Relative path plus anchor, always:

```markdown
[FR-01](05-functional-requirements.md#fr-01)
[the security NFRs](07-non-functional-requirements.md#nfr-security)
```

Relative, so the links survive being moved, mirrored, or published. Anchored, so the reader lands
on the requirement and not at the top of a 400-line file.

Never restate content that lives in another section. Link to it. Two copies of a business rule
means one of them is wrong within a month, and nobody knows which.

## Diagrams

- **Mermaid only.** Never an image; an image is a diagram nobody can edit and nobody updates.
- **Node labels in double quotes**: `A["Submit for approval"]`. Unquoted labels break on
  parentheses, slashes, and every non-ASCII character - which is most labels in a non-English spec.
- **`LR` for process flows** (they read as a timeline), **`TD` for hierarchies** (role trees,
  navigation, decomposition).
- `erDiagram` for the data model, `stateDiagram-v2` for lifecycles, `sequenceDiagram` only when the
  question is genuinely "who calls whom, in what order".
- Every decision node has a labelled edge for every branch, including the failure branch.
- One diagram per question. A diagram that answers two questions answers neither.

## Prose

- No emoji. Anywhere.
- Lists use `-`. Not `*`, not `+`.
- Sentence case headings ("Functional requirements", not "Functional Requirements").
- No em dash; write `-`.
- Tables keep their column headers exactly as the template ships them - downstream tooling and every
  other section's cross-references assume them.
- Short sentences. A requirement that needs a semicolon usually needs to be two requirements.

## Requirements are observable

Every FR and every acceptance criterion must be checkable by someone who has never met the
stakeholder.

- Not: "The system is user-friendly." That cannot fail a test.
- Yes: "A submission with no assigned approver is rejected, and the field is highlighted with the
  message defined in NFR-USE-04."

Every NFR carries a number and the way it is measured. "Fast" and "secure" are adjectives, and an
adjective cannot fail a test either.

## Cells are never blank

An empty table cell reads as "no constraint" to whoever implements it - which is how a permission
matrix with a blank cell becomes a data leak. If the value is unknown, write the open-issue ID:
`<unknown - [OI-03](11-assumptions-constraints.md#oi-03)>`. "TBD" with no ID is a blank cell with
extra steps.

## Byte stability

No generation dates, no timestamps, no run IDs anywhere in the templates or in the scaffolded
output. These files become prompt-cache prefix content for every downstream agent that reads the
specs; one volatile byte cold-misses the cache on every future run.

Dates that a *human* fills in (the revision-history rows, an open issue's needed-by) are fine -
they change when the content changes, which is exactly when the cache should miss.

## HTML comments

Authoring guidance lives in `<!-- -->` comments. Claude Code strips them from context, so they cost
nothing to read and they keep the prose clean for the human reader. Use them freely for "what
belongs here"; do not use them to hold content.

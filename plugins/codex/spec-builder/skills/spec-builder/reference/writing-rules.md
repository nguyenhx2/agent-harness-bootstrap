# Writing rules

The conventions every file under `docs/specs/` follows. They exist so that the selected sections
read as one document, and so that a link written in month one still resolves in month nine.

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
| `DS-xx` | Design-system component (14) | - |
| `DT-xx` | Design token (14) | - |

This table is the single authoring home of the ID scheme. The shipped `assets/specs/README.md`
carries the project-facing copy for downstream readers; when a prefix is added here, add it there
and in harness-bootstrap's `docs-graph.py` ID regex in the same change - the graph cannot trace an
ID it does not scan for.

**IDs are stable and are never reused.** A withdrawn requirement keeps its number, is marked
withdrawn, and is recorded in `13-revision-history.md`. Somewhere there is a task, a commit, or a
test that still names it; a recycled ID makes that reference lie.

### Module segment

A repo that specs more than one product module inserts the module's code into every ID it owns:
`FR-BLG-01`, `UC-PAY-03`, `NFR-BLG-SEC-01`. The segment is optional and every prefix in the table
accepts one - the flat form (`FR-01`) stays valid forever and is the default for a single-product
repo. There is no migration: a flat spec set that never grows a second module never changes.

- **Module codes** are 2-4 uppercase `[A-Z0-9]`, first character a letter, declared once in the
  root `README.md` index table alongside the folder each one owns (`BLG` -> `modules/billing/`).
- **NFR takes the module first, then the category**: `NFR-BLG-SEC-01`, never `NFR-SEC-BLG-01`.
  One module segment and one category segment, in that order, and no more.
- **Inside `docs/specs/modules/<module>/`, a bare ID is forbidden.** Every ID defined there carries
  that module's segment. The reason is mechanical, not stylistic: the docs graph is flat and keys
  every ID by its text alone, so two modules that each define a bare `FR-01` collapse into ONE
  graph node - one file wins `defined_in`, the other module's requirement is downgraded to a
  mention of it, and nothing reports the collision. The segment is what keeps them two.
- Cross-module references use the full ID and a relative path, exactly as within a module:
  `[FR-BLG-01](../billing/05-functional-requirements.md#fr-blg-01)`.

## Module folders

When the module form is in use, each module owns a folder and the sections that describe only it:

```
docs/specs/
  README.md                       # the index, and the module code -> folder table
  01-overview.md                  # cross-cutting, shared
  03-glossary.md
  11-assumptions-constraints.md
  13-revision-history.md
  modules/
    billing/                      # BLG
      05-functional-requirements.md
      07-non-functional-requirements.md
      08-data-model.md
    catalog/                      # CAT
      05-functional-requirements.md
      ...
```

- **Module-owned**: 05, 07, 08, 09, 10 - one copy per module, under `modules/<folder>/`. A module
  scaffold arrives pre-seeded: the sample IDs already carry the module's code and the links to
  root sections already point two levels up, so an unfilled module never reproduces the bare-ID
  merge.
- **Cross-cutting, one copy at the root**: the README index, 01, 03, 11, 13. A glossary per module
  is how two modules end up with two meanings for one word.
- **12-feasibility follows the risk**: at the root when the buildability question is the platform's
  (one table covering every module's FRs), inside a module when the risk is that module's alone.
- The folder name is the module's lowercase name (`billing`); the ID segment is its code (`BLG`).
  The mapping between the two is declared once, in the root `README.md` index table.
- Sections split by size (the rule below) split *within* their module folder.

`scripts/scaffold.py --module BLG:billing --module CAT:catalog` writes exactly this layout. The
section selection in `.sections.json` stays per SECTION, not per module: a selected section is
scaffolded for every named module.

## Cross-references

Relative path, plus an anchor whenever the target ID has one (see the anchor-form column above); a
plain file link when it does not, or when the reference is to a section as a whole:

```markdown
[FR-01](05-functional-requirements.md#fr-01)
[the security NFRs](07-non-functional-requirements.md#nfr-security)
[BF-01](04-business-flows.md)
```

Relative, so the links survive being moved, mirrored, or published. Anchored, wherever an anchor
exists, so the reader lands on the requirement and not at the top of a 400-line file.

Never restate content that lives in another section. Link to it. Two copies of a business rule
means one of them is wrong within a month, and nobody knows which.

## When a section outgrows its file

Any numbered section may become a folder once the single file would exceed ~400 lines or ~25 KB:

```
docs/specs/05-functional-requirements/
  README.md            # the summary table, UC-xx, US-xx, and the traceability matrix
  FR-01-<slug>.md      # one file per FR (or per small FR cluster)
  FR-02-<slug>.md
```

- The folder is named exactly like the file it replaces (`NN-<name>/`), so the section number and
  every reading-guide reference stay valid.
- The `README.md` index keeps everything that spans FRs; each `FR-nn-<slug>.md` carries the full FR
  block, and the anchor `{#fr-nn}` moves with it.
- Update every inbound link in the same change (`05-functional-requirements.md#fr-03` becomes
  `05-functional-requirements/FR-03-<slug>.md#fr-03`). A split that leaves stale links is worse
  than the long file.
- The same pattern applies to any other section that grows past the threshold (07 by NFR category,
  09 by integration, 04 by flow). Split by the section's own ID unit, never by arbitrary halves.
- Do not split early. Under the threshold, one file beats a folder: fewer reads for an agent,
  simpler diffs for a human.

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
matrix with a blank cell becomes a data leak. If the value is unknown, the required form is
`<unknown - OI-03>` - the open-issue ID, inline, every time. A bare "TBD" is not an accepted
substitute; it is a blank cell with extra steps, and it is not enough to pass the quality gate. This
is what makes "never invent a requirement" (SKILL.md) enforceable inside a table: the cell that
would otherwise carry a guess instead carries the ID of the person who owes you the real answer.

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

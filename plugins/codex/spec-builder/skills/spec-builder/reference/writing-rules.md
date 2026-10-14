# Writing rules

The conventions every file under `docs/specs/` follows, so the sections read as one document and
links keep resolving.

## Output language

**Prose matches the user's language** - descriptions, rationale and table cells.

**Codes are always English**, without exception:

- file names (`05-functional-requirements.md`, never a localised name)
- IDs and anchors (`FR-01`, `{#fr-01}`, `NFR-SEC-02`, `OI-03`)
- entity and field names (`Order.created_at`)
- enum and status values (`DRAFT`, `SUBMITTED`) - the *display label* may be localised, the *value*
  may not
- role names in the permission matrix (`role_approver`)
- section headings' anchor slugs

These end up in code, databases, URLs and commit messages. Where a term has a business name in the user's language and a schema name in English, record both
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

A frontmatter-wide variable (`PROJECT_NAME`) changed on a re-scaffold makes every file CONFLICT at
once: take the new render only for files nobody hand-edited, and reconcile the rest by hand.

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
withdrawn, and is recorded in `13-revision-history.md` - a task, commit or test may still name it.

### Module segment

A repo that specs more than one product module inserts the module's code into every ID it owns:
`FR-BLG-01`, `UC-PAY-03`, `NFR-BLG-SEC-01`. The segment is optional and every prefix in the table
accepts one - the flat form (`FR-01`) stays valid forever and is the default for a single-product
repo; it never needs migrating.

- **Module codes** are 2-4 uppercase `[A-Z0-9]`, first character a letter, declared once in the
  root `README.md` index table alongside the folder each one owns (`BLG` -> `modules/billing/`).
- **NFR takes the module first, then the category**: `NFR-BLG-SEC-01`, never `NFR-SEC-BLG-01`.
  One module segment and one category segment, in that order, and no more.
- **Inside `docs/specs/modules/<module>/`, a bare ID is forbidden.** Every ID defined there carries
  that module's segment: the docs graph keys every ID by its text alone, so two modules that each
  define a bare `FR-01` collapse silently into one node.
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

- **Module-owned**: 05, 07, 08, 09, 10 - one copy per module, under `modules/<folder>/`, scaffolded
  with sample IDs already carrying the module's code and root links pointing two levels up.
- **Cross-cutting, one copy at the root**: the README index, 01, 03, 11, 13 - never a glossary per
  module.
- **12-feasibility follows the risk**: at the root when the buildability question is the platform's
  (one table covering every module's FRs), inside a module when the risk is that module's alone.
- The folder name is the module's lowercase name (`billing`); the ID segment is its code (`BLG`).
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

Never restate content that lives in another section; link to it. Two copies of a business rule
drift apart.

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
  `05-functional-requirements/FR-03-<slug>.md#fr-03`).
- The same pattern applies to any other section that grows past the threshold (07 by NFR category,
  09 by integration, 04 by flow). Split by the section's own ID unit, never by arbitrary halves.
- Do not split early. Under the threshold, one file beats a folder.

## Diagrams

- **Mermaid only.** Never an image.
- **Node labels in double quotes**: `A["Submit for approval"]`. Unquoted labels break on
  parentheses, slashes, and every non-ASCII character.
- **`LR` for process flows** (they read as a timeline), **`TD` for hierarchies** (role trees,
  navigation, decomposition).
- `erDiagram` for the data model, `stateDiagram-v2` for lifecycles, `sequenceDiagram` only when the
  question is genuinely "who calls whom, in what order".
- Every decision node has a labelled edge for every branch, including the failure branch.
- One diagram per question.

## Prose

- No emoji. Anywhere.
- Lists use `-`. Not `*`, not `+`.
- Sentence case headings ("Functional requirements", not "Functional Requirements").
- No em dash; write `-`.
- Tables keep their column headers exactly as the template ships them - tooling and
  cross-references assume them.
- Short sentences. A requirement that needs a semicolon usually needs to be two requirements.

## Requirements are observable

Every FR and acceptance criterion is checkable by someone who has never met the stakeholder.

- Not: "The system is user-friendly." That cannot fail a test.
- Yes: "A submission with no assigned approver is rejected, and the field is highlighted with the
  message defined in NFR-USE-04."

Every NFR carries a number and the way it is measured. "Fast" and "secure" cannot fail a test.

## Acceptance criteria and FR status

Criteria are read by a confirming person, a test using them as its oracle, and `spec-check.py`, so
their form is fixed:

- One list item per criterion, ID first: `- [ ] AC-03.2 Given ..., when ..., then ...`. The number
  before the dot is the FR's (`AC-03.n` lives under `FR-03`, also in module form under
  `FR-BLG-03`); the number after it is never reused.
- **Given / when / then** for behaviour with a trigger. **Done when** for a deliverable with no
  trigger (a report, a document, a decision memo).
- The keywords stay English in every language, like the table headers; the clauses are in the
  spec's language: `AC-01.1 Given 承認待ちの申請, when 承認者が理由なしで却下する, then 却下は拒否される。`
- At least one negative case per FR. `spec-check.py` fails (`negative-case`) an FR with a single
  criterion.
- `AC-nn.n` is scoped to its FR, so it is not a row of the ID table above and the docs graph does
  not trace it on its own; the FR is the traced unit.

Every FR block carries `**Status**:` - `Draft` until the confirmation sheet comes back yes, then
`Confirmed`; `Withdrawn` or `Superseded` when it is retired (the block and the ID stay). Like
priority, the value is English whatever the prose language.

## Generated files

`docs/specs/confirmation.md` (the one-page sheet a person answers) and `docs/specs/index.json` (what
an agent reads first) are written by `python .claude/scripts/spec-check.py --write`, never by hand.
In the sheet only the reply columns - Decision, Comment, Answer, Confirmed - belong to the reader;
they survive regeneration, keyed by ID. Every other cell is rewritten from the spec: correct the
section, then regenerate. The sheet's headings
follow `--lang` (`en`, `ja`); its content is the spec's own text, in the spec's language.

## Cells are never blank

An empty cell reads as "no constraint" - a blank permission-matrix cell becomes a data leak. An
unknown value is written `<unknown - OI-03>`, the open-issue ID inline, every time. A bare "TBD" does
not pass the quality gate.

## Byte stability

No generation dates, timestamps or run IDs in the templates or scaffolded output: they are
prompt-cache prefix content, and one volatile byte cold-misses the cache every run. Dates a *human*
fills in (revision rows, an open issue's needed-by) are fine.

## HTML comments

Authoring guidance lives in `<!-- -->` comments, which Claude Code strips from context. Use them for
"what belongs here", never to hold content.

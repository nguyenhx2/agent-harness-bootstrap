---
name: spec-builder
version: 1.12.0
description: Build the requirements contract for a project - a selective set of numbered BA spec sections under docs/specs/ with stable IDs (FR/NFR/BR/UC/US/DS/DT), acceptance criteria, and grep-verifiable traceability. The core (overview, glossary, FRs, NFRs, open issues, revision history, index) always; stakeholders, business flows, access control, data model, integrations, UI wireframes, feasibility, and a design-system appendix when selected. Do NOT use it to digest documents into a knowledge base, to build the .claude agent harness (that is harness-bootstrap), or to write code or ADRs. Works from any raw input - an idea, meeting notes, a transcript, a PRD, legacy docs, or a codebase - in the user's language. Use this WHENEVER the user wants requirements written, structured, or standardized - "build specs", "tạo specs", "viết tài liệu phân tích yêu cầu", "要件定義を作成して" - and their equivalents in any language. It never invents a requirement; anything unstated becomes a flagged open issue instead of a guess.
allowed-tools: Bash(python:*), Bash(python3:*), Read, Write, Edit, Grep, Glob, AskUserQuestion, Agent
---

# Spec builder

Produces the requirements contract for a project: linked, numbered sections under `docs/specs/`,
traceable from user story to feasibility row, with no invented requirements in them.

**The sections are real files, not prose to retype.** They live in `assets/specs/` and are installed
by `scripts/scaffold.py` with their headings, tables, column headers, Mermaid scaffolds, and inline
authoring notes intact. Your job is the content and the judgment - the elicitation, the FR list, the
priorities, the security posture, the feasibility call. Do not regenerate the shape.

**Not every project gets every section.** The core is always installed: `README`, `01-overview`,
`03-glossary`, `05-functional-requirements`, `07-non-functional-requirements`,
`13-revision-history`. The rest are selected by what the input material actually contains - a
backend batch service has no wireframes to specify, and an empty section is noise that erodes trust
in the filled ones. Section numbers are stable whether or not their neighbors exist.

## The rule that governs everything

**Never invent a requirement.** Anything not stated by a stakeholder and not clearly implied by the
source goes to section 11 as an assumption (`AS-nn`) or open issue (`OI-nn`) and is flagged in the
final summary. Why this is the most expensive error available here, and the tell that you are about
to make it: [`reference/elicitation.md`](reference/elicitation.md).

## Tool discipline

- **One `AskUserQuestion` call per batch, then stop asking.** Skip any question the user already
  answered in their request or source material - confirming what someone just told you is friction,
  not diligence.
- **Scripts write scaffolded files.** `scaffold.py` installs the sections; never hand-write a
  template's shape. Hand-writing re-opens the drift the assets exist to close.
- **Parallel fill is allowed once 05 is confirmed.** Sections that do not depend on each other
  (02, 04, 09, 10 against a settled FR list) may be filled by agents dispatched in ONE message when
  the user wants speed. 05, 07, and 12 stay in the main session - they carry the judgment.
- **Verify, don't paste.** Whatever an agent drafts, re-check its IDs and cross-links against 05
  before accepting - agent output is input to check, not truth.

## Procedure

**1. Elicit.** [`reference/elicitation.md`](reference/elicitation.md) - the ask/infer table, the
routing by input type, the batches. Establish the system name and purpose, the problem, the
candidate feature list, the roles, the constraints, and the output language from whatever the user
brought. Infer *structure*, ask for *decisions*: priorities, permission scope, NFR targets, volumes,
and security posture are always asked.

**2. Select the sections and confirm the FR list** - one gate, before writing anything else:

- The FR list with *proposed* MoSCoW priorities, the roles, and the open issues so far.
- The section selection: core always; recommend each optional section only when the material shows
  it is real (stakeholder map -> 02, process handoffs -> 04, roles with scopes -> 06, owned
  persistent data -> 08, external systems -> 09, screens -> 10, known unknowns -> 11, buildability
  risk -> 12, an existing or planned design system -> 14). The elicitation file carries the
  question batch. Section 11 is auto-added the moment the first `AS-nn`/`OI-nn` exists - the
  never-invent rule needs somewhere to put them.

Everything from 02 onward derives from this gate; a wrong FR list costs every downstream document.

**3. Scaffold.** Write `vars.json`, then:

```bash
python scripts/scaffold.py --target <repo> --vars vars.json --dry-run   # review first
python scripts/scaffold.py --target <repo> --vars vars.json
```

```json
{
  "vars": {
    "PROJECT_NAME": "...",
    "PROJECT_SLUG": "...",
    "PROJECT_PURPOSE": "one line, the user's language",
    "DOC_OWNER": "..."
  },
  "flags": ["ai", "ui", "db", "flows", "access", "integration", "feasibility"]
}
```

Two kinds of flags, all lowercase in `vars.json` (markers inside templates are UPPERCASE):

- **Section flags** (from step 2): `stakeholders`, `flows`, `access`, `db` (08), `integration`,
  `ui` (10), `feasibility`, `design` (14). An unset flag skips the file. Section 11 is core, not
  flagged - it is where every `AS-nn`/`OI-nn` lives, and the never-invent rule needs that registry
  in every render.
- **Content flags**: `ai` (model consumes or produces content - switches on the AI/human boundary
  table in 05, the untrusted-content NFRs in 07, model feasibility in 12), and `ui`/`db` also gate
  conditional blocks inside other sections. Set only what is true.

The scaffolder **never overwrites an existing file**: `ADDED` / `KEPT` (identical) / `CONFLICT`
(exists and differs). CONFLICT is the reconciliation queue, not an error - resolve each by hand,
never delete what the user wrote. It exits non-zero on an unresolved `{{VAR}}`. Changing a
frontmatter-wide variable (`PROJECT_NAME`) floods every file with CONFLICT at once; take the new
render only for files nobody hand-edited, reconcile the rest.

**4. Fill.** Section by section, in order - each depends on the last (or in parallel per Tool
discipline above). Follow the inline `<!-- -->` notes; conventions are in
[`reference/writing-rules.md`](reference/writing-rules.md) - read it before writing, including the
folder split rule for sections that outgrow one file (~400 lines / ~25 KB).

Three sections carry the load, and they are the three most often thinned out:

- **05** - every FR is observable, anchored `{#fr-nn}`, with input/output, business rules (`BR-nn`
  with a source), and acceptance criteria including a negative case. Then UC-xx, US-xx, and the
  traceability matrix.
- **07** - the security NFRs are **mandatory and never "TBD"**: classification, encryption at rest
  and in transit, access-control model, secret management, and - if user content reaches an LLM -
  prompt-injection handling and provider retention terms. Undecided means an OI with an owner and a
  date, never a blank cell. The failure mode this prevents:
  [`reference/ba-standards.md`](reference/ba-standards.md).
- **12** (when selected) - every FR appears with Yes / Partial / No and a reason. "Partial" and
  "No" are the most valuable output of this skill: cheap now, expensive in month four.

**5. Verify.** The quality gate below. Then surface the open issues to the user - they cannot
correct an assumption you did not tell them you made. Once the set is complete, offer to invoke
`harness-bootstrap` via the **`Skill`** tool with `FR_LIST` (section 05's FR IDs, verbatim, in
order) and `GLOSSARY_SEED` (section 03's terms) prefilled; state the handoff in words if the tool
is unavailable.

## Re-running on an existing spec

New input against existing specs is `/spec-ingest`'s procedure (installed with the sections) -
statement-by-statement diff, conflicts surfaced never overwritten, IDs appended never renumbered,
one revision row per ingest. Follow it even when the command file is not installed. Run
`scaffold.py` again only to add sections not selected the first time; it reports `KEPT`/`CONFLICT`
for the rest - the byte-level form of the same rule.

## What standard this follows

An **opinionated synthesis**, not a certified implementation: ISO/IEC/IEEE 29148's SRS content
model, ISO/IEC 25010:2023's NFR taxonomy, BABOK v3 elicitation and traceability, MoSCoW, Cockburn
use cases, Given/When/Then, and OWASP ASVS + the LLM Top 10 behind 07's mandatory security NFRs.
Which section draws on which standard, why this shape, and the limits (not for regulated
industries; no safety attribute): [`reference/ba-standards.md`](reference/ba-standards.md).

**The output is the input contract for `harness-bootstrap`**: 05 clusters into the dev-agent
roster, 08 sets `db`, 10 sets `ui`, 07 sets `ai` and deny-rule strictness, 12 seeds the Phase 1
backlog (by hand - no automated reader). Full consumption map: ba-standards.md Part 3.

### Living specs: /spec-ingest and /spec-retract

Two commands ship with this skill (installed to `.claude/commands/` by the scaffold step) and carry
the update discipline:

- **`/spec-ingest <source>`** - fold a new source into the existing sections: diff, conflicts
  surfaced, IDs appended, one revision row, ripples applied (glossary copy, owning dev agent's FR
  list, traceability graph).
- **`/spec-retract <source|ID|claim>`** - trace everything a bad source touched, convert
  unsupported statements to `OI-nn` instead of deleting, mark withdrawn IDs in place, block
  affected tasks with a `human_gate`, rebuild the graph.

Both record to `docs/context/tool-changelog.md`. Versioning is the revision history plus git - no
side channel.

### The specs graph

When the set is complete (and after any later edit), if the repo carries the harness scripts:
`python .claude/scripts/docs-graph.py` then `python .claude/scripts/graph-html.py` ->
`docs/context/specs-graph.html`, a self-contained interactive graph with orphan IDs called out.
Not installed yet: the graph arrives with harness-bootstrap's verify step; move on.

## Composes with harness-bootstrap

If the full docs workspace exists, seed once 03 and 05 are filled: one
`docs/requirements/PRD-FR-NN-<slug>.md` stub per FR (Source requirement linking back to 05's
anchor), `docs/context/glossary.md` from 03, `docs/context/business-rules.md` from 05's BR tables.
**Seed, do not duplicate** - the spec section stays the source of truth. Re-seeding is safe:
reconcile against current 03/05, keep what a human edited, flag mismatches as OIs. No docs tree at
all: invoke `harness-bootstrap` first via the `Skill` tool. Its scaffolder fails loudly on
unresolved `{{VAR}}`s, and `{{FR_LIST}}` is one of them - build it from 05 verbatim.

## Quality gate

**Completeness**
- [ ] Every SELECTED section exists with frontmatter and at least one filled block; the core is
      always present (`README`, 01, 03, 05, 07, 11, 13). Verify: list `docs/specs/`, compare against
      the recorded selection from step 2; count includes any section that became a folder.
- [ ] Any `AS-`/`OI-`/`CO-` ID anywhere implies section 11 exists and defines it. Verify:
      `grep -o` the three prefixes across `docs/specs/`; if found and 11 is absent, the gate fails.
- [ ] No table cell is blank, and none reads a bare "TBD". Verify: grep every file for an empty
      cell (`\|\s*\|`) and the literal `TBD`; either hit fails unless the cell carries
      `<unknown - OI-nn>`, per writing-rules.md.
- [ ] Section 07's security subsections are all filled - classification, encryption,
      access-control model, secret management, and (if applicable) untrusted-content handling and
      provider retention. Verify: grep 07 for "TBD" (zero hits); every `NFR-SEC-nn` row has a
      non-placeholder value.

**Traceability** (each check applies only when both endpoint sections are selected)
- [ ] Every FR appears in 12's feasibility table. Verify: `grep -o 'FR-[0-9]*'` over 05 (file or
      folder) and 12, `sort -u` both, diff - they match exactly.
- [ ] Every FR has acceptance criteria including one negative case. Verify: for each `## FR-nn`
      heading, at least two `AC-nn.n` lines before the next `##`, one opening with "Given" plus an
      invalid or missing precondition.
- [ ] Every screen in 10 names an FR; every user-facing FR names a screen. Verify: 10's FR set is
      a subset of 05's; every user-facing FR in 05 appears in 10.
- [ ] Every component in 10's Elements tables has a `DS-nn` row in 14 (when 14 is selected); every
      role in 06 exists in 03; every entity in 06 exists in 08.
- [ ] All internal links resolve, including links into split-section folders. Verify: grep for
      `](`, extract path + anchor, confirm the target exists and carries the anchor.

**Grounding**
- [ ] Every requirement traces to something a stakeholder said or a source states. Verify: for
      each FR and mandatory security NFR, name the source line in your working notes - if none can
      be named, it belongs in 11, not 05 or 07.
- [ ] Every assumption has its impact-if-false; every open issue has a named owner. Verify: the
      empty-cell grep scoped to 11's tables.
- [ ] The final summary lists every OI, every AS, every Partial/No, and every NFR target you
      proposed rather than received. Verify: count the IDs in 11 and the Partial/No rows in 12;
      the summary names the same counts.

**Hygiene**
- [ ] Codes, IDs, filenames, entity names, and enum values are English, whatever the prose
      language. Verify: grep the ID columns for non-ASCII - zero hits.
- [ ] No generation date, timestamp, or run ID in any file. Verify: grep for ISO dates and
      "Generated on"; only human-filled dates in 11 and 13 are permitted.
- [ ] Mermaid node labels double-quoted; no emoji; lists use `-`. Verify per writing-rules.md.

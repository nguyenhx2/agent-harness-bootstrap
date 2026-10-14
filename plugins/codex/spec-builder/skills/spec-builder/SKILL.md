---
name: spec-builder
version: 1.20.1
description: Writes the requirements contract for a project under docs/specs/ from raw input - an idea, meeting notes, a transcript, a PRD, legacy docs or a codebase - in the user's language. Stable FR IDs, Given/When/Then acceptance criteria, flagged assumptions and open issues, a one-page confirmation sheet a PO or client answers yes/no/change, and a JSON index agents read instead of whole documents. Never invents a requirement. Research, strategy and docs repos get a lighter contract. Use when requirements must be written, confirmed, updated or standardized - "build specs", "tạo specs", "viết tài liệu phân tích yêu cầu", "要件定義を作成して", or the same in any language. Not for building the .claude agent harness (harness-bootstrap), digesting documents into a knowledge base, or writing code or ADRs.
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

**A repository whose product is not code gets the light contract.** Research questions, a decision
brief, or a docs scope - each item an `FR-nn` with `Done when` criteria - in README, 05, 11 and 13
only. It is selected by the same purpose flags harness-bootstrap uses (step 4).

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

**1. Read the sources.** Before the first question, when the user brought files rather than prose:
`scripts/route_sources.py <files-folders-urls> -o plan.json` picks a reader per source and prints
why, then `scripts/ingest.py` executes each plan entry. **Show the user the plan first**: one line
per source (file -> reader, or UNREADABLE -> why and the fix), then read. That table and the final
summary are the only progress reporting this step gets - never narrate file-by-file progress. You cannot elicit against a document you
have not read. **A source that cannot be read becomes an `OI-nn` in section 11** naming the file,
why it is unreadable, and the fix (a `pip install`, or a re-export request) - never a silent gap;
a scanned PDF extracts successfully and returns almost nothing, which is where invented
requirements come from. The routing table, the overrides, and the limits:
[`reference/source-routing.md`](reference/source-routing.md).

**2. Elicit.** [`reference/elicitation.md`](reference/elicitation.md) - the ask/infer table, the
routing by input type, the batches. Establish the system name and purpose, the problem, the
candidate feature list, the roles, the constraints, and the output language from whatever the user
brought. Infer *structure*, ask for *decisions*: priorities, permission scope, NFR targets, volumes,
and security posture are always asked.

**3. Select the sections and confirm the FR list** - one gate, before writing anything else.
First the shape: a repo that ships no code (research, strategy, docs) takes the light contract and
skips the section selection below - its four files are fixed.

- The FR list with *proposed* MoSCoW priorities, the roles, and the open issues so far.
- The section selection: core always; recommend each optional section only when the material shows
  it is real (stakeholder map -> 02, process handoffs -> 04, roles with scopes -> 06, owned
  persistent data -> 08, external systems -> 09, screens -> 10, known unknowns -> 11, buildability
  risk -> 12, an existing or planned design system -> 14). The elicitation file carries the
  question batch. Section 11 is auto-added the moment the first `AS-nn`/`OI-nn` exists - the
  never-invent rule needs somewhere to put them.

**Record the selection before you scaffold.** Write `<target>/docs/specs/.sections.json`: every
optional section in `selected` or `excluded` exactly once, each with a one-line reason, core
sections in neither. `scaffold.py` refuses to write anything without it, and refuses on an empty
reason or a selection that contradicts `vars.json`'s flags - the schema and the refusal message
are in the scaffolder itself.

Everything from 02 onward derives from this gate; a wrong FR list costs every downstream document.

**4. Scaffold.** Write `vars.json` (`.sections.json` from step 3 must already exist and agree with
its flags, or the run refuses and writes nothing), then:

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

Three kinds of flags, all lowercase in `vars.json` (markers inside templates are UPPERCASE):

- **Purpose flags**, the same as harness-bootstrap's: `purpose_code`, `purpose_research`,
  `purpose_strategy`, `purpose_docs`. Any non-code purpose without `purpose_code` scaffolds the
  light contract and needs no `.sections.json`; section flags are then refused. None at all means
  the full set, as before.

- **Section flags** (from step 3): `stakeholders`, `flows`, `access`, `db` (08), `integration`,
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

**Flat or module form.** Flat is the default and stays valid forever: one set of sections at
`docs/specs/`, IDs like `FR-01`. Use the module form when the product has real module boundaries
(separate owners, separate FR sets) or when the user asks for one module's spec - "build the spec
for billing" means module form, code `BLG`, and every ID that module defines carries it
(`FR-BLG-01`, `NFR-BLG-SEC-01`). Module-owned sections (05, 07, 08, 09, 10) go to
`docs/specs/modules/<folder>/`, the rest stay shared at the root, and the section selection is
still decided once per section, not per module.

```bash
python scripts/scaffold.py --target <repo> --vars vars.json --module BLG:billing --module CAT:catalog
```

Bare IDs inside a module folder are forbidden, and the reason is mechanical: the traceability graph
is flat, so two modules that each define `FR-01` merge into one node and one of them silently
becomes a mention of the other. Details: [`reference/writing-rules.md`](reference/writing-rules.md).

**5. Fill.** Section by section, in order - each depends on the last (or in parallel per Tool
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

**6. Verify and confirm.** `python .claude/scripts/spec-check.py --write` (installed by the
scaffold; add `--lang ja` for a Japanese reader) writes the two derived files and checks the set:
unique IDs, criteria on every live FR in checkable form, open issues defined and owned, and the
derived files in step with the spec. Fix every FAIL, then run the quality gate below.

- `docs/specs/confirmation.md` is the page the PO or client answers - each FR in plain words, its
  criteria, its open issues, and a yes / no / change column. Hand it over with the open issues;
  they cannot correct an assumption you did not tell them you made.
- `docs/specs/index.json` is what agents read first, so a task touching one FR loads one block.

When the sheet comes back, re-run `--write` (the replies are kept), fold each `change` in through
`/spec-ingest`, and set **Status**: Confirmed on each yes with one revision row. Once the set is complete, offer to invoke
`harness-bootstrap` via the **`Skill`** tool with `FR_LIST` (section 05's FR IDs, verbatim, in
order) and `GLOSSARY_SEED` (section 03's terms) prefilled; state the handoff in words if the tool
is unavailable.

## Into the agentic loop

A confirmed FR enters the loop as FR, then task, implement, verify-plan, review, done, with its
criteria as the oracle at every step - and a criterion found wrong goes back to the spec, never
around it. Most changes need none of that: a change that leaves every promise on the sheet intact
needs no spec work, and one that adds behaviour inside an agreed FR needs one appended criterion.
The step table and the proportion rule: [`reference/agentic-loop.md`](reference/agentic-loop.md).

## Re-running on an existing spec

New input against existing specs is `/spec-ingest`'s procedure (installed with the sections) -
statement-by-statement diff, conflicts surfaced never overwritten, IDs appended never renumbered,
one revision row per ingest. Follow it even when the command file is not installed. Run
`scaffold.py` again only to add sections not selected the first time - move each one from
`excluded` to `selected` in `.sections.json` with the reason that changed, and set its flag; it
reports `KEPT`/`CONFLICT` for the rest - the byte-level form of the same rule.

## What standard this follows

An **opinionated synthesis**, not a certified implementation: ISO/IEC/IEEE 29148's SRS content
model, ISO/IEC 25010:2023's NFR taxonomy, BABOK v3 elicitation and traceability, MoSCoW, Cockburn
use cases, Given/When/Then, and OWASP ASVS + the LLM Top 10 behind 07's mandatory security NFRs.
Which section draws on which standard, why this shape, and the limits (not for regulated
industries; no safety attribute): [`reference/ba-standards.md`](reference/ba-standards.md).

**The output is the input contract for `harness-bootstrap`**: 05 clusters into the dev-agent
roster, 08 sets `db`, 10 sets `ui`, 07 sets `ai` and deny-rule strictness, 12 seeds the Phase 1
backlog (by hand - no automated reader). Full consumption map: ba-standards.md Part 3. Agents on
the harness side read `docs/specs/index.json` first and open one FR block at its anchor.

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

### The traceability check

When the set is complete (and after any later edit), if the repo carries the harness scripts:
`python .claude/scripts/docs-graph.py --check` prints every orphan ID - one mentioned once and
referenced nowhere. Name each one as unstarted work or a dead reference. Not installed yet: the
check arrives with harness-bootstrap; move on.

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
      `docs/specs/.sections.json`'s `selected`; count includes any section that became a folder.
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
- [ ] Every FR has acceptance criteria in Given/when/then or Done-when form, including one
      negative case. Verify: `spec-check.py` exits 0 and prints no single-criterion warning; read
      each FR's criteria for the invalid or missing precondition.
- [ ] The confirmation sheet and the index match the spec. Verify: `spec-check.py` without
      `--write` exits 0 (it fails `stale` otherwise).
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
- [ ] Every source that could not be read has an `OI-nn` naming it. Verify: compare the routing
      plan's `unreadable` and `vision` entries against 11 - each file name appears there, with the
      fix (a `pip install` or a re-export request) stated.
- [ ] The final summary lists every OI, every AS, every Partial/No, and every NFR target you
      proposed rather than received. Verify: count the IDs in 11 and the Partial/No rows in 12;
      the summary names the same counts.

**Hygiene**
- [ ] Codes, IDs, filenames, entity names, and enum values are English, whatever the prose
      language. Verify: grep the ID columns for non-ASCII - zero hits.
- [ ] No generation date, timestamp, or run ID in any file. Verify: grep for ISO dates and
      "Generated on"; only human-filled dates in 11 and 13 are permitted.
- [ ] Mermaid node labels double-quoted; no emoji; lists use `-`. Verify per writing-rules.md.

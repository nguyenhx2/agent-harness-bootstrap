---
name: spec-builder
version: 1.7.0
description: Build a complete BA specification set (13-section structure under docs/specs/) for any project from raw input - an idea, meeting notes, a transcript, an existing PRD, or legacy docs. Use when the user asks to "build specs", "tạo specs", "viết tài liệu phân tích yêu cầu", "chuẩn hóa tài liệu BA", or wants requirement docs scaffolded for a new or existing project.
allowed-tools: Bash(python:*), Bash(python3:*), Read, Write, Edit, Grep, Glob, AskUserQuestion, Agent
---

# Spec builder

Produces the requirements contract for a project: thirteen linked sections under `docs/specs/`,
traceable from user story to feasibility row, with no invented requirements in them.

**The thirteen sections are real files, not prose to retype.** They live in `assets/specs/` and are
installed by `scripts/scaffold.py` with their headings, tables, column headers, Mermaid scaffolds,
and inline authoring notes intact. Your job is the content and the judgment - the elicitation, the
FR list, the priorities, the security posture, the feasibility call. Do not regenerate the shape.

## The rule that governs everything

**Never invent a requirement.** Anything not stated by a stakeholder and not clearly implied by the
source material goes to `11-assumptions-constraints.md` as an assumption (AS-nn) or an open issue
(OI-nn), with an owner, and is flagged to the user in the final summary.

A missing requirement stalls and gets asked about. A plausible invented one gets estimated, built,
and discovered in UAT - every document downstream treats it as settled. It is the most expensive
error available here, and the one a language model is most prone to.

## Procedure

**1. Elicit.** [`reference/elicitation.md`](reference/elicitation.md). Establish the system name and
one-line purpose, the problem, the candidate feature list, the roles, the known constraints, and the
output language - from whatever the user brought (a line, a transcript, a PRD, a codebase). Ask only
what cannot be inferred, in batches of at most 4 via `AskUserQuestion`.

Infer *structure*, ask for *decisions*. Priorities, permission scope, NFR targets, volumes, and
security posture are always asked - a number you made up is a fabricated requirement.

**2. Confirm the FR list** before writing anything else: the FRs with *proposed* MoSCoW priorities,
the roles, and the open issues so far. Everything from 02 onward derives from this list; a wrong
list costs twelve documents.

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
  "flags": ["ai", "ui", "db"]
}
```

Flags gate the conditional blocks inside the templates: `ai` (a model consumes or produces content -
this switches on the AI/human boundary table in 05, the untrusted-content NFRs in 07, and model
feasibility in 12), `ui` (the system has screens), `db` (it owns persistent data). Set only what is
true; an unset flag removes the block cleanly.

The scaffolder **never overwrites an existing file**. It reports `ADDED` / `KEPT` (identical) /
`CONFLICT` (exists and differs). CONFLICT is not an error - it is the reconciliation queue for a
project that already has specs. Resolve each by hand; never delete what the user wrote. It exits
non-zero on an unresolved `{{VAR}}`, so a missing variable fails loudly.

Changing a variable that appears in every file's frontmatter (`PROJECT_NAME`, `PROJECT_SLUG`) makes
every rendered file's bytes differ from what is on disk, so a re-run reports `CONFLICT` on all 14
files at once, not just the one you meant to change. Resolve that flood by taking the new render only
for files nobody has hand-edited since the last scaffold; reconcile the rest by hand, the same as any
other CONFLICT.

**4. Fill.** Section by section, in order - each depends on the last. Follow the inline `<!-- -->`
notes in each file; they say what belongs there and what the common failure is. Conventions are in
[`reference/writing-rules.md`](reference/writing-rules.md); read it before you start writing.

Three sections carry the load, and they are the three most often thinned out:

- **05** - every FR is observable, anchored `{#fr-nn}`, and carries input/output, business rules
  (BR-nn, each with a source), and acceptance criteria including a negative case. Then UC-xx,
  US-xx, and the traceability matrix.
- **07** - the security NFRs are **mandatory and are never "TBD"**: data classification, encryption
  at rest and in transit, the access-control model, secret management, and - if user content reaches
  an LLM - prompt-injection handling (untrusted content is data, never instructions) and the
  provider's data-retention terms. If the organisation has not decided, that is an OI with a named
  owner and a date. It is still not a blank cell.
- **12** - every FR from 05 appears in the feasibility table with Yes / Partial / No and a reason or
  dependency. No FR is omitted because it is "obviously fine". "Partial" and "No" are the most
  valuable output of this skill: they are cheap now and expensive in month four.

**5. Verify.** The quality gate below. Then surface the open issues to the user - they cannot
correct an assumption you did not tell them you made. Once the spec set is complete, offer to invoke
`harness-bootstrap` via the **`Skill`** tool - with `FR_LIST` (section 05's FR IDs, verbatim, in the same
order they appear) and `GLOSSARY_SEED` (section 03's terms) prefilled from this spec set, so its intake
does not re-collect what this skill already produced. State the exact handoff in words if the `Skill`
tool is unavailable.

## Re-running on an existing spec

New input arrives - more meeting notes, a follow-up interview, a corrected PRD - and `docs/specs/`
already has content. Reconcile, section by section; never regenerate over what is there:

- Read the existing section first. Treat it the same way you would treat a stakeholder's prior
  answer, not a draft to discard.
- New information that agrees with what is there: leave the section alone.
- New information that adds detail (a new FR, a new field, a new NFR target): append it with the
  next free ID. IDs already in use are never renumbered or reused.
- New information that contradicts what is there: do not silently overwrite. Record both readings as
  an OI in 11 and ask which one is current - a contradiction resolved without asking is the invented-
  requirement failure wearing a disguise.
- A section a human has since hand-edited (prose that no longer matches the template's voice, a row
  the template does not generate) is a sign someone corrected it after generation. Preserve it; fold
  new information around it rather than through it.
- Run `scripts/scaffold.py` again only to add files that do not exist yet (a section skipped the
  first time, e.g.); it will report `KEPT` or `CONFLICT` for everything else, which is the byte-level
  version of the same rule - see the CONFLICT guidance above.

## What standard this follows

An **opinionated synthesis**, not a certified implementation of one standard: the SRS content model of
ISO/IEC/IEEE 29148, the NFR taxonomy of ISO/IEC 25010:2023, BABOK v3 for elicitation and traceability,
MoSCoW, Cockburn use cases, Given/When/Then, and OWASP ASVS + the LLM Top 10 behind 07's mandatory
security NFRs. Not certified against 29148 - a regulated system needs the real standard, not this.

**The output is the input contract for `harness-bootstrap`**: 05 clusters into the dev-agent roster,
08 sets the `db` flag, 10 sets `ui`, 07 sets `ai` and the strictness of the deny rules (not the deny
rules themselves - those come from intake). 12 is what you draw the Phase 1 backlog from by hand;
unlike the others, harness-bootstrap has no automated step that reads it.
Without the specs, `spec-guardian` has nothing to guard and requirement drift is undetectable.
Full derivation and integration map: [`reference/ba-standards.md`](reference/ba-standards.md).

### Living specs: /spec-ingest and /spec-retract

The spec set is not write-once. Two commands ship with this skill (installed to
`.claude/commands/` by the scaffold step, alongside the sections) and carry the update discipline:

- **`/spec-ingest <source>`** - fold a new source (notes, transcript, legacy doc) into the
  existing sections: statement-by-statement diff, conflicts surfaced never overwritten, new IDs
  appended never renumbered, one revision-history row per ingest, and the ripples applied - the
  glossary copy, the owning dev agent's FR list, the traceability graph.
- **`/spec-retract <source|ID|claim>`** - the reverse: trace everything a bad source or wrong
  claim touched, convert unsupported statements to `OI-nn` open issues instead of deleting them,
  mark withdrawn IDs in place (numbers never come back), block affected tasks with a
  `human_gate`, and rebuild the graph.

Both record to `docs/context/tool-changelog.md`. Versioning is the revision history plus git - no
side channel.

### The specs graph

When the spec set is complete (and after any later spec edit), if the repo already carries the
harness scripts (`.claude/scripts/docs-graph.py` from harness-bootstrap), run:
`python .claude/scripts/docs-graph.py` then `python .claude/scripts/graph-html.py`. The result is
`docs/context/specs-graph.html` - a self-contained interactive graph of how the sections,
requirements, ADRs, and tasks reference each other, with orphan IDs called out. If the harness is
not installed yet, note that the graph arrives with harness-bootstrap's verify step and move on.

## Composes with harness-bootstrap

If the full docs workspace exists (`docs/requirements/`, `docs/context/`, `docs/templates/` - see the
`harness-bootstrap` skill), also seed, once 03 and 05 are filled:

- `docs/requirements/PRD-FR-NN-<slug>.md` - one stub per FR, from `docs/templates/PRD.md`, with the
  `Source requirement` link pointing back at `../specs/05-functional-requirements.md#fr-nn`.
- `docs/context/glossary.md` - from section 03 (terms, aliases, enum values).
- `docs/context/business-rules.md` - from the BR-nn tables in section 05.

Seed, do not duplicate: the spec section stays the source of truth and the context file links back
to it. If there is no docs tree at all, invoke `harness-bootstrap` first via the `Skill` tool (see
step 5's `FR_LIST`/`GLOSSARY_SEED` handoff above) - it creates the one this skill writes into.

**Re-running this seeding step is safe.** If a `PRD-FR-NN-<slug>.md`, `glossary.md`, or
`business-rules.md` already exists, reconcile it against the current 03/05 content instead of
overwriting it: add what is new, keep what a human has since edited, and flag a mismatch between the
spec and the seeded file as an open issue in 11. A seeded file is never regenerated over.

`harness-bootstrap`'s scaffolder fails loudly (non-zero exit) on any unresolved `{{VAR}}`, and
`{{FR_LIST}}` is one of them - build it from section 05's FR IDs verbatim, in the same order they
appear there, or the scaffold run stops instead of shipping a placeholder into a rule file.

## Quality gate

**Completeness**
- [ ] All 14 files exist (README + 13) with frontmatter; none is an empty stub unless the user asked
      for a skeleton. Verify: list `docs/specs/*.md`, count 14; each file has a `---`-delimited
      frontmatter block and at least one filled section below it.
- [ ] No table cell is blank, and none reads a bare "TBD". Verify: grep every file under
      `docs/specs/` for an empty cell (`\|\s*\|`) and for the literal string `TBD`. Either hit fails
      the gate unless the cell instead carries `<unknown - OI-nn>`, per writing-rules.md.
- [ ] Section 07's security subsections are all filled - classification, encryption, access-control
      model, secret management, and (if applicable) untrusted-content handling and provider
      retention. Verify: grep `07-non-functional-requirements.md` for "TBD" (zero hits expected),
      and confirm every `NFR-SEC-nn` row has a non-placeholder value in its last column.

**Traceability**
- [ ] Every FR appears in the feasibility table in 12. Verify: `grep -o 'FR-[0-9]*'` over
      `05-functional-requirements.md` and over `12-technical-feasibility.md`, `sort -u` both, and
      diff the two sets - they match exactly.
- [ ] Every FR has acceptance criteria, including at least one negative case. Verify: for each `##
      FR-nn` heading in 05, at least two `AC-nn.n` lines appear before the next `##`, and at least
      one of them opens with "Given" plus an invalid or missing precondition.
- [ ] Every screen in 10 names an FR; every user-facing FR names a screen. Verify: `grep -o
      'FR-[0-9]*'` over `10-ui-ux-wireframes.md` is a subset of 05's FR set; every FR in 05 with a
      user-facing surface appears at least once in that same grep.
- [ ] Every role in 06 exists in 03; every entity in 06 exists in 08. Verify: diff the role column
      headers in 06's permission matrix against the role list in 03; diff the entity column in 06's
      matrix against the entity names in 08's data dictionary.
- [ ] All internal links resolve. Verify: grep every file for `](`, extract the path and the
      `#anchor` when present, and confirm the target file exists and (if an anchor was given) that
      the anchor string appears in that file.

**Grounding**
- [ ] Every requirement traces to something a stakeholder said or a source document states. Nothing
      in 05 or 07 exists because it seemed likely. Verify: for each FR and each mandatory security
      NFR, name the stakeholder or source line it came from in your working notes before checking
      this box - if none can be named, it is an invention and belongs in 11, not in 05 or 07.
- [ ] Every assumption is in 11 with its impact-if-false; every open issue has a named owner. Verify:
      every `AS-nn` row has a non-empty "Impact if false" cell; every `OI-nn` row has a non-empty
      "Owner" cell - same empty-cell grep as the completeness check, scoped to 11's tables.
- [ ] The final summary lists every OI, every AS, every Partial/No, and every NFR target you
      proposed rather than received. Verify: count `OI-` and `AS-` IDs in 11 and confirm the same
      count is named in the summary; count `Partial`/`No` rows in 12 and do the same.

**Hygiene**
- [ ] Codes, IDs, filenames, entity names, and enum values are English, whatever the prose language.
      Verify: grep the ID columns (`FR-`, `NFR-`, `BR-`, entity and field names) for non-ASCII
      characters - zero hits.
- [ ] No generation date, timestamp, or run ID in any file. Verify: grep every file for an ISO date
      pattern (`\d{4}-\d{2}-\d{2}`) or "Generated on" - the only permitted hits are human-filled
      dates in 11's open-issue table and 13's revision history.
- [ ] Mermaid diagrams with double-quoted node labels; no emoji; lists use `-`. Verify: inside every
      ` ```mermaid ` block, grep for an unquoted label (`\[[A-Za-z]` not immediately followed by `"`)
      and for lines starting with `*` or `+` instead of `-`; grep the whole file for emoji code
      points - all zero hits.

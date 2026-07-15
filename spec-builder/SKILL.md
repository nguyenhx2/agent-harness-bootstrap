---
name: spec-builder
version: 1.3.0
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
correct an assumption you did not tell them you made.

## What standard this follows

An **opinionated synthesis**, not a certified implementation of one standard: the SRS content model of
ISO/IEC/IEEE 29148, the NFR taxonomy of ISO/IEC 25010:2023, BABOK v3 for elicitation and traceability,
MoSCoW, Cockburn use cases, Given/When/Then, and OWASP ASVS + the LLM Top 10 behind 07's mandatory
security NFRs. Not certified against 29148 - a regulated system needs the real standard, not this.

**The output is the input contract for `harness-bootstrap`**: 05 clusters into the dev-agent roster,
08 sets the `db` flag, 10 sets `ui`, 07 sets `ai` and the deny rules, 12 seeds the Phase 1 backlog.
Without the specs, `spec-guardian` has nothing to guard and requirement drift is undetectable.
Full derivation and integration map: [`reference/ba-standards.md`](reference/ba-standards.md).

## Composes with harness-bootstrap

If the full docs workspace exists (`docs/requirements/`, `docs/context/`, `docs/templates/` - see the
`harness-bootstrap` skill), also seed, once 03 and 05 are filled:

- `docs/requirements/PRD-FR-NN-<slug>.md` - one stub per FR, from `docs/templates/PRD.md`, with the
  `Source requirement` link pointing back at `../specs/05-functional-requirements.md#fr-nn`.
- `docs/context/glossary.md` - from section 03 (terms, aliases, enum values).
- `docs/context/business-rules.md` - from the BR-nn tables in section 05.

Seed, do not duplicate: the spec section stays the source of truth and the context file links back
to it. If there is no docs tree at all, run `harness-bootstrap` first - it creates the one this
skill writes into.

## Quality gate

**Completeness**
- [ ] All 14 files exist (README + 13) with frontmatter; none is an empty stub unless the user asked
      for a skeleton.
- [ ] No table cell is blank. An unknown value carries its open-issue ID, not "TBD".
- [ ] Section 07's security subsections are all filled - classification, encryption, access-control
      model, secret management, and (if applicable) untrusted-content handling and provider
      retention. None says "TBD".

**Traceability**
- [ ] Every FR appears in the feasibility table in 12. Count both; the numbers match.
- [ ] Every FR has acceptance criteria, including at least one negative case.
- [ ] Every screen in 10 names an FR; every user-facing FR names a screen.
- [ ] Every role in 06 exists in 03; every entity in 06 exists in 08.
- [ ] All internal links resolve - grep for `](` and verify the file and the anchor exist.

**Grounding**
- [ ] Every requirement traces to something a stakeholder said or a source document states. Nothing
      in 05 or 07 exists because it seemed likely.
- [ ] Every assumption is in 11 with its impact-if-false; every open issue has a named owner.
- [ ] The final summary lists every OI, every AS, every Partial/No, and every NFR target you
      proposed rather than received.

**Hygiene**
- [ ] Codes, IDs, filenames, entity names, and enum values are English, whatever the prose language.
- [ ] No generation date, timestamp, or run ID in any file. These are prompt-cache prefix content.
- [ ] Mermaid diagrams with double-quoted node labels; no emoji; lists use `-`.

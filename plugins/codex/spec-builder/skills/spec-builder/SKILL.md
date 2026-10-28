---
name: spec-builder
version: 1.23.0
description: Writes the requirements contract for a project under docs/specs/ from raw input - an idea, meeting notes, a transcript, a PRD, legacy docs or a codebase - in the user's language. Stable FR IDs, Given/When/Then acceptance criteria, flagged assumptions and open issues, a one-page confirmation sheet a PO or client answers yes/no/change, and a JSON index agents read instead of whole documents. Never invents a requirement. Research, strategy and docs repos get a lighter contract. Use when requirements must be written, confirmed, updated or standardized - "build specs", "tạo specs", "viết tài liệu phân tích yêu cầu", "要件定義を作成して", or the same in any language. Not for building the .claude agent harness (harness-bootstrap), digesting documents into a knowledge base, or writing code or ADRs.
allowed-tools: Bash(python:*), Bash(python3:*), Read, Write, Edit, Grep, Glob, AskUserQuestion, Agent
---

# Spec builder

Produces the requirements contract: linked, numbered sections under `docs/specs/`, traceable from
user story to feasibility row, with no invented requirement in them.

**The sections are real files.** `scripts/scaffold.py` installs them from `assets/specs/` with their
headings, tables, Mermaid scaffolds and inline authoring notes. Your job is the content and the
judgment - elicitation, the FR list, priorities, security posture, feasibility. Never hand-write a
template's shape.

**Not every project gets every section.** The core is always installed: `README`, `01-overview`,
`03-glossary`, `05-functional-requirements`, `07-non-functional-requirements`,
`11-assumptions-constraints`, `13-revision-history`. The rest are selected by what the material
contains; an empty section erodes trust in the filled ones. Section numbers never shift. A repo
whose product is not code gets the **light contract** instead: README, 05, 11 and 13, each item an
`FR-nn` with `Done when` criteria.

## The rule that governs everything

**Never invent a requirement.** Anything a stakeholder did not state and the source does not clearly
imply goes to section 11 as an assumption (`AS-nn`) or open issue (`OI-nn`) and is flagged in the
final summary. Why, and the tell that you are about to do it:
[`reference/elicitation.md`](reference/elicitation.md).

## Procedure

**1. Read the sources** (when the user brought files). `scripts/route_sources.py <files-folders-urls>
-o plan.json` picks a reader per source; `scripts/ingest.py` executes the plan. Show the plan first -
one line per source (file -> reader, or UNREADABLE -> why and the fix) - then read; report nothing
else until the final summary. **An unreadable source becomes an `OI-nn` in section 11** naming the
file and the fix, never a silent gap. Readers, overrides and limits:
[`reference/source-routing.md`](reference/source-routing.md).

**2. Elicit** - [`reference/elicitation.md`](reference/elicitation.md). Infer *structure*, ask for
*decisions*: priorities, permission scope, NFR targets, volumes and security posture are always
asked. One `AskUserQuestion` call per batch; skip anything the user or the sources already answered.

**3. Confirm the FR list and the sections** - one gate, before writing anything else. Show the FR
list with proposed MoSCoW priorities, the roles, and the open issues so far. Full contract only:
recommend each optional section when the material shows it is real (stakeholder map -> 02, process
handoffs -> 04, roles with scopes -> 06, owned persistent data -> 08, external systems -> 09,
screens -> 10, buildability risk -> 12, a design system -> 14) with elicitation's setup batch. Then
write `<target>/docs/specs/.sections.json`: every optional section in `selected` or `excluded`
exactly once, each with a one-line reason. The scaffolder refuses to run without it, on an empty
reason, or when it contradicts `vars.json`. Everything downstream derives from this gate.

**4. Scaffold.**

```bash
python scripts/scaffold.py --target <repo> --vars vars.json --dry-run   # review first
python scripts/scaffold.py --target <repo> --vars vars.json
```

```json
{
  "vars": {"PROJECT_NAME": "...", "PROJECT_SLUG": "...",
           "PROJECT_PURPOSE": "one line, the user's language", "DOC_OWNER": "..."},
  "flags": ["ai", "ui", "db", "flows", "access", "integration", "feasibility"]
}
```

- **Purpose flags**, shared with harness-bootstrap: `purpose_code`, `purpose_research`,
  `purpose_strategy`, `purpose_docs`. A non-code purpose without `purpose_code` scaffolds the light
  contract, needs no `.sections.json`, and refuses section flags. None means the full set.
- **Section flags** (step 3): `stakeholders`, `flows`, `access`, `db` (08), `integration`, `ui` (10),
  `feasibility`, `design` (14).
- **Content flags**: `ai` switches on the AI/human boundary in 05, the untrusted-content NFRs in 07
  and model feasibility in 12; `ui` and `db` also gate blocks inside other sections. Set only what is
  true.

The scaffolder **never overwrites a file**: `ADDED`, `KEPT` (identical) or `CONFLICT`. CONFLICT is
the reconciliation queue - resolve each by hand, never delete what the user wrote. An unresolved
`{{VAR}}` fails the run.

**Module form**, when the product has real module boundaries or the user asks for one module's spec
("the spec for billing" -> code `BLG`): `--module BLG:billing --module CAT:catalog`. Every ID that
module defines carries its code (`FR-BLG-01`); bare IDs inside a module folder are forbidden. Layout
and ID rules: [`reference/writing-rules.md`](reference/writing-rules.md).

**5. Fill**, section by section, following the inline `<!-- -->` notes and
[`reference/writing-rules.md`](reference/writing-rules.md) (read it first; it has the folder split
rule). Once 05 is confirmed, independent sections (02, 04, 09, 10) may go to agents dispatched in
ONE message; check their IDs and links against 05 before accepting. 05, 07 and 12 stay in the main
session - they carry the judgment and are the three most often thinned out:

- **05** - every FR observable, anchored `{#fr-nn}`, with input/output, business rules (`BR-nn` with
  a source) and acceptance criteria including a negative case; then UC-xx, US-xx and the
  traceability matrix.
- **07** - security NFRs are **mandatory and never "TBD"**: classification, encryption at rest and in
  transit, access-control model, secret management, and - if user content reaches an LLM -
  prompt-injection handling and provider retention. Undecided means an OI with an owner and a date.
  Why: [`reference/ba-standards.md`](reference/ba-standards.md).
- **12** (when selected) - every FR with Yes / Partial / No and a reason. Partial and No are the most
  valuable output of this skill.

**6. Verify and confirm.** `python .claude/scripts/spec-check.py --write` (add `--lang ja` for a
Japanese reader) regenerates `docs/specs/confirmation.md` (the page the PO answers yes / no /
change) and `docs/specs/index.json` (what agents read first), then checks IDs, criteria, open
issues and staleness. Fix every FAIL, then the quality gate below. Hand the sheet over with the open
issues. When it comes back, re-run `--write` (replies are kept), fold each `change` in through
`/spec-ingest`, and set **Status**: Confirmed on each yes with one revision row.

Then, if the harness scripts are installed, `python .claude/scripts/docs-graph.py --check` lists
orphan IDs - name each as unstarted work or a dead reference.

**7. Hand off.** Offer to invoke `harness-bootstrap` through the `Skill` tool with `FR_LIST` (05's FR
IDs, verbatim, in order) and `GLOSSARY_SEED` (03's terms); state the handoff in words without the
tool. The spec is its input contract: 05 clusters into the dev roster, 08 sets `db`, 10 sets `ui`, 07
sets `ai` and deny strictness, 12 seeds the Phase 1 backlog (ba-standards.md Part 3). If the full
docs workspace exists, seed once 03 and 05 are filled: one `docs/requirements/PRD-FR-NN-<slug>.md`
stub per FR linking back to 05's anchor, `docs/context/glossary.md` from 03,
`docs/context/business-rules.md` from 05's BR tables. **Seed, do not duplicate** - the spec stays
the source of truth.

## Living specs

- **`/spec-ingest <source>`** folds new input into existing sections: statement-by-statement diff,
  conflicts surfaced never overwritten, IDs appended never renumbered, one revision row. Follow it
  even when the command file is not installed.
- **`/spec-retract <source|ID|claim>`** traces what a bad source touched, converts unsupported
  statements to `OI-nn`, marks withdrawn IDs in place, and blocks affected tasks.
- To add a section later, move it from `excluded` to `selected` in `.sections.json` with the reason
  that changed, set its flag, and re-run `scaffold.py`.

A confirmed FR then enters the agentic loop with its criteria as the oracle; most changes need no
spec work at all. The step table and the proportion rule:
[`reference/agentic-loop.md`](reference/agentic-loop.md). The standards this synthesizes (ISO/IEC/IEEE
29148, ISO/IEC 25010, BABOK, OWASP ASVS and LLM Top 10) and their limits: `ba-standards.md`.

## Quality gate

`spec-check.py` exits 0 first. Then what it cannot decide:

- [ ] Every selected section exists with at least one filled block (compare `docs/specs/` against
      `.sections.json`); any `AS-`/`OI-`/`CO-` ID implies section 11 defines it.
- [ ] No blank table cell and no bare `TBD` (grep `\|\s*\|` and `TBD`) unless the cell reads
      `<unknown - OI-nn>`; section 07's security subsections are all filled.
- [ ] When both sections are selected: every FR appears in 12; 10's FRs are a subset of 05's and
      every user-facing FR names a screen; every component in 10 has a `DS-nn` row in 14; every role
      in 06 exists in 03 and every entity in 06 in 08.
- [ ] Every internal link resolves, including into split-section folders.
- [ ] Every FR and security NFR traces to a source line you can name - otherwise it belongs in 11.
      Every assumption has its impact-if-false, every open issue an owner, every unreadable source
      an `OI-nn`.
- [ ] The final summary lists every OI, AS, Partial/No, and every NFR target you proposed rather
      than received.
- [ ] IDs, codes, filenames and enum values are English whatever the prose language; no generation
      date or timestamp; Mermaid labels double-quoted; no emoji; lists use `-`.

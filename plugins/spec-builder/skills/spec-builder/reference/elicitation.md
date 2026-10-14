# Elicitation

How to get the inputs out of whatever the user actually brought - rarely a tidy brief.

## The one rule everything else serves

**Never invent a requirement.**

Anything the source material does not state and does not clearly imply goes to
`11-assumptions-constraints.md` - an assumption (AS-nn) if you proceed on it, an open issue (OI-nn)
if you do not - and is flagged in the final summary. It never appears in 05 or 07 as though someone
had decided it.

Why: a missing requirement is *visible* - someone asks, and it costs one conversation. A plausible
invented one is *invisible* - estimated, built, tested against itself, treated as settled by every
downstream document, and found in UAT. It is the most expensive BA error and the one an LLM is most
prone to. The tell: you are writing a requirement that reads well and that nobody said. Move it to 11.

## What to ask vs what to infer

| Input | Infer it | Ask |
|-------|----------|-----|
| System name, one-line purpose | Only if the source states it | If ambiguous |
| Problem statement | From the source, quoting where possible | If the source only describes a solution, ask what problem it solves |
| Feature list -> FR candidates | Yes - every capability the source names | Priorities (MoSCoW). Never assign them yourself |
| Priorities | No | Always. Priority is a stakeholder's answer, not a builder's |
| Roles and permissions | Role names, yes | The scope (Own/Team/All), the authorization model (RBAC vs ABAC) if it is not obviously RBAC, and - if the system is multi-tenant - the isolation boundary and any break-glass admin path. Almost none of this is stated or guessable |
| Data entities and fields | From the source and the flows | Cardinalities, retention period and deletion/erasure rights, backup/restore expectation, classification |
| NFR targets | No | Always. A number you made up is a fabricated requirement - availability/uptime, RPO/RTO, and observability expectations are the three most often skipped; do not let "performance" stand in for all three |
| Security posture | No | Ask which regime actually binds this project - GDPR/CCPA, HIPAA/PCI-DSS, SOC2/ISO 27001, or (a common pair for this practice's client base) Japan's APPI (個人情報保護法) or Vietnam's Decree 13 - and if nobody knows, that is an OI with a named owner |
| Tech stack | Only if the source states or the repo shows it | If undecided, it is an open issue - not a default |
| Product locale support | No | Languages served to users, RTL layout, currency/date-format convention - a business decision, distinct from the output-language row below and never inferred from it |
| Legacy system replacement | Only that one exists, if the source says so | The cutover plan (migrate once, dual-run, or a hard switch) and any data-migration mapping - ask, never infer an approach |
| Volumes and growth | No | Ask. An order-of-magnitude guess here is a design decision |
| Output language | From the user's own language | Only if genuinely unclear |

**Infer structure, ask for decisions.** A "submit for approval" flow implies an approver role -
structure. Who the approver is, whether they may approve their own submission, what happens when
they are on leave - decisions.

## Routing by input type

Classify the source first; the route decides how much you ask and in what order. Every route ends
at the same gate: the confirmed FR list plus the section selection.

| Source | Route | Reason |
|--------|-------|--------|
| A one-line idea | Guided elicitation, all four batches | Nothing can be inferred; asking is the work |
| Transcript or meeting notes | Extraction pass, then confirm the FR list | The facts exist; the risk is over-reading them |
| An existing PRD or spec | Map onto the sections, gaps become the questions | Structure exists; security, data, and feasibility usually do not |
| Legacy doc pile | Per-doc mapping table, then reconcile | Multiple sources disagree; the diff is the finding |
| Existing codebase | Read schema and route layer as evidence, ask intent | Code shows behaviour, never intent |
| Existing partial specs | Reconcile mode - diff, never overwrite | `/spec-ingest`'s discipline applies from the first read |

## Read the sources first

When the user hands over files, route and read them **before** the first question - a question
whose answer sat in a PDF you skimmed costs the user's trust. The commands, the reader table, the
unreadable-source rule and the limits are in [`source-routing.md`](source-routing.md). Relay the plan
as one line per source; it is the only narration this step gets, and the next thing the user sees
is the first question batch. A docs-to-knowledge class skill, if installed, does more for a large,
diagram-dense pile; delegating to it is legitimate, reading nothing is not.

## By input type

### A one-line idea

Expect to ask the most; never compensate by filling gaps yourself. Ask in batches (max 4 questions
per `AskUserQuestion` call), in this order:

1. Who uses it, and what do they do today instead?
2. What are the three things it must do? (These become the Must FRs.)
3. Who may see whose data? (Roles + scope.)
4. What already exists that it must talk to? (Integrations, identity, the system of record - and what
   happens to the flow if each one is unavailable.)

Then produce a *draft* FR list and get it confirmed before writing anything else.

### A transcript or meeting notes

The richest input, and the one most likely to be over-read:

- Extract only what was **said**. "We'll probably need approvals" is an open issue, not FR-03.
- Note who said each thing - it fills the `Source` column of the business rules and the `Owner`
  column in 11. A rule with no source is a guess.
- Disagreement in the room is an OI with both versions recorded, never an average of the two.
- Decisions *deferred* in the meeting are the highest-value open issues. Do not quietly resolve them.

### An existing PRD or spec

- Map it onto the numbered sections without restructuring or "improving" its content. Preserve the
  original ID if it has one and note the mapping.
- The gaps are the deliverable: security NFRs, data classification, permission scope, integration
  failure behaviour, feasibility. Fill 06, 07, 09, and 12 by asking, not by inferring from the FRs.
- Where the PRD contradicts itself, both readings go in 11 as an OI.

### Legacy docs and an existing codebase

- Code is evidence of behaviour, not of intent: `status IN ('A','B','C')` says the states exist, not
  which are used or correct.
- Read the schema for 08 and the route/permission layer for 06.
- Anything the code does that no stakeholder mentioned is an OI: "the system currently does X - is
  this a requirement or an accident?"
- Anything a stakeholder wants that the code cannot support is a `Partial` or `No` row in 12.
- A replacement or coexisting legacy system: the cutover plan (migrate once, run in parallel, or a
  hard switch) and any data-migration mapping are business decisions - ask; undecided, it is an OI
  blocking every FR that depends on cutover.

## Ask in the user's language

**Infer the language from how the user wrote to you, and ask every question in it** - question text,
option labels and option descriptions. Default to English only when the input is too short or too
mixed to tell. This is separate from the output-language choice in the setup batch below: that one
is a decision about the document; the interview language is inferred, never asked. IDs, codes,
filenames, entity and enum names stay English, per [`writing-rules.md`](writing-rules.md).

## Batching questions

Closed-choice questions (output language, security posture category - a small set of named options)
go through **`AskUserQuestion`**: max 4 options per question, up to 4 questions per call, the
recommended option first labeled `"(Recommended)"` only where one genuinely exists - most
elicitation questions have no safe recommendation. Open-ended questions (a name, a number, a
description) stay plain chat. Group each batch so one person can answer it in one sitting: do not
mix a p95 latency target with "who signs this off".

Suggested batches:

1. **Scope**: purpose, must-have features, explicit non-goals, output language.
2. **People**: user groups, roles, authorization model and tenancy isolation, who decides, who signs off.
3. **Data and systems**: entities, retention and deletion expectations, volumes, what it integrates
   with (and the fallback if each is down), what identity provider, product locale support.
4. **Constraints**: security and compliance obligations (name the regime, not just "secure"),
   deadlines, budget, stack constraints.

## The setup batch - language, sections, profile

One `AskUserQuestion` call, before scaffolding (skip any part the request already answered):

- **Output language** (single choice): Vietnamese / Japanese / English / other. Prose follows it;
  codes and IDs stay English per writing-rules.md.
- **Sections to create** (multi-select): the core is fixed and not offered (README, 01, 03, 05, 07,
  11, 13 - section 11 is core because every `AS-nn`/`OI-nn` needs its registry). Offer each
  optional section with a one-line description, pre-selecting the ones the source material shows to
  be real: stakeholder map -> 02, process handoffs -> 04, roles with scopes -> 06, owned persistent
  data -> 08, external systems -> 09, screens -> 10, buildability risk -> 12, an existing or
  planned design system -> 14. Recommend, never force: an unselected section can be added later by
  re-running the scaffolder.
- **Standards profile** (single choice): full synthesis (Recommended - the complete quality gate)
  / lightweight (core sections, gate limited to completeness + grounding; traceability checks run
  only over what exists). Lightweight changes the gate's breadth, never the never-invent rule.

**The batch's output is a file, not a memory.** Write `<target>/docs/specs/.sections.json` before
scaffolding: every optional section in `selected` or `excluded`, exactly once, each with a one-line
reason naming what in the source material decided it (or that the user chose it outright); core
sections in neither. `scaffold.py` refuses to write without it, with an empty reason, or when
`selected` disagrees with `vars.json`'s flags; the schema and refusal messages live in
`scripts/scaffold.py`. The selection is echoed in the confirmation gate and verified by the quality
gate.

An unanswered question is a result: an OI with an owner and a needed-by date. A spec set with no
open issues is almost always a fabricated one.

## Express elicitation - pacing, not shortcuts

A user in a hurry can compress the *process*, never the *content*. There is no defaults table -
business facts are never guessed. What can move faster:

- **Order and depth, not section count.** Draft 01-05 from what the user gave before opening a batch
  for 06+, so the FR list is visibly forming.
- **Fewer, denser batches.** Merge the four batches into 2-3 where the source already answers most
  of one, asking only the gaps - never silently.
- **A labeled shallow first pass.** Reach the FR list and confirmation gate fast, record 06/07/09/12
  as "pending detail" open issues, and schedule a second pass - never a guess standing in for it.

Priorities, NFR targets, security posture, and volumes are asked at every pace.

## The confirmation gate

Before writing sections 02-14, echo back the FR list with *proposed* MoSCoW priorities, the roles,
and the open issues collected so far. Get an explicit yes - it catches an invented requirement while
it is still one line.

## Final summary to the user

Always surface, in the last message:

- every OI, with its owner and what it blocks,
- every AS you proceeded on, and what breaks if it is false,
- every `Partial` and `No` in the feasibility table,
- any security NFR whose target you proposed rather than received.

They cannot correct what you did not tell them you assumed.

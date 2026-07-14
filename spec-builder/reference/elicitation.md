# Elicitation

How to get the inputs out of whatever the user actually brought - which is rarely a tidy brief.

## The one rule everything else serves

**Never invent a requirement.**

Anything the source material does not state and does not clearly imply goes to
`11-assumptions-constraints.md` - as an assumption (AS-nn) if you are proceeding on it, or as an
open issue (OI-nn) if you are not - and is flagged to the user in the final summary. It never
appears in 05 or 07 as though someone had decided it.

This is not pedantry. A missing requirement is *visible*: work stalls, someone asks, it gets
answered, and the cost is one conversation. A plausible invented requirement is *invisible*: it is
estimated, built, tested against itself, and every downstream document - the feasibility table, the
PRD, the task board, the test plan - treats it as settled. It surfaces in UAT, in front of the one
person who always knew it was wrong. It is the most expensive error available to a BA, and it is
the one an LLM is most prone to, because filling a gap with something plausible is exactly what a
language model is for.

The failure mode has a tell: you find yourself writing a requirement that reads well and that
nobody said. Stop, and move it to 11.

## What to ask vs what to infer

| Input | Infer it | Ask |
|-------|----------|-----|
| System name, one-line purpose | Only if the source states it | If ambiguous |
| Problem statement | From the source, quoting where possible | If the source only describes a solution, ask what problem it solves |
| Feature list -> FR candidates | Yes - every capability the source names | Priorities (MoSCoW). Never assign them yourself |
| Priorities | No | Always. Priority is a stakeholder's answer, not a builder's |
| Roles and permissions | Role names, yes | The scope (Own/Team/All) - almost never stated, almost never guessable |
| Data entities and fields | From the source and the flows | Cardinalities, retention, classification |
| NFR targets | No | Always. A number you made up is a fabricated requirement |
| Security posture | No | Ask, and if nobody knows, that is an OI with a named owner |
| Tech stack | Only if the source states or the repo shows it | If undecided, it is an open issue - not a default |
| Volumes and growth | No | Ask. An order-of-magnitude guess here is a design decision |
| Output language | From the user's own language | Only if genuinely unclear |

The distinction that matters: **infer structure, ask for decisions.** You may derive that a
"submit for approval" flow implies an approver role - that is structure. You may not derive who the
approver is, whether they may approve their own submission, or what happens if they are on leave -
those are decisions.

## By input type

### A one-line idea

Expect to ask the most. Do not compensate by filling the gaps yourself - a spec set built on one
line plus your imagination is thirteen documents of fiction with a table of contents.

Ask in batches (max 4 questions per `AskUserQuestion` call), in this order:

1. Who uses it, and what do they do today instead?
2. What are the three things it must do? (These become the Must FRs.)
3. Who may see whose data? (Roles + scope.)
4. What already exists that it must talk to? (Integrations, identity, the system of record.)

Then produce a *draft* FR list and get it confirmed before writing anything else. Everything after
05 is derived from it, so a wrong FR list costs twelve documents.

### A transcript or meeting notes

The richest input, and the one most likely to be over-read. Discipline:

- Extract only what was **said**. "We'll probably need approvals" is an open issue, not FR-03.
- Note who said each thing - it populates the `Source` column of the business rules table and the
  `Owner` column in 11. A rule with no source is a guess.
- Disagreement in the room is a finding, not noise. Two stakeholders describing the same process
  differently is an OI with both versions recorded, not an average of the two.
- Decisions that were *deferred* in the meeting are the highest-value open issues in the document.
  They are also the ones a model most wants to quietly resolve. Do not.

### An existing PRD or spec

- Map it onto the 13 sections; do not restructure its content, and do not "improve" a requirement
  while moving it. Preserve the original ID if it has one and note the mapping.
- The gaps are the deliverable. A PRD almost always has functional requirements and almost never
  has: security NFRs, data classification, permission scope, failure behaviour for integrations, or
  a feasibility assessment. Fill 06, 07, 09, and 12 by asking - not by inferring from the FRs.
- Where the PRD contradicts itself, both readings go in 11 as an OI. Choosing one silently is the
  invented-requirement failure wearing a disguise.

### Legacy docs and an existing codebase

- The code is evidence of behaviour, not of intent. `status IN ('A','B','C')` tells you the states
  exist; it does not tell you which are still used, and it certainly does not tell you which are
  correct.
- Read the schema for 08 and the route/permission layer for 06. These are the two places where
  reality most reliably beats documentation.
- Anything the code does that no stakeholder mentioned is an OI: "the system currently does X - is
  this a requirement or an accident?" That question has surfaced more scope than any other in this
  document.
- Anything a stakeholder wants that the code cannot support is a `Partial` or `No` row in 12.

## Batching questions

Use `AskUserQuestion`, at most 4 questions per call, grouped so each batch is answerable by one
person in one sitting. Do not interleave "what is your NFR target for p95 latency" with "who signs
this off" - they have different audiences and the mixed batch stalls on whichever is harder.

Suggested batches:

1. **Scope**: purpose, must-have features, explicit non-goals, output language.
2. **People**: user groups, roles, who decides, who signs off.
3. **Data and systems**: entities, volumes, what it integrates with, what identity provider.
4. **Constraints**: security and compliance obligations, deadlines, budget, stack constraints.

If the user cannot answer a batch, that is a result: each unanswered question becomes an OI with an
owner and a needed-by date. A spec set full of well-formed open issues is a good deliverable. A
spec set with no open issues is almost always a fabricated one - real projects have unknowns, and a
document that shows none has hidden them.

## The confirmation gate

Before writing sections 02-13, echo back:

- the FR list with proposed MoSCoW priorities (marked as *proposed*),
- the roles,
- the open issues you have already collected.

Get an explicit yes. This is the cheapest checkpoint in the whole procedure, and it catches the
invented requirement while it is still one line rather than one section.

## Final summary to the user

Always surface, in the last message:

- every OI, with its owner and what it blocks,
- every AS you proceeded on, and what breaks if it is false,
- every `Partial` and `No` in the feasibility table,
- any security NFR whose target you proposed rather than received.

The user's job is to correct these. They cannot correct what you did not tell them you assumed.

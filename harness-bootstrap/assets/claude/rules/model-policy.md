# Model policy

Loaded in every session, deliberately. security-privacy.md governs what must never leave the repo at
all. This file governs everything else: which model may SEE which data, and which seat runs on which
model. Both questions are answered here, in one place, because they change together and they change
often.

## Data classification

Every task carries the classification of the highest-classified data it touches - source, fixtures,
logs, screenshots, pasted excerpts, tool output. Classify BEFORE dispatch. Classifying after the fact
is not classification, it is a post-mortem.

| Class | What it is | May be processed by |
|---|---|---|
| Public | Already published, or publishable today with no approval: open-source code, public docs, marketing copy | {{MODEL_PUBLIC}} |
| Internal | Not secret, but not ours to publish: private source, internal designs, ticket text, non-sensitive telemetry | {{MODEL_INTERNAL}} |
| Confidential | Damaging if disclosed: unreleased product work, contracts, pricing, security findings, customer names, anything under NDA | {{MODEL_CONFIDENTIAL}} |
| Restricted | Regulated or existential: production PII, health or payment data, credentials, key material, {{PII_OR_DATA}} | {{MODEL_RESTRICTED}} |

The failure this table prevents: without it, classification is decided per-prompt by whoever opened
the terminal, and the decision is invisible - a Restricted excerpt pasted into a Public-tier model
leaves no trace anywhere except the provider's logs. The table makes the decision explicit, reviewable
before the fact, and identical for every agent.

Rules that come with the table:

- **Unclassified means Confidential** until someone classifies it. The failure mode of guessing is
  asymmetric: guessing too high wastes a little money, guessing too low is a disclosure.
- **Restricted data does not cross the organisation's boundary.** Not to a hosted API, not to a
  reviewer agent, not "just to summarise the schema".
- **A blank cell is a STOP, not a default.** If no approved or self-hosted model exists for a class,
  the work does NOT get delegated to an agent. It goes to a human. The absence of an approved model
  is an answer, and the answer is "not by an agent".
- An agent that cannot tell which class its input is in stops and asks. It does not proceed at the
  lowest plausible class.

## Seat tiers - the one table a model swap has to touch

Agents declare a **seat tier**, not a model. The tier is a statement about the work; the model is an
implementation detail of the tier.

| Seat tier | The work | Seats (as fielded) | Model |
|---|---|---|---|
| Judgment | Consequential calls under incomplete information, or catching another agent's mistakes: planning, decomposition, root-cause, review gates | `orchestrator`, `debugger`, `code-reviewer`, `security-reviewer`, `merge-manager` | `opus` |
| Implementation | Producing code, tests, docs, or structured output against a settled contract | the `<domain>-dev` seats, `qa-test`, `data-modeler`, `db-engineer`, `devops`, `ba-analyst`, `spec-guardian` | `sonnet` |
| Mechanical | Low-judgment, high-volume, fixed procedure: archiving, summarising an append-only log, running a pinned pipeline | `history-tracker`, `db-seeder`, `sast-runner` | `haiku` |

Seats this project did not field carry no row; the tier is the contract, the names are just this
roster's instantiation of it. A new agent is classified by the questions in the middle column, not by
analogy to the closest-sounding name.

**Changing provider, or moving a seat between tiers, is an edit to THIS table - never a sweep across
sixteen agent files.** That is the entire point of the indirection. Model choice is the single thing
in this harness most likely to change: a cheaper model lands, a provider's terms change, a regulator
rules a region out. A roster that hardcodes a model name in every agent body cannot survive that
without a sixteen-file diff that nobody reviews properly, and every one of those files is prompt-cache
prefix content (cost-model.md), so the sweep also cold-misses every cache it touches.

Precedence, and it is not negotiable: **classification beats tier.** If a task's class does not permit
the tier's model, the task is re-routed to a permitted model, or it is not delegated at all. A
judgment seat does not get an exception because the problem is hard.

## Residency and retention

- Processing region: {{DATA_RESIDENCY}}. A provider that cannot commit to it is not approved for
  Internal or above, whatever its benchmark scores.
- Any provider processing Confidential or Restricted data must have a **stated retention posture** -
  written down, in `docs/context/tool-changelog.md`, with the class it was approved for. Zero
  retention or short retention where the class demands it; "we think they don't train on it" is not a
  posture.
- No provider is added to the harness (an MCP server, a gateway, a third-party skill that calls out)
  until that row exists. The failure mode: an agent quietly gains an egress nobody approved, and the
  first person to notice it is a regulator.

## What never goes to any model, at any tier

Live secrets and credentials, key material, production PII, and customer data not covered by a DPA.
This is not restated here - security-privacy.md ("Secrets", "Retention and egress") and
agent-guardrails.md ("Secrets", "Personal and sensitive data") own it. This file adds only the model
dimension: no tier, no self-hosted deployment, and no "the model is on our own hardware" makes any of
that list acceptable input.

## Prompts and transcripts are artifacts

An agent's prompt and its output are records, not ephemera. The session logs in `docs/tasks/` are
committed text; the run archive under `.claude/state/history/` is on disk and usually backed up even
though it is gitignored.

- **A transcript inherits the classification of the highest-classified data it touched.** A prompt
  that quotes a Confidential contract clause produces a Confidential transcript, and it is stored and
  reviewed as one.
- Which means the cheap way to keep the archive Internal is to keep the prompts Internal: reference
  the file, do not paste the record.
- A transcript that would be Restricted must not be written to a committed artifact at all. If the
  work needs Restricted data in the prompt, see the STOP rule above - it was never an agent's task.

## Enforcement: the classification table is policy, the deny list is the control

Everything above is a rule, and a rule is context, not configuration. Claude Code loads it and tries
to follow it; it is not a hard gate. A rule alone therefore does not give you model sovereignty -- it
gives you a request for model sovereignty.

The control that makes it real works on the **data**, not on the model. Restricted material is denied
at the read boundary in `.claude/settings.json`:

```json
"permissions": {
  "deny": [
    "Read(data/restricted/**)",
    "Read(**/*.phi.json)"
  ]
}
```

(Illustrative. The real entries for this repository are in `.claude/settings.json` -- read them
there, and treat that file as the authoritative statement of what agents cannot see.)

**What an agent cannot read, it cannot send to any model, on any provider.** That is enforced by the
harness before the tool call happens, so it holds regardless of which model is driving, and it holds
even if the model ignores every word of this rule.

Consequences worth stating plainly:

- If Restricted data has no path you can name, this control cannot be applied, and the classification
  table is advisory only. Say so out loud rather than assuming you are covered.
- Work that genuinely requires Restricted data therefore does not get delegated to an agent at all.
  It goes to a human, or to an approved pipeline running inside the boundary. That is the intended
  outcome, not a limitation to route around.
- Do not "temporarily" remove a deny entry to unblock an agent. That is the whole control.

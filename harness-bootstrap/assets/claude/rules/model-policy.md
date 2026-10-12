# Model policy

Loaded in every session, deliberately. security-privacy.md governs what must never leave the repo at
all. This file governs everything else: which model may SEE which data. Which seat runs on which model is
in model-tiers.md, loaded when an agent file or the settings change.

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

## Seat tiers and enforcement

Which seat runs on which model, how a model swap is recorded, and why the deny list in
`.claude/settings.json` - not this file - is the control: `model-tiers.md`, which loads when an
agent file or the settings are touched. The one line that binds every session: **classification
beats tier.** A task whose class does not permit a seat's model is re-routed or not delegated.

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

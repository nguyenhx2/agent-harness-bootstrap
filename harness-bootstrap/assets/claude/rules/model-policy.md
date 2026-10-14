# Model policy

Loaded in every session, deliberately: which model may SEE which data.

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

Without the table, classification is decided per prompt and invisibly. Rules that come with it:

- **Unclassified means Confidential** until someone classifies it. Guessing too high wastes a
  little money; guessing too low is a disclosure.
- **Restricted data does not cross the organisation's boundary.** Not to a hosted API, not to a
  reviewer agent, not "just to summarise the schema".
- **A blank cell is a STOP, not a default.** If no approved or self-hosted model exists for a class,
  the work does NOT get delegated to an agent. It goes to a human. The absence of an approved model
  is an answer, and the answer is "not by an agent".
- An agent that cannot tell which class its input is in stops and asks. It does not proceed at the
  lowest plausible class.

**Classification beats tier.** A task whose class does not permit a seat's model is re-routed or
not delegated. Seat-to-model mapping and swaps are in `model-tiers.md`.

## Residency and retention

- Processing region: {{DATA_RESIDENCY}}. A provider that cannot commit to it is not approved for
  Internal or above, whatever its benchmark scores.
- Any provider processing Confidential or Restricted data must have a **stated retention posture** -
  written down, in `docs/context/tool-changelog.md`, with the class it was approved for. Zero
  retention or short retention where the class demands it; "we think they don't train on it" is not a
  posture.
- No provider is added to the harness (an MCP server, a gateway, a third-party skill that calls out)
  until that row exists - otherwise an agent quietly gains an egress nobody approved.
- Secrets, key material and production PII go to no model at any tier, self-hosted included
  (agent-guardrails.md owns that list).

## Prompts and transcripts are artifacts

Session logs in `docs/tasks/` are committed; the run archive in `.claude/state/history/` is on disk.

- **A transcript inherits the classification of the highest-classified data it touched.** Keep
  prompts Internal by referencing the file, not pasting the record.
- A transcript that would be Restricted is never written to a committed artifact - per the STOP
  rule, it was never an agent's task.

---
paths:
  - ".claude/agents/**"
  - ".claude/settings.json"
---

# Model tiers and enforcement

Split out of model-policy.md so it loads only when it can matter: when an agent file or the
settings are being changed. model-policy.md keeps what every session needs - the data
classification and the STOP rule.

## Seat tiers - the decision record for a model swap

Each agent file hardcodes its `model:` in frontmatter (the runtime reads it there). This table is
the DECISION RECORD behind those values: the tier states what kind of work the seat does, and the
tier - not analogy or habit - decides which model each seat gets.

| Seat tier | The work | Seat (`effort:`) | Model |
|---|---|---|---|
| Judgment | Planning, decomposition, dispatch | `orchestrator` (high) | `opus` |
{{#IF_PURPOSE_CODE}}| Judgment | Root cause under incomplete information | `debugger` (xhigh) | `opus` |
{{#IF_SOLO_REVIEW}}| Judgment | Review gate, quality and security in one pass | `reviewer` (high) | `opus` |
{{/IF_SOLO_REVIEW}}{{^IF_SOLO_REVIEW}}| Judgment | Review gate, code quality | `code-reviewer` (high) | `opus` |
| Judgment | Review gate, security | `security-reviewer` (high) | `opus` |
{{/IF_SOLO_REVIEW}}| Implementation | Code against a settled contract | `<domain>-dev` (medium) | `sonnet` |
{{#IF_TESTS}}| Implementation | Tests against stated criteria | `qa-test` (medium) | `sonnet` |
{{/IF_TESTS}}{{#IF_DB}}| Implementation | Schema and data model | `data-modeler` (high) | `sonnet` |
{{#IF_DB_ENGINEER}}| Implementation | Migrations and queries | `db-engineer` (medium) | `sonnet` |
{{/IF_DB_ENGINEER}}{{#IF_DB_SEEDER}}| Mechanical | Synthetic seed data | `db-seeder` (low) | `haiku` |
{{/IF_DB_SEEDER}}{{/IF_DB}}| Implementation | CI, build and infrastructure | `devops` (medium) | `sonnet` |
| Implementation | Requirements and specs | `ba-analyst` (high) | `sonnet` |
| Implementation | Scope and acceptance-criteria lock | `spec-guardian` (medium) | `sonnet` |
{{/IF_PURPOSE_CODE}}{{#IF_MERGE_GATE}}| Judgment | Serialized merges that must drop nothing | `merge-manager` (medium) | `opus` |
{{/IF_MERGE_GATE}}{{#IF_CHECKER}}| Judgment | Attacking claims, sources and reasoning in finished prose | `checker` (high) | `opus` |
{{/IF_CHECKER}}{{#IF_LONG}}| Judgment | Framing a decision and recommending an option | `strategist` (high) | `opus` |
| Implementation | Evidence with cited sources | `researcher` (medium) | `sonnet` |
{{/IF_LONG}}{{^IF_LONG}}{{#IF_PURPOSE_STRATEGY}}| Judgment | Framing a decision and recommending an option | `strategist` (high) | `opus` |
| Implementation | Evidence with cited sources | `researcher` (medium) | `sonnet` |
{{/IF_PURPOSE_STRATEGY}}{{^IF_PURPOSE_STRATEGY}}{{#IF_PURPOSE_RESEARCH}}| Implementation | Evidence with cited sources | `researcher` (medium) | `sonnet` |
{{/IF_PURPOSE_RESEARCH}}{{/IF_PURPOSE_STRATEGY}}{{/IF_LONG}}{{#IF_PURPOSE_DOCS}}| Implementation | Documents against an outline and a reader | `writer` (medium) | `sonnet` |
{{/IF_PURPOSE_DOCS}}{{#IF_LONG}}| Mechanical | Archiving the run history | `history-tracker` (low) | `haiku` |
{{/IF_LONG}}{{^IF_LONG}}{{#IF_AUDIT}}| Mechanical | Archiving the run history | `history-tracker` (low) | `haiku` |
{{/IF_AUDIT}}{{/IF_LONG}}{{#IF_AUDIT}}| Mechanical | Running a pinned scanner pipeline | `sast-runner` (low) | `haiku` |
{{/IF_AUDIT}}
Judgment: consequential calls under incomplete information, or catching another agent's mistakes.
Implementation: output against a settled contract. Mechanical: low-judgment, fixed procedure. The
effort in brackets is each seat's `effort:` line; change it here first, like the model.

Seats this project did not field carry no row; the tier is the contract, the names are just this
roster's instantiation of it. A new agent is classified by the tier definitions under the table, not by
analogy to the closest-sounding name.

**Changing provider, or moving a seat between tiers, starts as an edit to THIS table.** The
frontmatter sweep that follows is mechanical because the table says exactly which seats move; without
the table, a provider change becomes a judgment call repeated once per agent file, and nobody reviews
a many-file diff of judgment calls properly. Model choice is the single thing in this harness most
likely to change - a cheaper model lands, a provider's terms change, a regulator rules a region out -
so record the decision here first, then apply it to the `model:` lines it names. Each touched agent
file is prompt-cache prefix content, which is one more reason the sweep should be one
reviewed, deliberate change instead of drift.

Precedence, and it is not negotiable: **classification beats tier.** If a task's class does not permit
the tier's model, the task is re-routed to a permitted model, or it is not delegated at all. A
judgment seat does not get an exception because the problem is hard.

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

# Assessment: does this repo actually deliver the thesis?

The thesis this repo is built against:

> Models are commoditising and are a poor place to build durable advantage. The advantage moves to
> the **agent harness**, to **enterprise context**, and to **workflow integration**. Governance now
> has to cover **privacy, IP, and model sovereignty**. Do not position AI capability around *which
> model we use*; position it around the ability to turn **many models** into an agent system that has
> ROI, keeps data under control, and runs safely in production.

This document scores the repo against that, honestly, including where it falls short. It is written
to be argued with. If a claim below is not backed by a file or a runnable script in this repo, it is
marked as not delivered.

## Scorecard

| Pillar | Status | Evidence, or the gap |
|---|---|---|
| Models are commoditising | **Acknowledged and acted on** | `reference/cost-model.md` was rebuilt on current pricing. Opus 4.8 is **1.67x** Sonnet 5, not 5x. The old "cheap model everywhere except the review gate" advice was written for a 5x gap and is largely obsolete; the roster no longer relies on it. |
| Advantage is the harness | **Delivered, and falsifiable** | `eval/guardrail_eval.py` scaffolds a harness and fires 15 known-bad payloads at it: **15/15**. Every block is a shell script and an exit code. Swap Opus for Haiku and the result is byte-identical. The **safety floor is model-independent**, and that is a claim you can re-run rather than trust. |
| ROI | **Half delivered** | Cost is modelled per roster profile (`benchmark/model_cost.py`) and the harness's own overhead is measured (`benchmark/RESULTS.md`: read path -65%, write path -85%). **Value is not measured at all.** Cost-per-feature without value-per-feature is not ROI, and this repo does not pretend to compute the numerator. |
| Data under control (privacy) | **Delivered** | `security-privacy.md` (secrets, PII), enforced by `protect-secrets` hooks and settings deny rules, both tested. Audit mode makes product source technically read-only. |
| Governance: IP | **Delivered** | `ip-compliance.md`: dependency licence allow/deny by family, the AGPL-on-SaaS trigger, provenance risk on reproduced blocks, a runnable diff check for the reviewers. |
| Governance: model sovereignty | **Enforced for data at rest; advisory beyond it** | See below. Partially closed. |
| Many models -> one system | **Not delivered** | See below. This is the second largest gap. |
| Enterprise context | **Partial** | The docs tree, specs, ADRs, glossary, business rules and the task board are real and are wired into the agents. What is absent: any integration with the systems an enterprise actually runs on -- ticketing, SSO, a CMDB, an internal package registry. |
| Workflow integration | **Partial** | Slash commands, hooks, and a task board that survives compaction. No CI pipeline templates, no PR automation, no ticket sync. `devops` is a seat with no shipped pipeline. |

## Gap 1 - Model sovereignty: now enforced on data, still advisory on routing

**Status: partially closed.** The analysis below stands, and the fix it proposed has been
implemented -- read it, then read the resolution at the end.



`model-policy.md` defines a data-classification table (Public / Internal / Confidential /
Restricted) and binds each class to the models permitted to process it. The precedence rule is
right: **classification beats seat tier** -- if a task's data class does not permit the tier's model,
the work re-routes or it does not get delegated at all.

But that rule lives in `.claude/rules/`, which is **context, not configuration**. Claude Code's own
documentation is explicit about this: rules "shape Claude's behaviour but are not a hard enforcement
layer". So today, model sovereignty in this repo is enforced by the model's willingness to follow an
instruction. That is not sovereignty. That is a request.

The governance layer was honest about this rather than papering over it -- it deliberately shipped
**no** settings.json deny rule for classification, on the grounds that "sent Confidential text to a
hosted model" is not a distinguishable tool call, and claiming a deny rule enforced it would be
theatre. That reasoning is correct.

**What would actually close it**, and is the obvious next change: enforce on the *data*, not on the
*model*. If Restricted data lives at known paths, a `permissions.deny` entry on `Read(<those
paths>)` means the agent never obtains the data in the first place -- and what an agent cannot read,
it cannot leak to any model, on any provider. That converts sovereignty from an instruction into a
deterministic control, using exactly the mechanism the guardrail eval already proves works. It
requires the org to tell the bootstrap where its Restricted data lives, which is a question the
intake should be asking and currently is not.

### Resolution (implemented)

That control now ships. `.claude/settings.json` carries a `{{RESTRICTED_DENIES}}` slot at the head of
the deny list, the intake asks where Restricted data lives as glob patterns, and `model-policy.md`
states plainly that the classification table is the *policy* while the deny list is the *control*.

What is now genuinely enforced: **an agent cannot read Restricted paths, so it cannot send that data
to any model, on any provider, regardless of which model is driving or whether it read the rule.**
This uses the same mechanism the guardrail eval already proves works.

What is still advisory, and must not be oversold:

- **Routing itself.** Nothing prevents an agent from putting Confidential-but-readable text into a
  prompt to a model that the table does not permit. There is no tool call shaped like "sent this
  text to that provider", so there is nothing for a hook to intercept.
- **Data the org cannot locate.** If Restricted material has no nameable path, the deny list cannot
  cover it and the table is advice. The intake now forces that admission rather than letting it pass
  silently, but an admission is not a control.

So the honest claim is now: **this repo enforces model sovereignty at the data boundary, and governs
it by rule everywhere else.** That is a real improvement over "governs it by rule", and it is still
short of "enforces it".

## Gap 2 - "Many models" is aspirational; this is a single-vendor harness

The thesis asks for the ability to turn **many models** into an agent system. This repo runs on
Claude Code. Agent definitions are Claude Code frontmatter (`model:`, `effort:`, `tools:`,
`maxTurns:`). The `model:` field accepts `opus | sonnet | haiku | fable` -- four models from one
vendor.

So: **model tier is swappable. Model vendor is not.** Re-pointing this roster at a self-hosted Llama
or an Azure-hosted GPT is not a configuration change; it is a port.

Two things partially mitigate it, and neither is sufficient:

- `AGENTS.md` is the vendor-neutral document, and `CLAUDE.md` is a thin `@AGENTS.md` import. Other
  coding agents that read `AGENTS.md` get the rules. They do **not** get the hooks, the settings
  deny rules, or the permission model -- i.e. they get the advice and none of the enforcement. The
  file even says so.
- The seat-tier table in `model-policy.md` (judgment / implementation / mechanical -> model) is the
  right *shape* for portability: it is the one file a provider swap would edit, instead of a sweep
  across sixteen agent files. But it currently maps to Anthropic aliases, and nothing consumes it as
  an abstraction -- the agent files still name the model directly.

**What would close it:** make the tier the thing the agent declares, and generate the concrete
`model:` value from the tier table at scaffold time. The scaffolder already does exactly this kind
of substitution. That would make a vendor swap a one-file edit plus a re-run -- which is a real
portability claim rather than a rhetorical one. It is not done.

## Gap 3 - ROI has no numerator

The repo measures what the harness costs and what it saves. It does not measure what it produces.
`benchmark/model_cost.py` will tell you a feature costs about $2.38 on the default roster and about
$0.61 on an all-Haiku roster. It cannot tell you whether the Haiku feature is worth shipping.

That is the question that actually decides whether the thesis holds. If a good harness makes a cheap
model produce acceptable work, the thesis is right and model choice really is commoditised. If it
does not, then model quality still dominates and the harness is a cost optimisation rather than a
strategy.

**This repo does not answer that.** `eval/guardrail_eval.py` deliberately measures only the floor --
the things a cheap model is *prevented* from doing. The ceiling -- whether it writes good code,
whether a Haiku reviewer catches the bug an Opus reviewer catches -- needs an eval with real tasks,
real rubrics, and an API key, run against your own repo. The scaffolding for that is not here, and
inventing a number for it would be the single most dishonest thing this repository could do.

## What the repo does support, without qualification

Stripped of the aspirational framing, these hold:

1. **The harness's safety properties do not depend on the model.** Proven, re-runnable, 15/15.
2. **The harness itself is cheap to install and cheap to carry.** Measured: 65% less to read, 85%
   less to author, 66% of rule content kept out of the default session, ~0.2s to scaffold.
3. **Cost is a decision, not a default.** Every agent carries an explicit `model:` and `effort:`.
   Unset `model:` means `inherit`, which silently bills mechanical work at the caller's tier -- the
   quality gate treats that as a bug.
4. **The default roster is deliberately not the cheapest.** `sonnet-only` is ~19% cheaper. The
   default spends the difference on Opus review gates, on the argument that the seat whose entire
   job is catching what a generation pass got wrong is the worst place to economise. That is a bet,
   it is stated as a bet, and the table lets you take the other side of it.
5. **Governance is written down, versioned, and diffable** -- and the parts that can be enforced
   deterministically (secrets, PII, destructive ops, immutable ADRs, commit hygiene) are enforced by
   hooks, not by hope.

## Priority of the remaining work

1. **Enforce classification with path denies** (closes Gap 1, uses machinery that already works).
2. **Make seat tier the declared thing and generate `model:` from it** (closes Gap 2's mechanical
   half; the vendor port itself remains a port).
3. **Ship a quality eval harness** so the central claim -- that a good harness narrows the gap
   between model tiers -- can be tested rather than asserted (closes Gap 3).
4. CI templates and a real `devops` pipeline, so "workflow integration" means something.

Items 1 and 2 are small. Item 3 is the one that matters, and it is the one that could prove the
thesis wrong.

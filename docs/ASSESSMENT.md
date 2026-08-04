# Assessment

How this repo scores against the thesis it is built on, including where it falls short. Any claim not
backed by a file or a runnable script in this repo is marked as not delivered.

## Scorecard

| Pillar | Status | Evidence, or the gap |
|---|---|---|
| Models are commoditising | Acknowledged and acted on | `reference/cost-model.md` was rebuilt on current pricing. Opus 4.8 is 1.67x Sonnet 5, not 5x. The old "cheap model everywhere except the review gate" advice was written for a 5x gap and is largely obsolete; the roster no longer relies on it. |
| Advantage is the harness | Delivered, and falsifiable | `eval/guardrail_eval.py` scaffolds a harness and fires 25 payloads (11 must-block, 14 must-allow) at it: 25/25 correct. Every block is a shell script and an exit code. Swap Opus for Haiku and the result is byte-identical. The safety floor is model-independent, and the claim is re-runnable. The must-block set now includes the spawn boundary itself (see below); what the harness still leaves to prose rather than a gate is Gap 4. |
| ROI | Half delivered | Cost is modelled per roster profile (`benchmark/model_cost.py`) and the harness's own overhead is measured (`benchmark/RESULTS.md`: read path -54%, write path -85%). Value is not measured at all. Cost-per-feature without value-per-feature is not ROI. |
| Data under control (privacy) | Delivered | `security-privacy.md` (secrets, PII), enforced by `protect-secrets` hooks and settings deny rules, both tested. Audit mode makes product source technically read-only. |
| Governance: IP | Delivered | `ip-compliance.md`: dependency licence allow/deny by family, the AGPL-on-SaaS trigger, provenance risk on reproduced blocks, a runnable diff check for the reviewers. |
| Governance: model sovereignty | Enforced for data at rest; advisory beyond it | Gap 1 below. Partially closed. |
| Many models -> one system | Not delivered | Gap 2 below. Now has a concrete, sharper edge: the spawn boundary is Claude-Code-only by construction. |
| Enterprise context | Partial | The docs tree, specs, ADRs, glossary, business rules and the task board are real and are wired into the agents. New today: a generated code knowledge graph (`docs/context/code-graph.md`, module fan-in/fan-out) agents consult before a cross-module change, and DDD as an optional, composable methodology (flag `ddd`) binding the glossary to each dev agent's bounded context. Also new: a vetted path to extend a seat with a third-party skill - skills.sh discovery, a trust rubric (install count, publisher allow-list, audit status, mandatory content read) in `reference/skill-discovery.md`, and `/skill-wire` to attach one to a seat with a re-review, a diff, and a changelog record. That closes "no vetted way to extend seats with third-party skills"; see Gap 4 for what the review still leaves advisory. Absent: any integration with the systems an enterprise actually runs on - ticketing, SSO, a CMDB, an internal package registry. |
| Workflow integration | Partial | Slash commands, hooks, a task board that survives compaction, and now a post-bootstrap maintenance layer: `/harness-update` (idempotent re-run - `CONFLICT` queue, never clobbers), `/board-audit` (orphaned Active tasks, unlogged runs, attempt-cap breaches, unknown worktrees, stale graph), `/harness-tune` (deploy rights, deny/ask lists, spawn allowlist, attempt caps - diff shown, confirmed before landing), `/agent-permissions` (per-seat tool grants). Deployment control level (human-only / agent-with-approval / agent-non-prod, flag `deploy_ask`) is now an intake question, not a fixed posture. Still absent: CI pipeline templates, PR automation, ticket sync. `devops` is a seat with no shipped pipeline. |

## The thesis being scored

> Models are commoditising and are a poor place to build durable advantage. The advantage moves to
> the **agent harness**, to **enterprise context**, and to **workflow integration**. Governance now
> has to cover **privacy, IP, and model sovereignty**. Do not position AI capability around *which
> model we use*; position it around the ability to turn **many models** into an agent system that has
> ROI, keeps data under control, and runs safely in production.

## Gap 1 - Model sovereignty: enforced on data, advisory on routing

Status: partially closed.

`model-policy.md` defines a data-classification table (Public / Internal / Confidential /
Restricted) and binds each class to the models permitted to process it. The precedence rule is
classification beats seat tier: if a task's data class does not permit the tier's model, the work
re-routes or it does not get delegated at all.

That rule lives in `.claude/rules/`, which is context, not configuration. Claude Code's own
documentation is explicit: rules "shape Claude's behaviour but are not a hard enforcement layer". A
rule on its own therefore enforces model sovereignty only as far as the model chooses to follow it.

No `settings.json` deny rule ships for classification itself, because "sent Confidential text to a
hosted model" is not a distinguishable tool call and a deny rule could not intercept it.

### What is enforced

Enforcement is on the *data*, not on the *model*. Restricted data lives at known paths, so a
`permissions.deny` entry on `Read(<those paths>)` means the agent never obtains the data in the first
place, and what an agent cannot read it cannot leak to any model, on any provider, regardless of
which model is driving or whether it read the rule. This is the same mechanism the guardrail eval
exercises.

The pieces that implement it:

- `.claude/settings.json` carries a `{{RESTRICTED_DENIES}}` slot at the head of the deny list.
- The intake asks where Restricted data lives, as glob patterns.
- `model-policy.md` states that the classification table is the *policy* and the deny list is the
  *control*.

### What is still advisory

- **Routing itself.** Nothing prevents an agent from putting Confidential-but-readable text into a
  prompt to a model that the table does not permit. There is no tool call shaped like "sent this text
  to that provider", so there is nothing for a hook to intercept.
- **Data the org cannot locate.** If Restricted material has no nameable path, the deny list cannot
  cover it and the table is advice. The intake forces that admission rather than letting it pass
  silently, but an admission is not a control.

The current position: this repo enforces model sovereignty at the data boundary, and governs it by
rule everywhere else.

## Gap 2 - Many models: this is a single-vendor harness

The thesis asks for the ability to turn many models into an agent system. This repo runs on Claude
Code. Agent definitions are Claude Code frontmatter (`model:`, `effort:`, `tools:`, `maxTurns:`). The
`model:` field accepts `opus | sonnet | haiku | fable`: four models from one vendor.

Model tier is swappable. Model vendor is not. Re-pointing this roster at a self-hosted Llama or an
Azure-hosted GPT is not a configuration change; it is a port.

Two things partially mitigate it, and neither is sufficient:

- `AGENTS.md` is the vendor-neutral document, and `CLAUDE.md` is a thin `@AGENTS.md` import. Other
  coding agents that read `AGENTS.md` get the rules. They do not get the hooks, the settings deny
  rules, or the permission model, so they get the advice and none of the enforcement. The file says
  so.
- The seat-tier table in `model-policy.md` (judgment / implementation / mechanical -> model) is the
  right shape for portability: it is the one file a provider swap would edit, instead of a sweep
  across sixteen agent files. But it currently maps to Anthropic aliases, and nothing consumes it as
  an abstraction - the agent files still name the model directly.

What would close it: make the tier the thing the agent declares, and generate the concrete `model:`
value from the tier table at scaffold time. The scaffolder already does this kind of substitution. A
vendor swap would then be a one-file edit plus a re-run. It is not done.

The newest hook sharpens this rather than helping it. `guard-agent-spawn` is a PreToolUse hook keyed
to Claude Code's `Agent|Task` tool, and neither Cursor nor Codex exposes an equivalent subagent-spawn
hook point - `port.py` says so directly in its own header comment. On those two tools the roster still
exists as rules text the model can read, but nothing intercepts an off-roster spawn, a model-escalated
one, or a write dispatch with no registered task the way it does under Claude Code. The single-vendor
gap is not just the `model:` field anymore; the harness's most safety-critical control does not travel
with it.

## Gap 3 - ROI has no numerator

The repo measures what the harness costs and what it saves. It does not measure what it produces.
`benchmark/model_cost.py` will tell you a feature costs about $2.38 on the default roster and about
$0.61 on an all-Haiku roster. It cannot tell you whether the Haiku feature is worth shipping.

That is the question that decides whether the thesis holds. If a good harness makes a cheap model
produce acceptable work, the thesis is right and model choice really is commoditised. If it does not,
then model quality still dominates and the harness is a cost optimisation rather than a strategy.

Nothing in this repo measures it. `eval/guardrail_eval.py` measures only the floor: the things a
cheap model is *prevented* from doing. The ceiling - whether it writes good code, whether a Haiku
reviewer catches the bug an Opus reviewer catches - needs an eval with real tasks, real rubrics, and
an API key, run against your own repo. That scaffolding is not here, and no number for it is quoted
anywhere in the repo.

## Gap 4 - Per-agent module scope is a sentence, not a gate

Status: open, newly visible now that the spawn boundary exists for comparison.

Each dev agent's frontmatter says "Scope: you own `{{MODULE_PATHS}}`. Do not modify files outside
it." and the DDD rule restates the same boundary in domain language ("bounded contexts", never
import another context's internals). Both are `.claude/rules/` or agent-frontmatter prose - read,
not enforced. No hook checks an `Edit` or `Write` call's `file_path` against the dispatching agent's
declared scope before it lands. `protect-adr` already reads `tool_input.file_path` from the same
PreToolUse payload shape to block edits to Accepted ADRs; nothing analogous runs for module scope.

This is the same structural gap Gap 1 names for model sovereignty - a rule enforces only as far as
the model reading it chooses to comply - now visible for a second boundary because `guard-agent-spawn`
proved the harness can gate on payload contents when someone builds the hook. It had not been built
for scope.

What would close it: a `guard-agent-scope` hook, keyed the same way `guard-agent-spawn` is, comparing
the edited path against the calling agent's `MODULE_PATHS` glob before the write lands. The routing
table already threads a glob per agent through the scaffolder; the missing piece is a hook that reads
it per `Edit`/`Write`, not a new source of truth.

The skill-install path added today is the same pattern a third time. `reference/skill-discovery.md`'s
trust rubric and `/skill-wire`'s re-review at wire time both center on "read every file in the skill
for secret access, external data egress, or instructions to edit `.claude/`/`settings.json`/hooks" -
but that read is a procedure in a command file, carried out by the same model that is about to start
trusting the skill it is reviewing. No hook parses a candidate skill's files for those patterns before
`.claude/skills/` becomes content a future turn will follow; the gate is an `AskUserQuestion` and a
changelog line, not a technical control. A skill that got a sloppy review is trusted exactly as much
as a rule the model chose to follow - Gap 1's problem, in a third costume.

## What the repo supports today

1. **The harness's safety properties do not depend on the model.** Proven, re-runnable, 25/25.
2. **The harness itself is cheap to install and cheap to carry.** Measured: 54% less to read, 85%
   less to author, 67% of rule content kept out of the default session, ~0.2s to scaffold.
3. **Cost is a decision, not a default.** Every agent carries an explicit `model:` and `effort:`.
   Unset `model:` means `inherit`, which silently bills mechanical work at the caller's tier; the
   quality gate treats that as a bug.
4. **The default roster is deliberately not the cheapest.** `sonnet-only` is ~19% cheaper. The
   default spends the difference on Opus review gates, on the argument that the seat whose entire job
   is catching what a generation pass got wrong is the worst place to economise. That is a bet, it is
   stated as a bet, and the table lets you take the other side of it.
5. **Governance is written down, versioned, and diffable.** The parts that can be enforced
   deterministically (secrets, PII, destructive ops, immutable ADRs, commit hygiene) are enforced by
   hooks.
6. **The spawn boundary and anti-loop discipline are gates, not advice.** `guard-agent-spawn` blocks
   spawning a type outside the roster, overriding a roster seat's model at spawn time, and dispatching
   a write-capable seat with no registered `TASK-NNN` - three of the eval's must-block cases, with a
   matching allow case each. An `attempts:` cap (3, then `Blocked`) and `maxTurns` on every seat bound
   how long a stuck agent can run before a human has to look. `/board-audit` sweeps for the failure
   modes those controls don't catch by construction: orphaned Active tasks, unlogged completions, and
   worktrees the board never registered.
7. **Post-bootstrap operation is a maintained workflow, not a one-time scaffold.** `/harness-update`
   re-runs the scaffolder against a changed codebase and never overwrites a differing file - conflicts
   queue for a human to resolve, they do not get silently resolved for you. `/harness-tune` changes
   control-level dials (deploy rights, deny/ask lists, spawn allowlist, attempt caps) only after showing
   the diff and getting a yes.
8. **A seat can be extended with a third-party skill through a vetted path, not a blind drop.**
   `reference/skill-discovery.md`'s rubric (install count, publisher allow-list, duplicate and audit
   checks, a mandatory content read) gates install; `/skill-wire` re-reviews at wire time, refuses a
   skill that would instruct a config edit or hand a reviewer seat write-shaped instructions, and
   records every wire. What it still cannot do is described in Gap 4.

## Remaining work, in priority order

1. **Enforce classification with path denies** (closes Gap 1, uses machinery that already works).
2. **Make seat tier the declared thing and generate `model:` from it** (closes Gap 2's mechanical
   half; the vendor port itself remains a port, and the spawn boundary specifically does not travel
   to Cursor or Codex at all - that is a tool limitation, not a backlog item).
3. **Ship a quality eval harness** so the central claim - that a good harness narrows the gap between
   model tiers - can be tested rather than asserted (closes Gap 3).
4. CI templates and a real `devops` pipeline, so "workflow integration" means something beyond the
   maintenance layer (`/board-audit`, `/harness-tune`, `/harness-update`) that now exists.
5. **Ship a `guard-agent-scope` hook** so per-agent module ownership is enforced the same way the
   spawn boundary is, instead of living only in agent-frontmatter prose (closes Gap 4; the payload
   shape and the per-agent glob both already exist, `protect-adr` already shows the pattern).
6. **Add a first-pass content scan to skill install/wire** - grep a candidate skill's files for
   secret-adjacent calls, external endpoints, and config-edit instructions before the model's own
   content review runs. Not a replacement for the read (judgment still catches what a pattern match
   cannot), but a second line the model cannot skip under time pressure (extends Gap 4's fix to the
   skill-install path).

Items 1, 2, 5, and 6 are small - each reuses a mechanism the harness already has. Item 3 is the one
that matters, and it is the one that could prove the thesis wrong.

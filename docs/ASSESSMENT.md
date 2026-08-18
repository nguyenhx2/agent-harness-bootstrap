# Assessment

How this repo scores against the thesis it is built on, including where it falls short. Any claim not
backed by a file or a runnable script in this repo is marked as not delivered.

## Scorecard

| Pillar | Status | Evidence, or the gap |
|---|---|---|
| Models are commoditising | Acknowledged and acted on | `reference/cost-model.md` was rebuilt on current pricing. Opus 4.8 is 1.67x Sonnet 5, not 5x. The old "cheap model everywhere except the review gate" advice was written for a 5x gap and is largely obsolete; the roster no longer relies on it. |
| Advantage is the harness | Delivered, and falsifiable | `eval/guardrail_eval.py` scaffolds a harness and fires 107 payloads (40 must-block, 67 must-allow) at it: 107/107 correct, 214/214 when both hook flavors (`sh` and `ps1`) run. Every block is a shell script and an exit code. Swap Opus for Haiku and the result is byte-identical. The safety floor is model-independent, and the claim is re-runnable. The must-block set now includes the spawn boundary itself (see below); what the harness still leaves to prose rather than a gate is Gap 4. |
| ROI | Half delivered | Cost is modelled per roster profile (`benchmark/model_cost.py`) and the harness's own overhead is measured (`benchmark/RESULTS.md`: read path -45%, write path -85%). The read-path number moved from -54% to -45% this cycle because the skill grew real capability (tech-presets catalogue, wider skill sourcing, more intake coverage) faster than compression could claw it back - see `benchmark/RESULTS.md` Goal 2 for the trade. Value is not measured at all. Cost-per-feature without value-per-feature is not ROI. |
| Data under control (privacy) | Delivered | `security-privacy.md` (secrets, PII), enforced by `protect-secrets` hooks and settings deny rules, both tested. Audit mode makes product source technically read-only. |
| Governance: IP | Delivered | `ip-compliance.md`: dependency licence allow/deny by family, the AGPL-on-SaaS trigger, provenance risk on reproduced blocks, a runnable diff check for the reviewers. |
| Governance: model sovereignty | Enforced for data at rest; advisory beyond it | Gap 1 below. Partially closed. |
| Many models -> one system | Not delivered | Gap 2 below. Now has a concrete, sharper edge: the spawn boundary is Claude-Code-only by construction. |
| Enterprise context | Partial | The docs tree, specs, ADRs, glossary, business rules and the task board are real and are wired into the agents. New today: a generated code knowledge graph (`docs/context/code-graph.md`, module fan-in/fan-out) agents consult before a cross-module change, and DDD as the default methodology (TDD stays available, opt-in and composable) (flag `ddd`) binding the glossary to each dev agent's bounded context. Also new: a vetted path to extend a seat with a third-party skill - discovery across four source types now, not one (skills.sh, GitHub topic search, Anthropic's own repos, plugin marketplaces), a trust rubric (install count, publisher allow-list, audit status, mandatory content read) in `reference/skill-discovery.md`, and `/skill-wire` to attach one to a seat with a re-review, a diff, and a changelog record. That closes "no vetted way to extend seats with third-party skills"; see Gap 4 for what the review still leaves advisory. Intake grew three questions (internationalization, authorization model, operations posture), closing a questionnaire-coverage gap without adding a defaulted answer to any of them. `reference/tech-presets.md` gives codebase analysis a version-currency catalogue instead of relying on training-data memory, with an explicit rule that installed reality always wins over the preset - see Gap 5 for what keeps that catalogue honest. The sanctioned `env-read.py` path (list/check/diff/run, values never printed) closes the "devops/db/qa seats had no safe way to read local env files" gap; see Gap 4 for what it does not enforce. `.claude/.gitignore` is now shipped nested under `.claude/`, closing the edge case where per-task worktrees or machine state could get committed because the root `.gitignore` never mentioned them. Absent: any integration with the systems an enterprise actually runs on - ticketing, SSO, a CMDB, an internal package registry. |
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

The newest hook sharpens this rather than helping it, though less than this document used to claim.
`guard-agent-spawn` is a PreToolUse hook keyed to Claude Code's `Agent|Task` tool. Until recently
both this file and `port.py` stated that neither Cursor nor Codex exposed an equivalent
subagent-spawn hook point. **That is no longer true**: Cursor ships `subagentStart` / `subagentStop`
with a matcher on subagent type, and Codex ships `SubagentStart` / `SubagentStop` with an
`agent_type` matcher.

Cursor's documentation says `subagentStart` "can allow or deny subagent creation" and that exit 2
blocks. Codex's page lists exit-2 blocking for `PreToolUse`, `PostToolUse`, `UserPromptSubmit` and
`Stop`, and does not state it for `SubagentStart`, so on Codex the event is confirmed to exist and
its blocking behaviour is **unverified**. That distinction is worth keeping: this section is being
rewritten precisely because it previously asserted more than had been checked.

What has not changed is that a hook point is not the same as the control. Two things stand between
them, and both are real work rather than wiring:

- **The payload fields differ.** The hook reads `tool_input.subagent_type`, `tool_input.model` and
  `tool_input.prompt`. Cursor supplies `subagent_type`, `subagent_model` and `task`; Codex supplies
  `agent_type` and `agent_id`. An adapter mapping is needed, of the kind the Cursor adapter already
  performs for shell and read events.
- **Roster identity may not survive.** The check that carries the weight is "does
  `.claude/agents/<type>.md` exist". Cursor's documented subagent types are `generalPurpose`,
  `explore` and `shell`, and whether a named subagent reports its own name there is unverified.
  Codex takes its agent types from an `[agents.<name>]` TOML table rather than from markdown seats,
  so membership would only line up if the porter emitted that table too.

So the honest statement is: **reachable on both tools, equivalent on neither yet.** Today the
boundary still does not travel, and on Cursor and Codex the roster remains rules text a model can
read rather than a gate. The difference from before is that this is now a porting job with a known
shape, not a missing capability in the tools.

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

## Gap 4 - Per-agent module scope is a nudge, not a gate - and cannot become one without data Claude Code does not expose

Status: open, and this batch turned it from "nobody built the hook" into "the hook exists and is
structurally capped," which is a different, smaller gap than it looks.

Each dev agent's frontmatter says "Scope: you own `{{MODULE_PATHS}}`. Do not modify files outside
it." and the DDD rule restates the same boundary in domain language ("bounded contexts", never
import another context's internals). Both are `.claude/rules/` or agent-frontmatter prose on their
own - read, not enforced.

This batch shipped `guard-agent-scope.sh`, a `PreToolUse` hook on `Edit|Write`, to close it the way
`guard-agent-spawn` closed the spawn boundary. It does not, and its own header explains why: a
`PreToolUse` payload for `Edit|Write` carries `cwd` and `tool_input` (`file_path`, `content`) and
nothing that names which subagent is calling. `guard-agent-spawn` can gate because it fires on the
dispatch itself, where `tool_input.subagent_type` is the payload; once a dispatched agent starts
making its own `Edit`/`Write` calls, that identity is gone. `agent-history.sh`'s header confirms it
from the other side: subagent identity only ever arrives on `SubagentStop`, and that event carries no
`tool_input` at all. So a hook on this event cannot tell "the wrong seat editing outside its lane"
from "the orchestrator's own docs maintenance" from "the one dev agent this project has" - blocking
on data that is not there would either block legitimate writes indiscriminately or silently no-op,
both worse than an honest nudge. `protect-adr` is not a counterexample: it blocks purely on
`file_path` against a fixed list of Accepted ADRs and never needs to know who is calling, which is
exactly the property module-scope enforcement lacks.

What the hook does instead, using `/code-graph`'s module-ownership map and the sole in-flight task's
declared scope: it emits `hookSpecificOutput.additionalContext` - never a block - when an edited file
falls in a module a different agent owns and the Active task never named it, and it stays silent
whenever the picture is ambiguous (no graph yet, zero or more than one Active task, an unowned
module) rather than guessing. It always exits 0. It is real and it is tested (two of the eval's
must-allow cases exercise it), and it is genuinely useful signal. It is not, and cannot become, the
gate the previous version of this document said was simply unbuilt.

What would actually close it: a Claude Code payload capability this repo does not control - caller
identity on tool calls other than the dispatch itself. Until that exists, `guard-agent-scope`'s nudge
is the ceiling, not a stepping stone to a gate that a bit more code here would reach.

The skill-install path added today is the same pattern a third time. `reference/skill-discovery.md`'s
trust rubric and `/skill-wire`'s re-review at wire time both center on "read every file in the skill
for secret access, external data egress, or instructions to edit `.claude/`/`settings.json`/hooks" -
but that read is a procedure in a command file, carried out by the same model that is about to start
trusting the skill it is reviewing. No hook parses a candidate skill's files for those patterns before
`.claude/skills/` becomes content a future turn will follow; the gate is an `AskUserQuestion` and a
changelog line, not a technical control. A skill that got a sloppy review is trusted exactly as much
as a rule the model chose to follow - Gap 1's problem, in a third costume.

`env-read.py`, added this batch, is a fourth costume of the same problem. `protect-secrets` hard-blocks
the well-known vectors - `Read`/`Edit`/`Write` on a `.env*` path, and shell commands matching
`cat`/`type`/`head`/`Get-Content` against one - so those are an enforced control, not advice. But
nothing makes an agent route through `env-read.py` instead: a Bash command that opens the file some
other way (a short Python or Node one-liner, a text editor invoked as a subprocess, a tool whose name
the regex does not list) is not a shape the hook recognizes, and the rule that says "use
`env-read.py`" is `.claude/rules/agent-guardrails.md` prose - read, not enforced. The script is a
genuinely safer default when an agent chooses it (values never printed, production names refused);
it does not close the gap, it narrows what a careless agent would otherwise have to invent.

## Gap 5 - Tech-presets rot the moment nobody runs the currency check

Status: open, newly introduced by the file that closes a different gap.

`reference/tech-presets.md` gives codebase analysis a version-currency catalogue so a fresh model does
not propose a framework version from stale training data. `codebase-analysis.md` states the rule that
is supposed to keep it honest: what is actually installed always wins over the preset, versions get
verified against the registry rather than recalled from memory, and a preset that contradicts
installed reality becomes a migration proposal, not a silent rewrite.

That rule is text a model reads and (usually) follows - the same shape as every other gap in this
document. Nothing re-checks `tech-presets.md` itself against the outside world on any cadence: no
script diffs it against a package registry, no hook blocks a bootstrap that used it unchanged past
some age, and no CI job flags the file as stale. A catalogue that ships once and is then trusted by
every future bootstrap is exactly the kind of content that is accurate on the day it is written and
silently wrong a year later. The currency *rule* is real; the currency *check* is not automated.

What would close it: a script that spot-checks a sample of `tech-presets.md`'s pinned versions
against the relevant package registries and fails a scheduled job (not the bootstrap itself, which
should not depend on network access) when the drift exceeds some threshold - the same "trust but
verify on a schedule" shape `/board-audit` already uses for task-board drift.

## What the repo supports today

1. **The harness's safety properties do not depend on the model.** Proven, re-runnable, 107/107
   (214/214 across both hook flavors).
2. **The harness itself is cheap to install and cheap to carry, though less so than last cycle.**
   Measured: 45% less to read (down from 54% - the skill grew capability faster than compression
   could recover it, see `benchmark/RESULTS.md`), 85% less to author, 64% of rule content kept out
   of the default session, ~0.2s to scaffold.
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
   worktrees the board never registered. `guard-agent-scope` is the honest sibling of the spawn
   boundary: a nudge, not a gate, and documented as structurally unable to become one - see Gap 4.
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
   half; the vendor port itself remains a port). The spawn boundary still does not travel, but it
   has moved from "tool limitation" to backlog item: both Cursor and Codex now expose subagent-start
   hooks, so what is missing is a field mapping and a way to make roster identity line up, not a
   capability in the tools. See Gap 2 for what each one would take.
3. **Ship a quality eval harness** so the central claim - that a good harness narrows the gap between
   model tiers - can be tested rather than asserted (closes Gap 3).
4. CI templates and a real `devops` pipeline, so "workflow integration" means something beyond the
   maintenance layer (`/board-audit`, `/harness-tune`, `/harness-update`) that now exists.
5. **Not actionable by this repo.** Closing Gap 4's module-scope half for real needs Claude Code to
   expose caller/subagent identity on `Edit`/`Write` payloads, not more code here - `guard-agent-scope`
   already does everything an advisory hook can do without that data. Track the upstream capability;
   do not re-attempt a blocking version of this hook until it lands.
6. **Add a first-pass content scan to skill install/wire** - grep a candidate skill's files for
   secret-adjacent calls, external endpoints, and config-edit instructions before the model's own
   content review runs. Not a replacement for the read (judgment still catches what a pattern match
   cannot), but a second line the model cannot skip under time pressure (extends Gap 4's fix to the
   skill-install path).
7. **Widen `protect-secrets`'s command pattern past the literal `cat`/`type`/`head` list**, or accept
   that `env-read.py` is a safer default rather than an enforced one and say so wherever the harness
   currently implies otherwise (closes Gap 4's fourth costume).
8. **Schedule a currency check for `reference/tech-presets.md`** against the package registries it
   claims to reflect, separate from the bootstrap path itself (closes Gap 5).

Items 1, 2, 6, and 7 are small - each reuses a mechanism the harness already has. Item 3 is the one
that matters, and it is the one that could prove the thesis wrong. Item 5 is not actionable at all
right now - it waits on a platform capability, not a backlog slot.

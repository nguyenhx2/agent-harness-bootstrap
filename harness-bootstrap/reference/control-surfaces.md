# Control surfaces, ranked by hardness

The distinction that matters is **enforced** versus **advisory**. This repo states which of its own
controls are which - extracted here as a standalone, citable one-pager so it can be linked from the
bootstrap skill's own quality gate as well as from `docs/CONTEXT-MANAGEMENT.md`, instead of living
inside one long document.

<img src="../../docs/assets/control-layers.svg" alt="Control layers ranked by hardness: settings.json deny rules, PreToolUse hooks, tool allowlists, and maxTurns are enforced; rules, agent bodies, and effort are advisory">

## Enforced: the model does not get a vote

| Control | Where | What it stops |
|---|---|---|
| `permissions.deny` in `settings.json` | `Read(**/.env)`, `Read(**/*.pem)`, `Read(**/secrets/**)`, `Bash(git push --force:*)`, `Bash(rm -rf:*)`, plus a `{{RESTRICTED_DENIES}}` slot at the head of the list | What the agent cannot even **see**. The action never reaches a tool call |
| **PreToolUse hooks**, exit code 2 | `protect-secrets`, `guard-main-commit`, `check-commit-msg`, `protect-adr` | What the agent cannot **do**: read a `.env`, commit to `main`, ship a non-conventional commit message, edit an ADR whose on-disk status is `Accepted` |
| `tools:` allowlist in agent frontmatter | e.g. `code-reviewer` and `security-reviewer` get `Read, Grep, Glob, Bash` | What the agent cannot **reach**. A reviewer with `Edit` has stopped being a reviewer, and the frontmatter is what makes that structural rather than aspirational |
| `maxTurns` | e.g. `history-tracker: maxTurns: 10` | The circuit breaker. `cost-model.md`: *"the cost of a stuck agent is unbounded"* |

`eval/guardrail_eval.py` scaffolds a harness and fires the guardrail payload suite at it: 11
must-block and 14 must-allow cases, **all judged correctly**. Every block is a shell script and an
exit code, which is what the eval's header describes:

> `A cheap model cannot commit a secret. It cannot commit straight to main. It cannot edit an accepted
> ADR. It cannot ship an AI-attribution trailer. Not because it knows better, but because the hook
> exits 2 and the tool call never happens.`

Swap Opus for Haiku and the result is byte-identical. **The safety floor is model-independent.**

## Advisory

- **Rules in `.claude/rules/`.** These are context, not configuration. Claude Code's own documentation
  says rules *"shape Claude's behaviour but are not a hard enforcement layer"*. A rule is a good way
  to make an agent do the right thing. It is not a way to make the wrong thing impossible.
- **The agent body / system prompt.** Same category. It is instruction, and instruction can be
  outweighed, forgotten after compaction, or simply not followed.
- **`effort:`** is a **throttle**, not a control. It sets how hard the model pulls, not where it is
  allowed to go. `cost-model.md`: *"Do not starve a judgment seat to save money."* Lowering `effort`
  on an agent you do not trust makes it a worse agent, not a safer one.
- **Hooks that cannot see who is calling them.** A hook is only as enforceable as the payload it
  fires on: `guard-agent-scope` wants to block a write to a module a different seat owns, but the
  `PreToolUse` payload for `Edit|Write` names no calling subagent, so it advises instead - see its
  header and `assets/claude/hooks/README.md` for the finding.

`agent-guardrails.md` builds this into a four-layer model and puts rules at layer 3 of 4: *"Rules are
layer 3 - they are not the only layer, and they are not a substitute for the other three."*

## Turning an advisory control into an enforced one

A soft control becomes hard when it can be expressed as a file the harness checks.

"Never commit to main" appears twice in this repo, deliberately. Once as prose in `AGENTS.md`
(advisory), and once as `.claude/hooks/guard-main-commit.sh`, which parses the `Bash` tool call,
resolves the target directory from any `cd` or `git -C`, checks the effective branch, and **exits 2**
(enforced). The rule and the hook say the same thing; only one of them is enforced, and the other one
exists so the agent knows why before it hits the wall.

The migration path is always the same: find the tool call the violation is shaped like, and intercept
it. `docs/ASSESSMENT.md` walks this move for data classification. The rule (`model-policy.md`) says
which model may process which data class, which was advisory. The fix was not a better rule: Restricted
data lives at *known paths*, and `permissions.deny` on `Read(<those paths>)` means the agent never
obtains the data at all, and therefore cannot leak it to any model on any provider, regardless of which
model is driving or whether it read the rule.

## What could not be made hard

- **Model routing is still advisory.** Nothing prevents an agent from putting Confidential-but-readable
  text into a prompt to a model the policy table does not permit. The reason generalises: *"There is no
  tool call shaped like 'sent this text to that provider', so there is nothing for a hook to
  intercept."* A control surface needs a surface. Where there is no interceptable event, there is no
  hook.
- **Data the org cannot locate.** If Restricted material has no nameable path, the deny list cannot
  cover it and the classification table is advice. The intake forces that admission rather than letting
  it pass silently - *"but an admission is not a control."*

From `ASSESSMENT.md`: **this repo enforces model sovereignty at the data boundary, and governs it by
rule everywhere else.**

## The model as a layer

The memory hierarchy (`docs/CONTEXT-MANAGEMENT.md`, section 1) and the control ranking above are two
views of the same stack.

<img src="../../docs/assets/harness-architecture.svg" alt="Harness reference architecture in seven layers, bottom-up: the work, the enforcement plane, the state plane, the context plane, the policy plane, the model slot, and orchestration - with every layer below the model slot deterministic and model-agnostic">

Read it bottom-up. The work is at the bottom, and everything above it exists to protect it. The
enforcement plane is the thickest band because it is the only one that does not negotiate: shell
scripts and glob matching, no model consulted. Above that, the state plane is markdown in git; the
context plane is the volatile window `docs/CONTEXT-MANAGEMENT.md` is about; the policy plane is
advice. Only then does the **model** appear, in a slot near the top, with the seat-tier bindings
(`judgment -> opus`, `implementation -> sonnet`, `mechanical -> haiku`) drawn as replaceable contents
rather than as structure.

**Every layer beneath the slot is model-agnostic.** Swap the tier bindings and the deny list, the
hooks, the tool grants, the `maxTurns`, the board, the task files and the run archive are all
byte-for-byte what they were. The safety floor and the durable state sit underneath the model choice,
not on top of it.

The diagram carries the caveat from `docs/ASSESSMENT.md` Gap 2 on the drawing itself: **model tier is
swappable; model vendor is not.** The `model:` frontmatter field accepts `opus | sonnet | haiku |
fable` and nothing else, so re-pointing this roster at a self-hosted or third-party model is a **port**,
not a config change: there is no execution adapter in this repo. The tier table is not yet a
*generator* either. It states the binding, but each agent file still names its own `model:` directly,
so a tier swap today is a table edit **and** a sweep of the agent frontmatter. Making the tier the
declared thing and generating `model:` from it at scaffold time is listed as outstanding work, and it
is not done.

## Sources

- `harness-bootstrap/assets/claude/settings.json` - the deny rules.
- `harness-bootstrap/assets/claude/hooks/` and `hooks/README.md` - the PreToolUse hooks and their
  contract.
- `harness-bootstrap/assets/claude/rules/agent-guardrails.md` - the four-layer model.
- `harness-bootstrap/assets/claude/rules/model-policy.md` - the data-classification table.
- `eval/guardrail_eval.py` - the guardrail payload suite.
- `docs/ASSESSMENT.md` - what is enforced, what is advisory, and why model routing cannot be hooked.
- `docs/CONTEXT-MANAGEMENT.md` - the memory hierarchy this ranking sits alongside.

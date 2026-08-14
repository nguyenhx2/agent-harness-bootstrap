# Cost model - how to make a roster cheap without making it dumb

Read this before assigning `model:` or `effort:` to any generated agent. It is the reasoning behind
[`roster.md`](roster.md)'s allocation table; that table is the answer, this is the why.

## The pricing that actually applies

| Model | Alias | Input $/1M | Output $/1M | Context |
|---|---|---|---|---|
| Claude Fable 5 | `fable` | $10.00 | $50.00 | 1M |
| Claude Opus 4.8 | `opus` | $5.00 | $25.00 | 1M |
| Claude Sonnet 5 | `sonnet` | $3.00 | $15.00 | 1M |
| Claude Haiku 4.5 | `haiku` | $1.00 | $5.00 | 200K |

Cache reads cost ~0.1x input. Cache writes cost 1.25x (5-minute TTL) or 2x (1-hour TTL).

**The headline: Opus is 1.67x Sonnet, not 5x.** Much published multi-agent advice - including this
skill's previous version - dates from a five-fold Opus/Sonnet gap and concluded "spend the expensive
model only on review gates." At these prices that is mostly wrong: downgrading a reviewer to Sonnet
saves ~40% of that agent's tokens, not ~80%, and buys it by weakening the seat whose whole job is
catching what a generation pass got wrong. Haiku, though, is a genuine 3x saving against Sonnet and
5x against Opus - the cheap end of the ladder is where tier selection still pays.

## The four levers, ranked by how much they actually move the bill

### 1. `effort:` - the biggest lever, and the one most rosters never set

`effort` controls thinking depth and how much the model does per turn. It is valid subagent
frontmatter (`low` | `medium` | `high` | `xhigh` | `max`) and defaults to inheriting the session
level - in practice, whatever the human's session runs at, usually `high` or `xhigh`. On a ten-agent
roster that is a large, silent, unbudgeted spend. Lower effort means fewer, more-consolidated tool
calls, less preamble, terser output - it cuts thinking tokens, output tokens, AND turn count, so it
compounds.

| Effort | Use for | Notes |
|---|---|---|
| `low` | Mechanical, low-judgment work: archiving, summarizing an append-only log, running a fixed pipeline | Genuinely scoped work only - at `low` the model will not go above and beyond, which is the point |
| `medium` | Structured output against a settled contract: writing tests to stated criteria, seeding, checking a diff against a checklist | The cost-saving step-down. On Sonnet 5, `medium` ≈ Sonnet 4.6 at `high` |
| `high` | The default. Implementation, review, spec work - anything intelligence-sensitive | Recommended minimum for work where being wrong is expensive |
| `xhigh` | The hardest coding and agentic work: a cross-cutting refactor, a root-cause hunt | Best setting for coding/agentic on Opus 4.8 and Sonnet 5. Do **not** reach for it reflexively |
| `max` | Effectively never, in a generated roster | Prone to overthinking, diminishing returns. Reserve for a human deciding a specific hard case |

Two traps worth stating plainly:

- **Do not default everything to `xhigh`.** On Opus 4.8 the intelligence ceiling is high enough that
  `high` is the right starting point; `xhigh` is something you move *to* after measuring, not from.
- **Do not starve a judgment seat to save money.** At `low`/`medium` the model scopes work tightly to
  what was asked. That is exactly right for `history-tracker` and exactly wrong for `debugger`. If
  you see shallow reasoning on a hard problem, raise `effort` - do not try to prompt around it.

### 2. Context hygiene - what every request pays for, on every turn

An agent's input cost is dominated by things that are re-sent on *every* turn of its run: the system
prompt, the tool schemas, the loaded rules, and the files it has read. Those recur; the agent body you
wrote once does not dominate anything.

Three concrete cuts, in descending order of payoff:

**Path-scope the rules.** A `.claude/rules/` file with no `paths:` frontmatter loads at launch, into
every session, at the same priority as `CLAUDE.md` - a roster whose rules are all unconditional pays
for every one in every agent, forever, including `frontend.md` in the database agent. With `paths:`
the rule enters context only when Claude touches a matching file:

```markdown
---
paths:
  - "src/components/**/*.{tsx,jsx}"
  - "src/app/**/*.tsx"
---
# Frontend conventions
```

Only genuinely universal rules stay unconditional - in the generated roster that is `00-overview.md`,
`agent-guardrails.md`, `task-tracking.md`, `conventional-commits.md`, and the two governance rules
(`model-policy.md`, `ai-governance.md`), which decide what may be sent where *before* any file is
touched and so cannot be path-scoped. Everything else gets a `paths:` block - the single largest
recurring saving, costing nothing but frontmatter.

**Grant tools narrowly.** Every tool in `tools:` ships its JSON schema on every request. Reviewers
need `Read, Grep, Glob, Bash` - `Edit`/`Write` costs tokens *and* destroys their independence.
Omitting `tools:` inherits everything including every MCP tool on the machine - thousands of schema
tokens the agent never calls. `disallowedTools` strips MCP servers an agent has no business touching.

**Bound the runaway.** `maxTurns` is a circuit breaker: a looping agent burns the full context every
turn, and the cost of a stuck agent is unbounded. Set it on the mechanical seats, where a high turn
count means something already went wrong.

### 3. Model tier - still real, but a smaller dial than it used to be

Apply in this order and stop at the first match:

| Question | Model |
|---|---|
| Is the task mechanical and low-judgment - formatting, summarizing, running a fixed pipeline, archiving? | `haiku` |
| Does it make consequential judgment calls (planning, decomposition, root-cause) or exist to catch *other* agents' mistakes (a review or merge gate)? | `opus` |
| Otherwise - producing code, tests, docs, or structured output against a settled spec | `sonnet` |

Note the order changed from the usual formulation: **test for mechanical first.** That is where tier
selection still buys a 3-5x saving. The Opus-vs-Sonnet decision below it is a 1.67x dial, so make it
on quality grounds and stop agonizing about the cost.

`fable` is not assigned to any seat by default: it costs 2x Opus, and its strength - very
long-horizon autonomous runs - is not what a bounded, orchestrator-supervised task agent does. Field
it only when a human explicitly asks, on a specific hard problem.

**Never leave `model:` unset.** It defaults to `inherit` - the agent silently runs on whatever the
caller uses. Not a choice but the absence of one; on a mechanical agent it means Opus prices to
summarize a log file.

### 4. Prompt-cache stability - a 90% discount you get for free, or lose for free

Caching is a **prefix match** (`tools` → `system` → `messages`); any byte change invalidates
everything after it. Cache reads cost ~0.1x input. For a generated roster this means one rule, about
*authoring*, not runtime:

> **Agent bodies, rule files, and CLAUDE.md must be byte-stable across runs.**

Nothing in them may interpolate a timestamp, a run ID, a session counter, or today's date - a single
`Generated: 2026-07-14` line cold-misses that agent's cache on every future run. Volatile state
belongs in the task file under `docs/tasks/`, which the agent *reads* as a message, not in the
system prompt it *is*.

Two corollaries:

- Changing an agent's `tools:` list mid-project invalidates its whole cache (tools render at position
  zero). Batch roster changes; don't trickle them.
- The orchestrator dispatching to a stable agent set gets cache reads on every dispatch. A roster
  churning every session never warms.

## When NOT to spawn a subagent

A subagent is not free parallelism. It starts with a fresh context window and must re-establish
everything - re-read the files, re-load the rules, re-derive the situation - at full price, because
a fresh context has nothing cached. The trade is worth it when the subagent's work would otherwise
**flood the parent's context** with material the parent will never reference again - a wide search,
a long log, twenty files skimmed to find one; it returns a summary, the parent keeps a clean window
(this is why `Explore` exists). It is *not* worth it when the task is two tool calls the parent
could make itself: delegating a single `grep` costs more than running it.

So, for the orchestrator's dispatch rule:

- **Fan out** when the work is independent and voluminous - that's parallel wall-clock *and* context
  savings.
- **Inline it** when the work is small and its output is small.
- Never dispatch an agent whose entire job is to hand back something the parent already has.

## Putting it together

The allocation in [`roster.md`](roster.md) falls straight out of the above: the savings come from
the **bottom** of the roster (mechanical seats on `haiku`+`low`, bounded by `maxTurns`) and from
**context discipline on every seat** (path-scoped rules, narrow tool grants, stable bodies) - not
from downgrading the seats that do the thinking. Record the allocation in the setup-plan echo so a
human sees it was decided rather than defaulted, and re-state it in the quality gate. An agent
shipped with `model:` or `effort:` unset is a bug, not a default.

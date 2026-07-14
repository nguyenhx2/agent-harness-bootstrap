# Cost model — how to make a roster cheap without making it dumb

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

**The headline: Opus is 1.67x Sonnet, not 5x.** A lot of published multi-agent advice — including the
previous version of this skill — was written when the Opus/Sonnet gap was roughly five-fold, and it
concluded "spend the expensive model only on review gates." That conclusion was correct for those
prices and is mostly wrong for these. Downgrading a reviewer from Opus to Sonnet now saves ~40% on
that agent's tokens, not ~80%, and it buys that saving by weakening the seat whose entire job is to
catch what a generation pass got wrong.

Meanwhile Haiku is a genuine 3x saving against Sonnet and 5x against Opus — so the cheap end of the
ladder is where tier selection still pays.

## The four levers, ranked by how much they actually move the bill

### 1. `effort:` — the biggest lever, and the one most rosters never set

`effort` controls thinking depth and how much the model does per turn. It is valid subagent
frontmatter (`low` | `medium` | `high` | `xhigh` | `max`) and it defaults to inheriting the session
level, which in practice means every agent runs at whatever the human's session happens to be — usually
`high` or `xhigh`. On a ten-agent roster that is a large, silent, unbudgeted spend.

Lower effort means fewer and more-consolidated tool calls, less preamble, terser output. It reduces
*both* thinking tokens and output tokens, and it reduces the number of turns — so it compounds.

| Effort | Use for | Notes |
|---|---|---|
| `low` | Mechanical, low-judgment work: archiving, summarizing an append-only log, running a fixed pipeline | Genuinely scoped work only — at `low` the model will not go above and beyond, which is the point |
| `medium` | Structured output against a settled contract: writing tests to stated criteria, seeding, checking a diff against a checklist | The cost-saving step-down. On Sonnet 5, `medium` ≈ Sonnet 4.6 at `high` |
| `high` | The default. Implementation, review, spec work — anything intelligence-sensitive | Recommended minimum for work where being wrong is expensive |
| `xhigh` | The hardest coding and agentic work: a cross-cutting refactor, a root-cause hunt | Best setting for coding/agentic on Opus 4.8 and Sonnet 5. Do **not** reach for it reflexively |
| `max` | Effectively never, in a generated roster | Prone to overthinking, diminishing returns. Reserve for a human deciding a specific hard case |

Two traps worth stating plainly:

- **Do not default everything to `xhigh`.** On Opus 4.8 the intelligence ceiling is high enough that
  `high` is the right starting point; `xhigh` is something you move *to* after measuring, not from.
- **Do not starve a judgment seat to save money.** At `low`/`medium` the model scopes work tightly to
  what was asked. That is exactly right for `history-tracker` and exactly wrong for `debugger`. If
  you see shallow reasoning on a hard problem, raise `effort` — do not try to prompt around it.

### 2. Context hygiene — what every request pays for, on every turn

An agent's input cost is dominated by things that are re-sent on *every* turn of its run: the system
prompt, the tool schemas, the loaded rules, and the files it has read. Those recur; the agent body you
wrote once does not dominate anything.

Three concrete cuts, in descending order of payoff:

**Path-scope the rules.** A file in `.claude/rules/` with no `paths:` frontmatter loads at launch,
into every session, at the same priority as `CLAUDE.md`. A roster with fourteen unconditional rules
pays for all fourteen in every agent, forever — including `frontend.md` in the database agent and
`data-model.md` in the UI agent. Add `paths:` and the rule only enters context when Claude touches a
matching file:

```markdown
---
paths:
  - "src/components/**/*.{tsx,jsx}"
  - "src/app/**/*.tsx"
---
# Frontend conventions
```

Only genuinely universal rules stay unconditional — in the generated roster that is `00-overview.md`,
`agent-guardrails.md`, and `task-tracking.md`. Everything else gets a `paths:` block. This is the
single largest recurring saving available and it costs nothing but frontmatter.

**Grant tools narrowly.** Every tool in an agent's `tools:` list ships its JSON schema on every
request. Reviewers need `Read, Grep, Glob, Bash` — granting them `Edit`/`Write` costs tokens *and*
destroys their independence. Omitting `tools:` inherits everything, including every MCP tool
configured on the machine, which can be thousands of tokens of schema the agent will never call. Use
`disallowedTools` to strip MCP servers an agent has no business touching.

**Bound the runaway.** `maxTurns` is a circuit breaker. An agent that loops — re-reading, re-trying,
re-planning — burns the full context on every turn, and the cost of a stuck agent is unbounded. Set
`maxTurns` on the mechanical seats, where a high turn count means something has already gone wrong.

### 3. Model tier — still real, but a smaller dial than it used to be

Apply in this order and stop at the first match:

| Question | Model |
|---|---|
| Is the task mechanical and low-judgment — formatting, summarizing, running a fixed pipeline, archiving? | `haiku` |
| Does it make consequential judgment calls (planning, decomposition, root-cause) or exist to catch *other* agents' mistakes (a review or merge gate)? | `opus` |
| Otherwise — producing code, tests, docs, or structured output against a settled spec | `sonnet` |

Note the order changed from the usual formulation: **test for mechanical first.** That is where tier
selection still buys a 3–5x saving. The Opus-vs-Sonnet decision below it is a 1.67x dial, so make it
on quality grounds and stop agonizing about the cost.

`fable` is not assigned to any seat by default. It costs 2x Opus and its strengths — very long-horizon
autonomous runs — are not what a bounded, orchestrator-supervised task agent does. Field it only if a
human explicitly asks for it on a specific hard problem.

**Never leave `model:` unset.** It defaults to `inherit`, which means the agent silently runs on
whatever the caller happens to be using. That is not a choice; it is the absence of one, and on a
mechanical agent it means paying Opus prices to summarize a log file.

### 4. Prompt-cache stability — a 90% discount you get for free, or lose for free

Caching is a **prefix match**: the cached prefix is `tools` → `system` → `messages`, and any byte
change anywhere in the prefix invalidates everything after it. Cache reads cost ~0.1x input.

For a generated roster this means one rule, and it is a rule about *authoring*, not about runtime:

> **Agent bodies, rule files, and CLAUDE.md must be byte-stable across runs.**

Nothing in them may interpolate a timestamp, a run ID, a session counter, or today's date. A single
`Generated: 2026-07-14` line at the top of an agent file is enough to cold-miss that agent's cache on
every run of every future day. Put volatile state where it belongs — in the task file under
`docs/tasks/`, which the agent *reads* as a message, not in the system prompt it *is*.

Two corollaries:

- Changing an agent's `tools:` list mid-project invalidates its whole cache (tools render at position
  zero). Batch roster changes; don't trickle them.
- The orchestrator dispatching to a stable agent set gets cache reads on every dispatch. A roster
  churning every session never warms.

## When NOT to spawn a subagent

A subagent is not free parallelism. It starts with a fresh context window and must re-establish
everything it needs — re-read the files, re-load the rules, re-derive the situation. That
re-establishment is the dominant cost of a short subagent run, and it is paid at full price because a
fresh context has nothing cached.

The trade is worth it when the subagent's work would otherwise **flood the parent's context** with
material the parent will never reference again — a wide search, a long log, twenty files skimmed to
find one. It returns a summary; the parent keeps a clean window. That is a real saving and it is why
`Explore` exists.

It is *not* worth it when the task is two tool calls the parent could make itself. Delegating a single
`grep` costs more than running it.

So, for the orchestrator's dispatch rule:

- **Fan out** when the work is independent and voluminous — that's parallel wall-clock *and* context
  savings.
- **Inline it** when the work is small and its output is small.
- Never dispatch an agent whose entire job is to hand back something the parent already has.

## Putting it together

The allocation in [`roster.md`](roster.md) falls straight out of the above, and its shape is worth
noting: the savings come from the **bottom** of the roster (mechanical seats on `haiku`+`low`, bounded
by `maxTurns`) and from **context discipline applied to every seat** (path-scoped rules, narrow tool
grants, stable bodies) — not from downgrading the seats that do the thinking.

Record the allocation in the setup-plan echo so a human can see it was decided rather than defaulted,
and re-state it in the quality gate. An agent shipped with `model:` or `effort:` unset is a bug, not a
default.

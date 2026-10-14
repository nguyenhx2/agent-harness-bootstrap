# Cost model - how to make a roster cheap without making it dumb

The reasoning behind [`roster.md`](roster.md)'s allocation table. Read it before deviating from that
table.

## The pricing that actually applies

| Model | Alias | Input $/1M | Output $/1M | Context |
|---|---|---|---|---|
| Claude Fable 5 | `fable` | $10.00 | $50.00 | 1M |
| Claude Opus 4.8 | `opus` | $5.00 | $25.00 | 1M |
| Claude Sonnet 5 | `sonnet` | $3.00 | $15.00 | 1M |
| Claude Haiku 4.5 | `haiku` | $1.00 | $5.00 | 200K |

Cache reads cost ~0.1x input. Cache writes cost 1.25x (5-minute TTL) or 2x (1-hour TTL).

**Opus is 1.67x Sonnet, not 5x.** Downgrading a reviewer to Sonnet saves ~40% of that seat's tokens
and weakens the seat whose job is catching what generation got wrong. Haiku is a genuine 3x saving
against Sonnet and 5x against Opus - the cheap end of the ladder is where tier selection pays.

## The four levers, ranked by how much they move the bill

### 1. `effort:` - the biggest lever, and the one most rosters never set

`effort` (`low` | `medium` | `high` | `xhigh` | `max`) sets thinking depth and work per turn. Unset, it
inherits the session level - usually `high` or `xhigh` - which on a ten-seat roster is a large,
silent spend. Lower effort cuts thinking tokens, output tokens and turn count, so it compounds.

| Effort | Use for | Notes |
|---|---|---|
| `low` | Mechanical, low-judgment work: archiving, summarizing an append-only log, running a fixed pipeline | Genuinely scoped work only - at `low` the model will not go above and beyond, which is the point |
| `medium` | Structured output against a settled contract: writing tests to stated criteria, seeding, checking a diff against a checklist | The cost-saving step-down. On Sonnet 5, `medium` ≈ Sonnet 4.6 at `high` |
| `high` | The default. Implementation, review, spec work - anything intelligence-sensitive | Recommended minimum for work where being wrong is expensive |
| `xhigh` | The hardest coding and agentic work: a cross-cutting refactor, a root-cause hunt | Best setting for coding/agentic on Opus 4.8 and Sonnet 5. Do **not** reach for it reflexively |
| `max` | Effectively never, in a generated roster | Prone to overthinking, diminishing returns. Reserve for a human deciding a specific hard case |

**Dev seats run at `medium`.** A `<domain>-dev` seat works against a settled contract: in the
Guarded flow `spec-guardian` has locked the criteria and the design names modules, interfaces and
edge cases; in Direct work the change is one reversible module. The brief supplies the judgment, and
the anti-loop rule re-dispatches the third attempt one `effort:` tier higher (`task-control.md`).
Raise a dev seat to `high` only when its attempts show it (repeated `scope` failures on clear
briefs), and record it in `model-tiers.md`. Seats that make the calls - `ba-analyst`,
`data-modeler`, the reviewers, `strategist`, `checker` - stay at `high`.

- **Do not default everything to `xhigh`.** On Opus 4.8 start at `high`; move to `xhigh` after
  measuring.
- **Do not starve a judgment seat.** Tight scoping at `low`/`medium` is right for
  `history-tracker` and wrong for `debugger`. Shallow reasoning on a hard problem means raise
  `effort`, not prompt around it.

### 2. Context hygiene - what every request pays for, on every turn

Input cost is dominated by what is re-sent every turn: system prompt, tool schemas, loaded rules,
files read. In descending order of payoff:

**Path-scope the rules.** A `.claude/rules/` file with no `paths:` loads into every session at
`CLAUDE.md` priority - `frontend.md` in the database agent, forever. With `paths:` it loads only
when a matching file is touched:

```markdown
---
paths:
  - "src/components/**/*.{tsx,jsx}"
  - "src/app/**/*.tsx"
---
# Frontend conventions
```

Only rules that bind before any file is touched stay unconditional: `00-overview.md`,
`agent-guardrails.md`, `task-tracking.md`, `conventional-commits.md`, `model-policy.md`, and
`ai-governance.md` with the `ai` flag. The seat-tier table lives in path-scoped `model-tiers.md`.

**Grant tools narrowly.** Every tool in `tools:` ships its schema on every request. Reviewers need
`Read, Grep, Glob, Bash`; `Edit`/`Write` costs tokens and their independence. Omitting `tools:`
inherits every MCP tool on the machine. `disallowedTools` strips servers a seat has no business
touching.

**Bound the runaway.** `maxTurns` is a circuit breaker: a looping agent burns its full context every
turn. Set it on the mechanical seats, where a high turn count means something already went wrong.

**Verify in proportion to the diff.** The costliest habit is verification nobody needed: three
reviewers over a README edit, the full suite after every step, end to end for a rename.
`.claude/scripts/verify-plan.py` decides per diff - security review only when paths touch auth,
secrets, input parsing, data handling, AI tool calls, dependencies or infrastructure; end to end only
for a named critical flow; docs and config get the secret scan only - and logs each skipped gate
with its reason. Current models check their own work unprompted, so a brief asking for an extra
review pass buys one that learns nothing. Put the check in the gate once - a script exit code -
never in every brief.

**Keep resumable state compact.** The task file carries a three-line checkpoint (next step, last
green commit, open questions) that `task.py resume` prints with the last log rows; older log rows
are archived beside the file. Resuming costs the digest, not the history.

### 3. Model tier - a smaller dial than it used to be

Apply in this order and stop at the first match:

| Question | Model |
|---|---|
| Is the task mechanical and low-judgment - formatting, summarizing, running a fixed pipeline, archiving? | `haiku` |
| Does it make consequential judgment calls (planning, decomposition, root-cause) or exist to catch *other* agents' mistakes (a review or merge gate)? | `opus` |
| Otherwise - producing code, tests, docs, or structured output against a settled spec | `sonnet` |

**Test for mechanical first** - that is where tier selection buys 3-5x. Opus versus Sonnet is a
1.67x dial; decide it on quality.

`fable` is on no seat by default: it costs 2x Opus, and its strength - very long autonomous runs -
is not what a bounded, supervised task seat does. Field it only when a human asks, for a specific
hard problem.

**Never leave `model:` unset.** It defaults to `inherit`: a mechanical seat then summarizes a log at
Opus prices.

### 4. Prompt-cache stability - a 90% discount you get or lose for free

Caching is a **prefix match** (`tools` → `system` → `messages`); one changed byte invalidates
everything after it.

> **Agent bodies, rule files, and CLAUDE.md must be byte-stable across runs.**

No timestamp, run ID, session counter or date in them - one `Generated: 2026-07-14` line cold-misses
that agent's cache on every run. Volatile state belongs in the task file, which the agent reads as a
message.

- Changing a seat's `tools:` invalidates its whole cache (tools render first). Batch roster changes.
- A stable seat set gets cache reads on every dispatch; a roster churning every session never warms.

## When NOT to spawn a subagent

A subagent starts with a fresh, uncached context and re-reads everything at full price. It pays off
when its work would otherwise **flood the parent's context** - a wide search, a long log, twenty
files skimmed for one - and returns a summary. It does not pay off for two tool calls the parent
could make: delegating one `grep` costs more than running it.

- **Fan out** independent, voluminous work - parallel wall-clock and context savings.
- **Inline** small work with small output.
- Never dispatch a seat to hand back something the parent already has.

## Putting it together

The savings come from the **bottom** of the roster (mechanical seats on `haiku` + `low`, bounded by
`maxTurns`) and from **context discipline on every seat** (path-scoped rules, narrow tools, stable
bodies) - not from downgrading the thinking seats. Show the allocation in the setup-plan echo so a
human sees it was decided. A seat with `model:` or `effort:` unset is a bug.

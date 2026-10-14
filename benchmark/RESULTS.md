# Benchmark results

**English** · [日本語](RESULTS.ja.md)

What adopting `harness-bootstrap` buys, against the three things you would otherwise do: nothing,
the same by hand, or plain prompting with no control layer. Every figure is counted from files on
disk or produced by a real run, and one command reproduces them:

```bash
python benchmark/benchmark.py
```

## At a glance

| | No harness | harness-bootstrap |
|---|---:|---:|
| Known-bad actions blocked (88 hook payloads) | **0** | **88** |
| Bytes of harness you author yourself | **667,658** | **0** |
| Rule bytes loaded into every agent session | **0** | **21,016** |
| Time to stand it up | - | under 2s |

The third row is not in our favour. A bare agent carries no rules because there are none to
enforce. That is the trade, and a benchmark that hid it would not be worth reading.

## Baseline A - no harness at all

The eval's own known-bad payloads, sent to a generated harness and to a bare repo. Both repos have
identical files and git history; the only difference is `.claude/`.

```mermaid
%%{init: {"xyChart": {"height": 260, "width": 640}, "themeVariables": {"xyChart": {"plotColorPalette": "#2D6A4F"}}}}%%
xychart-beta horizontal
    title "Known-bad payloads blocked, of 88"
    x-axis ["Bare repo", "harness-bootstrap"]
    y-axis "Blocked" 0 --> 88
    bar [0, 88]
```

The bare repo has 0 hook files and no `settings.json`, so none of the 88 payloads had a hook to
receive them. "Nothing stopped it" is demonstrated, not asserted: the script performs the actions
in the bare repo and checks them by effect.

| Action in the bare repo | Result | Evidence |
|---|---|---|
| Read `.env` | COMPLETED | 51 bytes read, including `API_KEY` |
| Commit straight to the default branch | COMPLETED | `HEAD` moved on `main` |
| Commit `stuff` with an AI-attribution trailer | COMPLETED | landed, trailer present |
| Edit an Accepted ADR | COMPLETED | file grew 25 to 53 bytes |

The harness is the eval's: scaffolded with the `VARS` flags in `guardrail_eval.py`, `hooks_strict`,
`long` and `db` among them. A default install carries fewer hooks than the one measured. The
guardrails are hooks and deny rules - shell scripts, exit codes, glob matching - so no model is
consulted and the result cannot depend on the model. This is the claim the project rests on.

## Baseline B - by hand

What you would author yourself to stand up the same harness, measured by scaffolding one and
weighing what landed.

| Kind | Files | Bytes |
|---|---:|---:|
| Scripts | 12 | 329,568 |
| Hooks | 15 | 137,519 |
| Rules | 16 | 77,269 |
| Commands | 21 | 54,622 |
| Agents | 9 | 27,946 |
| Docs scaffolding | 15 | 18,492 |
| Root files | 8 | 17,370 |
| `settings.json` | 1 | 4,872 |
| **Total** | **97** | **667,658** |

About 185,400 estimated tokens if a model authored it instead.

- **This is the part you do not author, not the whole job.** You still write `tech-stack.md`,
  `coding-standards.md`, `git-workflow.md`, the orchestrator's routing table and each dev agent's
  scope. Those ship as no asset on purpose: they are decisions about your repo.
- **The scripts row is the most arguable.** Those twelve are working tools (graph scanners, the
  task board CLI, the verification planner, the toggle, the checkers), not configuration. A team
  doing this by hand might not build them, which leaves 338,090 bytes.

No figure in hours: hours are not measurable from a repository.

## Baseline C - direct LLM calls, no control layer

The measurable part is context. A rule without `paths:` frontmatter loads into every session of
every agent. A path-scoped rule loads only when a matching file is touched.

```mermaid
%%{init: {"xyChart": {"height": 260, "width": 640}, "themeVariables": {"xyChart": {"plotColorPalette": "#5A189A"}}}}%%
xychart-beta horizontal
    title "Rule bytes, by when they load"
    x-axis ["Every session", "Only on a match"]
    y-axis "KB" 0 --> 65
    bar [21.0, 62.4]
```

| | Rules | Bytes | Tokens (est.) |
|---|---:|---:|---:|
| Bare agent, no harness | 0 | 0 | 0 |
| Unconditional, always loaded | 7 | 21,016 | ~5,838 |
| Path-scoped, loaded on demand | 10 | 62,365 | ~17,324 |

75% of rule content stays out of the default session. The seven that stay are the ones no glob can
match: `00-overview`, `agent-guardrails`, `task-tracking`, `conventional-commits` (it governs commit
*messages*, not files), `output-style` (how the agent writes), and `model-policy` and
`ai-governance`, which decide what may be sent where before any file is touched. The table counts
every flag on; `ai-governance` ships only with `ai` and `output-style` only with `terse`. Seat tiers
live in the path-scoped `model-tiers`.

**Not measured, and not claimed:** whether an agent's code is better with a harness. Output
quality, task success, time to a correct change and review burden cannot be counted from a
repository. Baseline A measures enforcement, not judgment.

## Process - what a session carries and what one change costs

```mermaid
%%{init: {"xyChart": {"height": 260, "width": 640}, "themeVariables": {"xyChart": {"plotColorPalette": "#1D3557"}}}}%%
xychart-beta horizontal
    title "Simulated mission: review and suite runs"
    x-axis ["Without the ledger", "With the ledger"]
    y-axis "Gate runs" 0 --> 17
    bar [17, 11]
```

- **What every session carries** (`AGENTS.md`, `CLAUDE.md`, the unconditional rules): 26,169 bytes
  in 8 files with `ui`, `db`, `ai`, `ddd` and `tests` on, 23,098 bytes in 7 files with `tests` only.
- **Who runs each tier:** Inline is the main session, Direct the owning seat called straight,
  Standard the owning seat with a task file only when the work must survive a compaction, Guarded
  the orchestrator, one at a time.
- **The review gate per change class** (`verify-plan.py`): a docs-only or config-only diff needs no
  review seat and no test run; one source file earns code review and the full suite once; auth code
  and a dependency bump add security review. The secret scan always runs.
- **The verification ledger:** a simulated mission (3 units, a final check, a fix round, a
  re-review) falls from 17 gate runs to 11; `guard-agent-spawn` refuses the other 6 with a ledger
  line to cite.
- **Resuming a task with 40 session-log rows:** 8,253 bytes read whole, 5,901 with the log bounded
  by `task.py`, and 966 bytes (~268 tokens) for the `task.py resume` digest.

## Scaffold

A first run takes **under 2s** (1.62s here), creates 120 paths and exits 0. A re-run reports `KEPT`
and clobbers nothing. An unresolved `{{VAR}}` makes it exit non-zero rather than ship a placeholder.

The comparison is not seconds against seconds. It is deterministic file copying against a model
generating ~185,000 output tokens, which takes minutes, costs money and can hallucinate a hook that
does not run.

## For the record - against the predecessor skill

This benchmark used to compare against `project-bootstrap`, the skill this one replaced. The figure
is kept because it is true, and demoted because it answers "did our rewrite beat our last attempt",
which matters to nobody choosing whether to adopt this.

Read path: 234,196 to 136,249 bytes, -42%. It moves whenever the skill's reference docs change, in
either direction. A benchmark that only ever improves is a marketing document.

## Methodology

- **Bytes are exact**, counted from disk. **Tokens are estimated** at 3.6 chars/token without an
  `ANTHROPIC_API_KEY`; with a key the script calls the real `count_tokens` endpoint. The source is
  labelled either way.
- **Baseline A imports the eval's payload suite** rather than re-declaring it, so the safety figure
  cannot drift from the suite. It runs the `.sh` flavour and is skipped with a message if `bash` is
  unavailable.
- **Baseline A counts only the 88 must-block payloads** of the eval's hook suite. The eval's full
  290 cases per flavor include must-allow cases and the scaffold, ledger and toggle suites, which
  measure other properties and are not safety wins.
- **The bare repo is built from the same fixtures** and then has `.claude/` removed. Without the
  `.env` or the ADR, "nothing was blocked" would be trivially true.
- **Not measured here:** cost across model tiers (`benchmark/model_cost.py` models it) and
  per-dispatch tool-schema cost, which needs runtime instrumentation.

Hardware: Windows 11, Python 3.13. Scaffold timings are wall-clock, single run.
`python benchmark/benchmark.py --skip-guardrails` skips Baseline A, the only slow part. Two runs at
once need `HARNESS_BENCH_WORKDIR` pointing at separate directories, or each deletes the other's
harness mid-run.

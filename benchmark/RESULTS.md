# Benchmark results

## Summary

`harness-bootstrap` against `project-bootstrap`, the predecessor skill it replaces:

| | project-bootstrap | harness-bootstrap | Change |
|---|---:|---:|---:|
| Read path (bytes the model must pull into context) | 234,196 | 85,641 | -63% |
| Read path (files read) | 24 | 7 | -71% |
| Write path (bytes the model must author) | 95,064 | 14,595 | -85% |
| Rule content kept out of the default session | - | 66% | - |
| Scaffold time | - | ~0.2s | - |

## What is measured and what is estimated

- **Byte columns are exact.** They are counted from the files on disk.
- **Token columns are estimated** at 3.6 chars/token, because the run that produced this file had no
  API key. Tokens are what you are billed for and they are not a fixed multiple of bytes, so treat
  the token columns as an order of magnitude, not a quote. The script emits measured tokens when
  `ANTHROPIC_API_KEY` is present, and labels the source either way.
- **The write-path baseline is a proxy.** The old skill's output was not deterministic; it varied per
  run. It is sized here by the bytes of the template packs it had to reproduce, which is the closest
  countable stand-in, and is if anything conservative: the old skill also authored the rules, the
  agents, `CLAUDE.md` and the docs tree from prose briefs, none of which is counted here.
- **This measures the harness, not the outcome.** A cheaper bootstrap that produced a worse harness
  would be a bad trade. The correctness claims - hooks that actually block, rules that actually load,
  a task board the orchestrator can actually see - are covered by the tests in the repo, not by this
  benchmark.
- **Cost across model tiers is modelled, not measured.** `benchmark/model_cost.py` computes what a
  roster would cost from published prices and a stated workload. Its assumptions are at the top of
  the file and are editable. It cannot tell you whether a cheaper roster produces acceptable work;
  that is a quality question, and `eval/` measures only the safety floor.
- **Not measured: the per-dispatch cost of tool schemas.** Every tool in an agent's `tools:` list
  ships its schema on every request of that agent's run. Narrow grants reduce that, and the roster
  applies them, but quantifying it needs runtime instrumentation this script does not have.

## 1. Read path - what the model must pull into context to do one bootstrap

The old skill kept its hooks, commands, rules and templates as fenced code blocks inside markdown
"packs". To use them, the model had to read all of them.

| | Files read | Bytes | Tokens (est.) |
|---|---:|---:|---:|
| project-bootstrap | 24 | 234,196 | ~65,000 |
| harness-bootstrap | 7 | 85,641 | ~23,800 |
| **Reduction** | **-71%** | **-63%** | **-63%** |

The new skill reads `SKILL.md` plus six reference docs. It never reads `assets/`: the scaffolder
copies those files directly, so they never enter the context window at all.

## 2. Write path - what the model must generate as output tokens

Output tokens cost 5x input across every current model, and the old skill's core loop was *read 1,350
lines of assets, then retype them*.

| | Files authored | Bytes | Tokens (est.) |
|---|---:|---:|---:|
| project-bootstrap | 11 packs -> ~60 files | 95,064 | ~26,400 |
| harness-bootstrap | 3 + `vars.json` | 14,595 | ~4,100 |
| **Reduction** | | **-85%** | **-85%** |

What the new skill still authors by hand is what cannot be templated: `tech-stack.md`,
`coding-standards.md`, `git-workflow.md`, the orchestrator's routing table, and each dev agent's
scope. Those are decisions about a specific repo. Everything else is a file copy.

## 3. Session tax - the cost paid on every session, not once

A file in `.claude/rules/` with no `paths:` frontmatter loads at launch into every session of every
agent, at the same priority as `CLAUDE.md`. It is not a one-time cost; it is rent.

| | Rules | Bytes | Tokens (est.) |
|---|---:|---:|---:|
| Unconditional (always loaded) | 6 | 25,303 | ~7,000 |
| Path-scoped (loaded on demand) | 8 | 49,394 | ~13,700 |

**66% of the rule content is kept out of the default session.** The database agent no longer carries
the frontend rules; the UI agent no longer carries the migration-safety rules. They load when Claude
actually touches a matching file.

The six that stay unconditional are the ones no glob can scope: `00-overview`, `agent-guardrails`,
`task-tracking`, `conventional-commits` (which governs commit *messages*, not files, so no `paths:`
pattern can ever match it; that is why it is deliberately kept under 25 lines), and the two
governance rules `model-policy` and `ai-governance`, which decide what may be sent where *before* any
file is touched.

## 4. Scaffold - the deterministic path

| | |
|---|---|
| First run | **~0.2s** (varies 0.15-0.30s across runs), 73 paths created, exit 0 |
| Re-run (idempotency) | reports `KEPT`, 0 conflicts, nothing clobbered |
| Unresolved `{{VAR}}` | exits non-zero, rather than shipping a placeholder into a rule |

The comparison is not a fifth of a second against some other number of seconds. It is a fifth of a
second of deterministic file copying against a model generating ~26,000 output tokens, which takes
minutes of wall-clock, costs real money, and can hallucinate a hook that does not run.

## Reproducing

```bash
python benchmark/benchmark.py
```

Set `ANTHROPIC_API_KEY` to replace the estimated token columns with measured ones from the
`count_tokens` endpoint.

Baseline: `project-bootstrap`, the predecessor skill, at the commit it was replaced.
Hardware: Windows 11, Python 3.13. Scaffold timings are wall-clock, single run.

# claude-harness-bootstrap

Two Claude Code skills that stand up a complete, cost-aware AI-agent harness in any repository.

| Skill | What it does |
|---|---|
| [`harness-bootstrap`](harness-bootstrap/) | Generates the `.claude/` folder (agents, path-scoped rules, commands, hooks, settings), the `docs/` tree, and `AGENTS.md` + `CLAUDE.md`, so the repo runs under orchestrator-driven task control. Also has a read-only **audit mode** that builds an audit control plane beside untouched source. |
| [`spec-builder`](spec-builder/) | Generates the 13-section BA specification set under `docs/specs/` from any input — an idea, a transcript, meeting notes, an existing PRD, or legacy docs. |

They compose: `spec-builder` writes the requirements, `harness-bootstrap` builds the machine that
implements them.

## Install

```bash
git clone https://github.com/nguyenhx2/claude-harness-bootstrap.git
cp -r claude-harness-bootstrap/harness-bootstrap ~/.claude/skills/
cp -r claude-harness-bootstrap/spec-builder     ~/.claude/skills/
```

Then in any repo, ask Claude Code to "set up the base" / "chuẩn hoá .claude" / "khởi tạo workspace cho
AI agents", or invoke `/harness-bootstrap` directly.

Requires Python 3 for the scaffolder. Without it the skill still works — the assets are real files, so
they can be copied and edited by hand — but the deterministic path is faster and safer.

## What makes this different

**The assets are real files, not prose to retype.** Hooks, commands, rules, agent bodies, and doc
templates live under `assets/` as actual files. `scripts/scaffold.py` copies them with `{{VAR}}`
substitution and conditional blocks. The model spends its tokens on the decisions — the roster, the
scope, the reconciliation — not on transcribing 1,300 lines of boilerplate it just read.

**Every agent has a cost budget.** Each generated agent carries an explicit `model:`, `effort:`,
narrow `tools:`, and `maxTurns` where a loop means something has already gone wrong. An unset `model:`
means `inherit`, which silently bills mechanical work at the caller's tier — the skill treats that as a
bug, not a default.

**Rules load only when relevant.** A file in `.claude/rules/` without `paths:` frontmatter loads into
every session of every agent, forever. This skill path-scopes everything that can be scoped, so the
database agent does not carry the frontend rules and vice versa. Only four rules load unconditionally.

**The generated files are prompt-cache stable.** No timestamps, no generation dates, no run IDs
anywhere in any asset. A single volatile byte in a system prompt cold-misses the cache on every future
run; cache reads cost about a tenth of fresh input.

**The scaffolder never clobbers.** It reports `ADDED` / `KEPT` / `CONFLICT` and refuses to overwrite.
Conflicts are the brownfield reconciliation queue, not an error.

## The cost model, briefly

Published multi-agent advice mostly predates current pricing. Opus is now **1.67×** Sonnet, not 5×:

| Model | Alias | Input $/1M | Output $/1M |
|---|---|---|---|
| Claude Opus 4.8 | `opus` | $5.00 | $25.00 |
| Claude Sonnet 5 | `sonnet` | $3.00 | $15.00 |
| Claude Haiku 4.5 | `haiku` | $1.00 | $5.00 |

So "put the cheap model everywhere except the review gate" is no longer where the money is. The levers
that actually move the bill, in order:

1. **`effort:`** — controls thinking depth, output length, and turn count. Most rosters never set it,
   so every agent silently inherits the human's session level.
2. **Context hygiene** — path-scoped rules, narrow tool grants (every tool ships its schema on every
   request), `maxTurns` as a circuit breaker.
3. **Model tier** — still a real 3–5× saving at the *Haiku* end. The Opus-vs-Sonnet call is a 1.67×
   dial: make it on quality grounds and stop agonizing.
4. **Prompt-cache stability** — a ~90% discount you get for free, or lose for free.

Full reasoning: [`harness-bootstrap/reference/cost-model.md`](harness-bootstrap/reference/cost-model.md).

## Layout

```
harness-bootstrap/
  SKILL.md                  navigation only - the decisions, not the content
  reference/                read at the step that needs it
    cost-model.md             model + effort + context budget doctrine
    roster.md                 which agents to field, and their exact config
    intake.md                 the questionnaire
    codebase-analysis.md      brownfield discovery -> Inventory Report
    task-control.md           the orchestration loop, crash recovery, merge discipline
    audit-mode.md             read-only multi-repo audit control plane
  assets/                   real files, copied verbatim with {{VAR}} substitution
    claude/{agents,rules,commands,hooks}/
    docs/{templates,context}/
    audit/
    manifest.json
  scripts/scaffold.py       deterministic, stdlib-only, never overwrites

spec-builder/
  SKILL.md
  reference/{elicitation,writing-rules}.md
  assets/specs/             13 section templates
  scripts/scaffold.py
```

## License

MIT — see [LICENSE](LICENSE).

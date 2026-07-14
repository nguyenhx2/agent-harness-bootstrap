# claude-harness-bootstrap

Point Claude Code at any repo and get a working AI-agent setup: a roster of agents that know their
scope and their budget, guardrails that cannot be talked around, and a task board on disk that
survives the model forgetting everything.

[![eval](https://github.com/nguyenhx2/claude-harness-bootstrap/actions/workflows/eval.yml/badge.svg)](https://github.com/nguyenhx2/claude-harness-bootstrap/actions/workflows/eval.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Skills: 2](https://img.shields.io/badge/skills-2-blue.svg)](#the-two-skills)
[![Agents: 15](https://img.shields.io/badge/agents-15%20%2B%201%20template-blue.svg)](harness-bootstrap/assets/claude/agents/)
[![Guardrail eval: 15/15](https://img.shields.io/badge/guardrail%20eval-15%2F15-brightgreen.svg)](eval/guardrail_eval.py)
[![Claude Code compatible](https://img.shields.io/badge/Claude%20Code-compatible-5A189A.svg)](https://claude.com/claude-code)
[![Release](https://img.shields.io/github/v/release/nguyenhx2/claude-harness-bootstrap?display_name=tag&sort=semver)](https://github.com/nguyenhx2/claude-harness-bootstrap/releases)

## Install

**[Download the latest release](https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest)**
- or install both skills in one line:

```bash
curl -fsSL https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest/download/claude-harness-bootstrap.zip -o skills.zip \
  && unzip -o skills.zip -d ~/.claude/skills/ \
  && rm skills.zip
```

<details>
<summary><b>Other ways to install</b></summary>

<br>

**One skill at a time** (stable URLs, always the newest release):

```bash
# harness-bootstrap only
curl -fsSL https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest/download/harness-bootstrap.zip -o hb.zip
unzip -o hb.zip -d ~/.claude/skills/ && rm hb.zip

# spec-builder only
curl -fsSL https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest/download/spec-builder.zip -o sb.zip
unzip -o sb.zip -d ~/.claude/skills/ && rm sb.zip
```

**A pinned version**, if you need a specific build:

```bash
V=1.2.0
curl -fsSL "https://github.com/nguyenhx2/claude-harness-bootstrap/releases/download/v${V}/harness-bootstrap-v${V}.zip" -o hb.zip
unzip -o hb.zip -d ~/.claude/skills/ && rm hb.zip
```

**Verify the download:**

```bash
curl -fsSLO https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest/download/SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
```

**From source:**

```bash
git clone https://github.com/nguyenhx2/claude-harness-bootstrap.git
cp -r claude-harness-bootstrap/harness-bootstrap ~/.claude/skills/
cp -r claude-harness-bootstrap/spec-builder      ~/.claude/skills/
```

</details>

Requires **Python 3**. Check what you installed:

```bash
cat ~/.claude/skills/harness-bootstrap/VERSION
```

## Use it

In any repo, tell Claude Code:

```text
set up the base
```

or invoke `/harness-bootstrap` directly. It also triggers on "chuan hoa .claude", "khoi tao workspace
cho AI agents", "set up agents for this repo".

It will:

1. **Read your code first.** On an existing repo it produces an inventory (stack, modules, conventions,
   risky operations) and shows it to you before touching anything.
2. **Ask you ~20 questions**, in batches. On an existing repo most answers are pre-filled from the code.
3. **Show you the plan** - what it will create, keep, and modify, and the roster with each agent's model
   and effort - and wait for your go-ahead.
4. **Scaffold it** in about a fifth of a second, deterministically. It never overwrites a file you wrote.

No specs yet? Run `/spec-builder` first, then come back.

## What you get

```text
.claude/
  agents/           15 agents, each with an explicit model, effort, tool grant and turn limit
  rules/            14 rules - 6 always loaded, 8 that load only when you touch a matching file
  commands/         /new-task /task-resume /implement-fr /review-changes /secret-scan /deploy ...
  hooks/            6 hooks that physically block bad actions (see below)
  settings.json     permission allow/deny + hook registration
docs/
  tasks/
    master-plan.md      the board: one row per task
    active/TASK-NNN.md  goal, acceptance criteria, and a session log the agent writes AS IT WORKS
  specs/ requirements/ architecture/ context/ templates/
AGENTS.md + CLAUDE.md
```

The agents are wired: an `orchestrator` routes work, `spec-guardian` locks the contract before anyone
codes, a `<domain>-dev` implements, `qa-test` tests, and `code-reviewer` + `security-reviewer` run as
gates that **cannot edit code**.

## The three things it actually buys you

### 1. Your agents cannot do the dangerous thing

Not "are told not to" - **cannot**. The guardrails are shell scripts and glob rules, so they hold no
matter which model is driving:

| An agent tries to | Result |
|---|---|
| Read `.env`, a private key, `~/.ssh/`, `.npmrc` | Blocked |
| Read a path you classified as Restricted | Blocked - it never sees the data, so it cannot send it to any model |
| Commit straight to `main` | Blocked |
| Edit an Accepted ADR | Blocked |
| Ship a commit with an AI-attribution trailer | Blocked |
| Write a non-conventional commit message | Blocked |

```bash
python eval/guardrail_eval.py   # fires 15 known-bad payloads at a real generated harness -> 15/15
```

Swap every agent from Opus to Haiku and re-run: identical result.

<p align="center">
  <img src="docs/assets/control-layers.svg" alt="Control layers, hard (enforced) to soft (advisory)" width="820">
</p>

Rules in `.claude/rules/` are **advice** - the model can drift from them, especially after compaction.
Hooks, `permissions.deny`, `tools:` and `maxTurns` are **enforcement**. This repo is explicit about
which is which, and moves a control from soft to hard whenever it can be expressed as a file check.

### 2. The IDE can die and you lose nothing

Agent state lives in committed markdown, written **as the agent works** - not held in a context window
that compaction will summarise away.

<p align="center">
  <img src="docs/assets/memory-hierarchy.svg" alt="Memory tiers: always-RAM, lazy-RAM, disk, archive" width="820">
</p>

Crash mid-feature, and on the next session an agent with an empty context:

1. scans `docs/tasks/active/` for unfinished work, before accepting anything new,
2. reads the board and the task file's session log,
3. reconciles orphaned branches and worktrees against the board,
4. verifies against `git`, not against anything it "remembers",
5. carries on from the last recorded row.

`/task-resume` does this for you. The rule that makes it work: **a gate counts as passed only when the
session log records it.** An agent's "done" is a claim you verify, never a fact.

Full model, including the resume protocol: [**`docs/CONTEXT-MANAGEMENT.md`**](docs/CONTEXT-MANAGEMENT.md).

### 3. You stop paying for tokens you did not choose to spend

| Default behaviour | What you get instead |
|---|---|
| An agent with no `model:` inherits the caller's tier - so a log-summarising agent silently bills at Opus rates | Every agent has an explicit `model:` and `effort:` |
| A rule with no `paths:` loads into every session of every agent, forever | 8 of 14 rules are path-scoped. **66% of rule content never enters a default session** |
| An agent that loops burns full context on every turn, unbounded | `maxTurns` on every seat where a loop means something already went wrong |
| Omitting `tools:` inherits every tool on the machine, schema included, on every request | Narrow grants. Reviewers get `Read, Grep, Glob, Bash` and nothing else |

```bash
python benchmark/model_cost.py   # what one feature costs, by roster profile
```

| Roster | USD / feature |
|---|---:|
| all-opus, no effort tuning (what you get by not choosing) | 3.53 |
| **default roster** | **2.38** |
| sonnet-only | 1.92 |
| haiku-only | 0.61 |

Opus is **1.67x** Sonnet, not 5x - so tier is a smaller dial than most advice assumes, and `effort:` is
a bigger one. The default roster is deliberately *not* the cheapest: it spends the difference on Opus
review gates. Take the other side of that bet by editing one table in
[`roster.md`](harness-bootstrap/reference/roster.md).

## The whole thing, in one picture

<p align="center">
  <img src="docs/assets/harness-architecture.svg" alt="Harness reference architecture: seven layers, drawn bottom-up, with the model in a swappable slot near the top and every layer beneath it deterministic and model-agnostic" width="820">
</p>

The model sits in a slot. Above it, the orchestration flow runs on whichever model you gave it; below
it, nothing knows or cares which model that is - the hooks are shell scripts, the deny rules are globs,
and the task board is markdown in git. Move a seat from `opus` to `haiku` and the layers under the slot
do not change: your agent still cannot read `.env`, still cannot commit to `main`, and still writes its
session log to the same file.

One thing that diagram is blunt about, so you are not surprised later: you can swap the **tier**
(`opus` / `sonnet` / `haiku` / `fable`), but not the **vendor**. Claude Code's frontmatter accepts
nothing else, so pointing this roster at a self-hosted or third-party model is a port, not a config
change.

## The two skills

| Skill | Use it when |
|---|---|
| [**`harness-bootstrap`**](harness-bootstrap/) | You want agents, rules, hooks and a task board in a repo. Also has an **audit mode** that builds a read-only control plane beside source it must never modify. |
| [**`spec-builder`**](spec-builder/) | You have an idea, a transcript, or a pile of legacy docs, and you need a 13-section BA spec set. It **never invents a requirement** - anything unstated becomes a flagged open issue. |

```mermaid
flowchart LR
    IN[/"Idea, transcript,<br/>PRD, legacy docs"/]
    SB["spec-builder"]
    SPECS[/"docs/specs/ 01-13<br/>the contract"/]
    HB["harness-bootstrap"]
    SC["scaffold.py"]
    OUT[/".claude/ + docs/<br/>AGENTS.md + CLAUDE.md"/]

    IN --> SB --> SPECS --> HB --> SC --> OUT

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA
    class SC det
    class SB,HB mod
    class IN,SPECS,OUT art
```

Green runs for free. Purple costs tokens. More diagrams: [`docs/FLOWS.md`](docs/FLOWS.md).

## Governance

Three rules ship into every repo you bootstrap:

- **[`model-policy.md`](harness-bootstrap/assets/claude/rules/model-policy.md)** - you classify your data
  (Public / Internal / Confidential / Restricted) and say which models may process each class. Restricted
  paths get denied at the read boundary, so an agent cannot leak what it cannot open.
- **[`ip-compliance.md`](harness-bootstrap/assets/claude/rules/ip-compliance.md)** - dependency licence
  allow/deny, the AGPL-on-SaaS trigger, and a diff check the reviewers can actually run.
- **[`ai-governance.md`](harness-bootstrap/assets/claude/rules/ai-governance.md)** - which actions need a
  human who saw the specific action, not a config flag.

You supply the answers at intake. The skill never invents a policy for your company.

## Reference

| | |
|---|---|
| [`cost-model.md`](harness-bootstrap/reference/cost-model.md) | How model, effort, tools and cache stability actually affect the bill |
| [`roster.md`](harness-bootstrap/reference/roster.md) | Every agent's model, effort, tools, turn limit - and why |
| [`task-control.md`](harness-bootstrap/reference/task-control.md) | The orchestration loop, crash recovery, merge discipline |
| [`audit-mode.md`](harness-bootstrap/reference/audit-mode.md) | Read-only multi-repo audit control plane |
| [`ba-standards.md`](spec-builder/reference/ba-standards.md) | Which standards the 13 spec sections draw on (29148, BABOK v3, ISO 25010, MoSCoW) |
| [`CONTEXT-MANAGEMENT.md`](docs/CONTEXT-MANAGEMENT.md) | RAM vs disk, the resume protocol, hard vs soft controls |
| [`ASSESSMENT.md`](docs/ASSESSMENT.md) | An honest scorecard, including what this does **not** do |
| [`RESULTS.md`](benchmark/RESULTS.md) | The benchmark numbers and their caveats |
| [`RELEASING.md`](docs/RELEASING.md) | Semver, artifacts, notes format |

## Numbers

Reproduce with `python benchmark/benchmark.py`. Measured against the predecessor skill this replaces.

| | Before | After | Δ |
|---|---:|---:|---:|
| Bytes the model must read to bootstrap a repo | 234,196 | 83,339 | **-64%** |
| Bytes the model must write as output | 95,064 | 14,595 | **-85%** |
| Rule content kept out of the default session | - | 49,394 of 74,697 B | **66%** |
| Scaffold time | - | ~0.2 s, 73 files | - |
| Guardrail eval | - | **15/15** | - |

Byte figures are exact. Token figures in [`RESULTS.md`](benchmark/RESULTS.md) are estimated unless you
set `ANTHROPIC_API_KEY`, in which case the script counts them for real. The cost-per-feature table above
is modelled from published prices, not measured - it tells you what a roster costs, not whether a cheaper
one does acceptable work. `eval/` tests the safety floor; the quality ceiling is
[an open question](eval/README.md).

## Contributing

- **No invented numbers.** A script in `benchmark/` or `eval/` must print any figure you cite.
- **Assets stay byte-stable.** No timestamps or run IDs under `assets/` - they land in a system prompt
  and cold-miss the prompt cache forever.
- **No em-dashes.** Plain hyphens.

Releases follow [`docs/RELEASING.md`](docs/RELEASING.md). A tag with no artifact is not a release.

MIT - see [LICENSE](LICENSE).

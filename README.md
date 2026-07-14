# claude-harness-bootstrap

Give an AI agent a repo it can actually understand, and a harness it cannot escape.

[![eval](https://github.com/nguyenhx2/claude-harness-bootstrap/actions/workflows/eval.yml/badge.svg)](https://github.com/nguyenhx2/claude-harness-bootstrap/actions/workflows/eval.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Agents: 15](https://img.shields.io/badge/agents-15%20%2B%201%20template-blue.svg)](harness-bootstrap/assets/claude/agents/)
[![Guardrail eval: 15/15](https://img.shields.io/badge/guardrail%20eval-15%2F15-brightgreen.svg)](eval/guardrail_eval.py)
[![Claude Code compatible](https://img.shields.io/badge/Claude%20Code-compatible-5A189A.svg)](https://claude.com/claude-code)
[![Release](https://img.shields.io/github/v/release/nguyenhx2/claude-harness-bootstrap?display_name=tag&sort=semver)](https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest)

## Two skills

| | What it makes | You need it when |
|---|---|---|
| [**`spec-builder`**](spec-builder/) | **The input an AI can understand.** A 13-section spec set under `docs/specs/`: requirements with stable IDs, acceptance criteria, a data model, mandatory security NFRs. Built from an idea, a transcript, meeting notes, or a pile of legacy docs. It **never invents a requirement** - anything unstated becomes a flagged open issue. | The AI is guessing what to build, because nobody wrote it down. |
| [**`harness-bootstrap`**](harness-bootstrap/) | **The harness an AI runs inside.** `.claude/` with 15 agents, 14 rules, 6 blocking hooks and a deny list, plus `docs/tasks/`, a board that survives a crash. Fitted to *your* repo: it reads your code first, then builds the harness around what is actually there. | The AI can build, but nothing stops it doing damage and nothing survives when it forgets. |

They cover the two ends of the same gap: **the AI does not know what you want, and nothing constrains
what it does.**

<p align="center">
  <img src="docs/assets/ai-dlc-flow.svg" alt="AI-DLC flow: spec-builder produces the contract, harness-bootstrap builds the harness, then the delivery loop runs inside it" width="860">
</p>

Green is deterministic and free. Purple costs tokens. The loop on the right runs the same on any model
tier, because the gates around it are shell scripts rather than judgment.

---

## The problems these solve

**Your agent does not know what "done" means.** So it invents requirements, and they look plausible
enough to merge. `spec-builder` writes the contract first, with acceptance criteria the agent can be
checked against, and refuses to fill a gap with a guess.

**Your agent is one bad turn from real damage.** It can read `.env`, commit to `main`, edit an accepted
decision record. Telling it not to in a rules file is advice, and after a context compaction it will
not remember the advice. Hooks and a deny list block those actions without asking the model.

**Your agent forgets, then reports success anyway.** The IDE crashes, the context compacts, the session
ends, and the work existed nowhere but in a window that just closed. Here the state lives in committed
markdown the agent writes *as it works*, so a fresh agent resumes exactly where the last one stopped.

---

## Install

**[Download the latest release](https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest)**,
or install both skills in one line:

```bash
curl -fsSL https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest/download/claude-harness-bootstrap.zip -o skills.zip \
  && unzip -o skills.zip -d ~/.claude/skills/ \
  && rm skills.zip
```

Requires **Python 3**. Confirm what you installed:

```bash
cat ~/.claude/skills/harness-bootstrap/VERSION
```

<details>
<summary><b>One skill at a time, a pinned version, checksums, or from source</b></summary>

<br>

```bash
# one skill at a time (stable URLs, always the newest release)
curl -fsSL https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest/download/harness-bootstrap.zip -o hb.zip
unzip -o hb.zip -d ~/.claude/skills/ && rm hb.zip

curl -fsSL https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest/download/spec-builder.zip -o sb.zip
unzip -o sb.zip -d ~/.claude/skills/ && rm sb.zip
```

```bash
# a pinned version
V=1.0.0
curl -fsSL "https://github.com/nguyenhx2/claude-harness-bootstrap/releases/download/v${V}/harness-bootstrap-v${V}.zip" -o hb.zip
unzip -o hb.zip -d ~/.claude/skills/ && rm hb.zip
```

```bash
# verify the download
curl -fsSLO https://github.com/nguyenhx2/claude-harness-bootstrap/releases/latest/download/SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
```

```bash
# from source
git clone https://github.com/nguyenhx2/claude-harness-bootstrap.git
cp -r claude-harness-bootstrap/harness-bootstrap ~/.claude/skills/
cp -r claude-harness-bootstrap/spec-builder      ~/.claude/skills/
```

</details>

---

## Use it

**Brownfield** - a repo that already has code:

```text
set up the base
```

It reads your code before writing anything: stack, modules, conventions, risky operations. You get
that inventory first, most of the intake is pre-filled from it, and you are only asked what the code
cannot tell it. Existing files are **reconciled, not overwritten** - anything you wrote is reported as
a conflict for you to resolve.

**Greenfield** - an idea and an empty repo:

```text
/spec-builder     then     /harness-bootstrap
```

Specs first, and the agent roster comes out of them: cluster the FRs into domains, one dev agent per
domain, each scoped to the module path it will own.

Either way you see the plan - what will be created, kept and modified, plus every agent's model and
effort budget - and nothing is written until you approve it. The scaffold itself takes about a fifth
of a second.

### What lands in your repo

```text
.claude/
  agents/           15 agents, each with an explicit model, effort, tool grant and turn limit
  rules/            14 rules - 6 always loaded, 8 that load only when you touch a matching file
  commands/         /new-task /task-resume /implement-fr /review-changes /secret-scan /deploy ...
  hooks/            6 hooks that block bad actions before they happen
  settings.json     permission allow/deny + hook registration
docs/
  tasks/
    master-plan.md      the board: one row per task
    active/TASK-NNN.md  goal, acceptance criteria, and a session log the agent writes AS IT WORKS
  specs/ requirements/ architecture/ context/ templates/
AGENTS.md + CLAUDE.md
```

---

## What the harness guarantees

### It cannot do the dangerous thing

Not "is told not to". **Cannot.** The guardrails are shell scripts and glob rules:

| An agent tries to | Result |
|---|---|
| Read `.env`, a private key, `~/.ssh/`, `.npmrc` | Blocked |
| Read a path you classified as Restricted | Blocked. It never sees the data, so it cannot send it to any model |
| Commit straight to `main` | Blocked |
| Edit an Accepted ADR | Blocked |
| Ship a commit with an AI-attribution trailer | Blocked |

```bash
python eval/guardrail_eval.py   # 15 known-bad payloads at a real generated harness -> 15/15
```

Swap every agent from Opus to Haiku and re-run. Identical result: no model is in the loop.

<p align="center">
  <img src="docs/assets/control-layers.svg" alt="Control layers, hard (enforced) to soft (advisory)" width="820">
</p>

Rules in `.claude/rules/` are **advice**, and a model can drift from them after a compaction. Hooks,
`permissions.deny`, `tools:` and `maxTurns` are **enforcement**. A control moves from soft to hard the
moment it can be written as a file check.

### The IDE can die and you lose nothing

<p align="center">
  <img src="docs/assets/memory-hierarchy.svg" alt="Memory tiers: always-RAM, lazy-RAM, disk, archive" width="820">
</p>

State lives in committed markdown, written as the agent works, not in a context window that compaction
will summarise away. After a crash, an agent with an empty context scans `docs/tasks/active/`, reads
the session log, reconciles branches against the board, verifies against `git` rather than memory, and
continues from the last recorded row. `/task-resume` does it for you.

The rule that makes it work: **a gate counts as passed only when the session log records it.** An
agent's "done" is a claim you verify, never a fact.

Details: [`docs/CONTEXT-MANAGEMENT.md`](docs/CONTEXT-MANAGEMENT.md).

### You stop paying for tokens you did not choose to spend

| Default | Here |
|---|---|
| An agent with no `model:` inherits the caller's tier, so a log-summarising agent bills at Opus rates | Every agent has an explicit `model:` and `effort:` |
| A rule with no `paths:` loads into every session of every agent, forever | 8 of 14 rules are path-scoped. **66% of rule content never enters a default session** |
| An agent that loops burns full context every turn, unbounded | `maxTurns` on every seat where a loop means something already went wrong |
| Omitting `tools:` inherits every tool on the machine, schema included | Narrow grants. Reviewers get `Read, Grep, Glob, Bash` and nothing else |

| Roster | USD / feature |
|---|---:|
| all-opus, no effort tuning (what you get by not choosing) | 3.53 |
| **default roster** | **2.38** |
| sonnet-only | 1.92 |
| haiku-only | 0.61 |

Opus is **1.67x** Sonnet, not 5x, so tier is a smaller dial than most advice assumes and `effort:` is a
bigger one. The default roster is deliberately not the cheapest: it spends the difference on Opus review
gates. Take the other side of that bet by editing one table in
[`roster.md`](harness-bootstrap/reference/roster.md). These figures are modelled from published prices,
not measured - run `python benchmark/model_cost.py`.

---

## How the harness is built, and how it holds itself

<p align="center">
  <img src="docs/assets/generation-and-constraint.svg" alt="Where the agents, rules, commands and hooks come from, and how they hold each other in check" width="820">
</p>

Nothing in your `.claude/` folder is invented. Each agent, rule, hook and deny entry traces back to
something real: your code, your specs, or an answer you gave at intake, and `scaffold.py` copies the
rest from files on disk. Once it runs, the pieces hold each other: the orchestrator dispatches every
agent but cannot write product code, the reviewers gate the dev agents but cannot edit anything, the
board records what actually happened, and the hooks stop all of them without asking.

---

## The whole thing, in one picture

<p align="center">
  <img src="docs/assets/harness-architecture.svg" alt="Harness layers, with the model drawn as a swappable layer" width="820">
</p>

The model sits in a slot near the top. Every layer beneath it - the deny list, the hooks, the tool
grants, the board - is deterministic and unchanged when the model changes.

Model **tier** is swappable today: `opus`, `sonnet`, `haiku`, `fable`. Model **vendor** is not.
Re-pointing the roster at a self-hosted or third-party model is a port rather than a config change, and
no adapter ships here. See [`docs/ASSESSMENT.md`](docs/ASSESSMENT.md), Gap 2.

---

## Governance

Three rules ship into every repo you bootstrap. You supply the answers at intake; the skill never
invents a policy for your company.

- [**`model-policy.md`**](harness-bootstrap/assets/claude/rules/model-policy.md) - classify your data
  (Public / Internal / Confidential / Restricted) and say which models may process each class.
  Restricted paths are denied at the read boundary, so an agent cannot leak what it cannot open.
- [**`ip-compliance.md`**](harness-bootstrap/assets/claude/rules/ip-compliance.md) - dependency licence
  allow/deny, the AGPL-on-SaaS trigger, and a diff check the reviewers can run.
- [**`ai-governance.md`**](harness-bootstrap/assets/claude/rules/ai-governance.md) - which actions need
  a human who saw the specific action, not a config flag.

---

## Reference

| | |
|---|---|
| [`FLOWS.md`](docs/FLOWS.md) | Seven diagrams: the scaffolder, one feature end to end, context loading |
| [`CONTEXT-MANAGEMENT.md`](docs/CONTEXT-MANAGEMENT.md) | RAM vs disk, the resume protocol, hard vs soft controls |
| [`ASSESSMENT.md`](docs/ASSESSMENT.md) | Scorecard, including what this does not do |
| [`cost-model.md`](harness-bootstrap/reference/cost-model.md) | How model, effort, tools and cache stability affect the bill |
| [`roster.md`](harness-bootstrap/reference/roster.md) | Every agent's model, effort, tools, turn limit, and why |
| [`task-control.md`](harness-bootstrap/reference/task-control.md) | The orchestration loop, crash recovery, merge discipline |
| [`audit-mode.md`](harness-bootstrap/reference/audit-mode.md) | Read-only audit control plane, for source agents must never modify |
| [`ba-standards.md`](spec-builder/reference/ba-standards.md) | Which standards the 13 spec sections draw on |
| [`RESULTS.md`](benchmark/RESULTS.md) | Benchmark numbers and their caveats |
| [`RELEASING.md`](docs/RELEASING.md) | Semver, artifacts, note format |

### Numbers

Measured against the predecessor skill this replaces. Reproduce with `python benchmark/benchmark.py`.

| | Before | After | Δ |
|---|---:|---:|---:|
| Bytes the model must read to bootstrap a repo | 234,196 | 83,339 | **-64%** |
| Bytes the model must write as output | 95,064 | 14,595 | **-85%** |
| Rule content kept out of the default session | - | 49,394 of 74,697 B | **66%** |
| Scaffold time | - | ~0.2 s, 73 files | - |
| Guardrail eval | - | **15/15** | - |

Byte figures are exact. Token figures are estimated unless `ANTHROPIC_API_KEY` is set, in which case
the script counts them against the real endpoint.

---

## Contributing

- **No invented numbers.** A script in `benchmark/` or `eval/` must print any figure you cite.
- **Assets stay byte-stable.** No timestamps or run IDs under `assets/` - they land in a system prompt
  and cold-miss the prompt cache forever.
- **No em-dashes.** Plain hyphens.

Releases follow [`docs/RELEASING.md`](docs/RELEASING.md).

MIT - see [LICENSE](LICENSE).

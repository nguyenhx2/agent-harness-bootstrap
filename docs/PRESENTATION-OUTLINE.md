# Agent Harness - Presentation Outline

**English** · [日本語](PRESENTATION-OUTLINE.ja.md)

**The talk in one line:** give an AI agent a repo it can actually understand, and a harness it
cannot escape.
**Repo:** [agent-harness-bootstrap](https://github.com/nguyenhx2/agent-harness-bootstrap)
**Deck:** `presentation/index.html` - 23 slides, EN / VI / JA, follows this outline section by
section. It is the visual for this script, not a second copy of it: if a claim changes, change both.
**Duration:** 40 minutes (28 talk + 8 demo + Q&A). Shorter and longer variants at the end.

---

## The arc

> An agent fails because it does not understand the repo, or because nothing stops it →
> here are the nine places that shows up → the fix is a harness, not a better prompt →
> two skills build it, sized to what the repo is for → three mechanisms keep it working →
> watch it run → here are the numbers.

Lead with the idea, then the pain, then the product. The demo lands late, once the audience knows
what to look for.

---

## 0. The idea (2 min) - slides 1-2

Say the two halves before anything else. Everything after this is one of them.

| Half | What it means in the repo |
|---|---|
| **A repo it can actually understand** | A written contract with stable IDs. A team sized to what the repo is for. Rules that load only when they apply. Task state on disk, so a closed window loses nothing |
| **A harness it cannot escape** | Hooks that exit 2 before the tool runs. A deny list, a tool allowlist per seat, a cap on how deep agents spawn. None of it asks the model to agree |

**The line to land:** *"The problem is not that the model is not smart enough. It is that nothing
around the model is engineered."*

---

## 1. Where it breaks (5 min) - slides 3-4

Nine problems in three places. Number them; the numbers come back as the answers land.

| Where | What breaks |
|---|---|
| **Setup** | 01 kits install everything and fit nothing · 02 phrasing the prompt eats the time · 03 context is finite, however big the window |
| **Control** | 04 a rule written as an instruction can be skipped · 05 hallucination and overflow derail the process · 06 different models, unstable output |
| **Project** | 07 every repo has its own standard and purpose · 08 a closed chat or a crash takes the work with it · 09 few teams write specs an agent can build from |

**The human side, given room** (most audiences have never heard it framed): the instability is not
only the model's. Prompt style is not standardized, natural language is a lossy interface, how you
asked is not in git, and every hand-off is a fresh translation. Through a harness, free-form
language enters **once**, at intake, and becomes a contract; after that every hand-off is a file.
*"We are not trying to make people write better prompts. We are trying to make the prompt stop
being the interface."*

Close on the quote slide: *speed creates the advantage; control gets us to the destination.*

---

## 2. A harness is the operating system for an agent (2 min) - slide 5

Agent = application, harness = operating system, SDK = building blocks, model = CPU. With a
framework the developer writes the orchestration; with a harness the model makes the plan and the
harness keeps it on track. Preview the three mechanisms: **context**, **orchestration**,
**security**.

---

## 3. Two skills, one for each half (4 min) - slides 6-7

| Skill | Produces | Retires |
|---|---|---|
| **`spec-builder`** | A selective spec set (6 core sections, up to 8 optional): stable IDs, acceptance criteria, a data model, mandatory security NFRs | 09, 02 |
| **`harness-bootstrap`** | `.claude/`: a roster sized to the repo's purpose, path-scoped rules, hooks, a deny list, a task board on disk | 01, 04, 08 |

Four modes, chosen first: **Greenfield**, **Brownfield** (codebase analysis is mandatory and comes
first), **Audit** (read-only; a human applies fixes), **Update** (re-run against the existing
`vars.json`, never a re-bootstrap). Existing files are reconciled - `ADDED` / `KEPT` / `CONFLICT` -
never clobbered.

**Purpose profiles** answer 01 and 07. The first intake question is what the repo is for:

| Purpose | Seats | Verified by |
|---|---|---|
| Code | one dev agent per real module, the review gate, `spec-guardian`; test and database seats when asked | tests and code review; security review only when the diff earns it |
| Research | `researcher`, `checker` | every claim traced to a source that says it |
| Strategy | `strategist`, `researcher`, `checker` | distinct options, criteria fixed before scoring, the assumption that flips it |
| Docs | `writer`, `checker` | accurate against the source, links that resolve |

Purposes combine, and one `checker` serves every non-code purpose. Code-only options are refused
without the code purpose, so no seat is fielded with nothing to do.

**The line to land:** *"It reads your code before it writes anything. A generic template would look
right while describing someone else's repo."*

---

## 4. Skills: find, make, wire (2 min) - slide 8

- **Find** - discovery reads the manifests, searches only for stack-matching skills, and reads each
  one's files before you tick it. Nothing installs behind your back.
- **Make** - `/new-skill` first decides whether the workflow is a skill at all (refusing is a normal
  outcome), then scaffolds from a template, writes trigger cases and lints with `skill-check.py`.
- **Wire** - `/skill-wire` adds the skill to the seat's frontmatter `skills:` preload.
  `harness-view` reports a skill that sits on disk unwired.

---

## 5. Mechanism A: context (5 min) - slides 9-11

**Key message:** the context window is RAM, the work lives on disk, and compaction is survivable by
design. Answers 03, 05, 08.

| Tier | What lives there | What compaction does |
|---|---|---|
| **Always-RAM** | `CLAUDE.md`, the 7 unconditional rules, the agent body, tool schemas | Survives, because it is re-injected every turn |
| **Lazy-RAM** | The 10 path-scoped rules | Reloads when a matching file is touched |
| **Disk** | The board and one file per task: a checkpoint and a bounded session log | Nothing. It is committed markdown |
| **Archive** | One file per finished subagent run, written by a `SubagentStop` hook | Nothing. Written after the fact |

Three things make it a mechanism rather than a convention:

1. **Task state has one writer.** `task.py move` changes the board row, the file's `status:` and its
   folder together, then reads the row back. `guard-board` blocks a hand edit to the board.
2. **A resume reads three lines, not the history.** The checkpoint holds the next step, the last
   green commit and the open questions. The session log keeps its newest rows in the file and folds
   the rest into a committed archive beside it.
3. **Finished and crashed are told apart by a file.** Close-out writes `MISSION COMPLETE`. On long
   projects, `compact-checkpoint` writes state before a compaction and `session-context` puts the
   active tasks back in front of the agent after it.

**The line to land:** *"The window closing is not an incident. It is the expected case."*

---

## 6. Mechanism B: process proportional to the change (6 min) - slides 12-14

**Routing tiers**, decided before anything is dispatched. Most changes are Inline or Direct.

| Tier | The change | Who runs it |
|---|---|---|
| **Inline** | A question, a lookup, a doc or config edit, a fix you can see whole | The main session. No subagent |
| **Direct** | One module, reversible, no contract, schema, auth, payment or infrastructure | The owning agent, called straight. No task file |
| **Standard** | One domain, several files, or a numbered requirement | The owning agent. A task file only if it must survive a compaction |
| **Guarded** | Two or more domains, or schema, auth, money, a public contract, a migration, a deploy, personal data | The only tier that goes through the orchestrator |

Spawn depth and concurrent subagents are capped in `settings.json` env, so a fan-out cannot run away.
*"Choosing a heavier tier than the change needs is a defect, not caution."*

**Proportionate verification.** `verify-plan.py` reads the paths a diff touches and prints the gates
it needs; every skipped gate is one logged line with its reason.

| The diff touches | What runs |
|---|---|
| Anything | The secret scan. Never skipped |
| Docs or config only | No reviewer seat, no test run |
| Code | The tests that touch it, and code review. The full suite once, at the branch gate |
| Auth, secrets, parsing, data, AI tool calls, dependencies, infra | Security review too |
| A named critical flow | An end-to-end run for that flow, never by default |

**The Guarded flow:** orchestrator (analyze, decompose, register) → scoped dev seats → one gate over
the branch diff before the pull request. Reviewers hold no `Edit` or `Write`. A gate passes only when
the session log records the run: *an agent saying "done" is a claim to verify.* With the strict hook
set, `stop-evidence` sends back a completion claim that carries no evidence, once.

---

## 7. Mechanism C: security (5 min) - slides 15-17

**Key message:** defence in depth, and the model does not get a vote. Answers 04 and 06.

| Layer | What it stops |
|---|---|
| 1. Deny list | What it cannot **see**: `.env`, keys, `secrets/`, `git push --force`, `rm -rf` |
| 2. Hooks, exit 2 | What it cannot **do** |
| 3. Tool allowlist | What it cannot **reach**: judges hold no `Edit`; only the orchestrator holds `Agent` |
| 4. `maxTurns` and spawn caps | The runaway loop or fan-out |

State the weakness yourself: the deny list is prefix matching and re-ordering defeats it. It is a
speed bump; **the hooks are the gate.**

**Hooks on every event**, each in a `.sh` and a `.ps1` flavor, shipped only with the options that
need it (`harness-bootstrap/assets/claude/hooks/README.md` has the full table):

| When | What it catches | Does |
|---|---|---|
| Before a tool call | secrets, commits to main, Accepted ADRs, off-roster spawns, hand edits to the board, destructive commands (`rm -rf` on the root, a force push to a protected branch, `git reset --hard`), shipped migrations when a database is in the repo; the opt-in strict set adds uploads to unknown hosts, large files, lockfile edits, `curl \| sh` | blocks |
| After a failure | the same failing call, repeated | warns, then blocks |
| Before a stop | "all tests pass" with nothing behind it | sends it back once |
| Around a compaction | checkpoint before, active tasks back after | never blocks |
| After an edit | a changed spec, a stale graph, a broken link, an unsourced research claim | reminds |

**The strongest claim in the talk:** `eval/guardrail_eval.py` scaffolds a real harness and fires 250
payloads at it per hook flavor: 101 must-block, 149 must-allow, 250/250 correct, on a harness scaffolded
with the strict hooks, the long-session hooks and the database guard on (`hooks_strict`, `long`, `db`).
No model is consulted: the guardrails are shell scripts, so the result cannot depend on the model. *"A cheap model cannot commit a secret. Not because it knows
better, but because the hook exits 2 and the tool call never happens."* Then the honest limit: this
is the floor, not the ceiling.

---

## 8. Cost and the rest of the frontmatter (3 min) - slide 18

**Key message:** the expensive setup is the one you get by not choosing.

- **Model and effort per seat.** Opus for judgment and gates, Sonnet for work against a contract,
  Haiku for mechanical seats; low and medium effort wherever the contract is settled.
- **The rest of the frontmatter, set on purpose.** `disallowedTools` on every judge,
  `permissionMode` so a gate never stalls on a prompt, `omitClaudeMd` on reviewers, `memory` only on
  seats that learn the repo.
- **Briefs written for current models.** No "double-check" or "final verification" instructions -
  current models verify their own work, so the check lives in the gate once. Explicit limits on what
  a seat may delegate.

Modelled by `benchmark/model_cost.py`: the default roster costs $2.523 per feature, 32% below Opus
at xhigh everywhere. Say "modelled", never "measured".

---

## 9. One harness, three tools (2 min) - slide 19

Rules port to `.cursor/rules/*.mdc` and `AGENTS.md`; enforcement ports to `.cursor/hooks.json` (with
an adapter) and `.codex/hooks.json`. All three block a secret read and a commit to main; the port
adapter self-test is 32/32 across both hook flavors. Limits, out loud: Codex edits via `apply_patch`
so the ADR guard is best-effort; Cursor's `afterFileEdit` only observes; neither tool has a
subagent-spawn hook point.

---

## 10. Is it actually wired? (2 min) - slide 20

`tools/harness-view` reads what is on disk with no model in the loop:

- **Reads any harness** - code repos and research or writing repos, orchestrator-kit installs too;
  every documented frontmatter field; hooks on every event, from `settings.json` and from a seat's
  own `hooks:`.
- **Assess** - every finding links to its node: a seat with no module, an unregistered hook, a task
  whose board row and file disagree (marked `DRIFT`).
- **Edits** - park a rule, hook or seat (recorded in `.claude/disabled.json`; switching off a
  reviewer needs a typed confirmation), reorder a command's steps, set a seat's model, effort and
  tools.

---

## 11. Live demo (8 min) - slide 21 as fallback

Use a real repository with existing code; brownfield convinces, an empty folder does not.

1. **(30s)** The repo before: source, no `.claude/`.
2. **(90s)** `/harness-bootstrap`: it reads the code first, asks the purpose, shows the plan with
   every seat's model and effort. Nothing is written yet.
3. **(30s)** Approve. Read the wall-clock off the run (~0.2s).
4. **(2 min)** **Break it on purpose** - `cat .env`, a commit on `main`, an edit to an Accepted ADR.
   All blocked. This is the moment the talk is built around.
5. **(90s)** `python eval/guardrail_eval.py` live. *"No model was consulted. These are exit codes."*
6. **(60s)** `python .claude/scripts/verify-plan.py` on a docs-only change: secret scan, nothing else.
7. **(60s)** `/task-resume` in a fresh session: it reads the checkpoint and picks up mid-task.

Fallbacks: tooling fails → clip 4, then the gallery. Short on time → cut 6 and 7, **never 4 or 5**.

---

## 12. Proof (3 min) - slide 22

Every figure comes from a script and `scripts/check_numbers.py` fails CI if a document drifts.

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Read path (bytes pulled into context) | 234,196 | 178,719 | -24% |
| Read path (files read) | 24 | 10 | -58% |
| Write path (bytes the model must author) | 95,064 | 9,439 | -90% |

- 73% of rule content kept out of the default session
- Guardrail eval 250/250 (`hooks_strict`, `long`, `db` on), no model consulted
- Scaffold ~0.2s, and a re-run reports `KEPT` for every file

Byte counts are exact; token and cost figures are modelled at 3.6 chars per token.

---

## 13. Close (2 min) - slide 23

The agent understands the repo. It cannot leave the harness. The work is checked in proportion to
the change.

```
/spec-builder           # write the contract first
/harness-bootstrap      # build the harness for this repo
```

Point to the repo, the clip gallery and `docs/FLOWS.md`, and offer to run it on a volunteer's repo.

---

## Q&A preparation

| Question | Short answer |
|---|---|
| *Does this lock us into Claude Code?* | No. It ports to Cursor and Codex with enforcement; `AGENTS.md` is the vendor-neutral contract |
| *We already have a `.claude/` folder.* | It reconciles, never clobbers. Differences come back as `CONFLICT` |
| *Our repo is research, not code.* | Purpose profiles: a research repo gets `researcher` and `checker`, verified by sources, with no test or code-review seat |
| *Can the agent work around a hook?* | The deny list can be; it is a speed bump. Hooks fire before the tool runs and exit 2 |
| *Does a cheaper model break safety?* | No: no model is consulted, the guardrails are shell scripts, so the result cannot depend on the model. Code quality and review depth do degrade |
| *Does this slow developers down?* | Not on small work. Inline and Direct skip the orchestrator and the task file, and a docs change gets no reviewer at all |
| *Is this just a big CLAUDE.md?* | A CLAUDE.md is advice the model may forget after compaction. This is enforcement plus durable state |
| *Who owns the policy decisions?* | You do. Governance rules ship as blanks; the skill never invents a licence policy or a classification table |

---

## Timing variants

| Slot | What to do |
|---|---|
| **20 min** | Sections 0, 1, 3, 7, a short demo (steps 2, 4, 5), 13 |
| **40 min** | As written |
| **60 min** | Add a `docs/FLOWS.md` walkthrough, a `spec-builder` pass with clip 5, the `docs/ASSESSMENT.md` limits, and an audit-mode demo |

Never cut Section 0 or the human side of Section 1.

---

## Fact sheet

Checked by `scripts/check_numbers.py`; re-run it rather than editing a figure by hand.

- 18 agents (+1 dev-agent template), 17 rules, 23 commands, 26 hooks
- 7 unconditional rules, 10 path-scoped; 73% of rule content stays out of the default session
- Guardrail eval 250/250 (101 must-block, 149 must-allow) with `hooks_strict`, `long` and `db` on, no model consulted; port adapter 32/32
- Four routing tiers: Inline, Direct, Standard, Guarded - only Guarded uses the orchestrator
- Five task states: `Planned`, `Active`, `Blocked`, `Pending`, `Done`
- Four modes: Greenfield, Brownfield, Audit, Update
- Four purposes: code, research, strategy, docs

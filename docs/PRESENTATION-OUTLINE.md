# Agent Harness - Presentation Outline

**Topic:** Standardizing and building the operating foundation for AI coding agents
**The problem this talk solves:** ad-hoc, improvised AI coding
**Repo:** [agent-harness-bootstrap](https://github.com/nguyenhx2/agent-harness-bootstrap)
**Language:** English
**Target duration:** 40 minutes (28 talk + 8 demo + Q&A). Compression notes at the end.

---

## The narrative arc

One line of argument. Every section earns the next:

> AI coding today is ad-hoc → ad-hoc fails structurally, on both the machine side and the human side
> → the fix is a harness, not a better prompt → here are the three mechanisms that make it work
> → watch it run → here are the numbers.

**Deliberate ordering choice:** lead with the pain, not the product. The audience must feel the
problem before the solution means anything. The demo lands late, once they know what to look for.

---

## Section 0. Opening: why a harness at all (3 min)

> **This is the framing page. Everything after it is a consequence of this slide.**

**Key message:** AI coding today is *tự phát* - improvised. It works in a demo and breaks in a project.

Open with the contrast. Put this table on screen and walk it left to right:

| | **Ad-hoc AI coding (today)** | **Harnessed AI coding** |
|---|---|---|
| The instruction | A prompt someone typed, phrased their way | A written contract with stable IDs and acceptance criteria |
| Who does the work | One generalist agent, doing everything | A roster of scoped specialists, and a tier that decides how many of them a change earns |
| Memory | The context window. Compaction erases it | Committed markdown on disk. Compaction cannot touch it |
| Safety | "Please do not touch production" | Exit code 2. The tool call never happens |
| Cost | Whatever the default model charges | An explicit model and effort budget per seat |
| Reproducibility | Depends who asked, and how | Same repo, same contract, same structure |

**The sentence to land the section:**
> *"The problem is not that the model is not smart enough. It is that nothing around the model is
> engineered. We treat the most powerful tool we have ever put in a repository as something you chat
> with, not something you operate."*

**Then define the word, because the whole talk depends on it:**
> A **harness** is a controlled boundary the agent works inside: who does what, what it may read and
> touch, what it must write down, and what it simply cannot do.

**Asset:** Clip 4, "The complete solution" (~54s), works well here as a cold open if you prefer video
to a table. Otherwise the repo logo plus this table.
**Transition:** *"Let us be precise about what actually breaks. There are two halves to this, and most
teams only ever talk about one."*

---

## Section 1. The obstacles and risks (6 min)

**Key message:** These failures are predictable and structural. And half of them are ours, not the model's.

### 1a. The machine side - what the agent does wrong (3 min)

Straight from the pain points in the README:

| The obstacle | Why it bites in a real project |
|---|---|
| **No standard for what "good" looks like** | Every team invents its own agent setup. Nothing is comparable, reviewable, or transferable |
| **Agents do not compose** | One-off prompts do not add up to delivered work. Multi-step tasks stall halfway |
| **Hallucination** | It invents requirements, APIs, whole files. They look plausible enough to merge |
| **Context loss** | The window fills, compacts, and progress that lived only in that window is gone |
| **Security and blast radius** | It can read `.env`, commit to `main`, edit an accepted decision record |
| **Cost opacity** | An agent with no model set silently bills mechanical work at the top tier |
| **Tool lock-in** | The setup is rebuilt from scratch for Claude Code, Cursor, Codex |

**The line to land:** *"Telling the agent not to do these things is advice. After a context compaction,
it does not remember the advice."*

### 1b. The human side - the prompt problem nobody audits (3 min)

> **This section is the one most audiences have never heard framed out loud. Give it room.**

The instability does not only come from the model. It comes from **us**, and from natural language as
an interface:

- **Prompt style is not standardized.** Two engineers ask for the same feature in two different ways
  and get two different structures back. The output varies by person, by day, by mood. There is no
  house style for talking to an agent, so there is no consistency in what comes out.
- **Natural language is a lossy, unstable interface.** The same intent, phrased differently, produces
  different results. Nothing is reproducible. Worse: *how you asked* is invisible. It is not in git,
  it has no diff, nobody reviews it, and it cannot be rolled back.
- **It does not transfer.** A new team member has no idea how to ask. The person who "is good with
  the AI" becomes a bottleneck, and their skill is tacit and unteachable.
- **Every hand-off is a fresh translation.** Human prose in, model interpretation out, then that
  interpretation becomes the input to the next step. Ambiguity compounds at every boundary.

**The insight that turns this into the solution:**

> When agents talk to **each other** through a harness, the interface between them stops being prose
> and becomes **structure**: a spec section with a stable ID, a task file with acceptance criteria, a
> session log row. Free-form natural language enters **once**, at the intake boundary, and is
> immediately converted into a written contract. From that point on, every hand-off is
> file-mediated. **Structured input produces stable output.**

Say it plainly: *"We are not trying to make people write better prompts. We are trying to make the
prompt stop being the interface."*

**Transition:** *"Notice: none of these are model problems. A smarter model does not fix a single one."*

---

## Section 2. The thesis: it is a harness problem (3 min)

**Key message:** Models are commoditizing. The durable advantage is the harness around them.

- Models get cheaper and better every quarter. That is not where differentiation lives.
- What lasts: the **operating foundation** - agent roster, context discipline, workflow integration,
  governance.
- Reframe the goal: not *"which model do we use"* but *"can we turn any model into a controlled,
  ROI-positive, production-safe agent system."*
- Preview the three mechanisms you are about to explain, so the audience has a map:
  1. **Context** - how the system remembers
  2. **Orchestration** - how work is decomposed and driven
  3. **Security** - how it is prevented from doing damage

**Asset:** `docs/assets/ai-dlc-flow.svg`. Green is deterministic and free; purple costs tokens.
**Transition:** *"Concretely, this is two skills that generate one system."*

---

## Section 3. From scattered agents to a tailored system (4 min)

**Key message:** The harness is generated *for your repository*, not copied from a template.

| Skill | What it produces | The problem it retires |
|---|---|---|
| **`spec-builder`** | The input an AI can understand: a selective spec set under `docs/specs/` (6 core sections always, up to 8 optional), stable IDs, acceptance criteria, a data model, mandatory security NFRs | The AI is guessing what to build |
| **`harness-bootstrap`** | The harness the AI runs inside: `.claude/` with agents, rules, hooks, a deny list, plus a task board | Nothing constrains what it does, nothing survives when it forgets |

**Why "tailored" is the load-bearing word:**
- Three modes, chosen first: **Greenfield** / **Brownfield** / **Audit** (read-only; a human applies fixes).
- Brownfield runs a **mandatory codebase analysis first** and produces an Inventory Report: stack,
  modules, conventions, risky operations, existing assets, gaps. Everything downstream derives from
  that evidence.
- The dev-agent roster comes from the real module map (brownfield) or the FR clusters (greenfield).
- Existing files are **reconciled, never clobbered**: `ADDED` / `KEPT` / `CONFLICT`.

**The line to land:** *"It reads your code before it writes anything. A generic template would be worse
than nothing, because it would look right while describing someone else's repo."*

**Asset:** Clip 6, "harness-bootstrap in depth" (~59s), or `docs/FLOWS.md` diagram 2.

---

## Section 4. Mechanism 1: context management (5 min)

**Key message:** The context window is RAM. The work lives on disk. Compaction is survivable by design.

### The four-tier memory hierarchy

Do not present this as two tiers. The insight is that there are four, and only the bottom two are durable.

| Tier | What lives there | Cost | What compaction does |
|---|---|---|---|
| **Always-RAM** | `CLAUDE.md`, the 7 unconditional rules, the agent body, tool schemas | **30,643 bytes of rules**, re-sent every turn, forever | Survives, because it is re-injected |
| **Lazy-RAM** | The 9 path-scoped rules (`paths:` frontmatter) | **55,062 bytes** that most sessions never pay for | Reloads when a matching file is touched |
| **Disk** | `docs/tasks/master-plan.md` (the board) + `docs/tasks/active/TASK-NNN.md` (goal, criteria, decisions, **session log**) | A few hundred bytes, read once | **Nothing. It is committed markdown in git** |
| **Archive** | `.claude/state/history/` - one file per finished subagent run, written by a `SubagentStop` hook | Zero until read | Nothing. Written after the fact |

**Asset:** `docs/assets/memory-hierarchy.svg`

### Why this is a mechanism, not a convention

Three design decisions make it hold. Each is worth one sentence on stage:

1. **The session log is written *as the agent works*, not at the end.** A report written at the end is
   lost with the crash that prevented it. An append-only log survives the crash.
2. **Status is duplicated on purpose** - in the task file frontmatter *and* the board row - and both
   are written in the same step, then read back. The rule is: *"a write nobody confirmed is a wish."*
3. **A `Planned` task file lives in `active/`, not `pending/`.** This looks wrong and is not: the
   resume scan reads `active/`, so filing new work under `pending/` would hide it forever. The
   directory layout is not filing, it **is the index the resume protocol scans**.

### The resume protocol

- Session start: **scan before accepting a mission.** Unfinished work is picked up before anything new
  is taken on.
- Rebuild state from files, not from memory. **Trust ordering is a written rule: committed files and
  git state over any agent's final report.**
- A **`MISSION COMPLETE` marker** distinguishes "finished" from "crashed" by a file check rather than a
  guess. Marker present and silent means done. No marker and silent means crashed - resume.
- **A silent stall counts as a crash**, so a hung agent cannot masquerade as a working one.

**The line to land:** *"The window closing is not an incident. It is the expected case, and the system
is designed for it."*

**Asset:** Clip 2, "The operating flow" (~29s); `docs/CONTEXT-MANAGEMENT.md` for the deep dive.

---

## Section 5. Mechanism 2: process proportional to the change (5 min)

**Key message:** How much process a change gets is decided before anything is dispatched, and most
changes get almost none.

### Lead with the tier table. It is the first thing an agent reads

| Tier | The change | Who runs it |
|---|---|---|
| **Direct** | One module, reversible, touching no contract, schema, auth, payment or infrastructure | The owning agent, called straight. **No orchestrator, no task file** |
| **Standard** | One domain, several files, or a numbered requirement behind it | The owning agent too. A task file only when the work must survive a compaction |
| **Guarded** | Two or more domains, *or* schema, auth, money, a public contract, a migration, a deploy or personal data | The `orchestrator`, and the full flow below |

**The line to land:** *"Choosing a heavier tier than the change needs is a defect, not caution. A
one-line fix that pays for a planning pass, a task file and three reviews spends real time to learn
nothing - and after a few of those, people stop reaching for the harness on small work. Small work is
most work."*

The rest of this section describes the **Guarded** flow. Direct and Standard work skips straight to
the specialist.

### The state machine - five states, defined exactly once

| State | Meaning | Lives in |
|---|---|---|
| `Planned` | Registered and scoped, not started | `docs/tasks/active/` |
| `Active` | In progress. **Exactly one owner** | `docs/tasks/active/` |
| `Blocked` | Started, cannot proceed. Reason and unblocker recorded | `docs/tasks/active/` |
| `Pending` | Deliberately parked, a conscious decision to defer | `docs/tasks/pending/` |
| `Done` | Complete, results recorded | `docs/tasks/done/` |

Point out the distinction most teams blur: *"`Blocked` wants to move and cannot. `Pending` could move
and has been told not to."*

### The orchestrator's loop - five phases, on a Guarded change only

1. **Analyze** the requirement against the spec
2. **Decompose** into tasks with dependencies
3. **Register** on the board and create the task file. **The board allocates task IDs, never the brief**
4. **Drive** the lifecycle: dispatch, monitor, log
5. **Close out**: merge, audit the board, write the completion marker

### Routing: who is dispatched, and why it is not one generalist

- Each dev agent is scoped to real module paths, so two agents do not collide on the same files.
- Separation of duty is **structural, not aspirational**: reviewers hold no `Edit` or `Write`. *"A
  reviewer that edits code has become a dev agent and lost its independence."*
- Sub-tasks that exist to make a plan look thorough are overhead, not rigour: each one is a dispatch,
  a brief, a board row and a log row.

### One gate, on the branch, at the pull-request boundary

```
/review-changes over the whole branch diff:
  the suites → code-reviewer + security-reviewer → /secret-scan → PR opened
```

**Say the "once" out loud, because the old shape was a reviewer after each agent:** a reviewer
dispatched per agent re-reads the same files once per agent and reports the same findings each time.
Security review belongs to this boundary and to any moment the user asks for it - not to every change.

**The most important operational rule in the whole system - land this one hard:**

> A gate counts as passed **only when the task file's session log records the run.** An agent saying
> "done" or "all gates green" is a **claim to verify**, never a fact. Orchestrators have reported "all
> gates green" over a log containing no reviewer rows at all.

This is the mechanism that makes an agent system auditable: **evidence in a file beats a status report.**

### Concurrency discipline (mention briefly, it signals maturity)

- One orchestrator drives a project at a time; one merger, serialized.
- CI must be **green, not pending** - poll to a terminal state, never merge on a presumed pass.
- On conflicting appends, **union, do not pick a side**, and prove nothing was dropped: the merged test
  count must be greater than or equal to the sum of both sides.
- A **post-merge board audit is required after every merge**, because a merge that resolves a board
  collision by taking one side reverts a status flip with no error at all.

---

## Section 6. Mechanism 3: multi-layer security (5 min)

**Key message:** Defence in depth, and the repo is explicit about which layers are real.

### The distinction that matters: enforced versus advisory

Most "AI safety" in codebases is advisory text that a model may ignore after compaction. State which
of your layers the model **does not get a vote** on:

**Enforced - the model does not get a vote:**

| Layer | Mechanism | What it stops |
|---|---|---|
| **1. Deny list** | `permissions.deny` in `settings.json`: `Read(**/.env)`, `Read(**/*.pem)`, `Read(**/secrets/**)`, `Bash(git push --force:*)`, `Bash(rm -rf:*)`, plus a Restricted-paths slot | What the agent cannot **see**. The action never reaches a tool call |
| **2. PreToolUse hooks, exit code 2** | `protect-secrets`, `guard-main-commit`, `check-commit-msg`, `protect-adr` | What the agent cannot **do**: read a `.env`, commit to `main`, ship a bad commit message, edit an `Accepted` ADR |
| **3. Tool allowlist** | `tools:` in agent frontmatter | What the agent cannot **reach**. Least privilege per seat |
| **4. `maxTurns`** | e.g. `history-tracker: maxTurns: 10` | The circuit breaker. *"The cost of a stuck agent is unbounded"* |

**Advisory - useful, but honest about it:** the rules files, agent bodies, and effort settings. They
shape behaviour; they do not enforce it.

**Asset:** `docs/assets/control-layers.svg`; Clip 3, "The control layers" (~31s).

### Why layering matters: state the weakness yourself

> The deny list is **prefix matching** and is defeated by re-ordering (`rm -r -f`). It is a speed bump.
> **The hooks are the gate.** Saying this out loud is what makes the rest of the claims credible.

### The strongest claim in the talk

`eval/guardrail_eval.py` scaffolds a real harness and fires **40 known-bad and known-good payloads**
at it: **44 must-block, 68 must-allow, 112/112 correct.**

> *"A cheap model cannot commit a secret. It cannot commit straight to main. It cannot edit an
> accepted ADR. Not because it knows better, but because the hook exits 2 and the tool call never
> happens."*

Swap Opus for Haiku and the result is **byte-identical**. The safety floor is **model-independent**.

**State the honest limit immediately after:** this measures the **floor, not the ceiling**. Code
quality and review depth *do* degrade with a cheaper model. The eval does not measure that.

### Governance layer (30 seconds)

Three rules ship into every repo, and the skill **never invents a policy for your company**:
`model-policy` (data classification decides which model may process what), `ip-compliance`
(dependency licence allow and deny lists), `ai-governance` (which actions require a human).

---

## Section 7. Cost as a design decision (3 min)

**Key message:** The expensive configuration is the one you get by *not choosing*.

Every agent carries an explicit `model:` **and** `effort:`. An unset `model:` inherits the caller's
tier, which bills mechanical work at Opus rates.

| Tier | Seats | Why |
|---|---|---|
| `opus` | orchestrator, debugger, code-reviewer, security-reviewer | Judgment under incomplete information. The gates |
| `sonnet` | dev agents, `qa-test`, `spec-guardian`, `ba-analyst` | Bounded work against a written contract |
| `haiku` + `low` | `history-tracker`, `db-seeder` | High volume, mechanical, no judgment |

Modelled cost of **one feature** through the harness (`benchmark/model_cost.py`):

| Profile | USD / feature | vs default | Per 100 features |
|---|---:|---:|---:|
| all-frontier (fable, xhigh) | 8.007 | 2.92x | 791 |
| all-opus (xhigh, no effort tuning) | 4.004 | 1.46x | 400 |
| **DEFAULT roster** | **2.746** | **1.00x** | **275** |
| economy (gates opus, rest haiku) | 2.152 | 0.78x | 215 |
| haiku-only (medium) | 0.708 | 0.26x | 71 |

> **The default roster costs 31% less than putting Opus at xhigh everywhere, which is the configuration
> a team lands on by not choosing.**

Context is the other lever: 9 of 16 rules are path-scoped, keeping **62% of rule content out of the
default session**. A rule without `paths:` is rent paid on every request of every agent, forever.

---

## Section 8. Portability: one harness, three tools (2 min)

| | Claude Code | Cursor | Codex |
|---|---|---|---|
| Rules | `.claude/rules/*.md` | `.cursor/rules/*.mdc` + `AGENTS.md` | `AGENTS.md` (native) |
| Enforcement | `settings.json` hooks | `.cursor/hooks.json` + generated adapter | `.codex/hooks.json` (registers directly) |
| Blocks a secret read / commit to main | yes | yes | yes |

One command: `python scripts/port.py --target . --tool all`. The adapter is unit-tested in CI (32/32, both hook flavours).

**State the three honest limits out loud** - it buys credibility and pre-empts the sharpest question:
Codex routes edits through `apply_patch`, so `protect-adr` is best-effort there; Cursor's
`afterFileEdit` is observational, so an ADR edit is flagged rather than blocked; and
`guard-agent-spawn` does not port at all, because neither tool has Claude Code's `Agent` tool and so
neither exposes a subagent-spawn hook point.

---

## Section 8b. Seeing whether it is actually wired (2 min)

**Key message:** A harness that looks configured and has a hook nobody registered is a harness that
is not there. `tools/harness-view` reads what is on disk, with no model in the loop.

- **The graph.** Agents, rules, commands, hooks, skills and tasks, with the edges between them, plus a
  Flow view that runs from `settings.json` to the human.
- **`assess`.** Scores a harness against the project's own quality gate and links every finding back to
  the node that caused it: a seat with no module, a rule matching no path, a skill no agent was told
  to use. Run against three real harnesses it scores 99, 90 and 64 out of 100.
- **And it edits.** Park a rule, hook, command or seat (recorded in `.claude/disabled.json`, and
  switching off a reviewer needs a human to type the confirmation phrase); reorder, retitle or switch
  off a command's numbered steps; set a seat's `model`, `effort` and `tools` from pickers backed by a
  four-vendor reference you can edit per repository.

**The line to land:** *"Everything you have just seen is a file on disk, so a tool with no model in it
can tell you whether the harness you were promised is the harness you have."*

---

## Section 9. Live demo (8 min)

**Key message:** It is real, it is fast, and the guardrails actually fire.

Use a **real repository with existing code**. Brownfield is far more convincing than an empty folder.

1. **(30s) The repo before.** No `.claude/`, no `docs/`. Just source.
2. **(90s) Run `/harness-bootstrap`.** Let them watch it *read the code first*. Show the Inventory
   Report and the intake. Stop at the setup plan: nothing is written yet, and the plan names every
   agent's model and effort budget.
3. **(30s) Approve and scaffold.** Call the wall-clock off the run in front of you - it lands in
   **~0.2s**. Contrast with a model generating the same content: minutes, real money, and it can
   hallucinate a hook that never runs.
4. **(60s) Tour what landed.** `.claude/agents/`, `rules/`, `hooks/`, `settings.json`, `docs/tasks/`.
5. **(2 min) Break it on purpose. This is the moment the talk is built around.**
   - `cat .env` → blocked
   - `git commit` on `main` → blocked, with the hook's message
   - Edit an Accepted ADR → blocked
6. **(90s) Prove it is not the model being polite.** Run `python eval/guardrail_eval.py` live:
   **112/112** in seconds. Say it: *"No model was consulted. These are exit codes."*
7. **(60s) Show resume.** Open a task file with its session log, then `/task-resume` in a fresh
   session and watch it pick up mid-task.

**Fallbacks, decided in advance:**
- Tooling fails → play clip 4 (~54s), then the gallery
- Short on time → cut steps 4 and 7. **Never cut step 5 or 6**
- Pre-capture the eval output as a screenshot

---

## Section 10. Proof and results (4 min)

**Key message:** Every number comes from a script in this repo, and you can re-run all of them.

### Safety

| Claim | Figure | Source |
|---|---|---|
| Known-bad and known-good payloads handled correctly | **112/112** (44 blocked, 68 allowed) | `eval/guardrail_eval.py` |
| Result after swapping Opus for Haiku | **byte-identical** | same eval |
| Cursor/Codex port adapter | **32/32** | `port.py --self-test` |

### Efficiency of the harness itself

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Read path (bytes pulled into context) | 234,196 | **155,597** | **-34%** |
| Read path (files read) | 24 | **10** | **-58%** |
| Write path (bytes the model must author) | 95,064 | **9,439** | **-90%** |

### Session tax (paid on every request, of every agent, forever)

| | Rules | Bytes |
|---|---:|---:|
| Unconditional (always loaded) | 7 | 30,643 |
| Path-scoped (on demand) | 9 | 55,062 |
| **Kept out of the default session** | | **62%** |

### Cost per feature (modelled)

The table is in Section 7; do not put it on screen twice. What belongs here is where the money goes in
the default roster, per feature: `app-dev` $0.778, `orchestrator` $0.716, `code-reviewer` $0.421,
`security-reviewer` $0.404, `qa-test` $0.314, `spec-guardian` $0.088, `history-tracker` $0.025.

### Scaffold

**~0.2s**, exit 0. Re-run is **idempotent**: everything reports `KEPT`, nothing is clobbered. An
unresolved variable exits non-zero rather than shipping a placeholder into a live rule.

### What ships

**16** agents (+1 template), **16** rules, **22** commands, **10** hooks.

### Say this out loud, it is what makes the rest believable

- **Byte counts are exact**, counted from disk. **Token and cost figures are MODELLED**, derived at
  3.6 chars/token with no API key set. Do not present modelled numbers as measured.
- The **cost model cannot tell you whether a cheaper roster produces acceptable work.** That is a
  quality question. The eval measures only the safety floor.
- CI enforces all of it: the guardrail eval, a scaffold matrix on Linux and Windows, a diagram render
  check, and a check that **every figure in the docs matches what the scripts print**. The numbers
  cannot silently drift.

**Optional credibility slide:** `docs/ASSESSMENT.md` states honestly what is *not* solved. With a
technical audience this is usually the moment they start trusting you.

---

## Section 11. Close and call to action (2 min)

- Recap against the opening contrast: ad-hoc → engineered, on all four axes (contract, roles, memory, control).
- The three mechanisms, one line each: **context survives**, **process is proportional to the change
  and gated once on the branch**, **damage is blocked by exit codes**.
- The ask, on screen:
  ```
  /spec-builder           # write the contract first
  /harness-bootstrap      # build the harness for this repo
  ```
- Point to the repo, the clip gallery, and `docs/FLOWS.md`.
- Invite the first pilot: offer to run it live on a volunteer's repository after the session.

---

## Q&A preparation

| Question | Short answer |
|---|---|
| *Does this lock us into Claude Code?* | No. It ports to Cursor and Codex with enforcement. `AGENTS.md` is the vendor-neutral contract |
| *What if we already have a `.claude/` folder?* | It reconciles, never clobbers. Differences are reported as `CONFLICT` for you to merge |
| *Can the agent work around a hook?* | The deny list is prefix matching and is defeatable; that is a speed bump. The hooks are the gate: they fire before the tool runs and exit 2 |
| *Does a cheaper model break safety?* | No, and it is proven: byte-identical eval on Haiku. What degrades is code quality and review depth |
| *How much does it cost?* | $2.746 per feature modelled on the default roster, 31% below the not-choosing configuration. Three presets: Default / Economy / Thorough |
| *Is this just a big CLAUDE.md?* | A CLAUDE.md is advice the model may forget after compaction. This is enforcement plus durable state |
| *Who owns the policy decisions?* | You do. Governance rules ship as blanks. The skill never invents a licence policy or a classification table |
| *Does this slow developers down?* | Not on small work: a one-module, reversible change is Direct - straight to the owning agent, no orchestrator, no task file. The full flow is reserved for changes that span domains or touch schema, auth, money, a contract, a migration, a deploy or personal data, and the gate runs once on the branch rather than after every agent |

---

## Timing variants

| Slot | What to do |
|---|---|
| **20 min** | Sections 0, 1 (both halves, condensed), 3, 6, short demo (steps 2, 3, 5, 6), 11. Cut 4, 5, 7, 8, 8b, 10 |
| **40 min** (default) | As written |
| **60 min** | Add a `docs/FLOWS.md` walkthrough, a deeper `spec-builder` pass with clip 5, the `ASSESSMENT.md` limits discussion, and a second demo in audit mode |

**If you must cut only one thing:** cut Section 8 (portability). **Never cut Section 1b** - the human
prompt problem is the part the audience has not heard before.

**The deck is 25 slides** (`presentation/index.html`), trilingual, and follows this outline section by
section. It is the visual for this script, not a second copy of it: if a claim changes, change both.

---

## Asset checklist

- [ ] Clip gallery reachable: https://nguyenhx2.github.io/agent-harness-bootstrap/video/
- [ ] Clips 2, 3, 4, 6 downloaded locally as an offline fallback
- [ ] `docs/assets/ai-dlc-flow.svg`, `memory-hierarchy.svg`, `control-layers.svg` exported for slides
- [ ] Demo repository chosen (with existing code) and a full dry run completed
- [ ] `eval/guardrail_eval.py` and `benchmark/model_cost.py` output pre-captured as screenshots
- [ ] Terminal font size raised; projector-legible contrast
- [ ] Decide which figures you will quote, and never round them upward

---

## Fact sheet (verified against the repo)

Enforced by `scripts/check_numbers.py`, so these will not drift:

- **16** agents (+1 dev-agent template), **16** rules, **22** commands, **10** hooks
- **7** rules unconditional, **9** path-scoped → **62%** of rule content stays out of session
- Always-RAM rules **30,643 bytes**; path-scoped **55,062 bytes**
- Read path **-34%** (234,196 -> 155,597 bytes), files read **-58%** (24 -> 10)
- Write path **-90%** (95,064 → 9,439 bytes)
- Guardrail eval **112/112** (44 must-block, 68 must-allow), model-independent
- Port adapter self-test **32/32**
- Default roster **$2.746 per feature** modelled, **31%** below all-opus-xhigh
- Scaffold **~0.2s**, idempotent on re-run
- Roster **7 to 15 of the 16 seats**, never all of them by default
- Three tiers of process: Direct, Standard, Guarded - and the gate runs once, on the branch
- Five task states: `Planned`, `Active`, `Blocked`, `Pending`, `Done`
- Three modes: Greenfield, Brownfield, Audit
- `harness-view assess` on three real harnesses: **99**, **90** and **64** out of 100

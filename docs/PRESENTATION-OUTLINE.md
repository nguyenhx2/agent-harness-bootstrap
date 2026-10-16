# Agent Harness - Presentation Outline

**English** · [日本語](PRESENTATION-OUTLINE.ja.md)

**The talk in one line:** give an AI agent a repo it can actually understand, and a harness it
cannot escape.
**Repo:** [agent-harness-bootstrap](https://github.com/nguyenhx2/agent-harness-bootstrap)
**Deck:** `presentation/index.html` - 26 slides, EN / VI / JA, follows this outline section by
section. It is the visual for this script, not a second copy of it: if a claim changes, change both.
**Duration:** 40 minutes (28 talk + 8 demo + Q&A). Shorter and longer variants at the end.

---

## The arc

> An agent fails because it does not understand the repo, or because nothing stops it →
> here is what that looks like on a real repo → the answer is a harness, and this is how it fits
> together → seven questions teams ask, each answered by a mechanism → how the mechanisms work, and
> what running them live in Claude Code found → the proof → how to start.

Lead with the idea, then the pain, then the product. The questions are the spine of the talk: each
one is a sentence the audience has said, followed by the thing that answers it. The demo lands late,
once the audience knows what to look for.

---

## 0. The idea (2 min) - slides 1-2

Say the two halves before anything else. Everything after this is one of them.

| Half | What it means in the repo |
|---|---|
| **A repo it can actually understand** | A written contract with stable IDs. A team sized to what the repo is for. Rules that load only when they apply. Task state on disk, so a closed window loses nothing |
| **A harness it cannot escape** | Hooks that exit 2 before the tool runs, and block when they themselves fail. A deny list, a tool allowlist per seat, a cap on how deep agents spawn. None of it asks the model to agree |

**The line to land:** *"The problem is not that the model is not smart enough. It is that nothing
around the model is engineered."*

---

## 1. The problem (4 min) - slides 3-4

Five things an unharnessed agent does on a real repo, one card each: it **reads what it should not**
(`.env` while fixing a bug), **edits what it does not own**, **forgets the plan** when the context
compacts, **re-runs what already passed** (a README typo earns the full suite and every reviewer),
and **says "done" with no evidence**. None of these is fixed by a smarter model.

**The human side, given room:** the instability is not only the model's. Prompt style is not
standardized, natural language is a lossy interface, how you asked is not in git, and every
hand-off is a fresh translation. Through a harness, free-form language enters **once**, at intake,
and becomes a contract; after that every hand-off is a file. *"We are not trying to make people
write better prompts. We are trying to make the prompt stop being the interface."*

Close on the quote slide: *speed creates the advantage; control gets us to the destination.*

---

## 2. The answer (3 min) - slides 5-6

**Slide 5 is the overview diagram** (`docs/assets/harness-overview.svg`, the Japanese deck shows
`harness-overview.ja.svg`). Walk it left to right: what you bring flows into `spec-builder`, which
writes one contract; `harness-bootstrap` reads that contract **and the codebase itself** and builds
six parts (rules, hooks, an agent roster, routing, skills, verification); the work writes state to
disk (task board, run history, checkpoints); `harness-view` reads the harness and that state.

**Slide 6:** agent = application, harness = operating system, SDK = building blocks, model = CPU.
With a framework the developer writes the orchestration; with a harness the model makes the plan
and the harness keeps it on track.

---

## 3. Seven questions teams actually ask (16 min) - slides 7-16

Slide 7 is the map: the seven questions from the README's "The problems it solves", each bound to
the mechanism that answers it. Then one or two slides per question.

### Q1. "I want an agent team that fits my project." - slides 8-9

On an existing repo the code is read first and pre-fills the answers; then the first question is
what the repo is **for**:

| Purpose | Seats | Verified by |
|---|---|---|
| Code | one dev seat per real module, `code-reviewer`, `spec-guardian` | tests and code review; security review only when the diff earns it |
| Research | `researcher`, `checker` | every claim traced to a source that says it |
| Strategy | `strategist`, `researcher`, `checker` | distinct options, criteria fixed before scoring, the assumption that flips it |
| Docs | `writer`, `checker` | accurate against the source, links that resolve |

Sized from evidence: a run installs 3 to 17 of the 18 seats, never all of them by default.
Purposes combine, one `checker` serves every non-code purpose, and intake fits in at most two
question batches.

**Skills (slide 9):** **find** (stack-matching only, files read before you tick), **make**
(`/new-skill` decides first whether it is a skill at all; refusing is normal; then a template,
trigger cases and `skill-check.py`), **wire** (`/skill-wire` adds it to a seat's `skills:`
preload; `harness-view` reports a skill that sits on disk unwired).

### Q2. "I want it safe, without it overthinking or burning tokens." - slides 10-11

**Routing tiers**, as a ladder whose weight grows left to right. Most changes are Inline or Direct.

| Tier | The change | Who runs it |
|---|---|---|
| **Inline** | A question, a lookup, a doc or config edit, a fix you can see whole | The main session. No subagent, no task file |
| **Direct** | One module, reversible, no contract, schema, auth, payment or infrastructure | The owning seat, called straight |
| **Standard** | Several files, or a numbered requirement behind it | The owning seat; a task file only if it must survive a compaction |
| **Guarded** | Several seats in order, or schema, auth, money, a migration, a deploy, personal data | The only tier that goes through the orchestrator |

Every seat pins `model`, `effort`, `tools` and `maxTurns`; `settings.json` caps spawn depth and
concurrent subagents. *"Choosing a heavier tier than the change needs is a defect, not caution."*

**Verification that would learn nothing is refused (slide 11).** The chain: the diff →
`verify-plan.py` names the gates it needs (a docs edit gets no reviewer; the secret scan always
runs) → the gates → the **verification ledger** records each pass by a hash of the content it
checked. `guard-agent-spawn` then refuses a re-run on content that passed, a third review round, an
identical brief and a dispatch past the task's budget. Only a human can force one re-run, with
`REVERIFY: <reason>` in the brief, once, on the record.

### Q3. "I am worried about leaking keys." - slide 12

Always on: `protect-secrets` (reads and copies of `.env*` except `.env.example`, keys, `secrets/`,
`credentials/`, through Bash and PowerShell alike), `env-read.py` (runs a command with the values
loaded and redacts them from its output), `/secret-scan` (scans the diff before review). With
`hooks_strict`: `secret-guard` (a vendor-format key in a prompt is blocked before it is sent) and
`guard-egress` (an upload to a host not on the allowlist, the step a prompt injection needs).

### Q4. "Traditional SDLC is a struggle, and AI-DLC ends up half-hearted." - slide 13

One loop, with the spec as the oracle: **FR → task → implement → verify-plan → review → done**. A
criterion that turns out wrong goes back to the spec, never around it. Ceremony follows the change:
Inline and Direct need no spec work, Standard appends one criterion inside an FR already agreed,
Guarded confirms a new FR first (`spec-builder/reference/agentic-loop.md`).

### Q5. "I want specs a human can confirm and an AI can understand." - slide 14

`spec-builder` turns any input into one contract under `docs/specs/`: 6 core sections, up to 8
optional ones chosen by what the material contains. It shows a per-source reading plan before it
asks anything. The contract carries stable FR IDs and Given/When/Then criteria with a negative case,
and two views of it: `confirmation.md` (every FR in plain words with a yes / no / change column for
the PO) and `index.json` (what agents read first). Unknowns become `AS-nn` or `OI-nn`, never
invented content. `spec-check.py` regenerates both views and fails when either falls behind.

### Q6. "I want to understand and control how the agents work." - slide 15

`harness-view` reads what is on disk with no model in the loop: a live graph of every agent, rule,
hook, command and module; toggles that park a rule, hook or seat (a protected control needs a human
to type the phrase); run history from `agent-history`, and `agent-trace` for which rule loaded and
why; `harness-check.py` proves every cross-link points at something real.

### Q7. "Once built, it is too much to check, and the score is vague." - slide 16

`harness-view assess` is a plain rules engine, the same one behind the browser tab and CI: a
worklist ordered by weight x count / effort, one-click fixes, what changed since the last check, and
a published rubric (`tools/harness-view/RUBRIC.md`) across six categories: Safety, Cost control,
Traceability, Board health, Docs quality, Contract. The screenshot is a real harness: 219 nodes,
655 edges, scored 98/100.

---

## 4. How it works (8 min) - slides 17-21

**Context tiers (slide 17).** The window is RAM, the work lives on disk, and compaction is
survivable by design.

| Tier | What lives there | What compaction does |
|---|---|---|
| **Always-RAM** | `CLAUDE.md`, the 7 unconditional rules, the agent body, tool schemas | Survives, because it is re-injected every turn |
| **Lazy-RAM** | The 10 path-scoped rules and per-module `CLAUDE.md` files | Reloads when a matching file is touched |
| **Disk** | The board and one file per task: a checkpoint and a bounded session log | Nothing. It is committed markdown |
| **Archive** | One file per finished subagent run, written by a `SubagentStop` hook | Nothing. Written after the fact |

`task.py move` changes the board row, the file's `status:` and its folder together; `task.py
checkpoint` writes the next step and the last green commit, so a fresh session resumes in three
lines. *"The window closing is not an incident. It is the expected case."*

**Hooks on every event (slide 18),** drawn on the lifecycle, each marked block, warn, or context:
SessionStart (`session-context`), UserPromptSubmit (`secret-guard`), PreToolUse (`protect-secrets`,
`guard-destructive`, `guard-main-commit`, `check-commit-msg`, `guard-agent-spawn`, `guard-board`,
`protect-adr`; strict adds `guard-egress`, `guard-large-file`, `guard-deps`; `db` adds
`guard-migration`), PostToolUse (reminders, `retry-budget`), PreCompact (`compact-checkpoint`),
Stop (`stop-evidence`, `agent-history`). **Blocking guards fail closed:** a guard that times out or
crashes blocks the call (`onFailure: block`). Advisory hooks stay fail-open, because a broken
reminder must never stop work. Full table: `harness-bootstrap/assets/claude/hooks/README.md`.

**Defence in depth (slide 19):** deny list (what it cannot see), hooks (what it cannot do),
tool allowlist (what it cannot reach), `maxTurns` and spawn caps (the runaway). State the weakness
yourself: the deny list is prefix matching and re-ordering defeats it. It is a speed bump; **the
hooks are the gate.**

**Run live in Claude Code (slide 20).** v1.20.1 ran the hooks inside real Claude Code sessions for
the first time and closed four holes scripted payloads could not show:

1. **Git global options** - `git -c k=v commit`, `git -C . commit` and `git --git-dir .git push
   --force` walked past the commit and destructive guards. Now read through.
2. **The Windows ledger** - Windows PowerShell 5.1 put a BOM before the payload, so the ledger
   allowed every dispatch. Fixed; an unreadable payload now blocks.
3. **Guards fail closed** - under load a guard timed out and `Remove-Item -Recurse -Force .` ran.
   Every blocking guard now carries `onFailure: block`.
4. **Secrets through PowerShell** - `Get-Content .env` through the PowerShell tool was never
   checked. `protect-secrets` now sees it.

The guardrail eval now runs the `.ps1` flavour under the same Windows PowerShell the settings call,
and `.sh` hooks through Git Bash.

**One harness, three tools (slide 21).** Rules port to `.cursor/rules/*.mdc` and `AGENTS.md`;
enforcement to `.cursor/hooks.json` (with an adapter) and `.codex/hooks.json`. Limits, out loud:
Codex edits via `apply_patch` so the ADR guard is best-effort; Cursor's `afterFileEdit` only
observes; neither tool has a subagent-spawn hook point.

---

## 5. Proof (4 min) - slides 22-24

**The safety floor (slide 22):** `eval/guardrail_eval.py` scaffolds a real harness per hook flavour
and fires 312 payloads at it: 134 must-block, 178 must-allow, 312/312 correct for `.sh` and for
`.ps1`, with `hooks_strict`, `long` and `db` on. No model is consulted. The port adapter self-test
is 34/34. *"A cheap model cannot commit a secret. Not because it knows better, but because the hook
exits 2 and the tool call never happens."* Then the honest limit: this is the floor, not the
ceiling, and it measures the hooks of that scaffold, not agent behaviour.

**Every number comes from a script (slide 23).** `scripts/check_numbers.py` fails CI if a document
drifts.

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Read path (bytes pulled into context) | 234,196 | 136,872 | -42% |
| Read path (files read) | 24 | 10 | -58% |
| Write path (bytes the model must author) | 95,064 | 9,439 | -90% |

- 75% of rule content kept out of the default session
- 18 agents, 17 rules, 23 commands, 27 hooks; a run installs 3 to 17 of the 18 seats
- Guardrail eval 312/312 per hook flavour

Byte counts are exact; token figures are estimated at 3.6 chars per token.

**The real benchmark (slide 24)** shows a live agent session on a fixture repository, bare and
harnessed. Its numbers come from the benchmark's own output for this release and are filled into
the slide's `bench` data (element `#bench-results`); until then the slide is marked as a
placeholder. Present only the figures that output contains, and say what it does not measure.

---

## 6. Live demo (8 min) - slide 25 as fallback

Use a real repository with existing code; brownfield convinces, an empty folder does not.

1. **(30s)** The repo before: source, no `.claude/`.
2. **(90s)** `/harness-bootstrap`: it reads the code first, asks the purpose, shows the plan with
   every seat's model and effort. Nothing is written yet.
3. **(30s)** Approve. The scaffold reports `ADDED` / `KEPT` / `CONFLICT` per file.
4. **(2 min)** **Break it on purpose** - `cat .env`, a commit on `main`, `git -c k=v commit` on
   `main`, an edit to an Accepted ADR. All blocked. This is the moment the talk is built around.
5. **(90s)** `python eval/guardrail_eval.py` live. *"No model was consulted. These are exit codes."*
6. **(60s)** `python .claude/scripts/verify-plan.py` on a docs-only change: secret scan, nothing else.
7. **(60s)** `/task-resume` in a fresh session: it reads the checkpoint and picks up mid-task.

Fallbacks: tooling fails → the clips on slide 25, then the gallery. Short on time → cut 6 and 7,
**never 4 or 5**.

---

## 7. Close (2 min) - slide 26

The agent understands the repo. It cannot leave the harness. The work is checked in proportion to
the change.

```
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install harness-bootstrap@agent-harness-bootstrap
/plugin install spec-builder@agent-harness-bootstrap

/spec-builder           # write the contract first
/harness-bootstrap      # build the harness for this repo
```

Nothing is written until the one-screen plan is approved. Point to the repo, the clip gallery and
`docs/FLOWS.md`, and offer to run it on a volunteer's repo.

---

## Q&A preparation

| Question | Short answer |
|---|---|
| *Does this lock us into Claude Code?* | No. It ports to Cursor and Codex with enforcement; `AGENTS.md` is the vendor-neutral contract |
| *We already have a `.claude/` folder.* | It reconciles, never clobbers. Differences come back as `CONFLICT` |
| *Our repo is research, not code.* | Purpose profiles: a research repo gets `researcher` and `checker`, verified by sources, with no test or code-review seat |
| *Can the agent work around a hook?* | The deny list can be; it is a speed bump. Hooks fire before the tool runs and exit 2, git global options included |
| *What if a hook crashes or hangs?* | A blocking guard fails closed: the call is blocked. A missing interpreter is the one case that warns and allows, because a guard that blocks everything gets switched off |
| *Does a cheaper model break safety?* | No: no model is consulted, the guardrails are shell scripts. Code quality and review depth do degrade |
| *Does this slow developers down?* | Not on small work. Inline and Direct skip the orchestrator and the task file, a docs change gets no reviewer, and the ledger refuses re-runs that would learn nothing |
| *Is this just a big CLAUDE.md?* | A CLAUDE.md is advice the model may forget after compaction. This is enforcement plus durable state |
| *Who owns the policy decisions?* | You do. Governance rules ship as blanks; the skill never invents a licence policy or a classification table |

---

## Timing variants

| Slot | What to do |
|---|---|
| **20 min** | Sections 0, 1, slide 5, the question map (slide 7) with Q2 and Q3, slide 20, a short demo (steps 2, 4, 5), 7 |
| **40 min** | As written |
| **60 min** | Add a `docs/FLOWS.md` walkthrough, a `spec-builder` pass with its clip, the `docs/ASSESSMENT.md` limits, and an audit-mode demo |

Never cut Section 0 or the human side of Section 1.

---

## Fact sheet

Checked by `scripts/check_numbers.py`; re-run it rather than editing a figure by hand.

- 18 agents (+1 dev-agent template), 17 rules, 23 commands, 27 hooks; a run installs 3 to 17 of the 18 seats
- 7 unconditional rules, 10 path-scoped; 75% of rule content stays out of the default session
- Guardrail eval 312/312 (134 must-block, 178 must-allow) per hook flavour with `hooks_strict`, `long` and `db` on, no model consulted; port adapter 34/34
- spec-builder: 6 core sections, up to 8 optional
- Four routing tiers: Inline, Direct, Standard, Guarded - only Guarded uses the orchestrator
- Five task states: `Planned`, `Active`, `Blocked`, `Pending`, `Done`
- Four modes: Greenfield, Brownfield, Audit, Update
- Four purposes: code, research, strategy, docs
- Six rubric categories: Safety, Cost control, Traceability, Board health, Docs quality, Contract

---
name: harness-bootstrap
version: 1.5.0
description: Bootstraps or standardizes the complete AI-agent harness for a repo - analyzes the existing source first, then generates the .claude folder (agents with explicit model/effort/tool budgets, path-scoped rules, commands, hooks, settings.json), the docs tree (specs/requirements/architecture/tasks/context), and AGENTS.md + CLAUDE.md, so the repo runs under orchestrator-driven task control. Also runs in a read-only audit mode that builds an audit control plane beside untouched source. Use when the user asks to "set up base", "thiet lap base coding", "chuan hoa claude folder", "chuan hoa source thanh claude ready", "khoi tao workspace cho AI agents", "set up agents for this repo", or adopts a project that should follow the standard structure.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(git:*), Read, Write, Edit, Grep, Glob, AskUserQuestion, Agent, WebSearch
---

# Harness bootstrap

Sets up the standard operating harness for a repo: a roster of agents that know their scope and their
cost, rules that load only when relevant, hooks that actually fire, and a task board that survives
context compaction.

**The assets are real files, not prose to retype.** Everything copyable lives under `assets/` and is
installed by `scripts/scaffold.py`. Your job is the decisions - the roster, the scope, the variables -
not transcribing 1,300 lines of hooks and commands. Read a reference file when you reach its step;
never improvise a step that has one.

## Four modes - decide first

| Mode | When | What happens |
|---|---|---|
| **Greenfield** | Empty or near-empty repo | Generate the full structure from intake answers |
| **Brownfield** | Repo already has code, and maybe a partial `.claude/` | Run codebase analysis FIRST, derive most answers from evidence, then RECONCILE - never clobber |
| **Audit** | The repo(s) will be analysed but never modified by agents; a human applies any fixes | Build a read-only control plane beside untouched source. See [`reference/audit-mode.md`](reference/audit-mode.md) |
| **Update** | The repo was already bootstrapped by this skill and the user wants to tune it, add or retire agents, or pick up newer assets | Follow the installed `/harness-update` command: re-read reality, re-run the scaffolder with the existing `vars.json`, resolve the CONFLICT queue by hand. Do NOT redo intake - ask only the questions whose answers changed |

Selection rule: a `vars.json` (or a `.claude/` this skill clearly generated) means **update** - never
re-bootstrap over it. Otherwise: if agents will never modify the source (a human applies fixes), you
are in **audit** mode, however much code exists; any source code at all means **brownfield**.

Update mode in one line each: single dials → `/harness-tune` (control posture) or
`/agent-permissions` (one seat's tools); structural change (new seats, new assets, re-scope) → the
`/harness-update` procedure. All three are installed by the bootstrap itself.

## Procedure

**0. Codebase analysis** - brownfield and audit: MANDATORY. Greenfield: skip.
Follow [`reference/codebase-analysis.md`](reference/codebase-analysis.md). Produce the Inventory Report
(stack, modules, conventions, risky operations, existing assets, gaps) and show it to the user before
anything else. Its mapping tables - modules→dev agents, conventions→rules, risky ops→deny/hooks -
parameterize every later step.

**1. Intake** - [`reference/intake.md`](reference/intake.md). Closed-choice questions (methodology,
effort profile, control level, dev OS, docs language, and similar) go through the **`AskUserQuestion`**
tool: max 4 options per question, recommended option first labeled `"(Recommended)"`, up to 4 questions
batched per call. Free-text answers (project name, commands, globs) stay plain chat questions. In
brownfield, pre-fill every answer the analysis produced and only ask about what code cannot decide: docs
language, commit identity, data sensitivity, gated actions. **If no specs exist** (intake Q3), invoke the
`spec-builder` skill via the **`Skill`** tool before continuing - do not just note the gap and move on;
if the `Skill` tool is unavailable, state the exact handoff in words (what to run, with which inputs)
instead of a vague "hand off". Then echo a one-screen setup plan - what will be created, kept, and
modified, plus **the roster with each agent's model and effort** - and get confirmation before writing
anything.

**Detect the target tools first, then confirm them.** Before the plan, scan the repo for which AI
coding tools it already uses, and present the finding as the default for a question - never assume:
- `CLAUDE.md` or `.claude/` -> **Claude Code** (always the primary; the harness is generated for it).
- `.cursor/`, `.cursorrules`, or `AGENTS.md` -> **Cursor** is in use.
- `.codex/` or `AGENTS.md` -> **Codex** is in use (`AGENTS.md` is shared by both Cursor and Codex).

Then ask, with `AskUserQuestion` (multi-select), which tools the harness must run in. The answer sets
whether step 8 ports to Cursor, Codex, both, or neither. Detection only pre-fills the default; a team
may want Cursor support even if no `.cursor/` exists yet.

**2. Pick the roster** - [`reference/roster.md`](reference/roster.md). Tier 0 is unconditional
(orchestrator, the two reviewers, spec-guardian, ≥1 dev agent). Choose the preset (S/M/L) that matches
the project. Brownfield derives dev agents from the module mapping; greenfield from FR clustering, or a
single `app-dev` if no specs exist.

Every agent gets an explicit `model:` **and** `effort:`. Unset `model:` means `inherit`, which silently
bills mechanical work at the caller's tier. The allocation and the reasoning are in
[`reference/cost-model.md`](reference/cost-model.md) - read it before deviating from the table.

**2.5. Skill discovery and install** - [`reference/skill-discovery.md`](reference/skill-discovery.md).
Once the seats are known, ask (AskUserQuestion) whether to search [skills.sh](https://www.skills.sh/)
for skills matching them - recommended for dev and qa seats, skipped in audit mode. Every candidate
passes the trust rubric in the reference (installs, publisher, audit status, and a MANDATORY read of
the skill's actual files - a skill is instructions from the internet), and each install needs an
explicit yes per skill, never a batch. Installed skills serve nobody until `/skill-wire` maps them to
seats after bootstrap; the wire re-reviews content and records to `docs/context/tool-changelog.md`.

**3. Detect the dev OS.** This gates the hook flavor and the settings registration; get it wrong and the
guardrails never fire, silently. Windows → `.ps1` hooks. macOS/Linux → `.sh`. Mixed-OS team: pick the
majority and record the gap in `.claude/hooks/README.md`. Set the `windows` or `posix` flag accordingly.

**4. Run the scaffolder.** Write `vars.json` from the intake answers, then:

```bash
python scripts/scaffold.py --target <repo> --vars vars.json --dry-run   # review first
python scripts/scaffold.py --target <repo> --vars vars.json
```

`vars.json`:
```json
{
  "vars":  { "PROJECT_NAME": "...", "DEFAULT_BRANCH": "main", "PR_OR_MR": "PR", "...": "..." },
  "flags": ["posix", "ui", "db", "ai", "tdd", "ddd"]
}
```

Flags gate conditional assets and conditional blocks inside them: `ui`, `db`, `ai`, `audit`, `tdd`,
`ddd`, `deploy_ask`, and exactly one of `windows` / `posix`. Methodology: `tdd` AND `ddd` are both on
by default - red/green/refactor plus `rules/ddd.md`'s bounded-context discipline compose; drop one
only when intake explicitly picked a single methodology. `deploy_ask` moves `{{DEPLOY_CMD}}` from `permissions.deny` to
`permissions.ask` - set it only when intake's control-level question chose agent-initiated deploys.

The scaffolder **never overwrites an existing file**. It reports `ADDED` / `KEPT` (already identical) /
`CONFLICT` (exists and differs). **CONFLICT is not an error - it is the brownfield reconciliation
queue.** Resolve each by hand (keep, adapt, add, or flag), and never delete what the user wrote without
asking. It exits non-zero on an unresolved `{{VAR}}`, so a missing variable fails loudly instead of
shipping a placeholder into a rule file.

If Python is unavailable, `cp` the assets and edit the variables by hand. The assets are real files, so
this is still far cheaper than regenerating them - but say so, and fix Python.

**5. Fill in what only judgment can fill.** The scaffolder installs the invariant assets. You still author:
- the orchestrator's **routing table** (every agent appears; every module has exactly one owner),
- each dev agent's **scope** (real module paths - brownfield: paths that actually exist). When
  instantiating `dev-agent.md`, resolve its `{{#IF_...}}`/`{{^IF_...}}` blocks by hand against the
  chosen flags (keep the block's content if the flag matches, drop it otherwise) - the template is
  copied per-domain, not run through the scaffolder,
- the **project-specific rules** the scaffolder does not ship - `tech-stack.md`, `coding-standards.md`,
  `git-workflow.md` - written from the analysis, never invented. (`data-model.md` IS shipped: it
  carries the generic migration-safety discipline. You still fill in this project's actual entities.)
- the **settings.json allow/deny list** adapted to the actual stack found (the real DB-reset command,
  the real deploy command),
- `.env.example`, from config reads found in the source - never from guesswork.

**6. Wire up orchestration.** This is what makes the base *run*, not just exist:
- `docs/tasks/master-plan.md` gets the index table. In brownfield, seed Phase 1 from the analysis gap
  list - one registered task per gap - so the orchestrator finds real work on its first session.
- `AGENTS.md` names the orchestrator as the entry point for multi-step work and states the standard
  feature flow. `CLAUDE.md` is a thin `@AGENTS.md` import plus the Claude-specific bits - do not
  maintain two copies.
- Task lifecycle: [`reference/task-control.md`](reference/task-control.md). The orchestrator and
  `task-tracking.md` LINK to it; they do not restate it.

**7. Verify.** Run every checkable item in the quality gate below as an actual **`Bash`** tool call and
show its output in the response - never report a check as passed without having run it. Then smoke-test
the loop end to end: create one real task file, register it in master-plan, append a session-log row,
and `/task-resume` it. Finally, build the initial code graph - `python .claude/scripts/code-graph.py`
run via `Bash` from the repo root - so the orchestrator's first dispatch already has the module map
(`docs/context/code-graph.md`); on a greenfield repo with no source yet, note that `/code-graph`
should be run after the first module lands.

**8. Port to the other tools selected in step 1.** If the intake selected Cursor or Codex, run the
porter after scaffolding - `--tool cursor`, `--tool codex`, or `--tool all`:
`python scripts/port.py --target <repo> --tool all`. It converts `.claude/rules/`
into `.cursor/rules/*.mdc` (path-scoped rules become `globs:`, unconditional become `alwaysApply`),
and wires the hooks into each tool's hook system: Codex's payload matches Claude Code's so the hooks
register directly; Cursor gets a generated adapter that translates its payload and output. Two honest
limits it prints: Codex routes file edits through `apply_patch` so `protect-adr` is best-effort there,
and Cursor's `afterFileEdit` is observational so an ADR edit is flagged, not blocked, in Cursor. The
rules and the Bash-based guards port exactly. `AGENTS.md` is already read natively by both tools.

## Quality gate

**Structure**
- [ ] `.claude/` has `settings.json`, `rules/`, `agents/`, `commands/`, `hooks/` (+README), and `docs/`
      has `README.md`, `specs/`, `requirements/`, `architecture/`, `tasks/` (master-plan + active +
      pending + done), `context/`, `templates/`.
- [ ] Every path referenced by an agent, command, or rule exists. No references to agents that were not
      created. The routing table covers every agent - no orphans.
- [ ] Every seat of the standard feature flow is filled by exactly one agent, per the check table in
      `roster.md`. Any intentionally unfilled seat is named in AGENTS.md with who covers it instead.

**Cost and context** (this is the part most bootstraps skip)
- [ ] Every agent has an explicit `model:` **and** `effort:`. Neither is unset. The allocation matches
      `roster.md`, or a deviation is justified in `docs/context/tool-changelog.md`.
- [ ] Every agent has an explicit `tools:` list. **No agent omits it** - omitting inherits every tool
      including every MCP server, at full schema cost on every request.
- [ ] **Reviewers have no `Edit` or `Write`.** Not "usually" - none.
- [ ] Every rule that can be path-scoped **carries `paths:` frontmatter**. Only `00-overview`,
      `agent-guardrails`, `model-policy`, `ai-governance`, `task-tracking`, and `conventional-commits`
      load unconditionally. A rule without `paths:` is a permanent context tax on every agent in every
      session.
- [ ] **No generated file contains a timestamp, a generation date, or a run ID.** These files are
      prompt-cache prefix content; one volatile byte cold-misses the cache on every future run.
- [ ] `CLAUDE.md` + `AGENTS.md` together stay under ~200 lines. Adherence drops above that.

**Safety**
- [ ] All four guardrail layers present: settings.json deny rules, hooks, `agent-guardrails.md`, and a
      review command gated by `/secret-scan`. [`reference/control-surfaces.md`](reference/control-surfaces.md)
      ranks every control by hardness (enforced vs advisory) and is the citable reference for this bullet.
- [ ] settings.json denies destructive ops (force push, `rm -rf`, direct prod deploy, secret reads, DB
      reset) **adapted to the stack actually found**. Note the limit honestly: these are prefix matches
      and are defeated by re-ordering (`rm -r -f`) - they are a speed bump, and the hooks are the gate.
- [ ] **Hooks were tested on this machine, via `Bash` tool calls with a sample JSON payload** - the
      block case exits 2 and the pass case exits 0, shown in the transcript. Not "should work". In
      PowerShell check `$LASTEXITCODE`, never `$?` (a boolean).
- [ ] Hook flavor and the settings registration lines match the detected OS.
- [ ] `.env.example` covers every integration in the tech-stack rule and nothing more; placeholders only.

**Governance**
- [ ] `model-policy.md`: the data-classification table is FILLED - no `{{MODEL_*}}` placeholder
      survives, and every class the project handles names a model or provider. A class with no
      approved model reads as an explicit "not delegated to an agent" STOP, never as a blank cell.
- [ ] `model-policy.md`: `{{DATA_RESIDENCY}}` answered; every provider approved for Confidential+ has
      a retention posture recorded in `docs/context/tool-changelog.md`.
- [ ] `ip-compliance.md`: the licence allow AND deny lists are set, by the org. A generated default
      here is a legal opinion nobody gave. `ai-governance.md`: `{{GATED_ACTIONS}}` names this
      product's real irreversible actions.

**Grounding (brownfield)**
- [ ] The Inventory Report was produced and confirmed. Every dev agent's scope names real paths. Every
      rule's conventions match observed code - or the deviation is a registered task, not a silent fix.
- [ ] Pre-existing content was reconciled, not clobbered. Nothing the user wrote was deleted without
      explicit approval.
- [ ] `master-plan.md` carries the migration backlog, so orchestration has work on day one.

**Handoff**
- [ ] Summary: what was created / kept / changed, the roster with its model+effort allocation, the
      orchestration flow, and the suggested next step (`/task-resume` - `spec-builder` should already
      have been invoked via the `Skill` tool in step 1 if no specs existed, not merely suggested here).

## Common vs project-specific - the reuse discipline

**Common** (shipped as assets, copied near-verbatim): the hooks, the settings deny core, the invariant
rules (`agent-guardrails`, `task-tracking`, `docs-workflow`, `conventional-commits`), the review
knowledge-bases, the core commands, the TASK/PRD/ADR templates, the docs tree shape, the agent bodies.
These encode process, not domain. **Do not inject project specifics into them** - that is what keeps them
diff-comparable across repos and upgradable by re-running the bootstrap.

**Project-specific** (parameterized from intake + analysis): `tech-stack`, `coding-standards`,
`data-model` entities, the frontend primitives, `git-workflow`, the commit scope list, the settings
allow-list, the orchestrator routing table, every dev agent's scope, `.env.example` groups.

The test: if the sentence would still be true in a different company's repo, it belongs to a common
asset. If it names a module, a provider, or a brand, it must come from a `{{VAR}}` - never be invented.

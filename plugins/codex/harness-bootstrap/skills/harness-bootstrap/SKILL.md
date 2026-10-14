---
name: harness-bootstrap
version: 1.21.2
description: Bootstraps or standardizes the AI-agent harness for a repo - analyzes the existing source first, then generates the .claude folder (agents with explicit model/effort/tool budgets, path-scoped rules, commands, hooks, settings.json), the docs tree and AGENTS.md + CLAUDE.md, so the repo runs under orchestrator-driven task control. Covers code repos and repos dedicated to research, strategy or documentation, plus a read-only audit mode beside untouched source. Use when the user asks to "set up base", "thiet lap base coding", "chuan hoa claude folder", "chuan hoa source thanh claude ready", "khoi tao workspace cho AI agents", "set up agents for this repo", or adopts a project that should follow the standard structure. Not for writing a specification set - that is spec-builder.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(git:*), Read, Write, Edit, Grep, Glob, AskUserQuestion, Agent, WebSearch
---

# Harness bootstrap

Installs the standard operating harness: a roster of agents that know their scope and cost, rules
that load only when relevant, hooks that fire, and a task board that survives context compaction.

**The assets are real files.** `scripts/scaffold.py` installs everything under `assets/`. Your job is
the decisions - roster, scope, variables - never retyping hooks or commands. Read each reference
when you reach its step, not before; never improvise a step that has one.

## Pick the mode first

| Mode | When | What happens |
|---|---|---|
| **Update** | a `vars.json`, or a `.claude/` this skill generated, exists | Follow the installed `/harness-update`: re-run the scaffolder with the existing `vars.json`, resolve the CONFLICT queue, ask only what changed. Never re-bootstrap over it |
| **Audit** | agents will never modify the source; a human applies fixes | A read-only control plane beside untouched source: [`reference/audit-mode.md`](reference/audit-mode.md) |
| **Brownfield** | any source code exists | Analysis first, answers from evidence, then RECONCILE - never clobber |
| **Greenfield** | empty or near-empty repo | The full structure from intake answers |

Check the rows top to bottom; the first match wins. A single dial is `/harness-tune` (control
posture) or `/agent-permissions` (one seat's tools), not a re-run.

## Procedure

**0. Codebase analysis** (brownfield and audit; greenfield skips). Follow
[`reference/codebase-analysis.md`](reference/codebase-analysis.md) and show the user its Inventory
Report before anything else. Its mapping tables parameterize every later step.

**1. Intake.** Follow [`reference/intake.md`](reference/intake.md): purpose first, then one
pre-answered questionnaire of at most two `AskUserQuestion` calls, asked in the user's own language.
Stack proposals come from [`reference/tech-presets.md`](reference/tech-presets.md). Detect the target
tools (Cursor, Codex) with pass 9 of the analysis and confirm them (intake Q3a). **If no specs exist**
(intake Q3), invoke `spec-builder` through the `Skill` tool with the confirmed `purpose_*` flags
before continuing; without the tool, state the exact handoff. Then echo a one-screen plan - created,
kept, modified, and the roster with each seat's model and effort - and get confirmation before
writing anything.

**2. Pick the roster** - [`reference/roster.md`](reference/roster.md): purpose profiles, presets,
the allocation table and every frontmatter field. Every seat gets an explicit `model:`, `effort:`,
`tools:` and `maxTurns:`; unset `model:` silently bills mechanical work at the caller's tier. Read
[`reference/cost-model.md`](reference/cost-model.md) only before deviating from the table.

**2.5. Skills** - [`reference/skill-discovery.md`](reference/skill-discovery.md), when the
questionnaire's Skills answer asks for it (never in audit mode). Every candidate gets a per-skill
read of its files; nothing installs without its own tick in one batched `AskUserQuestion`.

**3. Detect the dev OS.** Windows sets `windows` (`.ps1` hooks), macOS/Linux `posix` (`.sh`). Get it
wrong and the guardrails never fire, silently. Mixed team: pick the majority and record the gap in
`.claude/hooks/README.md`. `.claude/scripts/` is flavor-neutral stdlib Python; never fork it per OS.

**4. Run the scaffolder.** Write `vars.json` from the answers (intake's vars table maps each answer
to its variable or flag), then:

```bash
python scripts/scaffold.py --target <repo> --vars vars.json --dry-run   # review first
python scripts/scaffold.py --target <repo> --vars vars.json
```

```json
{
  "vars":  { "PROJECT_NAME": "...", "DEFAULT_BRANCH": "main", "PR_OR_MR": "PR", "...": "..." },
  "flags": ["posix", "ui", "db", "ai", "ddd"],
  "modules": [{"path": "src/billing", "owner": "billing-dev", "invariants": "- amounts are integer cents"}]
}
```

Flags gate conditional assets and blocks: exactly one of `windows` / `posix`; the purposes
`purpose_code`, `purpose_research`, `purpose_strategy`, `purpose_docs` (none means `purpose_code`);
then `ui`, `db`, `db_engineer`, `db_seeder`, `ai`, `audit`, `tdd`, `ddd`, `light`, `unit`, `e2e`,
`tests`, `deploy_ask`, `long`, `solo_review`, `merge_gate`, `hooks_strict`, `terse`, `rtk`, `pr_cli`,
`target_cursor`, `target_codex`. What each one ships is in intake's vars table. The scaffolder
refuses code-only flags without `purpose_code`, and derives `checker` itself.

Each `modules` entry renders a module `CLAUDE.md` (owner, scope, local invariants, commands; 40 lines
at most), loaded only when files there are read. Put module- and path-specific guidance there or in
a path-scoped rule, never in the root files.

The scaffolder **never overwrites a file**: it reports `ADDED`, `KEPT` (identical) or `CONFLICT`.
**CONFLICT is the brownfield reconciliation queue, not an error** - resolve each by hand and never
delete what the user wrote without asking. An unresolved `{{VAR}}` fails the run. Without Python,
copy the assets and substitute by hand, say so, and fix Python.

**5. Author what only judgment can.**
- The **roster and routing tables** in `AGENTS.md`: every seat appears, every module has exactly one
  owner. They live there once. Adapt the Guarded tier row to this project's real irreversible
  surfaces.
- Each dev agent's **scope**, from real paths. `dev-agent.md` is copied per domain by hand, so
  resolve its `{{#IF_...}}` blocks yourself.
- The rules the scaffolder never ships - `tech-stack.md`, `coding-standards.md`, `git-workflow.md` -
  from the analysis, never invented; and this project's entities in the shipped `data-model.md`.
- The `settings.json` allow/deny lists adapted to the real DB-reset and deploy commands, and
  `.env.example` from config reads found in the source.

Common assets (hooks, the deny core, the invariant rules, review knowledge bases, core commands,
templates, agent bodies) stay project-neutral so they remain diff-comparable and upgradable. A
sentence that names a module, provider or brand comes from a `{{VAR}}` or an authored file.

**6. Wire up orchestration.** Seed `docs/tasks/master-plan.md` - in brownfield, Phase 1 from the
analysis gap list, grouped into a few large tasks the user approves. The task lifecycle is
[`reference/task-control.md`](reference/task-control.md), its single source.

**7. Verify** - each item as a real `Bash` call with its output shown; a check you did not run is
not passed.
- `python .claude/scripts/harness-check.py` exits 0 (seats, tiers, routing, hooks, citations,
  skills, board).
- Each hook fires on this machine with a sample payload: block exits 2, pass exits 0 (in PowerShell
  read `$LASTEXITCODE`, never `$?`).
- One real task end to end: create, register, log a row, `/task-resume` it, then
  `python .claude/scripts/board-check.py` exits 0.
- The maps: `code-graph.py` (code repos; writes the module-boundary map), `docs-graph.py --check`
  (orphan IDs), then `harness-graph.py --html`.

**8. Port** when intake selected Cursor or Codex: `python scripts/port.py --target <repo> --tool
cursor|codex|all`. It prints its own limits; relay them.

## Quality gate

What `harness-check.py` cannot decide:

- [ ] Every seat of the Guarded flow is filled exactly once (`roster.md`'s completeness check); an
      intentionally unfilled seat is named in `AGENTS.md` with who covers it.
- [ ] Every rule that can be path-scoped carries `paths:`. Only `00-overview`, `agent-guardrails`,
      `model-policy`, `task-tracking`, `conventional-commits` and (with `ai`) `ai-governance` load
      unconditionally.
- [ ] No generated file carries a timestamp, a generation date or a run ID - they are prompt-cache
      prefix content.
- [ ] `CLAUDE.md` + `AGENTS.md` stay under 200 lines with the roster and routing tables filled in.
- [ ] All four guardrail layers exist: `settings.json` deny rules, hooks, `agent-guardrails.md`, and
      a review command gated by `/secret-scan`. Hardness of each control:
      [`reference/control-surfaces.md`](reference/control-surfaces.md).
- [ ] The deny list is adapted to the stack found (force push, `rm -rf`, prod deploy, secret reads,
      DB reset). Prefix matches are a speed bump; the hooks are the gate.
- [ ] Hook flavor and settings registration match the detected OS; `.claude/.gitignore` exists.
- [ ] Seats that need env values (devops, db, qa) use `.claude/scripts/env-read.py`, never `cat`.
      `.env.example` holds placeholders only.
- [ ] `model-policy.md` has no `{{MODEL_*}}` left and a class with no approved model reads as an
      explicit STOP; `{{DATA_RESIDENCY}}` is answered; every Confidential+ provider has a retention
      posture in `docs/context/tool-changelog.md`.
- [ ] `ip-compliance.md` licence allow and deny lists were set by the org; `ai-governance.md`'s
      `{{GATED_ACTIONS}}` names this product's real irreversible actions.
- [ ] Brownfield: the Inventory Report was confirmed, every dev scope names real paths, nothing the
      user wrote was deleted without approval, and `master-plan.md` carries the migration backlog.
- [ ] Handoff: what was created / kept / changed, the roster with model and effort, the flow, and
      the next step (`/task-resume`).

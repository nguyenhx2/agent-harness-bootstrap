# Root files pack (project-bootstrap)

Skeletons for the three root instruction files. All English. CLAUDE.md stays under ~80 lines -
details live in rules; AGENTS.md mirrors it for non-Claude tools; README.md is the human-facing
system README. The three files (plus `rules/00-overview.md`) must agree on principles and paths.

---

## CLAUDE.md

```markdown
# CLAUDE.md - {{PROJECT_NAME}}

{{ONE_PARAGRAPH_SYSTEM_DESCRIPTION}} Features {{FR_RANGE}} in
`docs/specs/05-functional-requirements.md`.

Stack: {{STACK_ONE_LINER}}. Details: `.claude/rules/tech-stack.md`.

## Mandatory rules

All system rules live in `.claude/rules/` - read `00-overview.md` first. Precedence on conflict:
`.claude/rules/` > per-folder CLAUDE.md > defaults.

Invariant principles:

1. {{IF_AI_PRODUCT}}**Human-in-the-loop**: AI only proposes; humans review and decide.
2. **Follow the specs**: every feature maps to an FR and meets its acceptance criteria.
3. **{{DATA_PRINCIPLE_TITLE}}**: {{DATA_PRINCIPLE_LINE}} - see `.claude/rules/security-privacy.md`.
4. **Guardrails**: least privilege, untrusted-data defense, never read secrets, gated destructive
   actions - see `.claude/rules/agent-guardrails.md`.
5. {{IF_UI}}**Frontend standards**: no emoji, SVG icons only, official brand assets - see
   `.claude/rules/frontend.md` and `design-system.md`.
6. **Writing style (everywhere)**: no emoji in any output; never the em dash - write "-";
   commits/{{PR_OR_MR}}s carry NO AI attribution. See `.claude/rules/conventional-commits.md`.

## Documentation map (docs/)

| Path | Role | When agents read it |
|------|------|---------------------|
| `docs/specs/` | 13-section BA specs - source of truth | ALWAYS, before working on a feature |
| `docs/requirements/` | PRD per feature (PRD-FR-NN) | When implementing the corresponding FR |
| `docs/architecture/system-overview.md` | High-level architecture | ALWAYS |
| `docs/architecture/decisions/` | ADRs - immutable once Accepted | Before technical decisions |
| `docs/architecture/api-contracts/` | API schemas per domain | When adding/changing endpoints |
| `docs/tasks/` | master-plan + task files with AI session log | Start and end of every session |
| `docs/context/` | Long-term memory (glossary, business-rules, known-issues, tool-changelog) | When business context is needed |
| `docs/templates/` | TASK / PRD / ADR templates | When creating new files |

Documentation rules: no new doc structures outside these folders; new files from templates;
requirement changes logged in `docs/specs/13-revision-history.md`. Docs language:
{{DOCS_LANGUAGE}} (codes/enums English); everything under `.claude/` and the root instruction
files is English; task files and ADRs are 100% English.

## Task state (survives context compaction)

Task progress lives in markdown under `docs/tasks/` (committed) - see
`.claude/rules/task-tracking.md`. Agents MUST update the task file's session log after every
working session and MUST run `/task-resume TASK-NNN` before continuing any task in a new or
compacted session. The task files, not conversation memory, are the source of truth.

## Agents and orchestration

The `orchestrator` agent is the mission controller and default entry point for multi-step work:
it plans, decomposes into tasks, dispatches the specialists below, supervises results against
acceptance criteria, and records history in the task files.

| Agent | Scope |
|-------|-------|
{{AGENT_ROSTER_TABLE_ROWS}}

Standard feature flow: `spec-guardian` (FR check) -> specialist implements with TDD -> `qa-test`
-> `code-reviewer` + `security-reviewer` -> open {{PR_OR_MR}}. Command: `/implement-fr FR-NN`.

## Common commands

{{COMMAND_LIST_ONE_LINE}}

## Git

**{{GIT_PLATFORM}}** {{INSTANCE_HOST}}, repo `{{REPO_SLUG}}` - {{PR_OR_MR}}s, `{{PLATFORM_CLI}}`
CLI, CI in `{{CI_FILE}}`. See `.claude/rules/git-workflow.md`: never commit directly to
{{DEFAULT_BRANCH}}, Conventional Commits (hook-enforced), commit identity is **{{COMMIT_NAME}}**
`<{{COMMIT_EMAIL}}>` - verify `git config user.name`/`user.email` before every commit.

## Hooks

`.claude/hooks/` (registered in `settings.json`) automatically: block edits to Accepted ADRs,
block commit/push directly to {{DEFAULT_BRANCH}}, validate commit messages, block secret reads and
destructive DB commands, remind about revision history on spec changes. See `.claude/hooks/README.md`.

## AGENTS.md

`AGENTS.md` is the equivalent guide for other AI tools; the two files must stay in sync - when you
edit CLAUDE.md, update AGENTS.md accordingly.
```

## AGENTS.md

Same content as CLAUDE.md restructured for tool-agnostic agents, PLUS this preamble:

```markdown
# AGENTS.md - {{PROJECT_NAME}} (guide for AI coding tools)

This file mirrors CLAUDE.md for AI tools other than Claude Code (Codex, Cursor, Windsurf, ...).
The two files must stay in sync.

IMPORTANT - enforcement gap: Claude Code enforces guardrail layers 1-2 (settings.json permission
gates and hooks) automatically. Other tools DO NOT have those layers and must strictly self-comply
with the behavioral rules (`.claude/rules/agent-guardrails.md`, `security-privacy.md`) and the
review gates (`/review-{{PR_OR_MR_SLUG}}`, `/secret-scan` equivalents): never read `.env*` except
`.env.example`, never commit to {{DEFAULT_BRANCH}}, never run destructive DB commands, Conventional
Commits with no AI attribution, always update the task file session log.

[... then the same sections: rules, docs map, task state, agent roster (as role descriptions),
feature flow, git ...]
```

## README.md (human-facing)

Sections to generate:

1. **What & why** - the system in two paragraphs; feature table (FR / name / priority / status).
2. **Architecture** - Mermaid diagram (services, data stores, external providers) + stack table.
3. **Repository layout** - annotated tree (src modules, docs tree, .claude).
4. **How AI agents operate this repo** - entry points (orchestrator, /implement-fr), markdown task
   tracking under docs/tasks/, the four guardrail layers, the review gates. One short section -
   link to CLAUDE.md for the full contract.
5. **Getting started** - prerequisites, `cp .env.example .env.local` (fill values), install/dev/
   test commands, local services (docker compose) if any.
6. **Contributing** - branch naming, Conventional Commits, {{PR_OR_MR}} flow, review gates, CI.
```

# CLAUDE.md - {{PROJECT_NAME}}

@AGENTS.md

The imported `AGENTS.md` is the full contract and the single source of truth: the rules, the
documentation map, task state, the agent roster, the commands, testing, and git. Everything below
adds the Claude Code specific surface. It never restates or contradicts the contract above.

## Claude Code specifics

### Agents

Subagents are defined in `.claude/agents/` and rostered in `AGENTS.md`. The `orchestrator` is the
default entry point for any multi-step mission: dispatch it rather than driving the specialists by
hand, so that the work is decomposed into tasks and the history lands in the task files.

### Hooks

`.claude/hooks/`, registered in `.claude/settings.json`, enforce automatically what the rules
otherwise only state: edits to Accepted ADRs are blocked, commits and pushes directly to
`{{DEFAULT_BRANCH}}` are blocked, commit messages are validated against Conventional Commits, reads
of secret files are blocked, and destructive database commands are blocked. See
`.claude/hooks/README.md`.

A hook that blocks you is a rule you were about to break. Fix the action, and never route around
the hook, disable it, or reach for a shell equivalent of the blocked tool call.

### Settings

`.claude/settings.json` holds the permission rules (allow, ask, deny) and the hook registrations.
Changing it, or changing the rules, agents, or hooks, is a self-governing change: it needs the
owner's approval and never happens on an agent's own initiative.

### Commands

`.claude/commands/` holds the slash commands listed in `AGENTS.md`. `/deploy` is gated: it is
excluded from model invocation, so it runs only when the user invokes it directly, never as a step
an agent decides to take on its own.

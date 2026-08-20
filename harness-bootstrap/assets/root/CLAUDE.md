# CLAUDE.md - {{PROJECT_NAME}}

@AGENTS.md

The imported `AGENTS.md` is the full contract and the single source of truth: the rules, the
documentation map, task state, the agent roster, the commands, testing, and git. Everything below
adds the Claude Code specific surface. It never restates or contradicts the contract above.

## Claude Code specifics

### Agents

Subagents are defined in `.claude/agents/` and rostered in `AGENTS.md`. How much process a change
gets is decided by the tier table there, before anything is dispatched. The `orchestrator` is for
Guarded work - two or more domains, or a change touching schema, auth, money, a public contract, a
migration or a deploy - where decomposition into tasks and a durable history are worth their cost.
Single-domain work goes straight to the seat that owns it.

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

`.claude/commands/` holds the slash commands; the main ones are tabled in `AGENTS.md`. `/deploy` is gated: it is
excluded from model invocation, so it runs only when the user invokes it directly, never as a step
an agent decides to take on its own.

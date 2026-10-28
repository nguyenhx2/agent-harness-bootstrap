# CLAUDE.md - {{PROJECT_NAME}}

@AGENTS.md

`AGENTS.md` above is the contract. This file adds only the Claude Code surface and never restates it.

## Routing: who does the work

You do, at every tier in `AGENTS.md`. The tier sets how much checking the change gets, not who
writes it. The Agent tool is for the independent reviewer (required on a Guarded change), a large
read that returns a summary, and independent parallel batches. Wait for every dispatch to report and
check its result before your final answer.

A write-capable seat runs only when the user names it: put `TIER: direct` or `TIER: standard` in
the prompt, or a registered TASK-NNN (`guard-agent-spawn` refuses a write dispatch with neither).
The `orchestrator` runs only when the user asks for it; when it answers `Verdict: no orchestration
needed`, do the work here. Nesting depth and fan-out are capped in `.claude/settings.json` `env`.

## Hooks and settings

The hooks in `.claude/hooks/` (listed in its `README.md`) enforce what `AGENTS.md` states. A hook
that blocks you is a rule you were about to break: fix the action, never route around it, disable
it, or reach for a shell equivalent. Changing `.claude/settings.json`, a rule, an agent or a hook
needs the owner's approval.{{#IF_PURPOSE_CODE}} `/deploy` runs only when the user types it.{{/IF_PURPOSE_CODE}}

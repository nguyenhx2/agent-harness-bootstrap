# CLAUDE.md - {{PROJECT_NAME}}

@AGENTS.md

`AGENTS.md` above is the contract. This file adds only the Claude Code surface and never restates it.

## Routing: who does the work

Decide the tier from the table in `AGENTS.md`, then:

- **Inline** - you, the main session, do it and check the one thing you changed. No subagent:
  briefing one costs more than the work.
- **Direct / Standard** - dispatch the owning seat (`.claude/agents/`) once, with `TIER: direct` or
  `TIER: standard` in the prompt and no task file (`guard-agent-spawn` accepts the marker in place of
  a TASK-NNN). Read its report, check `git diff --stat`, done.
- **Guarded** - the `orchestrator`. For a long mission, start the session as it
  (`claude --agent orchestrator`) so the plan and the dispatches share one context.

Never dispatch the orchestrator for single-seat work. When it answers `Verdict: no orchestration
needed`, follow the route it names; `Verdict: cannot delegate`, do the work yourself at that tier; a
`Blocked` task with a human decision, ask the user and resume the same TASK-NNN. Nesting depth and
fan-out are capped in `.claude/settings.json` `env`.

## Hooks and settings

The hooks in `.claude/hooks/` (listed in its `README.md`) enforce what `AGENTS.md` states. A hook
that blocks you is a rule you were about to break: fix the action, never route around it, disable
it, or reach for a shell equivalent. Changing `.claude/settings.json`, a rule, an agent or a hook
needs the owner's approval.{{#IF_PURPOSE_CODE}} `/deploy` runs only when the user types it.{{/IF_PURPOSE_CODE}}

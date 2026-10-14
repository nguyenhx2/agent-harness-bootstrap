# CLAUDE.md - {{PROJECT_NAME}}

@AGENTS.md

The imported `AGENTS.md` is the full contract and the single source of truth: the rules, the
documentation map, task state, the agent roster, the commands, testing, and git. Everything below
adds the Claude Code specific surface. It never restates or contradicts the contract above.

## Claude Code specifics

### Routing: who does the work

Subagents are defined in `.claude/agents/` and rostered in `AGENTS.md`. Decide the tier from the
table there before dispatching anything, then:

- **Inline** - you, the main session, do it. Answer the question, make the edit, check the one
  thing you changed. No subagent: briefing one costs more than the work.
- **Direct / Standard** - dispatch the owning seat once, with `TIER: direct` or `TIER: standard`
  in the prompt and no task file (`guard-agent-spawn` accepts the marker in place of a TASK-NNN).
  Read its report, check `git diff --stat`, done.
- **Guarded** - the `orchestrator`. For a long mission, start the session as it
  (`claude --agent orchestrator`): the plan and the dispatches then share one context.

Never dispatch the orchestrator for single-seat work. When it answers `Verdict: no orchestration
needed`, follow the route it names; `Verdict: cannot delegate`, do the work yourself at that tier; a
`Blocked` task with a human decision, ask the user and resume the same TASK-NNN. Nesting depth and
fan-out are capped in `.claude/settings.json` `env`, so a delegation loop ends even when a prompt
does not stop it.

### Hooks, settings, commands

The hooks in `.claude/hooks/` (listed in `.claude/hooks/README.md`) enforce what `AGENTS.md`
states. A hook that blocks you is a rule you were about to break: fix the action, never route
around it, disable it, or reach for a shell equivalent. Changing `.claude/settings.json`, a rule,
an agent or a hook needs the owner's approval, never an agent's own initiative.{{#IF_PURPOSE_CODE}} `/deploy` is
excluded from model invocation: it runs only when the user types it.{{/IF_PURPOSE_CODE}}

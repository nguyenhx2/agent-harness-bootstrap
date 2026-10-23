# harness-bootstrap

**English** · [日本語](README.ja.md)

Builds the AI-agent harness a repository actually needs. It reads the source first, then writes
the `.claude/` folder - agents with explicit model, effort and tool budgets, path-scoped rules,
commands, hooks that block in the shell, `settings.json` - plus the `docs/` tree and
`AGENTS.md` / `CLAUDE.md`. A read-only audit mode builds an audit control plane beside source it
does not touch.

## Install

```text
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install harness-bootstrap@agent-harness-bootstrap
```

Or as a plain skill, for any agent the `skills` CLI supports:

```bash
npx skills add nguyenhx2/agent-harness-bootstrap --skill harness-bootstrap
```

Then run `/harness-bootstrap` in your repository. Nothing is written until you approve a
one-screen plan, and existing files are reconciled, never overwritten.

## Commands

`/harness-update`, `/harness-tune`, `/harness-toggle`, `/agent-permissions`, `/skill-wire`,
`/board-audit`, `/code-graph` and `/docs-graph` maintain a harness once it exists.

## What it runs, sends and fetches

- **Runs:** `python` on the bundled `scripts/scaffold.py` and `scripts/port.py`, `git` to read
  history, and `bash` or PowerShell to prove that the hooks it installs fire. Both scripts use only
  the Python standard library and write only inside the target repository.
- **Sends:** nothing. There is no telemetry, no server and no MCP server.
- **Fetches:** only through the agent's own `WebSearch`, when audit mode dates its baseline or
  `/skill-wire` looks for a skill. The hooks it installs make no network calls.

Full documentation, the scoring rubric and the `harness-view` viewer:
<https://github.com/nguyenhx2/agent-harness-bootstrap>. Licensed AGPL-3.0-only.

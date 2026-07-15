# The harness in Claude Code

Claude Code is where the harness is **generated** and where it enforces most completely. It reads
`.claude/` (agents, rules, hooks, `settings.json`) plus `AGENTS.md` and `CLAUDE.md`. Enforcement is the
`settings.json` permission deny list backed by six blocking hooks. Cursor and Codex render the same
harness; this is the reference implementation they are ported from.

## Setup

No porter step. The harness lands here directly when you scaffold it. From Claude Code, run
`/harness-bootstrap` (or copy an existing `.claude/` in). Requires Python 3. That is the whole install:
everything below is written by `scripts/scaffold.py`, not by hand.

## What lands

| Path | What it does |
|---|---|
| `.claude/agents/` | 15 agents, each with an explicit `model`, `effort`, `tools`, and `maxTurns` |
| `.claude/rules/*.md` | 14 rules with optional `paths:` frontmatter for path-scoped lazy loading |
| `.claude/hooks/` | 6 hooks (`.sh` on macOS/Linux, `.ps1` on Windows) plus a README |
| `.claude/settings.json` | Permission allow/deny list and the PreToolUse / PostToolUse / SubagentStop hook registration |
| `AGENTS.md` + `CLAUDE.md` | The vendor-neutral contract; `CLAUDE.md` is a thin `@AGENTS.md` import plus Claude-only bits |

Rules load lazily. A rule with no `paths:` loads every session; a rule with `paths: [glob]` attaches only
when a matching file is touched. Only 6 of the 14 load unconditionally: `00-overview`, `agent-guardrails`,
`model-policy`, `ai-governance`, `task-tracking`, `conventional-commits`. The other 8 stay off the default
context.

## What enforces vs. what is advice-only

| Control | Event | Effect |
|---|---|---|
| `protect-secrets` | PreToolUse (Bash + file reads) | Blocks reads of `.env`, keys, `~/.ssh`, `.npmrc` |
| `protect-adr` | PreToolUse (edits) | Blocks edits to an Accepted ADR |
| `guard-main-commit` | PreToolUse (Bash) | Blocks a direct commit to the default branch |
| `check-commit-msg` | PreToolUse (Bash) | Blocks a non-conventional or AI-attributed commit message |
| `specs-reminder` | PostToolUse | Flags: reminds after the fact, does not block |
| `agent-history` | SubagentStop | Records subagent history; observational, not a block |
| `settings.json` `permissions.deny` | Every tool call | Blocks force push, `rm -rf`, prod deploy, secret reads, DB reset (prefix match) |
| `.claude/rules/*.md` | Loaded into context | Advice only. A model can drift from a rule after a compaction |

A blocking hook exits 2 to deny. The deny list is a prefix match and is defeated by re-ordering flags
(`rm -r -f`), so it is a speed bump and the hooks are the real gate.

## Honest limits

- The deny list matches command prefixes only; treat it as a speed bump, not a wall. The hooks are the
  enforcement layer.
- Rules are advice. Only what is written as a hook or a deny entry actually blocks.

## Verify it works

Feed a known-bad payload to a hook and confirm it exits 2:

```bash
echo '{"cwd":".","tool_name":"Bash","tool_input":{"command":"cat .env"}}' \
  | bash .claude/hooks/protect-secrets.sh ; echo "exit=$?"    # expect exit=2
```

On Windows use the `.ps1` hook and check `$LASTEXITCODE`, never `$?`. For the full sweep, the repo ships
`python eval/guardrail_eval.py` (15 known-bad payloads at a real generated harness, expect 15/15). In the
tool itself, try to read `.env` or commit to `main` and confirm each is blocked.

## See also

- [Main README](../../README.md)
- [AGENTS.md contract](../../harness-bootstrap/assets/root/AGENTS.md)

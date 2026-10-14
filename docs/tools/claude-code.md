# The harness in Claude Code

**English** · [日本語](claude-code.ja.md)

Claude Code is where the harness is **generated** and where it enforces most completely. It reads
`.claude/` (agents, rules, hooks, `settings.json`) plus `AGENTS.md` and `CLAUDE.md`. Enforcement is the
`settings.json` permission deny list backed by hooks: a base set every harness registers, plus
guards that ship behind a flag (`hooks_strict`, `db`, `long`, and the research and docs purposes).
Cursor and Codex render the same harness; this is the reference implementation they are ported from.

## Setup

No porter step. The harness lands here directly when you scaffold it. From Claude Code, run
`/harness-bootstrap` (or copy an existing `.claude/` in). Requires Python 3. That is the whole install:
everything below is written by `scripts/scaffold.py`, not by hand.

## What lands

| Path | What it does |
|---|---|
| `.claude/agents/` | 3 to 17 of the 18 seats, picked by the repo's purpose and flags, each with an explicit `model`, `effort`, `tools`, and `maxTurns` |
| `.claude/rules/*.md` | Up to 17 rules (7 unconditional, 10 path-scoped, with every flag on) with optional `paths:` frontmatter for lazy loading |
| `.claude/hooks/` | Up to 26 hook scripts (`.sh` on macOS/Linux, `.ps1` on Windows) plus a README; the flags decide which are installed and registered |
| `.claude/scripts/` | Stdlib Python the harness runs on itself: `task.py`, `verify-plan.py`, `board-check.py`, `harness-check.py`, `harness-graph.py`, `code-graph.py`, `docs-graph.py`, `skill-check.py`, `harness-toggle.py`, `env-read.py` |
| `.claude/settings.json` | Permission allow/deny list, the spawn caps in `env`, and the hook registration |
| per-module `CLAUDE.md` | One per module from the analysis, 40 lines at most, loaded only when files there are read |
| `AGENTS.md` + `CLAUDE.md` | The vendor-neutral contract; `CLAUDE.md` is a thin `@AGENTS.md` import plus Claude-only bits |

Rules load lazily. A rule with no `paths:` loads every session; a rule with `paths: [glob]` attaches only
when a matching file is touched. Only 7 of the 17 load unconditionally: `00-overview`, `agent-guardrails`,
`model-policy`, `task-tracking`, `conventional-commits`, `ai-governance` and `output-style` - the last
two ship only with the `ai` and `terse` flags, so a default install loads fewer. The other 10 stay off
the default context; seat tiers live in the path-scoped `model-tiers`, which loads only when an agent
file or `settings.json` is touched.

## What enforces vs. what is advice-only

| Control | Event | Effect |
|---|---|---|
| `protect-secrets` | PreToolUse (Bash + file reads) | Blocks reads of `.env`, keys, `~/.ssh`, `.npmrc` |
| `protect-adr` | PreToolUse (edits) | Blocks edits to an Accepted ADR |
| `guard-main-commit` | PreToolUse (Bash) | Blocks a direct commit to the default branch |
| `check-commit-msg` | PreToolUse (Bash) | Blocks a non-conventional or AI-attributed commit message |
| `guard-destructive` | PreToolUse (Bash/PowerShell) | Blocks `rm -rf` on the repo root or home, a force push to a protected branch, `git reset --hard`, a DROP on a non-local host |
| `guard-agent-spawn` | PreToolUse (Agent/Task) | Blocks an off-roster agent, a non-pinned model, a write-capable dispatch with no task or tier marker, and a verification re-run the ledger shows already passed |
| `guard-board` | PreToolUse (edits) | Blocks a hand edit of a task row on the board; `task.py` is the writer |
| `guard-task-scope` | PreToolUse (edits) | Blocks creating a task file with no recorded request or fewer than two real criteria |
| `guard-agent-scope` | PreToolUse (edits) | Advisory only: nudges when an edit falls outside the sole active task's modules; the payload names no calling subagent, so it cannot block |
| `specs-reminder` | PostToolUse | Flags: reminds after the fact, does not block |
| `graph-stale` | PostToolUse | Refreshes the harness graph on a `.claude/` edit and names a new cross-module import on a source edit; never blocks |
| `agent-history` | SubagentStop | Records subagent history; observational, not a block |
| `hooks_strict` guards | various | Opt-in: large files, egress, unpinned dependencies, secrets in prompts and output, config changes, evidence-free "done". See `.claude/hooks/README.md` |
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
`python eval/guardrail_eval.py` (250 payloads at a real generated harness, expect 250/250; it measures a
harness scaffolded with `hooks_strict`, `long` and `db` on, so a default install carries fewer
hooks). No model is consulted: the guardrails are shell scripts, so the result cannot depend on
the model. In the
tool itself, try to read `.env` or commit to `main` and confirm each is blocked.

## See also

- [Main README](../../README.md)
- [AGENTS.md contract](../../harness-bootstrap/assets/root/AGENTS.md)

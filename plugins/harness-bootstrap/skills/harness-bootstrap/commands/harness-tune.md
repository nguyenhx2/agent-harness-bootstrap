---
description: Adjust how tight the harness is after bootstrap - deployment rights, deny/ask lists, spawn allowlist, attempt caps - with every change shown as a diff and confirmed before landing.
allowed-tools: Read, Grep, Glob, Edit, AskUserQuestion, Bash(git diff:*), Bash(git status)
---

Retune the control level of the harness in the repo you are currently in. This is the one
sanctioned path for loosening or tightening guardrails after bootstrap - changes land only with
the user's explicit confirmation, and the git diff of `.claude/` is shown before and after.

**Preflight.** Read `.claude/settings.json` first. If there is no `.claude/` directory, stop: this
repo has not been bootstrapped, and there is nothing to tune. Say so and point at the
`harness-bootstrap` skill.

**Read the real values, never assume them.** The scaffolded copy of this command has the repo's
deploy command and data paths baked in; this plugin copy does not. Before asking anything, read
them out of the repo:

- the deploy command: `permissions.deny` / `permissions.ask` in `.claude/settings.json`, and
  `.claude/commands/deploy.md` if it exists
- the database reset command: `.claude/commands/db-migration.md`, `package.json` scripts, or the
  `Makefile`
- the sensitive paths: the `Read(...)` deny entries in `settings.json` and
  `.claude/rules/model-policy.md`
- whether this repo runs split reviewers (`code-reviewer` + `security-reviewer`) or one merged
  `reviewer`: `ls .claude/agents/`

Quote what you found back to the user as part of the question. A dial turned against a guessed
value is a change nobody asked for.

Ask which dial to turn (AskUserQuestion, one batch), then apply only what was chosen:

1. **Deployment rights** - who may run the deploy command you just read:
   - `human-only` - keep/put it in `permissions.deny` (the default posture).
   - `agent-with-approval` - move it from `deny` to `ask`, so every run needs a live yes.
   - `agent-non-prod` - allow only the non-production variant the user names; production stays denied.
2. **Destructive-command posture** - same three-way choice for the database reset command,
   force-push, and `rm -rf`, each independently. Never remove a deny entry without naming its
   replacement control.
3. **Spawn allowlist** - add or remove types in `.claude/hooks/spawn-allowlist`. Warn before adding
   any write-capable type: it runs outside every roster budget.
4. **Attempt cap and turn caps** - raise or lower `maxTurns` per seat and the attempt cap in
   `.claude/rules/task-tracking.md`. Lowering is free; raising gets a cost warning.
5. **Review gates** - if this repo has split reviewers, toggle whether `security-reviewer` runs on
   every task or only on tasks touching the sensitive paths you read above; if it has one merged
   `reviewer`, tune how deep that pass goes on tasks that do not touch them. Removing the
   code-review gate entirely is refused; that is a different repo, not a tuning.
6. **Agent history detail** - edit `.claude/state/history-level` (line 1: `full`/`summary`/
   `minimal`/`off`; line 2: how many per-run files to keep). Lowering is free; raising to `full`
   gets a note that whole prompts and responses land on disk, PII included.

Turning a whole rule, command, or hook off (or back on) is not a tune - route that to
`/harness-bootstrap:harness-toggle`, which quarantines reversibly and records why.

Rules:
- Show the exact settings/file diff and get a yes BEFORE writing. One dial per confirmation.
- Record every accepted change in `docs/context/tool-changelog.md` (what, why, date, who asked).
- Never edit hooks' logic here. Tuning changes data (lists, caps, settings); hook code changes are
  a reviewed change like any other.

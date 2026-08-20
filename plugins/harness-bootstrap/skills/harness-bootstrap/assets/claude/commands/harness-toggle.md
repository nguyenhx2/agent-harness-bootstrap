---
description: Turn individual rules, commands, hooks, or agent seats off or back on at runtime - reversibly, with the change recorded and the harness graph refreshed.
allowed-tools: Read, Grep, Glob, AskUserQuestion, Bash(python .claude/scripts/harness-toggle.py:*), Bash(python3 .claude/scripts/harness-toggle.py:*), Bash(py -3 .claude/scripts/harness-toggle.py:*)
---

Enable or disable a single rule, command, hook, or agent seat without deleting anything. The script is the
only mutator - never move files or edit `settings.json` by hand for this.

Procedure:

1. Run `python .claude/scripts/harness-toggle.py list` and show the active/disabled inventory.
2. Ask what to change (AskUserQuestion built from the list). For a disable, ask for a one-line
   reason - it lands in `.claude/disabled.json` and is what a teammate reads six weeks later.
3. Show the exact invocation and what it will do (which files move, which `settings.json`
   registrations are removed) BEFORE running it. One item per confirmation.
4. Run it. The script updates `.claude/disabled.json` (committed - the team shares it, and
   scaffold re-runs respect it), moves the files under `.claude/disabled/`, and regenerates
   `harness-graph.json` + the HTML view so disabled items render greyed out.
5. Record the change in `docs/context/tool-changelog.md` (what, why, who asked).

Safety tiers the script enforces (do not try to route around them):

- **HARD** (`protect-secrets`, `guard-agent-spawn`, `security-privacy`, `agent-guardrails`,
  `review-changes`): the script exits 2 unless `--confirm "disable <name>"` carries that exact
  phrase. Relay the phrase ONLY if the user typed it themselves in this conversation - never
  compose it for them, never paraphrase it into the flag.
- **SOFT** (`guard-main-commit`, `check-commit-msg`, `protect-adr`, `ai-governance`): pass
  `--yes` only after the user explicitly confirmed.
- **Agents** park like anything else, but every seat is at least SOFT - the orchestrator's
  routing table still lists it, so a parked seat leaves a dispatch pointing at nothing. Fix the
  routing row in the same change. `orchestrator` and the reviewer seats (`code-reviewer`,
  `security-reviewer`, `reviewer`, `spec-guardian`) are HARD: only the orchestrator spawns, and
  the review seats ARE the code-review gate. Parking a seat is reversible; ADDING or RETIRING one
  is still `/harness-update`.

If a scaffold re-run or hand edit resurrected something that should be off, run
`python .claude/scripts/harness-toggle.py reapply` instead of disabling it again.

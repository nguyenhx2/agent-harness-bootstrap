---
description: Turn one rule, command, hook, or agent seat off or back on in the current repo - reversibly, with the reason recorded and the harness graph refreshed.
allowed-tools: Read, Grep, Glob, AskUserQuestion, Bash(python .claude/scripts/harness-toggle.py:*), Bash(python3 .claude/scripts/harness-toggle.py:*), Bash(py -3 .claude/scripts/harness-toggle.py:*)
---

Enable or disable a single rule, command, hook, or agent seat without deleting anything. The script is the
only mutator - never move files or edit `settings.json` by hand for this.

**Preflight.** This command operates on the repo you are currently in. If
`.claude/scripts/harness-toggle.py` is not there, stop and say so: either this repo has not been
bootstrapped (run the `harness-bootstrap` skill first), or it was bootstrapped by a version older
than the one that shipped the script (run `/harness-bootstrap:harness-update`). Do not fall back
to moving files yourself.

Procedure:

1. Run `python .claude/scripts/harness-toggle.py list` and show the active/disabled inventory.
2. Ask what to change (AskUserQuestion built from the list). For a disable, ask for a one-line
   reason - it lands in `.claude/disabled.json` and is what a teammate reads six weeks later.
3. Show the exact invocation and what it will do (which files move, which `settings.json`
   registrations are removed) BEFORE running it. One item per confirmation.
4. Run it. The script updates `.claude/disabled.json` (committed - the team shares it, and
   scaffold re-runs respect it), moves the files under `.claude/disabled/`, and regenerates
   `harness-graph.json` + the HTML view so disabled items render greyed out.
5. Record the change in `docs/context/tool-changelog.md` (what, why, who asked), if that file
   exists in this repo.

Safety tiers the script enforces (do not try to route around them):

- **HARD** (`protect-secrets`, `guard-agent-spawn`, `security-privacy`, `agent-guardrails`,
  `review-changes`): the script exits 2 unless `--confirm "disable <name>"` carries that exact
  phrase. Relay the phrase ONLY if the user typed it themselves in this conversation - never
  compose it for them, never paraphrase it into the flag.
- **SOFT** (`guard-main-commit`, `check-commit-msg`, `protect-adr`, `ai-governance`): pass
  `--yes` only after the user explicitly confirmed.
- **Agents** park like anything else, but every seat is at least SOFT: the orchestrator's routing
  table still lists it, so fix the routing row in the same change. `orchestrator` and the reviewer
  seats (`code-reviewer`, `security-reviewer`, `reviewer`, `spec-guardian`) are HARD. Parking is
  reversible; ADDING or RETIRING a seat is still `/harness-bootstrap:harness-update`, and tool
  grants are `/harness-bootstrap:agent-permissions`.

If a scaffold re-run or hand edit resurrected something that should be off, run
`python .claude/scripts/harness-toggle.py reapply` instead of disabling it again.

The same toggles are available without a model in the loop from `harness-view` (the optional
native viewer): select a node, use the button in the detail panel.

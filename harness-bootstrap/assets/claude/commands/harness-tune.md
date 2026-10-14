---
description: Tune the harness from evidence - reads the run archive, blocks and denials, retry and attempt-cap hits, verify-plan logs and the harness-view assessment, proposes a short ranked set of changes, asks once, applies the chosen ones and re-runs the check that proves each.
argument-hint: [focus - e.g. "cost", "too many blocks", "deploy"]
allowed-tools: Read, Grep, Glob, Edit, AskUserQuestion, Bash(git diff:*), Bash(git status), Bash(git log:*), Bash(python .claude/scripts/:*), Bash(python3 .claude/scripts/:*), Bash(harness-view assess:*)
---

Tune this harness from what actually happened in it, not from a fresh interview. Intake already
decided the shape; this command adjusts it where the record shows friction or risk. If `$1` names a
focus, weight the evidence toward it - never skip step 1.

## 1. Gather the evidence (read-only, one pass)

Collect each source if it exists; a missing source is a line in the report, not a reason to stop.

| Source | Read | What it can show |
|---|---|---|
| Run archive | `.claude/state/history/` (`index.md` and the per-run files) | seats never dispatched; runs that ended partial at `maxTurns`; one seat dominating the count |
| Blocks and denials | `BLOCKED:` and "denied" lines in the run archive and in task session logs | a guard that fires on legitimate work (false blocks), or a deny entry routed around by hand |
| Retry and attempt caps | `.claude/state/retry-budget`; `python .claude/scripts/task.py check`; `attempts:` and `Blocked` notes in `docs/tasks/active/` | loops the caps caught; tasks blocked by the cap rather than by a real blocker |
| Verification | the `log:` lines `verify-plan.py` wrote into task logs (`docs/tasks/**`) | gates that always run and never find anything; gates skipped on changes that later broke |
| Structure | `harness-view assess . --json` when the binary is on PATH; otherwise `python .claude/scripts/harness-graph.py` and `python .claude/scripts/board-check.py` | high and medium findings: orphan seats, unregistered hooks, unscoped rules |
| Recorded intent | `docs/context/tool-changelog.md`, `.claude/disabled.json` | what was tuned or switched off before, and why - never undo a recorded decision silently |

## 2. Propose at most four changes, ranked

Turn the evidence into candidate changes, each one a concrete edit with the evidence that motivates
it ("the review gate ran on 14 docs-only diffs and raised nothing"). Rank by impact: a safety gap
first, then repeated friction, then cost. Keep the top four; drop anything without evidence - a
change nobody's record asks for is a guess.

Each candidate maps to one of these dials, and only these:

1. **Deployment rights** - `{{DEPLOY_CMD}}` between `permissions.deny` (human-only), `permissions.ask`
   (agent with approval), or a named non-production variant in `allow`.
2. **Destructive commands** - deny entries for the database reset, force push, `rm -rf` and other
   stack-specific commands. A deny entry is never removed without naming the control that replaces it.
3. **Spawn allowlist** - `.claude/hooks/spawn-allowlist`. Adding a write-capable type runs work
   outside every roster budget; say so.
4. **Caps** - `maxTurns` per seat, the attempt cap in `.claude/rules/task-tracking.md`. Lowering is
   free; raising states the cost.
5. **Model and effort** - a seat's `effort:`, or its tier in `.claude/rules/model-tiers.md` first and
   the seat's `model:` second (the scaffolder refuses a seat that disagrees with its tier).
6. **Review gates** - when {{#IF_PURPOSE_CODE}}{{#IF_SOLO_REVIEW}}`reviewer`{{/IF_SOLO_REVIEW}}{{^IF_SOLO_REVIEW}}`security-reviewer`{{/IF_SOLO_REVIEW}}{{/IF_PURPOSE_CODE}}{{#IF_CHECKER}}{{#IF_PURPOSE_CODE}} or {{/IF_PURPOSE_CODE}}`checker`{{/IF_CHECKER}} is dispatched, through the triggers
   `.claude/scripts/verify-plan.py` reads (`.claude/verify-map.json`). Removing a review gate
   entirely is refused - that is a different repo, not a tuning.
7. **Agent-history detail** - `.claude/state/history-level`. Raising it to `full` puts whole prompts,
   PII included, on disk; say so.

Switching a whole rule, command, hook or seat off or on is `/harness-toggle`; adding or retiring a
seat, or a flag change, is `/harness-update`. Name the right command instead of doing it here.

## 3. Ask once

One `AskUserQuestion` call: a multi-select question listing the ranked changes (two to four
options), each label the change and each description its evidence and its cost. If the user picks
nothing, stop and report the evidence. If there were no candidates, say so with the numbers that
show it - "nothing to tune" is a result.

## 4. Apply, then prove each change

For each chosen change: show the exact diff, apply it, and run the check that exercises it - not
the whole eval.

| Change | Check |
|---|---|
| a deny/ask/allow entry | parse `.claude/settings.json` as JSON, then pipe one payload the entry should stop through the hook that guards it and read the exit code |
| spawn allowlist, caps, model or effort | `python .claude/scripts/harness-graph.py` (it refuses a malformed seat); for a tier change, re-read the tier row and the seat line together |
| review-gate triggers | `python .claude/scripts/verify-plan.py --files <a path from the evidence>` and confirm it now routes as intended |
| history level | the file's two lines read back as written |

A check that fails reverts that one change and is reported; the others stand.

## 5. Close the loop

`python .claude/scripts/harness-check.py` must exit 0; every finding names file:line and the fix. A finding introduced by this tune
is fixed or its change reverted before you report.

## 6. Record

One entry per applied change in `docs/context/tool-changelog.md`: what changed, the evidence, the
check that passed, who asked. Report outcome first: applied, declined, reverted, and what the next
review of this record should look at.

Never edit a hook's logic here - tuning changes data (lists, caps, frontmatter values), and hook
code is a reviewed change like any other.

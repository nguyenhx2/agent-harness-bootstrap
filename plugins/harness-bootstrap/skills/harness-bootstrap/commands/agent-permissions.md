---
description: Grant or revoke a single tool on a single roster seat, with the invariants that keep the roster safe enforced - reviewers stay read-only, only the orchestrator spawns, model changes go through the roster file.
allowed-tools: Read, Grep, Glob, Edit, AskUserQuestion, Bash(git diff:*)
---

Change one seat's `tools:` grant in the repo you are currently in.
Usage: `/harness-bootstrap:agent-permissions <agent> grant|revoke <Tool>`.

**Preflight.** If `.claude/agents/` does not exist, stop: this repo has no roster to permission.
Point at the `harness-bootstrap` skill. If it exists but the named seat does not, list the seats
that do rather than guessing which one was meant.

Procedure:

1. Read `.claude/agents/<agent>.md` and show the current frontmatter.
2. Check the change against the invariants below. If it violates one, refuse with the reason and
   the sanctioned alternative - do not ask for confirmation to break an invariant.
3. Show the exact frontmatter diff, get a yes, apply, and record it in
   `docs/context/tool-changelog.md` (seat, tool, direction, why, date).

Invariants (refusals, not warnings):

- **Reviewers never gain `Edit` or `Write`.** `code-reviewer`, `security-reviewer`, `reviewer`, and
  `spec-guardian` are gates; a gate that edits is a dev agent that lost its independence. If review
  findings should be auto-applied, that is a dev agent's task, dispatched with the findings.
- **Only the orchestrator holds `Agent`.** A second spawner is a second uncontrolled dispatch point;
  the scaffolder itself fails the build on it.
- **`model:` and `effort:` are not permissions.** Changing them is a roster/cost decision - point
  the user at the roster file and the skill's `reference/cost-model.md`, and require the change to
  be recorded.
- **No wildcard grants.** A seat lists exact tools; "give it everything" recreates the default-agent
  problem the roster exists to prevent.

Revocations apply immediately with no invariant check - narrowing is always safe.

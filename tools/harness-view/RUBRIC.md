# harness-view rubric

<!-- Generated: `harness-view rubric > RUBRIC.md`. Do not edit by hand. src/rubric.rs is the source; tests/rubric_test.rs keeps the two equal. -->

**English** · [日本語](RUBRIC.ja.md)

Every rule `harness-view assess` applies. Each finding names its rule id, the evidence (file:line), why it matters and a concrete fix, and the score can be recomputed from this table alone.

## How the score is computed

Each category starts at 100 and loses the weight of every finding in it (high 12, medium 5,      low 2, info 0), floored at 0. A rule that does not apply to this repository's purpose is not      checked, and a category with nothing to assess (Board health with no tasks; Traceability with      no tasks, commands or skills) is marked n/a rather than scored 100. Overall is the integer mean      of the six categories, n/a ones left out, rounded down; while a high Safety finding is open it      is capped at the Safety score, because a harness is only as trustworthy as its guardrails.      The weights are a stated convention, not a measurement.

| severity | weight |
|---|---|
| high | 12 |
| medium | 5 |
| low | 2 |
| info | 0 |

**Effort**: 1 = one click or one line, 2 = a small edit in one file, 3 = a decision or a new file. The worklist orders rules by weight times count divided by effort.

**Applies**: `all` to every repository, `code` when the repository's purposes include code, `non-code` when they include research, strategy or docs. The purposes come from the `purpose_*` flags in `.claude/state/vars.json`, else from the roster.

## Safety

### SAF-01 `reviewer-readonly`

- severity: high (weight 12) · effort: 1 · applies: all
- full marks: Every review seat (reviewer, checker, auditor ...) has no Edit, Write or NotebookEdit.
- finding: review seat `{name}` holds `{extra}`
- why: A reviewer that can write is not a gate; it can fix what it was supposed to report, and the review becomes self-approval.
- fix: Remove `{extra}` from `tools:` in `.claude/agents/{name}.md` and list it in `disallowedTools:`.

### SAF-02 `reviewer-disallowed`

- severity: low (weight 2) · effort: 1 · applies: all
- full marks: Every review seat names Edit and Write in `disallowedTools:`, so a later widening of `tools:` cannot grant them.
- finding: review seat `{name}` does not list Edit and Write in `disallowedTools`
- why: `tools:` says what a seat may use today; `disallowedTools:` keeps it true after someone edits the list.
- fix: Add `disallowedTools: Edit, Write, NotebookEdit` to the frontmatter of `.claude/agents/{name}.md`.

### SAF-03 `reviewer-memory`

- severity: medium (weight 5) · effort: 1 · applies: all
- full marks: No review seat sets `memory:`.
- finding: review seat `{name}` sets `memory:`
- why: Memory grants the seat Write and Edit on its memory directory, so a read-only reviewer is no longer read-only.
- fix: Delete the `memory:` line from `.claude/agents/{name}.md`.

### SAF-04 `spawn-boundary`

- severity: high (weight 12) · effort: 1 · applies: all
- full marks: Only the orchestrator holds a bare `Agent`; any other spawning seat names its targets as `Agent(a, b)`.
- finding: agent `{name}` can spawn any subagent
- why: Any seat with a bare Agent can fan out, and the spawn allowlist no longer bounds what runs.
- fix: In `.claude/agents/{name}.md`, remove `Agent` from `tools:`, or bound it: `Agent(<seat>, <seat>)`.

### SAF-05 `hook-missing-file`

- severity: high (weight 12) · effort: 2 · applies: all
- full marks: Every hook registered in settings.json or in a seat's frontmatter exists under `.claude/hooks/`.
- finding: hook `{name}` is registered but has no file on disk
- why: The registration runs a script that is not there, so the guardrail never fires and nothing reports it.
- fix: Restore `.claude/hooks/{name}.sh` (`/harness-update` re-installs shipped hooks), or delete the registration at the evidence line.

### SAF-06 `hook-unregistered`

- severity: medium (weight 5) · effort: 2 · applies: all
- full marks: Every hook file is registered in settings.json or a seat's frontmatter, or is a library another hook sources.
- finding: hook `{name}` exists but is not registered
- why: A hook nothing invokes is inert; it looks like a control and enforces nothing.
- fix: Register it in `.claude/settings.json`, e.g. `"PreToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "bash .claude/hooks/{name}.sh"}]}]`, or disable it in the viewer.

### SAF-07 `deny-list`

- severity: high (weight 12) · effort: 2 · applies: all
- full marks: settings.json carries a non-empty `permissions.deny` list.
- finding: settings.json has no permissions.deny entries
- why: The deny list is the first of the four guardrail layers; without it every destructive command reaches the hook layer or nothing at all.
- fix: Add to `.claude/settings.json`: `"permissions": {"deny": ["Bash(git push --force *)", "Bash(rm -rf *)", "Read(./**/.env)"]}`.

### SAF-08 `deny-coverage`

- severity: low (weight 2) · effort: 1 · applies: all
- full marks: The deny list covers force push, recursive delete and secret reads.
- finding: deny list does not mention {name}
- why: Deny rules are prefix matches and only a speed bump, but an absent one is not even that.
- fix: Add `{extra}` to `permissions.deny` in `.claude/settings.json`.

### SAF-09 `no-blocking-hook`

- severity: high (weight 12) · effort: 2 · applies: all
- full marks: At least one active hook is registered on PreToolUse or PermissionRequest.
- finding: no blocking (PreToolUse) hook is active
- why: Hooks are the layer that actually stops a tool call; with none active the guardrails are advice.
- fix: Register a PreToolUse hook such as `protect-secrets` in `.claude/settings.json`; `/harness-update` re-installs the shipped ones.

### SAF-10 `no-guardrail-rule`

- severity: medium (weight 5) · effort: 2 · applies: all
- full marks: `.claude/rules/agent-guardrails.md` exists.
- finding: agent-guardrails.md is not installed
- why: It is the always-loaded rule that states the boundaries the hooks enforce; without it agents get the enforcement but never the reasoning.
- fix: Restore `.claude/rules/agent-guardrails.md` (`/harness-update` re-installs it).

### SAF-11 `no-review-gate`

- severity: high (weight 12) · effort: 3 · applies: code
- full marks: A code repository has a review seat (code-reviewer, reviewer ...) or a `/review*` command.
- finding: no review command and no review seat
- why: The review gate is the fourth guardrail layer and the only one that reads the diff as a whole.
- fix: Add a read-only `.claude/agents/code-reviewer.md` (`tools: Read, Grep, Glob`) and a `.claude/commands/review-changes.md` that dispatches it.

### SAF-12 `no-review-command`

- severity: low (weight 2) · effort: 2 · applies: code
- full marks: A code repository with a review seat also has a `/review*` command that routes work to it.
- finding: a review seat exists but no command invokes it
- why: A reviewer nobody routes work to is only enforced by whoever remembers to dispatch it by hand.
- fix: Add `.claude/commands/review-changes.md` that runs the review seat over the current diff.

### SAF-13 `noncode-checker`

- severity: high (weight 12) · effort: 3 · applies: non-code
- full marks: A research, strategy or docs repository has a read-only checking seat (`checker`, or any review seat without Edit or Write).
- finding: no read-only seat checks the deliverable
- why: Without a seat that only reads, every claim and every figure is approved by whoever wrote it.
- fix: Add `.claude/agents/checker.md` with `tools: Read, Grep, Glob, WebFetch, WebSearch` and `disallowedTools: Edit, Write, NotebookEdit` (the skill ships one for non-code purposes).

### SAF-14 `harness-unprotected`

- severity: medium (weight 5) · effort: 2 · applies: all
- full marks: An active hook (such as `protect-harness`) or a permissions entry guards `.claude/settings*.json` and `.claude/hooks/`.
- finding: nothing guards the hooks and settings the guardrails live in
- why: A guard an agent can rewrite is one `echo >> .claude/hooks/...` away from `exit 0`; every other layer is only as strong as the files that hold it.
- fix: Install `protect-harness` (`/harness-update` adds it) and register it on PreToolUse with matcher `Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell` in `.claude/settings.json`.

## Cost control

### COST-01 `agent-tools`

- severity: high (weight 12) · effort: 1 · applies: all
- full marks: Every agent has an explicit `tools:` list.
- finding: agent `{name}` grants no explicit tool list
- why: Omitting tools inherits every tool including every MCP server, at full schema cost on every request and with no scope limit.
- fix: Add `tools: Read, Grep, Glob` to `.claude/agents/{name}.md` and widen it only to what the seat needs.

### COST-02 `agent-model`

- severity: medium (weight 5) · effort: 1 · applies: all
- full marks: Every agent sets `model:` to something other than `inherit`.
- finding: agent `{name}` does not pin a model
- why: An unset model inherits the caller's tier, so mechanical work bills at the most expensive model in the roster.
- fix: Add `model: sonnet` to `.claude/agents/{name}.md` (`haiku` for mechanical work, `opus` for judgment).

### COST-03 `agent-effort`

- severity: low (weight 2) · effort: 1 · applies: all
- full marks: Every agent sets `effort:`.
- finding: agent `{name}` does not pin an effort level
- why: Effort is the second half of the cost decision; unset means the caller's level applies to work that may not need it.
- fix: Add `effort: medium` to `.claude/agents/{name}.md`.

### COST-04 `agent-maxturns`

- severity: low (weight 2) · effort: 1 · applies: all
- full marks: Every agent sets `maxTurns:`.
- finding: agent `{name}` does not cap its turns
- why: Without a cap a seat that loses its way keeps billing until the session ends.
- fix: Add `maxTurns: 30` to `.claude/agents/{name}.md` (the scaffolder uses 10 to 100 by seat).

### COST-05 `rule-scoping`

- severity: medium (weight 5) · effort: 2 · applies: all
- full marks: Every rule carries `paths:` except the six that load unconditionally by design.
- finding: rule `{name}` loads in every session
- why: A rule without paths frontmatter is a permanent context tax on every agent in every session, whether or not the work touches it.
- fix: Add to the top of `.claude/rules/{name}.md`: `---` / `paths:` / `  - "<glob it governs>"` / `---`.

### COST-06 `instruction-length`

- severity: low (weight 2) · effort: 3 · applies: all
- full marks: CLAUDE.md and AGENTS.md together stay under 200 lines.
- finding: CLAUDE.md and AGENTS.md together run to {extra} lines
- why: Both load in every session, and adherence drops as they grow.
- fix: Move detail into path-scoped rules under `.claude/rules/` until the two files total under 200 lines.

## Traceability

### TRC-01 `task-owner-missing`

- severity: medium (weight 5) · effort: 2 · applies: all
- full marks: Every task's owner is a seat that exists.
- finding: task `{name}` is owned by `{extra}`, which is not on the roster
- why: Work assigned to a seat that does not exist cannot be dispatched and will sit on the board unnoticed.
- fix: Set the owner at the evidence line to a seat in `.claude/agents/`, or create `.claude/agents/{extra}.md`.

### TRC-02 `dangling-script`

- severity: medium (weight 5) · effort: 2 · applies: all
- full marks: Every script a command runs exists in `.claude/scripts/`.
- finding: `{name}` runs `{extra}`, which is not installed
- why: The command names a script that is not there, so it fails the first time it is used.
- fix: Install the script (`/harness-update` re-installs shipped scripts), or remove the reference at the evidence line.

### TRC-03 `skill-not-wired`

- severity: low (weight 2) · effort: 2 · applies: all
- full marks: Every installed skill is named by a seat, a command or a rule.
- finding: skill `{name}` is installed but nothing in the harness names it
- why: An unwired skill still costs review and update attention while changing nothing about how the harness behaves.
- fix: Run `/skill-wire {name}` to declare it on the seat that uses it, or remove `.claude/skills/{name}/`.

### TRC-04 `skill-wire-missing`

- severity: medium (weight 5) · effort: 2 · applies: all
- full marks: Every skill a seat declares is installed under `.claude/skills/`.
- finding: `{name}` declares skill `{extra}`, which is not installed
- why: The seat's instructions promise a capability the repo cannot supply, so the model follows a procedure that is not there.
- fix: Install the skill under `.claude/skills/{extra}/`, or remove it from the seat at the evidence line.

## Board health

### BRD-01 `blocked-no-unblocker`

- severity: medium (weight 5) · effort: 1 · applies: all
- full marks: Every Blocked task records what would unblock it.
- finding: task `{name}` is Blocked with no dependency recorded
- why: Nothing names what would unblock it, so it cannot be picked up when the blocker clears.
- fix: Add `deps: TASK-NNN` (what unblocks it) to the frontmatter at the evidence line.

### BRD-02 `task-no-status`

- severity: low (weight 2) · effort: 1 · applies: all
- full marks: Every task carries a status.
- finding: task `{name}` has no status
- why: A task with no status is invisible to every board sweep that filters by it.
- fix: Add `status: Pending` (or the board's real state) to the frontmatter of the task file.

### BRD-03 `board-drift`

- severity: medium (weight 5) · effort: 1 · applies: all
- full marks: On an orchestrator-kit board, every task's folder, `status:` and `TASKS.md` row agree.
- finding: task `{name}`: {extra}
- why: The folder, the status and the index disagree, so whichever one a reader trusts, another says something else.
- fix: Run `bash .claude/scripts/task.sh check`, then `bash .claude/scripts/task.sh move {name} <state>` to the state that is true. Never edit TASKS.md by hand.

## Docs quality

### DOC-01 `table-blank-line`

- severity: low (weight 2) · effort: 1 · applies: all
- full marks: No Markdown table in a task or the master plan has a blank line between rows.
- finding: {name}: blank line inside a table at line {extra}
- why: A blank line terminates a table in GitHub-flavoured Markdown, so every row after it renders as plain text here and on GitHub.
- fix: Delete the blank line at the evidence line.

## Contract

### CON-01 `instruction-contract`

- severity: medium (weight 5) · effort: 3 · applies: all
- full marks: `AGENTS.md` exists at the repository root.
- finding: no AGENTS.md at the repository root
- why: AGENTS.md is the vendor-neutral contract every tool but Claude Code reads; without it the rules under .claude/ reach one client and nothing else.
- fix: Create `AGENTS.md` at the root (`/harness-update` scaffolds it) and make `CLAUDE.md` start with `@AGENTS.md`.

### CON-02 `instruction-tiers`

- severity: info (weight 0) · effort: 2 · applies: all
- full marks: An instruction file carries the Direct / Standard / Guarded tier table.
- finding: AGENTS.md states no routing tiers
- why: Without the tier table nothing says which changes go straight to the owning agent and which earn the orchestrator, so every change costs the heaviest process or none of it.
- fix: Add the tier table to AGENTS.md, as the skill's `assets/root/AGENTS.md` writes it.

### CON-03 `instruction-nested-stub`

- severity: low (weight 2) · effort: 2 · applies: all
- full marks: Every per-folder instruction file says something specific about its subtree.
- finding: {name} governs a subtree and says almost nothing
- why: A per-folder contract applies to every change under its directory; an empty one is worse than none, because the folder reads as governed.
- fix: Write what is different about this subtree into {name}, or delete it.

## What the score does not measure

- whether the rules say anything useful for this codebase
- whether the agents' scopes match how the work is really organised
- whether a hook that exists actually blocks what it claims to
- code quality, test quality, writing quality, or the depth of any review

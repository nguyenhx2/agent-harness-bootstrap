# Tool changelog - {{PROJECT_NAME}}

A dated log of every change to the dependencies, tooling, and infrastructure of this project: what
changed, why, and how it was verified.

This is the file that answers "it worked last week, what changed?" The answer is almost never in
the application code. Record the change here at the time it is made, because reconstructing it
afterwards from lockfile diffs and pipeline logs costs a day.

Updated via `/sync-context`, and directly by {{#IF_DB}}`/db-migration` and {{/IF_DB}}`/deploy`.

**Target AI tools: {{TARGET_TOOLS}}.** The agentic tools this harness is maintained for, chosen at
intake. It is recorded rather than re-detected because the signals converged and no longer separate
the tools: Cursor reads `.claude/agents/`, `.claude/skills/` and `CLAUDE.md` natively, and all three
read `AGENTS.md`, so a later scan of this tree would guess. `/harness-update` reads this line to
decide what to re-port. The `target_cursor` / `target_codex` flags in `vars.json` are what actually
drive `port.py`, so change both together - a line here that disagrees with the flags is worse than
no line, because it will be believed.

| Date | Change | Why | Verified by |
|------|--------|-----|-------------|
| <YYYY-MM-DD> | <what changed, with the before and after version> | <the reason, or the task or ADR that required it> | <the check that proved it works> |

<!-- Include: dependency upgrades, tool and runtime version changes, CI configuration changes,
     infrastructure and hosting changes, database migrations, and pinned scanner or image versions.
     A version bump with no recorded reason is a version bump nobody dares to revert. -->

# Tool changelog - {{PROJECT_NAME}}

A dated log of every change to the dependencies, tooling, and infrastructure of this project: what
changed, why, and how it was verified.

This is the file that answers "it worked last week, what changed?" The answer is almost never in
the application code. Record the change here at the time it is made, because reconstructing it
afterwards from lockfile diffs and pipeline logs costs a day.

Updated via `/sync-context`, and directly by `/db-migration` and `/deploy`.

| Date | Change | Why | Verified by |
|------|--------|-----|-------------|
| <YYYY-MM-DD> | <what changed, with the before and after version> | <the reason, or the task or ADR that required it> | <the check that proved it works> |

<!-- Include: dependency upgrades, tool and runtime version changes, CI configuration changes,
     infrastructure and hosting changes, database migrations, and pinned scanner or image versions.
     A version bump with no recorded reason is a version bump nobody dares to revert. -->

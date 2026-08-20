# Pending tasks

Tasks in the `Pending` state: deliberately parked, descoped on request, or deferred to a later
phase. Paused with a recorded reason, not abandoned and not forgotten.

`Pending` is not `Blocked`, and the difference matters:

- `Blocked` means the task CANNOT proceed. Something external is missing, and someone specific can
  unblock it. The file stays in `docs/tasks/active/` and the work restarts the moment the blocker
  clears.
- `Pending` means the task COULD proceed, but the owner decided that it should not, for now. The
  file moves here.

Every file in this folder records why it was parked and what would justify resuming it. A task
parked with no recorded reason is indistinguishable from a task that was quietly dropped.

To resume one: move the file back to `docs/tasks/active/`, set `status: Active` in the frontmatter
AND in the `docs/tasks/master-plan.md` row, and continue with `/task-resume TASK-NNN`.

The session-start scan deliberately skips this folder. Nothing here is picked up automatically; a
pending task is resumed only when a human asks for it.

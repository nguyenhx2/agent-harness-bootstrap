<!-- Unconditional by necessity: this rule governs commit MESSAGES, which are not files, so no
`paths:` glob can trigger it. That makes it a permanent context tax - which is why it stays this
short. Anything longer belongs in a path-scoped rule. -->

# Conventional commits

Format: `<type>(<scope>): <subject>`, then an optional body, then optional footers.

- **type**: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
- **scope**: one of {{COMMIT_SCOPES}}. A new scope is added to this list in the same change that
  first uses it.
- **subject**: imperative, English, lowercase first letter, no trailing period, **72 characters
  maximum**. The length limit is hook-enforced and is the rule generated commits break most.
- **breaking change**: `!` after the scope, plus a `BREAKING CHANGE:` footer explaining the break.
- **footers**: reference the requirement and task IDs, e.g. `Refs: FR-12, TASK-034`.

## Never

- No AI-attribution trailer, ever: no `Co-Authored-By` naming a model, no "Generated with" line, no
  tool signature. Strip them if tooling adds them.
- No emoji, no em dash (write "-").
- No commit directly to `{{DEFAULT_BRANCH}}` (hook-enforced). One branch per task.

Enforced by the `check-commit-msg` hook, then code review, then optional CI lint.

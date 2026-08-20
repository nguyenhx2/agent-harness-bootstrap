@AGENTS.md

## Claude-specific

The rule files are not auto-loaded. Read them when the work touches what they cover:

- `.claude/rules/repo-invariants.md` - before changing a gate, a published figure, a generated file,
  or a version.
- `.claude/rules/external-contributions.md` - before merging, closing or answering a PR or issue
  from outside.

`.claude/skills/impeccable/` is vendored, not authored here. Leave it alone unless the task is
upgrading it.

`.claude/settings.local.json` is machine-local and untracked; it does not belong in a commit.

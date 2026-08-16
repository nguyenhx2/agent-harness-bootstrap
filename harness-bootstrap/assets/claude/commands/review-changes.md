---
description: Run code review and security review on the current diff before opening a {{PR_OR_MR}}.
allowed-tools: Bash(git diff:*), Bash(git status), Bash(git log:*), Read, Grep, Glob{{#IF_PR_CLI}}, Bash({{CI_STATUS_CMD}}:*), Bash({{PR_CLI}} view:*){{/IF_PR_CLI}}
---

Review the current changes before opening or merging a {{PR_OR_MR}}.

1. Get the diff: `git diff` and `git diff --staged`. For an existing branch use
   `git diff {{DEFAULT_BRANCH}}...HEAD` (three dots, merge-base to tip). Two dots on a stale
   branch reports commits the branch is merely missing as deletions, producing false findings.
2. Run `/secret-scan`. Any real secret or sensitive data in the diff is a blocker: stop until the
   value is removed from the diff and the credential is rotated.
{{#IF_SOLO_REVIEW}}3. Dispatch `reviewer`: coding standards, `.claude/rules/`, the commit messages on the branch
   (`git log origin/{{DEFAULT_BRANCH}}..HEAD --format=%s`) against Conventional Commits, plus
   secret handling, sensitive data, guardrails, and the security non-functional requirements
   in `docs/specs/` - one pass, both lenses.
4. Dispatch `spec-guardian`: verify the acceptance criteria of the linked FR and task are met.
5. Confirm {{LINT_CMD}}{{#IF_TESTS}} and {{TEST_CMD}}{{/IF_TESTS}} pass locally, and that the {{CI_PLATFORM}} pipeline is
   green in a terminal state (`{{CI_STATUS_CMD}}`; without a CLI on this project, read it from the
   {{GIT_PLATFORM}} web UI). A pending pipeline is not a green pipeline.
6. Aggregate the findings by severity: blocker, should fix, suggestion. Record the review in the
   task file session log; a gate counts as passed only when the log records the run.
{{/IF_SOLO_REVIEW}}{{^IF_SOLO_REVIEW}}3. Dispatch `code-reviewer`: coding standards, `.claude/rules/`, and the commit messages on the
   branch (`git log origin/{{DEFAULT_BRANCH}}..HEAD --format=%s`) against Conventional Commits.
4. Dispatch `security-reviewer`: secret handling, sensitive data, guardrails, the security
   non-functional requirements in `docs/specs/`.
5. Dispatch `spec-guardian`: verify the acceptance criteria of the linked FR and task are met.
6. Confirm {{LINT_CMD}}{{#IF_TESTS}} and {{TEST_CMD}}{{/IF_TESTS}} pass locally, and that the {{CI_PLATFORM}} pipeline is
   green in a terminal state (`{{CI_STATUS_CMD}}`; without a CLI on this project, read it from the
   {{GIT_PLATFORM}} web UI). A pending pipeline is not a green pipeline.
7. Aggregate the findings by severity: blocker, should fix, suggestion. Record the review in the
   task file session log; a gate counts as passed only when the log records the run.
{{/IF_SOLO_REVIEW}}

Do not merge and do not deploy. Reviewing is not approving.

---
description: Run the review gate on the current diff before opening a {{PR_OR_MR}} - only the reviews and test layers this diff needs.
argument-hint: [TASK-NNN]
allowed-tools: Bash(git diff:*), Bash(git status), Bash(git log:*), Bash(git rev-parse:*), Bash(python:*), Bash(python3:*), Read, Grep, Glob{{#IF_PR_CLI}}, Bash({{CI_STATUS_CMD}}:*), Bash({{PR_CLI}} view:*){{/IF_PR_CLI}}
---

Review the current changes before opening or merging a {{PR_OR_MR}}. Run this once, when the work
is complete - not after each step.

1. **Plan the gate.** `python .claude/scripts/verify-plan.py --base {{DEFAULT_BRANCH}}`, adding
   `--task $1` when a task is linked. It reads the branch diff (three dots, merge-base to tip) and
   prints each gate as REQUIRED or skip, with the reason. It reads the verification ledger
   (`.claude/state/verify-ledger.jsonl`): a gate that already passed on these exact bytes is
   skipped with the ledger line to cite, and one whose files changed since is narrowed to the
   changed paths. Run what it requires and nothing else:

   | Gate | Required when the diff touches | Seat |
   |---|---|---|
   | `/secret-scan` | anything - never skipped | - |
   | spec validation | `docs/specs/`, when `.claude/scripts/spec-check.py` exists: run it with `--write` | - |
{{#IF_PURPOSE_CODE}}   | code review | code, tests, schema, dependencies, infrastructure | {{#IF_SOLO_REVIEW}}`reviewer`{{/IF_SOLO_REVIEW}}{{^IF_SOLO_REVIEW}}`code-reviewer`{{/IF_SOLO_REVIEW}} |
   | security review | auth, secrets, input parsing, data handling, AI tool calls, dependencies, infrastructure, hooks | {{#IF_SOLO_REVIEW}}`reviewer`{{/IF_SOLO_REVIEW}}{{^IF_SOLO_REVIEW}}`security-reviewer`{{/IF_SOLO_REVIEW}} |
{{#IF_TESTS}}   | scoped tests, then the full suite once | behavior: code or schema, not docs or config | - |
   | end to end | a critical flow named in `.claude/verify-map.json` | - |
{{/IF_TESTS}}   | spec check | a linked task, or a spec | `spec-guardian` |
{{/IF_PURPOSE_CODE}}{{#IF_CHECKER}}   | content check | prose whose claims changed - wording, numbers, sources, links, negations; a typo-class edit (spelling, punctuation, reflow) needs none | `checker` |
{{/IF_CHECKER}}
   {{#IF_PURPOSE_CODE}}Docs and config changes need the secret scan and nothing else{{#IF_CHECKER}}, unless their claims
   changed{{/IF_CHECKER}}. {{/IF_PURPOSE_CODE}}The plan is a floor the user can raise: an explicit request for a review
   always runs it.
2. Run `/secret-scan`. A real secret or sensitive datum in the diff is a blocker: stop until the
   value is removed and the credential rotated.
3. Dispatch only the seats whose gate is REQUIRED, in parallel, each with the diff:
{{#IF_PURPOSE_CODE}}{{#IF_SOLO_REVIEW}}   - code or security review: Dispatch `reviewer` once with the required lenses, plus the commit
     subjects (`git log origin/{{DEFAULT_BRANCH}}..HEAD --format=%s`) against Conventional Commits.
{{/IF_SOLO_REVIEW}}{{^IF_SOLO_REVIEW}}   - code review: Dispatch `code-reviewer` - coding standards, `.claude/rules/`, and the commit
     subjects (`git log origin/{{DEFAULT_BRANCH}}..HEAD --format=%s`) against Conventional Commits.
   - security review: Dispatch `security-reviewer` - secret handling, sensitive data, guardrails,
     the security non-functional requirements in `docs/specs/`.
{{/IF_SOLO_REVIEW}}   - spec check: Dispatch `spec-guardian` - the acceptance criteria of the linked FR and task.
{{/IF_PURPOSE_CODE}}{{#IF_CHECKER}}   - content check{{^IF_PURPOSE_CODE}}, or a spec check for a linked task{{/IF_PURPOSE_CODE}}: Dispatch `checker` - the changed
     claims against their sources, the reasoning, and the task's acceptance criteria.
{{/IF_CHECKER}}
   Each reviewer reports every finding it sees, graded by severity. Filtering happens in step 5,
   not in the reviewer's brief - a reviewer told to report only the serious ones under-reports.
4. {{#IF_TESTS}}If tests are required: {{LINT_CMD}} and {{TEST_CMD}} pass locally, unless the plan says a green
   run is already logged at HEAD; end to end only for the flows the plan names. {{/IF_TESTS}}The {{CI_PLATFORM}}
   pipeline, if there is one, is green in a terminal state (`{{CI_STATUS_CMD}}`, or the
   {{GIT_PLATFORM}} web UI). Pending is not green.
5. **Aggregate.** Sort the findings into blocker, should fix, suggestion. Record each gate that
   ran with `task.py gate TASK-NNN <gate> pass|fail` - one step writes the ledger line and the
   session-log row - or `verify-plan.py --record <gate> --result pass|fail` when there is no
   task. A gate counts as passed only when that row exists.

`guard-agent-spawn` enforces the same ledger at dispatch: it refuses a review seat{{#IF_TESTS}} or `qa-test`{{/IF_TESTS}}
on content that already passed, a seat dispatched twice on the same content with no result
recorded, a third review round on the same files, an identical brief with no code change
since, and a dispatch past the task's budget. A block is the answer, not an obstacle: cite the
ledger line it names, or stop and summarise for the user. Only the user can override it.

## After fixes: at most two rounds

If the gate found blockers, fix them and run it a second time over the fix only - the diff since
the first round. Only blocker and should-fix findings earn that round; a suggestion never does. If
blockers remain after the second round, stop and hand them to the user with what was tried. A
reviewer asked for everything always finds something smaller, so without this bound the loop does
not end.

Do not merge and do not deploy. Reviewing is not approving.

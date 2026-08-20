---
description: Deploy to {{HOSTING}}. Gated - explicit user request only, after the {{PR_OR_MR}} is approved and merged.
allowed-tools: Bash(git status), Bash(git log:*), Read
disable-model-invocation: true
---

Deploy {{PROJECT_NAME}} to {{HOSTING}}.

This command is GATED. It never runs automatically, never runs as a step inside another command,
and never runs to "finish" a task. It runs only when the user invokes it directly. It is excluded
from model invocation for exactly this reason: an agent must not be able to reach production on its
own initiative.

## Preconditions

Verify every one of these and REFUSE the deploy, with the reason, if any is unmet:

1. The {{PR_OR_MR}} is reviewed, approved, and merged into `{{DEFAULT_BRANCH}}`.
2. The {{CI_PLATFORM}} pipeline on `{{DEFAULT_BRANCH}}` is green and in a terminal state. Pending is
   not green, and presumed-green is not green.
3. Every environment variable the target environment needs is present there. Confirm presence only:
   never read, print, or copy a secret value.
4. Migration status is clean: nothing pending, nothing partially applied.

## Steps

1. Run the forward migrations against the target environment.
2. Deploy to {{HOSTING}} from the merged commit on `{{DEFAULT_BRANCH}}`, never from a local working
   tree.
3. Verify the health endpoint returns success. Deployed is not the same as healthy.
4. Record the deploy in `docs/context/tool-changelog.md`: what shipped, from which commit, and how
   it was verified.

On failure: roll back, report what happened, and stop. Do not retry a failed deploy and do not
"fix forward" without the user's explicit go-ahead.

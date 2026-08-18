---
description: Human-gated deploy. Never invoked by the model on its own.
disable-model-invocation: true
---

# /deploy

Human-gated deploy. Never invoked by the model on its own.

## Preconditions

Verify every one of these and REFUSE the deploy, with the reason, if any is unmet:

1. The change is reviewed, approved, and merged into `main`.
2. The pipeline on `main` is green and in a terminal state. Pending is not green,
   and presumed-green is not green.
3. Nothing in `.claude/rules/agent-guardrails.md` is being worked around to get here.

## Steps

1. Run `/review-changes` one last time against the merged commit and confirm
   `code-reviewer` signed off on it.
2. Deploy from the merged commit, never from a local working tree.
3. Verify the health endpoint returns success. Deployed is not the same as healthy.

On failure: roll back, report what happened, and stop. Do not retry a failed deploy.

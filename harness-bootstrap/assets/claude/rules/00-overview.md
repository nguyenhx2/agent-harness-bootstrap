# Overview

Rules for {{PROJECT_NAME}}. Every agent and every change complies with this directory. The
principles are in `AGENTS.md`; this file says where each one is enforced.

## How these rules load

- No `paths:` frontmatter: loaded into EVERY session. Only rules that bind behavior before any file
  is touched earn that, and they stay short.
- With `paths:`: loaded only when a matching file is touched. Anything stack- or surface-specific
  belongs there.
- Precedence on conflict: `.claude/rules/` > per-folder CLAUDE.md > default habits.
- One idea, one home. A rule that needs another's content names the file; it does not restate it.

## Rule list

Always loaded:
- agent-guardrails.md - least privilege, untrusted data, secrets, gated actions, the done check.
- model-policy.md - data classification: which model may process which class.
{{#IF_AI}}- ai-governance.md - shipping AI features: gates, evals, auditability, the incident path.
{{/IF_AI}}{{#IF_TERSE}}- output-style.md - terse output.
{{/IF_TERSE}}- task-tracking.md - where task state lives; `task.py` changes it.
- conventional-commits.md - commit message format.

Loaded only when a matching file is touched:
{{#IF_PURPOSE_CODE}}- code-quality.md - the severity model and what counts as a finding.
{{/IF_PURPOSE_CODE}}- security-privacy.md - vulnerability classes, secrets, standards anchoring.
- ip-compliance.md - dependency licences, provenance, attribution, ownership.
{{#IF_PURPOSE_CODE}}- performance.md - performance patterns and the evidence rule.
{{/IF_PURPOSE_CODE}}{{#IF_TESTS}}- testing.md - what earns a test, mocking, when to run what.
{{/IF_TESTS}}{{#IF_DB}}- data-model.md - schema and migration discipline.
{{/IF_DB}}{{#IF_UI}}- frontend.md - UI conventions.
{{/IF_UI}}- docs-workflow.md - where docs live and when they change.
- model-tiers.md - seat tier to model, the swap procedure, the deny list as the control.

Which verification a change needs - tests, reviews, end-to-end - is decided per diff by
`python .claude/scripts/verify-plan.py`, not by habit.

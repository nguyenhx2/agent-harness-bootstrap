---
description: Update docs/context (glossary, business rules, known issues, tool changelog) from recent changes.
allowed-tools: Bash(git log:*), Bash(git diff:*), Read, Edit, Write, Grep, Glob
---

Review what has landed on `{{DEFAULT_BRANCH}}` since the last sync and update the project's
long-term memory in `docs/context/`:

- `business-rules.md`: behavior changes, as numbered BR-NN rules, each with its source (an FR or an
  ADR). A rule that lives only in code is a rule the next agent will break.
- `known-issues.md`: new issues, and issues now fixed. Record the WORKAROUND, not just the symptom.
  An environment gotcha discovered once and not written down is rediscovered by every agent.
- `tool-changelog.md`: dependency, tool, and infrastructure changes. What changed, why, and how it
  was verified.
- `glossary.md`: new domain terms, entity names, status enums, role names, and their synonyms.

Rules:

- Keep entries concise. Do not restate the diff; record what a future agent needs to know and could
  not infer from the code.
- Do not delete history. A fixed issue is marked resolved, not removed.
- Never copy a secret value, a credential, or real customer data into these files.

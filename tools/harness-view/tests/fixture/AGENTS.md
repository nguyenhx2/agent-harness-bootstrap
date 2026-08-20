# AGENTS.md - fixture

The contract every AI coding tool in this fixture reads. `CLAUDE.md` imports it.

The enforceable rules live in `.claude/rules/`. Start with
`.claude/rules/agent-guardrails.md`; `.claude/rules/testing.md` is path-scoped.

## Seats

| Agent | Use it for |
|---|---|
| `orchestrator` | dispatch and the Guarded flow |
| `app-dev` | features against a settled spec |
| `code-reviewer` | the review gate |

### How much process a change gets

Decide the tier before dispatching anything. Most changes are Direct.

| Tier | The change | Who runs it | What it adds |
|------|------------|-------------|--------------|
| **Direct** | one module, reversible, touches no contract or schema | the owning agent, called straight - no orchestrator, no task file | the agent proves each criterion itself and reports how |
| **Standard** | one domain, several files, or an FR behind it | the owning agent; register a task file when the work must survive a compacted session | a hand check of every criterion |
| **Guarded** | two or more domains, OR it touches schema, auth, money, a public contract | `orchestrator` - one at a time, never two on the same board | the full flow below |

Choosing a heavier tier than the change needs is a defect, not caution.

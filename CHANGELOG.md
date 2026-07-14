# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

Every release ships installable `.zip` artifacts with a `VERSION` file inside each skill. See
[`docs/RELEASING.md`](docs/RELEASING.md).

## v1.0.1

Fixes diagrams that did not render, including in the specs this skill generates for you.

**Fixed**

- Mermaid diagrams failed with "Unable to render rich display" on GitHub. A label containing an angle-bracket placeholder, such as `<name>` or `<actor>`, is parsed as an HTML tag: the renderer drops the text, and GitHub fails the whole block. This affected `docs/FLOWS.md` and, more seriously, six `spec-builder` section templates - so every spec set generated from them shipped broken diagrams. Placeholders in mermaid labels are now uppercase words with no angle brackets.
- `spec-builder/assets/specs/09-integration-interface.md` used `--|"text"|` for an edge, which is not a valid mermaid link. It is now a bidirectional arrow.
- `docs/FLOWS.md` carried a stale rule breakdown (`four unconditional, seven path-scoped, 77% kept out of the session`). The real figures are 6, 8 and 66%.
- The CHANGELOG said 13 commands. There are 14.

**Added**

- `docs/assets/generation-and-constraint.svg` - where the agents, rules, commands and hooks come from, and how they hold each other in check. Nothing generated is invented: each artifact traces to the codebase, the specs, or a human answer.
- `scripts/check_mermaid.py` now lints for the two failures that `mermaid-cli` renders happily but GitHub rejects: an angle-bracket token in a label, and a semicolon inside a message.
- `scripts/check_numbers.py` derives the artifact counts from the assets directory and the percentages from `benchmark.py`, then fails on any document that contradicts them. It scans every document rather than a hand-maintained list, which is how the stale figures in `FLOWS.md` survived.

## v1.0.0

First release. Two Claude Code skills: one writes the spec an agent can work from, the other builds
the harness the agent runs inside.

**Skills**

- `spec-builder` - a 13-section BA specification set under `docs/specs/`, built from an idea, a transcript, meeting notes, or legacy docs. Stable IDs and anchors, mandatory security NFRs, five-way traceability. It never invents a requirement: anything unstated becomes a flagged open issue. Standards basis in `ba-standards.md` (ISO/IEC/IEEE 29148, BABOK v3, ISO 25010:2023, MoSCoW, Cockburn, OWASP LLM Top 10).
- `harness-bootstrap` - generates `.claude/` (15 agents, 14 rules, 14 commands, 6 hooks, `settings.json`), the `docs/` tree, and `AGENTS.md` + `CLAUDE.md`. Reads an existing codebase first and reconciles rather than overwrites. Has a read-only audit mode for source that agents must never modify.

**Enforcement, not advice**

- 6 hooks block bad actions before they happen: reading `.env` or a private key, committing to the default branch, editing an Accepted ADR, an AI-attribution trailer, a non-conventional commit message.
- `permissions.deny` covers secrets and any path classified as Restricted, so an agent cannot send data it cannot open.
- `python eval/guardrail_eval.py` fires 15 known-bad payloads at a real generated harness: 15/15 blocked. The guardrails are shell scripts, so the result does not change with the model.

**State on disk, not in context**

- `docs/tasks/` is a board plus one file per task, with a session log the agent writes as it works. A fresh agent with an empty context resumes from it after a compaction, a session end, or a dead IDE. Documented in `docs/CONTEXT-MANAGEMENT.md`.

**Cost as a decision**

- Every agent carries an explicit `model:`, `effort:`, a narrow `tools:` grant and `maxTurns`. An unset `model:` inherits the caller's tier, which bills mechanical work at Opus rates.
- 8 of 14 rules are path-scoped, keeping 66% of rule content out of the default session.
- Assets are real files copied by `scripts/scaffold.py` rather than prose the model retypes: 64% less to read and 85% less to author than the predecessor skill. Figures from `benchmark/benchmark.py`.

**Governance**

- `model-policy.md` - data classification decides which model may process what. The classification table is the policy; the deny list is the control.
- `ip-compliance.md` - dependency licence allow/deny, the AGPL-on-SaaS trigger, a diff check for the reviewers.
- `ai-governance.md` - which actions need a human who saw the specific action.

**Tooling**

- `scripts/package.py` builds the release artifacts and refuses on a bad semver, a missing changelog section, or an archive that would drop loose files into the skills folder.
- CI runs the guardrail eval, a scaffold matrix on Linux and Windows, a mermaid render check, and a check that every figure in the docs matches what the scripts print.

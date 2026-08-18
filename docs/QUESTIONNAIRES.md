# Questionnaires

What each skill's question set actually explores, and why - so you know what you are being asked
before you are asked it. Full source: [`intake.md`](../harness-bootstrap/reference/intake.md) for
`harness-bootstrap`, [`elicitation.md`](../spec-builder/reference/elicitation.md) and
[`SKILL.md`](../spec-builder/SKILL.md) for `spec-builder`.

## `harness-bootstrap` intake

Codebase analysis runs first and pre-fills what it can. From there every question is one of two
kinds: a **confirmation** (analysis already found an answer - correct it or accept it in one line) or
a **real question** (nothing to infer from). Real questions are either closed-choice, through
`AskUserQuestion` (max 4 options, a recommended one labeled first), or open `chat` text when the
answer is a name, a number, or a policy position with no safe default. An **express path** ("use
defaults") skips straight to defaults for everything with one, printing the assumed table once for
confirmation - except project identity, the deploy-rights half of the control-level question,
Batch G (audit mode - scope cannot be defaulted), and Batch H, which express mode never touches.

```mermaid
flowchart TD
    A["Codebase analysis pre-fills what it can"] --> B{"Did analysis answer this question"}
    B -->|"yes"| C["CONFIRM - one-line correct-or-confirm"]
    B -->|"no"| D{"Closed set of options"}
    D -->|"yes"| E["AskUserQuestion - recommended option first"]
    D -->|"no"| F["chat - free text"]
    C --> G{"Express intake"}
    E --> G
    F --> G
    G -->|"yes"| H["Skip to default, except identity / deploy rights / Batch G / Batch H"]
    G -->|"no"| I["Ask every batch A through H in full"]
    H --> J["Batch H - governance, always asked, never defaulted"]
    I --> J
    J --> K["Echo one-screen setup plan and roster, get confirmation"]
    K --> L["scripts/scaffold.py writes the harness"]
```

| Batch | Extracts | Why it matters |
|---|---|---|
| A - project identity | Name, domain, docs language, whether specs already exist, target AI tools (Q3a - multi-select, pre-filled only from Strong evidence, and the losses stated before the choice: no `maxTurns` or per-seat `tools:` allowlist in either tool, no path-scoped rules in Codex) | Sets the vocabulary for every generated file and which tool-specific output (Cursor, Codex) gets ported. The tool answer is the one Batch A answer that persists - flags `target_cursor`/`target_codex` plus a line in `tool-changelog.md` - so `/harness-update` re-ports without re-asking a question the tree can no longer answer |
| B - tech stack | Language/framework (version-checked against `tech-presets.md`, never recalled from memory), DB + ORM, integrations and their fallback/update cadence, product internationalization, authorization model and tenancy, environments and who owns each, dev OS | Drives which rules load, the `db` flag, which hook flavor - Windows or POSIX - actually fires, and the locale/tenancy facts `tech-stack.md` and `data-model.md` are authored against |
| C - git and CI | Platform, commit identity, any bot with existing merge rights, default branch, commit convention and scopes | Feeds the main-commit guard and the PR/MR terminology; a wrong identity misattributes commits, and an unflagged auto-merge bot can bypass `merge-manager`'s gate |
| D - quality and safety | Roster shape (project horizon - flag `long`; role granularity - split reviewers or merged `reviewer`, flag `solo_review`; priority), testing choice (unit+e2e / unit only / e2e only / none - flags `unit`, `e2e`, `tests`) and frameworks, methodology (DDD default, TDD, TDD+DDD, or Lightweight opt-out - flag `light`), data sensitivity and the compliance regime that binds it (GDPR/CCPA/HIPAA/PCI-DSS/SOC2/ISO 27001/APPI/Decree 13) plus retention and deletion rights, effort profile, agent-run history detail (full/summary/minimal/off), operations posture (uptime, observability, incident ladder), control level | Sets the roster size and review shape, the delivery discipline, whether `qa-test`/`/test`/`rules/testing.md` ship at all, the AI/PII/compliance guardrail strictness, how much of each agent run is archived, the ops baseline, and whether deploy rights sit in `deny` or `ask` |
| E - DB operations and seed | DB agent roster, seed policy, the real destructive DB command | Turns a reset command into an enforceable `permissions.deny` entry instead of a guess |
| F - branding and frontend | Brand assets, icon policy, accessibility target | Feeds `rules/frontend.md` and the a11y bar agents build against |
| G - audit mode | Repo scope, standards per repo, scanner strategy | Defines a read-only control plane's boundary; never eligible for express intake because scope cannot be guessed |
| H - governance | Model sovereignty per data class, residency, dependency licences, gated actions and the incident path (now covering any production incident, not only a shipped AI feature's) | Policy positions only the org can hold - always asked in full, never defaulted, never guessed |

## `spec-builder` elicitation

These are BA questions, not intake questions: they clarify business facts a spec cannot invent -
priorities, permission scope, NFR targets, volumes, security posture. Everything else is inferred from
whatever the user brought (an idea, a transcript, a PRD, a codebase) and only the decisions are asked.
Questions batch by audience - scope, people, data and systems, constraints - through the same
`AskUserQuestion`/`chat` split as above, at most 4 per call. A user in a hurry can compress the
*pacing* (draft 01-05 before opening the next batch, combine batches the source already answers,
label a shallower first pass explicitly) but never the *content* - a business fact nobody stated is
never guessed, in any pace, at any speed.

```mermaid
flowchart TD
    A["Raw input - idea, transcript, PRD, or legacy docs"] --> B["Infer structure from the source"]
    A --> C["Ask only for decisions - priorities, scope, NFR targets, security posture"]
    C --> D["Batch via AskUserQuestion or chat, max 4 per call"]
    B --> E["Draft FR list with proposed MoSCoW priorities"]
    D --> E
    E --> F["Confirmation gate - FR list, roles, open issues so far"]
    F -->|"changes requested"| C
    F -->|"approved"| G["Write sections 02 through 13, in order"]
    G --> H["Quality gate - completeness, traceability, grounding, hygiene"]
    H --> I["Final summary - every OI, AS, Partial/No, and proposed NFR target"]
```

| Question batch | Extracts | Why it matters |
|---|---|---|
| Scope | Purpose, must-have features, explicit non-goals, output language | Becomes the draft FR list section 02 onward is built from - a wrong list costs every downstream section |
| People | User groups, roles, authorization model and tenancy isolation, who decides, who signs off | Role *names* can be inferred; permission *scope* (Own/Team/All), the RBAC/ABAC model, and any break-glass path almost never can - they are asked, not guessed |
| Data and systems | Entities, retention and deletion rights, volumes, integrations and their fallback if unavailable, identity provider, product locale support, legacy-system cutover | Feeds the data dictionary (08) and the integration NFRs (09); a volume or retention guess is a design decision in disguise |
| Constraints | Security/compliance obligations (the regime named, not just "secure"), deadlines, budget, stack constraints | Section 07's security NFRs are mandatory and are never left "TBD" - an unanswered one becomes a named, owned open issue instead |

The one rule governing both skills the same way: an answer that can be inferred from what is already
there is inferred; an answer that is a decision, a priority, or a policy position is always asked, and
if nobody knows it, that gap is recorded - as an open issue with an owner, never as a plausible guess
standing in for the real answer.

# Changelog

All notable changes to the `harness-bootstrap` skill are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).
This skill is released together with `spec-builder` under one repo version - see
[`docs/RELEASING.md`](../docs/RELEASING.md).

## [1.12.1] - 2026-08-16

### Fixed

- The Cursor adapter no longer crashes on macOS and Linux. It invoked PowerShell as `powershell`,
  a name that exists only on Windows, so every tool call raised a traceback and the guard never
  ran. It now resolves the interpreter at run time and fails closed when none exists.
- `port.py --self-test` covers both halves of that behaviour: the adapter must offer every
  interpreter name its platform may use, and must deny a call it cannot evaluate.

## [1.12.0] - 2026-08-16

### Fixed

- Guardrail bypasses found by audit: a command prefix defeated the commit and push guards, and
  `protect-secrets` matched read verbs instead of the file being read. Both are closed and pinned
  by eval cases in each hook flavour.
- `env-read.py` no longer leaks values through its `run` subcommand, and its docstring now states
  the real limits of redaction.
- Agents can read the env files they legitimately need. The deny rule matched `.env.example`, which
  every block message tells the agent to read; must-allow cases now cover the legitimate paths.
- The Cursor adapter no longer allows everything on a Windows harness, and the self-test covers
  both flavours.
- The task board directories are created, so the spawn check is armed on a fresh bootstrap.

### Added

- GitHub, GitLab and Bitbucket support, with platform detection that ranks its evidence and asks
  when signals disagree.
- A wiring gate asserting every installed hook is registered and every directory a hook needs exists.
- Wider manifest detection across Python, Ruby, .NET, Java and Kotlin, plus monorepo markers.
- Marketplace catalogs as a skill-discovery source; installation stays an explicit user choice.
- Opt-in `rtk` behind a wrapper hook, and an opt-in `terse` output-style rule.
- Questionnaires are asked in the user's own language.

## [1.11.1] - 2026-08-16

### Changed

- Released alongside the `harness-view` tool. No changes to this skill.

## [1.11.0] - 2026-08-16

### Changed

- Released alongside the `harness-view` tool, which gained the harness assessment described in the
  repo changelog. No changes to this skill.

## [1.10.0] - 2026-08-16

### Changed

- Released alongside the `harness-view` tool, which received the viewer overhaul described in the
  repo changelog. No changes to this skill.

## [1.9.0] - 2026-08-15

### Changed

- Documentation only for this skill: all 22 installed commands plus the two audit-only commands now
  carry a full reference (invocation, effect, what they write, what they refuse, and the flag that
  ships them). The release tooling also now enforces that the `harness-view` tool version matches
  the repo release version.

## [1.8.2] - 2026-08-15

### Fixed

- Path-scoped rules shipped invalid `paths:` frontmatter: the glob variables already carry quotes
  and the templates added another pair, producing `- ""src/**/*.ts""`. Every release since v1.0.0
  was affected. The eval now parses the frontmatter of every scoped rule in a real scaffold.

## [1.8.1] - 2026-08-14

### Fixed

- Published figure correction: the presentation deck still showed the previous guardrail-eval
  result. No change to the skill itself.

## [1.8.0] - 2026-08-14

### Added

- `/harness-toggle` turns a rule, command, or hook off and back on after the bootstrap, without
  editing files by hand. Disabled items move to `.claude/disabled/` and hooks also lose their
  `settings.json` registration, which is stored verbatim in a committed `.claude/disabled.json`
  so re-enabling restores it byte for byte. Scaffold re-runs respect the ledger instead of
  resurrecting what you switched off.
- Two safety tiers on that command: disabling `protect-secrets`, `guard-agent-spawn`,
  `security-privacy`, `agent-guardrails`, or `review-changes` needs a confirmation phrase you type
  yourself; a second tier needs an explicit `--yes`. Agents are never toggleable.
- `.claude/state/harness-graph.json` is a canonical, machine-readable map of the built harness:
  agents, rules, commands, hooks, settings, scripts, modules, and tasks, with typed edges
  (gates, triggers, enforces, reviews, owns, spawns, runs, invokes, escalates, references).
  The schema is documented in `docs/HARNESS-GRAPH-SCHEMA.md`.
- `harness-graph.html` gained a Flow view beside the existing force-directed Graph view: a layered
  left-to-right reading of settings, hooks, rules, agents, the merge-request gate, the human, and
  the commands, with the edge type written on every link.
- The graph now refreshes itself. Editing anything under `.claude/` or `docs/` rebuilds the harness
  and docs graphs immediately; only the code graph stays deferred, because scanning a source tree
  on every write is a tax most turns never use.
- Agent-run history has four detail levels (`full`, `summary`, `minimal`, `off`) and a retention
  cap, chosen at intake and changed later through `/harness-tune`. Previously every run was archived
  in full with no ceiling.
- A merged `reviewer` agent for small projects, selected by answering that you want consolidated
  roles rather than split ones. It carries both review checklists in one read-only seat.

### Changed

- The roster is fitted rather than fixed. `brainstormer`, `tech-researcher`, and `history-tracker`
  now ship only for long-running projects, and `db-engineer` and `db-seeder` are separate choices
  instead of arriving with any database. A default install is materially smaller than before.
- Testing is a question, not an assumption. You choose unit, end-to-end, both, or none, and the
  test agent, the `/test` command, and the testing rule ship only if you asked for them. Vitest is
  suggested for JavaScript and TypeScript stacks rather than presented as the default everywhere.
- The methodology question offers a fourth option, Lightweight, for teams who want the review gate
  without DDD or TDD ceremony. Each option states its benefit and its cost.
- Intake asks about roster shape directly: project horizon, split versus consolidated roles, and
  whether you are optimizing for speed or depth.
- Brownfield codebase analysis dispatches three parallel explorers instead of ten sequential passes,
  and skill discovery confirms every reviewed candidate in one question instead of one per skill.
- The read path shrank again after the new content landed: 129,638 bytes, 45 percent below the
  predecessor skill.

### Fixed

- The scaffolder rejects unknown or contradictory flags instead of accepting them silently. A
  mistyped OS flag previously produced a harness with no hook files but nine registrations pointing
  at them, leaving every guardrail dead with a zero exit code.
- `/harness-toggle` refuses path separators in an item name. Before that, a crafted name moved files
  from outside `.claude/` and lost them.
- A corrupt `.claude/disabled.json` now aborts loudly. It used to be read as empty, which destroyed
  the quarantine records and resurrected disabled controls on the next scaffold.
- The safety tiers are matched case-insensitively, so a differently-cased name can no longer walk
  past the confirmation on Windows.
- `.claude/hooks/README.md` is installed. It was referenced by the generated `CLAUDE.md` and by the
  quality gate but never actually copied.
- `.claude/state/history-level` is no longer gitignored, so a team that chose a quieter archive
  level keeps it instead of silently reverting to full archiving on every fresh clone.
- Data embedded in the generated graph page is escaped, and the details panel is built with DOM
  nodes rather than raw HTML, so repository content cannot execute as script in the viewer.
- Numerous conditional-content fixes: the rule index, the model policy, the commands table, and the
  audit roster no longer name agents, rules, or commands that a given flag set did not install.

## [1.7.0] - 2026-08-06

### Added

- `env-read.py`: devops, db, and qa seats can inspect and diff `.env.local`/`.env.test` without any
  value ever entering the transcript (`list`, `check`, `diff`, `run`). Production-named files are
  refused, and `protect-secrets` still blocks a direct read.
- A nested `.claude/.gitignore` ships with every scaffold, so per-task worktrees and machine state
  never get committed by accident.
- Skill discovery now searches four sources - skills.sh, GitHub topic search, `anthropics/skills`,
  and SHA-pinned plugin marketplaces - each surfaced with the trust signal it actually has.
- `reference/tech-presets.md`: a library catalogue with a standing rule - never quote a version from
  memory, verify it against the registry and record the date checked.
- Intake grew from 24 to 27 questions: i18n, authz/tenancy, and ops posture, plus APPI/Decree 13
  compliance naming, a typed-word confirmation for irreversible actions, and capability escalation
  on a third failed attempt.

### Fixed

- A commit-message guardrail bypass: `git commit -m "bad subject\n\nbody"` skipped validation
  entirely because a multi-line message was not parsed correctly.
- `guard-agent-spawn` handled an unreadable payload inconsistently between its two hook flavors;
  both now refuse it, the one deliberate exception to fail-open.
- The benchmark's own scaffold run was silently exiting 1 on a missing variable.

### Changed

- Hooks extract JSON fields in a single parser call instead of up to seven - 1.3x to 1.8x faster
  per call on machines without `jq`.
- Guardrail eval grew from 30 to 33 cases (66 across both hook flavors).

## [1.6.0] - 2026-08-04

### Added

- Docs knowledge graph: `/docs-graph` maps ID traceability across specs and generated docs;
  `graph-html.py` exports it as a self-contained interactive page, built automatically at the end
  of a run.
- A shield-and-eye logo, README banner, and video watermark/end cards, with `check_numbers.py` now
  guarding the presentation, video, and prose eval badges so they cannot drift silently.
- A board validator with dependency-cycle detection, `human_gate` markers, an attempt-reason
  taxonomy, and an advisory scope guard.

### Changed

- DDD is now the sole default methodology; TDD is opt-in, alone or combined with DDD.
- Command, hook, and eval counts grew (commands 20, hooks 9, eval cases 26); the read path shrank a
  further 54% after bootstrap.

## [1.5.0] - 2026-08-04

### Added

- Skill discovery and install: bootstrap step 2.5 searches skills.sh per seat under a trust rubric
  with a mandatory content read; `/skill-wire` maps installed skills to seats with re-review and a
  changelog record.
- Code knowledge graph: `/code-graph` builds the module/import map agents consult before a
  cross-module change; a non-blocking `graph-stale` hook flags drift.
- Express intake trimmed from 28 to 24 questions via closed-choice prompts; derivable answers are
  confirmed instead of re-asked.

### Changed

- TDD and DDD are now both default methodology flags; a single methodology remains a choice.
- Now invokes `spec-builder` through the Skill tool with prefilled variables, replacing a prose
  handoff between the two skills.
- Command, hook, and eval counts grew (commands 20, hooks 8, eval cases 22); the read path after
  bootstrap fell to 97,190 bytes (-59%).

## [1.4.0] - 2026-08-04

### Added

- `guard-agent-spawn` hook: blocks off-roster agent spawns, per-dispatch model escalation, and
  write-capable dispatches that name no task.
- DDD as a first-class methodology option alongside the TDD default; the two compose.
- Four post-bootstrap commands: `/board-audit`, `/harness-tune`, `/agent-permissions`,
  `/harness-update`.
- Anti-loop discipline: an `attempts:` counter on tasks with a hard cap before a task is marked
  Blocked.

### Changed

- Guardrail eval grew from 15 to 21 cases; rule, hook, and command counts increased accordingly.
- `port.py` now documents that `guard-agent-spawn` does not port to Cursor or Codex, since neither
  has a subagent-spawn hook point.

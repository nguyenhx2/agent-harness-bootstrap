# Changelog

All notable changes to the `harness-bootstrap` skill are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).
This skill is released together with `spec-builder` under one repo version - see
[`docs/RELEASING.md`](../docs/RELEASING.md).

## [1.21.1] - 2026-10-14

No functional change. The version moves with the repo release, which changes only the intro
video, the video page and the landing page.

## [1.21.0] - 2026-10-14

Faster hooks, a smaller footprint, and a benchmark run in real Claude Code sessions rather than
modelled. Live results: `benchmark/results/live-v1.21.0.md`.

### Added

- **A live benchmark** (`benchmark/live/`): real `claude -p` sessions on one fixture, with and
  without the harness, scored by scripts. 42 sessions: 0 of 3 leaks and 0 of 3 unsafe pushes with the harness, 3 of 3 each without.
- **`harness-check` fails a harness whose `CLAUDE.md` + `AGENTS.md` reach 200 lines**, the size at
  which instructions start to be skimmed.

### Changed

- **Hooks decide "not my command" before parsing anything.** Six `.sh` hooks in parallel on `ls`:
  5,563 -> 131 ms on the measuring machine; a live Claude Code round of hook waits 8.7 -> 1.2 s. `.ps1` gains less, as PowerShell startup dominates.
- **`SKILL.md` 24,026 -> 10,177 bytes**, with detail moved to the reference loaded at the step that
  needs it; a scaffolded harness loads 31,179 -> 26,169 bytes in every session on the full code profile.

### Fixed

- **Under four parallel sessions `guard-destructive.sh` hit its 30 s timeout** and, failing closed,
  blocked every Bash call. Its full check no longer starts a process for ordinary commands.
- `scaffold.py` copied some assets byte for byte, so on Windows four files landed with CRLF;
  output is LF everywhere now. The Cursor adapter ran `protect-adr` on reads and refused every read of an Accepted ADR.

## [1.20.1] - 2026-10-14

Fixes found by running the hooks inside real Claude Code sessions (`claude -p`), not only by piping
scripted payloads into them.

### Fixed

- **Git global options walked past four guards.** `git -c k=v commit`, `git -C . commit` and
  `git --git-dir .git push --force` skipped guard-main-commit, check-commit-msg, guard-destructive and guard-large-file. A commit landed on main live.
- **The verification ledger was off in the Windows flavour.** Windows PowerShell 5.1 prefixed the
  payload with a BOM, `json.loads` failed and every dispatch was allowed. Fixed in the hook and in `verify-plan.py`; an unreadable payload now blocks.
- **Guards failed open under load.** A blocking guard that timed out let `Remove-Item -Recurse
  -Force .` run. The 18 blocking handlers now carry `onFailure: "block"` (Claude Code 2.1.295+) and a 30 s timeout.
- **protect-secrets never saw the PowerShell tool,** so `Get-Content .env` there was not checked.

### Changed

- The git-only guards register with `"if": "Bash(*git *)"`, so a plain `ls` starts 2 hook processes
  instead of 4 on a default harness. Wall time is unchanged: hooks run in parallel and the slowest one decides.

## [1.20.0] - 2026-10-14

The harness now fits the repo's purpose and enforces proportion instead of describing it. A
verification ledger refuses a review or test that already passed on the same content, the roster
sizes itself to code, research, strategy or docs work, and every shipped seat carries deliberate
frontmatter. Figures below come from `benchmark/results/v1.20.0.md`.

### Added

- **Purpose profiles** (`purpose_code`, `purpose_research`, `purpose_strategy`, `purpose_docs`,
  combinable; none means code): research, docs and strategy harnesses field 3 to 4 seats and no code tooling.
- **Verification ledger and dispatch guard.** `verify-plan.py` picks the gates a diff needs and
  records passes by content hash; `guard-agent-spawn` refuses a repeat review, a third round or an over-budget task. Simulated mission: 17 -> 11 gate runs.
- **`task.py`** (atomic moves, a three-line checkpoint, bounded logs) and **`harness-check.py`**
  (one cross-link check, run at the end of every scaffold). Resuming a 40-row task reads 8,253 -> 966 bytes.
- **`/new-skill`**, a skill template with six trigger-case types, and `skill-check.py`.
- **Hooks for more scenarios**, opt-in by flag: `hooks_strict` (secret-guard, guard-config,
  egress, large files, dependencies, evidence on stop), `long` (checkpoint before compaction, session context, retry budget, agent trace), and per purpose (sources, links).

### Changed

- **Every seat's frontmatter is chosen, not defaulted:** `disallowedTools` on reviewers, `Agent`
  only on the orchestrator, `memory`, `effort`, `omitClaudeMd`, `initialPrompt`. Spawn depth 2 and concurrency 4 are set in `settings.json`.
- **Seats:** `strategist` and `researcher` replace `brainstormer` and `tech-researcher`; one
  `checker` reviews non-code work; `merge-manager` ships only with `merge_gate`; dev seats run at medium effort.
- **Intake is two questionnaires at most,** pre-answered from the codebase analysis.
  `/harness-tune` proposes up to four ranked changes from run evidence; `/harness-update` merges new hook registrations into an existing `settings.json`.
- **The code graph is a module-boundary check.** It now reports only real edges (6 of 6 on the
  sample monorepo, against 56 before), and flags a new cross-module import on the edit that adds it; the docs graph and the specs HTML are gone.
- **Always-loaded context, full profile: 36,800 -> 31,179 bytes.** Per-module `CLAUDE.md` files
  (40 lines at most) move module guidance out of the root; "double-check" instructions are removed.

### Fixed

- **`guard-destructive` now ships by default.** The default install only had the deny rule
  `Bash(git push --force:*)`, a prefix that `git push origin main --force` slipped past.
- `/harness-update` never registered new hooks, because it skipped an existing `settings.json`.

## [1.19.3] - 2026-10-13

Less process for small work, one test run per feature, and fewer tokens in every session. Measured
by the new PROCESS section of `benchmark/benchmark.py`, run on v1.19.2 and on this release.

### Added

- **An Inline tier: the main session does the work itself.** A question, a lookup, a doc or config
  edit, a fix you can see whole in a file or two - no subagent, no orchestrator, no task file.
  `CLAUDE.md` now carries a short routing section: Inline, dispatch the owner, or the orchestrator.
- **Seat wiring is checked, not hoped.** `scaffold.py` refuses a harness where a review seat holds
  `Edit`/`Write`, a seat's `model:` contradicts its row in `model-tiers.md`, or a shipped file cites
  a `.md` the harness does not contain. Four eval cases prove each check fires and stays quiet on a
  clean roster.

### Changed

- **Verify per feature, not per step.** While building, run only the tests touching what changed;
  the full suite runs once, at the branch gate, and a green run logged at the current commit is
  cited rather than repeated. Guarded flow full-suite steps: 2 -> 1.
- **`/review-changes` stops after two rounds.** The second covers only the fix, blockers and
  should-fix only; what remains goes to the user. A reviewer told to report everything always finds
  something smaller, so without a bound the loop did not end.
- **Always-loaded context: 41,296 -> 37,421 bytes** with every flag on, **41,102 -> 33,585** for a
  tests-only project. Seat tiers moved to path-scoped `model-tiers.md`; `ai-governance.md` ships
  only with the `ai` flag; the task-bar and enforcement sections lost their repetition.
- One session-log cadence - a row per completed unit - instead of three different ones.

### Fixed

- **The Direct tier could not be dispatched.** `guard-agent-spawn` refused any write-capable seat
  without a TASK-NNN, so every one-module fix paid for `/new-task`, a question and a board row. A
  dispatch now says `TIER: direct` or `TIER: standard` instead; Guarded work still needs a task.
- **`graph-stale` re-injected its reminder on every edit** past 20 files, including twenty edits of
  the same file. Each path is recorded once now, and a re-edit is silent.
- Five shipped files cited `task-control.md` or `cost-model.md`, which exist only inside the skill;
  brownfield setup seeded one task per gap against the few-and-large rule; `/implement-fr` and
  `/test` had duplicate or skipped step numbers, which agents follow literally.

## [1.19.2] - 2026-10-13

### Fixed

- **The bootstrapped graph scanner drew a harness as disconnected columns.** It found a skill only
  from one phrasing and a hook's rule only from a static table, two entries of which were wrong. It
  now reads references from every agent, rule, command, hook and skill file, the same way
  `harness-view` does, and names each edge by its two ends.
- **`harness-graph.py` and `harness-view` disagreed on every non-ASCII repository.** The script
  wrote ASCII escapes, the tool wrote UTF-8. Both now write UTF-8, and the parity fixture carries
  Japanese text so the gate can see it.

### Changed

- **Licence: PolyForm Noncommercial 1.0.0 to [AGPL-3.0-only](../LICENSE.md).** Any use is now
  free, commercial included; distributing or serving a modified version means publishing the source
  of the changes. A section 7 permission in [NOTICE](../NOTICE.md) keeps the harness scaffolded into
  your repository yours, outside the AGPL.
- Every shipped hook states the rule it enforces in its own header (`# Enforces: .claude/rules/...`),
  replacing the table the scanner used to keep.

## [1.19.1] - 2026-08-24

No change to the skill. The version moves with `harness-view`, which fixes a `serve` that could not
start on Windows and reworks the viewer's file panel, filters and dialogs.

## [1.19.0] - 2026-08-24

### Added

- **A bar for what earns a task, and a hook that holds it.** Task creation was unbounded: nothing
  said what earns a task, and executing one agreed piece of work could leave a board with a dozen
  rows nobody approved. `.claude/rules/task-tracking.md` now states it plainly - a task is work the
  USER agreed to, tasks are few and large, executing a task never creates more, and no agent opens
  one on its own, subagents included. The new `guard-task-scope` hook refuses to create a task file
  whose `requested_by:` is missing, is a bare `user`, or is an agent name (an agent cannot approve
  its own task), and one with fewer than two real acceptance criteria. Both hook flavours, six new
  eval cases, and the eval is now 112/112 per flavour.
- **`/new-task` asks and waits.** Unless your own message already asked for the task, the command
  puts it to you with `AskUserQuestion` before writing anything - the same discipline
  `/harness-toggle` uses for a protected control, where a confirmation counts only when you gave it
  yourself. The hook records the claim; the asking is the gate.

### Fixed

- The scanner a bootstrapped repo runs gained the **per-folder `CLAUDE.md`** support that shipped
  in harness-view a version ago but never reached this scanner. A project with `src/api/CLAUDE.md`
  now shows all its contracts in the graph, not just the root one.
- The published "bytes the model must write" figure stopped tracking the size of rules this skill
  SHIPS. It was estimated as `median(shipped rule size) x 3`, so improving a shipped rule inflated
  the figure and dropped the reduction headline. It is now a declared per-rule size with the basis
  stated, plus a measured `vars.json`.

## [1.18.2] - 2026-08-21

No change to the skill itself. The version moves with `harness-view`, which gained per-folder
instruction-file support, and with the landing page.

## [1.18.1] - 2026-08-21

### Fixed

- **Updating to a new skill version no longer invents conflicts.** `.gitattributes` checks this
  repo's text out native, so a skill cloned on Windows holds CRLF while the same skill in WSL, in
  CI, or unzipped from a release holds LF. Bootstrap from one and update from the other and every
  text asset differed by one byte per line: a real 1.17.0 to 1.18.0 upgrade reported 14 conflicts,
  **seven of them fake** - five `.gitkeep` files, `.claude/.gitignore` and `spawn-allowlist`,
  identical in every character. A reconciliation queue nobody can read is a reconciliation queue
  nobody works, and taking a new version is the one moment when reading it matters most. The
  scaffolder now forgives line endings and nothing else: a file you edited still conflicts, and a
  binary asset is still compared byte for byte.
- spec-builder ships **8** optional spec sections, not 9. The README was right and `docs/FLOWS.md`,
  the presentation outline and the deck in three languages were wrong. The number is now derived
  from the manifest and checked on every surface that states it, in all three languages.

## [1.18.0] - 2026-08-21

### Changed

- **Process is now proportional to the change.** Until now every change ran the same route: through
  the orchestrator, decomposed into tasks, with a reviewer pass after each agent. For a one-line
  backend fix that meant a planning pass, a task file, a test agent and two reviewers before
  anything landed - slow enough that people stop reaching for the harness on small work, which is
  most work. `AGENTS.md` now carries a tier table, read before anything is dispatched:
  - **Direct** - one module, reversible, no contract, schema, auth, payment or infrastructure
    touched. The owning agent is called straight. No orchestrator, no task file.
  - **Standard** - one domain, several files, or an FR behind it. Still the owning agent; a task
    file only when the work has to survive a compacted session.
  - **Guarded** - two or more domains, or schema, auth, money, a public contract, a migration, a
    deploy, or personal data. The orchestrator, and the full flow.

  Choosing a heavier tier than the change needs is now stated to be a defect, not caution.
- **The orchestrator hands back work it should not have taken.** Its description and its dispatch
  section both say so: a single-domain assignment off the Guarded list is named back to the seat
  that owns it. Decomposing anyway is pure overhead - every sub-task is a dispatch, a brief, a board
  row and a log entry.
- **Gates run once, on the branch, not after every agent.** `/review-changes` is that boundary. A
  reviewer dispatched after each agent re-reads the same files once per agent and reports the same
  findings each time, which is most of what made a small change feel expensive. Security review
  belongs to that boundary and to any moment you ask for it; it is no longer a per-task step, and
  `security-reviewer`, `code-reviewer` and `reviewer` each say so in their own description.
- **The orchestrator waits instead of checking.** It no longer polls a running agent for progress,
  and it no longer re-derives a finished agent's conclusion to satisfy itself that the work
  happened. When the agent reports, the check is on the result and it is one call: `git status` and
  `git diff --stat` answer "did this land, in the files it said". The full diff is read for a
  Guarded change, or when the stat disagrees with the report.
- **The other half of that trust: dev agents report evidence, not status.** Nobody re-runs their
  work to find out whether it happened, so a bare "done" is no longer a result. The seat names the
  files it changed, the criterion each change satisfies, the command whose output proves it, and -
  explicitly - whatever it could not verify.

## [1.17.0] - 2026-08-20

### Added

- **The eight harness-management commands now ship with the plugin**, not only into a bootstrapped
  repo. Until now `harness-bootstrap/` held a skill and nothing else, so `/harness-tune`,
  `/harness-toggle`, `/harness-update`, `/agent-permissions`, `/board-audit`, `/code-graph`,
  `/docs-graph` and `/skill-wire` existed *only* after a bootstrap had written them into that
  repo's `.claude/commands/`. Installing the plugin and typing `/harness-tune` found nothing,
  which read as the commands being broken rather than absent. They are now also in
  `harness-bootstrap/commands/`, available anywhere as `/harness-bootstrap:<name>`.
- The plugin copies are repo-agnostic where the scaffolded ones are substituted: they read the
  deploy command, the destructive commands, the sensitive paths and the reviewer layout out of
  `settings.json` and the roster and quote them back, rather than having intake's answers baked
  in, and each one states plainly when the current directory has no `.claude/`. The delivery
  commands stay scaffold-only on purpose - a `/deploy` that guesses is worse than no `/deploy`.

### Changed

- **`harness-toggle.py` toggles agent seats.** A parked seat moves to `.claude/disabled/agents/`
  and comes back byte-identically, exactly like a rule. Every seat is at least SOFT (`--yes`),
  because the orchestrator's routing table still lists it and a parked seat leaves a dispatch
  pointing at nothing; `orchestrator`, `code-reviewer`, `security-reviewer`, `reviewer` and
  `spec-guardian` are HARD (the typed phrase), because only the orchestrator spawns and the review
  seats *are* the code-review gate. Adding or retiring a seat is still `/harness-update`.
  Both scanners already read `.claude/disabled/agents/`, so graph parity is unaffected - verified
  byte-identical with a seat parked.

## [1.16.0] - 2026-08-20

### Fixed

- No change in this skill's assets. Released with the repo 1.16.0 landing-page rebuild.

## [1.15.1] - 2026-08-20

### Fixed

- The Codex packaging of this skill is now verified against the real client: `codex plugin add harness-bootstrap@agent-harness-bootstrap` installs it and the skill lands in the plugin cache. Three manifest defects found and fixed; see the root CHANGELOG.

## [1.15.0] - 2026-08-20

### Added

- Ships as an Agent Plugins 1.1.0 package under `plugins/harness-bootstrap/`, so it installs
  in Cursor, Codex, VS Code, Copilot and Kiro as well as Claude Code. The package is generated
  from this skill by `scripts/build_plugins.py` and CI fails when the two drift apart.

## [1.14.1] - 2026-08-20

### Fixed

- No change in this skill's assets. Released with the repo 1.14.1 media fix so the versions
  stay in step.

## [1.14.0] - 2026-08-20

### Changed

- `docs-graph.py`'s ID regex accepts one optional module segment on every prefix
  (`FR-BLG-01`); NFR takes module then category (`NFR-BLG-SEC-01`). Before this, two modules
  each defining a bare `FR-01` merged silently into one graph node, and a prefixed ID matched
  nothing at all.
- Dev agents own their module's spec folder when `docs/specs/modules/<module>/` exists:
  roster derivation, the dev-agent template's scope guidance and the Inventory Report's
  module mapping table all connect code modules to spec modules.

## [1.13.0] - 2026-08-19

### Changed

- Testing instructions cut back hard: the coverage target is gone from all four places that
  carried it, the 1:1 criterion mapping became a bound rather than a floor, and five of the eight
  copies of the mocking rule were removed. What earns a test is now a decision procedure with a
  retention rule.
- `/scaffold-feature` no longer writes a failing test on the DDD path.
- Target-tool detection is a ranked evidence pass, and the answer is persisted as `target_cursor`
  / `target_codex` plus `{{TARGET_TOOLS}}` instead of being discarded.

### Fixed

- `harness-graph.py` disagreed with `harness-view scan` four ways: a `files` count crashed it, a
  `[from, to]` edge pair was dropped, a YAML block list of tools parsed as one item, and it wrote
  CRLF on Windows. A parity gate now runs both scanners and fails on any difference.
- `rtk-rewrite.ps1` relayed through `cmd.exe`, so it could never work on Linux or macOS.
- `port.py` overwrote existing files instead of reporting ADDED / KEPT / CONFLICT.
- Corrected the claim that `guard-agent-spawn` cannot port: both Cursor and Codex expose a
  subagent-start hook. Reachable on both, equivalent on neither yet.

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

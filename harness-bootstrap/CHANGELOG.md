# Changelog

All notable changes to the `harness-bootstrap` skill are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).
This skill is released together with `spec-builder` under one repo version - see
[`docs/RELEASING.md`](../docs/RELEASING.md).

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

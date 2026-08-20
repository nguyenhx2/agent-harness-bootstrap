# Changelog

All notable changes to the `spec-builder` skill are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).
This skill is released together with `harness-bootstrap` under one repo version - see
[`docs/RELEASING.md`](../docs/RELEASING.md).

## [1.17.0] - 2026-08-20

### Fixed

- No change in this skill. Released with the repo 1.17.0 plugin-commands and viewer-editing work.

## [1.16.0] - 2026-08-20

### Fixed

- No change in this skill. Released with the repo 1.16.0 landing-page rebuild.

## [1.15.1] - 2026-08-20

### Fixed

- The Codex packaging of this skill is now verified against the real client: `codex plugin add spec-builder@agent-harness-bootstrap` installs it and the skill lands in the plugin cache. Three manifest defects found and fixed; see the root CHANGELOG.

## [1.15.0] - 2026-08-20

### Added

- Ships as an Agent Plugins 1.1.0 package under `plugins/spec-builder/`, so it installs in
  Cursor, Codex, VS Code, Copilot and Kiro as well as Claude Code. The package is generated
  from this skill by `scripts/build_plugins.py` and CI fails when the two drift apart.

## [1.14.1] - 2026-08-20

### Fixed

- No functional change in this skill. Released with the repo 1.14.1 to keep the versions in
  step.

## [1.14.0] - 2026-08-20

### Added

- **Section selection is a recorded decision.** `scaffold.py` refuses to write any section
  without `docs/specs/.sections.json` naming what was selected, what was excluded, and a
  reason per decision. The questionnaire existed since v1.8.0 as prose; a real run skipped it.
- **Source routing, distilled from the docs-to-knowledge skill.** `route_sources.py` decides
  per source how it is read (native / anydoc / markitdown / vision / read / unreadable), with
  a reason per decision; `ingest.py` executes the plan for pdf, docx, xlsx, pptx, text and
  images. A scanned PDF (under 80 chars/page) routes to vision instead of silently reading as
  almost nothing. A source nothing installed can read becomes an `OI-nn` in section 11 - the
  never-invent rule extended down to the file-reading layer.
- **The module axis.** `--module CODE:folder` (repeatable) places module-owned sections (05,
  07, 08, 09, 10) under `docs/specs/modules/<folder>/`, cross-cutting ones at the root.
  Module copies arrive pre-seeded: sample IDs carry the module code, links to root sections
  point two levels up. `/spec-ingest` and `/spec-retract` handle both shapes and refuse a new
  requirement that names no module in a module-form repo. The flat form stays valid forever.

### Changed

- `writing-rules.md` documents the module segment (2-4 uppercase, first a letter) and forbids
  bare IDs inside a module folder, because the flat traceability graph silently merges bare
  collisions across modules.

## [1.13.0] - 2026-08-19

### Fixed

- No functional change in this skill. Released with `harness-bootstrap` 1.13.0 to keep the versions
  in step.

## [1.12.1] - 2026-08-16

### Fixed

- No functional change in this skill. Released with `harness-bootstrap` 1.12.1 to keep the versions
  in step.

## [1.12.0] - 2026-08-16

### Fixed

- The scaffolder validates flags and honours the disabled ledger, so a typo no longer drops a
  section silently and a command the user disabled is no longer resurrected.

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

- Documentation only for this skill: `/spec-ingest` and `/spec-retract` gained full reference
  sections with worked examples, what they write, and what they refuse to do.

## [1.8.2] - 2026-08-15

### Fixed

- Released alongside `harness-bootstrap`. No changes to this skill.

## [1.8.1] - 2026-08-14

### Fixed

- Published figure correction: the presentation deck still showed the previous guardrail-eval
  result. No change to the skill itself.

## [1.8.0] - 2026-08-14

### Added

- A design-system section (`14-design-system.md`) with stable IDs for design tokens (`DT-nn`) and
  components (`DS-nn`), a source-of-truth link for the design file, and a mapping to the usability
  requirements. It cross-references the wireframe section in both directions when both are selected.
- A folder form for any section that outgrows one file: `05-functional-requirements/` with an index
  plus one file per requirement, anchors preserved. The threshold and the migration rule are written
  down rather than left to taste.
- A routing table for input material: an idea, a transcript, a pile of legacy documents, or an
  existing partial spec each get a named handling path with the reason it was chosen.

### Changed

- Sections are selected, not always generated. A core set (index, overview, glossary, functional
  requirements, non-functional requirements, assumptions and open issues, revision history) is
  always written; the other sections are chosen from what the input material actually contains. A
  project with no user interface no longer receives a wireframe section to repurpose.
- The questionnaire asks for the output language, which sections to build, and whether you want the
  full standards synthesis or a lighter profile, in batched questions that skip anything you already
  answered.
- Cross-section links are conditional, so a smaller selection produces no dead links and no table
  columns that cannot be filled.
- The quality gate checks the sections you selected rather than asserting a fixed file count.
- The reference documentation states each rule once. The identifier scheme, the never-invent
  rationale, and the standards table each have a single home now, with pointers from everywhere else.

### Fixed

- `/spec-ingest` described unknowns as blank cells, which the writing rules and the quality gate both
  reject; it now names the required unknown-with-open-issue form. Its section mapping for business
  rules pointed at the wrong section.
- The identifier scanner missed sub-categorized non-functional requirements (`NFR-SEC-01`) and
  assumptions (`AS-01`), so those never appeared in the traceability graph.
- The scaffolder's help text described the sibling skill rather than this one.

## [1.7.0] - 2026-08-06

No functional changes to this skill. Version bumped to stay in step with `harness-bootstrap`, which
this skill is always released alongside.

## [1.6.0] - 2026-08-04

### Added

- Living-spec commands: `/spec-ingest` folds a new source into an existing spec set (diffed,
  versioned, rippled to dependent agent files), and `/spec-retract` traces and withdraws a bad
  source or claim, converting affected sections into open issues and blocking affected tasks with a
  `human_gate`.
- Specs now feed the docs knowledge graph: `/docs-graph` (in `harness-bootstrap`) maps ID
  traceability across the 13 sections and exports it as an interactive `specs-graph.html`.

## [1.5.0] - 2026-08-04

### Changed

- Now invokes `harness-bootstrap` through the Skill tool with prefilled variables, replacing a
  prose handoff between the two skills.

## [1.4.0] - 2026-08-04

### Fixed

- Ten audit fixes: a complete ID-prefix table, a verifiable quality gate, a re-run procedure for
  existing specs, and the section-12 seeding claim corrected to manual (it was not automatic).

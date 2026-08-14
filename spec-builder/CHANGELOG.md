# Changelog

All notable changes to the `spec-builder` skill are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).
This skill is released together with `harness-bootstrap` under one repo version - see
[`docs/RELEASING.md`](../docs/RELEASING.md).

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

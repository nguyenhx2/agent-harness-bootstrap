# AGENTS.md - agent-harness-bootstrap

The contract for any AI coding tool working in **this** repository. `CLAUDE.md` imports it and adds
only the Claude-specific surface.

This repo is not an application. It publishes two skills (`harness-bootstrap`, `spec-builder`), a
Rust tool (`tools/harness-view`), and the documentation, deck and videos that describe them. So the
work here is mostly: change a thing, then find every place that described the old thing.

It also has to practise what it ships. The tier table in `harness-bootstrap/assets/root/AGENTS.md`
applies here too: a one-file fix goes straight to the work, and only genuinely cross-cutting work
(a release, a scanner change, anything touching the plugin trees) earns a plan.

## Rules

- `.claude/rules/repo-invariants.md` - the promises this repo makes. Read before changing a gate, a
  figure, a generated file, or a version.
- `.claude/rules/external-contributions.md` - how a PR or issue from outside is judged. Read before
  merging, closing or answering one.

## Two things that are always true here

**A gate is not trusted until it has been seen to fail.** Mutation-test it: break what it detects,
watch it go red, put it back. This repository has shipped checks that matched nothing more than
once, and each one looked exactly like a clean codebase.

**A number in the docs is derived, never typed.** `scripts/check_numbers.py` knows every place a
figure appears. Figures burned into pixels carry provenance instead: `video/RENDERED.json`,
`docs/assets/CAPTURED.json`.

## Seats

| Agent | Use it for |
|---|---|
| `contribution-triage` | an external PR or issue - reproduces the claim before anyone judges the fix |
| `docs-reconciler` | after a behaviour change, to find every doc that still describes the old one |

## Enforcement

Hooks in `.claude/hooks/`, registered in `.claude/settings.json`:

| Hook | Event | Does |
|---|---|---|
| `guard-stdlib-only.sh` | PreToolUse `Edit\|Write` | **blocks** a third-party import into `scripts/`, `eval/`, `benchmark/` - it would end that CI job with an `ImportError` |
| `guard-pr-merge.sh` | PreToolUse `Bash` | **blocks** `gh pr merge` when the PR's checks are missing or not green |
| `media-sync-reminder.sh` | PostToolUse `Edit\|Write` | reminds that the deck and videos bake skill content; never blocks |

`bash .claude/hooks/test-hooks.sh` proves all of them still fire, and still let good work through.
Run it after touching a hook. A guard that blocks everything gets switched off faster than one that
blocks nothing.

## Releasing

`docs/RELEASING.md`. Both skills and the tool move to one version together; `validate_release.py`
and `build_plugins.py --check` both have to be green before the tag.

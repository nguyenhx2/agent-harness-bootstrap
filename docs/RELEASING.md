# Releasing

Two skills, `harness-bootstrap` and `spec-builder`, released together under one repo version
(`vX.Y.Z`). This is CHANGELOG-driven: each skill's own `CHANGELOG.md` is the source of truth for
what shipped in it, and the GitHub release body is assembled from those files, not written by
hand.

## Procedure

1. **Bump the version.** Set `version: X.Y.Z` in the frontmatter of both `harness-bootstrap/SKILL.md`
   and `spec-builder/SKILL.md`. They always match - the two skills release together.
2. **Write the CHANGELOG entries.** Add `## [X.Y.Z] - YYYY-MM-DD` at the top of each skill's own
   `CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format, newest first).
   Only cover what actually touched that skill. If a skill has no functional change this release,
   still add an entry saying so - the version stays in sync either way.
   - Write for the person reading the GitHub release page, not the PR reviewer: what changed and
     why it matters to them, not the commit subject line. No em-dashes, plain hyphens.
   - Also add a `## vX.Y.Z` section to the repo-root `CHANGELOG.md` - a separate, pre-existing
     narrative changelog that `scripts/package.py --check` still gates on independently.
3. **Validate.**
   ```bash
   py -3.13 scripts/validate_release.py
   ```
   Fails on a missing CHANGELOG, a malformed or out-of-order entry, a skill whose newest CHANGELOG
   version does not match its own `SKILL.md`, or the two skills disagreeing on the version.
4. **Tag.**
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
5. **CI publishes.** The `release` workflow builds the artifacts and generates the release body with
   `py -3.13 scripts/release_notes.py X.Y.Z -o notes.md` (each skill's `## [X.Y.Z]` section becomes
   its own `### skill-name` block), then runs `gh release create` (or `gh release edit` +
   `gh release upload --clobber` if the release already exists, so a re-run is safe).

## What enforces this

| Rule | Enforced by |
| --- | --- |
| Every skill has a CHANGELOG entry for the release version | `scripts/validate_release.py` |
| Entries are `## [X.Y.Z] - YYYY-MM-DD`, newest-first | `scripts/validate_release.py` |
| A skill's CHANGELOG version matches its own `SKILL.md` `version:` | `scripts/validate_release.py` |
| Both skills agree on the repo version | `scripts/validate_release.py` |
| The sync check above runs on every push, not just at release time | `.github/workflows/eval.yml` (`guardrails` job) |
| The release body is assembled from the CHANGELOGs, not hand-typed | `scripts/release_notes.py`, called from `.github/workflows/release.yml` |
| The tag's `SKILL.md` version matches the tag itself | `scripts/package.py --check` (`release` job gate) |
| The repo-root `CHANGELOG.md` has a section for the release version | `scripts/package.py --check` (unchanged, separate from the per-skill files above) |
| Every archive carries a `VERSION` file matching the tag | `.github/workflows/release.yml` ("Assert VERSION is inside every archive") |
| A re-run of the release job does not fail on an existing release | `gh release edit` + `gh release upload --clobber` in `release.yml` |
| No em-dashes in any generated or written content | convention - checked by review, not tooling |

## Withdrawing a release

```bash
gh release delete vX.Y.Z --yes --cleanup-tag
```

Then record it in the affected skill's `CHANGELOG.md`, with the reason.

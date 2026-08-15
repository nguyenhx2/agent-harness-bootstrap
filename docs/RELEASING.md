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
   - Also add a `## [X.Y.Z] - YYYY-MM-DD` entry to `tools/harness-view/CHANGELOG.md`. The tool's
     binaries are attached to the same release, so the release body has to describe them; without
     the entry someone downloads a build with nothing saying what changed in it. This is gated.
   - Also add a `## vX.Y.Z` section to the repo-root `CHANGELOG.md` - a separate, pre-existing
     narrative changelog that `scripts/package.py --version X.Y.Z --check` still gates on
     independently.
3. **Validate.**
   ```bash
   py -3.13 scripts/validate_release.py X.Y.Z
   ```
   Fails on a missing CHANGELOG, a malformed, duplicate, or out-of-order entry, a skill whose
   newest CHANGELOG version does not match its own `SKILL.md`, the two skills disagreeing on the
   version, `tools/harness-view/Cargo.toml` disagreeing with the repo version, a missing
   `tools/harness-view/CHANGELOG.md` entry, or (with the version argument) a skill that has no
   entry for the version being released. Without the argument it runs the structure and sync checks only - that form runs in
   CI on every push.
4. **Tag.**
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
5. **CI publishes.** The `release` workflow builds the artifacts and generates the release body with
   `py -3.13 scripts/release_notes.py X.Y.Z -o notes.md` (each skill's and each tool's
   `## [X.Y.Z]` section becomes
   its own `### skill-name` block), then runs `gh release create` (or `gh release edit` +
   `gh release upload --clobber` if the release already exists, so a re-run is safe).

### Bumping the version

Three files carry the number and all three must agree, which `validate_release.py`
enforces: both skills' `SKILL.md` frontmatter, and `tools/harness-view/Cargo.toml`.
The Cargo version is what gets compiled into the released executables (Windows
VERSIONINFO, `--version`, the page footer), so a stale one ships a binary that
misreports itself.

## What enforces this

| Rule | Enforced by |
| --- | --- |
| Every skill has a CHANGELOG entry for the release version | `scripts/validate_release.py X.Y.Z` (release-job gate) and `scripts/release_notes.py` (exits non-zero when no skill has one) |
| Entries are `## [X.Y.Z] - YYYY-MM-DD`, newest-first | `scripts/validate_release.py` |
| A skill's CHANGELOG version matches its own `SKILL.md` `version:` | `scripts/validate_release.py` |
| Both skills agree on the repo version | `scripts/validate_release.py` |
| The sync check above runs on every push, not just at release time | `.github/workflows/eval.yml` (`guardrails` job) |
| The release body is assembled from the CHANGELOGs, not hand-typed | `scripts/release_notes.py`, called from `.github/workflows/release.yml` |
| The release body describes the attached tool binaries, not just the skills | `scripts/release_notes.py` reads `tools/harness-view/CHANGELOG.md`; `scripts/validate_release.py X.Y.Z` fails without that entry |
| The tag's `SKILL.md` version matches the tag itself | `scripts/package.py --version X.Y.Z --check` (`release` job gate) |
| The repo-root `CHANGELOG.md` has a section for the release version | `scripts/package.py --version X.Y.Z --check` (unchanged, separate from the per-skill files above) |
| Every archive carries a `VERSION` file matching the tag | `.github/workflows/release.yml` ("Assert VERSION is inside every archive") |
| A re-run of the release job does not fail on an existing release | `gh release edit` + `gh release upload --clobber` in `release.yml` |
| `tools/harness-view/Cargo.toml` matches the repo version | `scripts/validate_release.py` (and re-asserted per target in the `binaries` job) |
| The built binary reports the release version | `binaries` job runs `harness-view --version` on the natively-runnable targets |
| Standalone binaries are attached for every supported platform | `.github/workflows/release.yml` (`binaries` matrix job) |
| Re-running the binaries job replaces assets instead of failing | `gh release upload --clobber` in the `binaries` job |
| The application icon exists and carries every required size | `scripts/make_icons.py --check` (`guardrails` job) |
| No em-dashes in any generated or written content | convention - checked by review, not tooling |

## Withdrawing a release

```bash
gh release delete vX.Y.Z --yes --cleanup-tag
```

Then record it in the affected skill's `CHANGELOG.md`, with the reason.

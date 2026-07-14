# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

Every release ships installable `.zip` artifacts with a `VERSION` file inside each skill. A release
with no artifact is not a release, it is a tag. See [`docs/RELEASING.md`](docs/RELEASING.md).

## v1.2.1

Fixes an install that littered your skills folder.

**Fixed**
- The release archives placed `README.md`, `CHANGELOG.md` and `LICENSE` at the archive root. Extracting into `~/.claude/skills/` dropped those files loose in a directory that should contain skills and nothing else. Everything now sits under a skill directory, and `LICENSE` travels inside each skill.
- `scripts/package.py` now asserts both invariants (nothing at the archive root, no unexpected top-level directory) and exits non-zero if either is violated, so this cannot ship again through forgetfulness.

## v1.2.0

Installable release artifacts, the context-management model, and a WSL fail-open fix in the hooks.

**Added**
- Release packaging: `scripts/package.py` builds per-skill and bundle `.zip` artifacts, each carrying a `VERSION` file inside the skill directory, plus `SHA256SUMS`.
- `docs/RELEASING.md` - the release standard: semver, changelog section, artifacts, note format.
- `.claude/skills/release/` - the skill that performs a release end to end, so the process is executable rather than remembered.
- `docs/CONTEXT-MANAGEMENT.md` - how agent state is anchored to physical files, so work survives compaction, a paused session, a crashed agent, or a dead IDE. Includes the resume protocol and the hard-vs-soft control ranking.
- Four SVG diagrams under `docs/assets/`: memory hierarchy, crash and resume, control layers, and the harness architecture (which draws the model as a swappable layer with every reining layer beneath it).
- CI (`.github/workflows/eval.yml`): guardrail eval on every push, plus a scaffold matrix on Linux and Windows asserting no `{{VAR}}` placeholder survives into a rule file.

**Changed**
- README restructured: purpose first, numbers last.
- All em-dashes replaced with plain hyphens across the repo (360 occurrences in 14 files).
- Scaffold timing now quoted as `~0.2s` with its range, instead of a single run's decimal implying a precision that does not exist.

**Fixed**
- Hooks failed OPEN under WSL: a drive-letter path (`C:/x`) does not resolve, and WSL wants `/mnt/c` while git-bash wants `/c`. `protect-adr` and `guard-main-commit` silently stopped guarding. Fixed with a `wslpath`/`cygpath`-aware `norm_path` in both flavors.
- `protect-secrets` did not cover SSH/PGP private keys, `.npmrc`, `.pypirc`, `.netrc` or `~/.ssh/`.

**Removed**
- Releases v1.0.0, v1.1.0 and v1.1.1. They shipped no artifacts and their notes did not follow a standard.

## v1.1.0

Superseded by v1.2.0 and withdrawn. It introduced the benchmarks (`benchmark/`), the model-independence eval (`eval/`, 15/15), the governance layer (`model-policy`, `ip-compliance`, `ai-governance`), the flow diagrams, and the BA standards reference - all of which remain in v1.2.0.

## v1.0.0

Superseded by v1.2.0 and withdrawn. First rewrite of `project-bootstrap` into an asset-driven, cost-aware skill - all of which remains in v1.2.0.

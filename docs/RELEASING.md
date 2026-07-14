# Releasing

The standard every release must meet. It is short on purpose: a process nobody can remember is a
process nobody follows, which is why it is also executable as a skill (`.claude/skills/release/`).

## The rules

1. **Semver.** `MAJOR.MINOR.PATCH`, tagged `vX.Y.Z`. Breaking change to an asset, a manifest key, or
   the scaffolder contract is a MAJOR. New assets or rules are a MINOR. Fixes and docs are a PATCH.
2. **A release ships artifacts.** A tag with no installable `.zip` is not a release, it is a
   bookmark. `python scripts/package.py --version X.Y.Z` builds them.
3. **The version is inside the package.** Each skill directory in the archive carries a `VERSION`
   file. A skill installed on disk must be traceable to the release it came from - an unversioned
   skill is an unknown build, and you will not be able to answer "which one is broken".
4. **`SHA256SUMS` ships with every release.** Anyone pulling an artifact can verify it.
5. **CHANGELOG first, tag second.** `CHANGELOG.md` must contain a `## vX.Y.Z` section before the tag
   exists. `package.py` refuses to build otherwise - the preflight is the gate.
6. **The eval must be green.** CI runs the guardrail eval and the scaffold matrix. A release that
   ships a harness whose guardrails do not block is worse than no release: it looks armed and is not.

## The note format

Bullets. Short. Grouped under the Keep a Changelog headings, and only the ones that apply:

```markdown
**Added**
- One line per item. What it is, not how you feel about it.

**Changed**
- What changed and what a user has to do differently. If nothing, say nothing.

**Fixed**
- The bug, and the failure mode it caused. "Fixed a bug" tells the reader nothing.

**Removed**
- What is gone and what replaces it.

**Install**
- unzip <artifact> -d ~/.claude/skills/
```

Rules for the prose:

- **No em-dashes.** Plain hyphens.
- **No hype.** No "blazing", "revolutionary", "game-changing". The bullets carry the news.
- **No unsourced numbers.** Every figure traces to a script in the repo, and a modelled figure is
  labelled modelled. Do not round in a flattering direction.
- **Name the failure mode.** For a fix, say what went wrong, not just what was patched. A reader
  deciding whether to upgrade needs to know if they were exposed.

## The procedure

```bash
# 1. Write the CHANGELOG section for the new version.
$EDITOR CHANGELOG.md

# 2. Preflight. Refuses on a missing changelog section, a bad semver, a dead manifest.
python scripts/package.py --version X.Y.Z --check

# 3. Prove the harness still works. Both must exit 0.
python eval/guardrail_eval.py
python benchmark/benchmark.py

# 4. Build the artifacts.
python scripts/package.py --version X.Y.Z

# 5. Tag and publish, attaching the artifacts.
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z - <one line>" --notes-file <notes.md> dist/*
```

## Withdrawing a release

If a release shipped without artifacts, or with a broken harness, withdraw it rather than leaving it
for someone to install:

```bash
gh release delete vX.Y.Z --yes --cleanup-tag
```

Then record it in `CHANGELOG.md` under **Removed**, with the reason. A silently deleted release is
how a user ends up running a build nobody can identify.

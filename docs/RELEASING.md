# Releasing

The standard every release must meet. It is also executable as a skill (`.claude/skills/release/`),
so the process does not have to be remembered.

## The rules

1. **Semver.** `MAJOR.MINOR.PATCH`, tagged `vX.Y.Z`. A breaking change to an asset, a manifest key,
   or the scaffolder contract is a MAJOR. New assets or rules are a MINOR. Fixes and docs are a
   PATCH.
2. **A release ships artifacts.** `python scripts/package.py --version X.Y.Z` builds them. A tag with
   no installable `.zip` is a bookmark, not a release.
3. **The version is inside the package.** Each skill directory in the archive carries a `VERSION`
   file, and each `SKILL.md` carries a matching `version:` in its frontmatter, so a skill installed
   on disk is traceable to the release it came from. The preflight fails if a `SKILL.md` version does
   not match the tag. An unversioned skill is an unknown build, and "which one is broken" becomes
   unanswerable.
4. **`SHA256SUMS` ships with every release.** Anyone pulling an artifact can verify it.
5. **CHANGELOG first, tag second.** `CHANGELOG.md` must contain a `## vX.Y.Z` section before the tag
   exists. `package.py` refuses to build otherwise; the preflight is the gate.
6. **The eval AND the diagram check must be green** (`eval/guardrail_eval.py`, `scripts/check_mermaid.py`). CI runs the guardrail eval and the scaffold matrix. Do not ship a
   harness whose guardrails do not block.
7. **Every release carries its eval and benchmark.** The release attaches `eval-results.md` and
   `benchmark-results.md`, captured from the tagged commit, so the "26/26" and the numbers are
   provable per version. CI does this automatically on a tag.

## The note format

Optimize for a reader deciding whether to upgrade in under a minute. The whole body must fit on one
screen, about 40 lines.

- **Title.** The version plus a one-line theme: `vX.Y.Z - <theme>`.
- **Opening.** At most 2 sentences. What this release is, nothing more.
- **Breaking changes.** If any exist, they get their own section, first, above Added/Changed/Fixed.
  Each entry names the break and the exact migration step.
- **Added / Changed / Fixed.** Only the headings that apply. Max 5 bullets per heading. Max 2 lines
  per bullet. A bullet states what changed and the one-clause why - no narrative, no tutorial, no
  restating what a doc already says. Link to the doc for detail instead of inlining it.
- **Counts and metrics.** Only when they changed. Show the delta, e.g. `eval 15 -> 21 cases`. Drop a
  metric that did not move.
- **Install.** Unchanged: the unzip command per artifact.

Skeleton:

```markdown
# vX.Y.Z - <one-line theme>

<1-2 sentence opening: what this release is.>

**Breaking** (only if applicable)
- <what breaks> - migrate by <step>. See [docs/X.md](docs/X.md).

**Added**
- <what changed> - <why, one clause>.

**Fixed**
- <failure mode> - <why, one clause>.

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
- **Detail lives in the docs, not the notes.** If an item needs more than 2 lines to explain, link
  to the relevant doc instead of expanding the bullet.

## The procedure

```bash
# 1. Write the CHANGELOG section, and bump version: in every SKILL.md frontmatter.
$EDITOR CHANGELOG.md harness-bootstrap/SKILL.md spec-builder/SKILL.md

# 2. Preflight. Refuses on a missing changelog section, a bad semver, a dead manifest,
#    or a SKILL.md version that does not match the tag.
python scripts/package.py --version X.Y.Z --check

# 3. Prove the harness still works. All must exit 0.
python eval/guardrail_eval.py
python benchmark/benchmark.py
python harness-bootstrap/scripts/port.py --self-test
python scripts/check_numbers.py

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

Then record it in `CHANGELOG.md` under **Removed**, with the reason. A silently deleted release
leaves users running a build nobody can identify.

---
name: release
description: Cut a release of this repo - bump the version, write the CHANGELOG section, run the eval and benchmarks, build the installable .zip artifacts with a VERSION inside, tag, and publish to GitHub with standard-format notes. Use when the user asks to "release", "cut a release", "publish a version", "tag a version", "phát hành", "ra bản mới", or after a batch of changes that should ship.
allowed-tools: Bash(python:*), Bash(python3:*), Bash(git:*), Bash(gh:*), Read, Write, Edit, Grep, Glob, AskUserQuestion
---

# Release

Performs a release to the standard in [`docs/RELEASING.md`](../../../docs/RELEASING.md). That file is
the rule; this skill is the executable form of it. Read it if anything here is ambiguous.

**A tag with no artifact is not a release.** The single most common failure is shipping a version
nobody can install and nobody can identify once installed. Every step below exists to prevent that.

## Procedure

**1. Decide the version.** Semver, from what actually changed since the last tag:

```bash
git describe --tags --abbrev=0 2>/dev/null || echo "no tags yet"
git log $(git describe --tags --abbrev=0 2>/dev/null)..HEAD --oneline
```

- Breaking change to an asset, a `manifest.json` key, or the scaffolder contract: **MAJOR**.
- New assets, rules, agents, or commands: **MINOR**.
- Fixes, docs, CI: **PATCH**.

Ask the user to confirm the number before proceeding. Do not guess a MAJOR bump on their behalf.

**Then bump the version inside each skill.** Set `version: X.Y.Z` in the frontmatter of every
`SKILL.md` (`harness-bootstrap/SKILL.md`, `spec-builder/SKILL.md`). This is what makes an installed
skill self-identifying even before the packager injects its `VERSION` file, and the preflight in
step 3 fails the release if a `SKILL.md` version does not match the tag.

**And bump the tool.** `tools/harness-view/Cargo.toml`, then `cargo update -p harness-view` to
carry the number into `Cargo.lock`. The release workflow builds with `--locked`, which refuses to
update the lockfile, so bumping the manifest alone fails all four platform builds after the tag is
already pushed - a published release with no binaries. `validate_release.py` checks both.

**2. Write the CHANGELOG entries - per skill first.** The release body is CHANGELOG-driven: CI
assembles it from the two skills' own CHANGELOGs with `scripts/release_notes.py`, not from a
hand-written summary.

- Add `## [X.Y.Z] - YYYY-MM-DD` at the top of **`harness-bootstrap/CHANGELOG.md`** and
  **`spec-builder/CHANGELOG.md`** (Keep a Changelog format, newest first). Cover only what touched
  that skill; a skill with no functional change still gets a one-line no-op entry so the versions
  stay in sync.
- Also add a `## vX.Y.Z` section to the repo-root `CHANGELOG.md` - the separate narrative
  changelog that `package.py --check` gates on.
- Then validate the whole set: `python scripts/validate_release.py X.Y.Z` must pass.

Group under **Added / Changed / Fixed / Removed** and use only the headings that apply. Write it
for someone deciding whether to upgrade: max 5 bullets per heading, max 2 lines per bullet,
breaking changes in their own section first (see [`docs/RELEASING.md`](../../../docs/RELEASING.md)).

- One line per item. What it is, not how you feel about it, plus the one-clause why.
- For a **Fixed** entry, name the **failure mode**, not just the patch. "Fixed a bug in the hooks"
  tells a reader nothing; "hooks failed OPEN under WSL, so the guardrails silently stopped guarding"
  tells them whether they were exposed.
- If an item needs more than 2 lines to explain, link to the relevant doc instead of expanding it.
- No em-dashes. No hype. No unsourced numbers - every figure must trace to a script in this repo, and
  a modelled figure says it is modelled. Include a count only when it changed (e.g. `15 -> 21 cases`).

**3. Preflight.** This is the gate, not a formality:

```bash
python scripts/package.py --version X.Y.Z --check
```

It refuses on a non-semver version, a missing `## vX.Y.Z` CHANGELOG section, a missing `SKILL.md`, a
`SKILL.md` whose `version:` does not match the tag, or a scaffolder with no manifest. If it fails, fix
the cause - do not work around it.

**4. Prove the harness still works.** All must exit 0. Do not ship a harness whose guardrails do not
block, whose diagrams do not render, or whose figures contradict the scripts.

```bash
python eval/guardrail_eval.py                       # every case green; the count is derived, never hardcoded
python benchmark/benchmark.py                       # must exit 0
python harness-bootstrap/scripts/port.py --self-test # Cursor/Codex adapter, must be 32/32
python scripts/check_numbers.py                     # figures match the scripts
python scripts/check_mermaid.py                     # every diagram renders (needs node)
```

**5. Build the artifacts.**

```bash
python scripts/package.py --version X.Y.Z
```

Produces, under `dist/`: one `.zip` per skill, one bundle `.zip`, and `SHA256SUMS`. Each archive
carries a `VERSION` file **inside the skill directory**, so an installed skill is self-identifying.
The script verifies this and prints it - read the output rather than assuming.

Then capture the eval and benchmark for this exact version, so the proof ships with the release
(`package.py` wipes `dist/`, so write these after it):

```bash
{ echo '# Guardrail eval'; echo '```'; python eval/guardrail_eval.py 2>&1; echo '```'; } > dist/eval-results.md
{ echo '# Benchmark';      echo '```'; python benchmark/benchmark.py 2>&1; echo '```'; } > dist/benchmark-results.md
```

The CI release workflow does this automatically on a tag; do it by hand only for a manual release.

**6. Tag and publish.** Generate the notes from the CHANGELOGs; never hand-write the body.

```bash
python scripts/release_notes.py X.Y.Z -o notes.md   # exits non-zero if no skill has an entry
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Pushing the tag makes CI run the same generation and publish (idempotently: it edits and
re-uploads if the release already exists). For a manual publish, append the **Install** block to
`notes.md` first, then `gh release create vX.Y.Z --title "vX.Y.Z" --notes-file notes.md dist/*`:

```
**Install**
- unzip harness-bootstrap-vX.Y.Z.zip -d ~/.claude/skills/
```

**7. Verify what you published.** Do not report success from the fact that the command exited 0:

```bash
gh release view vX.Y.Z --json assets -q '.assets[].name'
```

Confirm the artifacts are actually attached. If the list is empty, the release is a tag and must be
fixed or withdrawn.

## Withdrawing a bad release

If a release shipped without artifacts, or with a red eval, withdraw it rather than leaving it for
someone to install:

```bash
gh release delete vX.Y.Z --yes --cleanup-tag
```

Then record it in the affected skill's `CHANGELOG.md` under **Removed**, with the reason.

## Quality gate

- [ ] Version is semver and the user confirmed the bump level.
- [ ] `version:` in every `SKILL.md` frontmatter matches the tag.
- [ ] Each skill's `CHANGELOG.md` has a `## [X.Y.Z] - YYYY-MM-DD` entry (no-op note allowed), the
      root `CHANGELOG.md` has its `## vX.Y.Z` section, and `validate_release.py X.Y.Z` passes.
- [ ] `package.py --version X.Y.Z --check` passes.
- [ ] `guardrail_eval.py` is fully green (the count is derived, never hardcoded), `benchmark.py`
      exits 0, `port.py --self-test` is 32/32, `check_numbers.py` and `check_mermaid.py` pass.
- [ ] `dist/` contains the per-skill zips, the bundle, `SHA256SUMS`, and the captured
      `eval-results.md` + `benchmark-results.md` for this version.
- [ ] Each zip carries `VERSION` inside the skill directory (the packager prints this - check it).
- [ ] `gh release view` lists the attached assets. A release with no assets is not done.
- [ ] Notes were generated by `release_notes.py` from the per-skill CHANGELOGs (see
      [`docs/RELEASING.md`](../../../docs/RELEASING.md)): breaking changes (if any) first, max 5
      bullets per heading, max 2 lines per bullet, whole body ~40 lines or less.
- [ ] No em-dashes anywhere in the notes.

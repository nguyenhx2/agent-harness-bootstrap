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

**2. Write the CHANGELOG section.** Add `## vX.Y.Z` at the top of `CHANGELOG.md`, above the previous
version. Group under **Added / Changed / Fixed / Removed** and use only the headings that apply.

Write it for someone deciding whether to upgrade:

- One line per item. What it is, not how you feel about it.
- For a **Fixed** entry, name the **failure mode**, not just the patch. "Fixed a bug in the hooks"
  tells a reader nothing; "hooks failed OPEN under WSL, so the guardrails silently stopped guarding"
  tells them whether they were exposed.
- No em-dashes. No hype. No unsourced numbers - every figure must trace to a script in this repo, and
  a modelled figure says it is modelled.

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
python eval/guardrail_eval.py                       # must be 15/15
python benchmark/benchmark.py                       # must exit 0
python harness-bootstrap/scripts/port.py --self-test # Cursor/Codex adapter, must be 5/5
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

**6. Tag and publish.** Write the notes to a file first; do not inline a multi-line body.

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z - <one line>" --notes-file notes.md dist/*
```

The notes file follows the same **Added / Changed / Fixed / Removed** shape as the CHANGELOG section,
plus an **Install** block:

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

Then record it in `CHANGELOG.md` under **Removed**, with the reason.

## Quality gate

- [ ] Version is semver and the user confirmed the bump level.
- [ ] `version:` in every `SKILL.md` frontmatter matches the tag.
- [ ] `CHANGELOG.md` has a `## vX.Y.Z` section, grouped, with failure modes named on every Fixed item.
- [ ] `package.py --check` passes.
- [ ] `guardrail_eval.py` is 15/15, `benchmark.py` exits 0, `port.py --self-test` is 5/5,
      `check_numbers.py` and `check_mermaid.py` pass.
- [ ] `dist/` contains the per-skill zips, the bundle, `SHA256SUMS`, and the captured
      `eval-results.md` + `benchmark-results.md` for this version.
- [ ] Each zip carries `VERSION` inside the skill directory (the packager prints this - check it).
- [ ] `gh release view` lists the attached assets. A release with no assets is not done.
- [ ] No em-dashes anywhere in the notes.

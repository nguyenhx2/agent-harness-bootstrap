# Repository invariants

Promises this repository makes to the people who clone it. Each one is load-bearing: breaking it
does not produce a test failure somewhere, it produces a guarantee that quietly stopped being true.

## 1. Every gate runs from a bare clone

`CONTRIBUTING.md`: *"Everything here runs on stdlib Python 3.13 - no `pip install` needed to run a
gate."* No workflow in `.github/workflows/` installs anything, so this is enforced by absence: add a
third-party import to a gate and that CI job ends with an `ImportError`.

The single documented exception is `scripts/check_mermaid.py`, which shells out to
`npx @mermaid-js/mermaid-cli`. A subprocess is not an import - that is the escape hatch when a real
dependency is unavoidable.

Enforced by `.claude/hooks/guard-stdlib-only.sh`.

## 2. A gate proves it can fire before it is trusted

A check that matches nothing is indistinguishable from a codebase with no problems: it prints ok and
exits 0. This has happened here repeatedly - the 80-character gate was born dead twice, the
`check_numbers` session-tax pattern matched zero lines because `**` sat between the number and the
phrase, and `build_plugins --check` reported drift correctly only three runs in four because
`filecmp` answered from a size-and-mtime cache.

So: a new check ships with a `self_test()` that fails when the detector is disabled, and any change
to an existing one is mutation-tested - break the thing it detects, watch it go red, put it back.
"It passed" is not evidence about a gate. "It failed when I broke the code" is.

## 3. Published figures come from a script, never from a keystroke

Every count, percentage and score in the README, the deck, the videos and the site is derived and
then gated by `scripts/check_numbers.py`. Figures burned into pixels carry their provenance
separately, because no text gate can read them: `video/RENDERED.json` for the clips,
`docs/assets/CAPTURED.json` for the UI screenshots. A shipped screenshot read `v1.12.0` for two
releases while the release page said `v1.14.0`; that is what those files exist to prevent.

Change a figure and the check tells you every place it also appears. Do not update the figure by
hand in one file and call it done.

## 4. Generated files carry no timestamp

Not in `harness-graph.json`, not in `references.json`, not in `RENDERED.json`, not in
`CAPTURED.json`. These files are prompt-cache prefix content and they are committed: one volatile
byte cold-misses the cache on every future run and makes every diff noise.

## 5. Scanned repository text never reaches `innerHTML`

`tools/harness-view` renders another repository's file contents into a page. Everything from disk
goes through `createElement` + `textContent`. Links are limited to `https?://`. Grep before
believing this still holds - and grep only tells the truth if the file is text, which is why a raw
control byte in a source file is treated as a defect (`scripts/check_js.py`).

## 6. Two skills, one version

`harness-bootstrap` and `spec-builder` always carry the same version, together with
`tools/harness-view/Cargo.toml`, `Cargo.lock`, `.claude-plugin/marketplace.json`, and the generated
`plugins/` tree. `scripts/validate_release.py` checks all of it; `scripts/build_plugins.py --check`
checks the generated tree matches the skills. Run both before tagging.

## 7. No AI attribution in the history

A commit message, a tag message and a pull-request description carry **no** AI attribution. None of
these belong in this repository:

```
Co-Authored-By: Claude <...>          Claude-Session: https://claude.ai/code/...
🤖 Generated with [Claude Code](...)   Generated with Claude Code
```

`Co-Authored-By:` is the one with a visible consequence: GitHub reads it and adds that identity to
the repository's **Contributors** list, where it sits beside the people who own this work. The
history records who is answerable for a change, and that is a person. Which tool helped write it is
no more part of the record than which editor it was typed in.

The rest is the same rule in a different place: a PR description is read by contributors deciding
whether to trust this project, and a machine-generated footer is noise in it.

Enforced for commit messages by `.claude/hooks/guard-no-ai-trailer.sh`. Nothing enforces it for PR
descriptions, so that one is discipline - check before opening.

## 8. Style

English throughout. No emoji anywhere, including commit messages. A hyphen, never an em dash. This
is the repository's own rule file, not a shipped template - no `{{VAR}}` placeholders belong in it.

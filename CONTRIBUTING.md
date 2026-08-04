# Contributing

Thanks for looking at this repo. It generates a harness other people's AI agents run inside, so the
bar is "does this still hold up" rather than "does it compile" - the checks below exist to answer
that automatically, so you do not have to remember it by hand.

## Dev setup

Everything here runs on stdlib **Python 3.13** (`py -3.13` on Windows, `python3` elsewhere) - no
`pip install` needed to run a gate. `scripts/check_mermaid.py` is the one exception: it shells out to
`npx @mermaid-js/mermaid-cli`, so it needs Node on PATH. Clone the repo and you can run every gate
immediately:

```bash
git clone https://github.com/nguyenhx2/agent-harness-bootstrap.git
cd agent-harness-bootstrap
py -3.13 eval/guardrail_eval.py
```

## The four gates before any PR

All four must exit 0. Run them from the repo root, in this order:

```bash
py -3.13 scripts/check_numbers.py                    # figures in the docs match reality
py -3.13 scripts/check_mermaid.py                    # every mermaid block actually renders
py -3.13 eval/guardrail_eval.py                       # the guardrails still block what they must
py -3.13 harness-bootstrap/scripts/port.py --self-test  # the Cursor/Codex adapter still enforces
```

- **`check_numbers.py`** scans every `.md` file in the repo for figures (agent/rule/hook/command
  counts, byte reductions, the guardrail score) and compares them against numbers it derives fresh
  from `benchmark/benchmark.py` and the assets directory. A number nobody checks drifts silently -
  this is how the repo's own "no invented numbers" rule gets enforced instead of just stated.
- **`check_mermaid.py`** renders every ` ```mermaid ` block with the same engine GitHub uses. GitHub's
  "Unable to render rich display" names neither the file nor the line, so this is the only way to
  find a broken diagram before a reader does.
- **`eval/guardrail_eval.py`** scaffolds a real harness and fires known-bad payloads at it - reading
  `.env`, committing to `main`, editing an Accepted ADR, spawning an off-roster agent - and checks
  every one is blocked. It is the proof, not a claim, that the safety floor does not depend on the
  model.
- **`port.py --self-test`** proves the Cursor/Codex hook adapter blocks the same payloads the native
  Claude Code hooks do, not just that it renders the files.

## No em-dashes

Plain hyphens (`-`) only, everywhere in this repo - docs, commit messages, generated assets, release
notes. It is a small thing that is trivial to get consistently right, so it is checked by convention
rather than tooling: if you see one, fix it.

## `README.ja.md` mirrors `README.md`

Same headings, same section order, same tables, same links - Japanese prose. If you change one, change
the other in the same PR. A README that only exists in one language is a broken promise to half the
badge row.

## Editing assets

Everything under `harness-bootstrap/assets/` and `spec-builder/assets/` is a template the scaffolder
renders into a target repo, so it follows stricter conventions than ordinary prose:

- **Conditional markers are UPPERCASE**, wrapping the block they gate:
  `{{#IF_TDD}} ... {{/IF_TDD}}` for "include when the flag is on", `{{^IF_TDD}} ... {{/IF_TDD}}` for
  "include when it is off". The flag name after `IF_` matches a flag in `manifest.json`.
- **Flags themselves are lowercase** in `vars.json` and `manifest.json` - `tdd`, `ddd`, `ui`, `db`,
  `ai`, `audit`, `deploy_ask`, and exactly one of `windows` / `posix`. The marker is
  `{{#IF_TDD}}`, the flag that satisfies it is `"tdd"`.
- **Assets stay byte-stable.** No timestamps, run IDs, or anything else that changes between two
  otherwise-identical scaffolds - these land in a system prompt and a run ID there cold-misses the
  prompt cache forever.
- The scaffolder never overwrites a file that differs from what it would generate; it reports
  `CONFLICT` instead. Do not add logic to your asset that depends on this behavior changing.

## How counts cascade

Change an asset that adds or removes an agent, rule, hook, or command, and the numbers quoted in
`README.md`, `README.ja.md`, and `CHANGELOG.md` are now wrong until someone updates them. You do not
have to hunt for every mention by hand: run `py -3.13 scripts/check_numbers.py` and it lists every
file and line whose figure disagrees with the assets directory, with the value it expects. Fix the
doc (or the code, if the doc turns out to be right) until the script is clean.

The same script also guards the MEDIA: `presentation/index.html` and the `video/` sources bake the
counts and the eval badge, and they drifted on every release until they entered the scan. Two rules
follow. **One**: when skill content changes, the presentation and intro videos are part of the
change - a repo hook (`.claude/hooks/media-sync-reminder.sh`) reminds the session, and
`check_numbers.py` fails the build on baked-count drift, but wording, diagrams, and slide claims
only a read can verify. **Two**: a re-render of `video/mp4` + `video/gif` follows any change to
`video/src` - the rendered artifact carries the numbers a viewer actually sees.

## Releasing

Concise standard, one page: [`docs/RELEASING.md`](docs/RELEASING.md). Semver, the artifact build, the
note format, and the checklist before a tag goes out.

# eval

## Result

`python eval/guardrail_eval.py` -> **107/107 correct (40 must-block, 67 must-allow).**

The count moved from 46 to 68 with a round of security-refusal cases against `scaffold.py` and
`harness-toggle.py` directly (not just the hooks): flag validation, contradictory methodology
flags, HOOK_RUNNER/HOOK_EXT derivation, a case-insensitive HARD tier in `harness-toggle`, a corrupt
quarantine ledger that must abort instead of being read as empty, poisoned ledger entries that must
be ignored, `enable` failing safe when it cannot restore a saved registration, path traversal in an
item name, and both graph scripts surviving a malformed `code-graph.json`. See
[What changed](#what-changed).

Pass `--flavor ps1` to ALSO run the identical payloads through the `.ps1` hooks (Windows parity),
for **214/214** when both flavors run. It is skipped cleanly, with a note and no failure, when no
`powershell`/`pwsh` is on `PATH`.

The guardrails are hooks and `settings.json` deny rules: shell scripts, exit codes, glob matching.
None of them consults the model.

| The harness prevents | Enforced by | Depends on the model? |
|---|---|---|
| Reading `.env`, private keys, `.npmrc`, `~/.ssh/` | `protect-secrets` hook + deny rules | No |
| Reading Restricted data paths | `settings.json` `permissions.deny` | No |
| Committing straight to the default branch | `guard-main-commit` hook | No |
| A non-conventional commit message | `check-commit-msg` hook | No |
| An AI-attribution trailer in a commit | `check-commit-msg` hook | No |
| Editing an Accepted ADR | `protect-adr` hook | No |
| Spawning an off-roster agent, escalating a seat's model, or a write-capable dispatch naming no task | `guard-agent-spawn` hook | No |
| Disabling a protection (protect-secrets, guard-agent-spawn, the review gate) without the user typing the confirmation phrase | `harness-toggle.py` exit 2 | No |
| An unknown flag, both/neither OS flag, or a HOOK_RUNNER/HOOK_EXT that contradicts the OS flag in `vars.json` | `scaffold.py` `validate_flags()` exit 1 | No |
| A contradictory methodology combo (`light`+`tdd`/`ddd`, or `tdd`/`unit`/`e2e` without `tests`) | `scaffold.py` `validate_flags()` exit 1 | No |
| Disabling a HARD-tier control by typing its name in the wrong case | `harness-toggle.py` `canonical_name()` + case-folded tier check, exit 2 | No |
| Any command proceeding on a corrupt `.claude/disabled.json` | `harness-toggle.py` `read_disabled()` raise / `scaffold.py` ledger read, exit 1 | No |
| A `disabled.json` entry whose `from` points outside `.claude/{rules,commands,hooks}/` | `scaffold.py` ignored-with-warning, asset still installed | No |
| `enable` dropping a quarantine record it cannot actually restore | `harness-toggle.py` `do_enable()` refuses before touching files, exit != 0 | No |
| Path traversal (`..`) in a `disable`/`enable` item name | `harness-toggle.py` `parse_item()` exit 1 | No |
| `harness-graph.py` / `graph-html.py` crashing on a malformed `code-graph.json` | try/except around the read, exit 0 with narrowed output | No |

Swap `opus` for `haiku` in every agent and re-run: the result is byte-identical. The safety floor is
model-independent.

The suite also checks the inverse - that the harness does not block legitimate work - and that a
malformed payload does not make a hook crash. A hook that crashes fails open, which is worse than no
hook at all: it looks like protection and provides none. This eval caught exactly that bug twice
during development, once when `jq` was absent and once under WSL.

## What changed

**Security-refusal hardening (46 -> 68 per flavor).** These cases exercise `scaffold.py` and
`harness-toggle.py` directly rather than firing a hook payload, following the same per-flavor
convention as the existing `harness-toggle` cases (the scripts' behavior does not depend on which
hook flavor is installed, but each is run once per flavor call for uniform counting). Each case
scaffolds into its own disposable `--target` under `.eval-workdir/`, except the ones that need real
quarantine state, which run against the shared per-flavor repo (after `run_toggle_suite`, so they
inherit its clean, enabled baseline, and restore what they perturb before the next case runs):

- **`scaffold.py` flag validation**: an unknown flag (e.g. `posx`, `sold_review`) names itself in
  the error; both `windows` and `posix` present is rejected; neither present is rejected; a valid
  payload still exits 0.
- **Contradictory methodology flags**: `light`+`tdd`, `light`+`ddd`, `tdd` without `tests`, and
  `unit` without `tests` are all rejected; `light` alone still exits 0.
- **HOOK_RUNNER/HOOK_EXT derivation**: a `vars.json` whose `HOOK_RUNNER` contradicts the OS flag is
  a hard error; with the vars absent entirely, the scaffolded `settings.json` still registers the
  correct runner and extension for the flag (asserted against the actual rendered hook command
  string, not just the exit code).
- **Case-insensitive HARD tier**: `disable hook/Protect-Secrets` and `disable
  rule/Security-Privacy` (wrong case) still refuse with exit 2 demanding the typed phrase, and
  leave the real files and their `settings.json` registration untouched - proven by asserting file
  state, not just the exit code, since `canonical_name()` resolving the case ahead of the safety
  check is exactly the mechanism a case-insensitive filesystem could otherwise let slip past.
- **Corrupt ledger abort**: a `.claude/disabled.json` containing invalid JSON makes
  `harness-toggle.py` abort any subcommand with exit 1 and no mutation (asserted: the corrupt bytes
  are unchanged and the target hook file never moves), and makes `scaffold.py` exit 1 instead of
  silently treating the ledger as empty.
- **Poisoned ledger entries**: a `disabled.json` entry whose `kind` is `rule`/`command`/`hook` but
  whose `from` points outside `.claude/{rules,commands,hooks}/` (e.g. `.claude/settings.json` or
  `CLAUDE.md`) is ignored with a warning, and the named asset is still installed by `scaffold.py`.
- **`enable` with an unrestorable registration**: deleting `settings.json` after a HARD disable
  (so the saved registration cannot be restored) makes `enable` exit non-zero while keeping BOTH
  the `disabled.json` record and the quarantined files - nothing is lost.
- **Path traversal**: `disable "rule/../../AGENTS"` is refused with a non-zero exit. This one is
  more than a format check: reverting the guard and re-running the identical command against a
  scratch copy actually moved the repo-root `AGENTS.md` into `.claude/disabled/rules/AGENTS.md` -
  `..` in an item name resolves through `.claude/rules/../../` right back to the repo root, so the
  name-format check is the only thing standing between a toggle command and a real file outside the
  harness.
- **Graph script resilience**: a malformed `.claude/state/code-graph.json` does not crash
  `harness-graph.py` or `graph-html.py` - both still exit 0 and produce their output file, per the
  "never fails the caller" contract in their own docstrings.

Three of these were verified to actually catch a regression, not just to pass, by reverting the
guard in a throwaway copy of the source file (never the repo's own `scaffold.py` or
`harness-toggle.py`) and re-running the exact failing scenario:

- Commenting out the unknown-flag check in `scaffold.py`'s `validate_flags()` and re-running the
  `posx` payload: exit code changed from 1 to 0, and the scaffold completed as if the flag were
  valid.
- Replacing `read_disabled()`'s `raise CorruptLedger(...)` with `return []` in `harness-toggle.py`
  and re-running `disable hook/check-commit-msg --yes` against a repo with a corrupt
  `disabled.json`: exit code changed from 1 to 0, and the hook was actually quarantined - a corrupt
  ledger silently accepted a real mutation instead of aborting.
- Removing the `..`/separator rejection from `parse_item()` in `harness-toggle.py` and re-running
  `disable "rule/../../AGENTS"` against a scaffolded repo: exit code changed from 1 to 0, and the
  repo-root `AGENTS.md` was actually moved into `.claude/disabled/rules/AGENTS.md` - confirming the
  traversal is a real file-mover, not just a cosmetic validation gap.

**v1.8.0 surfaces (33 -> 46 per flavor).** Three new groups, each asserting FILE STATE after the
run, not just the exit code (the framework gained `setup_files`/`delete_files` per-case fixtures
and `file_exists`/`glob_count`/`glob_contains` assertions):

- **graph-stale tiers**: an edit under `.claude/agents/` must leave a regenerated
  `.claude/state/harness-graph.json` behind; a docs edit must replace a seeded stale marker in
  `docs-graph.json`. Both must still never block.
- **agent-history levels**: `off` writes nothing, `minimal` writes one index line and no per-run
  file, `summary` truncates at 1,500 chars with a transcript pointer, a missing config means
  `full`, and retention with cap 1 prunes to exactly one per-run file (never `index.md`).
- **harness-toggle safety**: HARD items refuse with exit 2 until the literal typed phrase is
  supplied and the file provably does not move; a disabled hook's settings.json registration is
  removed while every other hook's survives; enable restores settings.json BYTE-exactly across a
  second disable/enable cycle; SOFT items need `--yes`; the `agent` kind is refused outright.

Writing these caught a real pre-existing bug: `agent-history.sh` consumed the payload's `cwd` and
transcript path raw, without the `norm_path()` drive-letter conversion every other hook applies.
Under a Windows bash it silently archived into a literal `C:/` subdirectory and could never read
its own config or the transcript. The hook now normalizes both paths; the history cases would have
failed forever otherwise.

**Coverage: every BLOCKING hook now has both a must-block and a must-allow case.** All 5 blocking
hooks (`protect-adr`, `guard-main-commit`, `check-commit-msg`, `protect-secrets`,
`guard-agent-spawn`) were audited against both sides. Only `guard-main-commit` had a gap - no
must-allow case existed, so a hook broken to block every commit unconditionally would still have
passed 107/107. The new case points the payload's `cwd` at a sibling git checkout on a non-default
branch (`feat/allow-test`, with a real commit - `git rev-parse --abbrev-ref HEAD` fails on an unborn
branch on current git, which would silently fall back to resolving the wrong repo's branch) and
asserts the commit is allowed.

That case was verified to actually catch a broken hook, not just to pass: with `guard-main-commit.sh`'s
branch check temporarily forced to always match (`if true; then` in place of the real branch
comparison), the case failed with exit 2 against a wanted 0, as it should. The hook was restored
before this file changed.

One design detail that mattered: the case originally embedded the sibling repo's path inside the
`command` string (`cd "<dir>" && git commit ...`, or `git -C <dir> commit ...`). Both are wrong -
`git -C <dir> commit` never even reaches the branch check (the hook's own trigger regex requires
`git` directly followed by `commit`/`push`, and `-C <dir>` sits in between), and a path embedded in
`command` is never run through the hook's `norm_path()` drive-letter conversion the way the JSON
`cwd` field is, so it resolves correctly under git-bash but breaks under WSL bash (which needs
`/mnt/c/...`, not `C:/...`). Routing the sibling path through `cwd` instead sidesteps both problems
and is what the fixed case does.

**Windows parity: `--flavor ps1`.** The default run only ever exercised the `.sh` hooks; the `.ps1`
twins that ship for Windows had no automated coverage at all, only the parity-contract comments in
each hook's header. `--flavor ps1` scaffolds a second harness with the Windows hook flavor
(`HOOK_RUNNER`/`HOOK_EXT` and the `windows` flag, matching what CI's `scaffold-matrix` job already
does for the scaffolder itself) and fires the identical payloads at the `.ps1` hooks through
`powershell`/`pwsh`. It is additive, not a replacement: the default `python eval/guardrail_eval.py`
still runs the `.sh` suite alone, so neither the default local run nor the `eval` CI job (which
never passes `--flavor`) changes behavior. If no PowerShell interpreter is found, the ps1 pass is
skipped with a printed reason and does not fail the run or affect the `.sh` results or exit code.

**Output.** The human-readable report is now split into a `--- POSIX (.sh) ---` / `--- Windows
(.ps1) ---` section per flavor that actually ran, but the final line is unchanged in shape - still
`N/N passed.` - for tooling that greps it. `--json` output gained a `"flavor"` field per result
(`"sh"` or `"ps1"`) and an optional `"ps1_skipped"` reason string; `"passed"`/`"failed"` stay the
combined totals of whatever ran.

## What this eval does not cover

It measures the floor (what a cheap model is prevented from doing), not the ceiling (whether a
cheaper model still does good work).

`benchmark/model_cost.py` will tell you a feature costs ~$2.38 on the default roster and ~$0.61 on an
all-Haiku one. It cannot tell you whether the Haiku feature is worth shipping, and nothing in this
repository can.

That is the question that decides whether the thesis holds:

- If a good harness lets a cheap model produce acceptable work, then model choice really is
  commoditised, and the harness is the strategy.
- If it does not, then model quality still dominates, and the harness is a cost optimisation rather
  than a strategy.

Answering it needs real tasks, real rubrics, an API key, and your own repo. The shape of that eval:

1. **Fixture tasks** from your backlog, with known-good outcomes: a bug with a known root cause, a
   feature with settled acceptance criteria, a diff with a planted defect.
2. **Run the same task** through the generated harness at several roster profiles (default /
   sonnet-only / haiku-only), holding the harness constant and varying only the models.
3. **Score against a rubric.** For a reviewer seat the metric is recall on planted defects. For a dev
   seat it is whether the acceptance criteria pass and whether the reviewers found anything.
4. **Report the gap**, including where it is zero. The useful result is not "Opus is better", it is
   how much better, on which seats, and whether the harness narrows it.

This is not built. It is item 3 on the roadmap in
[`../docs/ASSESSMENT.md`](../docs/ASSESSMENT.md).

## Running it

```bash
python eval/guardrail_eval.py                # human-readable, .sh hooks only
python eval/guardrail_eval.py --json         # machine-readable, exit 1 on any failure
python eval/guardrail_eval.py --flavor ps1   # ALSO run the .ps1 hooks (needs powershell/pwsh)
KEEP_EVAL_WORKDIR=1 python eval/guardrail_eval.py   # leave .eval-workdir/ on disk to inspect
```

It scaffolds a complete harness into `.eval-workdir/`, fires the payloads at the real generated
hooks, and cleans up. It needs `bash` (it always exercises the POSIX hook flavor) and `git`. With
`--flavor ps1` it additionally scaffolds a second, Windows-flavored harness alongside the first and
fires the same payloads at the `.ps1` hooks; if no `powershell`/`pwsh` is found on `PATH`, that part
is skipped with a printed note and the run still passes on the `.sh` results alone.

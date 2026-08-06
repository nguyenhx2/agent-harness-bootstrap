# eval

## Result

`python eval/guardrail_eval.py` -> **33/33 correct (11 must-block, 15 must-allow).**

The count moved from 25 to 26: `guard-main-commit` previously had only a must-block case
(straight-to-main). A hook that blocked every commit unconditionally - a real regression, not a
hypothetical - would still have passed the old suite. `allow: commit on a feature branch` closes
that gap; see [What changed](#what-changed) for how it was verified to actually catch a broken hook.

Pass `--flavor ps1` to ALSO run the identical 26 payloads through the `.ps1` hooks (Windows parity),
for **66/66** when both flavors run. It is skipped cleanly, with a note and no failure, when no
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

Swap `opus` for `haiku` in every agent and re-run: the result is byte-identical. The safety floor is
model-independent.

The suite also checks the inverse - that the harness does not block legitimate work - and that a
malformed payload does not make a hook crash. A hook that crashes fails open, which is worse than no
hook at all: it looks like protection and provides none. This eval caught exactly that bug twice
during development, once when `jq` was absent and once under WSL.

## What changed

**Coverage: every BLOCKING hook now has both a must-block and a must-allow case.** All 5 blocking
hooks (`protect-adr`, `guard-main-commit`, `check-commit-msg`, `protect-secrets`,
`guard-agent-spawn`) were audited against both sides. Only `guard-main-commit` had a gap - no
must-allow case existed, so a hook broken to block every commit unconditionally would still have
passed 33/33. The new case points the payload's `cwd` at a sibling git checkout on a non-default
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
does for the scaffolder itself) and fires the identical 26 payloads at the `.ps1` hooks through
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

# eval

## Result

`python eval/guardrail_eval.py` -> **15/15 known-bad payloads blocked.**

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

Swap `opus` for `haiku` in every agent and re-run: the result is byte-identical. The safety floor is
model-independent.

The suite also checks the inverse - that the harness does not block legitimate work - and that a
malformed payload does not make a hook crash. A hook that crashes fails open, which is worse than no
hook at all: it looks like protection and provides none. This eval caught exactly that bug twice
during development, once when `jq` was absent and once under WSL.

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
python eval/guardrail_eval.py           # human-readable
python eval/guardrail_eval.py --json    # machine-readable, exit 1 on any failure
KEEP_EVAL_WORKDIR=1 python eval/guardrail_eval.py   # leave .eval-workdir/ on disk to inspect
```

It scaffolds a complete harness into `.eval-workdir/`, fires the payloads at the real generated
hooks, and cleans up. It needs `bash` (it exercises the POSIX hook flavor) and `git`.

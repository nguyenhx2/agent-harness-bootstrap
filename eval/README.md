# eval

Two questions, and only one of them is answered here.

## The floor: does the harness's safety survive a model downgrade?

**Answered. `python eval/guardrail_eval.py` -> 15/15.**

The thesis this repo is built on says models are commoditising and the durable advantage is the
harness. If that is true, then the harness's *safety* properties must hold no matter which model is
driving. A cheap model inside a good harness must be unable to do the dangerous things a frontier
model can do without one.

That is testable, so we test it. The guardrails here are hooks and `settings.json` deny rules --
shell scripts, exit codes, glob matching. They never ask the model's opinion:

| The harness prevents | Enforced by | Depends on the model? |
|---|---|---|
| Reading `.env`, private keys, `.npmrc`, `~/.ssh/` | `protect-secrets` hook + deny rules | No |
| Reading Restricted data paths | `settings.json` `permissions.deny` | No |
| Committing straight to the default branch | `guard-main-commit` hook | No |
| A non-conventional commit message | `check-commit-msg` hook | No |
| An AI-attribution trailer in a commit | `check-commit-msg` hook | No |
| Editing an Accepted ADR | `protect-adr` hook | No |

Swap `opus` for `haiku` in every agent and re-run: the result is byte-identical. **The safety floor
is model-independent.** That is not an argument, it is an exit code.

The suite also checks the inverse -- that the harness does not block legitimate work -- and that a
malformed payload does not make a hook crash. A hook that crashes **fails open**, which is worse than
no hook at all: it looks like protection and provides none. This eval caught exactly that bug twice
during development (once when `jq` was absent, once under WSL), which is the whole argument for
having it.

## The ceiling: does a cheaper model still do good work?

**Not answered. Deliberately.**

`benchmark/model_cost.py` will tell you a feature costs ~$2.38 on the default roster and ~$0.61 on an
all-Haiku one. It cannot tell you whether the Haiku feature is worth shipping. Nothing in this
repository can, and inventing a number for it would be the most dishonest thing here.

This is the question that decides whether the thesis actually holds:

- If a good harness lets a cheap model produce acceptable work, then model choice really is
  commoditised, and the harness is the strategy.
- If it does not, then model quality still dominates, and the harness is a cost optimisation wearing
  a strategy's clothes.

To answer it you need real tasks, real rubrics, an API key, and your own repo. The shape of that
eval:

1. **Fixture tasks** from your backlog, with known-good outcomes -- a bug with a known root cause, a
   feature with settled acceptance criteria, a diff with a planted defect.
2. **Run the same task** through the generated harness at several roster profiles (default /
   sonnet-only / haiku-only), holding the harness constant and varying only the models.
3. **Score against a rubric**, not against vibes. For a reviewer seat the metric is recall on planted
   defects. For a dev seat it is whether the acceptance criteria pass and whether the reviewers
   found anything.
4. **Report the gap**, including where it is zero. The interesting result is not "Opus is better" --
   it is *how much* better, on *which seats*, and whether the harness narrows it.

We have not built this. It is item 3 on the roadmap in [`../docs/ASSESSMENT.md`](../docs/ASSESSMENT.md),
and it is the one that could prove the whole premise wrong.

## Running it

```bash
python eval/guardrail_eval.py           # human-readable
python eval/guardrail_eval.py --json    # machine-readable, exit 1 on any failure
KEEP_EVAL_WORKDIR=1 python eval/guardrail_eval.py   # leave .eval-workdir/ on disk to inspect
```

It scaffolds a complete harness into `.eval-workdir/`, fires the payloads at the real generated
hooks, and cleans up. It needs `bash` (it exercises the POSIX hook flavor) and `git`.

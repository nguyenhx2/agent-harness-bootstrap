# Agent Harness Bootstrap

Two Claude Code skills and a viewer. One writes specs both you and the AI understand. One fits an
agent team to your repo. The third lets you see the whole thing and switch any part of it off.

This wiki is the **reference**. The [README](https://github.com/nguyenhx2/agent-harness-bootstrap#readme)
is the argument for why any of it exists, and the
[landing page](https://nguyenhx2.github.io/agent-harness-bootstrap/) is the short version of that.
Start there if you have not read either.

## Start here

| If you want to | Read |
|---|---|
| Install it and run it once | [[Getting Started]] |
| Understand why the build is small on purpose | [[Tailored Build]] |
| Look up a seat, a rule, a hook, a command, a flag | the reference pages below |
| See what your harness actually looks like | [[Harness View]] |
| Work out why something is not firing | [[Troubleshooting]] |
| Ask the obvious question | [[FAQ]] |

## Reference

These five pages are **generated from the repository** by `scripts/build_wiki.py`. They are not
maintained by hand, which is the only reason a wiki's counts can be trusted:

- [[Agent Reference]] - the seats, their model and effort, and when each is installed
- [[Rule Reference]] - which rules load in every session and which are path-scoped
- [[Hook Reference]] - what blocks what, and the exit code that does it
- [[Command Reference]] - every slash command the harness installs
- [[Flag Reference]] - what each answer in the questionnaire turns on

If you edit one of those pages in the wiki UI, the next build overwrites it. Change the asset
instead, and the page follows.

## The one-paragraph version

`spec-builder` turns whatever you brought - an idea, a meeting transcript, legacy documents, a bare
repo - into one contract written to international standards, with stable requirement IDs.
`harness-bootstrap` reads your code, then builds the `.claude/` harness that fits it: a roster
derived from the contract and the modules that exist, rules scoped to paths that exist, and hooks
that block rather than advise. The guardrails are shell scripts and exit codes, so swapping every
agent from Opus to Haiku leaves the safety floor byte-identical. `harness-view` reads the result and
scores it, with no model in the loop.

## Proof you can run yourself

```bash
python eval/guardrail_eval.py                        # the safety floor, per hook flavour
python benchmark/benchmark.py                        # harnessed vs a bare repo
python harness-bootstrap/scripts/port.py --self-test # the Cursor and Codex adapter
python scripts/check_numbers.py                      # every published figure vs the scripts
```

Nothing on this wiki is a number somebody remembered. If a page and a script disagree, the script is
right and the page is a bug.

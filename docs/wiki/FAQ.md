# FAQ

## Does this only work with Claude Code?

It is built for Claude Code, and it ports. `python harness-bootstrap/scripts/port.py --target . --tool all`
converts the rules to Cursor's format and registers the hooks for Cursor and Codex. Codex's hook
payload matches Claude Code's, so its hooks are registered directly; Cursor gets a small adapter that
translates the payload and the answer.

The port carries **enforcement**, not just advice. The adapter is self-tested in CI on both hook
flavours.

## Can spec-builder read my PDF, Word and Excel files?

Yes, and more importantly it knows when it CANNOT. Every source you hand over is routed to a
reader that can actually read it (`route_sources.py` decides per file and prints why). The
dangerous case is handled explicitly: a scanned PDF "extracts" successfully and returns almost
nothing, which is exactly how a model ends up inventing a spec - so anything under 80
characters a page routes to a vision pass instead. A file nothing installed can open becomes a
named open issue (`OI-nn`) telling you which file, why, and what would fix it. It never becomes
a silent gap, and never a guess.

## Does the safety depend on which model I use?

No, and that is the central claim. The guardrails are shell scripts and exit codes. Swap every agent
from Opus to Haiku and `python eval/guardrail_eval.py` returns a byte-identical result.

What a cheaper model does change is the quality of the code written and the depth of the review.
That is the ceiling, and the eval does not measure it. The floor is what is model-independent.

## Why not just write the rules in a prompt?

Because a rule written as an instruction can be skipped. Anything that depends on the model choosing
to obey is not a control, it is a preference. A hook that exits 2 is a control.

The harness uses both, deliberately, and is explicit about which is which:
[`docs/ASSESSMENT.md`](https://github.com/nguyenhx2/agent-harness-bootstrap/blob/main/docs/ASSESSMENT.md)
lists what is enforced and what is only advisory.

## Will it overwrite my existing `.claude/`?

No. The scaffolder never overwrites a file that exists. It reports `ADDED`, `KEPT` or `CONFLICT`,
and a `CONFLICT` is yours to resolve. Nothing you wrote is deleted without you approving it.

## Why so few agents? Other kits ship far more.

That is the point rather than a shortfall. See [[Tailored Build]]. A seat nobody routes work to is a
context bill and a harder-to-read routing table, not capability in reserve. A run installs 7 to 15 of
the 16 seats depending on what the contract and the codebase justify, plus one dev agent per module
that actually exists.

## Do I have to use both skills?

No. Each stands alone. The contract makes the harness better and the harness makes the contract
enforceable, but you can run either on its own.

## What is the difference between a rule and a hook?

A rule is guidance the agent reads; a hook is a script that runs before or after a tool call and can
block it. Rules shape behaviour, hooks enforce it. See [[Rule Reference]] and [[Hook Reference]].

## Why are most rules path-scoped?

Because a rule loaded in every session is a permanent context cost on every request. Path-scoped
rules enter the window only when a matching file is touched, which keeps most rule content out of
the default session. Only the genuinely universal rules load unconditionally.

## Can an agent disable a guardrail?

No. `/harness-toggle` refuses agents outright, and safety-critical controls require a phrase typed
by a human, not a yes. Every toggle is recorded in the committed `.claude/disabled.json`, so turning
something off is a reviewable change rather than a silent one.

## Is this over-engineering for a small project?

Possibly, and the questionnaire has a lightweight answer for exactly that: minimal ceremony, no
methodology rule, the review gate kept. The leanest build is seven seats. If that is still too much,
`rm -rf .claude/` and the repo is as it was.

## Does it send my code anywhere?

The skills and the tool run locally. `harness-view` has no network calls at all. Whatever your
Claude Code session sends is between you and your provider; the harness adds nothing to it, and the
`model-policy` rule exists so you can write down which data classes may reach which provider at all.

## How do I know a claim on this wiki is true?

Run the script named next to it. Every figure published anywhere in this project is checked against
the scripts by `python scripts/check_numbers.py`, which fails the build on a contradiction. The
reference pages on this wiki are generated from the assets, so they cannot drift independently
either.

# Trigger cases - [[FILL: my-skill]]

Written before the skill is wired, and re-run whenever its description changes. Each case is
run twice where it makes sense: once with the skill installed and once without, so the skill is
judged on the difference it makes, not on whether it fires. `skill-check.py` requires all six
sections and every field below; it cannot judge whether the answers are good - that is this
file's reader.

## positive-discovery

The skill should trigger.

- Request: [[FILL: a realistic request, in the user's words]]
- Repo state: [[FILL: what exists in the repo when it is asked]]
- Expected skills: [[FILL: my-skill]]
- Not expected: [[FILL: neighbouring skills that must stay quiet]]
- Success criteria: [[FILL: the skill loads, and the output passes scripts/validate.py]]

## negative-discovery

A request that sounds close but belongs elsewhere. The skill must not trigger.

- Request: [[FILL: the near miss - shares keywords, different job]]
- Repo state: [[FILL: ...]]
- Expected skills: [[FILL: the skill or command that owns it, or none]]
- Not expected: [[FILL: my-skill]]
- Success criteria: [[FILL: my-skill is not loaded]]

## edge-case

The skill should trigger and cope with unusual input.

- Request: [[FILL: empty, huge, malformed, or partial input]]
- Repo state: [[FILL: e.g. a prerequisite missing]]
- Expected skills: [[FILL: my-skill]]
- Not expected: [[FILL: ...]]
- Success criteria: [[FILL: stops at the named prerequisite, or handles the input - never improvises]]

## conflict-composition

Several skills look relevant; routing must be explicit. Co-triggering is not a defect by itself.

- Request: [[FILL: a request that touches this skill and a neighbour]]
- Repo state: [[FILL: ...]]
- Expected skills: [[FILL: which one leads, and which one composes with it]]
- Not expected: [[FILL: ...]]
- Success criteria: [[FILL: each skill does only its own part; no duplicated output]]

## execution-quality

The skill measurably improves the result.

- Request: [[FILL: a representative task]]
- Repo state: [[FILL: ...]]
- Expected skills: [[FILL: my-skill]]
- Not expected: [[FILL: ...]]
- Success criteria: [[FILL: a measurable difference - validator passes, fewer defects, fewer turns]]
- Baseline (without the skill): [[FILL: what the same request produced with the skill absent]]

## efficiency

The skill loads only what it needs.

- Request: [[FILL: a request that needs SKILL.md but not every reference]]
- Repo state: [[FILL: ...]]
- Expected skills: [[FILL: my-skill]]
- Not expected: [[FILL: ...]]
- Success criteria: [[FILL: references not needed for this request stay unread; the report is short]]

# From spec to the agentic loop

The spec is not a phase that ends before the work starts. It is the oracle the loop checks against
at every step, and the loop only works if each step reads the same contract. This file says how a
requirement travels from `docs/specs/` into an agent's hands and back, and how much of that trip a
change actually needs.

## The loop

```
FR (confirmed)  ->  task  ->  implement  ->  verify-plan  ->  review  ->  done
       ^                                                                   |
       +---------------- a criterion that turned out wrong ----------------+
```

| Step | Reads | Produces | The oracle check |
|------|-------|----------|------------------|
| **FR** | the confirmation sheet's answer | **Status**: Confirmed in 05, a revision row | `spec-check.py` is green: the FR has `AC-nn.n` criteria in Given/when/then or Done-when form, and the sheet says yes |
| **task** | `docs/specs/index.json` - one entry, not the section | a task file with `fr: FR-nn` | the task names the FR; it never copies the criteria, so they cannot drift apart |
| **implement** | the FR's block at the `file` + `anchor` the index gives | the change, plus one test or check per criterion, named by its ID | the expected value comes from the criterion, never from running the code (`rules/testing.md`) |
| **verify-plan** | the diff | which gates this diff needs | every criterion ID of the FR maps to evidence: a test name, a command and its output, or a screen |
| **review** | the diff and the criterion IDs | findings | the reviewer checks each criterion-test pair, not the code alone |
| **done** | the evidence map | the task closed with it | a criterion with no evidence is not met; say so rather than close |

**A criterion that turns out wrong goes back to the spec, not around it.** If the implementer finds
that a criterion cannot be met, or that meeting it would be wrong, that is an open issue in 11 and a
`change` on the confirmation sheet - never a quietly adjusted test. The loop's whole value is that
the oracle is not the actor's to edit.

## Agents read the index first

`docs/specs/index.json` exists so that an agent working on one FR does not load every section to find
it. It carries, per FR: title, plain-words statement, priority, status, the sheet's decision,
criterion count and IDs, open issues, linked tasks, and the file and anchor of the full block.

- Pick work from the index: `status` Confirmed, `decision` yes, `open_issues` empty, `tasks` empty.
- Open the FR's own block at `file#anchor` and nothing else, unless the block links further.
- Never edit the index or the sheet by hand. `python .claude/scripts/spec-check.py --write`
  regenerates both; the check fails when either has fallen behind the spec.

## Ceremony in proportion

The full spec cycle is for changes to the contract. Most changes are not. Match the harness's tiers:

| The change | What the spec needs | Then |
|------------|---------------------|------|
| **Inline / Direct** - a fix, a refactor, a typo, anything that leaves every criterion's outcome unchanged | nothing - no FR, no sheet, no task | do it; the existing criteria still hold, so the existing tests are the check |
| **Standard** - new or changed behaviour inside an existing FR | one appended criterion (`AC-03.4`), `spec-check.py --write`, a revision row | the owning seat implements against it; the sheet shows the new line for the next confirmation |
| **Guarded** - a new FR, a changed priority, anything a stakeholder must agree to | the FR block, its criteria, the confirmation sheet answered | the full loop above |

The test for which row applies is one question: **would a stakeholder reading the sheet see a
different promise?** No: no spec work. Yes, inside an FR they already agreed to: append the
criterion. Yes, a new promise: confirm it first. A heavier row than the change needs is as much a
defect as a lighter one - ceremony that does not change the outcome is how teams learn to skip it.

## Non-code repositories

The loop is the same for the light contract (`purpose_research`, `purpose_strategy`,
`purpose_docs`). A research question, a decision or a document is an `FR-nn` item with `Done when`
criteria; the producing seat (`researcher`, `strategist`, `writer`) is the implementer, and
`checker` is the review. The evidence for a criterion is a citation, a comparison table or a link
check rather than a test.

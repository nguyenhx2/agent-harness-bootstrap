# Harness View

A harness you cannot inspect is a harness you are trusting on faith. `harness-view` reads what is
actually on disk and renders it, scores it, and lets you switch parts of it off.

**No model is involved in any of it.** That is not a limitation, it is the design: a browser and a
CI run cannot disagree about the answer.

## Install

Prebuilt binaries for Windows, macOS and Linux are attached to
[every release](https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest), with
checksums. Or build from source:

```bash
cargo install --path tools/harness-view
```

The source is the contract; the binaries are a convenience.

## Commands

```bash
harness-view scan   .    # write .claude/state/harness-graph.json and exit
harness-view serve  .    # browse the harness at localhost
harness-view assess .    # score it, and exit non-zero on a failing gate
harness-view watch  .    # re-scan as files change
```

`assess` exiting non-zero is what makes it usable in a pipeline: the same check a reviewer runs in
the browser is the one that can fail a build.

## What the views show

**Flow** lays the control plane out in the order control actually travels: settings, then hooks,
then rules, then the agent seats, then the merge gate, then the human. It answers "how is a change
to this repository actually kept in check" in one screen.

**Graph** is the same data as a force layout, for when you want to see clusters rather than order.

Every node is a file. Click it and you get the real content, formatted or raw, including task files
with their owning agent.

## What Assess scores

The engine checks the harness against this project's own quality gate and names each finding with
the node that caused it. The categories are board health, cost control, docs quality, safety and
traceability.

Things it will tell you about:

- a rule that loads in every session but matches no file in the repository
- an agent seat with no module, or a module with no owner
- a skill that is installed but wired to nothing
- a hook that ships but is not registered in `settings.json`
- an agent with no explicit `model` or `effort`, which silently bills at the caller's tier
- a reviewer that holds `Edit` or `Write`
- a task on the board whose owner does not exist

Run against three real harnesses it scored the generated one 99, and two hand-maintained ones 79 and
64. The lower two were driven by things like eighteen rules loading in every session, and agent
seats renamed without the task board following.

## Where the data comes from

`.claude/state/harness-graph.json`, written by the run itself. The schema is versioned and shared:
the Python scanner shipped with the skill and the Rust tool produce byte-identical output on the
same repository, which is checked, because two scanners that disagree are worse than one.

That file is also why `state` sits at the foot of the overview figure rather than at its entrance.
It is not an input to the run. It is what the run leaves behind, and it is what the viewer reads.

## Turning things off

The viewer's toggle panel and the `/harness-toggle` command write the same contract: the control
moves into `.claude/disabled/`, and the change is recorded in the committed `.claude/disabled.json`
including a hook's `settings.json` registration verbatim, so enabling restores it byte-exactly. One
contract, two front ends.

Safety-critical controls require a typed confirmation phrase rather than a click. Agents cannot
toggle anything.

## See also

- [[Hook Reference]] - what each hook blocks
- [[Tailored Build]] - the findings Assess reports, and why they matter

# Getting Started

**English** · [[日本語|Getting-Started-ja]]

## Install

Download the bundle from the [latest release](https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest)
and unzip it into your skills directory:

```bash
unzip agent-harness-bootstrap.zip -d ~/.claude/skills/
```

Or skip the download entirely - the recommended path is the plugin marketplace, inside any
Claude Code session:

```text
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install harness-bootstrap@agent-harness-bootstrap
/plugin install spec-builder@agent-harness-bootstrap
```

Updates then arrive with `/plugin update`. The zip remains the offline, pinned route.

Claude Code picks the skills up on the next session. Each archive carries a `VERSION` file inside
the skill directory, so an installed skill is self-identifying: if you are ever unsure what you have,
read `~/.claude/skills/harness-bootstrap/VERSION`.

## Which skill first

That depends on what you already have, not on which one is more interesting.

| Your situation | Run |
|---|---|
| An idea, a transcript, notes, or a pile of legacy docs, and no specs | `/spec-builder` first, then `/harness-bootstrap` |
| An existing codebase, with or without specs | `/harness-bootstrap` - it reads the code first |
| A repo you must analyse but never modify | `/harness-bootstrap`, and answer that it is audit-only |

Neither skill needs the other. The contract makes the harness better, and the harness makes the
contract enforceable, but each stands alone.

## What happens when you run harness-bootstrap

**1. It reads your code first.** In a repo with any source in it, the analysis is mandatory, not
optional. It produces an Inventory Report - the stack, the modules, the conventions it observed, the
risky operations it found, and the gaps - and shows it to you before anything is written. Everything
after this is parameterised by what that report found.

**2. It asks you what code cannot decide.** The first question is what the repo is for (code,
research, strategy, docs, in any combination); everything after it is asked only where that purpose
needs it. Then documentation language, commit identity, data sensitivity, which actions must be gated,
how long-lived the project is, whether you want tests automated. The closed choices are one
pre-answered questionnaire of at most two calls, in the language you write in, and anything the
analysis already answered is not asked again. If you have no specs yet it hands over to
`spec-builder` instead of just noting the gap.

**3. It shows you the plan before writing.** What will be created, what will be kept, what will be
modified, and the roster with each seat's model and effort. You confirm, or you change it.

**4. It scaffolds.** The scaffolder **never overwrites an existing file**. It reports each file as
`ADDED`, `KEPT` (already identical) or `CONFLICT` (exists and differs). A `CONFLICT` is not an
error - it is the reconciliation queue, and you resolve each one by hand. It also writes a short
`CLAUDE.md` into each module it found, and ends by checking that every link between the seats, hooks,
rules and commands resolves.

**5. You get a summary and a next step.** Usually `/task-resume`, or `spec-builder` if there are no
specs yet.

## Your first loop

The harness is not finished until the loop has run once. Create one real task, register it on the
board, and resume it:

```bash
/new-task          # asks, then writes docs/tasks/active/TASK-001.md and registers it in master-plan.md
/task-resume       # reads the task's checkpoint and picks up from the next step
/review-changes    # the review gate, before you open a PR
```

`/new-task` opens a task only for work you agreed to, and only after you say yes. From then on task
state changes through `python .claude/scripts/task.py`, which keeps the file, its folder and the board
row in step; a hand edit of a board row is refused. If `/task-resume` finds nothing, the board is
empty - which is itself the answer. In a brownfield
repo the analysis seeds the board from the gap list, so there is real work waiting on day one.

## Verify it actually guards

Do not take the guardrails on trust. From the repository:

```bash
python eval/guardrail_eval.py
```

It scaffolds a real harness (with the strict hooks, the long-session hooks and the database guard on)
and fires known-bad and known-good payloads at it, per hook flavour. No model is consulted. The same
command is what CI runs. If you want to see the difference the harness makes, `benchmark.py`
runs the must-block payloads against a harnessed repo and against the same repo with `.claude/`
removed. To check that the harness hangs together, run `python .claude/scripts/harness-check.py` in
your repo: it names the file and line of any link that points at nothing.

## Removing it

```bash
rm -rf .claude/
```

Every piece is a file. There is no daemon, no service, and nothing outside the repository to clean
up. That is deliberate: a harness you cannot delete in one command is a harness you cannot evaluate.

## Next

- [[Tailored Build]] - why the roster is smaller than the catalogue, and how that is decided
- [[Harness View]] - see what you just built, and score it
- [[Troubleshooting]] - when a hook does not fire

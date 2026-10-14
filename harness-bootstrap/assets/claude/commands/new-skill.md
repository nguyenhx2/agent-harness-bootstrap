---
description: Decide whether a recurring workflow earns a project skill, and if it does, scaffold it from the template, write its trigger cases, lint it, and wire it to the seat that needs it. Refusing to create one is a normal outcome.
argument-hint: <skill-name> [seat]
allowed-tools: Read, Write, Edit, Grep, Glob, AskUserQuestion, Bash(python:*), Bash(python3:*), Bash(git diff:*)
---

Create a project skill named **$1**, for seat **$2** if given. If $1 is empty, ask what workflow
the skill would capture and stop.

One flow, three commands: find an existing skill (`reference/skill-discovery.md` in the bootstrap
skill), or create one here, then wire it with `/skill-wire`. Creating is the last resort, not the
first: a skill that already exists and passes review beats one written today.

**Preflight.** Needs `.claude/templates/skill/`, `.claude/scripts/skill-check.py` and
`.claude/agents/`. If one is missing, stop and point at `/harness-update`.

## 1. Decide: skill, or somewhere else

A skill earns its place only when it is **reusable workflow or domain knowledge that measurably
improves behaviour** - something the model gets wrong or slow without it, needed across tasks, and
too large or too conditional to sit in context all the time. Everything else has a better home:

| The content is | It belongs in |
|---|---|
| a fact or convention every session needs | `CLAUDE.md` / `AGENTS.md` |
| a constraint that applies to certain paths | a rule in `.claude/rules/` (path-scoped) |
| a procedure the user starts by name, once | a command in `.claude/commands/` |
| a role: scope, tools, model, budget | an agent definition in `.claude/agents/` |
| something for people to read | a doc under `docs/` |
| a deterministic transformation or check | a script, called from wherever it is needed |
| knowledge the model already has | nowhere |

Then check what exists: read every `.claude/skills/*/SKILL.md` description and grep for the
workflow's key words. If a skill already covers it, extend that one - one canonical source,
never a second copy kept in sync by hand. If the workflow is generic rather than project-specific,
look for a published skill first (`reference/skill-discovery.md`).

**Then ASK, and wait.** Put the proposal to the user with `AskUserQuestion`: the workflow, the
evidence it recurs, why it is a skill and not one of the homes above, which seat(s) need it, and
what "measurably better" will mean. Create nothing without an explicit yes. If the answer is "put
it elsewhere", do that instead and stop.

## 2. Scaffold

Copy `.claude/templates/skill/` to `.claude/skills/$1/` and fill every `[[FILL: ...]]`:

- **name** - `$1`, lowercase and hyphens, equal to the folder name.
- **description** - what it does, then "Use when ...", then "Do not use for ..." naming the
  neighbouring skill or command that owns that job. It is in context in every session, so every
  word is paid for: lead with the use case, cut adjectives, and compare its key words against the
  other skills' descriptions - a phrase two skills both claim makes routing a coin toss.
- **SKILL.md body** - inputs, outputs, and "done when". Prerequisites with a stop condition,
  branches, a retry limit. Mark each step **fixed**, **guided** or **open** so the freedom is
  deliberate. Write what to do, with one good example, rather than a list of prohibitions. Ask for
  a short summary of the actions taken, never for the reasoning itself. Leave out anything the
  model already knows.
- **references/** - detail needed only sometimes. Every reference is named from SKILL.md; none
  leads to a further one.
- **scripts/** - every deterministic step, including the completion check `scripts/validate.py`:
  inputs validated, exit 0 / 1 / 2, idempotent. A script that touches the network, installs
  something or deletes files says why in SKILL.md, or loses that line. Delete the folder only if
  the skill truly has no deterministic step.

"Done" is the validator's exit code. Do not add a "double-check" or "final review" step on top of
it - a second subjective pass costs turns and finds nothing the script would not.

## 3. Trigger cases

Fill `.claude/skills/$1/evals/trigger-cases.md`: all six case types - positive discovery, negative
discovery, edge case, conflict/composition, execution quality, efficiency - each with the request,
the repo state, the expected and not-expected skills, and the success criteria. The negative case
is the near miss that shares key words with this skill; the conflict case names a neighbouring
skill. Execution quality states the baseline without the skill: if the skill makes no measurable
difference there, it is not worth its description's always-loaded cost - go back to step 1.

## 4. Lint

```bash
python .claude/scripts/skill-check.py --skill .claude/skills/$1
```

Before wiring, the only finding left should be `orphan`. Fix anything else - including warnings
about scripts - and run it again. Report the description's estimated token cost to the user.

## 5. Wire

Run `/skill-wire $1 <seat>` for each seat that needs it (`$2` if given). That is where the
`skills:` preload, the content review and the changelog record happen; this command does not
repeat them. If no seat fits and only the main session uses the skill, name it from the command or
rule that triggers it instead.

Then run the linter again: it must exit 0. An unwired skill is an orphan - it costs its
description in every session and serves nobody.

## Removing a skill

A skill that fails its execution-quality case, or that nothing has used for a release, goes:
unwire it with `/skill-wire`, delete `.claude/skills/<name>/`, and record why in
`docs/context/tool-changelog.md`. Keeping a skill that adds nothing is not free.

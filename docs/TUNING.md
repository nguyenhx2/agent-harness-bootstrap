# Post-bootstrap tuning

`harness-bootstrap` picks a starting posture at intake and writes it into `.claude/`. Real projects
drift from that posture - a deploy command earns trust, a seat needs a tool it does not have, the
board needs a health check, the skill ships a new asset you want to pick up, the code shifted enough
that the module map is stale. Five commands, installed into every bootstrapped repo, cover that drift. This page is the full reference for each: what it
does, when to reach for it, a worked example, and the invariants it will not let you break.

None of the five edit hook *logic*. They edit data - lists, caps, seat frontmatter, `vars.json` - the
same way any other reviewed change would. If what you want requires rewriting a `.sh`/`.ps1` hook,
that is a normal code change, not a tuning.

## `/board-audit`

**What it does.** Read-only sweep of `docs/tasks/` against reality: git worktrees, branches, and
`.claude/state/history/` runs. It never fixes anything - it reports `WHAT | WHERE | SUGGESTED ACTION`
and ends with `BOARD CLEAN` or a finding count.

**When to reach for it.** Before resuming work after a crash or a long gap, before a release, or any
time a task's status feels stale. It catches:

- **Stale Active** - a task marked `Active` with no recent session-log row and no matching run in
  `.claude/state/history/`.
- **Unlogged completions** - a subagent run finished (there's an archive file) but nobody wrote it
  into the task's session log.
- **Board drift** - frontmatter `status:` disagreeing with the master-plan row, or a file sitting in
  the wrong directory (`active/` vs `done/`).
- **Attempt-cap breaches** - a task at `attempts: 3` or more that is still `Active` instead of
  `Blocked` with an escalation note.
- **Unknown worktrees and branches** - work happening (or abandoned) outside anything the board
  references.
- **Blocked with no unblocker** - a `Blocked` task whose notes name no owner or condition, so it can
  never resurface on its own.
- **Stale code graph** - `.claude/state/code-graph.stale` is non-empty, or
  `python .claude/scripts/code-graph.py --check` exits 1: dispatch decisions are being made against
  an outdated module map. The fix is `/code-graph`, not ignoring it.

**Worked example.**

```text
/board-audit
```

```text
2 findings - board needs reconciliation
  Stale Active | docs/tasks/active/TASK-014.md | last session-log row is 4 days old, no matching
    history entry - reassign or close it out
  Unlogged completion | .claude/state/history/2026-08-01-143201-dev-agent.json | names TASK-009,
    session log has no matching row - collect the result
Next: reconcile TASK-014 first, it blocks the master-plan row above it.
```

Fix nothing yourself: `/board-audit` only sees. The orchestrator or the user reconciles.

## `/harness-tune`

**What it does.** The sanctioned path for loosening or tightening control after bootstrap: deployment
rights, destructive-command posture, the spawn allowlist, attempt/turn caps, and review-gate scope.
Every change shows as a diff and lands only after an explicit yes.

**When to reach for it.** The team's risk appetite changed since intake - you trust the agent with
staging deploys now, or a seat keeps hitting its turn cap on legitimately long tasks.

**Worked example.**

```text
/harness-tune
```

The command asks which dial to turn (one batch, `AskUserQuestion`), then shows the exact diff before
writing:

```text
Dial: Deployment rights
Current: human-only (fly deploy sits in permissions.deny)
Proposed: agent-with-approval (fly deploy moves to permissions.ask)

--- .claude/settings.json
-  "deny": ["Bash(fly deploy*)", ...]
+  "ask":  ["Bash(fly deploy*)", ...]

Apply? [y/N]
```

Every accepted change is recorded in `docs/context/tool-changelog.md` - what changed, why, when, who
asked.

**What it refuses.** Removing the code-review gate entirely. `/harness-tune` can narrow *which* tasks
route through `security-reviewer` (every task vs. only tasks touching PII/data paths), but it will not
delete the gate - that is a different repo, not a tuning.

## `/agent-permissions`

**What it does.** Grants or revokes exactly one tool on exactly one roster seat. Usage:

```text
/agent-permissions <agent> grant|revoke <Tool>
```

It reads the seat's current frontmatter, checks the change against the invariants below, shows the
diff, gets a yes, applies it, and records it in `docs/context/tool-changelog.md`.

**When to reach for it.** A dev agent needs `Bash` for a build step it currently can't run, or a seat
was over-granted at bootstrap and should be narrowed. Revocations apply immediately, no invariant
check needed - narrowing is always safe.

**Worked example.**

```text
/agent-permissions app-dev grant Bash
```

```text
.claude/agents/app-dev.md
- tools: Read, Grep, Glob, Edit, Write
+ tools: Read, Grep, Glob, Edit, Write, Bash

Apply? [y/N]
```

**What it refuses (invariants, not warnings - no confirmation prompt offered to override them):**

- **Reviewers never gain `Edit` or `Write`.** `code-reviewer`, `security-reviewer`, and
  `spec-guardian` are gates. A gate that can edit is a dev agent that lost its independence. If a
  review finding should be auto-applied, dispatch a dev agent with that finding - that is a task, not
  a permission change.
- **Only the orchestrator holds `Agent`.** A second spawner is a second uncontrolled dispatch point;
  the scaffolder itself fails the build if one appears.
- **`model:` and `effort:` are not permissions.** Changing them is a cost/roster decision -
  `/agent-permissions` points you at the roster file and `reference/cost-model.md` instead, and still
  requires the change to be recorded.
- **No wildcard grants.** A seat lists exact tools; "give it everything" is the default-agent problem
  the roster exists to prevent.

## `/harness-update`

**What it does.** Re-runs the bootstrap scaffolder on an already-bootstrapped repo, safely, any number
of times. It never overwrites a file that differs from what it would generate - everything you or your
team edited survives as a `CONFLICT` you resolve by hand.

**When to reach for it.** The skill shipped new assets or rules you want, the codebase changed enough
that a dev agent's path scope no longer matches reality, or you're adding/retiring an agent seat.

**Worked example.**

```text
/harness-update
```

```text
Re-reading the codebase for changed areas...
  src/billing/ is new since bootstrap - no seat owns it.

Re-running scaffold.py --target . --vars vars.json
  ADDED     .claude/commands/harness-tune.md   (new in this skill version)
  KEPT      .claude/agents/app-dev.md           (unchanged)
  CONFLICT  .claude/rules/testing.md            (you edited this; skill version differs)

3 files: 1 added, 1 kept, 1 conflict to resolve by hand.
Suggested: instantiate a dev-agent seat scoped to src/billing/, add it to the orchestrator's
routing table in the same change.
```

Adding a seat and not adding its routing row leaves it unreachable; adding a routing row with no seat
file dispatches to nothing - `/harness-update` checks both land together. Retiring a seat runs
`/board-audit` first, to confirm no Active task still names it as owner.

**What it never touches.** `tech-stack.md`, `coding-standards.md`, scopes, or any content derived from
your code or your intake answers - those go through the `CONFLICT` queue with you deciding, never a
silent overwrite.

## `/code-graph`

**What it does.** Builds or refreshes the repo's code knowledge graph - modules, files, and import
edges - so an agent can answer "what depends on the thing I am about to change" without reading the
whole tree. Writes two files: `.claude/state/code-graph.json` (machine-readable: modules, per-module
files, import edges with reference counts, module owner matched from the roster's scopes) and
`docs/context/code-graph.md` (agent-readable: a mermaid module graph plus a fan-in/fan-out table).
The non-blocking `graph-stale` hook appends every edited source file to
`.claude/state/code-graph.stale` as you work, so the graph's own staleness is always knowable; the
rebuild is deliberate, on request, never a side effect of an edit.

**When to reach for it.** Before dispatching or accepting a task that touches a cross-module edge,
after a `graph-stale` build-up flags in `/board-audit`, or any time an agent needs "what else calls
this module" answered without a full-tree read.

**Worked example.**

```text
/code-graph
```

```text
Checking .claude/state/code-graph.stale... 6 files edited since the last build.
Rebuilding: python .claude/scripts/code-graph.py
  14 modules, 212 files, 38 import edges.

Changed since the last build:
  NEW EDGE  billing -> notifications (billing/invoice.py now imports notify_customer)
  This is either a missing interface or a boundary violation - review before merging.
```

**What it never does.** Rebuild silently as a side effect of an edit - only `graph-stale` reacts to
edits, and it only marks the graph stale, never rebuilds it. And it does not replace the review a new
cross-module edge deserves; it surfaces the edge so a human or reviewer looks at it.

## `/skill-wire`

**What it does.** Maps a skill installed in `.claude/skills/` to one roster seat. Wiring is a
capability decision, so it gets the `/agent-permissions` shape: read the skill and the seat, re-run
the mandatory content review (every file, at wire time - an `npx skills update` can have changed
the text since install), check the scope actually fits the seat's role, show the diff, and record
the wire in `docs/context/tool-changelog.md`. Discovery and install criteria live in the bootstrap
skill's `reference/skill-discovery.md`: installs, publisher, skills.sh audit status, and a
mandatory read of the skill's files before anything is trusted.

**When to reach for it.** Right after installing a skill from [skills.sh](https://www.skills.sh/)
(`npx skills add <owner/repo>@<skill>`), or when a seat's work keeps needing a capability an
already-installed skill provides.

**Worked example.**

```text
/skill-wire pdf-processing qa-test
```

```text
Reading .claude/skills/pdf-processing/SKILL.md and .claude/agents/qa-test.md...
Content review: 3 files read, no config-edit or exfiltration instructions found.
Scope: report parsing fits qa-test's artifact checks. Diff:
  + Skills available: pdf-processing (parse PDF reports; source anthropics/skills, 12,400 installs)
Apply? [records to docs/context/tool-changelog.md]
```

**What it refuses.** A skill whose content instructs `.claude/`, `settings.json`, or hook edits is
wired to no seat, ever. Reviewers get read-only skills only. Only the orchestrator may hold a
skill that finds or installs other skills. Every wire is recorded - an unrecorded wire fails the
quality gate.

## Quick reference

| Command | Changes | Confirmation |
|---|---|---|
| `/board-audit` | Nothing - read-only | N/A |
| `/harness-tune` | Control-level dials: deploy rights, destructive-command posture, spawn allowlist, caps, review-gate scope | Diff shown, yes required, one dial at a time |
| `/agent-permissions` | One tool on one seat | Diff shown, yes required (invariant violations refuse instead) |
| `/harness-update` | Re-syncs `.claude/` with the current skill version and codebase | `CONFLICT` queue, resolved by hand |
| `/code-graph` | Rebuilds `.claude/state/code-graph.json` and `docs/context/code-graph.md`, clears the stale log | None - regenerates derived files, nothing hand-authored is touched |

## The three invariants that hold across all five

However you reach them - `/harness-tune`, `/agent-permissions`, or a hand edit reviewed like any
other change - three things do not move:

1. **Reviewers never gain write access.** `code-reviewer`, `security-reviewer`, `spec-guardian` stay
   read-only gates.
2. **Only the orchestrator spawns.** One dispatch point, enforced by the scaffolder's build check and
   by `guard-agent-spawn`.
3. **The code-review gate cannot be removed**, only rescoped to which paths trigger it.

See also: [`roster.md`](../harness-bootstrap/reference/roster.md) for what each seat is for,
[`cost-model.md`](../harness-bootstrap/reference/cost-model.md) for what a tuning costs, and
[`task-control.md`](../harness-bootstrap/reference/task-control.md) for the board mechanics
`/board-audit` checks against.

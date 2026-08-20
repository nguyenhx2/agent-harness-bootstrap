# Post-bootstrap tuning

`harness-bootstrap` picks a starting posture at intake and writes it into `.claude/`. Real projects
drift from that posture - a deploy command earns trust, a seat needs a tool it does not have, the
board needs a health check, the skill ships a new asset you want to pick up, the code shifted enough
that the module map is stale. Eight commands, installed into every bootstrapped repo, cover that
drift, plus two more (`/spec-ingest`, `/spec-retract`) that arrive with a `spec-builder` spec set and
ripple a source into or out of `docs/specs/`. This page is the full reference for all ten: what each
does, when to reach for it, a worked example, and the invariants it will not let you break.

The commands used during normal feature delivery - `/new-task`, `/implement-fr`, `/test`,
`/review-changes`, `/deploy`, and the rest - are a different family: they build the product, not the
harness. Their reference lives next to the sequence diagram they implement, in
[`docs/FLOWS.md` section 7](FLOWS.md#7-delivery-commands-command-by-command).

None of the eight edit hook *logic*. They edit data - lists, caps, seat frontmatter, `vars.json`,
the disabled ledger - the same way any other reviewed change would. If what you want requires
rewriting a `.sh`/`.ps1` hook, that is a normal code change, not a tuning.

## `/board-audit`

**What it does.** Runs `python .claude/scripts/board-check.py` first - stdlib-only validation of
every task file's frontmatter enums (`status`, `attempts`, `priority`, `human_gate`) and a
dependency-cycle check on `deps:` chains. A non-zero exit there means the board itself is
malformed, and that findings list is reported verbatim before anything else runs, because the
sweeps below assume well-formed frontmatter. Only then does it sweep `docs/tasks/` against
reality: git worktrees, branches, and `.claude/state/history/` runs. It never fixes anything - it
reports `WHAT | WHERE | SUGGESTED ACTION` and ends with `BOARD CLEAN` or a finding count.

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
rights, destructive-command posture, the spawn allowlist, attempt/turn caps, review-gate scope, and
agent-history detail. Six dials in total. Every change shows as a diff and lands only after an
explicit yes.

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
route through the review seat, but it will not delete the gate - that is a different repo, not a
tuning. The dial's shape depends on the roster: with the split reviewers (default, no
`solo_review`), it narrows whether `security-reviewer` runs on every task or only on tasks touching
PII/data paths, and `code-reviewer` keeps running unconditionally. With `solo_review` set, the two
gates are merged into the single `reviewer` agent, and the dial instead tunes how deep that merged
pass goes on tasks that do not touch PII/data paths - it cannot be tuned away on paths that do.

## `/harness-toggle`

**What it does.** Turns a single rule, command, hook, or agent seat off or back on, reversibly,
without deleting anything or rewriting `settings.json` by hand. `python .claude/scripts/harness-toggle.py` is the
only mutator: it moves the file(s) under `.claude/disabled/`, removes (or restores) the matching
`settings.json` registration, records the change in `.claude/disabled.json`, and regenerates
`harness-graph.json` plus the HTML view so disabled items render greyed out. A parked agent seat
moves to `.claude/disabled/agents/` the same way; every seat is at least SOFT, because the
orchestrator's routing table still lists it, and `orchestrator` plus the reviewer seats are HARD.
Parking a seat is reversible - ADDING or RETIRING one is still `/harness-update`.

**When to reach for it.** A rule or hook does not fit this repo and you want it off without losing
the file, or a scaffold re-run resurrected something the team had deliberately disabled.

**Worked example.**

```text
/harness-toggle
```

```text
python .claude/scripts/harness-toggle.py list
  active:   15 rules, 22 commands, 9 hooks
  disabled: none

Disable which item? protect-adr (hook)
Reason: this repo has no docs/adr/ directory yet
```

```text
python .claude/scripts/harness-toggle.py disable protect-adr --yes
  moved .claude/hooks/protect-adr.sh -> .claude/disabled/hooks/protect-adr.sh
  removed settings.json PreToolUse registration
  recorded in .claude/disabled.json (reason: no docs/adr/ directory yet)
  regenerated harness-graph.json + harness-graph.html
```

**Safety tiers.** Two, enforced by the script itself, not by convention:

- **HARD** - `protect-secrets`, `guard-agent-spawn`, `security-privacy`, `agent-guardrails`,
  `/review-changes`: refused (exit 2) unless the invocation carries `--confirm "disable <name>"`
  with that exact phrase, and the phrase must be the user's own words from this conversation, never
  composed on their behalf.
- **SOFT** - `guard-main-commit`, `check-commit-msg`, `protect-adr`, `ai-governance`: refused until
  `--yes` is passed, after the user has explicitly confirmed.

**What survives a scaffold re-run.** `.claude/disabled.json` is committed and shared with the team;
`/harness-update` and a fresh `scaffold.py` run both read it, so a disabled item does not silently
come back. If one does resurface (a hand edit, a merge), run
`python .claude/scripts/harness-toggle.py reapply` rather than disabling it a second time.

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

- **Reviewers never gain `Edit` or `Write`.** `code-reviewer`, `security-reviewer` (or the merged
  `reviewer`, on a `solo_review` roster), and `spec-guardian` are gates. A gate that can edit is a
  dev agent that lost its independence. If a review finding should be auto-applied, dispatch a dev
  agent with that finding - that is a task, not a permission change.
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

**Respects toggle state.** If `.claude/disabled.json` exists, `/harness-update` runs
`python .claude/scripts/harness-toggle.py reapply` after conflicts are resolved, so a `--force`
overwrite or a hand edit can't silently resurrect something the team deliberately disabled. Before
finishing, it also confirms the scaffolder's spawn-boundary lint still passes and the routing table
covers every seat, then regenerates the harness graph (`python .claude/scripts/harness-graph.py
--html`) - script-driven changes don't fire the Edit/Write hooks that normally keep it current.

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

**What it never does.** Rebuild the *code* graph silently as a side effect of an edit - `graph-stale`
only marks it stale for a source-file edit, deliberately, since a full source scan on every write
would tax every session. (The harness graph and the docs graph are different: `graph-stale` rebuilds
those two immediately on `.claude/` and `docs/` edits, because both scans are cheap. Only the code
graph stays deferred to an explicit `/code-graph` run.) And `/code-graph` does not replace the review
a new cross-module edge deserves; it surfaces the edge so a human or reviewer looks at it. Running it
also refreshes `.claude/state/harness-graph.json` and both HTML exports
(`docs/context/harness-graph.html`, `docs/context/specs-graph.html`), since module owners feed into
the harness graph.

**Engine.** Defaults to the stdlib regex extractor in `.claude/scripts/code-graph.py` - zero install,
best-effort static edges, "missing an edge" means absence of evidence, not evidence of isolation. If
a GitNexus/codegraph MCP server (or a comparable code-index tool) is available in the session, it may
replace the extraction for richer call-level edges; the file contract does not change either way, so
nothing downstream cares which engine ran. The choice is asked once and recorded in
`docs/context/tool-changelog.md`. If the external engine becomes unavailable mid-project, the next
`/code-graph` run falls back to the builtin engine on its own - degraded edges, same files.

## `/docs-graph`

**What it does.** Builds the documentation twin of the code graph: which document defines each
requirement/decision/task ID, who references it, and which IDs are orphans. Writes
`.claude/state/docs-graph.json`, `docs/context/docs-graph.md` (mermaid + orphan list), and - via
`graph-html.py` - the interactive `docs/context/specs-graph.html`. Purpose is TRACEABILITY;
`/code-graph` covers dependency. The same script pass also regenerates
`docs/context/harness-graph.html`, the interactive map of agents, hooks, rules, commands,
settings, and modules.

**When to reach for it.** After any spec edit, when spec-guardian needs to check a diff's claimed
requirement IDs, or when the orchestrator wants the unscheduled-requirement backlog (orphan IDs).

**Worked example.**

```text
/docs-graph
```

```text
python .claude/scripts/docs-graph.py
  42 docs, 118 IDs, 96 edges, 3 orphan(s)
python .claude/scripts/graph-html.py
  wrote docs/context/specs-graph.html, docs/context/harness-graph.html
Orphans: FR-017 (defined in 05, no task references it), BR-009, ADR-0007 - unstarted work or dead references.
```

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

## The spec side

Two more commands arrive with a `spec-builder` spec set rather than the harness - see
`spec-builder/SKILL.md` for the skill they belong to.

### `/spec-ingest`

**What it does.** Folds a new information source - meeting notes, a transcript, a legacy doc, an
email thread - into an existing `docs/specs/` set without regenerating anything. Usage:
`/spec-ingest <path-or-pasted-source>`. It reads the source whole, maps each extractable statement to
its home section (a `03` glossary term, a `05` FR or business rule, a `07` NFR, and so on - a section
may be one file or a folder of `FR-nn-<slug>.md` files with an index), then diffs each mapped
statement against what the section already says: a new fact with no conflict is added with a source
note; a conflict with existing normative text is never silently overwritten - both versions are
shown, `AskUserQuestion` decides which wins, and the loser is recorded in the revision history; a
restated fact is skipped and the corroboration noted instead. A statement that maps to a section the
project never selected at creation is surfaced as a finding, not forced elsewhere.

**When to reach for it.** A new source of truth shows up after the spec set already exists - more
meeting notes, an updated transcript, a legacy doc someone finally found - and it needs reconciling
against the sections rather than bolted on as a separate file.

**Worked example.**

```text
/spec-ingest meeting-notes-2026-08-12.txt
```

```text
Mapped 6 statements: 2 to 05 (new FR candidates), 1 to 07 (an NFR target), 3 to 03 (glossary terms).
Conflict: 05 already states "refund window: 14 days"; the note says "30 days".
Which wins? [14 days (current) / 30 days (new source)]
Applied: FR-22 added, NFR-09 target updated, 3 glossary terms added.
Recorded in 13-revision-history.md. Ripples: glossary.md updated, business-rules.md updated.
docs-graph rebuilt: 0 new orphans.
```

**What it writes.** The mapped-to spec section(s), one row in `13-revision-history.md` per ingest
(date, source, sections touched, IDs added/changed, who approved any conflict), and - where a harness
exists - the ripple targets: `docs/context/glossary.md`, `docs/context/business-rules.md`, the owning
dev agent's FR list, and the board (a new FR with no owning module becomes a Pending task, never a
silent seat assignment). It then rebuilds traceability (`python .claude/scripts/docs-graph.py` and
`graph-html.py`) and records the ingest itself in `docs/context/tool-changelog.md`.

**What it refuses.** Regenerating a section from a template over hand-written content. Renumbering an
ID - a new requirement always takes the next free number. Letting the raw source become the
reference: the spec absorbs the source, the source never replaces the spec.

### `/spec-retract`

**What it does.** Removes or corrects information already absorbed into `docs/specs/`. Usage:
`/spec-retract <source-name | ID | quoted-claim>` - a whole source that turned out unreliable, one
wrong requirement, or a specific claim. It traces the blast radius first: every section (and, in
folder form, every `FR-nn-<slug>.md`) mentioning the source, ID, or claim's key terms; every document
`.claude/state/docs-graph.json` shows referencing the affected IDs; every task naming them. The full
list is shown before anything changes. A wrong value gets fixed in its defining section. A claim with
no remaining source does not vanish - it converts to an open issue (`OI-nn`: "was asserted by
`<source>`, source retracted, needs confirmation"), because a silently deleted requirement looks
identical to one that never existed, and someone may have built on it.

**When to reach for it.** A source turns out to be unreliable, wrong, or superseded, and the spec
already has content built from it.

**Worked example.**

```text
/spec-retract "vendor-api-notes.pdf"
```

```text
Blast radius: FR-14, FR-15 (only-sourced from this doc), BR-07 (corroborated elsewhere - stays),
2 tasks reference FR-14/15 (TASK-031, TASK-033).
FR-14, FR-15 -> Withdrawn, reason: source retracted (2026-08-14). BR-07 loses one source note, stays.
TASK-031, TASK-033 -> Blocked, human_gate: requirement withdrawn.
Recorded in 13-revision-history.md. docs-graph rebuilt: 0 new orphans (both IDs still resolve, as
Withdrawn).
```

**What it writes.** One row in `13-revision-history.md` (what was retracted, why, which IDs went
`Withdrawn` or converted to `OI-nn`, who decided), and - where a harness exists - the ripple: the
owning dev agent's FR list drops withdrawn IDs, Active tasks implementing them go `Blocked` with
`human_gate: requirement withdrawn` (a human decides whether the work stops, never a silent
deletion), and glossary terms only the retracted source defined are marked disputed. Rebuilds
traceability the same way `/spec-ingest` does, and records the retraction in
`docs/context/tool-changelog.md`.

**What it refuses.** Reusing a withdrawn ID - a retracted `FR-nn` keeps its number, marked
`Withdrawn`, and the next requirement takes a fresh one. Deleting a claim outright just because its
source disappeared - it becomes a tracked open issue instead.

These two ship with the `spec-builder` skill, not `harness-bootstrap` - a repo that only bootstrapped
the harness does not have them until `spec-builder` is also installed on it.

## Quick reference

| Command | Changes | Confirmation |
|---|---|---|
| `/board-audit` | Nothing - read-only (runs `board-check.py` first) | N/A |
| `/harness-tune` | Control-level dials: deploy rights, destructive-command posture, spawn allowlist, caps, review-gate scope, agent-history detail | Diff shown, yes required, one dial at a time |
| `/harness-toggle` | Enables/disables one rule, command, hook, or agent seat; updates `.claude/disabled.json` and the harness graph | HARD items need a typed confirm phrase; SOFT items and every agent seat need `--yes` |
| `/agent-permissions` | One tool on one seat | Diff shown, yes required (invariant violations refuse instead) |
| `/harness-update` | Re-syncs `.claude/` with the current skill version and codebase | `CONFLICT` queue, resolved by hand |
| `/code-graph` | Rebuilds `.claude/state/code-graph.json` and `docs/context/code-graph.md`, clears the stale log | None - regenerates derived files, nothing hand-authored is touched |
| `/docs-graph` | Rebuilds `.claude/state/docs-graph.json`, `docs/context/docs-graph.md`, and both HTML graph exports | None - derived files only |
| `/skill-wire` | One installed skill onto one seat's "Skills available" section | Diff shown, yes required; content re-review at wire time, invariant violations refuse |
| `/spec-ingest` (`spec-builder`) | Spec section(s), `13-revision-history.md` row, glossary/business-rules/board ripples | Conflicts shown via `AskUserQuestion`; IDs appended, never renumbered |
| `/spec-retract` (`spec-builder`) | Corrects or converts spec content to `OI-nn`, `13-revision-history.md` row, downstream ripples | Blast radius shown before any change; withdrawn IDs never reused |

## The three invariants that hold across all of them

However you reach them - `/harness-tune`, `/agent-permissions`, or a hand edit reviewed like any
other change - three things do not move:

1. **Reviewers never gain write access.** `code-reviewer`, `security-reviewer` (or `reviewer`, when
   merged under `solo_review`), `spec-guardian` stay read-only gates.
2. **Only the orchestrator spawns.** One dispatch point, enforced by the scaffolder's build check and
   by `guard-agent-spawn`.
3. **The code-review gate cannot be removed**, only rescoped to which paths trigger it.

See also: [`roster.md`](../harness-bootstrap/reference/roster.md) for what each seat is for,
[`cost-model.md`](../harness-bootstrap/reference/cost-model.md) for what a tuning costs, and
[`task-control.md`](../harness-bootstrap/reference/task-control.md) for the board mechanics
`/board-audit` checks against.

# Post-bootstrap tuning

**English** · [日本語](TUNING.ja.md)

`harness-bootstrap` picks a starting posture at intake and writes it into `.claude/`. Real projects
drift from that posture - a deploy command earns trust, a seat needs a tool it does not have, the
board needs a health check, the skill ships a new asset you want to pick up, the code shifted enough
that the module map is stale. Nine commands, installed into every bootstrapped repo, cover that
drift (`/code-graph` only on a repo with the code purpose), plus two more (`/spec-ingest`,
`/spec-retract`) that arrive with a `spec-builder` spec set and ripple a source into or out of
`docs/specs/`. This page is the full reference for all eleven: what each does, when to reach for it,
a worked example, and the invariants it will not let you break. Rule of thumb: a single dial is
`/harness-tune` or `/agent-permissions`; switching one control off or on is `/harness-toggle`; a
structural change (new seats, new assets, a re-scope) is `/harness-update`.

The commands used during normal feature delivery - `/new-task`, `/implement-fr`, `/test`,
`/review-changes`, `/deploy`, and the rest - are a different family: they build the product, not the
harness. Their reference lives next to the sequence diagram they implement, in
[`docs/FLOWS.md` section 7](FLOWS.md#7-delivery-commands-command-by-command).

None of them edit hook *logic*. They edit data - lists, caps, seat frontmatter, `vars.json`,
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
- **Unreviewed module edge** (code repos) - `python .claude/scripts/code-graph.py --check` exits 1:
  the code imports across a module line that `docs/context/code-graph.md` does not list. Each edge
  it names is a decision - remove the import, or accept it with `/code-graph` - never something to
  ignore.

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

**What it does.** Tunes the harness from what actually happened in it, not from a fresh interview.
It reads one pass of evidence, proposes at most four ranked changes, asks once, applies the ones you
choose, proves each, and closes the loop. The evidence, each source optional (a missing one is a line
in the report, not a reason to stop):

- **Run archive** (`.claude/state/history/`) - seats never dispatched, runs that ended partial at
  `maxTurns`, one seat dominating the count.
- **Blocks and denials** - `BLOCKED:` and "denied" lines: a guard that fires on legitimate work, or a
  deny entry routed around by hand.
- **Retry and attempt caps** - `.claude/state/retry-budget`, `task.py check`, `attempts:` and
  `Blocked` notes: loops the caps caught.
- **Verification** - the `log:` lines `verify-plan.py` wrote: gates that always run and never find
  anything, or were skipped on changes that later broke.
- **Structure** - `harness-view assess . --json` when the binary is on PATH, otherwise
  `harness-graph.py` and `board-check.py`: orphan seats, unregistered hooks, unscoped rules.
- **Recorded intent** - `docs/context/tool-changelog.md` and `.claude/disabled.json`: what was tuned
  or switched off before, and why. A recorded decision is never undone silently.

Each candidate maps to one of seven dials, and only these: deployment rights; destructive-command
deny entries; the spawn allowlist; caps (`maxTurns`, the attempt cap); model and effort (a seat's
`effort:`, or its tier in `model-tiers.md` first and the seat's `model:` second); review gates (the
triggers `verify-plan.py` reads from `.claude/verify-map.json`); and agent-history detail.

**When to reach for it.** The team's risk appetite changed since intake - you trust the agent with
staging deploys now, a seat keeps hitting its turn cap on legitimately long tasks, or a review gate
runs on every docs-only diff and raises nothing. With no evidence behind a change, it proposes
nothing: "nothing to tune" is a result, reported with the numbers that show it. An argument such as
`/harness-tune cost` weights the evidence toward that focus but never skips the read.

**Worked example.**

```text
/harness-tune deploy
```

The command gathers the evidence, then asks once (one `AskUserQuestion`, a multi-select; each option
is the change, its description the evidence and the cost), and shows the exact diff before writing:

```text
Change 1 of 2: Deployment rights
Evidence: 6 session logs record "deploy" asked by hand; no run touched production.
Current: human-only (fly deploy sits in permissions.deny)
Proposed: agent-with-approval (fly deploy moves to permissions.ask)

--- .claude/settings.json
-  "deny": ["Bash(fly deploy*)", ...]
+  "ask":  ["Bash(fly deploy*)", ...]
```

Each applied change is followed by the check that exercises it: a deny/ask/allow entry is parsed as
JSON and one payload the entry should stop is piped through the hook that guards it; a seat, cap,
model or effort edit goes through `harness-graph.py`, which refuses a malformed seat; a review-gate
change goes through `verify-plan.py --files <a path from the evidence>`. A check that fails reverts
that one change and is reported; the others stand. The command ends with
`python .claude/scripts/harness-check.py`, which must exit 0, and records one entry per applied change
in `docs/context/tool-changelog.md`: what changed, the evidence, the check that passed, who asked.

**What it refuses.** Removing a review gate entirely. `/harness-tune` can narrow *which* changes
route through a review seat, but it will not delete the gate - that is a different repo, not a
tuning. A deny entry is never removed without naming the control that replaces it, and raising a cap
or the history level to `full` (whole prompts, PII included, on disk) states its cost. It never
edits a hook's logic: tuning changes data - lists, caps, frontmatter values - and hook code is a
reviewed change like any other. Switching a whole rule, command, hook or seat on or off is
`/harness-toggle`; adding or retiring a seat is `/harness-update`, and it names the right command
instead of doing the work here.

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
  active:
    rule/00-overview
    ...
    hook/protect-adr
    ...
  disabled:
    (none)

Disable which item? hook/protect-adr
Reason: this repo has no docs/adr/ directory yet
```

```text
python .claude/scripts/harness-toggle.py disable hook/protect-adr --yes --reason "no docs/adr/ directory yet"
  moved .claude/hooks/protect-adr.sh -> .claude/disabled/hooks/protect-adr.sh
  removed settings.json PreToolUse registration
  recorded in .claude/disabled.json (reason: no docs/adr/ directory yet)
  regenerated harness-graph.json + harness-graph.html
```

**Safety tiers.** Two, enforced by the script itself, not by convention:

- **HARD** - `protect-secrets`, `guard-agent-spawn`, `security-privacy`, `agent-guardrails`,
  `/review-changes`, and the `orchestrator` and review seats: refused (exit 2) unless the invocation carries `--confirm "disable <name>"`
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
  `reviewer`, on a `solo_review` roster), `spec-guardian` and `checker` are gates. A gate that can edit is a
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
team edited survives as a `CONFLICT` you resolve by hand. The one additive exception is
`settings.json`: when it differs, every hook this version ships that the file does not yet register
is added (reported as `MERGED`), nothing you wrote changes, nothing listed in `.claude/disabled.json`
is re-registered, and a second run adds nothing.

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
  ADDED     .claude/commands/new-skill.md       (new in this skill version)
  KEPT      .claude/agents/app-dev.md           (unchanged)
  CONFLICT  .claude/rules/testing.md            (you edited this; skill version differs)
  MERGED    .claude/settings.json: registered guard-board

4 files: 1 added, 1 kept, 1 conflict to resolve by hand, 1 merged.
Suggested: instantiate a dev-agent seat scoped to src/billing/, add it to the orchestrator's
routing table in the same change.
```

Adding a seat and not adding its routing row leaves it unreachable; adding a routing row with no seat
file dispatches to nowhere - `/harness-update` checks both land together. Retiring a seat runs
`/board-audit` first, to confirm no Active task still names it as owner.

**Respects toggle state.** If `.claude/disabled.json` exists, `/harness-update` runs
`python .claude/scripts/harness-toggle.py reapply` after conflicts are resolved, so a `--force`
overwrite or a hand edit can't silently resurrect something the team deliberately disabled.

**Re-ports to the recorded targets.** Intake persisted which other tools the harness must run in (the
`target_cursor` / `target_codex` flags in `vars.json` and the "Target AI tools" line in
`docs/context/tool-changelog.md`). `/harness-update` reads them and runs `port.py` for exactly those
targets without asking again and without re-scanning the tree, which cannot name its own tool. A
`.cursor/` or `.codex/` file without the porter's `generated by port.py` marker was written by a
human: it is reported as `CONFLICT` and left alone.

**Closes with a check.** Before finishing it confirms the scaffolder's spawn-boundary lint still
passes, the routing table covers every seat, and a known-bad hook payload still fires, then
regenerates the harness graph (`python .claude/scripts/harness-graph.py --html`) - script-driven
changes don't fire the Edit/Write hooks that normally keep it current. The final step is
`python .claude/scripts/harness-check.py`, which must exit 0; every finding names file:line and the fix.

**What it never touches.** `tech-stack.md`, `coding-standards.md`, scopes, or any content derived from
your code or your intake answers - those go through the `CONFLICT` queue with you deciding, never a
silent overwrite.

## `/code-graph`

**What it does.** Maintains the repo's module-boundary map, which answers one question
deterministically: does the code import across a module line that nobody agreed to? Two files back
it: `docs/context/code-graph.md`, **committed** - one row per module with its owner, the modules it
depends on and the modules that depend on it, and that list *is* the set of allowed cross-module
edges - and `.claude/state/code-graph.json`, gitignored machine state (modules, files per module,
edges with reference counts, module owner matched from the roster's scopes) that
`guard-agent-scope`, `/new-task` and the harness graph read. It draws no picture. Ships on a repo with
the code purpose.

**What keeps it honest without anyone reading it.** The non-blocking `graph-stale` hook runs
`code-graph.py --file` on every source edit and names, once, any cross-module import the map does not
list, on the edit that adds it. `python .claude/scripts/code-graph.py --check` exits 1 when the code
has an edge the map lacks; run it in review or CI, and `/board-audit` treats a failure as a finding.

**When to reach for it.** When `--check` fails, before dispatching or accepting a task that touches a
cross-module edge, or any time an agent needs "what else calls this module" answered without a
full-tree read.

**Worked example.**

```text
/code-graph
```

```text
python .claude/scripts/code-graph.py --check
  NEW EDGE  billing -> notifications (billing/invoice.py imports notify_customer)
This is either a missing interface or a boundary violation. Remove the import, or accept it.

Accepted: python .claude/scripts/code-graph.py
  14 modules, 212 files, 38 import edges.
git diff docs/context/code-graph.md
  billing: depends on  + notifications
```

**What it never does.** Accept an edge for you. Each new edge is a decision, not a refresh: the
rebuild is what accepts it, and the diff of the committed map is what review approves. Edges are
static imports resolved to repo paths - relative paths, workspace package names (`package.json`,
`go.mod`, `Cargo.toml`), Python modules that exist on disk, and the `@/` and `~/` aliases - so imports
assembled at runtime, other path aliases and C# `using` are not seen. A missing edge is absence of
evidence, not evidence of isolation; for "who uses this symbol", grep is still the tool. After a
rebuild it refreshes `.claude/state/harness-graph.json` (`harness-graph.py --html`), since module
owners feed into the harness graph.

**How agents use it.** The orchestrator reads the target module's row before a dispatch: its "Used
by" list is the blast radius the brief names. A dev agent does not need to read it; the hook speaks up
when an edit crosses a line the map does not list, and the agent then stops and reports instead of
shipping the edge.

**Engine.** Defaults to the stdlib static extractor in `.claude/scripts/code-graph.py` - zero install.
If a GitNexus/codegraph MCP server (or a comparable code-index tool) is available in the session, it
may replace the extraction for richer call-level edges; the file contract does not change either way,
so nothing downstream cares which engine ran.

## `/docs-graph`

**What it does.** Checks DOCS traceability: which document defines each requirement, decision or task
ID, who references it, and which IDs are orphans. It is the documentation twin of the code graph and
answers a different question - traceability, not dependency. It draws nothing and writes no Markdown:
it prints the doc, ID and edge counts and the orphan-ID list, which is the part anyone acts on, and
writes `.claude/state/docs-graph.json` (every ID, the document that defines it, every document that
references it) for a query such as "which documents mention FR-12". It is not rebuilt automatically;
run it after editing documents that define or cite IDs.

**When to reach for it.** After any spec edit, when `spec-guardian` needs to check a diff's claimed
requirement IDs against the graph, or when the orchestrator wants the unscheduled-requirement backlog
(orphan IDs).

**Worked example.**

```text
/docs-graph
```

```text
python .claude/scripts/docs-graph.py --check
  42 docs, 118 IDs, 96 edges, 3 orphan(s)
Orphans: FR-017 (defined in 05, no task references it), BR-009, ADR-0007 - unstarted work or dead references.
```

`--check` exits 1 when any orphan exists, which is how an edit that broke traceability is caught. Each
orphan is reported by name and as one of two things: unstarted work (a requirement no task or other
document references yet) or a dead reference (an ID cited once, defined nowhere).

## `/skill-wire`

**What it does.** Maps a skill installed in `.claude/skills/` - or created here with `/new-skill` - to
one roster seat. Wiring is a capability decision, so it gets the `/agent-permissions` shape: read the
skill and the seat, re-run the mandatory content review (every file, at wire time - an
`npx skills update` can have changed the text since install; for a plugin skill, the whole plugin
bundle), check the scope actually fits the seat's role, show the diff, and record the wire in
`docs/context/tool-changelog.md`. The change itself is one name added to the seat's `skills:`
frontmatter, which preloads the skill's full content at every spawn - so only a skill the seat uses on
most runs is worth preloading, and a skill with `disable-model-invocation: true` cannot be preloaded
and is refused. Discovery and install criteria live in the bootstrap skill's
`reference/skill-discovery.md`: installs, publisher, skills.sh audit status, and a mandatory read of
the skill's files before anything is trusted. After the wire, `skill-check.py` must no longer report
the skill as an orphan.

**When to reach for it.** Right after installing a skill from [skills.sh](https://www.skills.sh/)
(`npx skills add <owner/repo>@<skill>`) or creating one with `/new-skill`, or when a seat's work keeps
needing a capability an already-installed skill provides.

**Worked example.**

```text
/skill-wire pdf-processing qa-test
```

```text
Reading .claude/skills/pdf-processing/SKILL.md and .claude/agents/qa-test.md...
Content review: 3 files read, no config-edit or exfiltration instructions found.
Scope: report parsing fits qa-test's artifact checks. Diff:
  + skills: pdf-processing
Apply? [records to docs/context/tool-changelog.md]
```

**What it refuses.** A skill whose content instructs `.claude/`, `settings.json`, or hook edits is
wired to no seat, ever. Reviewers get read-only skills only. Only the orchestrator may hold a
skill that finds or installs other skills. Workflow knowledge stays in the skill: the wire adds a
name, it never copies the steps into the agent body. Every wire is recorded - an unrecorded wire
fails the quality gate.

## `/new-skill`

**What it does.** Decides whether a recurring workflow earns a project skill and, only if it does,
creates it. It is the last resort of one flow: find an existing skill (`reference/skill-discovery.md`),
or create one here, then wire it with `/skill-wire`. It first sorts the content into its proper home -
a fact every session needs belongs in `CLAUDE.md`/`AGENTS.md`, a path constraint in a path-scoped
rule, a procedure started by name in a command, a role in an agent definition, a deterministic check
in a script - and checks `.claude/skills/` for an existing skill to extend. It then asks, with
`AskUserQuestion`, putting the workflow, the evidence it recurs and what "measurably better" will
mean, and creates nothing without an explicit yes. On a yes it copies `.claude/templates/skill/` to
`.claude/skills/<name>/`, fills it (a description that leads with the use case and names the
neighbouring skill that owns the adjacent job, a body with fixed, guided and open steps, references,
and a `scripts/validate.py` whose exit code is "done"), writes the six trigger cases under
`evals/trigger-cases.md`, lints with `python .claude/scripts/skill-check.py --skill
.claude/skills/<name>`, and runs `/skill-wire` for each seat that needs it.

**When to reach for it.** A workflow keeps being re-explained across tasks, nothing published fits it,
and it is too large or too conditional to sit in context all the time. Refusing to create one is a
normal outcome.

**Worked example.**

```text
/new-skill release-notes docs-writer
```

```text
Home check: a procedure started by name once per release is a command, not a skill - unless it
carries reference material the model gets wrong without it.
Evidence it recurs: 4 release-note rewrites in the session logs. Proposed: a skill. Create it? [yes/no]
```

**What it refuses.** Creating a skill nobody agreed to, a second copy of an existing skill kept in
sync by hand, a lint result with anything left but `orphan` before the wire, and an unwired skill left
behind: it costs its description in every session and serves nobody. Removing one is also its job -
unwire it, delete `.claude/skills/<name>/`, and record why in `docs/context/tool-changelog.md`.

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
docs-graph --check: 0 new orphans. spec-check --write: FR-22 awaits confirmation.
```

**What it writes.** The mapped-to spec section(s), one row in `13-revision-history.md` per ingest
(date, source, sections touched, IDs added/changed, who approved any conflict), and - where a harness
exists - the ripple targets: `docs/context/glossary.md`, `docs/context/business-rules.md`, the owning
dev agent's FR list, and the board (a new FR with no owning module becomes a Pending task, never a
silent seat assignment). It then checks traceability (`python .claude/scripts/docs-graph.py --check`, whose orphan IDs are the
ingest's loose ends), regenerates the confirmation sheet and the agent index with
`python .claude/scripts/spec-check.py --write` (a new or changed FR appears with an empty decision,
the cue to send it back for confirmation), and records the ingest itself in
`docs/context/tool-changelog.md`.

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
Recorded in 13-revision-history.md. docs-graph --check: 0 new orphans (both IDs still resolve, as
Withdrawn).
```

**What it writes.** One row in `13-revision-history.md` (what was retracted, why, which IDs went
`Withdrawn` or converted to `OI-nn`, who decided), and - where a harness exists - the ripple: the
owning dev agent's FR list drops withdrawn IDs, Active tasks implementing them go `Blocked` with
`human_gate: requirement withdrawn` (a human decides whether the work stops, never a silent
deletion), and glossary terms only the retracted source defined are marked disputed. Checks
traceability the same way `/spec-ingest` does, runs `spec-check.py --write` so withdrawn FRs leave
the confirmation sheet and keep their entry in `index.json` with the new status, and records the
retraction in `docs/context/tool-changelog.md`.

**What it refuses.** Reusing a withdrawn ID - a retracted `FR-nn` keeps its number, marked
`Withdrawn`, and the next requirement takes a fresh one. Deleting a claim outright just because its
source disappeared - it becomes a tracked open issue instead.

These two ship with the `spec-builder` skill, not `harness-bootstrap` - a repo that only bootstrapped
the harness does not have them until `spec-builder` is also installed on it.

## Quick reference

| Command | Changes | Confirmation |
|---|---|---|
| `/board-audit` | Nothing - read-only (runs `board-check.py` first) | N/A |
| `/harness-tune` | Control-level dials chosen from the run record: deploy rights, destructive-command posture, spawn allowlist, caps, model and effort, review-gate scope, agent-history detail | At most four ranked changes, asked once; diff shown, each change proved by a check, `harness-check.py` last |
| `/harness-toggle` | Enables/disables one rule, command, hook, or agent seat; updates `.claude/disabled.json` and the harness graph | HARD items need a typed confirm phrase; SOFT items and every agent seat need `--yes` |
| `/agent-permissions` | One tool on one seat | Diff shown, yes required (invariant violations refuse instead) |
| `/harness-update` | Re-syncs `.claude/` with the current skill version and codebase, re-ports to the recorded targets | `CONFLICT` queue, resolved by hand; `harness-check.py` last |
| `/code-graph` | Rebuilds the committed module-boundary map `docs/context/code-graph.md` and `.claude/state/code-graph.json` (code repos) | Each new edge is a decision; the diff of the map is what review approves |
| `/docs-graph` | Prints the orphan-ID list and writes `.claude/state/docs-graph.json` (no Markdown, no picture) | None - derived file only; `--check` exits 1 on any orphan |
| `/skill-wire` | One installed or local skill onto one seat's `skills:` list | Diff shown, yes required; content re-review at wire time, invariant violations refuse |
| `/new-skill` | A new project skill under `.claude/skills/`, its trigger cases, a lint run | An explicit yes before anything is created; refusing is a normal outcome |
| `/spec-ingest` (`spec-builder`) | Spec section(s), `13-revision-history.md` row, glossary/business-rules/board ripples | Conflicts shown via `AskUserQuestion`; IDs appended, never renumbered |
| `/spec-retract` (`spec-builder`) | Corrects or converts spec content to `OI-nn`, `13-revision-history.md` row, downstream ripples | Blast radius shown before any change; withdrawn IDs never reused |

## The three invariants that hold across all of them

However you reach them - `/harness-tune`, `/agent-permissions`, or a hand edit reviewed like any
other change - three things do not move:

1. **Reviewers never gain write access.** `code-reviewer`, `security-reviewer` (or `reviewer`, when
   merged under `solo_review`), `spec-guardian` and `checker` stay read-only gates.
2. **Only the orchestrator spawns.** One dispatch point, enforced by the scaffolder's build check and
   by `guard-agent-spawn`.
3. **The code-review gate cannot be removed**, only rescoped to which paths trigger it.

See also: [`roster.md`](../harness-bootstrap/reference/roster.md) for what each seat is for,
[`cost-model.md`](../harness-bootstrap/reference/cost-model.md) for what a tuning costs, and
[`task-control.md`](../harness-bootstrap/reference/task-control.md) for the board mechanics
`/board-audit` checks against.

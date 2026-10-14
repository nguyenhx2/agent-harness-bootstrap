# Flows

**English** · [日本語](FLOWS.ja.md)

Visual reference for the two skills in this repo: `spec-builder`, which produces the requirements
contract, and `harness-bootstrap`, which builds the machine that implements it.

Every diagram below is Mermaid and renders natively on GitHub. The claims in them are taken from the
source: `harness-bootstrap/SKILL.md`, its `reference/` docs, `scripts/scaffold.py`,
`assets/manifest.json`, `assets/claude/settings.json`, `assets/claude/hooks/README.md`,
`spec-builder/SKILL.md`, and `benchmark/RESULTS.md`. Section 7 is the exception - a written command reference rather than a
diagram, placed here because it documents the commands diagram 4's sequence actually calls.

## Legend

The colours carry meaning: **green is free, purple is billed**. A step is green when a script does it
deterministically for zero tokens, and purple when a model has to think about it. `harness-bootstrap`
moves as much of the work as possible from purple to green: the assets are real files copied by
`scaffold.py`, not 1,300 lines of prose for a model to retype.

```mermaid
flowchart LR
    D["Deterministic / script<br/>no model, no tokens"]
    M["Model / judgment<br/>this costs tokens"]
    H["Human / user<br/>decisions and confirmations"]
    G["Guardrail / blocking<br/>hooks, gates, denials"]
    A["Artifact / file<br/>what lands on disk"]

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef hum fill:#1D3557,stroke:#0B1B2B,stroke-width:1px,color:#A8DADC
    classDef gate fill:#9D0208,stroke:#370617,stroke-width:1px,color:#FFBA08
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class D det
    class M mod
    class H hum
    class G gate
    class A art
```

Mermaid applies `classDef` to flowcharts only, not to sequence diagrams. The two sequence diagrams
below therefore carry the same semantics in their prose and notes rather than in fills.

## 1. Overall system flow - how the two skills relate

`spec-builder` writes the contract; `harness-bootstrap` builds the machine that implements it. They
are separate skills because they answer different questions: *what must be true* versus *who builds
it, under what guardrails, at what cost*. The decision point is whether `docs/specs/` already holds a
requirements set. If it does, go straight to `harness-bootstrap`. If it does not, either run
`spec-builder` first, or bootstrap with a single `app-dev` and register a task to split it once
modules emerge. `harness-bootstrap` does not require specs to exist; it fields a smaller roster when
they do not. When intake finds no specs it invokes `spec-builder` through the `Skill` tool rather than
only noting the gap, and the handoff carries the confirmed `purpose_*` flags into spec-builder's
`vars.json`, so the purpose is asked once across both skills and a repo that ships no code gets
spec-builder's light contract.

```mermaid
flowchart TD
    START(["Repo to be made agent-ready"])
    Q{"Does docs/specs/<br/>hold a requirements set?"}

    SB["spec-builder<br/>elicit, scaffold selective sections<br/>(6 core always + up to 8 optional), fill"]
    SPECS[/"docs/specs/ 01-13<br/>the requirements contract"/]

    HB["harness-bootstrap<br/>analyze, purpose, roster, scaffold, wire"]
    HARNESS[/".claude/ + docs/ + AGENTS.md + CLAUDE.md<br/>the machine"/]

    NOSPEC["Bootstrap anyway:<br/>Preset S, one app-dev,<br/>registered task to split later"]
    RUN["/task-resume - orchestration runs"]

    START --> Q
    Q -->|"yes"| HB
    Q -->|"no, and requirements are unsettled"| SB
    Q -->|"no, and the user wants to start coding"| NOSPEC
    SB --> SPECS
    SPECS --> HB
    NOSPEC --> HB
    HB --> HARNESS
    HARNESS --> RUN

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef hum fill:#1D3557,stroke:#0B1B2B,stroke-width:1px,color:#A8DADC
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class SB,HB,NOSPEC mod
    class START,Q hum
    class SPECS,HARNESS art
    class RUN det
```

The dependency runs one way. `spec-builder` writes into a docs tree that `harness-bootstrap` creates,
so on a repo with no docs tree at all, `harness-bootstrap` runs first and `spec-builder` fills the
`docs/specs/` folder it made. Once section 03 (glossary) and section 05 (functional requirements) are
filled, `spec-builder` also seeds `docs/requirements/PRD-FR-NN-*.md`, `docs/context/glossary.md`, and
`docs/context/business-rules.md` - seeding, not duplicating: the spec section remains the source of
truth and the context files link back to it.

## 2. harness-bootstrap, end to end

Read it as three bands: a **purple** analysis and decision phase where a model is required, a
**green** scaffolding step where a script does the bulk copying for free, and a second **purple**
phase for the things no template can know - the routing table, each dev agent's scope, the real deny
commands. The repo's **purpose** (code, research, strategy, docs - one or more) is the first intake
question and decides the base roster and the verification, so a research or documentation repo is
not handed a test suite and a code review gate. The `CONFLICT` branch out of the scaffolder is not an error path: it is the brownfield
reconciliation queue, and it is why the scaffolder never overwrites a file the user wrote.

```mermaid
flowchart TD
    START(["User invokes /harness-bootstrap"])
    MODE{"Mode"}

    GF["Greenfield<br/>empty or near-empty repo"]
    BF["Brownfield<br/>source exists, agents will modify it"]
    AU["Audit<br/>agents analyze, a human applies fixes"]

    ANALYZE["Codebase analysis - MANDATORY<br/>stack, modules, data layer, integrations,<br/>conventions, risky ops, existing .claude/, git reality"]
    INV[/"Inventory Report<br/>mapping tables: modules to dev agents,<br/>conventions to rules, risky ops to deny and hooks"/]
    CONFIRM{"User confirms<br/>or corrects the report"}

    INTAKE["Intake: the purpose first, then only what that purpose needs.<br/>One pre-answered questionnaire, at most two AskUserQuestion calls,<br/>asked in the language the user wrote in.<br/>Brownfield: pre-fill from evidence, ask only what code cannot decide"]
    NOSPECS["No specs yet?<br/>invoke spec-builder via the Skill tool,<br/>carrying the confirmed purpose flags"]
    TOOLS["Detect + confirm target tools<br/>ranked evidence: only settings.json hooks, .cursor/<br/>and .codex/ own formats are Strong - CLAUDE.md and<br/>.claude/agents are Weak, AGENTS.md alone asks.<br/>Answer persists as target_cursor / target_codex"]
    PLAN{"One-screen setup plan:<br/>created / kept / modified,<br/>roster with model + effort.<br/>User confirms"}

    ROSTER["Pick the roster<br/>the purpose decides the base: code gets the review gate and dev agents<br/>(preset S/M/L); research, strategy and docs get 3 to 5 seats with a checker.<br/>Explicit model, effort, tools and maxTurns on every agent"]
    SKILLS["Skill discovery and install, when the questionnaire asks for it<br/>trust rubric + mandatory content read, yes per skill.<br/>/skill-wire maps a skill to a seat; /new-skill when nothing fits"]
    OS["Detect the dev OS<br/>Windows to .ps1, macOS or Linux to .sh<br/>sets the windows / posix flag"]
    VARS[/"vars.json<br/>vars + flags: one or more purpose_code / research / strategy / docs,<br/>ui, db, db_engineer, db_seeder, ai, audit, tdd, ddd, light, unit, e2e, tests,<br/>deploy_ask, long, solo_review, merge_gate, hooks_strict, terse, rtk, pr_cli,<br/>target_cursor, target_codex, exactly one of windows / posix<br/>+ modules: one CLAUDE.md per module, 40 lines at most"/]

    DRY["scaffold.py --dry-run"]
    SCAFFOLD["scaffold.py<br/>deterministic copy of assets/"]
    HCHECK["harness-check.py --stage scaffold<br/>every seat, hook, rule, command and skill link resolves"]

    ADDED[/"ADDED<br/>file did not exist"/]
    KEPT[/"KEPT<br/>exists and is byte-identical"/]
    CONFLICT[/"CONFLICT<br/>exists and differs - not written"/]
    MISSINGVAR["Unresolved {{VAR}}<br/>exit 1, nothing written"]

    RECONCILE["Reconcile by hand:<br/>keep / adapt / add / flag.<br/>Never clobber what the user wrote"]

    GAPFILL["Model-authored gap-fill<br/>orchestrator routing table, dev-agent scopes,<br/>tech-stack.md, coding-standards.md, git-workflow.md,<br/>settings.json allow/deny for the real stack, .env.example"]
    WIRE["Orchestration wiring<br/>master-plan index table, Phase 1 seeded from the<br/>analysis gap list, AGENTS.md entry point,<br/>CLAUDE.md as a thin @AGENTS.md import"]

    GATE{"Quality gate<br/>structure / cost and context / safety /<br/>governance / grounding / handoff"}
    SMOKE["Smoke-test the loop: a real task file,<br/>master-plan row, session-log row, /task-resume,<br/>board-check.py exits 0"]
    MAPS["Build the maps: code-graph.py (module-boundary map),<br/>docs-graph.py --check (orphan IDs),<br/>harness-graph.py --html (the wiring)"]
    PORT["Port to the RECORDED targets<br/>port.py --tool cursor / codex / all:<br/>.cursor/rules + adapter, .codex/hooks.json.<br/>/harness-update re-reads them, never re-asks"]
    DONE(["Harness runs under orchestration"])

    START --> MODE
    MODE -->|"no source"| GF
    MODE -->|"source, agents may write"| BF
    MODE -->|"source, agents never write"| AU

    GF --> INTAKE
    BF --> ANALYZE
    AU --> ANALYZE
    ANALYZE --> INV --> CONFIRM
    CONFIRM -->|"corrections override findings"| ANALYZE
    CONFIRM -->|"confirmed"| INTAKE

    INTAKE -->|"no docs/specs/"| NOSPECS --> INTAKE
    INTAKE --> TOOLS --> PLAN
    PLAN -->|"changes requested"| INTAKE
    PLAN -->|"confirmed"| ROSTER
    ROSTER --> SKILLS --> OS --> VARS
    VARS --> DRY --> SCAFFOLD

    SCAFFOLD --> ADDED
    SCAFFOLD --> KEPT
    SCAFFOLD --> CONFLICT
    SCAFFOLD --> MISSINGVAR
    SCAFFOLD --> HCHECK
    MISSINGVAR -->|"add the var, re-run"| VARS

    CONFLICT --> RECONCILE
    ADDED --> GAPFILL
    KEPT --> GAPFILL
    RECONCILE --> GAPFILL

    GAPFILL --> WIRE --> GATE
    GATE -->|"a check fails"| GAPFILL
    GATE -->|"all green"| SMOKE --> MAPS --> PORT --> DONE

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef hum fill:#1D3557,stroke:#0B1B2B,stroke-width:1px,color:#A8DADC
    classDef gate fill:#9D0208,stroke:#370617,stroke-width:1px,color:#FFBA08
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class ANALYZE,INTAKE,NOSPECS,TOOLS,ROSTER,SKILLS,OS,GAPFILL,WIRE,RECONCILE mod
    class DRY,SCAFFOLD,HCHECK,SMOKE,MAPS,PORT det
    class START,MODE,CONFIRM,PLAN,GF,BF,AU,DONE hum
    class GATE,MISSINGVAR gate
    class INV,VARS,ADDED,KEPT,CONFLICT art
```

Three points from the diagram:

- **Mode is chosen first, and it is not about size.** If agents will never modify the source and a
  human applies every fix, the mode is audit however much code exists; otherwise any source code at
  all means brownfield.
- **The Inventory Report gates everything.** In brownfield and audit it is mandatory, it must be
  shown to the user, and its mapping tables are what turn a generic template into a description of
  this specific codebase. No file is generated before it is confirmed.
- **CONFLICT is a queue, not a failure.** The scaffolder skips those files, prints them, and exits 0.
  Only an unresolved `{{VAR}}` makes it exit non-zero, because a placeholder shipped into a live rule
  file matches nothing and fails silently.

### 2a. Where each artifact comes from, and how the artifacts hold each other

The flowchart above is the procedure. The picture below is the *derivation*: which source each
generated file traces back to - the codebase, the specs, or an intake answer - and, once generated,
how the pieces rein each other in. Read the top panel left to right, and the bottom panel as a ring.

<p align="center">
  <img src="assets/generation-and-constraint.svg" alt="Generation and mutual constraint: three sources converge into vars.json and scaffold.py, and the generated agents, rules, board and hooks then hold each other in check" width="820">
</p>

Two claims it makes that the flowchart above does not. First, the model authors only what cannot be
templated: the routing table, each dev agent's scope, and the three project-specific rules
(`tech-stack`, `coding-standards`, `git-workflow`). Everything else is a file copy. Second, no seat is
trusted - the orchestrator routes but has no Write outside `docs/` and `.claude/`, the reviewers gate
but hold no `Edit` or `Write`, the board records what the session log can prove, and the hooks bind
every agent including the one dispatching them.

## 3. The scaffolder in detail

`scripts/scaffold.py` is stdlib-only, has no dependencies, and is what makes the skill cheap: it
copies real asset files instead of asking a model to regenerate them. It walks `assets/manifest.json`
once, entry by entry. Everything it does is mechanical, which is why the diagram is green apart from
the red stops where it refuses to guess.

```mermaid
flowchart TD
    START(["python scripts/scaffold.py --target REPO --vars vars.json"])
    LOAD["Load vars.json: vars + flags + modules<br/>Load assets/manifest.json"]
    NOMAN["manifest or asset missing<br/>ScaffoldError, exit 2"]
    VALID{"Flag set valid?<br/>known names, exactly one OS flag,<br/>no contradiction, code-only flags need purpose_code"}
    BADFLAGS["Print each problem<br/>exit 1, nothing written"]
    DERIVE["Derive: no purpose means purpose_code,<br/>checker follows any non-code purpose,<br/>HOOK_RUNNER and HOOK_EXT follow the OS flag"]
    LOOP{"Next manifest entry"}

    ONLY{"--only prefix set<br/>and src does not match?"}
    FLAGS{"Flag filter<br/>when: AND over flags<br/>when_any: OR over flags<br/>when_not: skip if any is set"}
    SKIP[/"SKIPPED by flags<br/>e.g. frontend.md without 'ui',<br/>*.ps1 without 'windows'"/]
    OFF[/"DISABLED<br/>listed in .claude/disabled.json,<br/>never resurrected"/]

    READ["Read the asset<br/>subst: false to copy bytes verbatim"]
    BLOCKS["Resolve conditional blocks<br/>{{#IF_X}} kept if flag X is set<br/>{{^IF_X}} kept if flag X is NOT set<br/>repeated passes, innermost first"]
    SUBST["Substitute {{VAR}} from vars<br/>dest path is substituted too.<br/>A missing key is recorded, not blanked"]

    EXISTS{"Destination exists?"}
    SAME{"Bytes identical<br/>to the payload?"}

    ADDED[/"ADDED<br/>queued for writing, mkdir parents,<br/>chmod +x if 'exec'"/]
    KEPT[/"KEPT<br/>already identical - untouched"/]
    CONFLICT[/"CONFLICT<br/>exists and differs.<br/>NOT written unless --force"/]
    MERGED[/"MERGED<br/>settings.json only: hook registrations<br/>this version ships are added, nothing removed"/]

    MODS["modules in vars.json:<br/>render module-CLAUDE.md into each module,<br/>never over an existing CLAUDE.md,<br/>over 40 lines fails the run"]
    REPORT["Report: ADDED / KEPT / CONFLICT /<br/>MERGED / DISABLED / SKIPPED + summary counts"]
    MISS{"Any unresolved {{VAR}}<br/>or module problem?"}
    FAIL["Print the missing keys per file<br/>exit 1 - nothing was written"]
    WRITE["Write the queued files"]
    SPAWN{"More than one seat<br/>holds the Agent tool?"}
    WIRED{"Controls installed but<br/>not wired?"}
    HCHECK{"harness-check.py --stage scaffold<br/>finds a link that does not resolve?"}
    BAD["Print file and line, exit 1"]
    OK["exit 0<br/>CONFLICTs are listed, not fatal"]
    QUEUE["Brownfield reconciliation queue:<br/>keep / adapt / add / flag, by hand"]

    START --> LOAD
    LOAD -->|"not found"| NOMAN
    LOAD --> VALID
    VALID -->|"no"| BADFLAGS
    VALID -->|"yes"| DERIVE --> LOOP
    LOOP --> ONLY
    ONLY -->|"yes, skip"| LOOP
    ONLY -->|"no"| FLAGS
    FLAGS -->|"flags not satisfied"| SKIP --> LOOP
    FLAGS -->|"wanted, but toggled off"| OFF --> LOOP
    FLAGS -->|"wanted"| READ
    READ --> BLOCKS --> SUBST --> EXISTS
    EXISTS -->|"no"| ADDED --> LOOP
    EXISTS -->|"yes"| SAME
    SAME -->|"yes"| KEPT --> LOOP
    SAME -->|"no"| CONFLICT --> LOOP
    CONFLICT -.->|"settings.json"| MERGED
    LOOP -->|"manifest exhausted"| MODS --> REPORT
    REPORT --> MISS
    MISS -->|"yes"| FAIL
    MISS -->|"no"| WRITE --> SPAWN
    SPAWN -->|"yes"| BAD
    SPAWN -->|"no"| WIRED
    WIRED -->|"yes"| BAD
    WIRED -->|"no"| HCHECK
    HCHECK -->|"yes"| BAD
    HCHECK -->|"no"| OK
    CONFLICT -.-> QUEUE

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef hum fill:#1D3557,stroke:#0B1B2B,stroke-width:1px,color:#A8DADC
    classDef gate fill:#9D0208,stroke:#370617,stroke-width:1px,color:#FFBA08
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class LOAD,VALID,DERIVE,LOOP,ONLY,FLAGS,READ,BLOCKS,SUBST,EXISTS,SAME,MODS,REPORT,MISS,WRITE,SPAWN,WIRED,HCHECK,OK det
    class START hum
    class NOMAN,BADFLAGS,FAIL,BAD gate
    class SKIP,OFF,ADDED,KEPT,CONFLICT,MERGED art
    class QUEUE mod
```

The scaffolder refuses three decisions on purpose:

- It **never overwrites.** An existing file that differs is reported and left alone, because on a
  brownfield repo the differing file is usually something a human wrote. Use `--force` for files you
  have explicitly decided to replace. The one additive exception is `settings.json`: a hook this
  version ships that the file does not register yet is added (reported as `MERGED`), and nothing you
  wrote is changed or removed.
- It **fails on an unresolved variable** rather than writing a literal `{{DB_RESET_CMD}}` into a deny
  rule that would then never match anything, and it writes nothing at all when it does, so a failed
  run cannot leave a half-built harness.
- It **refuses an incoherent harness.** A flag set that contradicts itself, a second seat holding
  `Agent`, a control installed but not wired, and any link `harness-check.py` cannot resolve each stop
  the run with the file and line to fix.

Re-running on an unchanged repo is idempotent: everything comes back `KEPT`, nothing is clobbered.

## 4. One feature, end to end through the generated harness

This is the **Guarded** flow - what the generated `.claude/` folder runs when a change spans two or
more domains, or touches schema, auth, money, a public contract, a migration, a deploy, or personal
data. It is not what every change runs. The tier table in the generated `AGENTS.md` has four rows
and decides which one a request is, before anything is dispatched: **Inline** (a question, a lookup,
a small edit - the main session does it itself, with no subagent and no task file), **Direct** (one
module, reversible - straight to the agent that owns it, no orchestrator, no task file), **Standard**
(one domain or several files - the owning agent, with a task file only when the work must survive a
compacted session) and **Guarded**, the flow below. Direct and Standard dispatches carry `TIER: direct`
or `TIER: standard` in the prompt, which `guard-agent-spawn` accepts in place of a `TASK-NNN` for a
write-capable seat; Guarded work still needs a registered task. A planning pass costs more than a
small change, so a heavier tier than the change needs is a defect. For a long Guarded mission the
session can be started as the orchestrator itself (`claude --agent orchestrator`) instead of
dispatching it.

Note where the gate sits below: **once, on the branch, at the pull-request boundary** - not after
each agent. A reviewer dispatched per agent re-reads the same files once per agent and reports the
same findings each time. The same holds for tests: verification is per feature, not per step, so
while building a dev agent runs only the tests that touch what it changed, and the full suite runs
once at the gate. What the gate runs is not a fixed list: `verify-plan.py` reads the branch diff and
prints each gate as required or skipped with the reason (a docs-only change needs the secret scan and
nothing else), and the verification ledger remembers what already passed. A gate that passed on these
exact bytes is cited rather than repeated, one whose files changed since is narrowed to the changed
paths, and `guard-agent-spawn` refuses a re-run, a third review round, an identical brief, or a
dispatch past the task's budget (`dispatch_budget`, default 24). Task state moves only through
`task.py` - `new`, `move`, `log`, `gate`, `checkpoint`, `attempt` - which writes the task file, its
folder and its board row together and reads the row back; `guard-board` blocks a hand edit of a task
row. In cost terms: the
orchestrator, the reviewers, and the debugger are Opus seats; the dev agents, `qa-test`, and
`spec-guardian` are Sonnet; the mechanical seats (`history-tracker`, `db-seeder`) are Haiku at `low`
effort. The hooks cost nothing, being shell scripts rather than a model, and they are the only
participant here that can say no.

The sequence below shows the default roster (`tests` chosen, split reviewers). Two flags reshape it:
without `tests`, `qa-test` and its gate do not exist and the diagram's "Run the suite" step is
skipped; with `solo_review` set, `code-reviewer` and `security-reviewer` collapse into one merged
`reviewer` seat and the parallel `par` block below becomes a single pass instead of two.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Orch as orchestrator
    participant Board as task board<br/>docs/tasks/
    participant Spec as spec-guardian
    participant Dev as domain-dev
    participant QA as qa-test
    participant CR as code-reviewer
    participant SR as security-reviewer
    participant Plan as verify-plan.py<br/>+ verification ledger
    participant Hooks as hooks<br/>.claude/hooks/

    User->>Orch: Mission: implement FR-07
    Orch->>Board: Session-start scan: task.py resume and task.py check<br/>human_gate rows first, then Active and Blocked
    Board-->>Orch: Unfinished work first - otherwise accept the mission

    Note over Orch,Board: Registration. A registered-but-not-started task is Planned,<br/>and a Planned file lives in active/ - pending/ means parked.
    Orch->>Board: task.py new: TASK-NNN from docs/templates/TASK.md<br/>status: Planned in frontmatter AND in the master-plan row,<br/>written together and read back
    Orch->>Board: task.py log: the first session-log row

    Orch->>Spec: Verify scope and acceptance criteria BEFORE any implementation,<br/>once per mission. The FR must be Confirmed in docs/specs/index.json
    Spec-->>Orch: Contract locked, or drift found and escalated
    Note over Spec: Read-only. No Bash - it has nothing to run.
    Orch->>Board: task.py move TASK-NNN Active - file, folder and row together

    Orch->>Dev: Dispatch: TASK code, FR/PRD, target files,<br/>acceptance criteria, isolated worktree + branch
    Note over Dev: Design first, in the task file. Tests ship with the code - DDD default.<br/>Under opt-in TDD the failing test comes first.
    Dev->>Hooks: Edit / Write
    Hooks-->>Dev: PreToolUse: protect-adr, protect-secrets, guard-board - allowed (exit 0)
    Hooks-->>Dev: PostToolUse: specs-reminder, and graph-stale names any cross-module<br/>import the module-boundary map does not list

    Dev->>Hooks: Bash: git commit (on the default branch)
    Hooks-->>Dev: BLOCKED. guard-main-commit exits 2:<br/>"do not commit directly to main - branch first"
    Note over Hooks: A hook that blocks you is a rule you were about to break.<br/>Never route around it with a shell equivalent.
    Dev->>Hooks: Bash: git checkout -b feat/... then git commit
    Hooks-->>Dev: check-commit-msg validates Conventional Commits - passes (exit 0)
    Note over Dev: While building: only the tests touching what changed,<br/>never the full suite per step
    Dev->>Board: task.py log per completed unit, task.py checkpoint:<br/>done, next step, files touched
    Dev-->>Orch: Implementation complete (a CLAIM, not a fact)

    Orch->>Plan: /review-changes: verify-plan.py --base main --task TASK-NNN
    Plan-->>Orch: Each gate REQUIRED or skipped, with the reason.<br/>A gate that passed on these exact bytes is skipped with the ledger line to cite
    Orch->>Orch: /secret-scan on the diff - never skipped

    Orch->>QA: If required: run the full suite once - tests map 1:1 to the acceptance criteria
    Hooks-->>Orch: guard-agent-spawn reads the ledger first: refuses a re-run on content that passed
    QA-->>Orch: Green

    par Reviewers run in parallel, only the lenses the plan requires
        Orch->>CR: Review the diff
        CR-->>Orch: Pass / findings
    and
        Orch->>SR: Review secrets, PII, authz
        SR-->>Orch: Pass / findings
    end
    Note over CR,SR: Neither has Edit or Write. A reviewer that edits code<br/>has become a dev agent and lost its independence.
    Note over Orch,SR: At most two rounds. The second covers only the fix delta and only<br/>blocker and should-fix findings, and what remains goes to the user.

    Orch->>Board: task.py gate TASK-NNN gate pass or fail:<br/>one step writes the ledger line and the session-log row
    Note over Orch,Board: A gate counts as passed ONLY when that row exists.<br/>"All gates green" over a log with no reviewer rows is the classic failure.

    alt A gate has no logged row
        Orch->>Dev: Re-run the gate. The claim is not evidence.
    else Every gate is logged
        Orch->>Orch: Merge: one merger, serialized, against the LIVE mainline tip<br/>diff with three dots, union on shared lists, never --ours/--theirs
        Orch->>Board: Post-merge audit, task.py check: every task file's frontmatter<br/>status equals its board row, Done files and Done rows agree 1:1
        Orch->>Board: Outcome section, then task.py move TASK-NNN Done:<br/>frontmatter, board row and the active/ to done/ move in one step
    end

    Note over Orch: Close-out: remove the worktree, delete the merged branch,<br/>prune, and sweep out-of-repo scratch (gated, enumerated).
    Orch->>Board: No Active or Blocked tasks left in scope:<br/>terminal phase + a final MISSION COMPLETE session-log row (task.py log)
    Orch-->>User: Summary. Then the instance terminates rather than idling.
    Note over Orch,Board: Marker present + silent = finished, do NOT resume.<br/>No marker + silent = crashed, resume from file state.
```

The files are the truth and an agent's report is a claim. A gate is passed when the task file's
session log holds a row for it, not when an agent says "reviewed". Status lives in two places, the
task file's frontmatter and the master-plan row, with the file's folder following it, and
`task.py move` writes all three in the same step and reads the row back, because a merge that resolves a board collision by taking one side reverts a status flip with
no error at all. The hooks are the hard edge: `PreToolUse` fires before the tool runs, exit 2 blocks
it, and the message on stderr goes back to the model. The `MISSION COMPLETE` marker makes "finished"
distinguishable from "crashed" by a file check instead of a guess.

## 5. spec-builder

Same shape, different contract: read what the user brought, elicit what only a human knows, let the
script lay down the selected sections - a 6-file core always, plus up to 8 optional sections chosen
from what the input material actually contains - then spend model tokens on the content rather than
on the headings. The governing rule is
that **nothing is invented**. An unstated requirement becomes an assumption (AS-nn) or an open issue
(OI-nn) with a named owner, because a plausible invented requirement gets estimated, built, and
discovered in UAT. A repository whose product is not code (research, strategy, docs) takes a light
contract instead - README, 05, 11 and 13 only, each item an `FR-nn` with `Done when` criteria - picked
by the same `purpose_*` flags harness-bootstrap uses.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant SB as spec-builder<br/>the model
    participant Route as route_sources.py<br/>+ ingest.py
    participant Scaffold as scripts/scaffold.py
    participant Specs as docs/specs/
    participant Check as spec-check.py
    participant HB as harness-bootstrap

    User->>SB: Raw input: an idea, meeting notes, a transcript,<br/>an existing PRD, legacy docs, a codebase
    SB->>Route: Pick a reader per source
    Route-->>SB: The plan. Shown to the user first: file to reader,<br/>or UNREADABLE with the fix. An unreadable source becomes an OI-nn
    SB->>SB: Elicit - infer STRUCTURE, ask for DECISIONS
    SB->>User: AskUserQuestion, batches of at most 4:<br/>priorities, permission scope, NFR targets, volumes,<br/>security posture, output language
    User-->>SB: Answers. Anything unanswered becomes AS-nn / OI-nn.

    SB->>User: ONE gate: the FR list with proposed MoSCoW priorities, the roles,<br/>the open issues so far, and which optional sections the material justifies
    User-->>SB: Confirmed or corrected
    Note over SB,User: Everything from section 02 onward derives from this list.<br/>A wrong list costs every downstream section, selected or not.
    SB->>Specs: Record the selection in .sections.json:<br/>every optional section selected or excluded, with a reason

    SB->>Scaffold: vars.json - PROJECT_NAME, PROJECT_SLUG,<br/>PROJECT_PURPOSE, DOC_OWNER + purpose and section flags:<br/>stakeholders, flows, access, db, integration, ui, feasibility, design
    Scaffold->>Scaffold: --dry-run first. Refuses without .sections.json,<br/>or when it contradicts the flags
    Scaffold->>Specs: Write the core (README, 01, 03, 05, 07, 11, 13) always,<br/>plus each selected optional section (up to 8, including<br/>14-design-system) - headings, tables, Mermaid scaffolds,<br/>inline authoring notes. Flat, or per module with --module
    Scaffold-->>SB: ADDED / KEPT / CONFLICT. Exit 1 on an unresolved &#123 -&#123 -VAR&#125 -&#125 -.
    Note over Scaffold,Specs: Deterministic and free. The model does not retype the shape -<br/>CONFLICT is the reconciliation queue for a repo that already has specs.

    SB->>Specs: Fill section by section, in order - each depends on the last
    Note over SB,Specs: The three that carry the load:<br/>05 observable FRs, anchored, with BR-nn and a NEGATIVE acceptance case<br/>07 security NFRs, never "TBD" - an undecided value is an OI with an owner<br/>12 every FR gets Yes / Partial / No - "Partial" and "No" are the valuable output

    SB->>Check: spec-check.py --write
    Check->>Specs: Writes confirmation.md (the page a PO or client answers)<br/>and index.json (what agents read instead of whole documents)
    Check-->>SB: Unique IDs, checkable criteria on every live FR,<br/>open issues owned, derived files in step. Fix every FAIL
    SB->>SB: Traceability check - every FR from 05 appears in 12 (count both),<br/>every screen in 10 names an FR, every role in 06 exists in 03,<br/>every entity in 06 exists in 08, no blank cells, all links resolve
    SB->>User: Hand over the confirmation sheet with every OI, every AS,<br/>every Partial/No, and every NFR target that was proposed rather than received
    User-->>SB: yes / no / change per FR
    SB->>Specs: /spec-ingest folds each change in, Status: Confirmed on each yes,<br/>one revision row

    opt The docs workspace exists
        SB->>HB: Seed docs/requirements/PRD-FR-NN-*.md, docs/context/glossary.md,<br/>docs/context/business-rules.md - linking back, not duplicating
    end
    SB-->>HB: Handoff via the Skill tool, FR_LIST and GLOSSARY_SEED prefilled:<br/>the contract exists. Bootstrap the harness that implements it<br/>(dev agents clustered from the FR list), then /implement-fr.
```

The ordering is a discipline: the FR list is confirmed *before* anything else is written, and the
sections are filled in order because each depends on the last. The traceability check at the end is
mechanical - count the FRs in 05, count the rows in 12, they match - which is the kind of check a
model will skip unless it is written down as a gate. The confirmation sheet exists because a
product owner cannot correct an assumption nobody told them was made; the index exists so that a
task touching one FR loads one block, not the whole section. A change that leaves every promise on
the sheet intact needs no spec work, and one that adds behaviour inside an agreed FR needs one
appended criterion.

## 6. Context loading - why the harness is cheap

This is the mechanic behind the numbers in `benchmark/RESULTS.md`. A file in `.claude/rules/` with
**no `paths:` frontmatter** loads at launch, into every session of every agent, at the same priority
as `CLAUDE.md`. It is not a one-time cost, it is rent. Add `paths:` and the rule only enters context
when Claude actually touches a matching file.

```mermaid
flowchart TD
    subgraph ALWAYS["Always loaded - paid on every request, of every agent, forever"]
        CLAUDEMD[/"CLAUDE.md<br/>thin @AGENTS.md import + the Claude-specific surface"/]
        AGENTSMD[/"AGENTS.md<br/>the contract: rules, docs map, roster, commands, git"/]
        R1[/"00-overview.md"/]
        R2[/"agent-guardrails.md"/]
        R3[/"task-tracking.md"/]
        R4[/"conventional-commits.md<br/>governs commit MESSAGES, not files -<br/>no glob can ever scope it"/]
        R5[/"model-policy.md<br/>decides what may be sent where<br/>before any file is touched"/]
        BODY[/"The agent's own body<br/>one file per agent under .claude/agents/"/]
        SCHEMA[/"Tool schemas - one per entry in tools:<br/>omitting tools: inherits EVERY tool,<br/>including every MCP server on the machine"/]
    end

    TOUCH{"Claude touches a file"}

    subgraph LAZY["Lazily loaded - enters context only on a path match"]
        L1[/"code-quality.md - SOURCE_GLOBS"/]
        L2[/"performance.md - SOURCE_GLOBS"/]
        L3[/"security-privacy.md - SOURCE_GLOBS"/]
        L4[/"testing.md - TEST_GLOBS + SOURCE_GLOBS (flag tests)"/]
        L5[/"frontend.md - UI_GLOBS (flag ui)"/]
        L6[/"data-model.md - DB_GLOBS (flag db)"/]
        L7[/"docs-workflow.md - docs/**"/]
        L8[/"ddd.md - SOURCE_GLOBS (flag ddd)"/]
        L9[/"ip-compliance.md - SOURCE_GLOBS + DEP_MANIFEST_GLOBS"/]
        L10[/"model-tiers.md - .claude/agents/** and settings.json"/]
        L11[/"module CLAUDE.md - only when files in that module are read"/]
    end

    NEVER[/"assets/ - the hooks, commands, templates, agent bodies.<br/>NEVER enter the context window: scaffold.py copies them.<br/>The model reads SKILL.md + 9 reference docs, and nothing else."/]

    WINDOW["The agent's context window"]

    CLAUDEMD --> AGENTSMD
    ALWAYS --> WINDOW
    TOUCH -->|"src/**"| L1
    TOUCH -->|"src/**"| L2
    TOUCH -->|"src/**"| L3
    TOUCH -->|"*.test.ts"| L4
    TOUCH -->|"src/components/**"| L5
    TOUCH -->|"prisma/**"| L6
    TOUCH -->|"docs/**"| L7
    TOUCH -->|"src/**"| L8
    TOUCH -->|"package.json"| L9
    TOUCH -->|".claude/agents/**"| L10
    TOUCH -->|"src/billing/**"| L11
    LAZY -->|"only the matching rule"| WINDOW
    NEVER -.->|"never"| WINDOW

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef hum fill:#1D3557,stroke:#0B1B2B,stroke-width:1px,color:#A8DADC
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class CLAUDEMD,AGENTSMD,R1,R2,R3,R4,R5,BODY,SCHEMA art
    class L1,L2,L3,L4,L5,L6,L7,L8,L9,L10,L11 art
    class NEVER det
    class WINDOW mod
    class TOUCH hum
```

7 unconditional rules, ten path-scoped ones (two of the seven are flag-gated: `ai-governance.md` ships only with the `ai` flag and `output-style.md` only with `terse`). On the shipped asset set that is 23,047 bytes always
loaded against 62,365 bytes loaded on demand: **73% of the rule content is kept out of the default
session**, so the database agent no longer carries the frontend rules and the UI agent no longer
carries the migration-safety rules.

Three other levers sit in the same diagram:

- Guidance true of one module lives in that module's own `CLAUDE.md` (40 lines at most: owner, scope,
  local invariants, commands). Claude Code loads it only when it reads files there, so it costs
  nothing in a session that never touches the module.
- Every tool in an agent's `tools:` list ships its JSON schema on *every* request. Omitting `tools:`,
  and thereby inheriting every MCP server on the machine, is treated as a bug in the quality gate.
- Every file in the always-loaded band is prompt-cache prefix content, so a single `Generated: <date>`
  line in an agent body cold-misses that agent's cache on every future run. No generated file carries
  a timestamp.

## 7. Delivery commands, command by command

Diagram 4 is the procedure; this section is the per-command reference for everything it invokes,
plus the handful of planning and maintenance commands that don't fit a single sequence step.
`docs/TUNING.md` documents the commands that adjust the *harness's own posture* (plus the two
`spec-builder` commands that ripple a source into or out of `docs/specs/`). This section documents
the commands used during normal *feature delivery* - the ones a dev agent or the orchestrator runs
while building the product itself. Same shape as `TUNING.md`, terser, since these run far more often:
invocation, what it's for, what it does, what it writes, what it refuses, and when it ships.

### Registering and planning work

#### `/new-task <short-title>`

Creates a task file from the template and registers it on the master plan - but only for work the
user agreed to. It first asks whether the work was requested and whether it is bigger than the
paperwork (a typo, a rename, a one-line fix and a step inside work already registered are not tasks;
something noticed while doing something else is a finding to report, not a row), and refusing is a
normal outcome. Unless the user's own message already asked for it, it puts the proposal to them with
`AskUserQuestion` and creates the task only on an explicit yes. Registration is one command,
`python .claude/scripts/task.py new`, which allocates the next `TASK-NNN` across `active/`,
`pending/` and `done/`, fills `docs/templates/TASK.md`, sets `status: Planned`, adds the board row,
reads it back to confirm the write landed, and logs the first session-log row. `--requested-by`
records what was asked for (never `user` or an agent name) and at least two observable criteria are
required. With `--fr` the task links to an FR by criterion ID and `spec-check.py --write` refreshes
`docs/specs/index.json`. If `.claude/state/code-graph.json` exists it also seeds a "Relevant modules"
line (the owner's module plus everything with a direct dependency edge into it) so the dispatch brief
carries a blast-radius hint before any code is touched.

**Writes:** a new `docs/tasks/active/TASK-NNN-<slug>.md`, a new row in `master-plan.md`, the first
session-log row. **Refuses:** opening a task nobody asked for, reusing a task number or overwriting an
existing task file on a collision, fewer than two criteria, proceeding with no title (asks, then
stops). **Ships:** unconditional.

#### `/new-adr <decision-title>`

Creates an Architecture Decision Record from the template. Determines the next `ADR-NNN`, copies
`docs/templates/ADR.md`, and fills context, decision, options considered, and consequences -
including the negative ones, since "an ADR with no downside recorded is an advertisement, not a
decision record." Leaves `status: Proposed`; only the user flips it to `Accepted`.

**Writes:** a new `docs/architecture/decisions/ADR-NNN-<slug>.md`, a new row in that folder's
`README.md` index. **Refuses:** writing in anything but English, even on a non-English-docs project -
ADRs stay portable; editing an Accepted ADR at all, which is hook-enforced (`protect-adr`) rather
than a convention - a change of mind is a *new* ADR that supersedes the old one, and every other edit
must land before the accept flip, because the hook reads the on-disk status at flip time and blocks
everything after it. **Ships:** unconditional.

#### `/new-spec-section <section-number-or-name>`

Scaffolds a specification section following the project's standard BA structure. With no argument it
lists which standard sections `docs/specs/` is missing and asks. Dispatches `ba-analyst`, deriving
content from PRDs, the codebase, and the user's answers, and cross-links every FR to an ID,
acceptance criteria, and the use case it serves.

**Writes:** the new/filled `docs/specs/` section, a row in `docs/specs/13-revision-history.md`.
**Refuses:** inventing a requirement - an unanswered question becomes a recorded open question,
never a plausible guess, because "a fabricated requirement is worse than a missing one, because it
looks settled"; inventing a parallel numbering scheme instead of following the existing one.
**Ships:** with `purpose_code` (it ships with `harness-bootstrap`, even though it dispatches the
`ba-analyst` agent in the spec-builder style).

#### `/scaffold-feature <feature-slug>`

Creates the skeleton of a feature module: entry point, library module, UI component, failing test -
structure only, no behavior. Follows the layout in `.claude/rules/coding-standards.md`: the entry
point (route handler, controller, or command) does input validation and delegation only, the library
module holds the business logic and is testable without the transport layer, the UI component is
built from existing design-system primitives rather than new one-off styles, and a failing unit test
names the acceptance criterion it will eventually prove.

**Writes:** the new skeleton files; a routing-table row if the feature's domain has no owner yet.
**Refuses:** filling in the business logic - "leave the logic unimplemented rather than filling it
with a plausible guess"; proceeding with no feature slug (asks, then stops). **Ships:** with `purpose_code`.

### Implementing

#### `/implement-fr <FR-id>`

Plans and implements a functional requirement end-to-end against its acceptance criteria - the
command diagram 4's sequence actually traces. It is the Guarded flow, so if the work turns out to be
Direct it says so and hands it to the owning agent instead of running the ceremony around it. With
no argument it lists the FRs in `docs/specs/index.json` that are Confirmed, decided yes, and have no
open issues and no task yet, and asks rather than guessing. It reads the FR entry in the index and
then only its block at the entry's file and anchor (plus the matching PRD, if one exists), and
**stops unless the entry says `Confirmed` and `yes`**: a Draft FR, or one the confirmation sheet does
not answer yes, is a promise nobody agreed to. It dispatches `spec-guardian` to lock scope and
acceptance criteria *before* any code is written - an FR with no observable acceptance criteria stops
here and escalates - registers the work via `/new-task`, moves it to `Active` with `task.py move`,
and assigns the specialist per the routing table. A design pass in the task file comes before the
first line of code. Implementation follows whichever methodology the project chose at intake:
test-first under TDD, tests shipped in the same change under DDD/default, or a session-log note of
how each criterion was verified by hand on a project with no automated suite. Once the whole FR is
implemented - not after each step - it runs `/review-changes TASK-NNN` a single time; that gate runs
the test layers it needs, so `/test` is not run first. It closes with an evidence map: one line per
criterion ID (`AC-nn.n`) naming the test, the command and its output, or the screen that proves it,
then the checkpoint.

**Writes:** task session-log rows, the checkpoint, and the code itself via the dispatched dev agent
(plus a glossary entry for any new domain term, under DDD). **Refuses:** implementing an FR that is
not Confirmed; deploying - that is always a separate, explicit `/deploy`; skipping the review gate,
even under Lightweight methodology, which drops ceremony but not the gate; closing with a criterion
that has no evidence. **Ships:** with `purpose_code`.

#### `/db-migration <migration-name>`

Generates a database migration from schema changes, following the ERD and the data dictionary. Diffs
the schema against the data model in `docs/specs/` (updating the ERD and data dictionary in the same
PR/MR if the design is new), generates the migration with the project's migration tool against the
**local development database only**, and reviews the generated SQL before applying it.

**Writes:** the migration file, ERD/data-dictionary updates when the design changed, the seed script
(updated in the same PR/MR so it still matches the schema), a `docs/context/tool-changelog.md` entry.
**Refuses:** running a migration, reset, or schema push against a shared, staging, or production
database under any circumstance - the command file is explicit that this is a gated action and *not*
gated by this command, i.e. out of scope entirely rather than merely restricted; applying generated
SQL automatically when it contains a `DROP` of a populated column/table, a `NOT NULL` added without a
default, a destructive type change, or any other data-loss statement - it escalates to the user
instead, because "generated does not mean safe." **Ships:** only when the `db` flag is set.

#### `/seed-db`

Seeds the local or development database with deterministic synthetic data per the ERD, by dispatching
`db-seeder` under the `db-seed` skill. Checks the connection target first, uses fixed seed values so
two runs produce the same rows, upserts rather than blind-inserts so re-running never duplicates
rows, and verifies row counts per table afterward.

**Writes:** rows in the local/development database (no doc files - the report is the row-count
summary). **Refuses:** running against anything but a local or development database - it refuses
outright if the connection target points at shared, staging, or production; using real customer
records or a production dump, even as a one-off. **Ships:** only when both `db` and `db_seeder` are
set.

### Quality gates

#### `/test`

Runs lint and the test layers this change needs - `verify-plan.py` says which, and a green run
already logged at HEAD is cited and not repeated - and reports each failure with its owning agent.
The end-to-end suite runs only for the critical flows the plan names, or on request. Every
external provider must be mocked - a test that makes a real network call is reported as a failure
even when it passes, because a green result from a live call is not a repeatable one. Reports the
coverage figure against the project's target and whether it regressed against the default branch,
and maps each failure to the agent that owns the code (per the routing table) and the acceptance
criterion it breaks.

**Writes:** a session-log row on the task file recording the run (pass/fail, coverage), and with a
green full suite `task.py checkpoint --green` records the commit so it is never run twice. **Refuses:**
editing a test to make it pass - a failing test is either a real defect or a wrong expectation, and
deciding which is the point. **Ships:** only when the `tests` flag is set (frameworks vary: unit
only, e2e only, or both, per the testing choice at intake).

#### `/review-changes`

Runs the review gate on the current diff before opening a PR/MR - optionally with a `TASK-NNN`.
It starts with `verify-plan.py --base <default branch>`, which reads the branch diff (three dots,
merge-base to tip) and prints each gate as REQUIRED or skipped with the reason: the secret scan
always, spec validation when `docs/specs/` changed, code review for code, tests, schema,
dependencies and infrastructure, security review for auth, secrets, input parsing, data handling,
dependencies and hooks, the scoped tests and then the full suite once for behaviour, an end-to-end
run only for a flow named in `.claude/verify-map.json`, and a content check for prose whose claims
changed. A gate that already passed on these exact bytes is skipped with the ledger line to cite, and
one whose files changed since is narrowed to the changed paths; docs and config changes need the
secret scan and nothing else. It runs `/secret-scan` first (any real secret is a blocker), then
dispatches only the seats whose gate is required, in parallel: the merged `reviewer` under
`solo_review`, or `code-reviewer` plus `security-reviewer` on the split roster, with `spec-guardian`
verifying the linked FR and task acceptance criteria and `checker` for changed non-code claims.
Lint and tests are confirmed locally, and the CI pipeline must be green in a *terminal* state -
pending never counts. Findings are aggregated by severity: blocker, should-fix, suggestion, and each
gate that ran is recorded with `task.py gate`, which writes the ledger line and the session-log row in
one step. The gate is capped at two rounds: after fixes the second round covers only the fix delta
and only blocker and should-fix findings, and whatever remains is escalated to the user.
`guard-agent-spawn` enforces the same ledger at dispatch time.

**Writes:** a ledger line and a session-log row per gate that ran - "a gate counts as passed only
when the log records the run." **Refuses:** merging or deploying - "reviewing is not approving."
**Ships:** unconditional; its shape (merged vs. split reviewers, with or without `checker`) follows
the flags.

#### `/secret-scan`

Scans the current diff (`git diff` plus staged) for secrets and sensitive data before a commit or
PR/MR - no arguments. Looks for credential patterns (`sk-`, `AKIA`, `AIza`, `ghp_`, `glpat-`, `xox`,
JWT-shaped strings, private-key headers, hardcoded `password=`/`api_key=`/`secret=`/`token=`),
forbidden files (`.env*` other than `.env.example`, `*.pem`/`*.key`/`*.jks`/`*.p12`/`*.tfvars`,
service-account JSON), real-looking personal or customer data in fixtures and seeds, and secrets
hiding in CI config, container files, lockfiles, docs, and code comments.

**Writes:** nothing - reports `file:line` plus the pattern TYPE only. **Refuses:** ever printing the
matched value, even truncated, or writing it anywhere; letting the change proceed on any hit until
the value is removed from the diff *and* the credential is rotated - rotation is mandatory even after
the commit is amended, because a secret that reached a commit is compromised regardless. **Ships:**
unconditional (`/review-changes` and `/implement-fr`'s flow both call it).

### Release

#### `/deploy`

Deploys the project to its hosting target - no arguments. This is the one command with
`disable-model-invocation: true` in its frontmatter: an agent cannot trigger it on its own
initiative, it never runs as a step inside another command, and it runs only when a human types
`/deploy` directly. Before doing anything it verifies every precondition and refuses, naming the
reason, if any is unmet: the PR/MR is reviewed, approved, and merged to the default branch; CI is
green *and* in a terminal state (pending or presumed-green don't count); every environment variable
the target needs is present there (confirmed present only - the command never reads, prints, or
copies a secret value); migration status is clean. Only then does it run the forward migrations,
deploy from the merged commit on the default branch (never a local working tree), and verify the
health endpoint - "deployed is not the same as healthy."

**Writes:** a `docs/context/tool-changelog.md` entry (what shipped, from which commit, how it was
verified). **Refuses:** deploying with any precondition unmet; retrying a failed deploy or "fixing
forward" without the user's explicit go-ahead - on failure it rolls back, reports, and stops.
**Ships:** with `purpose_code`, but functionally gated by the control-level dial in
`/harness-tune`: deploy rights default to human-only (`permissions.deny`) until moved to `ask` or a
named non-production variant.

*Ambiguity worth flagging:* the command file's own `allowed-tools` is narrow -
`Bash(git status), Bash(git log:*), Read` - and the file doesn't name which tool actually executes
the migration and deploy steps it describes in prose. Read literally, the file does not fully specify
how those steps run; treat this as the command file's own gap rather than an inferred mechanism.

### Keeping memory current

#### `/sync-context`

Reviews what has landed on the default branch since the last sync and updates the project's
long-term memory in `docs/context/` - no arguments. Adds behavior changes as numbered `BR-NN` rules
(each sourced to an FR or ADR) to `business-rules.md`; records new and newly-fixed issues in
`known-issues.md`, capturing the workaround rather than just the symptom; logs dependency/tool/infra
changes in `tool-changelog.md`; adds new domain terms, entities, status enums, and role names to
`glossary.md`.

**Writes:** `docs/context/business-rules.md`, `known-issues.md`, `tool-changelog.md`, `glossary.md`.
**Refuses:** deleting history - a fixed issue is marked resolved, not removed; copying a secret,
credential, or real customer data into any of these files; restating the diff instead of recording
what a future agent actually needs and couldn't infer from the code. **Ships:** unconditional.

#### `/task-resume [TASK-NNN]`

Resumes a task from its checkpoint after a compaction or in a new session. With no argument it lists
every unfinished task (`Planned`, `Active`, `Blocked`), human gates first, and does not resume
anything. With a task ID it runs `python .claude/scripts/task.py resume TASK-NNN`, which prints the
board row, the checkpoint (next step, last green commit, open questions), the open acceptance
criteria, the last few session-log rows, and whether HEAD and the working tree match the checkpoint -
so the whole log is not read by default. It trusts that digest over conversation memory: the
conversation may have been compacted, the files were committed. When the digest reports drift, or
uncommitted paths, it reconciles before continuing (`task.py check` names the disagreement) rather
than picking a side.

**Writes:** session-log rows after every meaningful unit of work (`task.py log`); any status change
through `task.py move`, which updates the task file, its folder and the master-plan row together; a
rewritten checkpoint before it stops. **Refuses:** stashing, discarding, or clobbering uncommitted
work it finds in the tree - it drives that work to completion or escalates it. **Ships:**
unconditional.

### Exploring a decision

#### `/brainstorm <topic>`

Runs a structured brainstorming session on a decision or feature idea. Dispatches `strategist`,
after `researcher` when the options need evidence, to frame the actual decision and its constraints -
including anything already fixed by an Accepted ADR - produce 3 to 5 genuine options with a
trade-off matrix, and give a recommendation with its reasoning. When the recommendation rests on an
unmeasured assumption, it runs a small timeboxed measurement spike before committing to it.

**Writes:** nothing directly - it routes the outcome onward: a stack-affecting decision to `/new-adr`
before implementation starts, a product-affecting one into the PRD in `docs/requirements/`, anything
else into the task file decisions section. **Refuses:** including a straw-man option that exists
only to be rejected - "noise"; deciding on the user's behalf - "the agent never decides silently."
**Ships:** only when the `long` flag is set (it ships alongside the `strategist` and `researcher`
agents).

### Audit-only pair

These two ship only when a repo was bootstrapped in **audit mode** (the `AU` branch in diagram 2,
`audit` flag) - a read-only control plane where agents scan and record, and a human applies every
fix. They do not exist in a normal delivery bootstrap.

#### `/security-scan [repo-slug]`

Runs the pinned deterministic scanner suite in Docker against the product repos and records new
findings. With no argument it scans every repo in the workspace. Dispatches `sast-runner`, which runs
its full pinned matrix (SAST, secrets, dependency/CVE, infrastructure-as-code policy) against the
target repo(s) through a **read-only mount** - a guardrail, not a convenience: it makes it structurally
impossible for a scanner to write into product source. Raw output lands in `docs/findings/raw/` (one
file per scanner per repo, JSON/SARIF where available), then gets normalized and deduped against
`docs/findings/<repo>/`, with secret matches redacted to location plus pattern type *before* anything
touches disk.

**Writes:** `docs/findings/raw/` (raw scanner output), `docs/findings/<repo>/` (a new finding file at
`status: New` for each new result; a reopened finding goes back to `status: Confirmed` rather than
duplicating). **Refuses:** assigning severity or anchoring requirement IDs - that's `/triage-findings`'
job; silently skipping a scanner that crashed or timed out - it's reported as missing coverage, never
a clean result. **Ships:** only in audit mode (`audit` flag).

#### `/triage-findings [repo-slug]`

Walks every finding at `status: New` under `docs/findings/` through confirmation, severity,
requirement anchoring, and task registration. Dispatches the review agent(s) appropriate to the
finding type to confirm or reject each one - a rejected finding becomes `status: False-positive` and
*keeps* its reasoning rather than being deleted, so the next scan re-raises it and the recorded
reasoning stops the team from re-litigating it. Confirmed findings get a project-scale severity, then
`spec-guardian` anchors `standard`, `standard_version`, and `requirement_id` from the verified
standards table. Each confirmed finding becomes work through `/new-task`, linked both ways.

**Writes:** status transitions on finding files under `docs/findings/`; new task files via
`/new-task`. **Refuses:** anchoring a finding to a standards-table row that is missing, unverified,
or carries no verification date - it leaves the finding at `status: New` and reports it blocked
instead, because citing a possibly-wrong control is worse than citing none; closing a finding on a
claim that it was fixed - only a clean re-check sets `status: Verified`; applying the fix itself -
that is always the user's job. **Ships:** only in audit mode (`audit` flag).

### Quick reference

| Command | Writes / changes | Ships |
|---|---|---|
| `/new-task` | New task file, master-plan row, first session-log row (only for agreed work) | Unconditional |
| `/new-adr` | New ADR file, ADR index row | Unconditional |
| `/new-spec-section` | New/filled spec section, revision-history row | `purpose_code` |
| `/scaffold-feature` | New skeleton files (no logic), routing-table row if new domain | `purpose_code` |
| `/implement-fr` | Task session-log rows, checkpoint, code via the dispatched dev agent | `purpose_code` |
| `/db-migration` | Migration file, ERD/data-dictionary, seed script, tool-changelog | `db` |
| `/seed-db` | Rows in the local/dev database only | `db` + `db_seeder` |
| `/test` | Task session-log row (pass/fail, coverage) | `tests` |
| `/review-changes` | Ledger line and session-log row per gate (findings by severity) | Unconditional |
| `/secret-scan` | Nothing - reports `file:line` + pattern type only | Unconditional |
| `/deploy` | tool-changelog entry (what shipped, from which commit) | `purpose_code`; human-invoked only |
| `/sync-context` | business-rules.md, known-issues.md, tool-changelog.md, glossary.md | Unconditional |
| `/task-resume` | Session-log rows, checkpoint; status in the task file, folder and master-plan row together | Unconditional |
| `/brainstorm` | Nothing directly - routes to `/new-adr`, a PRD, or the task's decisions section | `long` |
| `/security-scan` | docs/findings/raw/, docs/findings/<repo>/ | `audit` |
| `/triage-findings` | Finding status transitions, new task files via `/new-task` | `audit` |

## Accuracy notes

- The byte and file counts above are exact, counted from disk. The token figures in
  `benchmark/RESULTS.md` are **estimated** at 3.6 chars/token, not measured: the benchmark run had no
  API key. They are an order of magnitude, not a quote.
- The orchestrator's session-start scan of the board (`task.py resume`, `task.py check`) is a
  **procedure in the agent body**, not a hook. The always-registered hooks in
  `assets/claude/settings.json` are `PreToolUse` (protect-adr, guard-agent-scope, guard-task-scope,
  guard-board, protect-secrets, guard-main-commit, check-commit-msg, guard-destructive,
  guard-agent-spawn), `PostToolUse` (specs-reminder, graph-stale) and `SubagentStop` (agent-history).
  The rest register inside the block of the flag that ships them: `hooks_strict` (large files,
  egress, dependencies, secrets in prompts and output, config changes, evidence-free "done"), `db`
  (migrations), `long` (retry budget, compaction checkpoint, a `SessionStart` context injection, an
  event trace), `purpose_research`, `purpose_docs`, `rtk` and `audit`. `assets/claude/hooks/README.md`
  is the table. Diagram 4 shows the scan as an orchestrator action for that reason.
- `CONFLICT` does **not** change the scaffolder's exit code. An unresolved `{{VAR}}`, an invalid flag
  set, a second `Agent`-holding seat, an unwired control or an unresolved link (exit 1), or a
  missing manifest/asset (exit 2), does. Diagram 3 reflects the code.
- The `merge-manager` seat is optional and is omitted from diagram 4. Where it is not fielded, the
  orchestrator merges and applies the same rules itself.

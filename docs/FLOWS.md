# Flows

Visual reference for the two skills in this repo: `spec-builder`, which produces the requirements
contract, and `harness-bootstrap`, which builds the machine that implements it.

Every diagram below is Mermaid and renders natively on GitHub. The claims in them are taken from the
source: `harness-bootstrap/SKILL.md`, its `reference/` docs, `scripts/scaffold.py`,
`assets/manifest.json`, `assets/claude/settings.json`, `spec-builder/SKILL.md`, and
`benchmark/RESULTS.md`.

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
they do not.

```mermaid
flowchart TD
    START(["Repo to be made agent-ready"])
    Q{"Does docs/specs/<br/>hold a requirements set?"}

    SB["spec-builder<br/>elicit, scaffold 13 sections, fill"]
    SPECS[/"docs/specs/ 01-13<br/>the requirements contract"/]

    HB["harness-bootstrap<br/>analyze, roster, scaffold, wire"]
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
commands. The `CONFLICT` branch out of the scaffolder is not an error path: it is the brownfield
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

    INTAKE["Intake questionnaire<br/>AskUserQuestion, max 4 per call.<br/>Brownfield: pre-fill from evidence, ask only<br/>what code cannot decide"]
    TOOLS["Detect + confirm target tools<br/>scan for .cursor/ .codex/ AGENTS.md,<br/>then ask: Claude Code / Cursor / Codex"]
    PLAN{"One-screen setup plan:<br/>created / kept / modified,<br/>roster with model + effort.<br/>User confirms"}

    ROSTER["Pick the roster<br/>Tier 0 unconditional, preset S/M/L,<br/>explicit model: AND effort: on every agent"]
    OS["Detect the dev OS<br/>Windows to .ps1, macOS or Linux to .sh<br/>sets the windows / posix flag"]
    VARS[/"vars.json<br/>vars + flags: ui, db, ai, audit,<br/>exactly one of windows / posix"/]

    DRY["scaffold.py --dry-run"]
    SCAFFOLD["scaffold.py<br/>deterministic copy of assets/"]

    ADDED[/"ADDED<br/>file did not exist"/]
    KEPT[/"KEPT<br/>exists and is byte-identical"/]
    CONFLICT[/"CONFLICT<br/>exists and differs - not written"/]
    MISSINGVAR["Unresolved {{VAR}}<br/>exit 1 - fails loudly"]

    RECONCILE["Reconcile by hand:<br/>keep / adapt / add / flag.<br/>Never clobber what the user wrote"]

    GAPFILL["Model-authored gap-fill<br/>orchestrator routing table, dev-agent scopes,<br/>tech-stack.md, coding-standards.md, git-workflow.md,<br/>settings.json allow/deny for the real stack, .env.example"]
    WIRE["Orchestration wiring<br/>master-plan index table, Phase 1 seeded from the<br/>analysis gap list, AGENTS.md entry point,<br/>CLAUDE.md as a thin @AGENTS.md import"]

    GATE{"Quality gate<br/>structure / cost and context / safety /<br/>grounding / handoff"}
    SMOKE["Smoke-test the loop:<br/>real task file, master-plan row,<br/>session-log row, /task-resume"]
    PORT["Port to the tools selected at intake<br/>port.py --tool cursor / codex / all:<br/>.cursor/rules + adapter, .codex/hooks.json"]
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

    INTAKE --> TOOLS --> PLAN
    PLAN -->|"changes requested"| INTAKE
    PLAN -->|"confirmed"| ROSTER
    ROSTER --> OS --> VARS
    VARS --> DRY --> SCAFFOLD

    SCAFFOLD --> ADDED
    SCAFFOLD --> KEPT
    SCAFFOLD --> CONFLICT
    SCAFFOLD --> MISSINGVAR
    MISSINGVAR -->|"add the var, re-run"| VARS

    CONFLICT --> RECONCILE
    ADDED --> GAPFILL
    KEPT --> GAPFILL
    RECONCILE --> GAPFILL

    GAPFILL --> WIRE --> GATE
    GATE -->|"a check fails"| GAPFILL
    GATE -->|"all green"| SMOKE --> PORT --> DONE

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef hum fill:#1D3557,stroke:#0B1B2B,stroke-width:1px,color:#A8DADC
    classDef gate fill:#9D0208,stroke:#370617,stroke-width:1px,color:#FFBA08
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class ANALYZE,INTAKE,TOOLS,ROSTER,OS,GAPFILL,WIRE,RECONCILE mod
    class DRY,SCAFFOLD,SMOKE,PORT det
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
the two places where it refuses to guess.

```mermaid
flowchart TD
    START(["python scripts/scaffold.py --target REPO --vars vars.json"])
    LOAD["Load vars.json: vars + flags<br/>Load assets/manifest.json"]
    NOMAN["manifest or asset missing<br/>ScaffoldError, exit 2"]
    LOOP{"Next manifest entry"}

    ONLY{"--only prefix set<br/>and src does not match?"}
    FLAGS{"Flag filter<br/>when: AND over flags<br/>when_any: OR over flags"}
    SKIP[/"SKIPPED by flags<br/>e.g. frontend.md without 'ui',<br/>*.ps1 without 'windows'"/]

    READ["Read the asset<br/>subst: false to copy bytes verbatim"]
    BLOCKS["Resolve conditional blocks<br/>{{#IF_X}} kept if flag X is set<br/>{{^IF_X}} kept if flag X is NOT set<br/>repeated passes, innermost first"]
    SUBST["Substitute {{VAR}} from vars<br/>dest path is substituted too.<br/>A missing key is recorded, not blanked"]

    EXISTS{"Destination exists?"}
    SAME{"Bytes identical<br/>to the payload?"}

    ADDED[/"ADDED<br/>write file, mkdir parents,<br/>chmod +x if 'exec'"/]
    KEPT[/"KEPT<br/>already identical - untouched"/]
    CONFLICT[/"CONFLICT<br/>exists and differs.<br/>NOT written unless --force"/]

    REPORT["Report: ADDED / KEPT / CONFLICT / SKIPPED<br/>+ summary counts"]
    MISS{"Any unresolved {{VAR}}<br/>across all entries?"}
    FAIL["Print the missing keys per file<br/>exit 1"]
    OK["exit 0<br/>CONFLICTs are listed, not fatal"]
    QUEUE["Brownfield reconciliation queue:<br/>keep / adapt / add / flag, by hand"]

    START --> LOAD
    LOAD -->|"not found"| NOMAN
    LOAD --> LOOP
    LOOP --> ONLY
    ONLY -->|"yes, skip"| LOOP
    ONLY -->|"no"| FLAGS
    FLAGS -->|"flags not satisfied"| SKIP --> LOOP
    FLAGS -->|"wanted"| READ
    READ --> BLOCKS --> SUBST --> EXISTS
    EXISTS -->|"no"| ADDED --> LOOP
    EXISTS -->|"yes"| SAME
    SAME -->|"yes"| KEPT --> LOOP
    SAME -->|"no"| CONFLICT --> LOOP
    LOOP -->|"manifest exhausted"| REPORT
    REPORT --> MISS
    MISS -->|"yes"| FAIL
    MISS -->|"no"| OK
    CONFLICT -.-> QUEUE

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef hum fill:#1D3557,stroke:#0B1B2B,stroke-width:1px,color:#A8DADC
    classDef gate fill:#9D0208,stroke:#370617,stroke-width:1px,color:#FFBA08
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class LOAD,LOOP,ONLY,FLAGS,READ,BLOCKS,SUBST,EXISTS,SAME,REPORT,MISS,OK det
    class START hum
    class NOMAN,FAIL gate
    class SKIP,ADDED,KEPT,CONFLICT art
    class QUEUE mod
```

The scaffolder refuses two decisions on purpose:

- It **never overwrites.** An existing file that differs is reported and left alone, because on a
  brownfield repo the differing file is usually something a human wrote. Use `--force` for files you
  have explicitly decided to replace.
- It **fails on an unresolved variable** rather than writing a literal `{{DB_RESET_CMD}}` into a deny
  rule that would then never match anything.

Re-running on an unchanged repo is idempotent: everything comes back `KEPT`, nothing is clobbered.

## 4. One feature, end to end through the generated harness

This is the flow the generated `.claude/` folder exists to run. The orchestrator is the only entry
point for multi-step work; the specialists are dispatched, not driven by hand. In cost terms: the
orchestrator, the reviewers, and the debugger are Opus seats; the dev agents, `qa-test`, and
`spec-guardian` are Sonnet; the mechanical seats (`history-tracker`, `db-seeder`) are Haiku at `low`
effort. The hooks cost nothing, being shell scripts rather than a model, and they are the only
participant here that can say no.

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
    participant Hooks as hooks<br/>.claude/hooks/

    User->>Orch: Mission: implement FR-07
    Orch->>Board: Session-start scan of docs/tasks/active/<br/>grep "status: Active" and "status: Blocked"
    Board-->>Orch: Unfinished work first - otherwise accept the mission

    Note over Orch,Board: Registration. A registered-but-not-started task is Planned,<br/>and a Planned file lives in active/ - pending/ means parked.
    Orch->>Board: Create TASK-NNN from docs/templates/TASK.md<br/>status: Planned in frontmatter AND in the master-plan row
    Orch->>Board: Append the first session-log row

    Orch->>Spec: Verify scope and acceptance criteria BEFORE any implementation
    Spec-->>Orch: Contract locked, or drift found and escalated
    Note over Spec: Read-only. No Bash - it has nothing to run.
    Orch->>Board: status: Active in BOTH places

    Orch->>Dev: Dispatch: TASK code, FR/PRD, target files,<br/>acceptance criteria, isolated worktree + branch
    Note over Dev: TDD: the failing test comes first.
    Dev->>Hooks: Edit / Write
    Hooks-->>Dev: PreToolUse: protect-adr, protect-secrets - allowed (exit 0)
    Hooks-->>Dev: PostToolUse: specs-reminder

    Dev->>Hooks: Bash: git commit (on the default branch)
    Hooks-->>Dev: BLOCKED. guard-main-commit exits 2:<br/>"do not commit directly to main - branch first"
    Note over Hooks: A hook that blocks you is a rule you were about to break.<br/>Never route around it with a shell equivalent.
    Dev->>Hooks: Bash: git checkout -b feat/... then git commit
    Hooks-->>Dev: check-commit-msg validates Conventional Commits - passes (exit 0)
    Dev->>Board: Session-log row: what was done, result
    Dev-->>Orch: Implementation complete (a CLAIM, not a fact)

    Orch->>QA: Run the suite - tests map 1:1 to the acceptance criteria
    QA->>Board: Session-log row: tests green
    QA-->>Orch: Green

    par Reviewers run in parallel
        Orch->>CR: Review the diff
        CR->>Board: Session-log row: findings
        CR-->>Orch: Pass / findings
    and
        Orch->>SR: Review secrets, PII, authz
        SR->>Board: Session-log row: findings
        SR-->>Orch: Pass / findings
    end
    Note over CR,SR: Neither has Edit or Write. A reviewer that edits code<br/>has become a dev agent and lost its independence.

    Orch->>Orch: /secret-scan on the diff
    Orch->>Board: Read back the session log
    Note over Orch,Board: A gate counts as passed ONLY when the session log records the run.<br/>"All gates green" over a log with no reviewer rows is the classic failure.

    alt A gate has no logged row
        Orch->>Dev: Re-run the gate. The claim is not evidence.
    else Every gate is logged
        Orch->>Orch: Merge: one merger, serialized, against the LIVE mainline tip<br/>diff with three dots, union on shared lists, never --ours/--theirs
        Orch->>Board: Post-merge board audit: every task file's frontmatter<br/>status equals its board row - Done files and Done rows agree 1:1
        Orch->>Board: Outcome section, status: Done in BOTH places,<br/>move the file active/ to done/
    end

    Note over Orch: Close-out: remove the worktree, delete the merged branch,<br/>prune, and sweep out-of-repo scratch (gated, enumerated).
    Orch->>Board: No Active or Blocked tasks left in scope:<br/>terminal phase + a final MISSION COMPLETE session-log row
    Orch-->>User: Summary. Then the instance terminates rather than idling.
    Note over Orch,Board: Marker present + silent = finished, do NOT resume.<br/>No marker + silent = crashed, resume from file state.
```

The files are the truth and an agent's report is a claim. A gate is passed when the task file's
session log holds a row for it, not when an agent says "reviewed". Status lives in two places, the
task file's frontmatter and the master-plan row, and every status change writes both in the same
step, because a merge that resolves a board collision by taking one side reverts a status flip with
no error at all. The hooks are the hard edge: `PreToolUse` fires before the tool runs, exit 2 blocks
it, and the message on stderr goes back to the model. The `MISSION COMPLETE` marker makes "finished"
distinguishable from "crashed" by a file check instead of a guess.

## 5. spec-builder

Same shape, different contract: elicit what only a human knows, let the script lay down the thirteen
sections, then spend model tokens on the content rather than on the headings. The governing rule is
that **nothing is invented**. An unstated requirement becomes an assumption (AS-nn) or an open issue
(OI-nn) with a named owner, because a plausible invented requirement gets estimated, built, and
discovered in UAT.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant SB as spec-builder<br/>the model
    participant Scaffold as scripts/scaffold.py
    participant Specs as docs/specs/
    participant HB as harness-bootstrap

    User->>SB: Raw input: an idea, meeting notes, a transcript,<br/>an existing PRD, legacy docs, a codebase
    SB->>SB: Elicit - infer STRUCTURE, ask for DECISIONS
    SB->>User: AskUserQuestion, batches of at most 4:<br/>priorities, permission scope, NFR targets, volumes,<br/>security posture, output language
    User-->>SB: Answers. Anything unanswered becomes AS-nn / OI-nn.

    SB->>User: Confirm the FR list FIRST - FRs with proposed MoSCoW<br/>priorities, the roles, the open issues so far
    User-->>SB: Confirmed or corrected
    Note over SB,User: Everything from section 02 onward derives from this list.<br/>A wrong list costs twelve documents.

    SB->>Scaffold: vars.json - PROJECT_NAME, PROJECT_SLUG,<br/>PROJECT_PURPOSE, DOC_OWNER + flags ai / ui / db
    Scaffold->>Scaffold: --dry-run first
    Scaffold->>Specs: Write 14 files: README + sections 01-13,<br/>headings, tables, Mermaid scaffolds, inline authoring notes
    Scaffold-->>SB: ADDED / KEPT / CONFLICT. Exit 1 on an unresolved &#123 -&#123 -VAR&#125 -&#125 -.
    Note over Scaffold,Specs: Deterministic and free. The model does not retype the shape -<br/>CONFLICT is the reconciliation queue for a repo that already has specs.

    SB->>Specs: Fill section by section, in order - each depends on the last
    Note over SB,Specs: The three that carry the load:<br/>05 observable FRs, anchored, with BR-nn and a NEGATIVE acceptance case<br/>07 security NFRs, never "TBD" - an undecided value is an OI with an owner<br/>12 every FR gets Yes / Partial / No - "Partial" and "No" are the valuable output

    SB->>SB: Traceability check - every FR from 05 appears in 12 (count both),<br/>every screen in 10 names an FR, every role in 06 exists in 03,<br/>every entity in 06 exists in 08, no blank cells, all links resolve
    SB->>User: Surface every OI, every AS, every Partial/No, and every NFR<br/>target that was proposed rather than received

    opt The docs workspace exists
        SB->>HB: Seed docs/requirements/PRD-FR-NN-*.md, docs/context/glossary.md,<br/>docs/context/business-rules.md - linking back, not duplicating
    end
    SB-->>HB: Handoff: the contract exists. Bootstrap the harness that implements it<br/>(dev agents clustered from the FR list), then /implement-fr.
```

The ordering is a discipline: the FR list is confirmed *before* anything else is written, and the
sections are filled in order because each depends on the last. The traceability check at the end is
mechanical - count the FRs in 05, count the rows in 12, they match - which is the kind of check a
model will skip unless it is written down as a gate.

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
        BODY[/"The agent's own body<br/>one file per agent under .claude/agents/"/]
        SCHEMA[/"Tool schemas - one per entry in tools:<br/>omitting tools: inherits EVERY tool,<br/>including every MCP server on the machine"/]
    end

    TOUCH{"Claude touches a file"}

    subgraph LAZY["Lazily loaded - enters context only on a path match"]
        L1[/"code-quality.md - SOURCE_GLOBS"/]
        L2[/"performance.md - SOURCE_GLOBS"/]
        L3[/"security-privacy.md - SOURCE_GLOBS"/]
        L4[/"testing.md - TEST_GLOBS + SOURCE_GLOBS"/]
        L5[/"frontend.md - UI_GLOBS (flag ui)"/]
        L6[/"data-model.md - DB_GLOBS (flag db)"/]
        L7[/"docs-workflow.md - docs/**"/]
    end

    NEVER[/"assets/ - the hooks, commands, templates, agent bodies.<br/>NEVER enter the context window: scaffold.py copies them.<br/>The model reads SKILL.md + 6 reference docs, and nothing else."/]

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
    LAZY -->|"only the matching rule"| WINDOW
    NEVER -.->|"never"| WINDOW

    classDef det fill:#2D6A4F,stroke:#081C15,stroke-width:1px,color:#D8F3DC
    classDef mod fill:#5A189A,stroke:#240046,stroke-width:1px,color:#E0AAFF
    classDef hum fill:#1D3557,stroke:#0B1B2B,stroke-width:1px,color:#A8DADC
    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class CLAUDEMD,AGENTSMD,R1,R2,R3,R4,BODY,SCHEMA art
    class L1,L2,L3,L4,L5,L6,L7 art
    class NEVER det
    class WINDOW mod
    class TOUCH hum
```

Six unconditional rules, eight path-scoped ones. On the shipped asset set that is 25,303 bytes always
loaded against 49,394 bytes loaded on demand: **66% of the rule content is kept out of the default
session**, so the database agent no longer carries the frontend rules and the UI agent no longer
carries the migration-safety rules.

Two other levers sit in the same diagram:

- Every tool in an agent's `tools:` list ships its JSON schema on *every* request. Omitting `tools:`,
  and thereby inheriting every MCP server on the machine, is treated as a bug in the quality gate.
- Every file in the always-loaded band is prompt-cache prefix content, so a single `Generated: <date>`
  line in an agent body cold-misses that agent's cache on every future run. No generated file carries
  a timestamp.

## Accuracy notes

- The byte and file counts above are exact, counted from disk. The token figures in
  `benchmark/RESULTS.md` are **estimated** at 3.6 chars/token, not measured: the benchmark run had no
  API key. They are an order of magnitude, not a quote.
- The orchestrator's session-start scan of `docs/tasks/active/` is a **procedure in the agent body**,
  not a `SessionStart` hook. The hook events registered in `assets/claude/settings.json` are
  `PreToolUse` (protect-adr, protect-secrets, guard-main-commit, check-commit-msg), `PostToolUse`
  (specs-reminder), and `SubagentStop` (agent-history). Diagram 4 shows the scan as an orchestrator
  action for that reason.
- `CONFLICT` does **not** change the scaffolder's exit code. Only an unresolved `{{VAR}}` (exit 1) or
  a missing manifest/asset (exit 2) does. Diagram 3 reflects the code.
- The `merge-manager` seat is optional and is omitted from diagram 4. Where it is not fielded, the
  orchestrator merges and applies the same rules itself.

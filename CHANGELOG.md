# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

Every release ships installable `.zip` artifacts with a `VERSION` file inside each skill. See
[`docs/RELEASING.md`](docs/RELEASING.md).

## v1.10.0

The viewer became usable on a real board. Everything here is `harness-view`; the two skills are
unchanged apart from their version stamp.

- **The task board reads as a board.** Task nodes were labelled with their full title, up to 378px
  wide, packed into lanes 10px apart: 190 overlapping pairs, unreadable. Nodes now carry the task id
  and sort by status, so the column forms colour bands by Active / Blocked / Pending / Done, and
  overlaps are zero. The full title is one click away in the panel.
- **Markdown is rendered by a real library.** The hand-written renderer is gone, replaced by vendored
  `marked` with `DOMPurify` sanitising its output. Both are inlined, so the page still makes no
  network request. A wide table now keeps its real width and scrolls inside its own frame instead of
  collapsing one character per column, which is what broke the preview.
- **Browse for a folder.** A Browse button walks the filesystem and loads a repo, with recently
  opened folders listed and removable. The server lists directory names only, because a browser
  cannot hand a page a real filesystem path.
- **The preview fills the panel** instead of sitting in a fixed 340px box with empty space below it.
- Icons on the header buttons, and the auto-refresh interval is a setting (5s / 10s / 30s / 60s)
  that takes effect immediately. Its checkbox is no longer misaligned.
- Release notes now describe the tools, not only the skills, and a missing tool entry fails a gate.

### Fixed

- Markdown tables in the preview rendered as vertical stacks of single characters. Two causes: the
  panel's own `width: 100%` table rule captured every rendered table by id specificity, and the
  hand-rolled parser. Both are gone.
- Node overlap in the graph view fell from 47 pairs to 4 at full density, and from 1 to 0 at the
  default filter, by letting the separation pass work outside the visible canvas bounds.

Honest note: the markdown library is about 12 times slower than the hand-rolled parser (30ms versus
2.3ms on the largest file in a real repo). Rendering happens only when a file is opened, so it is not
perceptible, but it is a real regression and not worth pretending otherwise.

## v1.9.0

`harness-view` grew up: it ships as a real application you can download and run, and the viewer
became usable on a large board instead of merely correct.

- **Standalone builds for Windows, macOS and Linux**, attached to every release as signed-by-hash
  archives with the binary, its README and the schema. No Rust toolchain and no Python needed.
  The Windows executable carries proper file metadata (product, version, company) and the project
  icon, and double-clicking it serves the folder it sits in and opens a browser.
- **An icon for the tool**, derived from the repo's own shield-and-eye mark by a committed
  generator script, so it can be regenerated rather than being an opaque binary. The served page
  finally has a favicon too.
- **The tool version is enforced against the release version**, so a binary can no longer report a
  number that disagrees with the tag it shipped under.
- **Choose a folder from the browser.** The viewer no longer needs a restart to look at another
  repo: type or pick a path, and recent roots are remembered. A path that is not a harness says so
  instead of showing an empty page.
- **Read the files, not just the boxes.** Agents, rules, commands, tasks and the master plan can be
  opened in place, formatted by default with a one-click switch to the raw markdown.
- **Trace a connection.** Clicking a node lights its neighbours and the edges between them with a
  moving dash and fades everything unrelated, which is the point of having a graph at all.
- **Three connection-line styles** (curved, orthogonal, straight), hook nodes badged Pre / Post /
  Stop with blocking hooks marked, task nodes showing owner and status, and an optional master-plan
  tab when the repo keeps one.

### Fixed

- The viewer served a blank page. A JavaScript string broken across two lines killed the whole
  script, and because the canvas was sized only after a successful load, any failure left an
  unsized canvas with no error shown. Both are fixed, and a new gate parses every embedded script
  so a syntax error cannot ship again.
- **87 of 172 nodes were drawn off screen** on a real board with no indication they existed. The
  view now scales to fit, and a lane with more nodes than fit wraps instead of running off the
  bottom.
- Edges were drawn between node centres, so lines ran under the boxes and every arrowhead was
  hidden behind its target. Edge labels all landed on the same point: 2,526 overlapping pairs on
  one board, now zero.
- Panning cleared the selection you were trying to inspect.
- Nodes overlapped each other in the graph view because the layout treated a 180px-wide box as a
  point: 76 overlapping pairs, now zero.
- Documentation: every command both skills install is now documented with its invocation, what it
  writes, what it refuses to do, and which flag ships it. Sixteen of them had no documentation at
  all.

## v1.8.2

Running the new `harness-view` against a real scaffolded harness found a bug that had been
shipping since the first release.

- **Path-scoped rules emitted invalid frontmatter.** The glob variables carry their own quotes and
  the rule templates added a second pair, so every scoped rule shipped `- ""src/**/*.ts""` instead
  of `- "src/**/*.ts"`. A rule that looks scoped but whose `paths:` block does not parse is the
  quietest failure this harness can have, and the session-tax figures assume the scoping works.
  Present in every release from v1.0.0 to v1.8.1. The eval now scaffolds a harness and parses each
  `paths:` block, so it cannot come back.
- The native viewer counted a command's reference to the skill's own `<skill>/scripts/scaffold.py`
  as an installed script, inventing two edges the Python scanner correctly omitted. Both scanners
  now produce byte-identical graphs on a full 72-node harness, not just on the small fixture.

Guardrail eval: 69/69 per hook flavor, 138/138 across both.

## v1.8.1

- The presentation deck claimed the old `40/40` guardrail-eval result after the suite reached
  68 cases. The figure checker missed it because its eval-badge scan only covered Markdown, and
  in the deck the identifying words follow the number instead of preceding it. Both are fixed,
  and the checker now proves it catches this exact drift.

## v1.8.0

A fitted harness instead of a fixed one, a map of what got built, and runtime control over it.

- **The roster fits the project.** Planning and history seats ship only for long-running work, the
  database seats are separate choices, small projects can merge the two reviewers into one, and
  testing is a question with a real "none" answer rather than an always-on assumption. A default
  install is materially smaller than before.
- **See the harness you built.** A canonical `harness-graph.json` records every agent, rule,
  command, hook, and their typed relationships; the viewer gained a layered Flow view beside the
  force-directed one; and both graphs rebuild themselves as soon as you change the harness or the
  docs.
- **Turn things off without hand-editing.** `/harness-toggle` disables and re-enables rules,
  commands, and hooks through a committed ledger that survives scaffold re-runs, with a typed
  confirmation guarding the controls that matter most.
- **A native viewer.** `tools/harness-view` is an optional Rust binary that reads the same graph
  contract and serves the same two views, with a file watcher and a toggle panel. The bundled HTML
  viewer still needs nothing installed.
- **Specs you actually asked for.** `spec-builder` now selects sections from the input material
  instead of always writing thirteen, adds a design-system section with token and component IDs,
  and can split a long section into a folder.
- **Safety fixes worth naming.** The scaffolder rejects mistyped flags that used to leave every
  guardrail silently dead; the toggle refuses path traversal; a corrupt ledger aborts instead of
  resurrecting disabled controls; and the generated graph page escapes repository content.

Guardrail eval: 69/69 per hook flavor, 138/138 across both. Read path 45 percent below the
predecessor skill. Figures from `eval/guardrail_eval.py` and `benchmark/benchmark.py`.

## v1.7.0

Wider skill sourcing, current-version presets, a value-free path to local env files, and two
guardrail holes closed.

**Added**

- `env-read.py`: devops, db, and qa seats can work with `.env.local`/`.env.test` without a value
  ever entering the transcript - `list`, `check`, `diff`, `run`. Production-named files refused.
  `protect-secrets` stays strict; direct reads are still blocked.
- `.claude/.gitignore` ships with the harness, so per-task worktrees and machine state never get
  committed. Nested on purpose: it cannot conflict with the repo's root ignore file.
- Skill discovery now covers four sources - skills.sh, GitHub topic search, `anthropics/skills`,
  and plugin marketplaces (SHA-pinned entries only) - each with the trust signals it actually
  exposes. See [reference/skill-discovery.md](harness-bootstrap/reference/skill-discovery.md).
- `reference/tech-presets.md`: a library catalogue with a rule that matters more than the
  catalogue - never write a version from memory, verify it against the registry and record the
  date. A model's knowledge cutoff is why the harness pins Next.js 15 when 16 is out.
- Intake 24 -> 27 questions: i18n, authz and tenancy, ops posture; compliance now names APPI and
  Decree 13. From an obra/superpowers audit: typed-word `discard` confirmation for irreversible
  actions, capability escalation on the third attempt, comparative pattern analysis when debugging.

**Fixed**

- A one-newline bypass of the commit-message guardrail: `git commit -m "bad subject\n\nbody"`
  skipped validation entirely, reachable by accident since multi-line messages are normal.
- `guard-agent-spawn` behaved differently in its two flavors on an unreadable payload. Both now
  refuse it - the one deliberate exception to fail-open, pinned by the eval.
- The benchmark's own scaffold run was silently exiting 1 on a missing variable.

**Changed**

- Hooks extract JSON fields in one parser call instead of up to seven: 1.3x to 1.8x faster per
  call on machines without `jq`. `check_numbers.py` 8.4x faster on doc-heavy trees.
- Eval 30 -> 33 cases (66 across both hook flavors). Read path -45% / 128,072 B: it grew this
  cycle because the skill does more, and [benchmark/RESULTS.md](benchmark/RESULTS.md) says so
  rather than hiding it.

## v1.6.0

Living specs, a docs graph, DDD by default, and a face: shield logo, banner, and media that a gate
now keeps honest.

**Added**

- Docs knowledge graph: `/docs-graph` maps ID traceability (defining doc, references, orphans) and
  `graph-html.py` exports both graphs as self-contained interactive pages
  (`docs/context/harness-graph.html`, `specs-graph.html`), built at the end of both skills.
- spec-builder living-spec commands: `/spec-ingest` (fold a new source in - diffed, versioned,
  rippled to dependent agent files) and `/spec-retract` (trace and withdraw a bad source or claim,
  converted to open issues, affected tasks blocked with a `human_gate`).
- Windows quickstart (`irm` + `Expand-Archive`) and a paste-to-agent self-install block, both
  languages. New shield-and-eye logo, README banner, deck favicon, video watermark + end cards.
- Eval: a `guard-main-commit` allow case it was missing, plus optional `--flavor ps1` Windows
  parity (33/33 default, 66/66 both flavors). `check_numbers.py` now guards presentation, video,
  and prose eval badges - the drift class that recurred every release is now a failing gate.
- PR #1 merged: board validator with dependency-cycle detection, `human_gate` markers,
  attempt-reason taxonomy, advisory scope guard, `control-surfaces.md`.

**Changed**

- DDD is the sole default methodology; TDD is opt-in (alone or combined) - it trades delivery
  speed for proof discipline, so intake asks instead of assuming.
- Counts: commands 20 -> 21 (+2 spec-side), hooks 8 -> 9, eval 22 -> 26 cases; read path -54% /
  108,591 B after bootstrap.
- README reframed: problem scenarios first, "what you get" as tailoring dimensions (the counts are
  the toolbox, not the product), spec-builder's 13-section standard named; benchmark results
  rebuilt around three goals with bar charts; presentation and all six intro clips audited,
  corrected, and re-rendered.

## v1.5.0

Skill discovery, a code knowledge graph, and a friendlier front door.

**Added**

- Code knowledge graph: `/code-graph` builds the module/import map agents consult before any
  cross-module change (`.claude/scripts/code-graph.py`, stdlib only); the non-blocking
  `graph-stale` hook records drift and `/board-audit` flags it.
- Skill discovery and install: bootstrap step 2.5 searches [skills.sh](https://www.skills.sh/)
  per seat under a trust rubric with a mandatory content read
  ([reference/skill-discovery.md](harness-bootstrap/reference/skill-discovery.md)); `/skill-wire`
  maps installed skills to seats with re-review, invariant refusals, and a changelog record.
- Express intake: 28 -> 24 questions, closed choices via AskUserQuestion, derivable answers
  confirmed instead of re-asked; the governance batch is still never defaulted.
- `docs/TUNING.md` covers all six post-bootstrap commands; CONTRIBUTING.md rewritten.

**Changed**

- TDD and DDD are now BOTH default methodology flags; single-methodology remains a choice.
- README rewritten around the two skills' one-line essence (363 -> 180 lines), mirrored in
  Japanese; long detail moved into linked docs.
- The two skills invoke each other through the Skill tool with prefilled variables, replacing
  prose handoffs.
- Counts: commands 18 -> 20, hooks 7 -> 8, eval 21 -> 22 cases; read path after bootstrap
  97,190 B (-59%).

## v1.4.0

The spawn boundary, a DDD option, and post-bootstrap tuning.

**Added**

- `guard-agent-spawn` hook on `Agent|Task`: blocks off-roster spawns, per-dispatch model escalation,
  and write-capable dispatches that name no task. Allowlist at `.claude/hooks/spawn-allowlist`.
- DDD as a first-class methodology (flag `ddd`, ships `rules/ddd.md`); TDD stays the default
  (flag `tdd`) and the two compose. Intake asks which, plus a control-level question whose
  `deploy_ask` flag moves the deploy command from `deny` to `ask`.
- Four post-bootstrap commands: `/board-audit` (orphan and stale-task sweep), `/harness-tune`
  (control dials), `/agent-permissions` (per-seat tool grants), `/harness-update` (safe re-run).
- Anti-loop discipline: `attempts:` counter on tasks, hard cap 3 then Blocked; `maxTurns` on all
  16 seats; the scaffolder fails the build if more than one seat holds the `Agent` tool.
- Release notes standard: one screen, capped bullets ([docs/RELEASING.md](docs/RELEASING.md)).

**Changed**

- Guardrail eval 15 -> 21 cases (3 spawn blocks, 3 spawn allows). Counts: rules 14 -> 15,
  hooks 6 -> 7, commands 14 -> 18.
- README slimmed 13% in both languages; every stale figure re-synced by `check_numbers.py`.
- spec-builder: 10 audit fixes - complete ID-prefix table, verifiable quality gate, re-run
  procedure for existing specs, section-12 seeding claim corrected to manual.
- `port.py` now states that `guard-agent-spawn` does not port: Cursor and Codex have no
  subagent-spawn hook point, so the spawn boundary is Claude Code only.

## v1.3.0

Intro videos, a tool-selection questionnaire in the docs, and drift caught at the source.

**Added**

- Three intro clips under `video/`, each as a 1080p MP4 (rendered with Manim) and a self-contained HTML animation: what it is and why, the operating flow, and the control layers. They play in the browser via a GitHub Pages gallery (`video/index.html`), so no download is needed. Linked from the README (English and Japanese). Content and colour grammar trace to `README.md` and `docs/FLOWS.md`.
- `.claude/agents/docs-reconciler.md` - a local agent that reconciles the docs against the code, skills, and scripts, and fixes drift.
- The target-tools questionnaire (detect `.cursor/` / `.codex/` / `AGENTS.md`, then ask which of Claude Code / Cursor / Codex to target) is now documented in the `intake.md` reference, matching the SKILL.md procedure.
- Every release now attaches `eval-results.md` and `benchmark-results.md`, captured from the tagged commit, so the "15/15" and the numbers are provable per version.

**Changed**

- `docs/FLOWS.md` diagram 2 now shows the `/harness-bootstrap` invocation, the tool-selection questionnaire, and the Cursor/Codex port step, matching the current procedure. It previously opened with the stale phrase "set up the base".
- Benchmark read-path figure updated to 85,641 bytes / -63% (was 83,339 / -64%): the read path grew as `SKILL.md` gained the port and questionnaire content.
- The logo is redesigned in a dark-blue palette and reads as an agent node held inside the harness frame by two control anchors.

**Fixed**

- `check_numbers.py` guarded only the percentages, so the raw "after" byte figure had drifted silently across four files. It now also guards the exact after-read and after-write byte figures, counted from disk.
- Two reference docs pointed at a stale `docs/templates/TASK.md.template` path; the shipped template has no `.template` suffix.

## v1.2.0

The guardrails now port to Cursor and Codex, not just the rules.

**Added**

- `harness-bootstrap/scripts/port.py` - ports a scaffolded harness to Cursor and Codex. `--tool cursor|codex|all`. It converts `.claude/rules/` to `.cursor/rules/*.mdc` (path-scoped `paths:` becomes `globs:`, unconditional becomes `alwaysApply`), registers the hooks in `.codex/hooks.json` directly (Codex's payload matches Claude Code's), and writes a `.cursor/hooks.json` plus an adapter that translates Cursor's payload and output.
- The porter's adapter is unit-tested in CI (`port.py --self-test`): it denies a `.env` read and a commit to `main`, and allows `npm test`, through the Cursor hook path. 5/5.
- README: separate install and setup instructions for Claude Code, Cursor, and Codex, and a mechanics table for what crosses over.

**Changed**

- Enforcement now ports. The prior README claimed Cursor and Codex get the rules without the guardrails; both tools have hook systems that block, so the hooks port too. Two honest limits remain, printed by the porter: Codex edits files through `apply_patch` so `protect-adr` is best-effort there, and Cursor's `afterFileEdit` is observational so an ADR edit is flagged rather than blocked.

## v1.1.0

Repository renamed, and concrete guidance for running the harness alongside other tools.

**Changed**

- The repository is now `agent-harness-bootstrap` (was `claude-harness-bootstrap`). The name drops the vendor, matching the porting guidance below. GitHub redirects the old URL; the installed skill directories (`harness-bootstrap`, `spec-builder`) are unchanged. The release bundle is now `agent-harness-bootstrap.zip`.

**Added**

- README: how to run the two skills without clashing with other installed skills - invoke `/harness-bootstrap` and `/spec-builder` by name, and rely on the scaffolder writing only into the target repo and never overwriting a file.
- README: how to use the generated harness with Cursor and Codex. Codex reads the generated `AGENTS.md` natively; Cursor reads `AGENTS.md` and `.cursor/rules/*.mdc`, with a `paths:` to `globs:` mapping. The rules port; the hooks and deny list do not, so those tools get the guidance without the enforcement.

## v1.0.1

Fixes diagrams that did not render, including in the specs this skill generates for you.

**Fixed**

- Mermaid diagrams failed with "Unable to render rich display" on GitHub. A label containing an angle-bracket placeholder, such as `<name>` or `<actor>`, is parsed as an HTML tag: the renderer drops the text, and GitHub fails the whole block. This affected `docs/FLOWS.md` and, more seriously, six `spec-builder` section templates - so every spec set generated from them shipped broken diagrams. Placeholders in mermaid labels are now uppercase words with no angle brackets.
- `spec-builder/assets/specs/09-integration-interface.md` used `--|"text"|` for an edge, which is not a valid mermaid link. It is now a bidirectional arrow.
- `docs/FLOWS.md` carried a stale rule breakdown (`four unconditional, seven path-scoped, 77% kept out of the session`). The real figures are 6, 8 and 66%.
- The CHANGELOG said 13 commands. There are 14.

**Added**

- `docs/assets/generation-and-constraint.svg` - where the agents, rules, commands and hooks come from, and how they hold each other in check. Nothing generated is invented: each artifact traces to the codebase, the specs, or a human answer.
- `scripts/check_mermaid.py` now lints for the two failures that `mermaid-cli` renders happily but GitHub rejects: an angle-bracket token in a label, and a semicolon inside a message.
- `scripts/check_numbers.py` derives the artifact counts from the assets directory and the percentages from `benchmark.py`, then fails on any document that contradicts them. It scans every document rather than a hand-maintained list, which is how the stale figures in `FLOWS.md` survived.

## v1.0.0

First release. Two Claude Code skills: one writes the spec an agent can work from, the other builds
the harness the agent runs inside.

**Skills**

- `spec-builder` - a 13-section BA specification set under `docs/specs/`, built from an idea, a transcript, meeting notes, or legacy docs. Stable IDs and anchors, mandatory security NFRs, five-way traceability. It never invents a requirement: anything unstated becomes a flagged open issue. Standards basis in `ba-standards.md` (ISO/IEC/IEEE 29148, BABOK v3, ISO 25010:2023, MoSCoW, Cockburn, OWASP LLM Top 10).
- `harness-bootstrap` - generates `.claude/` (`15 agents, 15 rules, 21 commands, 9 hooks`, `settings.json`), the `docs/` tree, and `AGENTS.md` + `CLAUDE.md`. Reads an existing codebase first and reconciles rather than overwrites. Has a read-only audit mode for source that agents must never modify.

**Enforcement, not advice**

- 9 hooks block bad actions before they happen: reading `.env` or a private key, committing to the default branch, editing an Accepted ADR, an AI-attribution trailer, a non-conventional commit message, or an off-roster agent spawn.
- `permissions.deny` covers secrets and any path classified as Restricted, so an agent cannot send data it cannot open.
- `python eval/guardrail_eval.py` fires 21 payloads (11 must-block, 10 must-allow) at a real generated harness: `33/33` correct. The guardrails are shell scripts, so the result does not change with the model.

**State on disk, not in context**

- `docs/tasks/` is a board plus one file per task, with a session log the agent writes as it works. A fresh agent with an empty context resumes from it after a compaction, a session end, or a dead IDE. Documented in `docs/CONTEXT-MANAGEMENT.md`.

**Cost as a decision**

- Every agent carries an explicit `model:`, `effort:`, a narrow `tools:` grant and `maxTurns`. An unset `model:` inherits the caller's tier, which bills mechanical work at Opus rates.
- 9 of 15 rules are path-scoped, keeping `66%` of rule content out of the default session.
- Assets are real files copied by `scripts/scaffold.py` rather than prose the model retypes: 64% less to read and 85% less to author than the predecessor skill. Figures from `benchmark/benchmark.py`.

**Governance**

- `model-policy.md` - data classification decides which model may process what. The classification table is the policy; the deny list is the control.
- `ip-compliance.md` - dependency licence allow/deny, the AGPL-on-SaaS trigger, a diff check for the reviewers.
- `ai-governance.md` - which actions need a human who saw the specific action.

**Tooling**

- `scripts/package.py` builds the release artifacts and refuses on a bad semver, a missing changelog section, or an archive that would drop loose files into the skills folder.
- CI runs the guardrail eval, a scaffold matrix on Linux and Windows, a mermaid render check, and a check that every figure in the docs matches what the scripts print.

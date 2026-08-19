# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

Every release ships installable `.zip` artifacts with a `VERSION` file inside each skill. See
[`docs/RELEASING.md`](docs/RELEASING.md).

## Unreleased

Documentation and instruction tuning from a user's-seat audit. No skill logic changed.

### Changed

- The plugin marketplace is now the FIRST install route in the README (both languages), the
  wiki and `docs/PLUGIN.md` - it is the path with working updates, so it leads. The zip stays
  fully supported as the offline, pinned route.
- Source routing became a visible value instead of an internal mechanism: a symptom row in the
  README's opening table ("it read my scanned PDF and wrote a spec from three words"), a card
  bullet on both landing pages, a wiki FAQ entry, and a "What you will be asked" paragraph
  describing the per-source plan the user sees.
- The source-reading step gained a user-visible checkpoint: the skill now shows the one-line
  per-source plan (reader chosen, or unreadable and why) BEFORE asking anything, and is
  explicitly forbidden from narrating file-by-file progress - the plan table and the final
  summary are its only two progress surfaces.

## v1.14.0

The spec set grows a module axis, the section questionnaire becomes a gate that refuses, and
spec-builder finally reads the documents it always claimed to. Plus a second distribution
channel: both skills install and update as Claude Code plugins.

### Specs know what a module is

Asking for one module's spec used to produce a flat, undifferentiated tree, because the system
had no concept of a module.

- **Folders**: `docs/specs/modules/<folder>/` holds a module's own sections (05, 07, 08, 09,
  10); the cross-cutting ones stay at the root. `scaffold.py --module BLG:billing` does the
  placement. The flat form stays valid forever - no forced migration.
- **IDs carry the module**: `FR-BLG-01`, on the exact pattern `NFR-SEC-01` already used. This is
  not a style choice: the docs graph is flat, and two modules that each defined a bare `FR-01`
  were silently MERGED into one node - one module's requirement demoted to a mention of the
  other's, no error, no warning. The graph regex now recognises the segment on every prefix.
- **Module scaffolds arrive pre-seeded**: sample IDs already carry the code, links to root
  sections already point two levels up. An unfilled module cannot reproduce the merge.
- **The ID table and the graph regex are now held together by a gate** (`check_id_table.py`),
  landed BEFORE the regex change it exists to police. The constraint used to be a sentence.
- Dev agents own their module's spec folder: roster derivation, the dev-agent template and the
  Inventory Report's module mapping now connect code modules to spec modules.

### The section questionnaire became a mechanism

The selective-sections questionnaire has existed since v1.8.0 - as prose, which a real run
skipped, scaffolding everything flat. `scaffold.py` now REFUSES to write a section without
`docs/specs/.sections.json` recording what was selected, what was excluded, and a reason per
decision. `check_sections.py` proves every refusal branch still fires, fixture-style, in CI.

### spec-builder reads real documents

The skill promised it worked from "a PRD, legacy docs" while containing zero code that reads
pdf, docx, xlsx or pptx. The routing mechanism is distilled from the docs-to-knowledge skill
(701 lines against its 2,348): per-source strategy with a reason string, capability detection
that degrades honestly, and the branch that matters most - a scanned PDF under 80 chars/page
routes to vision instead of silently returning almost nothing for a model to fill with
invention. A source nothing can read becomes an `OI-nn` in section 11, never a silent gap.

### Distribution: plugins, in parallel with the zips

`/plugin marketplace add nguyenhx2/agent-harness-bootstrap` then
`/plugin install harness-bootstrap@agent-harness-bootstrap`. Both skills auto-load as
single-skill plugins pointing at the existing directories - verified by installing, not by
reading the docs. Updates arrive when the marketplace version bumps, and `validate_release.py`
now fails a release that bumps the skills but not the marketplace. The zips remain the
offline, pinned path; nothing about them changed.

### Fixed since v1.13.0 (shipped on main before this tag)

- The Japanese README embedded the ENGLISH flagship GIF, and the deck played English MP4s to a
  reader who had chosen Japanese; no URL could link into the gallery or deck in a given
  language. Both now honour `?lang=`, and every Japanese page links with it.
- The figure gate was blind to every bolded number: `**63%**` put the emphasis marks between
  the figure and the phrase identifying the claim, so the pattern matched nothing in the two
  READMEs. Twelve stale figures across nine files, all found by the repaired gate itself.
- Clip 05 claimed spec-builder scaffolds "the 13 sections"; sections have been selective since
  v1.8.0. Re-rendered in both languages, verified by reading the shipped pixels.
- `check_media.py` had no self-test - the exact "green and useless" mode it polices. It now
  proves all three of its branches fire, on every invocation.

## v1.13.0

Static analysis, a generated wiki, a public board, and a testing rule that finally says what a
test is for. Most of the change to the harness itself is deletion.

### Testing: less of it, and better aimed

The harness was asking for tests nobody needed. Counted across the shipped default, the mocking
rule appeared in 8 files, the criterion-to-test mapping in 6, and a coverage target in 4 - a
target the intake never asks for, so a model invented the number and four files repeated it as
policy while `/test` turned it into a per-run ratchet.

- **The coverage target is gone.** Published comparisons found every arm hitting 92 to 100%
  coverage while their bug counts spread widely, so the number was never evidence.
- **1:1 was a floor; it is now a bound.** Every criterion is pinned by at least one test, one test
  may pin several, and a criterion already pinned does not get a second.
- **What earns a test is a decision procedure** with three admission questions and a retention
  rule that says plainly that deleting a redundant test is normal work.
- **`/scaffold-feature` stops manufacturing a failing test** on the DDD path - a test written
  against a module with no behaviour, before the design pass runs, is a test written to be
  rewritten.
- A test's expected value must come from the acceptance criterion. "I ran it and this is what it
  returned" is how a bug becomes a fixture.

### Fixed, and these were silent

- **The two graph scanners disagreed four ways.** SCHEMA.md promises `harness-graph.py` and
  `harness-view scan` write identical bytes. A `files` count crashed the Python side outright, a
  `[from, to]` edge pair was silently dropped by it, a YAML block list of tools came out as one
  item with the dash attached, and on Windows it wrote CRLF against the Rust side's LF.
- **CI proved one hook flavour while everything published claimed two.** Turning on the second
  found a real defect in the first minute: `rtk-rewrite.ps1` relayed through `cmd.exe`, which does
  not exist off Windows.
- **`port.py` overwrote hand edits**, contradicting the invariant the scaffolder states twice. It
  now reports ADDED / KEPT / CONFLICT and exits non-zero while a conflict stands.
- **Two claims in the repo were false.** Both Cursor and Codex now expose subagent-start hooks, so
  the spawn boundary is reachable on both, though equivalent on neither yet.
- Four checks were green without testing anything, including one written this cycle. Each now
  carries a mutation test proving it fails on the input it missed.

### Added

- **CodeQL** for actions, python, rust and javascript-typescript. Its first run found five real
  findings, all resolved. The viewer's UI moved into real `.js` files so it can be analysed at all.
- **A generated wiki**, published automatically on every merge. Five reference pages are derived
  from the assets, so their counts cannot drift; the builder validates its own output.
- **Target-tool detection** from ranked evidence, persisted as flags rather than asked again.
- **A Command Steps panel** in `harness-view`, and `serve` now starts without a harness so the
  viewer can be pointed anywhere.
- Guardrail eval: 107/107 per hook flavour, 214/214 across both, now genuinely run by CI.

## v1.12.1

A patch release. v1.12.0 shipped a Cursor adapter that could not run outside Windows, and a set of
published figures that had drifted away from the suites they describe.

### Fixed

- **The ported Cursor adapter crashed on macOS and Linux.** It invoked PowerShell by the name
  `powershell`, which exists only on Windows; everywhere else the binary is `pwsh`. A harness
  ported to Cursor and then opened on another machine raised a traceback on every tool call, so
  the guard never ran. It now tries every candidate name, and denies with an actionable message
  when none is present rather than allowing the call it could not evaluate.
- **Eight published figures contradicted the suites they describe.** The eval split was quoted as
  "15 must-block, 25 must-allow" beside a 107/107 the pair does not add up to, the port adapter
  self-test as 5/5 for a suite of 18, and Baseline A as 15 payloads of 69 when it replays 22 of
  107. Each figure now has a constant that its own script asserts on every run.
- **The figure checker could not see a claim whose subject sat in backticks.** It blanked inline
  code spans before building context, which erased the words identifying what a number referred
  to. That is why "5/5" survived in the release skill's own quality gate.

Guardrail eval: 107/107 per hook flavour, 214/214 across both. Port adapter self-test: 18/18.

## v1.12.0

A security audit of both skills found three controls that were installed but never wired, and this
release closes them. It also gives agents the git tooling they were always told to use, and adds an
assessment engine that would have caught the whole class earlier.

### Fixed, and these matter

- **A command prefix defeated the commit and push guards.** The pattern anchored on `git commit` at
  the start of a command, so anything in front of it walked through. This was never about one tool:
  `env git commit`, `time git push`, or any wrapper a team installs tomorrow had the same effect.
- **`protect-secrets` matched read verbs, not the file.** It carried a closed list of ways to read a
  file, so any reader not on the list read secrets freely. It now matches the file being touched,
  which is the primitive that does not need to predict every verb.
- **`env-read.py` leaked the values it promised never to print.** Its `run` subcommand handed env
  values to any child command with stdout inherited, while the docstring said values are never
  printed. Values are now redacted on the way out, and the docstring says exactly what redaction
  does and does not cover.
- **Agents were blocked from env they legitimately needed.** The deny rule matched `.env.example`,
  the one file every block message tells the agent to read. That is the reported failure, and the
  cause was that no test covered the allow side. The deny list now names value-bearing files, and
  the eval covers reading the example file, seeding a local one, and running with one loaded.
- **The Cursor adapter allowed everything on Windows** while printing that it blocked, because the
  hook lookup was hardcoded to one flavour and the self-test only ever ran the other.
- **The task board directory that arms the spawn check was never created**, so the check was inert
  from the moment of install. A missing board now blocks rather than allows.
- An Accepted ADR could be edited under a translating shell, because one guard normalised the
  working directory but not an absolute file path. Found only because the Windows self-test was
  added above.

### Added

- **`harness-view assess`** and an Assess tab: a deterministic engine that scores a harness against
  this project's own quality gate and names what is wrong, with a link to the offending node. No
  model is involved, so a browser and a CI pipeline cannot disagree. Run against three real
  harnesses it scored the generated one 99 and two hand-maintained ones 79 and 64.
- **A wiring gate.** Every installed hook must be registered and every directory a hook keys off
  must exist. That single check covers three of the failures above.
- **Git platform support for GitHub, GitLab and Bitbucket.** The harness previously told agents to
  open and merge pull requests without giving them a command to do it. Detection ranks its evidence
  rather than trusting the remote, and asks when the signals disagree. Bitbucket has no first-party
  CLI of this shape, so it pushes the branch and hands the human the URL rather than pretending.
- **Skills in the graph**, so you can see which are installed and which are actually wired to a seat.
- **`rtk`, opt-in and off by default**, behind a wrapper hook we own so it can be disabled through
  `/harness-toggle` and tested by the eval. The wrapper refuses to touch any command the guards
  watch, so the compressor can never be the reason a guard did not fire.
- **An output-style rule** adapted from `i-have-adhd` under the `terse` flag.
- Wider stack detection: Python, Ruby, .NET, Java and Kotlin, and monorepo markers. Marketplace
  catalogs feed skill suggestions, and installing anything remains the user's explicit choice.
- Questionnaires are now asked in the language the user writes in, inferred rather than asked.

### Not integrated, deliberately

`caveman` was evaluated and rejected. Its compression engine is BSL-1.1, and the `ip-compliance`
rule this skill installs into other people's repositories denies BSL by name. Shipping it would
have contradicted the rule we ask others to keep.

Guardrail eval: 107/107 per hook flavour, 214/214 across both.

## v1.11.1

- `harness-view` reads JSON and YAML properly. A settings file opens as a collapsible, coloured
  tree rather than one unreadable paragraph, and an unparseable file says why instead of failing
  silently.
- Fixed the inspection panel's layout: the value sat at the middle of the row and the separator
  came apart, because the key cell had been turned into a flex container and a flex cell stops
  being a table cell.

## v1.11.0

`harness-view` can now tell you whether a harness is any good, not just show you its shape.

- **A harness assessment, scored by logic rather than opinion.** A new tab and a
  `harness-view assess` command grade a repo against the quality gate this project publishes:
  agents without an explicit model or effort, rules that load in every session, reviewers holding
  write access, hooks registered but missing from disk, tasks owned by seats that left the roster.
  Every finding names its file and jumps to the node. No model is consulted, so the same numbers
  come out in a browser and in CI, and the command fails the build on a high finding.
- Run against three real harnesses it produced a spread worth the effort: the scaffolder's own
  output scored 99, while two hand-maintained ones scored 79 and 64. The lower two had genuinely
  drifted: renamed agent seats the task board never followed, and eighteen rules loading in every
  single session at 73 KB a time.
- The score is deliberately five category numbers rather than one verdict, the arithmetic is shown,
  and the tab carries a list of what the score does not measure.
- The inspection panel gained icons and colour that carry meaning: destructive actions look
  destructive, and task status uses the same colour constant as the graph so the two cannot drift.

### Fixed

- Task-list checkboxes in the file preview rendered as wide empty text boxes, because the sanitiser
  strips `type` from a form control regardless of the allow-list. The preview no longer contains
  form controls at all.
- A table that ends early now explains itself. The cause is a blank line inside the table in the
  source file, which is where GFM ends a table and where GitHub ends it too, so the fix is to name
  the problem rather than to render it differently from GitHub.

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

Guardrail eval: 107/107 per hook flavor, 214/214 across both.

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

Guardrail eval: 107/107 per hook flavor, 214/214 across both. Read path 45 percent below the
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

- `9 hooks` block bad actions before they happen: reading `.env` or a private key, committing to the default branch, editing an Accepted ADR, an AI-attribution trailer, a non-conventional commit message, or an off-roster agent spawn.
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

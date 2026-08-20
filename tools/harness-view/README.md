# harness-view

A standalone, deterministic analyzer for a repo that ran the `harness-bootstrap`
skill. It reads `.claude/` (agents, rules, commands, hooks, settings), the task
board and the code graph, and shows how everything is wired together. No AI
involved - it only reads files and reports relationships.

The skill's own HTML output (`docs/context/harness-graph.html`) needs nothing
but Python and a browser; this tool is the power version: a native binary with
a live-refreshing UI, file watching, and safe runtime toggles.

## Install and run

There are three ways to run it. They all produce the same tool; pick whichever
suits you. The web UI is compiled into the executable, so no route needs Python,
Node, or any runtime install.

### 1. Download a prebuilt build (no toolchain)

Every release attaches a standalone executable per platform, each built on that
platform's own runner:

| Platform | Asset |
|---|---|
| Windows x86_64 | `harness-view-<version>-x86_64-pc-windows-msvc.zip` |
| macOS Apple Silicon | `harness-view-<version>-aarch64-apple-darwin.tar.gz` |
| macOS Intel | `harness-view-<version>-x86_64-apple-darwin.tar.gz` |
| Linux x86_64 | `harness-view-<version>-x86_64-unknown-linux-gnu.tar.gz` |

Each archive contains the binary, this README and `SCHEMA.md`, and a `.sha256`
sits beside it on the release page.

Windows (PowerShell):

```powershell
Expand-Archive harness-view-1.8.2-x86_64-pc-windows-msvc.zip -DestinationPath .
cd harness-view-1.8.2-x86_64-pc-windows-msvc
.\harness-view.exe serve D:\Projects\my-repo
```

macOS and Linux:

```bash
tar xzf harness-view-1.8.2-x86_64-unknown-linux-gnu.tar.gz
cd harness-view-1.8.2-x86_64-unknown-linux-gnu
./harness-view serve ~/projects/my-repo
```

On macOS the binary is unsigned, so Gatekeeper quarantines a downloaded file.
Clear it once with `xattr -d com.apple.quarantine ./harness-view`, or build from
source instead.

### 2. Double-click it (Windows)

Drop `harness-view.exe` anywhere and double-click it. With no arguments it serves
the current directory, prints the URL, and opens your browser. The console window
stays open while the server runs; closing it stops the server.

Where you put the executable does not matter. If the folder it starts in has no
`.claude/`, it says so on the console and the page opens on its **No folder
loaded** state - use **Browse** to pick a repository, and the graph appears. Only
`scan`, `assess` and `watch` still refuse to run without a `.claude/`, because
each of those answers a question about one named path and an empty answer would
look like a result.

This applies **only** to the no-argument launch. Every explicit invocation
behaves exactly as it always has: nothing opens a browser, nothing pauses.

### 3. Build from source (needs Rust)

```
cargo install --path tools/harness-view
```

### Everyday invocations

```
harness-view                              # serve the current folder, open a browser
harness-view serve .                      # serve the current folder, no browser
harness-view serve /path/to/repo --port 8080
harness-view scan /path/to/repo
harness-view watch /path/to/repo
harness-view --version                    # also shown in the page footer
harness-view --help
```

### Pointing it at other repos

One running server can inspect several projects. Either type the path into the
header box (Windows `D:\Projects\x` and `D:/Projects/x` both work) or press
**Browse** and walk the filesystem: folders that are themselves harnesses are
marked, and recently opened folders are listed for one-click return and can be
removed individually or cleared. That list lives in the browser, never on disk.
Browsing is served by `GET /browse?path=<dir>`, which returns directory names
only - no file names, no contents - because a browser cannot give a page a real
filesystem path (`showDirectoryPicker()` yields a handle without one). Under the hood that is `GET /graph.json?root=<path>`; a
path that does not exist or has no `.claude/` returns HTTP 400 with the reason
shown in the page, and the previous graph stays on screen.

### Safety, in one place

- The server binds to `127.0.0.1` only. It is a local tool, not a service to
  expose; there is no authentication because there is no remote surface.
- Mutating and file-reading endpoints require same-origin browser requests
  (`Origin` and `Sec-Fetch-Site` checked, `Content-Type: application/json` on
  `POST`), so another open tab cannot drive it.
- `GET /file` is read-only and limited to `.claude/` and `docs/`, capped at
  256 KB, always served as `text/plain` with `nosniff`.
- `GET /browse` returns subdirectory names for navigation only, never file names
  or contents, and is refused cross-origin like the rest.
- Rendered markdown is sanitised with DOMPurify against an allow-list before it
  reaches the page, because the file being previewed comes from the repository
  under inspection and the page is same-origin with `POST /toggle`. Raw mode is
  inserted as text and never parsed.
- Toggling is tiered: HARD-protected controls need a confirmation phrase typed
  literally, SOFT-protected ones need an explicit acknowledgement, and roster
  seats are at least SOFT. Full detail under [Runtime toggles](#runtime-toggles).
- `POST /command` writes a command file back after a step edit. It takes a bare
  command NAME, never a path, so the only thing it can write is
  `.claude/commands/<name>.md`; it is capped at 512 KB and refuses an empty
  body. Full detail under [Editing command steps](#editing-command-steps).

## Version and metadata

The crate version tracks the repo release version; `scripts/validate_release.py`
fails the build when the two drift, so a downloaded binary cannot report a
version the release never had. On Windows it is compiled into a real VERSIONINFO
resource, so `Properties -> Details` shows the product name, description and file
version, and Explorer shows the application icon. `--version` and the served page
footer report the same string.

The icon is generated from the project mark (`docs/assets/logo-mark.svg`) by
`scripts/make_icons.py`; regenerate it rather than editing the binaries by hand.

## Commands

```
harness-view scan   [path] [-o out.json]  # write .claude/state/harness-graph.json
harness-view serve  [path] [--port 7420]  # local web UI at http://127.0.0.1:7420/
harness-view watch  [path]                # rebuild the graph on .claude/ or docs/ changes
harness-view assess [path] [--json]       # score the harness; exit 1 on a high finding
```

What each one actually prints, against a real harness:

```
$ harness-view scan D:/Projects/msboost
harness-view: 172 nodes, 505 edges -> D:\Projects\msboost\.claude\state\harness-graph.json

$ harness-view serve D:/Projects/msboost --port 7420
harness-view: serving D:\Projects\msboost on http://127.0.0.1:7420/

$ harness-view watch D:/Projects/msboost
harness-view: watching D:\Projects\msboost (Ctrl+C to stop)
harness-view: rebuilt (172 nodes, 505 edges)
```

`scan` writes a file and exits, which is the form to use in a script or a hook.
`serve` and `watch` stay in the foreground until interrupted.

- `scan` emits the graph described in [SCHEMA.md](SCHEMA.md) (schema version 1,
  shared with the skill's Python scanner). Output is byte-stable: sorted nodes,
  sorted edges, sorted keys, no timestamps.
- `serve` renders two views of the same graph: **Flow** (layered left to right:
  rules -> hooks and settings -> agents -> merge-request gate -> human ->
  commands, with edge-type labels) and **Graph** (force-directed). The legend
  toggles node types; modules, tasks and scripts are hidden by default. Every
  request to `/graph.json` re-scans, so the page is always current; an optional
  10 second auto-refresh keeps it live. Clicking a node traces its connected
  subgraph: the node, its neighbours, and the edges between any two of them are
  drawn with a marching dash while everything unrelated fades back. Hooks carry
  a `PRE`/`POST`/`STOP` badge for the event they fire on, blocking hooks in
  red; tasks carry their board status; a disabled item is dashed, red-bordered
  and struck through. A third **Master plan** tab appears only when the repo has
  `docs/tasks/master-plan.md`.
- The path box in the header re-points the viewer at any repo with a `.claude/`
  folder, so one running server can inspect several projects. Recent paths are
  remembered in the browser, never on disk.
- `watch` uses OS file notifications and rewrites
  `.claude/state/harness-graph.json` on every change burst (500 ms debounce).
  Events under `.claude/state/` are ignored so the rebuild never re-triggers
  itself.

## Assessment

`assess` scores a harness against the quality gate that `harness-bootstrap`
already asserts, and reports what it saw with the file that proves it. It is a
plain rules engine: no model, no network, no judgment calls. The same engine
backs the **Assess** tab in the web UI and `GET /assess?root=<path>`, so a
browser and a CI job cannot disagree about the same repo.

```
$ harness-view assess D:/Projects/msboost
harness assessment: D:/Projects/msboost
  overall 64/100   high 0  medium 15  low 55
    Board health    95/100  (1 findings)
    Cost control     0/100  (33 findings)
    Docs quality    28/100  (36 findings)
    Safety         100/100  (0 findings)
    Traceability   100/100  (0 findings)
```

It exits 1 when any high finding is outstanding, so it can gate a pipeline:

```
harness-view assess . --json > assessment.json   # exit 1 blocks the build
```

### What it checks

| Category | Checks |
|---|---|
| Safety | reviewers hold no `Edit`/`Write`; only the orchestrator holds `Agent`; registered hooks exist on disk and hook files are registered; the four guardrail layers are present (deny rules, a blocking hook, `agent-guardrails.md`, a review gate) |
| Cost control | every agent pins `model` and `effort`; every agent has an explicit `tools` list; every rule that can be path-scoped carries `paths:` |
| Traceability | tasks are owned by seats that exist; commands do not run scripts that are absent |
| Board health | Blocked tasks name what would unblock them; tasks carry a status |
| Docs quality | no blank line inside a Markdown table (it silently ends the table on GitHub and here) |

### What the score is, and is not

Each category starts at 100 and loses 12 per high finding, 5 per medium and 2
per low, floored at 0. The overall figure is the plain mean of the five. Those
weights are a stated convention, not a measurement, and the UI shows the
derivation rather than hiding it behind one number.

It does not measure whether the rules say anything useful for your codebase,
whether an agent's scope matches how the code is really organised, whether a
hook that exists actually blocks what it claims to, or anything at all about
code quality. A clean report means every rule here passed, not that the harness
is good.

### Findings link back to the graph

Every finding that names a node carries a **show in graph** button: it unhides
that node type if you had filtered it out, switches to the graph, selects the
node and lights its connections. A finding you cannot locate is a complaint,
not a report.

## Runtime toggles

The details panel of `serve` can disable or enable rules, commands and hooks.
It uses the same contract as the harness's `/harness-toggle` command:

- rules and commands move between `.claude/<kind>/X.md` and
  `.claude/disabled/<kind>/X.md`;
- hooks also have their `settings.json` registration objects removed and stored
  verbatim (with position) in `.claude/disabled.json`, so enabling restores the
  registration exactly where it was;
- `.claude/disabled.json` is the committed record: atomic writes, sorted keys,
  no dates.

Roster seats toggle here too: a parked agent moves to
`.claude/disabled/agents/X.md` and the graph greys it out, exactly like a rule.
Parking a seat is reversible and recorded; ADDING or RETIRING one is still a
roster change and goes through `/harness-bootstrap:harness-update`.

Safety model, in two tiers:

**HARD** - the `protect-secrets` and `guard-agent-spawn` hooks, the
`security-privacy` and `agent-guardrails` rules, the `/review-changes` command,
and the `orchestrator`, `code-reviewer`, `security-reviewer`, `reviewer` and
`spec-guardian` seats. Refused with HTTP 403 unless the request carries
`confirm_hard` holding the literal phrase `disable <name>`. The page prompts for
it and sends what was typed, byte for byte: nothing is trimmed or case-folded, so
`Disable x` and `disable x ` are both refused again. This is the same gate
`/harness-bootstrap:harness-toggle` applies as `--confirm "disable <name>"`. In
the CLI the rule is that the model must never compose the phrase on the user's
behalf; in the browser there is no model in the loop at all, so the human typing
it *is* the gate rather than a proxy for it.

**SOFT** - the `guard-main-commit`, `check-commit-msg` and `protect-adr` hooks,
the `ai-governance` rule, and **every** agent seat (by category, not by name: the
orchestrator's routing table still lists it). Refused with HTTP 409 until the
request carries `confirm_soft: true`; the UI asks for that explicitly. A HARD
seat needs both flags, because it is in both tiers.

Enabling is never gated. Restoring a control is not the risk the tiers exist for.

### The endpoint

`POST /toggle` with a JSON body:

```json
{"kind": "rule|command|hook|agent", "name": "<bare name>", "enable": false,
 "reason": "optional", "confirm_soft": false, "confirm_hard": ""}
```

The endpoint only accepts same-origin browser requests: a request with a
foreign `Origin` or a `Sec-Fetch-Site` other than `same-origin`/`none`, or
without `Content-Type: application/json`, is refused with 403. This stops a
page open in another tab from silently mutating `.claude/` while `serve` runs.

### Reading a file

`GET /file?root=<repo>&path=<repo-relative path>` backs the sidebar's Preview
and the Master plan tab. It is read-only and deliberately narrow:

- only `.claude/` and `docs/` are readable - nothing else in the repo is served
- both sides are canonicalized and the result must still sit inside the root,
  so `..`, an absolute path, and a symlink pointing out of the tree are all
  refused by the same check rather than by pattern-matching the string
- the body is capped at 256 KB and truncated with a visible marker
- it is always `text/plain` with `X-Content-Type-Options: nosniff`, never
  `text/html`, and the page renders it with `textContent`
- the same same-origin rules as `/toggle` apply

## Editing command steps

Selecting a command reads its file and renders the numbered steps as a chain of
cards. The chain is editable:

- **Reorder** - drag a step's number. A step only moves inside its own group, so
  a precondition can never be dropped into the procedure as an action.
- **Switch off** - `Off` comments a step out in place, wrapped in
  `<!-- harness-view:disabled-step ... -->`. `On` puts it back exactly where it
  was. The steps still standing renumber around the gap.
- **Retitle** - `Edit` opens the step's own text. `Apply` is local.
- **Save** - one write for everything unsaved. `Revert` discards it all. The bar
  only exists while something is unsaved, so its presence is the dirty flag.

Nothing reaches disk until Save, so a mis-drop costs a Revert rather than a file.

**What a save rewrites.** Only the line spans the steps occupy. Frontmatter,
headings, the prose between groups, the trailing text and every byte the panel
never showed are passed through untouched, because serialization replaces spans
rather than regenerating the document from the parse tree. An unedited step is
written back as the bytes it arrived as, which is what makes the guarantee
testable: `serializing_an_untouched_parse_returns_the_file_unchanged` parses and
re-serializes every fixture command and asserts the result is byte-identical,
line endings included. Two more tests pin that switching a step off and back on
restores the original, and that reordering leaves a section's closing prose at
the end instead of dragging it up the page behind the step it was attached to.

**What "off" is, honestly.** An HTML comment removes a step from the rendered
procedure and records the intent. It does not stop a model that reads the raw
file from seeing the text. It is a reversible edit, not an enforcement boundary -
the enforcement boundary is still `POST /toggle`, which quarantines whole files
out of the tree. A step whose own text contains `-->` cannot be wrapped at all;
the control is disabled up front with that as its tooltip rather than writing a
file whose comment block ends early.

### The endpoint

`POST /command` with a JSON body:

```json
{"name": "<bare command name>", "content": "<the whole file>", "root": "<repo>"}
```

Same gate as `POST /toggle`: same-origin only, `Content-Type: application/json`,
plain-text refusals so the page can show them verbatim. It takes a NAME and
builds the path itself, so `..`, a separator, or a drive letter fail the
character check before any path exists; the only file it can write is
`.claude/commands/<name>.md`. A disabled command is not editable - enable it
first. Content is capped at 512 KB, and an empty body is refused: emptying a
command is not an edit anyone meant, and removing one is `POST /toggle`'s job.

## Markdown rendering

Files opened in the sidebar and the master-plan tab are rendered by
[marked](https://github.com/markedjs/marked) and sanitised by
[DOMPurify](https://github.com/cure53/DOMPurify). Both are vendored under
`vendor/` and inlined into the page, so the viewer still makes no network
request and there is no build step. Versions, licences and provenance are in
[`vendor/README.md`](vendor/README.md). The icon button beside **Hide file**
switches between the formatted view and the raw markdown, and the two surfaces
remember that choice separately.

## Development

```
cargo test          # scanner fixtures, determinism, toggle round trips
cargo build --release
```

Dependencies are deliberately small and auditable: `serde_json`, `tiny_http`,
`notify`.

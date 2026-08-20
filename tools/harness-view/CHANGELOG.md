# Changelog

All notable changes to the `harness-view` tool are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).
This tool is versioned and released together with the two skills under one repo version - see
[`docs/RELEASING.md`](../../docs/RELEASING.md). Its `Cargo.toml` version is gate-enforced against
that number, so the binary can never report a version the release does not carry.

## [1.15.1] - 2026-08-20

### Fixed

- No functional change in this tool. Released with the skills' 1.15.1 to keep the versions in step.

## [1.15.0] - 2026-08-20

### Fixed

- No functional change in this tool. Released with the skills' 1.15.0 to keep the versions in
  step.

## [1.14.1] - 2026-08-20

### Fixed

- No change to the binary's behaviour. The published SCREENSHOTS of its web UI carried a
  stale version in the footer (v1.12.0 on the landing page and README while the release
  was v1.14.0) - the same burned-into-pixels drift the clips had. Retaken from this
  release's binary, with a provenance gate so a release can no longer ship them stale.

## [1.14.0] - 2026-08-20

### Fixed

- No functional change in this tool. Released with `harness-bootstrap` 1.14.0 to keep the
  versions in step.

## [1.13.0] - 2026-08-19

### Added

- A Command Steps panel: selecting a command renders its steps and the agents, commands, scripts
  and rules each one touches, every annotation clickable through to that node. Read-only, with no
  schema change and no new endpoint.
- `serve` starts without a harness and offers a folder picker, so the viewer can be pointed at any
  repository regardless of where the binary sits. `scan`, `assess` and `watch` still require one.

### Changed

- The UI moved from an inline `<script>` block into `src/ui.js` and `src/ui-steps.js`, spliced in
  at startup, so CodeQL can analyse the one page that renders repository text into a DOM.

## [1.12.1] - 2026-08-16

### Fixed

- No functional change in this tool. Released with the repo version 1.12.1.

## [1.12.0] - 2026-08-16

### Added

- `assess`, as a tab and a command: a deterministic score of a harness against the project's own
  quality gate, with every finding naming its file and linking to the node.
- Skill nodes, so you can see which installed skills are wired to a seat and which are not.

## [1.11.1] - 2026-08-16

### Added

- JSON and YAML are rendered properly instead of being dumped as one wrapped run of text. JSON
  gets a collapsible tree with coloured keys and values, collapsed where a node has many children
  so a large settings file opens as something you can scan. YAML gets syntax colouring. A file that
  does not parse falls back to its raw text with a notice carrying the parser's own message.

### Fixed

- The inspection panel put the value halfway across the row and broke the row separator into two
  pieces. The key cell had been made a flex container to lay out its icon, which takes a table cell
  out of the table's formatting context, so the declared column width was computed and then ignored.
  The value now starts right after the key and the separator spans the row.

## [1.11.0] - 2026-08-16

### Added

- An **Assess** tab and a matching `harness-view assess` command that score a harness on its own
  published quality gate: safety, cost control, traceability, board health and docs quality, each
  with the findings that produced it. Every finding names the file it came from and links to the
  offending node in the graph. The engine is plain logic with no model involved, so the browser and
  a CI pipeline cannot disagree, and `assess` exits non-zero on a high finding.
- Statistics beside the score: nodes and edges by type, agents by model tier, tasks by status,
  hooks blocking versus advisory, and the session tax in bytes that unscoped rules cost every agent
  in every session.
- Icons and meaningful colour in the inspection panel. Disable reads as destructive and Enable as a
  restore; task status reuses the exact colour constant the graph badges use, so the panel and the
  nodes can never drift apart; model and effort are coloured on a cost scale.

### Fixed

- Task-list checkboxes rendered as wide empty text boxes. DOMPurify strips `type` from an `input`
  as clobbering protection whatever the allow-list says, so every checkbox became a text field.
  Task items are now inert glyphs and form controls cannot reach the preview at all.
- A markdown table that ends early because the source file has a blank line inside it now says so
  in place, naming the file, instead of leaving the reader with a wall of raw pipes. The rendering
  itself stays faithful to the spec, because GitHub renders that file the same way.

## [1.10.0] - 2026-08-16

### Added

- A folder browser. The Browse button walks the filesystem and loads a folder, with recently opened
  folders listed and removable. A browser cannot hand a page a real filesystem path, so the server
  lists directory names for navigation; it returns names only, never file names or contents.
- Icons on the header buttons, beside the labels rather than replacing them.
- The auto-refresh interval is a setting (5s / 10s / 30s / 60s) instead of a fixed ten seconds, and
  a change takes effect immediately rather than on the next reload.

### Changed

- Markdown rendering now uses [marked](https://github.com/markedjs/marked) with output sanitised by
  [DOMPurify](https://github.com/cure53/DOMPurify), both vendored under `vendor/` and inlined into
  the page. The hand-rolled parser it replaces is deleted. Rendering a large document costs more
  than it did (the 81 KB master plan went from about 2 ms to about 30 ms), which is invisible for
  an on-demand render and buys correct GFM tables, nested lists, inline formatting and links.
  Raw mode never goes near either library and stays byte-exact.

### Fixed

- Tables in the file preview were unreadable: `#detail table` forced `width: 100%` with
  `table-layout: fixed` onto every table in the panel, including rendered markdown, so a
  many-column table collapsed into one-character columns. The metadata-table rules are now scoped
  to the metadata table, and a wide table keeps its natural width and scrolls in its own container.
- The preview was a fixed 340px box that left the rest of a tall sidebar empty. It now fills the
  space below the metadata and scrolls internally.
- Tasks overlapped each other in the Flow view. Lane width was computed from the column width with
  no reference to how wide the boxes actually were, so 378px task boxes were placed in lanes 16px
  apart: 190 overlapping pairs on one board, now zero. Lanes are sized from the real widths, task
  nodes show their id with the full title in the sidebar, and tasks are grouped by status so the
  column reads as a board.
- The graph view's node separation could not converge on a dense graph because it clamped nodes to
  the visible canvas, leaving them nowhere to move apart into.
- The auto-refresh checkbox sat above the baseline of the controls beside it.

## [1.9.0] - 2026-08-15

### Added

- Standalone builds for Windows, macOS (Intel and Apple silicon) and Linux, attached to the release
  as archives carrying the binary, its README and the schema, each with a SHA-256 file. No Rust
  toolchain and no Python needed to run one.
- The Windows executable carries real file metadata (product, file version, company, description)
  and the project icon, so Explorer and the taskbar show it properly.
- Launching the executable with no arguments serves the folder it sits in and opens a browser,
  which is what a double-click should do. Every explicit invocation is unchanged.
- An icon for the tool, derived from the repo's shield-and-eye mark by `scripts/make_icons.py`, plus
  a favicon for the served page.
- Choose a folder from the browser: type or pick a path and the viewer re-scans without a restart.
  Recent roots are remembered. A path that is not a harness reports why instead of showing nothing.
- Read the files, not just the boxes: agents, rules, commands, tasks and the master plan open in
  place, formatted by default with a one-click switch to raw markdown.
- Clicking a node lights its neighbours and the edges between them with a moving dash and fades
  everything unrelated.
- Three connection-line styles (curved, orthogonal, straight), hook nodes badged Pre / Post / Stop
  with blocking hooks marked, task nodes showing owner and status, and an optional master-plan tab.

### Fixed

- The viewer served a blank page: a JavaScript string broken across two lines killed the whole
  script, and the canvas was sized only after a successful load, so any failure left an unsized
  canvas with no error shown.
- 87 of 172 nodes were drawn off screen on a real board with no indication they existed. The view
  now scales to fit, and an over-full lane wraps instead of running off the bottom.
- Edges were drawn between node centres, so lines ran under the boxes and every arrowhead was
  hidden behind its target. Edge labels all landed on the same point.
- Panning cleared the selection being inspected.
- Nodes overlapped in the graph view because the layout treated a wide box as a point.

## [1.8.2] - 2026-08-14

### Fixed

- A command citing the skill's own `<skill>/scripts/*.py` no longer becomes a `runs` edge to a
  script that was never installed. The scanner requires the `.claude/scripts/` prefix, matching the
  Python implementation exactly on a full harness.

## [1.8.0] - 2026-08-14

### Added

- First release: a deterministic, non-AI analyzer of a repo that ran `harness-bootstrap`. `scan`
  emits the canonical `harness-graph.json`, `serve` renders it as a Flow and a Graph view with a
  toggle panel, and `watch` re-scans on change. Reads the same schema the Python twin writes.

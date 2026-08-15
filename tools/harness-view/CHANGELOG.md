# Changelog

All notable changes to the `harness-view` tool are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).
This tool is versioned and released together with the two skills under one repo version - see
[`docs/RELEASING.md`](../../docs/RELEASING.md). Its `Cargo.toml` version is gate-enforced against
that number, so the binary can never report a version the release does not carry.

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

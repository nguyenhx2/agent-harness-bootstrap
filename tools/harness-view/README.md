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

Drop `harness-view.exe` into a repo that has a `.claude/` folder and double-click
it. With no arguments it serves the current directory, prints the URL, and opens
your browser. The console window stays open while the server runs; closing it
stops the server. If the folder has no `.claude/`, it says so and waits for a
keypress instead of flashing shut.

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

One running server can inspect several projects: the path box in the header
accepts any folder containing `.claude/` (Windows `D:\Projects\x` and
`D:/Projects/x` both work), and the recent list is remembered in the browser,
never written to disk. Under the hood that is `GET /graph.json?root=<path>`; a
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
- Agents are never toggleable; HARD-protected controls are refused outright and
  SOFT-protected ones need an explicit confirmation. Full detail under
  [Runtime toggles](#runtime-toggles).

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
harness-view scan  [path] [-o out.json]   # write .claude/state/harness-graph.json
harness-view serve [path] [--port 7420]   # local web UI at http://127.0.0.1:7420/
harness-view watch [path]                 # rebuild the graph on .claude/ or docs/ changes
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

Safety model: **agents are never toggleable** (roster changes go through
`/harness-update`). HARD-protected controls - the `protect-secrets` and
`guard-agent-spawn` hooks, the `security-privacy` and `agent-guardrails` rules,
and the `/review-changes` command - are refused here with HTTP 403; disabling
one of those requires the `/harness-toggle` command, where the user must type
the confirmation phrase themselves. SOFT-protected controls - the
`guard-main-commit`, `check-commit-msg` and `protect-adr` hooks and the
`ai-governance` rule - refuse with HTTP 409 until the request carries
`confirm_soft: true`; the UI asks for that confirmation explicitly.

### The endpoint

`POST /toggle` with a JSON body:

```json
{"kind": "rule|command|hook", "name": "<bare name>", "enable": false,
 "reason": "optional", "confirm_soft": false}
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

## Development

```
cargo test          # scanner fixtures, determinism, toggle round trips
cargo build --release
```

Dependencies are deliberately small and auditable: `serde_json`, `tiny_http`,
`notify`.

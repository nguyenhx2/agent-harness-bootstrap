# Hooks

Guardrail layer 2. Ship ONE flavor per project - `.ps1` on Windows, `.sh` on macOS/Linux - and
register it from `registration.windows.json` / `registration.posix.json` (merge the `hooks` object
into `.claude/settings.json`). The two flavors are behaviorally equivalent by contract.

| Hook | Event | Matcher | Blocks / does | Flavor note |
|------|-------|---------|---------------|-------------|
| `protect-adr` | PreToolUse | `Edit\|Write` | Edits to an ADR whose on-disk `status: Accepted`. ADRs are immutable - supersede with a new one. | Both resolve `file_path` against payload `cwd`. |
| `guard-main-commit` | PreToolUse | `Bash`, `PowerShell` (`if` `*git *`) | `git commit` / `git push` - also behind git global options (`-c k=v`, `-C dir`, `--no-pager`, `--git-dir`, `--work-tree`) - while the effective branch is `{{DEFAULT_BRANCH}}` or `master`. Resolves the target dir from `cd` / `git -C` so worktrees don't misfire. | Both resolve relative target dirs against payload `cwd`. |
| `check-commit-msg` | PreToolUse | `Bash`, `PowerShell` (`if` `*git *`) | A `git commit -m` subject (global options before `commit` included) that violates conventional-commits: bad type, >72 chars, trailing period, uppercase description. | PS **must** use `-cmatch`/`-cnotmatch`; bash `grep -E` is case-sensitive already. Plain `-match` silently passes `Feat:`. |
| `protect-secrets` | PreToolUse | `Read\|Edit\|Write\|Bash\|PowerShell` | Reads/edits of `.env*` (except `.env.example`), `*.pem/key/pfx/p12`, `secrets?/` + `credentials?/` dirs, service-account JSON; shell commands that read/copy `.env` - also once the shell has rewritten the name (a glob such as `.e?v` or `.env*`, quotes split inside it, a pipe or bracket right after it) and a recursive `grep` through the working directory or a directory holding a `.env`, with no `--include` or env `--exclude`; destructive DB commands (`{{DB_RESET_PATTERN}}`). | Parity-locked: identical globs, command patterns and block conditions in both flavors. Matching is case-INSENSITIVE on purpose (`-match` / `grep -Ei`). |
| `protect-harness` | PreToolUse | `Edit\|Write\|MultiEdit\|NotebookEdit\|Bash\|PowerShell` (no `if`: a redirect target is invisible to one) | An Edit or Write to `.claude/settings.json`, `.claude/settings.local.json` or anything under `.claude/hooks/` **asks the user** (`permissionDecision: "ask"`); a shell command that writes there is **blocked**. Every other guard is only as strong as these files; `/harness-toggle` is the recorded way to switch one off and never meets this hook. | Ask for edits because `/harness-tune` edits the deny list and the spawn allowlist legitimately; block shell writes because nothing legitimate makes them and, verified live, an "ask" is waved through in `bypassPermissions` mode while an exit 2 is not. Case-insensitive in both flavors. Shell writes are matched best-effort (a writing verb or redirect next to the path). |
| `guard-agent-spawn` | PreToolUse | `Agent\|Task` | Four checks on every subagent dispatch: 1) roster membership - `subagent_type` must have a `.claude/agents/<type>.md` or be on the `spawn-allowlist`; 2) model pinning - a spawn cannot override a roster seat's `model:`; 3) task linkage - a write-capable seat (`Edit`/`Write` in `tools:`) must name a registered `TASK-NNN` in the dispatch prompt; 4) the verification ledger (`verify-plan.py --dispatch-check`, see below) - no re-run on content that passed, at most two dispatches of a seat on one content with no result, two review rounds, no identical brief, and a per-task dispatch budget. | Allowlist is `.claude/hooks/spawn-allowlist` (one type per line, `#` comments); ships with `Explore` and `Plan`. |
| `guard-agent-scope` | PreToolUse | `Edit\|Write` | Nothing - **advisory, not enforced**. The Edit/Write payload names no calling subagent (see the hook's header and "Gotchas" below), so it cannot block a write to a module a different seat owns. Instead it emits `additionalContext` when a write falls outside the sole Active task's declared "Related files and modules" AND the target module's owner (`.claude/state/code-graph.json`) differs from the task's `owner:`. Silent whenever the picture is ambiguous. | Non-blocking, always exit 0. Needs perl or python3 for the graph comparison; jq alone cannot express it (same call as `agent-history`'s transcript parsing). |
| `specs-reminder` | PostToolUse | `Edit\|Write` | Nothing. Emits `additionalContext` when `docs/specs/` changes: update `13-revision-history.md`, sync the PRD. | Non-blocking, always exit 0. |
| `graph-stale` | PostToolUse | `Edit\|Write` | Nothing. Two tiers by edited path: a harness file (`.claude/` agents/rules/commands/hooks, `settings.json`, `disabled.json`) regenerates `harness-graph.json` + its HTML immediately (cheap scan); a source file, once the module-boundary map exists, is checked with `code-graph.py --file`, and any cross-module import the map does not list is named once in `additionalContext` until the next{{#IF_PURPOSE_CODE}} `/code-graph`{{/IF_PURPOSE_CODE}} rebuild accepts it. The docs graph is not rebuilt here: it is a check run on demand (`/docs-graph`). | Non-blocking, always exit 0. Script-driven mutations (scaffold re-runs, `harness-toggle.py`) do not fire this hook - those tools regenerate the graph themselves. |
| `agent-history` | SubagentStop | `*` | Nothing. Archives each finished subagent run to `.claude/state/history/` at the detail level set in `.claude/state/history-level` (line 1: `full`/`summary`/`minimal`/`off`; line 2: retention count - only the newest N per-run files are kept, `index.md` never pruned). Missing/unreadable config means `full`/200, the historical behavior. | Non-blocking, always exit 0. Change the level with `/harness-tune` dial 6. |
| `guard-board` | PreToolUse | `Edit\|Write` | A hand edit to a task row of `docs/tasks/master-plan.md`: an Edit whose `old_string`/`new_string` touches a `\| TASK-NNN \|` row, a Write that replaces an existing board, any MultiEdit of it. Task state lives in three places (row, `status:`, folder) and `python .claude/scripts/task.py move` changes all three and reads the row back. The message names that command. | `task.py` writes through Bash, so it never meets this hook. The first Write that creates the board is allowed; so are Edits to the Phases table and prose, which have no CLI verb. |

`protect-repos` (PreToolUse `Edit|Write`, blocks writes into product-repo dirs) ships only with the
audit workspace - see `assets/audit/hooks/`.

## Opt-in hooks: one per scenario

These ship only when their flag is set, and the scaffolder registers them in `settings.json` inside
the same flag's block, so a hook is never installed without being wired. They are not in the base
`registration.*.json` files for the same reason `rtk-rewrite` is not. Each one decides
deliberately between **block** (exit 2) and **warn** (exit 0 with `additionalContext`); the
column says which and why.

| Hook | Flag | Event / matcher | Does | Block or warn, and why |
|------|------|-----------------|------|------------------------|
| `guard-destructive` | **none - ships by default** | PreToolUse `Bash\|PowerShell` | `rm -rf` on the repo root, home, `/`, a top-level system dir, a drive root or a top-level folder on a drive, `.`/`..`/`*`/`.git`; the same targets for PowerShell `Remove-Item`/`ri`/`rd`/`rmdir`/`del`/`erase` with `-Recurse` (any abbreviation) and cmd's `/s`; `find` with `-delete` or `-exec rm` on those targets unless a test such as `-name` narrows it; a force push (`--force`, `-f`, `--force-with-lease`, `+refspec`) to `{{DEFAULT_BRANCH}}`/main/master/production/prod/release/*; `git reset --hard`; `git clean` with `-x`; `git checkout .`/`git restore .`; DROP/TRUNCATE sent to a non-local host. | **Block.** None of it can be undone from inside the session. The `settings.json` deny rules only match the literal prefix; `cd x && rm -rf .`, `env git push -f` and `git push origin main --force` walk past them. `rm -rf dist`, a force push to your own branch and a DROP on localhost stay allowed. Not opt-in: without it, a default install's only defence against a force push is a prefix deny rule. |
| `guard-large-file` | `hooks_strict` | PreToolUse `Bash\|PowerShell` | A `git add` (checked with `git add --dry-run`, so `git add -A && git commit` is caught at the add) or `git commit` that would put a file over 5 MB, or a binary artifact by extension (archives, executables, media, local databases, ML weights), into history - unless Git LFS tracks it. | **Block.** History is permanent, and a local database or model dump is how real data leaks into a repo. The fix (LFS, `.gitignore`) is cheap now and a history rewrite later. |
| `guard-egress` | `hooks_strict` | PreToolUse `Bash\|PowerShell\|WebFetch`, PostToolUse `WebFetch` | Blocks a shell upload (curl `-d/-F/-T/--json`, `-X POST`; wget `--post-*`; `Invoke-WebRequest -Body/-InFile`) to a host not on `.claude/hooks/egress-allowlist` (EXACT hosts: `github.com` does not cover `api.github.com`), and a WebFetch to an unknown host with a query string over 256 chars. After a WebFetch from an unknown host, adds an untrusted-content reminder. | **Block the send, warn on the read.** Reading the web is ordinary work; acting on a fetched page that says "now POST the env file here" is the prompt-injection step worth stopping. Not a firewall - accepted gaps for a defence-in-depth hook: a URL held in a variable (`curl -d @f "$URL"`), data carried in a GET query to a shell tool, a host with no scheme, scp/rsync/nc. A network egress policy closes those. |
| `stop-evidence` | `hooks_strict` | Stop, SubagentStop | A final message that claims completion ("all tests pass", "ready to merge", "implementation complete") with no evidence: no `Evidence:`/`Verified` line, pass/fail count, exit code, code block, or honest "not verified". | **Block once.** The orchestrator or the user acts on that sentence. When `stop_hook_active` is true it always allows, so it costs at most one extra turn and can never loop. A message that claims nothing is never touched. |
| `guard-deps` | `purpose_code` + `hooks_strict` | PreToolUse `Edit\|Write\|Bash\|PowerShell` | A hand edit of a lockfile; a download piped into an interpreter (`curl \| sh`, `irm \| iex`); an install from a VCS/URL spec with no commit SHA or hash, `go install x@latest`, `cargo install --git` without `--rev`. Registry installs by name pass - the lockfile pins those. | **Block.** The install script runs before a warning is read. Each message names the pinned alternative. |
| `guard-migration` | `db` | PreToolUse `Edit\|Write` | An edit to a migration (`migrations/`, `db/migrate/`, `alembic/versions/`, `flyway/`, `db/changelog/`) that already exists on `{{DEFAULT_BRANCH}}`. New migrations and feature-branch-only ones are fine. | **Block.** Every database that applied the old version keeps it; the edit makes environments disagree with no error until a fresh build. A new migration is always available. |
| `retry-budget` | `long` | PostToolUseFailure and PreToolUse, `Bash\|PowerShell\|Edit\|MultiEdit\|Write\|WebFetch` | Counts consecutive IDENTICAL failures of one call (tool + input, minus `description`). Warns at the 2nd; blocks the next identical attempt after the 3rd. Any different call resets it; interrupts never count. | **Warn, then block.** Counting failures rather than repeats means successful polling (`gh pr checks`, a status command) is never touched; an unchanged retry of something that failed three times will fail a fourth. The message points at `task.py attempt`. |
| `compact-checkpoint` | `long` | PreCompact `manual\|auto` | Writes `.claude/state/compact-checkpoint.md`: branch, `/compact` instructions, each active task with status, owner, its `## Checkpoint` lines (from `task.py checkpoint`) and first unchecked item, and uncommitted changes. No timestamp; overwritten each time. | **Never blocks.** Blocking an automatic compaction triggered by a context-limit error fails the request outright. |
| `session-context` | `long` | SessionStart `startup\|resume\|clear\|compact` | Injects the active tasks with owner and next step (checkpoint Next step, else first unchecked item), at most 8; after a compaction, points at `.claude/state/compact-checkpoint.md`. Silent with nothing to say. | **Context only** (SessionStart cannot block). The two moments a long session loses its place - a fresh start and a compaction - are moments a hook sees and a rule does not. |
| `research-sources` | `purpose_research` | PostToolUse `Edit\|Write` | A Markdown note under `research/`, `findings/`, `notes/`, `report(s)/`, `brief(s)/`, `sources/` or `literature/` with 400+ characters and no URL, DOI, arXiv id, footnote, Sources section or explicit `Assumption:`/`Unsourced:` label. | **Warn.** Notes are written in passes - claims first, sources while checking - and blocking the draft stops the work that finds the sources. |
| `docs-links` | `purpose_docs` | PostToolUse `Edit\|Write` | Relative Markdown links whose target does not exist, resolved from the file's own directory (fenced code, schemes, `#anchors` and `/site-absolute` paths skipped). Names up to 5. | **Warn.** A restructure breaks links between its steps; blocking each write would stop the restructure. A full link check belongs in CI. |
| `secret-guard` | `hooks_strict` | UserPromptSubmit; PostToolUse `Bash\|PowerShell\|Read\|Grep` | Vendor-format keys (AWS, GitHub, GitLab, Slack, Anthropic, OpenAI, ElevenLabs, Groq, xAI, Hugging Face, npm, PyPI, SendGrid, DigitalOcean, Shopify, Stripe live, Google API and OAuth client secrets) and PEM private-key headers, in a prompt or in tool output. No generic `password=` rule. | **Block the prompt** (exit 2: it is never sent, and the user - not Claude - sees why). **Warn on output**: it is already in the transcript, so the warning stops it spreading and asks for rotation. |
| `guard-config` | `hooks_strict` | ConfigChange `user_settings\|project_settings\|local_settings` | A mid-session settings change that sets `disableAllHooks`, sets `defaultMode: bypassPermissions`, adds an allow rule that pre-approves any command (bare `Bash`/`PowerShell`; wildcard-only specifiers such as `Bash(**)`, `Bash(*:*)`, `Bash( *)`; a shell or wrapper by name such as `Bash(bash:*)`, `Bash(sh -c:*)`, `Bash(env:*)`), removes any rule from `permissions.deny` (compared with the last accepted list in `.claude/state/config-guard/`, or the committed HEAD version of project settings), unregisters a hook still installed in `.claude/hooks/`, or deletes `.claude/settings.json`. | **Block.** It switches a guard off while the work it watches is running. The change stays on disk and loads next session; `/harness-toggle` passes because it moves the file and the registration together. Claude Code shows a blocked ConfigChange to nobody, so each refusal is logged to `.claude/state/config-guard.log`. |
| `agent-trace` | `long` | SubagentStart `*`, InstructionsLoaded, PermissionDenied `*` | One line per event in `.claude/state/trace.log`: subagent starts, every rule or memory file that entered context and why (`path_glob_match`, `session_start`...), and what auto mode refused. Keeps the newest 1500 lines. | **Log only**, never in context. The only direct evidence that a path-scoped rule fired; nothing here needs Claude to act. |

Not shipped, on purpose:

- **Notification, MessageDisplay**: the exit code is ignored and they cannot reach Claude; a desktop
  ping is per-machine taste that belongs in user settings.
- **TaskCreated / TaskCompleted**: they track the TaskCreate/TaskUpdate tool list and agent teams,
  not the board. Board completion already needs a result: `task.py move <TASK-NNN> Done --note`.
- **FileChanged on env files**: it cannot block and Claude never sees it; `protect-secrets` already
  stops the reads, and `secret-guard` catches a value that gets printed anyway.
- **A turn budget**: seats carry `maxTurns`, Claude Code caps stop-hook continuations, and
  `retry-budget` covers the expensive case (the same failing call, again).
- **SubagentStop logging**: `agent-history` already archives every finished run.

## Hook map: event, flag, and when to turn it on

| Hook | Lifecycle event | Flag | Turn it on when |
|------|-----------------|------|-----------------|
| `protect-secrets` | PreToolUse | always | Always - it is the floor. |
| `protect-harness` | PreToolUse | always | Always - the floor under the floor: the files every other guard lives in. |
| `guard-agent-spawn` | PreToolUse | always | Always. |
| `guard-main-commit`, `check-commit-msg` | PreToolUse | always | Always. |
| `protect-adr`, `guard-task-scope`, `guard-board` | PreToolUse | always | Always. |
| `guard-agent-scope`, `specs-reminder`, `graph-stale` | PreToolUse / PostToolUse | always | Always (advisory only). |
| `agent-history` | SubagentStop | always | Always; tune detail with `/harness-tune`. |
| `rtk-rewrite` | PreToolUse | `rtk` | You installed `rtk` and want smaller command output. |
| `protect-repos` | PreToolUse | `audit` | Audit workspaces only. |
| `guard-destructive` | PreToolUse | always | Always - irreversible operations are baseline safety, and the deny rules are only prefix matches. |
| `guard-large-file` | PreToolUse | `hooks_strict` | The repo must stay clonable, or it sits near local databases or model files. |
| `guard-egress` | PreToolUse, PostToolUse | `hooks_strict` | Agents read the web or untrusted files and can also run `curl`. |
| `secret-guard` | UserPromptSubmit, PostToolUse | `hooks_strict` | Anyone works with live credentials nearby. |
| `guard-config` | ConfigChange | `hooks_strict` | You rely on the hooks holding for a whole session (long runs, auto mode). |
| `stop-evidence` | Stop, SubagentStop | `hooks_strict` | You act on "done" without re-checking it. |
| `guard-deps` | PreToolUse | `hooks_strict` + `purpose_code` | A code repo with a lockfile, or any supply-chain exposure. |
| `guard-migration` | PreToolUse | `db` | Automatically with a database. |
| `retry-budget` | PostToolUseFailure, PreToolUse | `long` | Sessions run long enough to loop on a failing command. |
| `compact-checkpoint` | PreCompact | `long` | Sessions run long enough to compact. |
| `session-context` | SessionStart | `long` | Work spans sessions, or compactions. |
| `agent-trace` | SubagentStart, InstructionsLoaded, PermissionDenied | `long` | You want to see which rules loaded and what ran in parallel. |
| `research-sources` | PostToolUse | `purpose_research` | A research repo. |
| `docs-links` | PostToolUse | `purpose_docs` | A documentation repo. |

## Disabling a hook

Never delete a hook file or hand-edit its `settings.json` registration to silence it. The sanctioned
path is `/harness-toggle` (`python .claude/scripts/harness-toggle.py disable hook/<name>`): it moves
both flavor files to `.claude/disabled/hooks/`, removes the registration objects and saves them
verbatim in `.claude/disabled.json` so `enable` restores them exactly, and scaffold re-runs respect
the list instead of resurrecting the hook. `protect-secrets` and `guard-agent-spawn` are
HARD-protected - the script refuses without a literal user-typed confirmation phrase. If a `--force`
scaffold or a hand edit brings a disabled hook back, `harness-toggle.py reapply` is the repair verb.

## Contract

- Payload arrives as JSON on **stdin**. Signal by **exit code**: `2` = BLOCK, with the reason on
  **stderr** (that text is what Claude sees and acts on); `0` = allow. Any other code is a hook
  FAILURE - see the next point for what that does.
- **Requires Claude Code 2.1.295 or later** for `onFailure` (the version the hooks docs name).
  Use 2.1.295+ for these registrations; an older version is expected to treat both fields as
  absent - fail-open guards, `if` not applied - but that has not been verified release by
  release, so do not rely on it.
- **A blocking guard fails CLOSED when the guard itself fails.** Every guard whose job is to block
  is registered with `"onFailure": "block"` and `"timeout": 30`: a timeout, a crash or any exit
  other than 0/2 now blocks the call instead of waving it through. This was found live: under
  load a `.ps1` guard took 13.2 s, hit the old 10 s timeout, and `Remove-Item -Recurse -Force .`
  ran. Fail-closed guards: `protect-adr`, `guard-task-scope`, `guard-board`, `protect-secrets`,
  `protect-repos`, `guard-main-commit`, `check-commit-msg`, `guard-destructive`,
  `guard-agent-spawn`, and the strict blockers `guard-large-file`, `guard-egress`, `guard-deps`,
  `guard-migration`, `secret-guard` (on UserPromptSubmit) and `guard-config`. Advisory hooks,
  loggers, `rtk-rewrite` and the cost guards (`retry-budget`) stay fail-open: a broken reminder
  must never stop work. (`onFailure` has no effect on Stop/SubagentStop, so `stop-evidence` is
  unaffected.) The eval's contract suite fails if a blocking guard loses the field or an
  advisory hook gains it.
- **A missing tool is not a failure.** When a bash guard finds no jq, perl or python3 to parse its
  payload, it prints a warning and exits 0. That is deliberate: a missing interpreter would
  otherwise turn every guard into a wall that blocks all work, and a harness that blocks
  everything gets switched off. The `settings.json` deny rules and the rules files remain the
  backstop. **One deliberate exception**: `guard-agent-spawn` refuses a dispatch whose payload it
  cannot read, because an unreadable spawn cannot be shown to name a roster seat, and letting an
  unverifiable spawn through is precisely the thing that hook exists to stop. The eval pins this
  so it stays a decision rather than an accident.
- Fast, no network, plain-ASCII messages. Blocking hooks have no side effects.
- **`if` keeps cheap calls cheap.** A handler with `"if": "<permission rule>"` only starts when the
  tool call matches. The git-only guards (`guard-main-commit`, `check-commit-msg`,
  `guard-large-file`) carry `Bash(*git *)` / `PowerShell(*git *)`, one handler per tool (an `if`
  rule names one tool). The leading `*` is deliberate: `Bash(git *)` would match
  `git -c k=v commit` and `cd x && git commit` (Claude Code checks each subcommand) but NOT
  `env git commit` or `rtk git commit` - `env` and `rtk` are not among the wrappers Claude Code
  strips - and the guards exist to catch both. `if` is best-effort: when Claude Code cannot parse
  a command it runs the hook anyway, which is the safe direction. `guard-destructive` and
  `protect-secrets` carry no `if`: they must see every command. Effect on a plain `ls` through
  the Bash tool: 4 hook processes -> 2 in a default harness, 9 -> 6 with `hooks_strict`, `long`
  and `rtk`. Fewer processes is half of it; the other half is what each one costs - see
  "Latency" below.

## Latency

Hooks run in parallel, so the slowest guard decides how long every Bash call waits, and a guard
that waits long enough gets turned off. Under load it is worse than a wait: a fail-closed guard
that reaches its 30 s timeout blocks the call, and `guard-destructive.sh` did exactly that with
four Claude Code sessions running at once on Windows, blocking every Bash call in each session.

What a hook costs is mostly the processes it starts, not what it computes. On Windows every
external process and every bash subshell (`$(...)`, `printf | grep`) costs 50-250 ms, and the old
`.sh` guards started a JSON parser plus several of those per call, two per token in
`guard-destructive`. On `.ps1`, PowerShell's own start dominates and `ConvertFrom-Json` adds a
module load.

**The fast path.** Every hook that starts on a Bash call (`protect-secrets`, `guard-destructive`,
`guard-egress`, `guard-deps`, `retry-budget`, and, behind their `if`, `guard-main-commit`,
`check-commit-msg`, `guard-large-file`) first decides the common case, "this command is not
mine", from the raw payload:

- `.sh`: `read_payload` takes stdin without a fork, and `fast_str` decodes `tool_input.command`
  with bash builtins (no subshell, no external process). `.ps1`: `Get-FastString` does the same
  before `ConvertFrom-Json` runs.
- The decode is exact or it gives up. The key must occur once; the value must be printable ASCII
  and use no JSON escape but `\" \\ \n \r \t` (everything `JSON.stringify` writes for such text).
  Anything else (non-ASCII, `\u` escapes, a duplicate key) takes the full parse.
- A hook may only **exit 0** on the fast path, and only on a test that is a necessary condition of
  every block it raises: `guard-destructive` needs a deletion verb or `git` as a token, or
  DROP/TRUNCATE; `guard-egress` a curl/wget/iwr/irm/Invoke-* word; `guard-deps` a download tool,
  `iex`, or a package manager starting a word; `protect-secrets` a `.env` or a DB-reset match;
  `retry-budget` an existing state file. Each test is written case-insensitively, or with the same
  operator the full check uses, so it is never narrower than what it fronts. Doubt falls through
  to the full parse, which is unchanged.
- `guard-destructive.sh` also does its full check on builtins (it has no `if` and its real work
  is `rm` and `git`, the commands that reach it); only a forced push's `git rev-parse` and the
  host scan after a DROP/TRUNCATE still start a process.

The eval pins both sides: the "fast path:" cases are the shapes a careless pre-check would let
through (a separator inside `\n`/`\t`, a quoted or capitalised verb, a lookalike `"command"` in the
description), and its fast-path suite runs each hook with `PATH` empty (`.sh`) or reports whether
`ConvertFrom-Json`'s module loaded (`.ps1`), so a fast path that quietly stopped deciding goes red.

**Measured 2026-10-14**, one Windows 11 machine (22 cores, heavily loaded by parallel eval runs, so
absolute numbers are high), Git Bash 5.2 and Windows PowerShell 5.1, a harness with
`hooks_strict`, `long` and `rtk`, median of 7 interleaved runs. Not a published figure: re-measure
before quoting it.

| | `.sh` before | `.sh` after | `.ps1` before | `.ps1` after |
|---|---|---|---|---|
| slowest single guard on `ls -la` | 4424 ms (`guard-egress`) | 90 ms | 466 ms | 369 ms |
| all 6 guards in parallel, `ls -la` | 5563 ms | 131 ms | 620 ms | 548 ms |
| all 9 guards in parallel, `git status` | 5125 ms | 139 ms | 1034 ms | 937 ms |
| `guard-destructive`, 4 concurrent, `git push --force-with-lease origin feat/x && rm -rf node_modules dist build/out coverage`, p95 | 12034 ms | 175 ms | 1420 ms | 1424 ms |

Through Claude Code itself (`claude -p`, haiku, three parallel `ls` calls, `.sh`): the PreToolUse
window went from 8.7 s to 1.2 s. The `.ps1` flavor still pays one PowerShell start per guard
(roughly 300 ms each on an idle machine); merging the Bash guards into one dispatcher would pay it
once, but `/harness-toggle`, `guard-config` and the graph all address hooks by file, and a
dispatcher would make disabling it disable `protect-secrets` without the HARD confirmation.

## Env files: what a seat may read, and how

A blanket block is not a policy. Seats genuinely need env values to do their work - does
`DATABASE_URL` exist in `.env.test`, run the migration with `.env.local` loaded - and a harness
that refuses all of it gets the hook switched off, which is strictly worse than a rule people can
follow. What must never happen is a VALUE reaching the transcript, because from there it is in the
archive and the provider's logs permanently.

| Action | Verdict | Why |
|---|---|---|
| Read `.env.example` | allowed | It is the tracked placeholder. It holds names, never values. |
| Read any other `.env*` | blocked | The value would land in the transcript. |
| Write or append to a local `.env.local` / `.env.dev` / `.env.test` | allowed | Setting up a dev environment is not disclosure. |
| `cp .env.example .env.local` | allowed | Seeding a local file from the placeholder. |
| Anything naming a prod/production/live/release env file | blocked | Never a target, whatever the verb. |
| `.claude/scripts/env-read.py list / check / diff` | allowed | Presence and shape, never values. |
| `.claude/scripts/env-read.py run -- <cmd>` | allowed | Values load into the child's environment; its output is captured and every value is replaced with `[redacted:KEY]` before printing. |

`env-read.py` is the sanctioned path and it is deliberately narrow: `printenv`, `env`, `set` and
inline shells (`sh -c`, `bash -c`, `powershell -c`) are refused outright, because their output IS
the secret and redacting it would leave a lie. Its honest limit is written in its own docstring:
redaction matches values literally, so a command that deliberately transforms a value before
printing it defeats it. That stops accidents and casual misuse, which is what actually happens. It
is not a sandbox, and a seat you would not trust with the value should not be given `run`.

Two layers enforce this and they must agree. `protect-secrets` matches the FILE rather than a list
of reader verbs, because a verb allowlist let `strings .env` and any wrapper through. The
`settings.json` deny rules are the speed bump behind it; they name the value-bearing files
explicitly rather than globbing `.env.*`, which used to catch `.env.example` and block the one file
every error message tells the agent to read. If you add a deny rule here, check it against the
allow cases in the guardrail eval before shipping it.

## Gotchas that bit us

- **`agent-history` is `SubagentStop`, not `PostToolUse`.** The subagent tool is `Agent` (there is
  no `Task` tool), and the `SubagentStop` payload carries **no** `tool_input`/`tool_response` - it
  has `agent_type`, `agent_id`, `agent_transcript_path`, `cwd`. A `PostToolUse` registration
  archives empty files.
- **Resolve every path against the payload's `cwd`.** The hook process's own cwd is not the
  project's; a bare relative `.claude/state/history` writes to the wrong place.
- **bash hooks need a JSON parser.** `jq` is NOT installed by default on macOS, and a missing `jq`
  would make a security hook silently allow everything. Each `.sh` falls back `jq` -> `perl`
  (core `JSON::PP`) -> `python3`, and warns on stderr if none exists. The fast path (see
  "Latency") needs none of them, so a command it can decode exactly is judged even with no parser
  installed; `guard-destructive` then still blocks, the rest still allow what is not theirs.
- **A gate regex in a variable, not inline, and never trusted on status alone.** `[[ $s =~ $re ]]`
  returns 2 for a regex the engine rejects; `fast_unmatched` allows only on status 1, so a bad
  regex reads as "maybe mine" and takes the full parse.
- **POSIX ERE has no portable `\b`** (BSD grep), so word boundaries are hand-rolled as
  `(^|[^a-zA-Z0-9_.-])` / `([^a-zA-Z0-9_-]|$)` in both flavors, keeping the regexes aligned.
- **A bash on Windows cannot always resolve a `C:/x` `cwd` in a file test or hand it to a
  POSIX-built `python3`/`perl` as an openable path** - which bash and which interpreter resolve is
  itself platform-dependent, so this bit hooks that had never touched the filesystem beyond a
  literal-string test before (`graph-stale`, `guard-agent-scope`). `guard-agent-spawn.sh`'s
  `norm_path()` (wslpath/cygpath, falling back to a manual `/mnt/<drive>` or `/<drive>` guess) is
  copied verbatim into every `.sh` hook that opens a file under the payload's `cwd`.
- **A `PreToolUse` payload for `Edit|Write` names no calling subagent.** `subagent_type` and
  `agent_id` exist only on the `Agent|Task` dispatch call (`guard-agent-spawn`) and on the
  `SubagentStop` event (`agent-history`) - never on the subagent's own subsequent tool calls. A
  hook that wanted to block "seat X writing outside its module" on this event would be guessing at
  who X is. `guard-agent-scope` is written the way it is - advisory, keyed off the task board and
  the code graph instead of an identity the payload does not carry - because of this gap.

- **A Stop hook that blocks can loop.** Exit 2 on `Stop` makes Claude continue, and the next stop
  fires the hook again. `stop-evidence` allows unconditionally when the payload's
  `stop_hook_active` is true, so it bounces a turn at most once. Claude Code also caps consecutive
  stop-hook continuations, but a hook that leans on that cap burns eight turns where one is enough.
- **A PreCompact hook must not fail.** Blocking an automatic compaction that was triggered to
  recover from a context-limit error fails the request. `compact-checkpoint` exits 0 on every path.
- **Booleans need their own branch in the JSON fallback.** perl's `JSON::PP` decodes `true` to an
  object, so the field reader the older hooks share prints nothing for it. The newer hooks print
  `true`/`false` explicitly; without that, `stop_hook_active` would always read as false.
- **TAB is IFS whitespace.** `IFS=$'\t' read a b c` collapses an empty middle field and shifts the
  rest. Hooks that split parsed fields use `\037` (unit separator) instead.
- **A perl one-liner interpolates `"@name"`.** `retry-budget` first compared a key against
  `"@sig"`, which perl reads as an empty array, so every call hashed to the same signature. It is
  `q{@sig}` now, and the eval's reset case is what caught it.
- **Windows sessions may run commands through a `PowerShell` tool, not `Bash`.** The shell guards
  above register `Bash|PowerShell` and read `tool_input.command` from either.
- **A side effect in a PreToolUse hook is deliberate only in `retry-budget`**, which deletes its
  own state file when a different call resets the count. It writes nothing else and never touches
  the tool call.

## Template variables

The hook bodies are parameterised at scaffold time with the default branch, the commit-types
list, the DB reset pattern, and (audit only) the workspace root and repo list. The values shown
in the table above are this repo's installed values.

## Testing

Pipe a sample payload in and assert the exit code - block case `2`, allow case `0`. In PowerShell
read **`$LASTEXITCODE`**, never `$?` (`$?` is a boolean, so it never equals 2):

```powershell
'{"tool_input":{"file_path":".env"}}' | powershell -NoProfile -File .claude/hooks/protect-secrets.ps1; $LASTEXITCODE
```

```bash
echo '{"tool_input":{"file_path":".env"}}' | bash .claude/hooks/protect-secrets.sh; echo $?
```

## Overriding the verification ledger (for the user, not the agent)

`guard-agent-spawn` refuses verification that would learn nothing: a review or suite on content that
already passed, a third review round, a dispatch past the task's budget. The block message tells the
agent to stop and ask you; it never names the override, because a hook that teaches its bypass to the
agent it blocks has no override, only a password everyone knows.

When you decide a re-run is worth it, tell the agent to add one of these lines to the dispatch brief:

- `REVERIFY: <your reason>` - one forced re-run of that seat on that exact content. It is spent once
  used: a second forced re-run on the same content is refused too. Change the code, or decide
  something else.
- `BUDGET: <your reason>` - one dispatch past the task's budget. The budget is
  `dispatch_budget` in `.claude/verify-map.json` (default 24 per task).

Every dispatch, forced or not, is a line in `.claude/state/verify-ledger.jsonl`, and the agent-history
archive keeps the brief, so who forced what stays on the record.

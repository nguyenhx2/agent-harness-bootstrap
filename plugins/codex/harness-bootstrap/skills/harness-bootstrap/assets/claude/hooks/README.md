# Hooks

Guardrail layer 2. Ship ONE flavor per project - `.ps1` on Windows, `.sh` on macOS/Linux - and
register it from `registration.windows.json` / `registration.posix.json` (merge the `hooks` object
into `.claude/settings.json`). The two flavors are behaviorally equivalent by contract.

| Hook | Event | Matcher | Blocks / does | Flavor note |
|------|-------|---------|---------------|-------------|
| `protect-adr` | PreToolUse | `Edit\|Write` | Edits to an ADR whose on-disk `status: Accepted`. ADRs are immutable - supersede with a new one. | Both resolve `file_path` against payload `cwd`. |
| `guard-main-commit` | PreToolUse | `Bash` | `git commit` / `git push` while the effective branch is `{{DEFAULT_BRANCH}}` or `master`. Resolves the target dir from `cd` / `git -C` so worktrees don't misfire. | Both resolve relative target dirs against payload `cwd`. |
| `check-commit-msg` | PreToolUse | `Bash` | A `git commit -m` subject that violates conventional-commits: bad type, >72 chars, trailing period, uppercase description. | PS **must** use `-cmatch`/`-cnotmatch`; bash `grep -E` is case-sensitive already. Plain `-match` silently passes `Feat:`. |
| `protect-secrets` | PreToolUse | `Read\|Edit\|Write\|Bash` | Reads/edits of `.env*` (except `.env.example`), `*.pem/key/pfx/p12`, `secrets?/` + `credentials?/` dirs, service-account JSON; shell commands that read/copy `.env`; destructive DB commands (`{{DB_RESET_PATTERN}}`). | Parity-locked: identical globs, command patterns and block conditions in both flavors. Matching is case-INSENSITIVE on purpose (`-match` / `grep -Ei`). |
| `guard-agent-spawn` | PreToolUse | `Agent\|Task` | Three checks on every subagent dispatch: 1) roster membership - `subagent_type` must have a `.claude/agents/<type>.md` or be on the `spawn-allowlist`; 2) model pinning - a spawn cannot override a roster seat's `model:`; 3) task linkage - a write-capable seat (`Edit`/`Write` in `tools:`) must name a registered `TASK-NNN` in the dispatch prompt. | Allowlist is `.claude/hooks/spawn-allowlist` (one type per line, `#` comments); ships with `Explore` and `Plan`. |
| `guard-agent-scope` | PreToolUse | `Edit\|Write` | Nothing - **advisory, not enforced**. The Edit/Write payload names no calling subagent (see the hook's header and "Gotchas" below), so it cannot block a write to a module a different seat owns. Instead it emits `additionalContext` when a write falls outside the sole Active task's declared "Related files and modules" AND the target module's owner (`.claude/state/code-graph.json`) differs from the task's `owner:`. Silent whenever the picture is ambiguous. | Non-blocking, always exit 0. Needs perl or python3 for the graph comparison; jq alone cannot express it (same call as `agent-history`'s transcript parsing). |
| `specs-reminder` | PostToolUse | `Edit\|Write` | Nothing. Emits `additionalContext` when `docs/specs/` changes: update `13-revision-history.md`, sync the PRD. | Non-blocking, always exit 0. |
| `graph-stale` | PostToolUse | `Edit\|Write` | Nothing. Three tiers by edited path: a harness file (`.claude/` agents/rules/commands/hooks, `settings.json`, `disabled.json`) regenerates `harness-graph.json` + its HTML immediately (cheap scan); a `docs/**/*.md` edit regenerates the docs graph + HTML; a source file is appended to `.claude/state/code-graph.stale`, with an `additionalContext` nudge past 20 accumulated edits - full code scans stay deliberate (`/code-graph`). | Non-blocking, always exit 0. Script-driven mutations (scaffold re-runs, `harness-toggle.py`) do not fire this hook - those tools regenerate the graph themselves. |
| `agent-history` | SubagentStop | `*` | Nothing. Archives each finished subagent run to `.claude/state/history/` at the detail level set in `.claude/state/history-level` (line 1: `full`/`summary`/`minimal`/`off`; line 2: retention count - only the newest N per-run files are kept, `index.md` never pruned). Missing/unreadable config means `full`/200, the historical behavior. | Non-blocking, always exit 0. Change the level with `/harness-tune` dial 6. |

`protect-repos` (PreToolUse `Edit|Write`, blocks writes into product-repo dirs) ships only with the
audit workspace - see `assets/audit/hooks/`.

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
  **stderr** (that text is what Claude sees and acts on); `0` = allow. Any other code is ignored.
- Fast (< 1s), no network, plain-ASCII messages. Blocking hooks have no side effects.
- Fail **open**, never closed: an unparseable payload or a missing dependency exits 0 - the
  `settings.json` deny rules and `rules/agent-guardrails.md` remain the backstop. **One deliberate
  exception**: `guard-agent-spawn` refuses a dispatch whose payload it cannot read, because an
  unreadable spawn cannot be shown to name a roster seat, and letting an unverifiable spawn through
  is precisely the thing that hook exists to stop. The eval pins this so it stays a decision rather
  than an accident.

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
  (core `JSON::PP`) -> `python3`, and warns on stderr if none exists.
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

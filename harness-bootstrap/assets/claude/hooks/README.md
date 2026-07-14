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
| `specs-reminder` | PostToolUse | `Edit\|Write` | Nothing. Emits `additionalContext` when `docs/specs/` changes: update `13-revision-history.md`, sync the PRD. | Non-blocking, always exit 0. |
| `agent-history` | SubagentStop | `*` | Nothing. Archives each finished subagent run (prompt + final response) to `.claude/state/history/`. | Non-blocking, always exit 0. |

`protect-repos` (PreToolUse `Edit|Write`, blocks writes into product-repo dirs) ships only with the
audit workspace - see `assets/audit/hooks/`.

## Contract

- Payload arrives as JSON on **stdin**. Signal by **exit code**: `2` = BLOCK, with the reason on
  **stderr** (that text is what Claude sees and acts on); `0` = allow. Any other code is ignored.
- Fast (< 1s), no network, plain-ASCII messages. Blocking hooks have no side effects.
- Fail **open**, never closed: an unparseable payload or a missing dependency exits 0 - the
  `settings.json` deny rules and `rules/agent-guardrails.md` remain the backstop.

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

## Template variables

Substituted at scaffold time: `{{DEFAULT_BRANCH}}`, `{{COMMIT_TYPES}}`, `{{DB_RESET_PATTERN}}`, and
(audit only) `{{WORKSPACE_ROOT}}`, `{{REPO_DIR_LIST}}`.

## Testing

Pipe a sample payload in and assert the exit code - block case `2`, allow case `0`. In PowerShell
read **`$LASTEXITCODE`**, never `$?` (`$?` is a boolean, so it never equals 2):

```powershell
'{"tool_input":{"file_path":".env"}}' | powershell -NoProfile -File .claude/hooks/protect-secrets.ps1; $LASTEXITCODE
```

```bash
echo '{"tool_input":{"file_path":".env"}}' | bash .claude/hooks/protect-secrets.sh; echo $?
```

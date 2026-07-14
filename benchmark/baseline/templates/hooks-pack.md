# Hooks pack (project-bootstrap)

Full scripts for the six standard hooks. PowerShell versions are canonical (Windows-native); bash
equivalents follow for macOS/Linux - generate ONE flavor per project, matching the dev OS answer,
and register in `settings.json` (see `settings.json.template`). Also generate
`.claude/hooks/README.md` with the standard table (hook / event / purpose) and the conventions:
fast (< 1s), no network, no side effects beyond blocking/reminding, exit 2 = block with a message
on stderr, plain-ASCII messages.

Placeholders: `{{DEFAULT_BRANCH}}` (usually `main`), `{{COMMIT_TYPES}}` (default
`feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert`), `{{DB_RESET_PATTERN}}` (regex of
the stack's destructive DB commands, e.g. `prisma\s+migrate\s+reset|prisma\s+db\s+push\s+.*--force-reset|drop\s+database`).

Test every hook after generation: pipe a sample JSON payload in and assert the exit code (block
case exits 2, allow case exits 0). Example:
`echo '{"tool_input":{"file_path":".env"}}' | powershell -NoProfile -File .claude/hooks/protect-secrets.ps1; echo $?`

---

## protect-adr - PreToolUse (Edit|Write)

Blocks edits to ADRs whose status is Accepted (ADRs are immutable; change = new ADR). Timing note:
the hook reads the ON-DISK (pre-edit) status, so the commit that flips `proposed -> accepted`
itself passes, but every edit AFTER it is blocked - including fixing now-stale prose in the same
file. Make the accept-flip its OWN final commit, landing all other edits (including any
self-referential "still a draft" text) BEFORE the flip; after it the file is frozen forever.

```powershell
# protect-adr.ps1
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }
$norm = $path -replace '\\', '/'
if ($norm -match 'docs/architecture/decisions/ADR-\d+[^/]*\.md$') {
    if (Test-Path $path) {
        $head = Get-Content $path -TotalCount 10 -ErrorAction SilentlyContinue
        if ($head -match '^status:\s*Accepted') {
            [Console]::Error.WriteLine("BLOCKED: this ADR has status Accepted and is immutable. Create a new ADR with /new-adr and mark the old one 'Superseded by ADR-NNN' (only the status line may change).")
            exit 2
        }
    }
}
exit 0
```

```bash
#!/usr/bin/env bash
# protect-adr.sh
payload=$(cat)
path=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty')
[ -z "$path" ] && exit 0
norm=${path//\\//}
if printf '%s' "$norm" | grep -Eq 'docs/architecture/decisions/ADR-[0-9]+[^/]*\.md$'; then
  if [ -f "$path" ] && head -10 "$path" | grep -Eq '^status:[[:space:]]*Accepted'; then
    echo "BLOCKED: this ADR has status Accepted and is immutable. Create a new ADR with /new-adr and mark the old one 'Superseded by ADR-NNN'." >&2
    exit 2
  fi
fi
exit 0
```

## guard-main-commit - PreToolUse (Bash)

Blocks `git commit`/`git push` while the EFFECTIVE branch is `{{DEFAULT_BRANCH}}`/`master`.
Resolves the branch from the command's actual target dir (a leading `cd <dir>` or `git -C <dir>`),
falling back to `payload.cwd`, so it does not misfire on git worktrees.

```powershell
# guard-main-commit.ps1
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$cmd = $payload.tool_input.command
if (-not $cmd) { exit 0 }
if ($cmd -notmatch '(^|[;&|]\s*)git\s+(commit|push)\b') { exit 0 }
$baseCwd = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }
$targetDir = $baseCwd
if ($cmd -match '(?:^|[;&|]\s*)cd\s+"([^"]+)"' -or $cmd -match "(?:^|[;&|]\s*)cd\s+'([^']+)'" -or $cmd -match '(?:^|[;&|]\s*)cd\s+([^\s;&|]+)') {
    if ($matches[1]) { $targetDir = $matches[1] }
} elseif ($cmd -match 'git\s+-C\s+"([^"]+)"' -or $cmd -match "git\s+-C\s+'([^']+)'" -or $cmd -match 'git\s+-C\s+([^\s]+)') {
    if ($matches[1]) { $targetDir = $matches[1] }
}
$branch = git -C $targetDir rev-parse --abbrev-ref HEAD 2>$null
if (-not $branch) { $branch = git -C $baseCwd rev-parse --abbrev-ref HEAD 2>$null }
if ($branch -eq '{{DEFAULT_BRANCH}}' -or $branch -eq 'master') {
    [Console]::Error.WriteLine("BLOCKED: effective branch is '$branch'. Per .claude/rules/git-workflow.md, do not commit/push directly to {{DEFAULT_BRANCH}}. Create a branch: git checkout -b feat/<slug> and commit again.")
    exit 2
}
exit 0
```

```bash
#!/usr/bin/env bash
# guard-main-commit.sh
payload=$(cat)
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0
printf '%s' "$cmd" | grep -Eq '(^|[;&|][[:space:]]*)git[[:space:]]+(commit|push)\b' || exit 0
base_cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty'); [ -z "$base_cwd" ] && base_cwd=$(pwd)
target_dir="$base_cwd"
cd_dir=$(printf '%s' "$cmd" | grep -oE '(^|[;&|][[:space:]]*)cd[[:space:]]+("[^"]+"|'"'"'[^'"'"']+'"'"'|[^[:space:];&|]+)' | head -1 | sed -E 's/.*cd[[:space:]]+//; s/^["'"'"']//; s/["'"'"']$//')
gc_dir=$(printf '%s' "$cmd" | grep -oE 'git[[:space:]]+-C[[:space:]]+("[^"]+"|'"'"'[^'"'"']+'"'"'|[^[:space:]]+)' | head -1 | sed -E 's/.*-C[[:space:]]+//; s/^["'"'"']//; s/["'"'"']$//')
[ -n "$cd_dir" ] && target_dir="$cd_dir" || { [ -n "$gc_dir" ] && target_dir="$gc_dir"; }
branch=$(git -C "$target_dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
[ -z "$branch" ] && branch=$(git -C "$base_cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ "$branch" = "{{DEFAULT_BRANCH}}" ] || [ "$branch" = "master" ]; then
  echo "BLOCKED: effective branch is '$branch'. Do not commit/push directly to {{DEFAULT_BRANCH}}. Create a branch: git checkout -b feat/<slug>." >&2
  exit 2
fi
exit 0
```

## check-commit-msg - PreToolUse (Bash)

Validates the subject of `git commit -m` against `conventional-commits.md`. Skips editor-flow
commits, `--amend --no-edit`, and Merge/Revert subjects. PowerShell caveat: use
`-cmatch`/`-cnotmatch` - plain `-match` is case-insensitive and breaks the lowercase checks.

```powershell
# check-commit-msg.ps1
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$cmd = $payload.tool_input.command
if (-not $cmd) { exit 0 }
if ($cmd -notmatch '(^|[;&|]\s*)git\s+commit\b') { exit 0 }
if ($cmd -match '--amend' -and $cmd -match '--no-edit') { exit 0 }
$msg = $null
if ($cmd -match '(?s)-m\s+"(.*?)"') { $msg = $Matches[1] }
elseif ($cmd -match "(?s)-m\s+'(.*?)'") { $msg = $Matches[1] }
if (-not $msg) { exit 0 }
$subject = ($msg -split "(`r)?`n")[0].Trim()
if ($subject -match '^(Merge|Revert)\b') { exit 0 }
$types = '{{COMMIT_TYPES}}'
$pattern = "^($types)(\([a-z0-9-]+\))?(!)?: \S.*$"
$problems = @()
if ($subject -cnotmatch $pattern) { $problems += "subject must match '<type>(<scope>)?: <description>' with lowercase type in [$types]" }
if ($subject.Length -gt 72) { $problems += "subject is $($subject.Length) chars (max 72)" }
if ($subject -cmatch '\.\s*$') { $problems += "subject must not end with a period" }
if ($subject -cmatch '^[a-z]+(\([a-z0-9-]+\))?(!)?: [A-Z]') { $problems += "description starts uppercase - use lowercase" }
if ($problems.Count -gt 0) {
    [Console]::Error.WriteLine("BLOCKED: commit message violates .claude/rules/conventional-commits.md:")
    foreach ($p in $problems) { [Console]::Error.WriteLine(" - $p") }
    [Console]::Error.WriteLine("Subject was: '$subject'. Example: feat(core): add health endpoint")
    exit 2
}
exit 0
```

```bash
#!/usr/bin/env bash
# check-commit-msg.sh
payload=$(cat)
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0
printf '%s' "$cmd" | grep -Eq '(^|[;&|][[:space:]]*)git[[:space:]]+commit\b' || exit 0
printf '%s' "$cmd" | grep -q -- '--amend' && printf '%s' "$cmd" | grep -q -- '--no-edit' && exit 0
msg=$(printf '%s' "$cmd" | sed -nE 's/.*-m[[:space:]]+"([^"]*)".*/\1/p'); [ -z "$msg" ] && msg=$(printf '%s' "$cmd" | sed -nE "s/.*-m[[:space:]]+'([^']*)'.*/\1/p")
[ -z "$msg" ] && exit 0
subject=$(printf '%s' "$msg" | head -1 | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')
printf '%s' "$subject" | grep -Eq '^(Merge|Revert)\b' && exit 0
types='{{COMMIT_TYPES}}'
problems=()
printf '%s' "$subject" | grep -Eq "^($types)(\([a-z0-9-]+\))?(!)?: [^[:space:]]" || problems+=("subject must match '<type>(<scope>)?: <description>' with lowercase type in [$types]")
[ ${#subject} -gt 72 ] && problems+=("subject is ${#subject} chars (max 72)")
printf '%s' "$subject" | grep -Eq '\.[[:space:]]*$' && problems+=("subject must not end with a period")
printf '%s' "$subject" | grep -Eq '^[a-z]+(\([a-z0-9-]+\))?(!)?: [A-Z]' && problems+=("description starts uppercase - use lowercase")
if [ ${#problems[@]} -gt 0 ]; then
  echo "BLOCKED: commit message violates .claude/rules/conventional-commits.md:" >&2
  for p in "${problems[@]}"; do echo " - $p" >&2; done
  echo "Subject was: '$subject'. Example: feat(core): add health endpoint" >&2
  exit 2
fi
exit 0
```

## protect-secrets - PreToolUse (Read|Edit|Write|Bash)

Blocks file access to secrets (`.env*` except `.env.example`, key files, secrets dirs,
service-account JSON), shell commands that read/copy `.env`, and destructive DB commands.

```powershell
# protect-secrets.ps1
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$secretPattern = '(^|/)\.env(\.[^/]+)?$|(^|/)(secrets?|credentials?)/|\.(pem|key|pfx|p12)$|service[-_]?account.*\.json$'
$allowPattern = '\.env\.example$'
$path = $payload.tool_input.file_path
if ($path) {
    $norm = $path -replace '\\', '/'
    if ($norm -match $secretPattern -and $norm -notmatch $allowPattern) {
        [Console]::Error.WriteLine("BLOCKED: this file may contain secrets ($norm). Per .claude/rules/agent-guardrails.md, agents do not read/edit secrets. Use .env.example for placeholders.")
        exit 2
    }
}
$cmd = $payload.tool_input.command
if ($cmd) {
    if ($cmd -match '(cat|type|more|less|head|tail|Get-Content|gc|copy|cp|echo)\s+[^\s]*\.env(\.[a-zA-Z0-9_-]+)?(\s|$|"|'')' -and $cmd -notmatch '\.env\.example') {
        [Console]::Error.WriteLine("BLOCKED: this command reads/copies a .env file. If you need the variable list, read .env.example.")
        exit 2
    }
    if ($cmd -match '{{DB_RESET_PATTERN}}') {
        [Console]::Error.WriteLine("BLOCKED: destructive DB command. Migrations only via the controlled /db-migration flow; DB resets must be run by the user themselves.")
        exit 2
    }
}
exit 0
```

```bash
#!/usr/bin/env bash
# protect-secrets.sh
payload=$(cat)
path=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty')
if [ -n "$path" ]; then
  norm=${path//\\//}
  if printf '%s' "$norm" | grep -Eq '(^|/)\.env(\.[^/]+)?$|(^|/)(secrets?|credentials?)/|\.(pem|key|pfx|p12)$|service[-_]?account.*\.json$' \
     && ! printf '%s' "$norm" | grep -Eq '\.env\.example$'; then
    echo "BLOCKED: this file may contain secrets ($norm). Agents do not read/edit secrets; use .env.example for placeholders." >&2
    exit 2
  fi
fi
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')
if [ -n "$cmd" ]; then
  if printf '%s' "$cmd" | grep -Eq '(cat|more|less|head|tail|cp|echo)[[:space:]]+[^[:space:]]*\.env(\.[a-zA-Z0-9_-]+)?([[:space:]]|$|")' \
     && ! printf '%s' "$cmd" | grep -q '\.env\.example'; then
    echo "BLOCKED: this command reads/copies a .env file. If you need the variable list, read .env.example." >&2
    exit 2
  fi
  if printf '%s' "$cmd" | grep -Eq '{{DB_RESET_PATTERN}}'; then
    echo "BLOCKED: destructive DB command. Migrations only via /db-migration; resets must be run by the user." >&2
    exit 2
  fi
fi
exit 0
```

## specs-reminder - PostToolUse (Edit|Write)

Non-blocking: when a file under `docs/specs/` (except the revision-history file) is edited, injects
a reminder to update the revision history and sync the PRD.

```powershell
# specs-reminder.ps1
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }
$norm = $path -replace '\\', '/'
if ($norm -match 'docs/specs/' -and $norm -notmatch '13-revision-history\.md$') {
    $out = @{ hookSpecificOutput = @{ hookEventName = 'PostToolUse'; additionalContext = 'Reminder: you just edited docs/specs/. If this is a requirement change (not a typo/format fix), update docs/specs/13-revision-history.md and sync the related PRD in docs/requirements/.' } } | ConvertTo-Json -Compress
    [Console]::Out.WriteLine($out)
}
exit 0
```

```bash
#!/usr/bin/env bash
# specs-reminder.sh
payload=$(cat)
path=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty')
[ -z "$path" ] && exit 0
norm=${path//\\//}
if printf '%s' "$norm" | grep -q 'docs/specs/' && ! printf '%s' "$norm" | grep -q '13-revision-history\.md$'; then
  jq -cn '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:"Reminder: you just edited docs/specs/. If this is a requirement change, update docs/specs/13-revision-history.md and sync the related PRD in docs/requirements/."}}'
fi
exit 0
```

## agent-history - PostToolUse (Task|Agent)

Non-blocking audit trail: archives every completed subagent run (the prompt sent in and the
agent's final response) as one markdown file in `.claude/state/history/` (gitignored - add
`.claude/state/` to `.gitignore`). Always exits 0. The `history-tracker` agent reads/curates the
archive. Core logic (adapt field names to the current hook payload schema if they differ):

```powershell
# agent-history.ps1 (essential shape - never block, never throw)
try {
    $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $dir = '.claude/state/history'
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $agent = $payload.tool_input.subagent_type; if (-not $agent) { $agent = 'agent' }
    $desc = $payload.tool_input.description; if (-not $desc) { $desc = 'run' }
    $slug = ($desc.ToLower() -replace '[^a-z0-9]+', '-').Trim('-')
    if ($slug.Length -gt 48) { $slug = $slug.Substring(0, 48) }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $rand = -join ((97..122) | Get-Random -Count 4 | ForEach-Object { [char]$_ })
    $file = Join-Path $dir "$stamp-$agent-$slug-$rand.md"
    $prompt = $payload.tool_input.prompt
    $response = $payload.tool_response | ConvertTo-Json -Depth 5
    @("# $agent - $desc", '', '## Prompt', '', '```', $prompt, '```', '', '## Response', '', '```', $response, '```') | Set-Content -Path $file -Encoding UTF8
} catch { }
exit 0
```

```bash
#!/usr/bin/env bash
# agent-history.sh (essential shape - never block, never throw)
{
  payload=$(cat)
  dir='.claude/state/history'; mkdir -p "$dir"
  agent=$(printf '%s' "$payload" | jq -r '.tool_input.subagent_type // "agent"')
  desc=$(printf '%s' "$payload" | jq -r '.tool_input.description // "run"')
  slug=$(printf '%s' "$desc" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-|-$//g' | cut -c1-48)
  file="$dir/$(date +%Y%m%d-%H%M%S)-$agent-$slug-$RANDOM.md"
  { echo "# $agent - $desc"; echo; echo '## Prompt'; echo; echo '```'
    printf '%s' "$payload" | jq -r '.tool_input.prompt // ""'
    echo '```'; echo; echo '## Response'; echo; echo '```'
    printf '%s' "$payload" | jq -r '.tool_response // {} | tostring'
    echo '```'; } > "$file"
} 2>/dev/null
exit 0
```

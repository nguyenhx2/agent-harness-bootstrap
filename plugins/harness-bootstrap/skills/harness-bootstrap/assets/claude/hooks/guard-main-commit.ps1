# guard-main-commit.ps1
# Event: PreToolUse   Matcher: Bash
# Enforces: .claude/rules/conventional-commits.md
# Blocks `git commit` / `git push` while the EFFECTIVE branch is {{DEFAULT_BRANCH}} or master.
# The effective branch is resolved from the command's actual target dir (a leading `cd <dir>` or
# `git -C <dir>`), falling back to the payload's `cwd`, so the hook does not misfire on git
# worktrees or on commands that operate on a sibling checkout.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
} catch {
    exit 0
}

# --- fast path: decide the common case without ConvertFrom-Json -------------------------------
# This hook starts on every shell call. ConvertFrom-Json loads a module, about a fifth of the run
# on Windows PowerShell 5.1, and most commands can never be blocked here - so that case is decided
# from the raw text first. Get-FastString returns one string field decoded EXACTLY, or $null: the
# key must occur once, and the value must be printable ASCII using no JSON escape but \" \\ \n \r
# \t (everything JSON.stringify writes for such text). A hook may only exit 0 on it, and only on a
# test that is a necessary condition of every block it raises; $null or an exception falls
# through to the full parse, which is unchanged. Copied verbatim - see "Latency" in
# hooks/README.md.
function Get-FastString([string]$raw, [string]$key) {
    if ([regex]::Matches($raw, '"' + $key + '"\s*:').Count -ne 1) { return $null }
    $m = [regex]::Match($raw, '"' + $key + '"\s*:\s*"((?:[^"\\]|\\.)*)"')
    if (-not $m.Success) { return $null }
    $s = $m.Groups[1].Value
    if ($s -cmatch '[^\x20-\x7E]') { return $null }
    $s = $s.Replace('\\', [string][char]1)
    if ($s -cmatch '\\([^"nrt]|$)') { return $null }
    $s = $s.Replace('\"', '"').Replace('\n', "`n").Replace('\r', "`r").Replace('\t', "`t")
    return $s.Replace([string][char]1, '\')
}

# The guard only acts on `git ... commit` or `git ... push`.
try {
    $fc = Get-FastString $raw 'command'
    if ($null -ne $fc -and -not ($fc -match 'commit|push')) { exit 0 }
} catch { }

try {
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$cmd = $payload.tool_input.command
if (-not $cmd) { exit 0 }
# git GLOBAL options may sit between `git` and the subcommand - `git -c k=v commit`, `git -C .
# commit`, `git --no-pager commit`, `git --git-dir=.git commit`, `git --work-tree x push`. A pattern
# that required `git\s+commit` let every one of those through, and a live session committed to the
# default branch that way. Same shape as the bash twin's GIT_PREFIX.
$gitVal = '(?:[^\s"'']*(?:"[^"]*"|''[^'']*''))+[^\s"'']*|\S+'
$gitOpt = "-[cC]\s+(?:$gitVal)|--(?:git-dir|work-tree|namespace|config-env)\s+(?:$gitVal)|--[a-z-]+=(?:$gitVal)|-\S+"
$gitPrefix = "(?:^|[^a-zA-Z0-9_.-])git(?:\s+(?:$gitOpt))*\s+"
$gitRe = $gitPrefix + '(?:commit|push)\b'
$m = [regex]::Match($cmd, $gitRe)
if (-not $m.Success) { exit 0 }
# The global options of THAT git invocation - never the subcommand's own arguments, where -C
# means something else (`git commit -C HEAD` reuses a message).
$gitHead = $m.Value

$baseCwd = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }
$targetDir = $baseCwd

# A leading `cd <dir>` wins over `git -C <dir>`: the cd happens first and git -C is relative to it
# only when git -C is itself relative, which the branch lookup below tolerates.
if ($cmd -match '(?:^|[;&|]\s*)cd\s+"([^"]+)"' -or
    $cmd -match "(?:^|[;&|]\s*)cd\s+'([^']+)'" -or
    $cmd -match '(?:^|[;&|]\s*)cd\s+([^\s;&|]+)') {
    if ($Matches[1]) { $targetDir = $Matches[1] }
} elseif ($gitHead -cmatch '\s-C\s+"([^"]+)"' -or
          $gitHead -cmatch "\s-C\s+'([^']+)'" -or
          $gitHead -cmatch '\s-C\s+([^\s]+)') {
    if ($Matches[1]) { $targetDir = $Matches[1] }
}
$gitDir = $null
if ($gitHead -cmatch '--git-dir(?:=|\s+)"([^"]+)"' -or
    $gitHead -cmatch "--git-dir(?:=|\s+)'([^']+)'" -or
    $gitHead -cmatch '--git-dir(?:=|\s+)([^\s]+)') {
    $gitDir = $Matches[1]
}

# Relative target dirs resolve against the payload cwd, not the hook process's cwd.
if (-not [System.IO.Path]::IsPathRooted($targetDir)) {
    try { $targetDir = [System.IO.Path]::GetFullPath((Join-Path $baseCwd $targetDir)) } catch { $targetDir = $baseCwd }
}

if ($gitDir) {
    $branch = git -C $targetDir --git-dir=$gitDir rev-parse --abbrev-ref HEAD 2>$null
} else {
    $branch = git -C $targetDir rev-parse --abbrev-ref HEAD 2>$null
}
if (-not $branch) { $branch = git -C $baseCwd rev-parse --abbrev-ref HEAD 2>$null }
if (-not $branch) { exit 0 }   # not a git repo (or git missing): nothing to guard

if ($branch -eq '{{DEFAULT_BRANCH}}' -or $branch -eq 'master') {
    [Console]::Error.WriteLine("BLOCKED: effective branch is '$branch'. Per .claude/rules/git-workflow.md, do not commit/push directly to {{DEFAULT_BRANCH}}. Create a branch: git checkout -b feat/<slug> and commit again.")
    exit 2
}
exit 0

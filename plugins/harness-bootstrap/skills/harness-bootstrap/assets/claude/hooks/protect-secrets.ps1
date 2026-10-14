# protect-secrets.ps1
# Event: PreToolUse   Matcher: Read|Edit|Write|Bash
# Enforces: .claude/rules/security-privacy.md
# Blocks three things:
#   1. file access (Read/Edit/Write) to secret-bearing paths: .env* (except .env.example), key
#      material (*.pem/*.key/*.pfx/*.p12), secrets?/ + credentials? dirs, service-account JSON, .npmrc/.pypirc/.netrc
#   2. shell commands that read/copy a .env file
#   3. destructive DB commands ({{DB_RESET_PATTERN}})
#
# PARITY CONTRACT: protect-secrets.ps1 and protect-secrets.sh must stay behaviorally EQUIVALENT -
# same secret-file globs, same command patterns, same block conditions. If you change one, change
# the other. The command alternation below deliberately includes the PowerShell spellings
# (Get-Content, gc, type, copy) AND the POSIX spellings (cat, more, less, head, tail, cp, echo);
# the .sh twin carries the identical list even though the PS cmdlet names can never appear in a
# POSIX shell - keeping the regex identical is worth more than pruning dead alternatives.
#
# CASE-SENSITIVITY: matching here is intentionally case-INSENSITIVE (PowerShell -match's default,
# and the .sh twin uses `grep -Ei` to match it). Windows paths are case-insensitive and `GET-CONTENT`
# / `.ENV` must not slip through. This is the opposite of check-commit-msg, which needs -cmatch.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
} catch {
    exit 0
}

$secretPattern = '(^|/)\.env(\.[^/]+)?$|(^|/)(secrets?|credentials?)/|\.(pem|key|pfx|p12|ppk|asc|gpg)$|service[-_]?account.*\.json$|(^|/)id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$|(^|/)\.(npmrc|pypirc|netrc)$|(^|/)\.aws/credentials$|(^|/)\.ssh/'
$allowPattern  = '\.env\.example$'
# NOTE: the leading char class is a hand-rolled word boundary. POSIX ERE (grep -E) has no portable
# \b, so the .sh twin cannot use one; we use the identical construct here so the two regexes stay
# literally the same modulo \s vs [[:space:]].
# Parity with the .sh flavor: match the FILE, not a closed list of reader verbs. A verb list
# let `strings .env` and any wrapper through. Scrubs below remove the forms that may
# legitimately name a .env file, before the test runs.
# The name ends at anything a file name cannot contain - a pipe, a redirect, a bracket, a comma
# from brace expansion - not only at a space or quote: `cat .env|base64` and `(cat .env)` once
# walked past a terminator list that stopped at space, quote, ; and &.
$cmdPattern    = '(^|[^a-zA-Z0-9_./-])[^\s]*\.env(\.[a-zA-Z0-9_-]+)?([^a-zA-Z0-9_.-]|$)'
$cmdScrubs     = @(
    '--exclude(-dir)?=[^\s]*',
    '(?i)(cp|copy|mv|Copy-Item)\s+[^\s]*\.env\.example\s+[^\s]*\.env(\.[a-zA-Z0-9_-]+)?',
    '>>?\s*[^\s]*\.env(\.[a-zA-Z0-9_-]+)?',
    '[^\s]*env-read\.py[^;&|]*',
    '[^\s]*\.env\.example'
)
$dbResetPattern = '{{DB_RESET_PATTERN}}'

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

# A shell call can only be blocked here for naming a .env file or for matching the DB-reset
# pattern - the same -match tests as below, on the same decoded command. A file_path always
# takes the full path.
try {
    $fc = $null
    if (-not $raw.Contains('"file_path"')) { $fc = Get-FastString $raw 'command' }
    # Also falls through for a dot-name carrying a glob, quote, brace or backslash (`.e?v`,
    # `.e""nv`) and for any grep: see 2b below.
    if ($null -ne $fc -and -not ($fc -match '\.env' -or $fc -match '\.[^\s/]*[\]\[*?{"''\\`]' -or
            $fc -match 'grep' -or $fc -match $dbResetPattern)) { exit 0 }
} catch { }

try {
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

function Block-Env([string]$why) {
    [Console]::Error.WriteLine("BLOCKED: $why Values never enter the transcript. Read .env.example for the variable list, or use .claude/scripts/env-read.py (list/check/diff, or run to execute with the values loaded but never printed).")
    exit 2
}

# --- 1. file access ---------------------------------------------------------------------------
$path = $payload.tool_input.file_path
if ($path) {
    $norm = $path -replace '\\', '/'
    if ($norm -match $secretPattern -and $norm -notmatch $allowPattern) {
        [Console]::Error.WriteLine("BLOCKED: this file may contain secrets ($norm). Per .claude/rules/agent-guardrails.md, agents do not read/edit secrets. Use .env.example for placeholders.")
        exit 2
    }
}

# --- 2 + 3. shell commands --------------------------------------------------------------------
$cmd = $payload.tool_input.command
if ($cmd) {
    $cmdScrubbed = $cmd
    foreach ($rx in $cmdScrubs) { $cmdScrubbed = $cmdScrubbed -replace $rx, '' }
    if ($cmdScrubbed -match $cmdPattern) {
        [Console]::Error.WriteLine("BLOCKED: this command names a .env file. Values never enter the transcript. Read .env.example for the variable list, or use .claude/scripts/env-read.py (list/check/diff, or run to execute with the values loaded but never printed).")
        exit 2
    }
    # 2b. The shell rewrites a name before the command sees it, so a literal match is not enough.
    # Same three checks, same order, as shell_words in the .sh twin.
    #   Quote removal: `.e""nv` and `.e\nv` are `.env` by the time cat opens them.
    #   Globbing: a word that a .env name would match (`.e?v`, `.env*`, `.e[n]v`, `.*`) is the
    #     file. Only a word whose last part starts with a dot can match one.
    #   Recursive grep: refused when it searches the working directory, or a directory holding a
    #     .env file, with no --include or env --exclude filter.
    $stripQ = { param($t) $t.Replace('"', '').Replace("'", '').Replace('\', '').Replace('`', '') }
    $c = & $stripQ $cmd
    $s = & $stripQ $cmdScrubbed
    $s = $s -replace '--exclude(-dir)?=[^\s]*', ''
    if ($s -match $cmdPattern) { Block-Env 'this command names a .env file once its quotes are removed.' }
    $ws = @(($c -replace '[;&|()<>=,{}]', ' ') -split '\s+' | Where-Object { $_ })
    for ($i = 0; $i -lt $ws.Count; $i++) {
        $w = $ws[$i]
        if ($w -eq '--exclude' -or $w -eq '--exclude-dir') { $i++; continue }
        if ($w -notmatch '[*?\[]') { continue }
        $b = ($w -split '/')[-1]
        if (-not $b.StartsWith('.')) { continue }
        if ('.env' -like $b -or '.env.local' -like $b -or '.env.production' -like $b) {
            Block-Env "the pattern '$w' expands to a .env file."
        }
    }
    $cwdPosix = ([string]$payload.cwd) -replace '\\', '/'
    $cwdPosix = $cwdPosix.TrimEnd('/')
    foreach ($line in ($c -split '&&|\|\||;|\|')) {
        $t = @($line -split '\s+' | Where-Object { $_ })
        $g = -1
        for ($i = 0; $i -lt $t.Count; $i++) {
            if ($t[$i] -cmatch '^(grep|egrep|fgrep)$' -or $t[$i] -cmatch '/grep$') { $g = $i; break }
        }
        if ($g -lt 0) { continue }
        $rec = $false; $inc = $false; $opts = $true; $patSeen = $false; $paths = @()
        for ($i = $g + 1; $i -lt $t.Count; $i++) {
            $w = $t[$i]
            if ($opts -and $w -eq '--') { $opts = $false; continue }
            if ($opts) {
                if ($w -in @('--recursive', '--dereference-recursive', '--directories=recurse')) { $rec = $true; continue }
                if ($w -eq '--include' -or $w -like '--include=*' -or $w -like '--exclude=*env*' -or $w -like '--exclude-dir=*') { $inc = $true; continue }
                if ($w -in @('-e', '-f') -or $w -like '--regexp=*' -or $w -like '--file=*') { $patSeen = $true; continue }
                if ($w.StartsWith('--')) { continue }
                if ($w.StartsWith('-')) { if ($w -cmatch '[rR]') { $rec = $true }; continue }
            }
            if (-not $patSeen) { $patSeen = $true; continue }
            $paths += $w
        }
        if (-not $rec -or $inc) { continue }
        if ($paths.Count -eq 0) { $paths = @('.') }
        foreach ($dir in $paths) {
            if ($dir -ne '/') { $dir = $dir.TrimEnd('/') }
            $found = $dir -in @('.', './', '..', '*', '/', '') -or ($cwdPosix -and $dir -eq $cwdPosix)
            if (-not $found) {
                $d = if ($dir -match '^(/|[A-Za-z]:/)') { $dir } else { "$cwdPosix/$dir" }
                $hit = @(Get-ChildItem -LiteralPath $d -Force -Filter '.env*' -File -ErrorAction SilentlyContinue |
                         Where-Object { $_.Name -eq '.env' -or ($_.Name -like '.env.*' -and $_.Name -ne '.env.example') })
                $found = $hit.Count -gt 0
            }
            if ($found) {
                Block-Env "grep -r through '$dir' would print what is inside a .env file on the way. Add --include='*.ts' (or --exclude='.env*'), or use the Grep tool."
            }
        }
    }
    if ($cmd -match $dbResetPattern) {
        [Console]::Error.WriteLine("BLOCKED: destructive DB command. Schema changes go through the controlled migration flow; DB resets must be run by the user themselves.")
        exit 2
    }
}
exit 0

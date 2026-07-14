# protect-secrets.ps1
# Event: PreToolUse   Matcher: Read|Edit|Write|Bash
# Blocks three things:
#   1. file access (Read/Edit/Write) to secret-bearing paths: .env* (except .env.example), key
#      material (*.pem/*.key/*.pfx/*.p12), secrets?/ + credentials? dirs, service-account JSON
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
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$secretPattern = '(^|/)\.env(\.[^/]+)?$|(^|/)(secrets?|credentials?)/|\.(pem|key|pfx|p12)$|service[-_]?account.*\.json$'
$allowPattern  = '\.env\.example$'
# NOTE: the leading char class is a hand-rolled word boundary. POSIX ERE (grep -E) has no portable
# \b, so the .sh twin cannot use one; we use the identical construct here so the two regexes stay
# literally the same modulo \s vs [[:space:]].
$cmdPattern    = '(^|[^a-zA-Z0-9_.-])(cat|type|more|less|head|tail|Get-Content|gc|copy|cp|echo)\s+[^\s]*\.env(\.[a-zA-Z0-9_-]+)?(\s|$|"|'')'
$cmdAllow      = '\.env\.example'
$dbResetPattern = '{{DB_RESET_PATTERN}}'

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
    if ($cmd -match $cmdPattern -and $cmd -notmatch $cmdAllow) {
        [Console]::Error.WriteLine("BLOCKED: this command reads/copies a .env file. If you need the variable list, read .env.example.")
        exit 2
    }
    if ($cmd -match $dbResetPattern) {
        [Console]::Error.WriteLine("BLOCKED: destructive DB command. Migrations only via the controlled /db-migration flow; DB resets must be run by the user themselves.")
        exit 2
    }
}
exit 0

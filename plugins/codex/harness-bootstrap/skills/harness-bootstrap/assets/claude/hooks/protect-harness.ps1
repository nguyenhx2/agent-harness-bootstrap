# protect-harness.ps1
# Event: PreToolUse   Matcher: Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell
# Flag: none - ships with every harness
# Enforces: .claude/rules/agent-guardrails.md
# Guards the files that enforce the harness itself: .claude/settings.json,
# .claude/settings.local.json, and anything under .claude/hooks/. An Edit or Write there asks the
# user; a shell command that writes there is blocked. See protect-harness.sh for why.
#
# PARITY CONTRACT: protect-harness.sh and protect-harness.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the PreToolUse JSON payload on stdin. Ask = a JSON decision on stdout and exit
# 0; block = exit 2 with the reason on stderr; allow = exit 0 with no output.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
} catch {
    exit 0
}
# Every ask below needs `.claude/settings` or `.claude/hooks` in the payload, in either slash.
if (-not ($raw -match '\.claude(/|\\\\)(settings|hooks)')) { exit 0 }

try {
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

function Ask([string]$why) {
    $o = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'ask'; permissionDecisionReason = $why } }
    [Console]::Out.WriteLine(($o | ConvertTo-Json -Compress -Depth 4))
    exit 0
}

$protectedRe = '(^|/)\.claude/(settings(\.local)?\.json$|hooks/)'
$path = [string]$payload.tool_input.file_path
if (-not $path) { $path = [string]$payload.tool_input.notebook_path }
if ($path) {
    $norm = $path -replace '\\', '/'
    if ($norm -match $protectedRe) {
        Ask "protect-harness: $norm enforces the harness. An agent edit here can switch a guard off, so a person decides. To disable a control on purpose, use /harness-toggle instead."
    }
}

$cmd = [string]$payload.tool_input.command
if ($cmd) {
    $c = $cmd -replace '\\', '/'
    if ($c -match '\.claude/(settings(\.local)?\.json|hooks/)') {
        $writeRe = '(>|(^|[^a-zA-Z0-9_-])(sed\s+-i|tee|cp|mv|rm|truncate|chmod|ln|install|dd|perl|python3?|node|ruby|Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item|ri|del|move|copy)([^a-zA-Z0-9_-]|$))'
        if ($c -match $writeRe) {
            [Console]::Error.WriteLine('BLOCKED by protect-harness: this command writes to a file that enforces the harness (.claude/settings or .claude/hooks). Change it with the Edit tool, which asks the user, or switch a control off on purpose with /harness-toggle.')
            exit 2
        }
    }
}
exit 0

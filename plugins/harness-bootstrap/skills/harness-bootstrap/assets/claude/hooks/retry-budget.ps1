# retry-budget.ps1
# Events: PostToolUseFailure and PreToolUse (Matcher: Bash|PowerShell|Edit|MultiEdit|Write|WebFetch)
# Registered only on the tools whose failures loop - a shell command, an edit whose old_string
# never matches, a fetch that keeps failing. On `*` it started a process for every tool call.
# Flag: long
# Enforces: .claude/rules/agent-guardrails.md (no silent retry loops)
#   PostToolUseFailure: records the failed call's signature (tool name + input minus
#     `description`) in .claude/state/retry-budget; the 2nd identical consecutive failure WARNS.
#   PreToolUse: BLOCKS (exit 2) a call identical to one that has failed 3 times in a row. Any
#     different call resets the count. Interrupted calls are never counted.
#
# WHY COUNT FAILURES, NOT REPEATS: see retry-budget.sh - successful polling repeats legitimately.
#
# PARITY CONTRACT: retry-budget.sh and retry-budget.ps1 must stay behaviorally EQUIVALENT - same
# thresholds, same reset rule, same signature fields. The hash itself differs per flavor.
#
# Contract: reads the hook JSON payload on stdin. exit 2 = BLOCK (PreToolUse only, reason on
# stderr); exit 0 otherwise, optionally with hookSpecificOutput JSON on stdout. Fails OPEN.

$Limit = 3
$WarnAt = 2

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

try {
    $hookEvent = [string]$payload.hook_event_name
    $tool = [string]$payload.tool_name
    if (-not $tool) { exit 0 }
    $session = if ($payload.session_id) { [string]$payload.session_id } else { '-' }
    $baseCwd = if ($payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }
    if (-not (Test-Path -LiteralPath (Join-Path $baseCwd '.claude') -PathType Container)) { exit 0 }
    $state = Join-Path $baseCwd '.claude/state/retry-budget'

    $ti = $payload.tool_input
    if ($ti -and $ti.PSObject.Properties['description']) { $ti.PSObject.Properties.Remove('description') }
    $canon = if ($ti) { $ti | ConvertTo-Json -Compress -Depth 20 } else { '{}' }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes("$tool`n$canon")
    $sig = -join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })

    $sSession = ''; $sSig = ''; $sCount = 0
    if (Test-Path -LiteralPath $state -PathType Leaf) {
        $parts = ([System.IO.File]::ReadAllText($state).TrimEnd("`r", "`n")) -split [char]0x1f
        if ($parts.Count -ge 3) {
            $sSession = $parts[0]; $sSig = $parts[1]
            $parsed = 0
            if ([int]::TryParse($parts[2], [ref]$parsed)) { $sCount = $parsed }
        }
    }
} catch {
    exit 0
}

$us = [string][char]0x1f
if ($hookEvent -ceq 'PostToolUseFailure') {
    if ($payload.is_interrupt -eq $true) { exit 0 }
    $count = 1
    if ($sSession -ceq $session -and $sSig -ceq $sig) { $count = $sCount + 1 }
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $state) | Out-Null
        [System.IO.File]::WriteAllText($state, "$session$us$sig$us$count`n")
    } catch { }
    if ($count -eq $WarnAt) {
        $out = @{
            hookSpecificOutput = @{
                hookEventName     = 'PostToolUseFailure'
                additionalContext = "retry-budget: this exact $tool call has now failed $count times in a row. Do not retry it unchanged - read the error and change the input or the approach. After $Limit identical failures the next identical attempt is blocked."
            }
        } | ConvertTo-Json -Compress -Depth 5
        [Console]::Out.WriteLine($out)
    }
    exit 0
}
if ($hookEvent -ceq 'PreToolUse') {
    if (-not (Test-Path -LiteralPath $state -PathType Leaf)) { exit 0 }
    if ($sSession -ceq $session -and $sSig -ceq $sig) {
        if ($sCount -ge $Limit) {
            [Console]::Error.WriteLine("BLOCKED by retry-budget: this exact $tool call has failed $sCount times in a row with the same input; a further identical attempt will fail the same way. Change the input or the approach (any different call resets this count), or stop and report the blocker - for a dispatched task, record it with: python .claude/scripts/task.py attempt <TASK-NNN> --reason <infra|scope|env> --note `"...`".")
            exit 2
        }
    } else {
        Remove-Item -LiteralPath $state -Force -ErrorAction SilentlyContinue
    }
}
exit 0

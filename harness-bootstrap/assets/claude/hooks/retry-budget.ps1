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

# A PreToolUse call is only ever blocked when the state file exists, and it rarely does: one
# different call deletes it. So answer "no state file" without the parser.
try {
    $fe = Get-FastString $raw 'hook_event_name'
    $fw = Get-FastString $raw 'cwd'
    if ($fe -ceq 'PreToolUse' -and $fw -and
        -not (Test-Path -LiteralPath (Join-Path $fw '.claude/state/retry-budget'))) { exit 0 }
} catch { }

try {
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

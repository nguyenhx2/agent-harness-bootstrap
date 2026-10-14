# agent-trace.ps1
# Events: SubagentStart (Matcher: *), InstructionsLoaded (no matcher), PermissionDenied (Matcher: *)
# Flag: long
# Enforces: .claude/rules/agent-guardrails.md (what ran is observable, not inferred)
# NEVER BLOCKS, PRINTS NOTHING. Appends one tab-separated line per event to
# .claude/state/trace.log: subagent starts (type, id), instruction files that entered context
# (load_reason, memory_type, path) and auto-mode permission denials (tool, reason, target).
# Keeps the newest 1500 lines once the log passes 2000.
#
# WHY A LOG AND NOT CONTEXT: see agent-trace.sh.
#
# PARITY CONTRACT: agent-trace.sh and agent-trace.ps1 must write the same fields in the same order.
#
# Contract: reads the hook JSON payload on stdin. Always exit 0, nothing on stdout.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json

    function Field([string]$s) {
        if (-not $s) { $s = '-' }
        $s = $s -replace "[`t`r`n]", ' '
        if ($s.Length -gt 160) { $s = $s.Substring(0, 160) }
        return $s
    }

    $hookEvent = [string]$payload.hook_event_name
    $rawCwd = ([string]$payload.cwd) -replace '\\', '/'
    $baseCwd = if ($payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }
    if (-not (Test-Path -LiteralPath (Join-Path $baseCwd '.claude') -PathType Container)) { exit 0 }

    switch -CaseSensitive ($hookEvent) {
        'SubagentStart' {
            $detail = "$(Field $payload.agent_type)`t$(Field $payload.agent_id)"
        }
        'InstructionsLoaded' {
            $p = ([string]$payload.file_path) -replace '\\', '/'
            $prefix = $rawCwd.TrimEnd('/') + '/'
            if ($rawCwd -and $p.StartsWith($prefix)) { $p = $p.Substring($prefix.Length) }
            $detail = "$(Field $payload.load_reason)`t$(Field $payload.memory_type)`t$(Field $p)"
        }
        'PermissionDenied' {
            $what = [string]$payload.tool_input.command
            if (-not $what) { $what = [string]$payload.tool_input.file_path }
            if (-not $what) { $what = [string]$payload.tool_input.url }
            $detail = "$(Field $payload.tool_name)`t$(Field $payload.reason)`t$(Field $what)"
        }
        default { exit 0 }
    }

    $log = Join-Path $baseCwd '.claude/state/trace.log'
    New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
    $stamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    [System.IO.File]::AppendAllText($log, "$stamp`t$hookEvent`t$detail`n")
    $lines = [System.IO.File]::ReadAllLines($log)
    if ($lines.Count -gt 2000) {
        [System.IO.File]::WriteAllText($log, (($lines | Select-Object -Last 1500) -join "`n") + "`n")
    }
} catch { }
exit 0

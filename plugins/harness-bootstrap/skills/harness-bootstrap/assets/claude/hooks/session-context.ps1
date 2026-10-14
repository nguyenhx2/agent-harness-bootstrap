# session-context.ps1
# Event: SessionStart   Matcher: startup|resume|clear|compact
# Flag: long
# Enforces: .claude/rules/task-tracking.md (start from the board, not from memory)
# NEVER BLOCKS. Injects additionalContext naming every task in docs/tasks/active/ with its owner
# and next step (the task's "## Checkpoint" Next step, else its first unchecked item), and after
# a compaction points at .claude/state/compact-checkpoint.md. Silent when there is nothing to say.
# At most 8 tasks are listed.
#
# PARITY CONTRACT: session-context.sh and session-context.ps1 must emit the same text.
#
# Contract: reads the SessionStart JSON payload on stdin. Emits
# hookSpecificOutput.additionalContext JSON on stdout, or nothing. Always exit 0.

try {
    $raw = [Console]::In.ReadToEnd()
    $payload = if ($raw) { $raw | ConvertFrom-Json } else { $null }
} catch {
    $payload = $null
}

try {
    $sourceKind = if ($payload) { [string]$payload.source } else { '' }
    $baseCwd = if ($payload -and $payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }

    function Clean([string]$s) { return ($s -replace '["\\]', '' -replace '[\x00-\x1f]', '') }

    function Get-TaskFields([string]$file) {
        $r = @{ o = ''; nx = ''; cn = '' }
        $fm = $false; $cp = $false; $n = 0
        foreach ($line in [System.IO.File]::ReadAllLines($file)) {
            $n++
            $line = $line -replace "`r$", ''
            if ($n -eq 1 -and $line.StartsWith('---')) { $fm = $true; continue }
            if ($fm -and $line.StartsWith('---')) { $fm = $false; continue }
            if ($fm) {
                if ($line -cmatch '^owner:[ \t]*(.*)$') { $r.o = $Matches[1] }
                continue
            }
            if ($line.StartsWith('## ')) { $cp = ($line -ceq '## Checkpoint') }
            if (-not $r.nx -and $line -cmatch '^[ \t]*- \[ \] ([^<].*)$') { $r.nx = $Matches[1] }
            if ($cp -and $line -cmatch '^- Next step:[ \t]*(.*)$') { $r.cn = $Matches[1] }
        }
        return $r
    }

    $activeDir = Join-Path $baseCwd 'docs/tasks/active'
    $files = @()
    if (Test-Path -LiteralPath $activeDir -PathType Container) {
        $files = @(Get-ChildItem -LiteralPath $activeDir -Filter '*.md' -File | Sort-Object Name)
    }
    $msg = ''
    $listed = 0
    foreach ($f in $files) {
        if ($listed -ge 8) { break }
        $listed++
        $r = Get-TaskFields $f.FullName
        $next = $r.cn
        if (-not $next -or $next -ceq '-') { $next = $r.nx }
        if (-not $next) { $next = '-' }
        $owner = if ($r.o) { $r.o } else { '-' }
        $msg += "`n- $(Clean $f.Name) (owner: $(Clean $owner)) - next: $(Clean $next)"
    }
    if ($files.Count -gt 0) {
        $more = ''
        if ($files.Count -gt $listed) { $more = " ($($files.Count - $listed) more not shown)" }
        $msg = "session-context: active tasks in docs/tasks/active/${more}:$msg`nDetail for one task: python .claude/scripts/task.py resume <TASK-NNN>. Update the board only through task.py."
    }
    if ($sourceKind -ceq 'compact' -and (Test-Path -LiteralPath (Join-Path $baseCwd '.claude/state/compact-checkpoint.md') -PathType Leaf)) {
        $note = 'Context was just compacted. Re-read .claude/state/compact-checkpoint.md - it records the branch, the active tasks and the uncommitted changes as they were before the summary - before continuing.'
        if ($msg) { $msg = "$note`n$msg" } else { $msg = $note }
    }
    if (-not $msg) { exit 0 }

    $out = @{
        hookSpecificOutput = @{
            hookEventName     = 'SessionStart'
            additionalContext = $msg
        }
    } | ConvertTo-Json -Compress -Depth 5
    [Console]::Out.WriteLine($out)
} catch { }
exit 0

# compact-checkpoint.ps1
# Event: PreCompact   Matcher: manual|auto
# Flag: long
# Enforces: .claude/rules/task-tracking.md (state lives on disk, not in the context window)
# NEVER BLOCKS. Before a compaction, writes .claude/state/compact-checkpoint.md: the branch, any
# /compact instructions, every task in docs/tasks/active/ with its status, owner, first unchecked
# item and its own "## Checkpoint" lines (kept current by `python .claude/scripts/task.py
# checkpoint`), and the uncommitted changes.
#
# WHY NEVER BLOCK: see compact-checkpoint.sh - blocking an automatic compaction can fail the
# request outright. Every path here exits 0.
#
# PARITY CONTRACT: compact-checkpoint.sh and compact-checkpoint.ps1 must write the same sections
# from the same sources.
#
# Contract: reads the PreCompact JSON payload on stdin. Always exit 0.

try {
    $raw = [Console]::In.ReadToEnd()
    $payload = if ($raw) { $raw | ConvertFrom-Json } else { $null }
} catch {
    $payload = $null
}

try {
    $trigger = if ($payload -and $payload.trigger) { [string]$payload.trigger } else { 'auto' }
    $instr = if ($payload -and $payload.custom_instructions) { [string]$payload.custom_instructions } else { '-' }
    $baseCwd = if ($payload -and $payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }
    if (-not (Test-Path -LiteralPath (Join-Path $baseCwd '.claude') -PathType Container)) { exit 0 }
    $state = Join-Path $baseCwd '.claude/state'
    New-Item -ItemType Directory -Force -Path $state | Out-Null
    $out = Join-Path $baseCwd '.claude/state/compact-checkpoint.md'

    function Get-TaskFields([string]$file) {
        $r = @{ t = ''; s = ''; o = ''; nx = ''; cn = ''; cg = ''; cq = '' }
        $fm = $false; $cp = $false; $n = 0
        foreach ($line in [System.IO.File]::ReadAllLines($file)) {
            $n++
            $line = $line -replace "`r$", ''
            if ($n -eq 1 -and $line.StartsWith('---')) { $fm = $true; continue }
            if ($fm -and $line.StartsWith('---')) { $fm = $false; continue }
            if ($fm) {
                if ($line -cmatch '^title:[ \t]*(.*)$') { $r.t = $Matches[1] -replace '"', '' }
                elseif ($line -cmatch '^status:[ \t]*(.*)$') { $r.s = $Matches[1] }
                elseif ($line -cmatch '^owner:[ \t]*(.*)$') { $r.o = $Matches[1] }
                continue
            }
            if ($line.StartsWith('## ')) { $cp = ($line -ceq '## Checkpoint') }
            if (-not $r.nx -and $line -cmatch '^[ \t]*- \[ \] ([^<].*)$') { $r.nx = $Matches[1] }
            if ($cp) {
                if ($line -cmatch '^- Next step:[ \t]*(.*)$') { $r.cn = $Matches[1] }
                elseif ($line -cmatch '^- Last green commit:[ \t]*(.*)$') { $r.cg = $Matches[1] }
                elseif ($line -cmatch '^- Open questions:[ \t]*(.*)$') { $r.cq = $Matches[1] }
            }
        }
        return $r
    }
    function Or-Dash([string]$v) { if ($v) { return $v } else { return '-' } }

    $hasGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
    $branch = ''
    if ($hasGit) { $branch = (& git -C $baseCwd rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim() }

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('# Compaction checkpoint')
    $lines.Add('')
    $lines.Add("Written by the compact-checkpoint hook before compaction (trigger: $trigger) and overwritten by")
    $lines.Add('the next one. It is what the session knew before its context was summarized: re-read it, then')
    $lines.Add('the task files it names, before continuing. Per task: python .claude/scripts/task.py resume <TASK-NNN>.')
    $lines.Add('')
    $lines.Add("- Branch: $(Or-Dash $branch)")
    $lines.Add("- Compaction instructions: $(Or-Dash $instr)")
    $lines.Add('')
    $lines.Add('## Active tasks')
    $lines.Add('')
    $activeDir = Join-Path $baseCwd 'docs/tasks/active'
    $files = @()
    if (Test-Path -LiteralPath $activeDir -PathType Container) {
        $files = @(Get-ChildItem -LiteralPath $activeDir -Filter '*.md' -File | Sort-Object Name)
    }
    foreach ($f in $files) {
        $r = Get-TaskFields $f.FullName
        $lines.Add("- $($f.Name) - $(Or-Dash $r.t) (status: $(Or-Dash $r.s), owner: $(Or-Dash $r.o))")
        $lines.Add("  - checkpoint next step: $(Or-Dash $r.cn)")
        $lines.Add("  - last green commit: $(Or-Dash $r.cg)")
        $lines.Add("  - open questions: $(Or-Dash $r.cq)")
        $lines.Add("  - first unchecked item: $(Or-Dash $r.nx)")
    }
    if ($files.Count -eq 0) { $lines.Add('- none') }
    $lines.Add('')
    $lines.Add('## Uncommitted changes')
    $lines.Add('')
    $changes = @()
    if ($hasGit) { $changes = @(& git -C $baseCwd status --short 2>$null | Select-Object -First 20) }
    if ($changes.Count -gt 0) { foreach ($c in $changes) { $lines.Add("    $c") } } else { $lines.Add('- none') }

    [System.IO.File]::WriteAllText($out, (($lines -join "`n") + "`n"))
} catch { }
exit 0

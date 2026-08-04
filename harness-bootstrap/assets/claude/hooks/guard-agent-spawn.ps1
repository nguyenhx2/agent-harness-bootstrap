# guard-agent-spawn.ps1
# Event: PreToolUse   Matcher: Agent|Task
# The spawn boundary of the harness. Blocks two escapes:
#   1. Spawning an agent type that is not a roster seat (no .claude/agents/<type>.md) and not on
#      the explicit allowlist. An agent the roster does not define runs with no scope, no model
#      budget, and no maxTurns - it is outside the harness by construction.
#   2. Overriding a roster seat's model at spawn time. The roster is where cost and capability are
#      decided; change the roster file, not the spawn.
#
# Read-only built-in types may be permitted in .claude/hooks/spawn-allowlist (one name per line,
# '#' comments). The shipped default allows Explore and Plan - both read-only - and nothing else.
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

$baseCwd = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }
$agentsDir = Join-Path $baseCwd '.claude/agents'
$allowlist = Join-Path $baseCwd '.claude/hooks/spawn-allowlist'

# No harness in this repo: nothing to guard against, do not break other projects.
if (-not (Test-Path $agentsDir)) { exit 0 }

$stype = $payload.tool_input.subagent_type

# --- 1. roster membership -------------------------------------------------
if (-not $stype) {
    [Console]::Error.WriteLine("BLOCKED: this spawn names no subagent_type, so it would run a generic agent outside the harness (no scope, no model budget, no maxTurns). Dispatch a roster seat from .claude/agents/ instead, or add the type to .claude/hooks/spawn-allowlist if the team decides it is safe.")
    exit 2
}

$seatFile = Join-Path $agentsDir "$stype.md"
$allowed = Test-Path $seatFile
if (-not $allowed -and (Test-Path $allowlist)) {
    foreach ($line in Get-Content $allowlist) {
        $name = ($line -replace '#.*$', '').Trim()
        if ($name -and $name -eq $stype) { $allowed = $true; break }
    }
}
if (-not $allowed) {
    [Console]::Error.WriteLine("BLOCKED: '$stype' is not a roster seat (.claude/agents/$stype.md does not exist) and is not in .claude/hooks/spawn-allowlist. Agents outside the roster run with no scope, no cost budget, and no turn cap. Use a roster seat, or ask the user to extend the roster or the allowlist.")
    exit 2
}

# --- 2. model pinning (roster seats only) ---------------------------------
$override = $payload.tool_input.model
if ($override -and (Test-Path $seatFile)) {
    $pinned = $null
    $inFm = $false
    foreach ($line in Get-Content $seatFile) {
        if ($line -match '^---\s*$') { if ($inFm) { break } else { $inFm = $true; continue } }
        if ($inFm -and $line -match '^model:\s*(\S+)') { $pinned = $Matches[1]; break }
    }
    if ($pinned -and $override -ne $pinned) {
        [Console]::Error.WriteLine("BLOCKED: spawn overrides '$stype' from its roster model '$pinned' to '$override'. The roster is where cost and capability are decided (.claude/rules/model-policy.md). Edit .claude/agents/$stype.md if the seat's model should change.")
        exit 2
    }
}

# --- 3. task linkage for write-capable seats ------------------------------
# A dispatch to a seat that can Edit or Write must name a registered task, or the work is an
# orphan the board cannot see. Read-only seats may be dispatched freely.
if (Test-Path $seatFile) {
    $toolsLine = $null
    $inFm2 = $false
    foreach ($line in Get-Content $seatFile) {
        if ($line -match '^---\s*$') { if ($inFm2) { break } else { $inFm2 = $true; continue } }
        if ($inFm2 -and $line -match '^tools:\s*(.+)$') { $toolsLine = $Matches[1]; break }
    }
    if ($toolsLine -and $toolsLine -match '(^|[,\s])(Edit|Write)(,|\s|$)') {
        $activeDir = Join-Path $baseCwd 'docs/tasks/active'
        if (Test-Path $activeDir) {
            $taskId = $null
            if ($payload.tool_input.prompt -match 'TASK-\d{1,5}') { $taskId = $Matches[0] }
            if (-not $taskId) {
                [Console]::Error.WriteLine("BLOCKED: '$stype' can write, but this dispatch names no TASK-NNN. Work with no registered task is invisible to the board and becomes an orphan. Register the task (see /new-task), put its code in the dispatch prompt, and dispatch again.")
                exit 2
            }
            if (-not (Get-ChildItem -Path $activeDir -Filter "*$taskId*" -ErrorAction SilentlyContinue)) {
                [Console]::Error.WriteLine("BLOCKED: this dispatch names $taskId but docs/tasks/active/ holds no such task file. A Planned or Active task lives in active/ (task-control.md). Register it first, then dispatch.")
                exit 2
            }
        }
    }
}

exit 0

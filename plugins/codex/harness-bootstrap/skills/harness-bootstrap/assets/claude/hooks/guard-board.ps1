# guard-board.ps1
# Event: PreToolUse   Matcher: Edit|Write (a MultiEdit payload is handled too, if a host sends one)
# Flag: none - ships with every harness, beside .claude/scripts/task.py
# Enforces: .claude/rules/task-tracking.md (one writer for task state)
# BLOCKS (exit 2) a hand edit to the task rows of docs/tasks/master-plan.md: an Edit touching a
# `| TASK-NNN |` row, a Write replacing an existing board, or any MultiEdit of it. task.py writes
# through Bash and is never seen here; the first Write that creates the board, and Edits to the
# Phases table or prose, are allowed.
#
# WHY BLOCK, NOT WARN: see guard-board.sh - board/file drift is what task.py exists to prevent.
#
# PARITY CONTRACT: guard-board.sh and guard-board.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (reason on stderr, shown
# to Claude); exit 0 = allow. Fails OPEN on an unreadable payload.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$hint = 'Use the task CLI, which updates the row, the task file status: and its folder together: python .claude/scripts/task.py move <TASK-NNN> <Planned|Active|Blocked|Pending|Done> --note "..." (task.py new "<title>" ... adds a task; task.py check reports drift).'

$tool = [string]$payload.tool_name
$path = ([string]$payload.tool_input.file_path) -replace '\\', '/'
if (-not $path) { exit 0 }
if (-not ($path -ceq 'docs/tasks/master-plan.md' -or $path -ceq './docs/tasks/master-plan.md' -or $path -clike '*/docs/tasks/master-plan.md')) { exit 0 }

if ($tool -ceq 'MultiEdit') {
    [Console]::Error.WriteLine("BLOCKED by guard-board: a MultiEdit of docs/tasks/master-plan.md is refused whole - task rows are written only by task.py. $hint Edit the Phases table or prose with a single Edit instead.")
    exit 2
}
if ($tool -ceq 'Write') {
    $baseCwd = if ($payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }
    $abs = if ($path -cmatch '^(/|[A-Za-z]:/)') { $path } else { (($baseCwd -replace '\\', '/').TrimEnd('/')) + '/' + $path }
    if (-not (Test-Path -LiteralPath $abs -PathType Leaf)) { exit 0 }
    [Console]::Error.WriteLine("BLOCKED by guard-board: rewriting docs/tasks/master-plan.md would replace task rows by hand. $hint")
    exit 2
}
$text = [string]$payload.tool_input.old_string + "`n" + [string]$payload.tool_input.new_string
if ($text -cmatch '\|\s*TASK-[0-9]+') {
    [Console]::Error.WriteLine("BLOCKED by guard-board: this edit changes a task row of docs/tasks/master-plan.md by hand. $hint")
    exit 2
}
exit 0

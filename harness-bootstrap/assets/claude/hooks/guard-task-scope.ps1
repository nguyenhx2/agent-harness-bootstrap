# guard-task-scope.ps1
# Event: PreToolUse   Matcher: Edit|Write
#
# Refuses to CREATE a task file that nobody asked for, or that is too small to be a task.
#
# The rule this enforces is in .claude/rules/task-tracking.md: a task is work the USER agreed to,
# tasks are few and large, and executing one never creates more. That rule was written first and
# was not enough - prose is what gets skipped under momentum, which is how a board ends up with a
# dozen rows for one agreed piece of work and the agreed work buried among them.
#
# Two things are checkable from the file itself, and this hook checks exactly those:
#
#   1. `requested_by:` names who asked. An agent cannot approve its own task, so an agent name is
#      refused, and so is a bare "user" - that is a claim, not a record of what was asked for.
#   2. At least two real acceptance criteria. A change with nothing observable to satisfy is a step
#      or a one-line fix, not a task.
#
# What it CANNOT check, stated plainly: whether the user really approved. Nothing in the payload
# proves that. What the field does is make the claim explicit and auditable in the file that
# outlives the session, the same way `attempts:` makes retry counts auditable.
#
# EDITING an existing task file is untouched. This fires on creation only.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow. Never blocks on an unparseable payload.

$ErrorActionPreference = 'Stop'

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }
$norm = $path -replace '\\', '/'

# Both shapes: the tool sends an absolute path, the eval and a hand-run send a repo-relative one.
if ($norm -notmatch '(^|/)docs/tasks/[^/]+/TASK-[^/]*\.md$') { exit 0 }

# Creation only. Editing an existing task is normal work.
if (Test-Path -LiteralPath $path) { exit 0 }

$body = $payload.tool_input.content
if (-not $body) { $body = $payload.tool_input.new_string }
if (-not $body) { exit 0 }

$problems = @()

$req = ''
foreach ($line in ($body -split "`r?`n")) {
    if ($line -match '^(?i)requested_by:\s*(.*)$') {
        $req = $Matches[1].Trim().Trim('"').Trim("'")
        break
    }
}

$labels = @('user', 'the user', 'agent', 'orchestrator', 'claude', 'assistant')
if (-not $req) {
    $problems += '`requested_by:` is missing. A task records who asked for it.'
} elseif ($req.StartsWith('<') -or $labels -contains $req.ToLower() -or
          @('-', 'tbd', 'todo', 'n/a') -contains $req.ToLower()) {
    if ($req.StartsWith('<')) {
        $problems += '`requested_by:` is still the template placeholder.'
    } else {
        $problems += "``requested_by: $req`` is a label, not a record. Write what was actually " +
                     'asked for, or the issue it came from - an agent cannot approve its own task.'
    }
}

# Acceptance criteria that are real: a checkbox whose text is not the template placeholder.
$real = 0
foreach ($line in ($body -split "`r?`n")) {
    $s = $line.Trim()
    if ($s -notmatch '^[-*]\s*\[[ xX]\]\s*') { continue }
    $rest = ($s -replace '^[-*]\s*\[[ xX]\]\s*', '').Trim()
    if (-not $rest -or $rest.StartsWith('<')) { continue }
    $real++
}
if ($real -lt 2) {
    $problems += "only $real real acceptance criteria. Work with nothing observable to satisfy " +
                 'is a step inside a task, or a change small enough to just make.'
}

if ($problems.Count -eq 0) { exit 0 }

[Console]::Error.WriteLine('BLOCKED: this task file does not meet the bar for opening a task.')
[Console]::Error.WriteLine('')
foreach ($p in $problems) { [Console]::Error.WriteLine($p) }
[Console]::Error.WriteLine('')
[Console]::Error.WriteLine('See .claude/rules/task-tracking.md. Tasks are few and large, and no agent opens one on')
[Console]::Error.WriteLine('its own - that includes every subagent. If this came out of something you noticed while')
[Console]::Error.WriteLine('doing something else: finish what you were given, report the finding, and let the user')
[Console]::Error.WriteLine('decide. If it is smaller than the paperwork around it, just make the change.')
exit 2

# guard-agent-scope.ps1
# Event: PreToolUse   Matcher: Edit|Write
#
# ADVISORY, NOT ENFORCED - and that is a deliberate finding, not a shortcut. Before writing this
# hook we checked whether a PreToolUse payload for Edit|Write identifies the calling subagent, the
# way it would have to in order to BLOCK a write to a module a different seat owns. It does not.
# Evidence, from this harness's own hooks:
#   - agent-history.sh/.ps1's header states plainly: subagent identity (agent_type, agent_id)
#     arrives ONLY on the SubagentStop event, and that event's payload carries NO
#     tool_input/tool_response at all - an earlier version of that hook was registered on
#     PostToolUse and archived empty files because of exactly this gap.
#   - guard-agent-spawn.ps1 reads tool_input.subagent_type, but only because IT fires on the
#     Agent|Task tool call itself (the dispatch), not on the dispatched agent's own subsequent tool
#     calls. Once a subagent starts working, its Edit/Write calls carry cwd and tool_input
#     (file_path, content) and nothing that names who is typing.
# So a hook on THIS event cannot tell "code-reviewer editing outside its lane" from "the
# orchestrator's own docs/ maintenance" from "the one dev agent this project has". Blocking on data
# that is not there would either block legitimate writes indiscriminately or silently no-op - both
# worse than an honest advisory. See hooks/README.md for the same note.
#
# What this hook does instead: using the module ownership already recorded by /code-graph
# (.claude/state/code-graph.json) and the sole in-flight task's declared scope
# (docs/tasks/active/*.md, "Related files and modules:"), it emits
# hookSpecificOutput.additionalContext when an edited file falls in a module the Active task did
# not name AND that module is owned (per the graph) by a DIFFERENT agent than the task's own
# `owner:`. That is a nudge, not a gate: it never blocks, and it stays silent whenever the picture
# is ambiguous (no graph yet, zero or more than one Active task, an unowned module) rather than
# guessing. Always exits 0.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch { exit 0 }

$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }
$baseCwd = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }

$graphPath = Join-Path $baseCwd ".claude/state/code-graph.json"
if (-not (Test-Path $graphPath)) { exit 0 }

try { $graph = Get-Content $graphPath -Raw | ConvertFrom-Json } catch { exit 0 }
if (-not $graph.modules) { exit 0 }

$normBase = ($baseCwd -replace '\\', '/').TrimEnd('/')
$norm = $path -replace '\\', '/'
if ($norm.StartsWith("$normBase/")) { $norm = $norm.Substring($normBase.Length + 1) }

$targetMod = $null
$targetOwner = $null
foreach ($modProp in $graph.modules.PSObject.Properties) {
    if ($modProp.Value.files -and ($modProp.Value.files -contains $norm)) {
        $targetMod = $modProp.Name
        $targetOwner = $modProp.Value.owner
        break
    }
}
if (-not $targetMod) {
    foreach ($modProp in $graph.modules.PSObject.Properties) {
        $pfx = $modProp.Name.TrimEnd('/')
        if ($norm -eq $pfx -or $norm.StartsWith("$pfx/")) {
            $targetMod = $modProp.Name
            $targetOwner = $modProp.Value.owner
            break
        }
    }
}
if (-not $targetMod -or -not $targetOwner -or $targetOwner -eq '-') { exit 0 }

$activeDir = Join-Path $baseCwd "docs/tasks/active"
if (-not (Test-Path $activeDir)) { exit 0 }

$activeTasks = @()
foreach ($f in Get-ChildItem -Path $activeDir -Filter "*.md" -ErrorAction SilentlyContinue) {
    $text = Get-Content $f.FullName -Raw
    if ($text -notmatch '(?s)^---\r?\n(.*?)\r?\n---\r?\n') { continue }
    $fm = $Matches[1]
    if ($fm -notmatch '(?m)^status:\s*(\S+)' -or $Matches[1] -ne 'Active') { continue }
    $owner = $null
    if ($fm -match '(?m)^owner:\s*(\S+)') { $owner = $Matches[1] }
    $modulesLine = ''
    if ($text -match 'Related files and modules:\s*(.+)') { $modulesLine = $Matches[1].Trim() }
    $activeTasks += [pscustomobject]@{ Name = $f.Name; Owner = $owner; ModulesLine = $modulesLine }
}
if ($activeTasks.Count -ne 1) { exit 0 }
$task = $activeTasks[0]

$namedPaths = @()
if ($task.ModulesLine) {
    $namedPaths = ($task.ModulesLine -split '[,;]') | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -ne '-' }
}
$inScope = $false
foreach ($p in $namedPaths) {
    $pTrim = $p.TrimEnd('/')
    if ($norm -eq $pTrim -or $norm.StartsWith("$pTrim/")) { $inScope = $true; break }
}
if ($inScope) { exit 0 }
if (-not $task.Owner -or $task.Owner -eq $targetOwner) { exit 0 }

$namedTxt = if ($task.ModulesLine) { $task.ModulesLine } else { '(none named)' }
$msg = "Advisory: this write to $norm falls in module '$targetMod' (owner per code-graph.json: $targetOwner), which the sole Active task $($task.Name) (owner: $($task.Owner)) did not name under 'Related files and modules' ($namedTxt). This may be crossing a module boundary the task brief did not scope for - confirm before continuing. (Advisory only: this hook cannot see who is calling it, so it cannot block.)"

$out = @{ hookSpecificOutput = @{ hookEventName = "PreToolUse"; additionalContext = $msg } } | ConvertTo-Json -Compress -Depth 5
Write-Output $out
exit 0

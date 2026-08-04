# graph-stale.ps1
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking. When a SOURCE file is edited and a code graph has been built, records the path in
# .claude/state/code-graph.stale so agents (and /code-graph --check) know the graph no longer
# matches the code. The rebuild itself is deliberate (/code-graph), never a side effect of an edit.
# Once the drift is large (more than 20 edited files since the last build), this ALSO emits
# hookSpecificOutput.additionalContext nudging /code-graph - same emit pattern as
# specs-reminder.ps1's fixed-literal JSON. Never blocks: always exit 0.

$ErrorActionPreference = "SilentlyContinue"

try { $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { exit 0 }
if (-not $payload) { exit 0 }

$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }
$base = $payload.cwd
if (-not $base) { $base = "." }

$norm = $path -replace '\\', '/'
$srcExts = @('.py', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.go', '.java', '.cs', '.rb', '.php', '.rs')
$ext = [System.IO.Path]::GetExtension($norm)
if ($srcExts -notcontains $ext) { exit 0 }

$graph = Join-Path $base ".claude/state/code-graph.json"
if (-not (Test-Path $graph)) { exit 0 }

$stateDir = Join-Path $base ".claude/state"
if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Force $stateDir | Out-Null }
$staleFile = Join-Path $stateDir "code-graph.stale"
Add-Content -Path $staleFile -Value $norm

$lines = (Get-Content $staleFile | Measure-Object -Line).Lines
if ($lines -gt 20) {
    $msg = "The code graph is now stale against $lines edited source file(s) - run /code-graph to refresh the module map before relying on it for dispatch decisions."
    $out = @{ hookSpecificOutput = @{ hookEventName = "PostToolUse"; additionalContext = $msg } } | ConvertTo-Json -Compress
    Write-Output $out
}
exit 0

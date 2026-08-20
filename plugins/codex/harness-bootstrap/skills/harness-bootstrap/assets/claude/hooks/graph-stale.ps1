# graph-stale.ps1
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking graph maintenance, three tiers by cost of the rebuild:
#   1. HARNESS edits (.claude/ agents, rules, commands, hooks, settings.json, disabled.json):
#      regenerate .claude/state/harness-graph.json + harness-graph.html IMMEDIATELY - the scan
#      is ~50 small files, cheap enough to rebuild as a side effect.
#   2. DOCS edits (docs/**/*.md, only when a docs graph was already built): regenerate the docs
#      graph + HTML immediately - docs trees are small too.
#   3. SOURCE edits: record the path in .claude/state/code-graph.stale; the rebuild stays
#      deliberate (/code-graph). Past 20 accumulated edits this ALSO emits
#      hookSpecificOutput.additionalContext nudging /code-graph - same emit pattern as
#      specs-reminder.ps1's fixed-literal JSON.
# Never blocks: always exit 0.

$ErrorActionPreference = "SilentlyContinue"

try { $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { exit 0 }
if (-not $payload) { exit 0 }

$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }
$base = $payload.cwd
if (-not $base) { $base = "." }

# Runs the first available interpreter: python, python3, or the Windows py launcher.
function Invoke-Py {
    param([string[]]$PyArgs)
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { & $cmd.Source @PyArgs *> $null; return }
    $cmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($cmd) { & $cmd.Source @PyArgs *> $null; return }
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { & $cmd.Source -3 @PyArgs *> $null; return }
}

$norm = $path -replace '\\', '/'

# Tier 1: harness wiring changed - rebuild the harness graph now.
if ($norm -match '(^|/)\.claude/(agents|rules|commands)/.+\.md$' -or
    $norm -match '(^|/)\.claude/hooks/.+\.(sh|ps1)$' -or
    $norm -match '(^|/)\.claude/(settings|disabled)\.json$') {
    $scanner = Join-Path $base ".claude/scripts/harness-graph.py"
    if (Test-Path $scanner) {
        Invoke-Py @($scanner, '--target', $base, '--html', '--quiet')
    }
    exit 0
}

# Tier 2: a docs file changed and a docs graph exists - rebuild it now.
if ($norm -match '(^|/)docs/.+\.md$') {
    $docsJson = Join-Path $base ".claude/state/docs-graph.json"
    $docsScript = Join-Path $base ".claude/scripts/docs-graph.py"
    if ((Test-Path $docsJson) -and (Test-Path $docsScript)) {
        Invoke-Py @($docsScript, '--target', $base)
        Invoke-Py @((Join-Path $base ".claude/scripts/graph-html.py"), '--target', $base)
    }
    exit 0
}

# Tier 3: only source files invalidate the code graph.
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

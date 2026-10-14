# graph-stale.ps1
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking graph maintenance, two tiers by edited path:
#   1. HARNESS edits (.claude/ agents, rules, commands, hooks, settings.json, disabled.json):
#      regenerate .claude/state/harness-graph.json + harness-graph.html IMMEDIATELY - the scan
#      is ~50 small files, cheap enough to rebuild as a side effect.
#   2. SOURCE edits, once a module-boundary map exists (docs/context/code-graph.md, or the
#      machine copy in .claude/state/): ask `code-graph.py --file` whether THIS file now imports
#      across a module line the map does not list, and pass its additionalContext through. Each
#      new edge is named once until the next /code-graph rebuild accepts it.
# The docs graph is no longer rebuilt here: it is a check run on demand (/docs-graph).
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

# Tier 2: a source file changed - did it add a cross-module edge the boundary map lacks?
$srcExts = @('.py', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.go', '.java', '.cs', '.rb', '.php', '.rs')
$ext = [System.IO.Path]::GetExtension($norm)
if ($srcExts -notcontains $ext) { exit 0 }

$helper = Join-Path $base ".claude/scripts/code-graph.py"
if (-not (Test-Path $helper)) { exit 0 }
if (-not ((Test-Path (Join-Path $base "docs/context/code-graph.md")) -or
          (Test-Path (Join-Path $base ".claude/state/code-graph.json")))) { exit 0 }

# The helper prints the PostToolUse JSON itself, or nothing. Unlike Invoke-Py above, its stdout
# is the hook's output, so it is passed through rather than discarded.
$cmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $cmd) { $cmd = Get-Command python3 -ErrorAction SilentlyContinue }
if ($cmd) {
    $out = & $cmd.Source $helper --target $base --file $path --hook 2>$null
} else {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if (-not $cmd) { exit 0 }
    $out = & $cmd.Source -3 $helper --target $base --file $path --hook 2>$null
}
if ($out) { Write-Output ($out -join "`n") }
exit 0

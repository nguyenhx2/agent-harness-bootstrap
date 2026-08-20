# protect-adr.ps1
# Event: PreToolUse   Matcher: Edit|Write
# Blocks edits to ADRs whose on-disk status is "Accepted" (ADRs are immutable; a change means a
# NEW ADR that supersedes the old one).
#
# TIMING NOTE: the hook reads the ON-DISK (pre-edit) status, so the very edit that flips
# `proposed -> accepted` passes - it sees the OLD status - but every edit AFTER it is blocked,
# including fixing now-stale prose in the same file. Land all other edits FIRST and make the
# accept-flip its own final commit; after that the file is frozen.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow.

$ErrorActionPreference = 'Stop'

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0   # unparseable payload: fail open, the settings.json deny rules remain the backstop
}

$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }

# Resolve against the payload's cwd so a relative file_path is checked against the right file.
$base = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }
try {
    $abs = if ([System.IO.Path]::IsPathRooted($path)) { $path } else { Join-Path $base $path }
    $abs = [System.IO.Path]::GetFullPath($abs)
} catch {
    $abs = $path
}

$norm = $abs -replace '\\', '/'
if ($norm -notmatch 'docs/architecture/decisions/ADR-\d+[^/]*\.md$') { exit 0 }

if (Test-Path -LiteralPath $abs) {
    $head = Get-Content -LiteralPath $abs -TotalCount 10 -ErrorAction SilentlyContinue
    if ($head -match '^status:\s*Accepted') {
        [Console]::Error.WriteLine("BLOCKED: this ADR has status Accepted and is immutable. Create a new ADR with /new-adr and mark the old one 'Superseded by ADR-NNN' (only the status line may change).")
        exit 2
    }
}
exit 0

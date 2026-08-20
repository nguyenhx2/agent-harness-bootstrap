# protect-repos.ps1
# Event: PreToolUse   Matcher: Edit|Write
# Layer 2 of the separation-of-duties enforcement for AUDIT workspaces: resolves the target path
# (relative paths against the payload's cwd, `..` collapsed, separators normalized) and blocks any
# Edit/Write inside a product repo dir. Audit agents are READ-ONLY on product source: they record
# findings under docs/findings/ and the user applies the fixes.
#
# CASE-SENSITIVITY TRAP: PowerShell -match / -like / -eq are case-INSENSITIVE by default. A naive
# `$norm -like "$root/$r/*"` with repo 'Backend' ALSO matches docs/findings/backend/... (the
# findings dir is conventionally the lowercased repo name), silently blocking the agent's own
# finding writes. Compare path SEGMENTS with -ceq only; do NOT "simplify" back to -match/-like.
#
# {{REPO_DIR_LIST}} = the repo dir names in EXACT on-disk casing, PowerShell array literal form,
# e.g. 'Repo-One', 'repo-two'. On a case-insensitive filesystem, if a repo dir is plausibly
# referenced under more than one casing, list every casing actually observed; the settings.json
# deny globs and rules/agent-guardrails.md remain the backstop for exotic spellings.
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

$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }

try {
    $base = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }
    if (-not [System.IO.Path]::IsPathRooted($path)) { $path = Join-Path $base $path }
    $full = [System.IO.Path]::GetFullPath($path)
} catch {
    exit 0   # unparseable path: let the settings.json deny globs and the tool decide
}

$norm  = ($full -replace '\\', '/').TrimEnd('/')
$root  = (([System.IO.Path]::GetFullPath('{{WORKSPACE_ROOT}}')) -replace '\\', '/').TrimEnd('/')
$repos = @({{REPO_DIR_LIST}})

if ($norm.Length -gt ($root.Length + 1) -and $norm.Substring(0, $root.Length + 1) -ceq "$root/") {
    # Inside the workspace root: only the FIRST segment of the relative path can name a product
    # repo. docs/findings/backend/... has first segment 'docs' -> passes even if a repo is 'Backend'.
    $first = ($norm.Substring($root.Length + 1) -split '/')[0]
    foreach ($r in $repos) {
        if ($first -ceq $r) {
            [Console]::Error.WriteLine("BLOCKED: '$norm' is inside product repo '$r'. This is a read-only audit workspace (separation of duties): agents never modify product source. Record a finding in docs/findings/ instead; the user applies fixes.")
            exit 2
        }
    }
} else {
    # Outside the workspace root (unexpected for an audit agent): conservative - block if ANY
    # path segment names a product repo, still case-sensitively.
    foreach ($seg in ($norm -split '/')) {
        foreach ($r in $repos) {
            if ($seg -ceq $r) {
                [Console]::Error.WriteLine("BLOCKED: '$norm' contains product-repo dir '$r'. Read-only audit workspace: agents never modify product source.")
                exit 2
            }
        }
    }
}
exit 0

# guard-config.ps1
# Event: ConfigChange   Matcher: user_settings|project_settings|local_settings
# Flag: hooks_strict
# Enforces: .claude/rules/agent-guardrails.md (the guardrails cannot be switched off mid-session)
# BLOCKS (exit 2) a settings change, made while a session runs, that sets disableAllHooks, sets
# defaultMode bypassPermissions, adds an allow rule that pre-approves any command (bare Bash or
# PowerShell, a wildcard-only specifier such as Bash(**) or Bash(*:*), or a shell or wrapper by
# name such as Bash(bash:*) or Bash(sh -c:*)), removes a rule from permissions.deny (compared with
# the last accepted list in .claude/state/config-guard/, or HEAD for project settings), unregisters
# a hook still installed in .claude/hooks/ (project settings), or deletes .claude/settings.json.
# The blocked change stays on disk and loads
# in the next session. Claude Code shows a blocked ConfigChange to nobody, so every refusal is also
# appended to .claude/state/config-guard.log.
#
# WHY BLOCK: see guard-config.sh.
#
# PARITY CONTRACT: guard-config.sh and guard-config.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the ConfigChange JSON payload on stdin. exit 2 = block the change; exit 0 =
# allow. Fails OPEN on an unreadable payload or an unparseable settings file.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$src = [string]$payload.source
if (@('user_settings', 'project_settings', 'local_settings') -cnotcontains $src) { exit 0 }
$baseCwd = if ($payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }
$file = [string]$payload.file_path
if (-not $file) {
    if ($src -ceq 'project_settings') { $file = Join-Path $baseCwd '.claude/settings.json' }
    elseif ($src -ceq 'local_settings') { $file = Join-Path $baseCwd '.claude/settings.local.json' }
    else { exit 0 }
}

function Refuse([string]$why) {
    try {
        if (Test-Path -LiteralPath (Join-Path $baseCwd '.claude') -PathType Container) {
            $log = Join-Path $baseCwd '.claude/state/config-guard.log'
            New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
            $stamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
            [System.IO.File]::AppendAllText($log, "$stamp`t$src`t$why`n")
        }
    } catch { }
    [Console]::Error.WriteLine("BLOCKED by guard-config: $why The change was not applied to this session (it is still on disk, so a new session would load it). Disable a hook with /harness-toggle; change permissions deliberately, between sessions.")
    exit 2
}

# Test-UnrestrictedShell RULE -> $true when an allow rule pre-approves ANY command: Bash or
# PowerShell bare, a specifier that is only wildcards and colons once spaces are dropped, or one
# whose command is itself a shell or a run-anything wrapper. Same list as the bash twin.
function Test-UnrestrictedShell([string]$e) {
    if ($e -ceq 'Bash' -or $e -ceq 'PowerShell') { return $true }
    $m = [regex]::Match($e, '^(Bash|PowerShell)\((.*)\)$')
    if (-not $m.Success) { return $false }
    $inner = $m.Groups[2].Value
    $flat = $inner -replace '[ \t]', ''
    if ($flat -cmatch '^[*:]+$') { return $true }
    $first = (($inner -replace '^\s+', '') -replace '[\s:].*$', '').ToLower()
    if ($first.EndsWith('.exe')) { $first = $first.Substring(0, $first.Length - 4) }
    return (@('bash', 'sh', 'zsh', 'dash', 'ksh', 'fish', 'pwsh', 'powershell', 'cmd', 'env', 'eval', 'exec', 'sudo', 'xargs', 'nohup') -ccontains $first)
}

if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
    if ($src -ceq 'project_settings') { Refuse '.claude/settings.json was deleted, which unregisters every hook.' }
    exit 0
}

try {
    $text = [System.IO.File]::ReadAllText($file)
    $cfg = $text | ConvertFrom-Json
    if ($null -eq $cfg -or $cfg -is [string] -or $cfg -is [array]) { exit 0 }
} catch {
    exit 0
}

if ($cfg.disableAllHooks -eq $true) { Refuse 'disableAllHooks: true switches off every guardrail hook.' }
if ($cfg.permissions -and [string]$cfg.permissions.defaultMode -ceq 'bypassPermissions') {
    Refuse 'defaultMode bypassPermissions removes every permission prompt.'
}
if ($cfg.permissions -and $cfg.permissions.allow) {
    foreach ($a in @($cfg.permissions.allow)) {
        if ($a -is [string] -and (Test-UnrestrictedShell $a)) {
            Refuse "the allow rule '$a' pre-approves every command (a bare wildcard, or a shell or wrapper launched by name)."
        }
    }
}

# A deny list only grows mid-session. Baseline: the deny list this hook last accepted for this
# source, else (project settings) the one committed at HEAD. Nothing to compare -> nothing to say.
$stateDir = Join-Path $baseCwd '.claude/state/config-guard'
$snap = Join-Path $stateDir "$src.deny"
$newDeny = @()
if ($cfg.permissions -and $cfg.permissions.deny) {
    $newDeny = @(@($cfg.permissions.deny) | Where-Object { $_ -is [string] } | Sort-Object -Unique -CaseSensitive)
}
$baseline = @()
if (Test-Path -LiteralPath $snap -PathType Leaf) {
    $baseline = @([System.IO.File]::ReadAllLines($snap) | ForEach-Object { $_.TrimEnd("`r") } | Where-Object { $_ })
} elseif ($src -ceq 'project_settings' -and (Get-Command git -ErrorAction SilentlyContinue)) {
    $baseNorm = (($baseCwd -replace '\\', '/').TrimEnd('/')) + '/'
    $fileNorm = $file -replace '\\', '/'
    if ($fileNorm.StartsWith($baseNorm)) {
        $rel = $fileNorm.Substring($baseNorm.Length)
        $headText = & git -C $baseCwd show "HEAD:$rel" 2>$null
        if ($LASTEXITCODE -eq 0 -and $headText) {
            try {
                $headCfg = (($headText | Out-String) | ConvertFrom-Json)
                if ($headCfg.permissions -and $headCfg.permissions.deny) {
                    $baseline = @(@($headCfg.permissions.deny) | Where-Object { $_ -is [string] })
                }
            } catch { }
        }
    }
}
$lost = @($baseline | Where-Object { $newDeny -cnotcontains $_ })
if ($lost.Count -gt 0) {
    Refuse "permissions.deny lost $($lost.Count) rule(s), for example '$($lost[0])'. A deny list only grows while a session runs."
}

$hooksDir = Join-Path $baseCwd '.claude/hooks'
if ($src -ceq 'project_settings' -and (Test-Path -LiteralPath $hooksDir -PathType Container)) {
    foreach ($f in (Get-ChildItem -LiteralPath $hooksDir -File | Where-Object { $_.Extension -ceq '.sh' -or $_.Extension -ceq '.ps1' } | Sort-Object Name)) {
        if (-not $text.Contains("hooks/$($f.BaseName).")) {
            Refuse "hook $($f.BaseName) is still installed in .claude/hooks/ but no longer registered in settings.json."
        }
    }
}

# Accepted: this deny list is the baseline the next change is compared against.
try {
    if (Test-Path -LiteralPath (Join-Path $baseCwd '.claude') -PathType Container) {
        New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
        [System.IO.File]::WriteAllText($snap, (($newDeny -join "`n") + "`n"))
    }
} catch { }
exit 0

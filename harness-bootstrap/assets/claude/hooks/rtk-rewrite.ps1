# rtk-rewrite.ps1
# Event: PreToolUse   Matcher: Bash
# OPTIONAL, ships only with the `rtk` flag. Offers a Bash command to rtk
# (https://github.com/rtk-ai/rtk, Apache-2.0), which rewrites it into a form whose OUTPUT is
# smaller: `git status` becomes `rtk git status`, same information, fewer tokens back. Measured
# on rtk's own repo: `git log -30` 17,653 chars to 6,380.
#
# PARITY CONTRACT: rtk-rewrite.ps1 and rtk-rewrite.sh must stay behaviorally EQUIVALENT - same
# version gate, same pass-through patterns, same silence when rtk is absent. If you change one,
# change the other. The eval fires the identical payloads at both flavors.
#
# WHY A WRAPPER INSTEAD OF REGISTERING `rtk hook claude` DIRECTLY. Three reasons, all load-bearing:
#   1. /harness-toggle resolves a hook to .claude/hooks/<name>.{sh,ps1}. A bare binary
#      registration has no file, so it could never be disabled through the sanctioned path.
#   2. The eval can fire payloads at a file. It cannot fire them at someone else's binary.
#   3. It puts a boundary we own between a third-party binary and the tool call, which is the
#      whole premise of this harness.
#
# THE PASS-THROUGH RULE, and it is the point of this file. A command that any of our own guards
# inspects is NEVER handed to rtk - it is passed through untouched. rtk rewrites `git commit -m x`
# into `rtk git commit -m x` (verified), and while check-commit-msg's anchor now tolerates a
# wrapper prefix, a compressor must never be the reason a guard did not fire. Pass-through is
# always safe: no rewrite means the original command, which is what would have happened anyway.
#
# TRUST SURFACE WORTH KNOWING ABOUT: rtk reads .rtk/filters.toml from the repo, and a filter file
# can change what command output the model sees. rtk itself treats an untrusted one as hostile and
# skips it (its own docs describe hiding malicious code or suppressing scanner output as the
# threat). The generated .gitignore ignores .rtk/ so a local config never travels by accident.
#
# NETWORK: rtk has a telemetry endpoint compiled in. It is gated on explicit consent that defaults
# to off, and settings.json sets RTK_TELEMETRY_DISABLED=1 as a second lock. This is a NAMED
# relaxation of the no-network-in-hooks rule - see hooks/README.md.
#
# Contract: reads the PreToolUse JSON payload on stdin. Always exit 0 - this hook never blocks.
# On stdout: either rtk's hookSpecificOutput JSON, or nothing at all (meaning "no rewrite").

$MinVersion = [version]'0.45.0'

try {
    $payload = [Console]::In.ReadToEnd()
    if (-not $payload) { exit 0 }
} catch {
    exit 0
}

# rtk absent is the normal case: the flag ships the hook, the user installs the binary separately.
# Silence matters here - a nag on every Bash call would be worse than the tokens it saves.
$rtk = Get-Command rtk -ErrorAction SilentlyContinue
if (-not $rtk) { exit 0 }

# Version gate. Below the pinned minimum the payload contract is not one we tested against, so we
# do nothing rather than guess.
try {
    $verRaw = & rtk --version 2>$null
    $m = [regex]::Match(($verRaw -join ' '), '[0-9]+\.[0-9]+\.[0-9]+')
    if (-not $m.Success) { exit 0 }
    if ([version]$m.Value -lt $MinVersion) { exit 0 }
} catch {
    exit 0
}

# --- extract the command --------------------------------------------------------------------
try {
    $cmd = ($payload | ConvertFrom-Json).tool_input.command
} catch {
    exit 0
}
if (-not $cmd) { exit 0 }

# --- the pass-through rule ------------------------------------------------------------------
# GuardedGit mirrors guard-main-commit's anchor. GuardedEnv mirrors protect-secrets' cmdPattern,
# deliberately WITHOUT that hook's scrubs: protect-secrets subtracts the legitimate forms because
# it must allow them, whereas here the conservative answer to "does this command mention a .env
# file at all" is simply not to touch it.
# If either hook's matcher changes, change the twin here - a drift means a guarded command
# reaching rtk.
$GuardedGit = '(^|[^a-zA-Z0-9_.-])git\s+(commit|push)([^a-zA-Z0-9_-]|$)'
$GuardedEnv = '(^|[^a-zA-Z0-9_./-])[^\s]*\.env(\.[a-zA-Z0-9_-]+)?(\s|$|"|''|;|&)'

if ($cmd -cmatch $GuardedGit) { exit 0 }
if ($cmd -match  $GuardedEnv) { exit 0 }

# --- hand it to rtk -------------------------------------------------------------------------
# The payload goes to rtk through a temp FILE redirected by cmd, not through a PowerShell pipe.
# This is not a stylistic choice. `$payload | & rtk hook claude` and a redirected
# System.Diagnostics.Process both deliver NOTHING to rtk once this script has already consumed
# its own stdin with ReadToEnd: rtk answers "Failed to parse JSON input: expected value at line 1
# column 1", which is serde's message for empty input, while still exiting 0. The .sh twin has no
# such problem, so the failure was silent and one-sided - the exact parity break this hook's
# contract exists to prevent. Verified: pipe and Process both return 0 bytes here, the redirect
# returns the 143-byte rewrite.
# stderr is discarded: rtk writes an install nag there, and anything on our stderr would reach
# the model as if this hook had something to say. stdout is relayed verbatim, so the rewrite
# contract stays rtk's to define rather than something we re-encode and get wrong.
$tmp = $null
try {
    $tmp = [System.IO.Path]::GetTempFileName()
    # WriteAllBytes, not Set-Content: Windows PowerShell would prepend a UTF-8 BOM and rtk would
    # reject the payload. StandardInputEncoding cannot help - it does not exist on 5.1.
    [System.IO.File]::WriteAllBytes($tmp, [System.Text.Encoding]::UTF8.GetBytes($payload))
    $out = & cmd.exe /c "`"$($rtk.Source)`" hook claude < `"$tmp`" 2>NUL"
    if ($LASTEXITCODE -ne 0) { exit 0 }
    $joined = ($out -join "`n")
    if ($joined) { [Console]::Out.Write($joined) }
} catch {
    exit 0
} finally {
    if ($tmp) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
}
exit 0

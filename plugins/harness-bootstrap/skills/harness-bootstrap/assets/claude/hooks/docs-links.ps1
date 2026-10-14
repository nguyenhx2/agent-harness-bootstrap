# docs-links.ps1
# Event: PostToolUse   Matcher: Edit|Write
# Flag: purpose_docs
# Enforces: .claude/rules/docs-workflow.md (a link is a promise that the target exists)
# WARNS (additionalContext, exit 0) when a Markdown file just written contains relative links
# whose target does not exist, resolved against the file's own directory. Lists up to 5. Skips
# fenced code blocks, URLs with a scheme, same-page anchors and site-absolute paths.
#
# WHY WARN, NOT BLOCK: see docs-links.sh - a restructure breaks links between its steps.
#
# PARITY CONTRACT: docs-links.sh and docs-links.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the PostToolUse JSON payload on stdin. Emits hookSpecificOutput JSON on stdout,
# or nothing. Always exit 0.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json

    $path = ([string]$payload.tool_input.file_path) -replace '\\', '/'
    if (-not $path) { exit 0 }
    if ($path -cnotmatch '\.(md|MD|markdown)$') { exit 0 }
    $baseCwd = if ($payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }
    $abs = if ($path -cmatch '^(/|[A-Za-z]:/)') { $path } else { (($baseCwd -replace '\\', '/').TrimEnd('/')) + '/' + $path }
    if (-not (Test-Path -LiteralPath $abs -PathType Leaf)) { exit 0 }
    $dir = $abs.Substring(0, $abs.LastIndexOf('/'))

    $targets = @()
    $fence = $false
    foreach ($line in [System.IO.File]::ReadAllLines($abs)) {
        if ($line -cmatch '^[ \t]*(```|~~~)') { $fence = -not $fence; continue }
        if ($fence) { continue }
        foreach ($m in [regex]::Matches($line, '\]\(([^)]+)\)')) { $targets += $m.Groups[1].Value }
    }

    $broken = @()
    $n = 0
    foreach ($t in $targets) {
        if (-not $t) { continue }
        if ($t.StartsWith('<')) { $t = $t.Substring(1) }
        $gt = $t.IndexOf('>'); if ($gt -ge 0) { $t = $t.Substring(0, $gt) }
        $sp = $t.IndexOf(' '); if ($sp -ge 0) { $t = $t.Substring(0, $sp) }
        if ($t.StartsWith('#') -or $t.StartsWith('/')) { continue }
        if ($t -cmatch '^[A-Za-z][A-Za-z0-9+.-]*:') { continue }
        $p = $t
        $h = $p.IndexOf('#'); if ($h -ge 0) { $p = $p.Substring(0, $h) }
        $q = $p.IndexOf('?'); if ($q -ge 0) { $p = $p.Substring(0, $q) }
        if (-not $p) { continue }
        $p = $p.Replace('%20', ' ')
        if (-not (Test-Path -LiteralPath "$dir/$p")) {
            $n++
            if ($n -le 5) { $broken += ($t -replace '["\\]', '' -replace '[\x00-\x1f]', '') }
        }
    }
    if ($n -eq 0) { exit 0 }

    $name = $path -replace '["\\]', '' -replace '[\x00-\x1f]', ''
    $out = @{
        hookSpecificOutput = @{
            hookEventName     = 'PostToolUse'
            additionalContext = "docs-links: $name has $n relative link(s) whose target does not exist: $($broken -join ', '). Fix the path, or remove the link if the target is gone."
        }
    } | ConvertTo-Json -Compress -Depth 5
    [Console]::Out.WriteLine($out)
} catch { }
exit 0

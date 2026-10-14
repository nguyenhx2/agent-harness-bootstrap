# research-sources.ps1
# Event: PostToolUse   Matcher: Edit|Write
# Flag: purpose_research
# Enforces: .claude/rules/docs-workflow.md (a research claim carries its source)
# WARNS (additionalContext, exit 0) when a Markdown research note (under research/, findings/,
# notes/, report(s)/, brief(s)/, sources/ or literature/) has 400+ characters of text and cites
# nothing: no URL, DOI, arXiv id, footnote, Sources/References heading, "Source:" line, or explicit
# "Assumption:" / "Unsourced:" label.
#
# WHY WARN, NOT BLOCK: see research-sources.sh - notes are written in passes.
#
# PARITY CONTRACT: research-sources.sh and research-sources.ps1 must stay behaviorally
# EQUIVALENT. (?im) gives the same per-line ^ and case-insensitivity as grep -Ei.
#
# Contract: reads the PostToolUse JSON payload on stdin. Emits hookSpecificOutput JSON on stdout,
# or nothing. Always exit 0.

$MinChars = 400
$SourceRe = '(?im)(https?://|doi:|doi\.org/|arxiv|\[\^[^\]]+\]|^#+\s*(sources|references|bibliography|citations)|(^|[^a-z])sources?:|assumption:|unsourced:)'

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json

    $path = ([string]$payload.tool_input.file_path) -replace '\\', '/'
    if (-not $path) { exit 0 }
    if ($path -notmatch '\.(md|markdown)$') { exit 0 }
    if ("/$path" -notmatch '/(research|findings|notes|reports?|briefs?|sources|literature)/') { exit 0 }

    $baseCwd = if ($payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }
    $abs = if ($path -cmatch '^(/|[A-Za-z]:/)') { $path } else { (($baseCwd -replace '\\', '/').TrimEnd('/')) + '/' + $path }
    if (-not (Test-Path -LiteralPath $abs -PathType Leaf)) { exit 0 }

    $text = [System.IO.File]::ReadAllText($abs)
    $chars = ($text -replace '[ \t\r\n]', '').Length
    if ($chars -lt $MinChars) { exit 0 }
    if (($text -replace "`r", '') -match $SourceRe) { exit 0 }

    $name = $path -replace '["\\]', '' -replace '[\x00-\x1f]', ''
    $out = @{
        hookSpecificOutput = @{
            hookEventName     = 'PostToolUse'
            additionalContext = "research-sources: $name makes claims but cites no source - no URL, DOI, footnote, or Sources section. Give each factual claim its source as you check it, or label it explicitly (Assumption: / Unsourced:) so a reader can tell evidence from inference."
        }
    } | ConvertTo-Json -Compress -Depth 5
    [Console]::Out.WriteLine($out)
} catch { }
exit 0

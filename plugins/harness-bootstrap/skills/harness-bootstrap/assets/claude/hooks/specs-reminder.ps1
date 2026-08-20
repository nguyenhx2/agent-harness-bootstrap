# specs-reminder.ps1
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking. When a file under docs/specs/ (other than the revision-history file itself) is
# edited, emits hookSpecificOutput.additionalContext reminding Claude to update the revision
# history and sync the related PRD. Never blocks: always exit 0.
#
# Contract: reads the PostToolUse JSON payload on stdin. Structured output goes on stdout as JSON;
# exit 0 = allow (PostToolUse cannot un-do the tool call anyway).

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }

$norm = $path -replace '\\', '/'
if ($norm -match 'docs/specs/' -and $norm -notmatch '13-revision-history\.md$') {
    $out = @{
        hookSpecificOutput = @{
            hookEventName     = 'PostToolUse'
            additionalContext = 'Reminder: you just edited docs/specs/. If this is a requirement change (not a typo/format fix), update docs/specs/13-revision-history.md and sync the related PRD in docs/requirements/.'
        }
    } | ConvertTo-Json -Compress -Depth 5
    [Console]::Out.WriteLine($out)
}
exit 0

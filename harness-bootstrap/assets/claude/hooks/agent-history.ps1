# agent-history.ps1
# Event: SubagentStop   Matcher: * (every subagent)
#
# WHY SubagentStop AND NOT PostToolUse: an earlier version of this hook was registered as
# PostToolUse with matcher "Task|Agent" and read $payload.tool_input / $payload.tool_response.
# That was wrong. Claude Code has a dedicated SubagentStop event that fires when a subagent
# finishes, and its payload has NO tool_input/tool_response at all - so the old hook archived
# empty files. SubagentStop is the correct surface. The subagent tool is `Agent` (there is no
# `Task` tool); with SubagentStop we do not name the tool at all.
#
# SubagentStop payload fields used here:
#   cwd                    - session working dir; ALL paths resolve against this, never a bare
#                            relative path (the hook process's cwd is not the project's)
#   agent_type             - the subagent's type/name
#   agent_id               - the subagent's identifier
#   agent_transcript_path  - JSONL transcript of the SUBAGENT's own run (preferred source)
#   transcript_path        - JSONL transcript of the parent session (fallback)
#
# Non-blocking audit trail: archives every completed subagent run (the prompt it was given + its
# final response) as one markdown file under .claude/state/history/ (gitignore .claude/state/).
# The history-tracker agent reads and curates the archive.
#
# Contract: ALWAYS exits 0. This hook must never block a run and never throw.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json

    # --- resolve the archive dir against the payload's cwd ------------------------------------
    $base = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }
    $dir  = Join-Path $base '.claude/state/history'
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $agent = if ($payload.agent_type) { $payload.agent_type } else { 'agent' }
    $agentId = if ($payload.agent_id) { $payload.agent_id } else { '' }

    # --- pull the prompt + final response out of the subagent transcript ----------------------
    # Transcript is JSONL: one object per line, top-level `type` ('user'|'assistant') and a
    # `message` object with `role` and a `content` array of blocks (text / tool_use / tool_result).
    $tp = $payload.agent_transcript_path
    if (-not $tp) { $tp = $payload.transcript_path }
    if ($tp -and -not [System.IO.Path]::IsPathRooted($tp)) { $tp = Join-Path $base $tp }

    function Get-BlockText($msg) {
        if (-not $msg) { return '' }
        $c = $msg.content
        if (-not $c) { return '' }
        if ($c -is [string]) { return $c }
        $parts = @()
        foreach ($b in $c) {
            if ($b.type -eq 'text' -and $b.text) { $parts += $b.text }
        }
        return ($parts -join "`n")
    }

    $prompt = ''
    $response = ''
    if ($tp -and (Test-Path -LiteralPath $tp)) {
        foreach ($line in (Get-Content -LiteralPath $tp -ErrorAction SilentlyContinue)) {
            if (-not $line.Trim()) { continue }
            $entry = $null
            try { $entry = $line | ConvertFrom-Json } catch { continue }
            if ($entry.type -eq 'user' -and -not $prompt) {
                $prompt = Get-BlockText $entry.message      # first user turn = the prompt sent in
            } elseif ($entry.type -eq 'assistant') {
                $t = Get-BlockText $entry.message
                if ($t) { $response = $t }                  # last assistant text = final response
            }
        }
    }
    if (-not $prompt)   { $prompt = '(prompt unavailable - no readable subagent transcript)' }
    if (-not $response) { $response = '(response unavailable - no readable subagent transcript)' }

    # --- slug from the first line of the prompt (SubagentStop has no `description` field) ------
    $desc = ($prompt -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 1)
    if (-not $desc) { $desc = 'run' }
    $desc = $desc.Trim()
    $slug = ($desc.ToLower() -replace '[^a-z0-9]+', '-').Trim('-')
    if (-not $slug) { $slug = 'run' }
    if ($slug.Length -gt 48) { $slug = $slug.Substring(0, 48).Trim('-') }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $rand  = -join ((97..122) | Get-Random -Count 4 | ForEach-Object { [char]$_ })
    $file  = Join-Path $dir "$stamp-$agent-$slug-$rand.md"

    $lines = @(
        "# $agent - $desc",
        '',
        "- agent_type: $agent",
        "- agent_id: $agentId",
        "- finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "- transcript: $tp",
        '',
        '## Prompt',
        '',
        '```',
        $prompt,
        '```',
        '',
        '## Response',
        '',
        '```',
        $response,
        '```'
    )
    Set-Content -LiteralPath $file -Value $lines -Encoding UTF8
} catch {
    # Swallow everything: an audit-trail hook must never break a run.
}
exit 0

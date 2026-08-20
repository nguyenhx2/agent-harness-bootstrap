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
# Detail level and retention come from .claude/state/history-level (2 lines: level, keep-count).
#   full    - whole prompt + response per run (the historical behavior; default when unreadable)
#   summary - per-run file, prompt/response truncated to 1500 chars + transcript pointer
#   minimal - one index line per run in state/history/index.md, no per-run file
#   off     - record nothing
# After a per-run write, only the newest <keep-count> files are kept (filenames start with the
# timestamp, so name order is age order; index.md is never pruned). keep-count 0 means
# NEVER PRUNE, not keep-none - minimal/off write no per-run files, so 0 is their natural
# value and nothing accumulates.
#
# Contract: ALWAYS exits 0. This hook must never block a run and never throw.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json

    # --- resolve the archive dir against the payload's cwd ------------------------------------
    $base = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }

    # --- detail level + retention: .claude/state/history-level, 2 lines -----------------------
    $level = 'full'; $keep = 200
    $cfg = Join-Path $base '.claude/state/history-level'
    if (Test-Path -LiteralPath $cfg) {
        $cfgLines = @(Get-Content -LiteralPath $cfg -TotalCount 2 -ErrorAction SilentlyContinue)
        $l1 = if ($cfgLines.Count -ge 1) { "$($cfgLines[0])".Trim() } else { '' }
        $l2 = if ($cfgLines.Count -ge 2) { "$($cfgLines[1])".Trim() } else { '' }
        if ($l1 -in @('full', 'summary', 'minimal', 'off')) { $level = $l1 }
        if ($l2 -match '^\d+$') { $keep = [int]$l2 }
    }
    if ($level -eq 'off') { exit 0 }

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

    # --- minimal: one index line, no per-run file ---------------------------------------------
    if ($level -eq 'minimal') {
        $short = if ($desc.Length -gt 120) { $desc.Substring(0, 120) } else { $desc }
        $stampNow = Get-Date -Format 'yyyyMMdd-HHmmss'
        Add-Content -LiteralPath (Join-Path $dir 'index.md') `
            -Value "$stampNow | $agent | $agentId | $short" -Encoding UTF8
        exit 0
    }

    # --- summary: cap both bodies, keep the pointer to the full transcript --------------------
    if ($level -eq 'summary') {
        if ($prompt.Length -gt 1500) {
            $prompt = $prompt.Substring(0, 1500) + "`n[truncated - full transcript: $tp]"
        }
        if ($response.Length -gt 1500) {
            $response = $response.Substring(0, 1500) + "`n[truncated - full transcript: $tp]"
        }
    }

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

    # --- retention: keep only the newest $keep per-run files (never index.md) -----------------
    if ($keep -gt 0) {
        Get-ChildItem -LiteralPath $dir -Filter '*.md' -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne 'index.md' } |
            Sort-Object Name |
            Select-Object -SkipLast $keep |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
} catch {
    # Swallow everything: an audit-trail hook must never break a run.
}
exit 0

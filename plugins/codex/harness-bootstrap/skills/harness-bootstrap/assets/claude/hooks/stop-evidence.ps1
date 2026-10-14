# stop-evidence.ps1
# Events: Stop and SubagentStop (no matcher)
# Flag: hooks_strict
# Enforces: .claude/rules/agent-guardrails.md ("done" means shown, not asserted)
# BLOCKS the stop ONCE (exit 2, reason on stderr) when the final message claims completion and
# carries no evidence - no command output, pass/fail count, exit code, "Evidence:"/"Verified"
# line, or honest "not verified".
#
# Only a session that EDITED something is held to it (an Edit/Write/MultiEdit/NotebookEdit call in
# the transcript, or, with no transcript, uncommitted changes): an answer to a question that changed
# nothing is not a completion claim. See stop-evidence.sh.
#
# WHY BLOCK, AND WHY ONLY ONCE: see stop-evidence.sh. When `stop_hook_active` is true the session
# is already continuing because of a stop hook, and this hook allows unconditionally - it can
# never loop.
#
# PARITY CONTRACT: stop-evidence.sh and stop-evidence.ps1 must stay behaviorally EQUIVALENT -
# same claim and evidence patterns, both case-insensitive. (?m) makes ^/$ line anchors here, as
# they are for grep's line-by-line match in the bash twin.
#
# Contract: reads the Stop/SubagentStop JSON payload on stdin. exit 2 = keep going (reason on
# stderr); exit 0 = allow the stop. Fails OPEN on an unreadable payload.

$Claim = '(?im)(all (the )?tests (now )?pass|tests (are )?(now )?passing|(is|are) (now )?(done|complete|completed|finished|fixed|resolved)|(task|work|implementation|feature|fix|change|changes) (is |are )?(now )?(done|complete|completed)|ready (to merge|for review|to ship)|successfully (implemented|fixed|completed|resolved)|implementation complete)'
$Evidence = '(?im)(evidence:|verified|verification:|did not run|could not run|not run|[0-9]+ (tests? )?(passed|passing|failed|failing)|exit (code |status )?[0-9]|```|[0-9]+/[0-9]+ (passed|tests|checks)|(^|[^a-z])ran([^a-z]|$))'

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

if ($payload.stop_hook_active -eq $true) { exit 0 }
$msg = [string]$payload.last_assistant_message
if (-not $msg) { exit 0 }
$msg = $msg -replace "`r", ''

if ($msg -notmatch $Claim) { exit 0 }
if ($msg -match $Evidence) { exit 0 }

# Did this session change anything? A subagent's own transcript first, then the session's.
$editCall = '"name"\s*:\s*"(Edit|Write|MultiEdit|NotebookEdit)"'
$transcript = [string]$payload.agent_transcript_path
if (-not $transcript) { $transcript = [string]$payload.transcript_path }
if ($transcript -and (Test-Path -LiteralPath $transcript -PathType Leaf)) {
    $hit = Select-String -LiteralPath $transcript -Pattern $editCall -Quiet -ErrorAction SilentlyContinue
    if (-not $hit) { exit 0 }
} else {
    $dir = [string]$payload.cwd
    if (-not $dir) { $dir = (Get-Location).Path }
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) { exit 0 }
    $status = & $git.Source -C $dir status --porcelain 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $status) { exit 0 }
}

$who = 'your'
if ([string]$payload.hook_event_name -ceq 'SubagentStop') { $who = "this subagent's" }
[Console]::Error.WriteLine("stop-evidence: $who final message claims the work is done but shows no evidence. Before stopping, add one line that starts with 'Evidence:' naming what you ran and what it returned (for example: Evidence: npm test - 42 passed, exit 0), or say plainly 'Not verified:' and why. Do not re-run anything you already ran; quote it.")
exit 2

# check-commit-msg.ps1
# Event: PreToolUse   Matcher: Bash
# Validates the subject line of `git commit -m "..."` against .claude/rules/conventional-commits.md.
# Skips editor-flow commits (no -m), `--amend --no-edit`, and Merge/Revert subjects.
#
# CASE-SENSITIVITY TRAP: PowerShell -match / -notmatch are case-INSENSITIVE by default, which
# silently defeats every lowercase check below ("Feat: X" would pass). Use -cmatch / -cnotmatch
# for the subject checks. Do NOT "simplify" them back to -match.
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

$cmd = $payload.tool_input.command
if (-not $cmd) { exit 0 }
if ($cmd -notmatch '(^|[;&|]\s*)git\s+commit\b') { exit 0 }
if ($cmd -match '--amend' -and $cmd -match '--no-edit') { exit 0 }

# AI-attribution trailers, checked FIRST and against the RAW command.
# It must precede the -m extraction below, for parity with the bash twin: a non-greedy `(.*?)`
# against a multi-line message can capture only up to the first quote it finds, and any capture
# failure trips the `exit 0` editor-flow guard - so a check placed after it may never run at all.
# Matching $cmd sidesteps both. Case-INsensitive (-match, not -cmatch) on purpose: the trailer is
# machine-generated and its casing varies.
# The rule file forbids these trailers, but a rule is advisory; this is the layer that enforces.
if ($cmd -match '(?i)co-authored-by:[^"]*(claude|anthropic|copilot|cursor)|generated with[^"]*(claude|anthropic)') {
    [Console]::Error.WriteLine("BLOCKED: remove the AI-attribution trailer (Co-Authored-By / 'Generated with').")
    [Console]::Error.WriteLine("See .claude/rules/conventional-commits.md - this repository does not attribute commits to tools.")
    exit 2
}

$msg = $null
if ($cmd -match '(?s)-m\s+"(.*?)"') { $msg = $Matches[1] }
elseif ($cmd -match "(?s)-m\s+'(.*?)'") { $msg = $Matches[1] }
if (-not $msg) { exit 0 }   # editor flow / -F file: git's own hooks own that path

$subject = ($msg -split "(`r)?`n")[0].Trim()
if ($subject -match '^(Merge|Revert)\b') { exit 0 }

$types = '{{COMMIT_TYPES}}'
$pattern = "^($types)(\([a-z0-9-]+\))?(!)?: \S.*$"
$problems = @()

if ($subject -cnotmatch $pattern) { $problems += "subject must match '<type>(<scope>)?: <description>' with lowercase type in [$types]" }
if ($subject.Length -gt 72) { $problems += "subject is $($subject.Length) chars (max 72)" }
if ($subject -cmatch '\.\s*$') { $problems += "subject must not end with a period" }
if ($subject -cmatch '^[a-z]+(\([a-z0-9-]+\))?(!)?: [A-Z]') { $problems += "description starts uppercase - use lowercase" }


if ($problems.Count -gt 0) {
    [Console]::Error.WriteLine("BLOCKED: commit message violates .claude/rules/conventional-commits.md:")
    foreach ($p in $problems) { [Console]::Error.WriteLine(" - $p") }
    [Console]::Error.WriteLine("Subject was: '$subject'. Example: feat(core): add health endpoint")
    exit 2
}
exit 0

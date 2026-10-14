# secret-guard.ps1
# Events: UserPromptSubmit (no matcher) and PostToolUse (Matcher: Bash|PowerShell|Read|Grep)
# Flag: hooks_strict
# Enforces: .claude/rules/security-privacy.md (a secret value never enters the transcript)
#   UserPromptSubmit: BLOCKS (exit 2) a prompt carrying a credential-shaped string - it is never
#     sent; stderr goes to the user.
#   PostToolUse: WARNS (additionalContext) when tool output contained one - it cannot be pulled
#     back, so the warning stops it spreading and asks for rotation.
#
# PARITY CONTRACT: secret-guard.sh and secret-guard.ps1 must stay behaviorally EQUIVALENT - same
# pattern list, same order, same labels. Patterns are case-SENSITIVE (-cmatch), like grep -E.
#
# Contract: reads the hook JSON payload on stdin. exit 2 = block the prompt (reason on stderr, to
# the user); exit 0 otherwise, optionally with hookSpecificOutput JSON on stdout. Fails OPEN.

$Patterns = @(
    @('Anthropic API key', 'sk-ant-[A-Za-z0-9_-]{20,}'),
    @('OpenAI API key', 'sk-(proj-)?[A-Za-z0-9_-]{32,}'),
    @('AWS access key id', '(AKIA|ASIA)[0-9A-Z]{16}'),
    @('GitHub token', '(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})'),
    @('Slack token', 'xox[abprs]-[A-Za-z0-9-]{10,}'),
    @('Stripe live key', '(sk|rk)_live_[A-Za-z0-9]{20,}'),
    @('Google API key', 'AIza[0-9A-Za-z_-]{35}'),
    @('Google OAuth client secret', 'GOCSPX-[A-Za-z0-9_-]{28}'),
    @('ElevenLabs API key', 'sk_[0-9a-f]{48}'),
    @('GitLab token', 'glpat-[A-Za-z0-9_-]{20,}'),
    @('Hugging Face token', 'hf_[A-Za-z]{34}'),
    @('npm token', 'npm_[A-Za-z0-9]{36}'),
    @('PyPI token', 'pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}'),
    @('SendGrid API key', 'SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}'),
    @('Groq API key', 'gsk_[A-Za-z0-9]{52}'),
    @('xAI API key', 'xai-[A-Za-z0-9]{80}'),
    @('DigitalOcean token', 'do[por]_v1_[a-f0-9]{64}'),
    @('Shopify token', 'shp(at|ca|pa|ss)_[a-fA-F0-9]{32}'),
    @('private key', '-----BEGIN ([A-Z]+ )?PRIVATE KEY-----')
)

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

# Keys published in vendor documentation as placeholders: they match by design and grant nothing.
# Removed before the scan, so a real key next to one is still caught. Same list as secret-guard.sh.
$Examples = @(('AKIA' + 'IOSFODNN7EXAMPLE'), ('AKIA' + 'I44QH8DHBEXAMPLE'))  # split: no literal for a scanner

function Get-FirstHit([string]$text) {
    foreach ($e in $Examples) { $text = $text.Replace($e, '') }
    foreach ($p in $Patterns) {
        if ($text -cmatch $p[1]) { return $p[0] }
    }
    return $null
}

$hookEvent = [string]$payload.hook_event_name
if ($hookEvent -ceq 'UserPromptSubmit') {
    $prompt = [string]$payload.prompt
    if (-not $prompt) { exit 0 }
    $kind = Get-FirstHit $prompt
    if (-not $kind) { exit 0 }
    [Console]::Error.WriteLine("secret-guard: this prompt was NOT sent - it contains what looks like a $kind. Once a key is in the conversation it stays in the transcript and the provider's logs. Put it in a local env file or a secret store and refer to it by name (for example: the key in STRIPE_KEY). If you pasted it anywhere else, rotate it.")
    exit 2
}
if ($hookEvent -ceq 'PostToolUse') {
    $resp = $payload.tool_response
    if ($null -eq $resp) { exit 0 }
    $text = if ($resp -is [string]) { $resp } else { try { $resp | ConvertTo-Json -Depth 20 -Compress } catch { '' } }
    if (-not $text) { exit 0 }
    $kind = Get-FirstHit $text
    if (-not $kind) { exit 0 }
    $tool = ([string]$payload.tool_name) -replace '[^A-Za-z0-9_-]', ''
    $out = @{
        hookSpecificOutput = @{
            hookEventName     = 'PostToolUse'
            additionalContext = "secret-guard: the output of that $tool call contains what looks like a $kind. It is now in the transcript. Do not repeat, quote, summarize or write it anywhere, and do not run anything that would print it again. Tell the user which secret was exposed and where it came from, so they can rotate it."
        }
    } | ConvertTo-Json -Compress -Depth 5
    [Console]::Out.WriteLine($out)
}
exit 0

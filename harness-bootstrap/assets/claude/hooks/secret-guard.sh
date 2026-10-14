#!/usr/bin/env bash
# secret-guard.sh
# Events: UserPromptSubmit (no matcher) and PostToolUse (Matcher: Bash|PowerShell|Read|Grep)
# Flag: hooks_strict
# Enforces: .claude/rules/security-privacy.md (a secret value never enters the transcript)
# Looks for credential-shaped strings - the vendor formats in PATTERNS below (cloud, code-host,
# package-registry, AI-provider and payment keys) and PEM private-key headers - in two places:
#   UserPromptSubmit: BLOCKS (exit 2). The prompt is not sent, so the key never reaches the model,
#     the transcript or the provider's logs. stderr goes to the USER (Claude never sees it): it
#     names the kind of key and asks them to send it by reference instead, and to rotate it if it
#     was pasted anywhere else.
#   PostToolUse: WARNS (additionalContext, exit 0) when a tool's output contained one - `cat` of a
#     config file, `printenv`, a log. The value is already in the transcript and cannot be pulled
#     back, so blocking is impossible; what is still possible is not spreading it further and
#     telling the user which secret to rotate.
#
# The patterns are vendor formats with fixed prefixes and lengths, chosen so ordinary text, hashes
# and UUIDs do not match. No generic "password=" rule: it fires on every config example and a
# guard that cries wolf gets switched off. protect-secrets stops the obvious reads; this catches
# what got past it.
#
# PARITY CONTRACT: secret-guard.sh and secret-guard.ps1 must stay behaviorally EQUIVALENT - same
# pattern list, same order, same labels, same documented-example allow-list.
#
# Contract: reads the hook JSON payload on stdin. exit 2 = block the prompt (reason on stderr, to
# the user); exit 0 otherwise, optionally with hookSpecificOutput JSON on stdout. Fails OPEN.

PATTERNS=(
  'Anthropic API key|sk-ant-[A-Za-z0-9_-]{20,}'
  'OpenAI API key|sk-(proj-)?[A-Za-z0-9_-]{32,}'
  'AWS access key id|(AKIA|ASIA)[0-9A-Z]{16}'
  'GitHub token|(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})'
  'Slack token|xox[abprs]-[A-Za-z0-9-]{10,}'
  'Stripe live key|(sk|rk)_live_[A-Za-z0-9]{20,}'
  'Google API key|AIza[0-9A-Za-z_-]{35}'
  'Google OAuth client secret|GOCSPX-[A-Za-z0-9_-]{28}'
  'ElevenLabs API key|sk_[0-9a-f]{48}'
  'GitLab token|glpat-[A-Za-z0-9_-]{20,}'
  'Hugging Face token|hf_[A-Za-z]{34}'
  'npm token|npm_[A-Za-z0-9]{36}'
  'PyPI token|pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}'
  'SendGrid API key|SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}'
  'Groq API key|gsk_[A-Za-z0-9]{52}'
  'xAI API key|xai-[A-Za-z0-9]{80}'
  'DigitalOcean token|do[por]_v1_[a-f0-9]{64}'
  'Shopify token|shp(at|ca|pa|ss)_[a-fA-F0-9]{32}'
  'private key|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----'
)

# json_fields KEY... -> JF array; the pseudo-key @response yields tool_response serialized as
# JSON text (whatever its shape), so the scan sees every string in it.
json_fields() {
  local keys=("$@")
  JF=()
  if command -v jq >/dev/null 2>&1; then
    local k
    for k in "${keys[@]}"; do
      if [ "$k" = "@response" ]; then
        JF+=("$(printf '%s' "$payload" | jq -c '.tool_response // empty' 2>/dev/null)")
      else
        JF+=("$(printf '%s' "$payload" | jq -r --arg k "$k" 'getpath($k | split(".")) | if type == "string" or type == "boolean" or type == "number" then tostring else empty end' 2>/dev/null)")
      fi
    done
  elif command -v perl >/dev/null 2>&1; then
    while IFS= read -r -d '' v; do JF+=("$v"); done < <(
      printf '%s' "$payload" | perl -0777 -MJSON::PP -e '
        local $/; my $d = eval { decode_json(<STDIN>) };
        for my $k (@ARGV) {
          if ($k eq q{@response}) {
            my $r = (ref($d) eq "HASH") ? $d->{tool_response} : undef;
            my $o = !defined $r ? "" : ref $r ? JSON::PP->new->canonical->encode($r) : $r;
            $o =~ s/\0//g;
            print($o . "\0");
            next;
          }
          my $v = $d;
          if ($d) {
            for my $p (split /\./, $k) {
              $v = (ref($v) eq "HASH") ? $v->{$p} : undef;
              last unless defined $v;
            }
          } else { $v = undef; }
          my $o = "";
          if (defined $v) {
            if (ref($v) eq "JSON::PP::Boolean") { $o = $v ? "true" : "false"; }
            elsif (!ref $v) { $o = $v; }
          }
          $o =~ s/\0//g;
          print($o . "\0");
        }
      ' "${keys[@]}" 2>/dev/null
    )
  elif command -v python3 >/dev/null 2>&1; then
    while IFS= read -r -d '' v; do JF+=("$v"); done < <(
      printf '%s' "$payload" | python3 -c '
import json, sys
try: root = json.load(sys.stdin)
except Exception: root = None
out = []
for k in sys.argv[1:]:
    if k == "@response":
        r = root.get("tool_response") if isinstance(root, dict) else None
        out.append("" if r is None else r if isinstance(r, str) else json.dumps(r, sort_keys=True))
        continue
    v = root
    for p in k.split("."):
        v = v.get(p) if isinstance(v, dict) else None
        if v is None: break
    if isinstance(v, bool): out.append("true" if v else "false")
    elif isinstance(v, (str, int, float)): out.append(str(v))
    else: out.append("")
sys.stdout.write("\0".join(o.replace("\0", "") for o in out) + "\0")
' "${keys[@]}" 2>/dev/null
    )
  else
    echo "secret-guard: no jq/perl/python3 available to parse the hook payload; allowing. Deliberate: a missing tool degrades this guard to a warning, never to blocking every call." >&2
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
}

# Keys published in vendor documentation as placeholders. They match the patterns by design and
# grant nothing, and blocking them blocks every question about the docs that contain them. They are
# removed before the scan, so a real key next to one is still caught.
# Split so this file never holds a literal a repository secret scanner would flag.
EXAMPLES=(
  'AKIA''IOSFODNN7EXAMPLE'
  'AKIA''I44QH8DHBEXAMPLE'
)

# first_hit TEXT -> label of the first pattern that matches, or nothing
first_hit() {
  local entry text="$1" ex
  for ex in "${EXAMPLES[@]}"; do text=${text//"$ex"/}; done
  for entry in "${PATTERNS[@]}"; do
    if printf '%s' "$text" | grep -Eq -e "${entry#*|}"; then
      printf '%s' "${entry%%|*}"
      return 0
    fi
  done
  return 1
}

payload=$(cat)
json_fields hook_event_name prompt tool_name @response
event="${JF[0]}"

case "$event" in
  UserPromptSubmit)
    [ -z "${JF[1]}" ] && exit 0
    kind=$(first_hit "${JF[1]}") || exit 0
    echo "secret-guard: this prompt was NOT sent - it contains what looks like a $kind. Once a key is in the conversation it stays in the transcript and the provider's logs. Put it in a local env file or a secret store and refer to it by name (for example: the key in STRIPE_KEY). If you pasted it anywhere else, rotate it." >&2
    exit 2
    ;;
  PostToolUse)
    [ -z "${JF[3]}" ] && exit 0
    kind=$(first_hit "${JF[3]}") || exit 0
    tool=$(printf '%s' "${JF[2]}" | tr -cd 'A-Za-z0-9_-')
    printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"secret-guard: the output of that $tool call contains what looks like a $kind. It is now in the transcript. Do not repeat, quote, summarize or write it anywhere, and do not run anything that would print it again. Tell the user which secret was exposed and where it came from, so they can rotate it.\"}}"
    exit 0
    ;;
esac
exit 0

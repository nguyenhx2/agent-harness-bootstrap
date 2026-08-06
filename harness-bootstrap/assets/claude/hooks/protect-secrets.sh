#!/usr/bin/env bash
# protect-secrets.sh
# Event: PreToolUse   Matcher: Read|Edit|Write|Bash
# Blocks three things:
#   1. file access (Read/Edit/Write) to secret-bearing paths: .env* (except .env.example), key
#      material (*.pem/*.key/*.pfx/*.p12), secrets?/ + credentials? dirs, service-account JSON, .npmrc/.pypirc/.netrc
#   2. shell commands that read/copy a .env file
#   3. destructive DB commands ({{DB_RESET_PATTERN}})
#
# PARITY CONTRACT: protect-secrets.sh and protect-secrets.ps1 must stay behaviorally EQUIVALENT -
# same secret-file globs, same command patterns, same block conditions. If you change one, change
# the other. The command alternation below carries the PowerShell spellings (Get-Content, gc,
# type, copy) as well as the POSIX ones (cat, more, less, head, tail, cp, echo). The cmdlet names
# cannot occur in a POSIX shell, but keeping the regex identical to the .ps1 twin is worth more
# than pruning dead alternatives - and `type` IS a real POSIX shell builtin, so it stays.
#
# CASE-SENSITIVITY: matching here is intentionally case-INSENSITIVE (`grep -Ei`) to match
# PowerShell -match's default, so `.ENV` and `CAT` cannot slip through. This is the opposite of
# check-commit-msg.sh, whose lowercase checks must stay case-sensitive.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow.

# JSON extraction: jq is preferred but is NOT installed by default on macOS, and a missing jq
# would make this hook silently fail OPEN - a security hook that allows everything. Fall back to
# perl (core JSON::PP - ships with macOS and every Linux), then python3. With no extractor at all
# we warn loudly and allow; the settings.json deny rules remain the backstop.
#
# json_fields fetches every field this hook needs in ONE parser invocation instead of one per
# field: jq's startup is a few ms, cheap enough that its branch below still does one call per
# field, but perl/python3 process startup is the dominant cost of the whole hook (tens to
# hundreds of ms - see hooks/README.md), and that cost was being paid twice per invocation here.
# Sets the array JF, one slot per requested key, always the same length as the argument list.
json_fields() {
  local keys=("$@")
  JF=()
  if command -v jq >/dev/null 2>&1; then
    local k
    for k in "${keys[@]}"; do
      JF+=("$(printf '%s' "$payload" | jq -r --arg k "$k" 'getpath($k | split(".")) // empty' 2>/dev/null)")
    done
  elif command -v perl >/dev/null 2>&1; then
    while IFS= read -r -d '' v; do JF+=("$v"); done < <(
      printf '%s' "$payload" | perl -0777 -MJSON::PP -e '
        local $/; my $d = eval { decode_json(<STDIN>) };
        for my $k (@ARGV) {
          my $v = $d;
          if ($d) {
            for my $p (split /\./, $k) {
              $v = (ref($v) eq "HASH") ? $v->{$p} : undef;
              last unless defined $v;
            }
          } else { $v = undef; }
          print(((defined $v && !ref $v) ? $v : "") . "\0");
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
    v = root
    for p in k.split("."):
        v = v.get(p) if isinstance(v, dict) else None
        if v is None: break
    out.append(v if isinstance(v, str) else "")
sys.stdout.write("\0".join(out) + "\0")
' "${keys[@]}" 2>/dev/null
    )
  else
    echo "protect-secrets: no jq/perl/python3 available to parse the hook payload; allowing. Install jq - the settings.json deny rules are your only remaining secret guard." >&2
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
}

secret_pattern='(^|/)\.env(\.[^/]+)?$|(^|/)(secrets?|credentials?)/|\.(pem|key|pfx|p12|ppk|asc|gpg)$|service[-_]?account.*\.json$|(^|/)id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$|(^|/)\.(npmrc|pypirc|netrc)$|(^|/)\.aws/credentials$|(^|/)\.ssh/'
allow_pattern='\.env\.example$'
cmd_pattern='(^|[^a-zA-Z0-9_.-])(cat|type|more|less|head|tail|Get-Content|gc|copy|cp|echo)[[:space:]]+[^[:space:]]*\.env(\.[a-zA-Z0-9_-]+)?([[:space:]]|$|"|'"'"')'
cmd_allow='\.env\.example'
db_reset_pattern='{{DB_RESET_PATTERN}}'

payload=$(cat)
json_fields tool_input.file_path tool_input.command
path="${JF[0]}"
cmd="${JF[1]}"

# --- 1. file access ---------------------------------------------------------------------------
if [ -n "$path" ]; then
  norm=${path//\\//}
  if printf '%s' "$norm" | grep -Eqi "$secret_pattern" \
     && ! printf '%s' "$norm" | grep -Eqi "$allow_pattern"; then
    echo "BLOCKED: this file may contain secrets ($norm). Per .claude/rules/agent-guardrails.md, agents do not read/edit secrets. Use .env.example for placeholders." >&2
    exit 2
  fi
fi

# --- 2 + 3. shell commands --------------------------------------------------------------------
if [ -n "$cmd" ]; then
  if printf '%s' "$cmd" | grep -Eqi "$cmd_pattern" \
     && ! printf '%s' "$cmd" | grep -Eqi "$cmd_allow"; then
    echo "BLOCKED: this command reads/copies a .env file. If you need the variable list, read .env.example." >&2
    exit 2
  fi
  if printf '%s' "$cmd" | grep -Eqi "$db_reset_pattern"; then
    echo "BLOCKED: destructive DB command. Migrations only via the controlled /db-migration flow; DB resets must be run by the user themselves." >&2
    exit 2
  fi
fi
exit 0

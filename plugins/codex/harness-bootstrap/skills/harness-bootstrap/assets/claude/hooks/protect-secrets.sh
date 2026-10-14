#!/usr/bin/env bash
# protect-secrets.sh
# Event: PreToolUse   Matcher: Read|Edit|Write|Bash
# Enforces: .claude/rules/security-privacy.md
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
# A closed list of reader verbs was the wrong shape: anything off the list read secrets
# freely (`strings .env`, `rtk read .env`, any wrapper installed tomorrow). Match the FILE
# instead, then subtract the forms that may legitimately name it. Best-effort by nature - a
# command can obfuscate the path - which is why settings.json deny rules sit behind this.
cmd_pattern='(^|[^a-zA-Z0-9_./-])[^[:space:]]*\.env(\.[a-zA-Z0-9_-]+)?([[:space:]]|$|"|'"'"'|;|&)'
# Scrubbed off BEFORE the test, so a command whose only secret mentions are these is allowed:
#   > .env.local                  writing a local env file is setup, not disclosure
#   .env.example                  the tracked placeholder
#   env-read.py                   the sanctioned value-free path
#   cp .env.example .env.local    seeding a local file from the example
# Scrubbing rather than a second allow-regex matters: `cat .env > .env.bak` must still block,
# and it does, because only the redirect target is removed and `cat .env` survives the scrub.
cmd_scrub='s/(cp|copy|mv|Copy-Item)[[:space:]]+[^[:space:]]*\.env\.example[[:space:]]+[^[:space:]]*\.env(\.[a-zA-Z0-9_-]+)?//g; s/>>?[[:space:]]*[^[:space:]]*\.env(\.[a-zA-Z0-9_-]+)?//g; s/[^[:space:]]*\.env\.example//g; s/[^[:space:]]*env-read\.py[^;&|]*//g'
db_reset_pattern='{{DB_RESET_PATTERN}}'

# --- fast path: decide the common case with bash builtins only ---------------------------------
# This hook starts on every shell call, and on Windows each subshell or external process costs
# 50-250 ms: the JSON parser, every `printf | grep`, every `$(...)`. Most commands can never be
# blocked here, so that case is decided before any of them run. read_payload takes stdin without
# a fork; fast_str decodes one string field EXACTLY or gives up. A hook may only exit 0 on what
# these return, and only on a test that is a necessary condition of every block it raises; any
# doubt falls through to the full parse, which is unchanged. Copied verbatim into every hook that
# has a fast path - see "Latency" in hooks/README.md.
read_payload() {
  payload=
  # bash reads a pipe one byte per syscall: fine for a shell call's few hundred bytes, slower than
  # one `cat` past a few KB (an Edit or Write payload), so the rest of a long one goes to cat.
  if IFS= read -r -d '' -n 4096 payload; then
    payload+=$(cat)
  fi
}
# fast_str KEY -> FAST_STR. Fails unless the payload holds "KEY": exactly once, with a string value
# that is printable ASCII and uses no JSON escape but \" \\ \n \r \t - everything JSON.stringify
# writes for such text, so the decode is exact. Runs in the C locale: in a multibyte locale a lead
# byte could swallow the backslash of an escaped quote and end the value early.
fast_str() {
  local key=$1 s rest re re2 bs='\' q='"' had=${LC_ALL+x} old=${LC_ALL-} rc=1
  LC_ALL=C
  re="\"$key\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\""
  re2="\"$key\"[[:space:]]*:"
  if [[ $payload =~ $re ]]; then
    s=${BASH_REMATCH[1]}
    rest=${payload#*"$q$key$q"}
    rc=0
    [[ $rest =~ $re2 ]] && rc=1
    case $s in *[!\ -~]*) rc=1 ;; esac
    s=${s//"$bs$bs"/$'\001'}
    case $s in *"$bs"[!nrt\"]*|*"$bs") rc=1 ;; esac
    s=${s//"$bs$q"/"$q"}
    s=${s//"${bs}n"/$'\n'}
    s=${s//"${bs}r"/$'\r'}
    s=${s//"${bs}t"/$'\t'}
    FAST_STR=${s//$'\001'/"$bs"}
  fi
  if [ "$had" = x ]; then LC_ALL=$old; else unset LC_ALL; fi
  return $rc
}
# fast_unmatched ERE: true only when ERE was compiled and did not match FAST_STR (exit status 1).
# A regex the engine rejects (status 2) must never read as "no match".
fast_unmatched() {
  local had=${LC_ALL+x} old=${LC_ALL-} rc
  LC_ALL=C
  [[ $FAST_STR =~ $1 ]]
  rc=$?
  if [ "$had" = x ]; then LC_ALL=$old; else unset LC_ALL; fi
  [ "$rc" -eq 1 ]
}

read_payload
# A shell call can only be blocked here for naming a .env file or for matching the DB-reset
# pattern. The pattern is user-supplied, so it is tried here only when this bash can match
# case-insensitively (nocasematch on =~ is proven on the spot) and the pattern is plain ASCII with
# no anchor or backslash - grep reads ^ $ per line and knows GNU escapes that bash's regex may not.
# Anything else takes the full path. A file_path always does.
fast_db_unmatched() {
  local rc=0 had=${LC_ALL+x} old=${LC_ALL-}
  LC_ALL=C
  case $db_reset_pattern in *[!\ -~]*|*'^'*|*'$'*|*'\'*) rc=1 ;; esac
  if [ "$had" = x ]; then LC_ALL=$old; else unset LC_ALL; fi
  [ "$rc" -eq 0 ] || return 1
  rc=1
  shopt -s nocasematch
  if [[ AbC =~ ^aBc$ ]]; then fast_unmatched "$db_reset_pattern" && rc=0; fi
  shopt -u nocasematch
  return $rc
}
case $payload in
  *'"file_path"'*) ;;
  *) fast_str command && fast_unmatched '\.[Ee][Nn][Vv]' && fast_db_unmatched && exit 0 ;;
esac
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
  cmd_scrubbed=$(printf '%s' "$cmd" | sed -E "$cmd_scrub")
  if printf '%s' "$cmd_scrubbed" | grep -Eqi "$cmd_pattern"; then
    echo "BLOCKED: this command names a .env file. Values never enter the transcript. Read .env.example for the variable list, or use .claude/scripts/env-read.py (list/check/diff, or run to execute with the values loaded but never printed)." >&2
    exit 2
  fi
  if printf '%s' "$cmd" | grep -Eqi "$db_reset_pattern"; then
    echo "BLOCKED: destructive DB command. Schema changes go through the controlled migration flow; DB resets must be run by the user themselves." >&2
    exit 2
  fi
fi
exit 0

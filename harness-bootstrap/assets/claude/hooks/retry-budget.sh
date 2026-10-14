#!/usr/bin/env bash
# retry-budget.sh
# Events: PostToolUseFailure and PreToolUse (Matcher: Bash|PowerShell|Edit|MultiEdit|Write|WebFetch)
# Registered only on the tools whose failures loop - a shell command, an edit whose old_string
# never matches, a fetch that keeps failing. On `*` it started a process for every tool call.
# Flag: long
# Enforces: .claude/rules/agent-guardrails.md (no silent retry loops)
# A runaway guard keyed on FAILURE, not on repetition:
#   PostToolUseFailure: records the failed call's signature (tool name + input, minus the free-text
#     `description`) in .claude/state/retry-budget. The second identical consecutive failure WARNS
#     (additionalContext, exit 0).
#   PreToolUse: BLOCKS (exit 2) a call identical to one that has already failed 3 times in a row.
#     Any different call in between resets the count - an Edit that fixes the cause, then the same
#     test command again, is a fresh attempt.
# Interrupted calls (is_interrupt: true) are never counted.
#
# WHY COUNT FAILURES, NOT REPEATS: polling - `gh pr checks`, a status command, a background
# task's output - repeats the identical call legitimately and succeeds each time. A guard on
# repetition would block that. Repeating a call that FAILED, unchanged, is the loop worth
# stopping: the third identical failure has already shown the fourth will fail too, and every
# attempt costs a turn. The block message points at the task's own retry counter (task.py attempt).
#
# PARITY CONTRACT: retry-budget.sh and retry-budget.ps1 must stay behaviorally EQUIVALENT - same
# thresholds, same reset rule, same signature fields. (The signature HASH differs between flavors;
# a machine only ever runs one flavor, so the state file never mixes them.)
#
# Contract: reads the hook JSON payload on stdin. exit 2 = BLOCK (PreToolUse only, reason on
# stderr); exit 0 otherwise, optionally with hookSpecificOutput JSON on stdout. Fails OPEN.

LIMIT=3
WARN_AT=2

# json_fields KEY... -> JF array; the pseudo-key @sig yields the canonical JSON of tool_input
# with `description` removed (the call signature).
json_fields() {
  local keys=("$@")
  JF=()
  if command -v jq >/dev/null 2>&1; then
    local k
    for k in "${keys[@]}"; do
      if [ "$k" = "@sig" ]; then
        JF+=("$(printf '%s' "$payload" | jq -cS '(.tool_input // {}) | if type == "object" then del(.description) else . end' 2>/dev/null)")
      else
        JF+=("$(printf '%s' "$payload" | jq -r --arg k "$k" 'getpath($k | split(".")) | if type == "string" or type == "boolean" or type == "number" then tostring else empty end' 2>/dev/null)")
      fi
    done
  elif command -v perl >/dev/null 2>&1; then
    while IFS= read -r -d '' v; do JF+=("$v"); done < <(
      printf '%s' "$payload" | perl -0777 -MJSON::PP -e '
        local $/; my $d = eval { decode_json(<STDIN>) };
        for my $k (@ARGV) {
          if ($k eq q{@sig}) {
            my $ti = (ref($d) eq "HASH" && ref($d->{tool_input}) eq "HASH") ? { %{$d->{tool_input}} } : {};
            delete $ti->{description};
            print(JSON::PP->new->canonical->encode($ti) . "\0");
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
    if k == "@sig":
        ti = root.get("tool_input") if isinstance(root, dict) else None
        ti = dict(ti) if isinstance(ti, dict) else {}
        ti.pop("description", None)
        out.append(json.dumps(ti, sort_keys=True, separators=(",", ":")))
        continue
    v = root
    for p in k.split("."):
        v = v.get(p) if isinstance(v, dict) else None
        if v is None: break
    if isinstance(v, bool): out.append("true" if v else "false")
    elif isinstance(v, (str, int, float)): out.append(str(v))
    else: out.append("")
sys.stdout.write("\0".join(out) + "\0")
' "${keys[@]}" 2>/dev/null
    )
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
}

# Copied verbatim from guard-agent-spawn.sh.
norm_path() {
  local p d rest
  p=$(printf '%s' "$1" | tr '\\' '/')
  case "$p" in
    [A-Za-z]:/*) ;;
    *) printf '%s' "$p"; return ;;
  esac
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -u "$p" 2>/dev/null && return
  fi
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -u "$p" 2>/dev/null && return
  fi
  d=$(printf '%s' "${p%%:*}" | tr 'A-Z' 'a-z')
  rest=${p#*:}
  if [ -d "/mnt/$d" ]; then printf '/mnt/%s%s' "$d" "$rest"
  elif [ -d "/$d" ]; then printf '/%s%s' "$d" "$rest"
  else printf '%s' "$p"
  fi
}

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
# A PreToolUse call is only ever blocked when the state file exists, and it rarely does: one
# different call deletes it. So answer "no state file" without the parser. The cwd decides where
# the file is; a drive path (C:/x) is tried as given and under /mnt/c and /c, since telling which
# one norm_path would pick costs a fork. Exit early only when one of those holds .claude/ and none
# holds the state file; any doubt takes the full path.
retry_fast_clear() {
  local c d rest t seen=0 lc=abcdefghijklmnopqrstuvwxyz uc=ABCDEFGHIJKLMNOPQRSTUVWXYZ
  local cands=()
  fast_str hook_event_name && [ "$FAST_STR" = PreToolUse ] || return 1
  fast_str cwd || return 1
  c=${FAST_STR//\\//}
  [ -n "$c" ] || return 1
  case $c in
    [A-Za-z]:/*)
      d=${c%%:*}; rest=${c#*:}
      case $d in [A-Z]) t=${uc%%"$d"*}; d=${lc:${#t}:1} ;; esac
      cands=("$c" "/mnt/$d$rest" "/$d$rest") ;;
    *) cands=("$c"); seen=1 ;;
  esac
  for t in "${cands[@]}"; do
    [ -e "$t/.claude/state/retry-budget" ] && return 1
    [ -d "$t/.claude" ] && seen=1
  done
  [ "$seen" -eq 1 ]
}
retry_fast_clear && exit 0
json_fields hook_event_name tool_name session_id is_interrupt cwd @sig
event="${JF[0]}"
tool="${JF[1]}"
session="${JF[2]:--}"
interrupt="${JF[3]}"
base_cwd=$(norm_path "${JF[4]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)
[ -z "$tool" ] && exit 0
[ -d "$base_cwd/.claude" ] || exit 0
state="$base_cwd/.claude/state/retry-budget"
sig=$(printf '%s\n%s' "$tool" "${JF[5]}" | cksum | tr -d ' \t')

s_session=""; s_sig=""; s_count=0
if [ -f "$state" ]; then
  IFS=$'\037' read -r s_session s_sig s_count < "$state"
  s_count=${s_count%$'\r'}  # a state file written on Windows may end in CRLF
  case "$s_count" in ''|*[!0-9]*) s_count=0 ;; esac
fi

case "$event" in
  PostToolUseFailure)
    [ "$interrupt" = "true" ] && exit 0
    if [ "$s_session" = "$session" ] && [ "$s_sig" = "$sig" ]; then
      count=$((s_count + 1))
    else
      count=1
    fi
    mkdir -p "${state%/*}" 2>/dev/null
    printf '%s\037%s\037%s\n' "$session" "$sig" "$count" > "$state" 2>/dev/null
    if [ "$count" -eq "$WARN_AT" ]; then
      printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUseFailure\",\"additionalContext\":\"retry-budget: this exact $tool call has now failed $count times in a row. Do not retry it unchanged - read the error and change the input or the approach. After $LIMIT identical failures the next identical attempt is blocked.\"}}"
    fi
    exit 0
    ;;
  PreToolUse)
    [ -f "$state" ] || exit 0
    if [ "$s_session" = "$session" ] && [ "$s_sig" = "$sig" ]; then
      if [ "$s_count" -ge "$LIMIT" ]; then
        echo "BLOCKED by retry-budget: this exact $tool call has failed $s_count times in a row with the same input; a further identical attempt will fail the same way. Change the input or the approach (any different call resets this count), or stop and report the blocker - for a dispatched task, record it with: python .claude/scripts/task.py attempt <TASK-NNN> --reason <infra|scope|env> --note \"...\"." >&2
        exit 2
      fi
    else
      rm -f "$state" 2>/dev/null
    fi
    exit 0
    ;;
esac
exit 0

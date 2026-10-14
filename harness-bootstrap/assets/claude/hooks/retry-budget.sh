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

payload=$(cat)
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

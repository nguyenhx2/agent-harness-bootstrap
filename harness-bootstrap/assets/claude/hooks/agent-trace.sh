#!/usr/bin/env bash
# agent-trace.sh
# Events: SubagentStart (Matcher: *), InstructionsLoaded (no matcher), PermissionDenied (Matcher: *)
# Flag: long
# Enforces: .claude/rules/agent-guardrails.md (what ran is observable, not inferred)
# NEVER BLOCKS, PRINTS NOTHING. Appends one tab-separated line per event to
# .claude/state/trace.log:
#   SubagentStart       when a subagent started, its type and id. agent-history archives the
#                       run when it STOPS; the start line is what shows which seats ran at the
#                       same time and how long each took.
#   InstructionsLoaded  which rule or memory file actually entered context, and why
#                       (session_start, path_glob_match, nested_traversal, include, compact).
#                       This is the only direct evidence that a path-scoped rule fired - or that
#                       one meant to stay out of the default session did not.
#   PermissionDenied    what auto mode's classifier refused, with its reason. Fires only in auto
#                       mode; a PreToolUse hook's own block is not reported here.
# The log keeps its newest 1500 lines once it passes 2000. .claude/state/ is never committed,
# so these lines carry a timestamp.
#
# WHY A LOG AND NOT CONTEXT: none of these needs Claude to act. Injecting them would spend tokens
# on every rule load; a file a person (or /harness-tune) can read costs nothing in the session.
#
# PARITY CONTRACT: agent-trace.sh and agent-trace.ps1 must write the same fields in the same order.
#
# Contract: reads the hook JSON payload on stdin. Always exit 0, nothing on stdout.

json_fields() {
  local keys=("$@")
  JF=()
  if command -v jq >/dev/null 2>&1; then
    local k
    for k in "${keys[@]}"; do
      JF+=("$(printf '%s' "$payload" | jq -r --arg k "$k" 'getpath($k | split(".")) | if type == "string" or type == "boolean" or type == "number" then tostring else empty end' 2>/dev/null)")
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

# one-line field: no tabs or newlines, at most 160 characters
field() { printf '%s' "$1" | tr '\t\r\n' '   ' | cut -c1-160; }

payload=$(cat)
json_fields hook_event_name cwd agent_type agent_id file_path memory_type load_reason tool_name reason tool_input.command tool_input.file_path tool_input.url
event="${JF[0]}"
raw_cwd=$(printf '%s' "${JF[1]}" | tr '\\' '/')
base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)
[ -d "$base_cwd/.claude" ] || exit 0

case "$event" in
  SubagentStart)
    detail="$(field "${JF[2]:--}")	$(field "${JF[3]:--}")" ;;
  InstructionsLoaded)
    p=$(printf '%s' "${JF[4]}" | tr '\\' '/')
    [ -n "$raw_cwd" ] && p=${p#"${raw_cwd%/}/"}
    detail="$(field "${JF[6]:--}")	$(field "${JF[5]:--}")	$(field "${p:--}")" ;;
  PermissionDenied)
    what="${JF[9]}"; [ -z "$what" ] && what="${JF[10]}"; [ -z "$what" ] && what="${JF[11]}"
    detail="$(field "${JF[7]:--}")	$(field "${JF[8]:--}")	$(field "${what:--}")" ;;
  *) exit 0 ;;
esac

log="$base_cwd/.claude/state/trace.log"
mkdir -p "${log%/*}" 2>/dev/null || exit 0
printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" "$event" "$detail" >> "$log" 2>/dev/null
lines=$(wc -l < "$log" 2>/dev/null | tr -d ' ')
if [ "${lines:-0}" -gt 2000 ]; then
  tail -n 1500 "$log" > "$log.tmp" 2>/dev/null && mv "$log.tmp" "$log" 2>/dev/null
fi
exit 0

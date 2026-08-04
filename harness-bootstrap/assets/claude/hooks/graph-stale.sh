#!/usr/bin/env bash
# graph-stale.sh
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking. When a SOURCE file is edited and a code graph has been built, records the path in
# .claude/state/code-graph.stale so agents (and /code-graph --check) know the graph no longer
# matches the code. The rebuild itself is deliberate (/code-graph), never a side effect of an edit:
# a hook that rebuilds a whole graph on every write would tax every session for a map most turns
# never read. Once the drift is large (more than 20 edited files since the last build), the map is
# probably steering dispatch decisions wrong rather than just slightly behind, so this ALSO emits
# hookSpecificOutput.additionalContext nudging /code-graph - same emit pattern as
# specs-reminder.sh's fixed-literal JSON. Never blocks: always exit 0.
#
# Contract: reads the PostToolUse JSON payload on stdin. Exit 0 = allow, always.

json_str() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$payload" | jq -r --arg k "$1" 'getpath($k | split(".")) // empty' 2>/dev/null
  elif command -v perl >/dev/null 2>&1; then
    printf '%s' "$payload" | perl -0777 -MJSON::PP -e 'my $k=shift; local $/; my $d=eval{decode_json(<STDIN>)}; exit 0 unless $d; for my $p (split /\./,$k){ $d = (ref($d) eq "HASH") ? $d->{$p} : undef; last unless defined $d } print $d if defined $d && !ref $d' "$1" 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$payload" | python3 -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for p in sys.argv[1].split("."):
    d = d.get(p) if isinstance(d, dict) else None
    if d is None: break
sys.stdout.write(d if isinstance(d, str) else "")' "$1" 2>/dev/null
  fi
}

# Same path normalization as guard-agent-spawn.sh: a bash on Windows cannot resolve "C:/x" in a
# file test, which would make the code-graph.json check below fail silently on some platforms.
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
path=$(json_str tool_input.file_path)
[ -z "$path" ] && exit 0
base_cwd=$(json_str cwd)
[ -z "$base_cwd" ] && base_cwd="."
base_cwd=$(norm_path "$base_cwd")

# Only source files invalidate the graph, and only if a graph exists to invalidate.
norm=${path//\\//}
case "$norm" in
  *.py|*.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs|*.go|*.java|*.cs|*.rb|*.php|*.rs) : ;;
  *) exit 0 ;;
esac
[ -f "$base_cwd/.claude/state/code-graph.json" ] || exit 0

mkdir -p "$base_cwd/.claude/state" 2>/dev/null
stale_file="$base_cwd/.claude/state/code-graph.stale"
printf '%s\n' "$norm" >> "$stale_file" 2>/dev/null

lines=$(wc -l < "$stale_file" 2>/dev/null | tr -d '[:space:]')
case "$lines" in ''|*[!0-9]*) lines=0 ;; esac
if [ "$lines" -gt 20 ]; then
  msg="The code graph is now stale against $lines edited source file(s) - run /code-graph to refresh the module map before relying on it for dispatch decisions."
  printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "$msg"
fi
exit 0

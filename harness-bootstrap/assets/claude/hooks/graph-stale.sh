#!/usr/bin/env bash
# graph-stale.sh
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking. When a SOURCE file is edited and a code graph has been built, records the path in
# .claude/state/code-graph.stale so agents (and /code-graph --check) know the graph no longer
# matches the code. The rebuild itself is deliberate (/code-graph), never a side effect of an edit:
# a hook that rebuilds a whole graph on every write would tax every session for a map most turns
# never read. Never blocks: always exit 0.
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

payload=$(cat)
path=$(json_str tool_input.file_path)
[ -z "$path" ] && exit 0
base_cwd=$(json_str cwd)
[ -z "$base_cwd" ] && base_cwd="."

# Only source files invalidate the graph, and only if a graph exists to invalidate.
norm=${path//\\//}
case "$norm" in
  *.py|*.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs|*.go|*.java|*.cs|*.rb|*.php|*.rs) : ;;
  *) exit 0 ;;
esac
[ -f "$base_cwd/.claude/state/code-graph.json" ] || exit 0

mkdir -p "$base_cwd/.claude/state" 2>/dev/null
printf '%s\n' "$norm" >> "$base_cwd/.claude/state/code-graph.stale" 2>/dev/null
exit 0

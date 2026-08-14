#!/usr/bin/env bash
# graph-stale.sh
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking graph maintenance, three tiers by cost of the rebuild:
#   1. HARNESS edits (.claude/ agents, rules, commands, hooks, settings.json, disabled.json):
#      regenerate .claude/state/harness-graph.json + harness-graph.html IMMEDIATELY - the scan
#      is ~50 small files, cheap enough to rebuild as a side effect, and a stale wiring map is
#      worse than the ~100ms it costs.
#   2. DOCS edits (docs/**/*.md, only when a docs graph was already built): regenerate the docs
#      graph + HTML immediately - docs trees are small too.
#   3. SOURCE edits: record the path in .claude/state/code-graph.stale so agents (and
#      /code-graph --check) know the graph lags the code. The rebuild itself stays deliberate
#      (/code-graph): a full source scan on every write would tax every session for a map most
#      turns never read. Past 20 accumulated edits this ALSO emits
#      hookSpecificOutput.additionalContext nudging /code-graph.
# Never blocks: always exit 0.
#
# Contract: reads the PostToolUse JSON payload on stdin. Exit 0 = allow, always.

# json_fields fetches every field this hook needs in ONE parser invocation instead of one per
# field - perl/python3 process startup (the fallback path when jq is absent) is the dominant cost
# of this hook, and it was being paid twice per edit. Sets array JF, same length as the arg list.
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
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
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
json_fields tool_input.file_path cwd
path="${JF[0]}"
base_cwd="${JF[1]}"
[ -z "$path" ] && exit 0
[ -z "$base_cwd" ] && base_cwd="."
base_cwd=$(norm_path "$base_cwd")

norm=${path//\\//}

# Tier 1: harness wiring changed - rebuild the harness graph now. Requires the scanner to be
# installed; a repo scaffolded before harness-graph.py existed just falls through harmlessly.
case "$norm" in
  */.claude/agents/*.md|*/.claude/rules/*.md|*/.claude/commands/*.md|\
  */.claude/hooks/*.sh|*/.claude/hooks/*.ps1|*/.claude/settings.json|*/.claude/disabled.json|\
  .claude/agents/*.md|.claude/rules/*.md|.claude/commands/*.md|\
  .claude/hooks/*.sh|.claude/hooks/*.ps1|.claude/settings.json|.claude/disabled.json)
    if [ -f "$base_cwd/.claude/scripts/harness-graph.py" ]; then
      if command -v python3 >/dev/null 2>&1; then PY=python3
      elif command -v python >/dev/null 2>&1; then PY=python
      else exit 0; fi
      "$PY" "$base_cwd/.claude/scripts/harness-graph.py" --target "$base_cwd" --html --quiet >/dev/null 2>&1
    fi
    exit 0 ;;
esac

# Tier 2: a docs file changed and a docs graph exists - rebuild it now.
case "$norm" in
  */docs/*.md|docs/*.md)
    if [ -f "$base_cwd/.claude/state/docs-graph.json" ] && \
       [ -f "$base_cwd/.claude/scripts/docs-graph.py" ]; then
      if command -v python3 >/dev/null 2>&1; then PY=python3
      elif command -v python >/dev/null 2>&1; then PY=python
      else exit 0; fi
      "$PY" "$base_cwd/.claude/scripts/docs-graph.py" --target "$base_cwd" >/dev/null 2>&1
      "$PY" "$base_cwd/.claude/scripts/graph-html.py" --target "$base_cwd" >/dev/null 2>&1
    fi
    exit 0 ;;
esac

# Tier 3: only source files invalidate the code graph, and only if a graph exists to invalidate.
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

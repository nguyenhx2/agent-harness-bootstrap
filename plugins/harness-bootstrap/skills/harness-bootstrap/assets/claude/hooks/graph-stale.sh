#!/usr/bin/env bash
# graph-stale.sh
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking graph maintenance, two tiers by edited path:
#   1. HARNESS edits (.claude/ agents, rules, commands, hooks, settings.json, disabled.json):
#      regenerate .claude/state/harness-graph.json + harness-graph.html IMMEDIATELY - the scan
#      is ~50 small files, cheap enough to rebuild as a side effect, and a stale wiring map is
#      worse than the ~100ms it costs.
#   2. SOURCE edits, once a module-boundary map exists (docs/context/code-graph.md, or the
#      machine copy in .claude/state/): ask `code-graph.py --file` whether THIS file now imports
#      across a module line the map does not list, and pass its additionalContext through. That
#      is the decision the map exists for, raised on the edit that makes it - not a staleness
#      count the agent has to act on later. Each new edge is named once until the next
#      /code-graph rebuild accepts it; a re-edit stays quiet.
# The docs graph is no longer rebuilt here: it is a check run on demand (/docs-graph).
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

# Tier 2: a source file changed - did it add a cross-module edge the boundary map lacks?
case "$norm" in
  *.py|*.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs|*.go|*.java|*.cs|*.rb|*.php|*.rs) : ;;
  *) exit 0 ;;
esac
[ -f "$base_cwd/.claude/scripts/code-graph.py" ] || exit 0
[ -f "$base_cwd/docs/context/code-graph.md" ] || [ -f "$base_cwd/.claude/state/code-graph.json" ] || exit 0
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else exit 0; fi
# The helper prints the PostToolUse JSON itself (json.dumps escapes the paths) or nothing.
"$PY" "$base_cwd/.claude/scripts/code-graph.py" --target "$base_cwd" --file "$(norm_path "$path")" --hook 2>/dev/null
exit 0

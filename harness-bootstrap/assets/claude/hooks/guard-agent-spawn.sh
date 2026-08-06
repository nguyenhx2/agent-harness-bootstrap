#!/usr/bin/env bash
# guard-agent-spawn.sh
# Event: PreToolUse   Matcher: Agent|Task
# The spawn boundary of the harness. Blocks two escapes:
#   1. Spawning an agent type that is not a roster seat (no .claude/agents/<type>.md) and not on
#      the explicit allowlist below. An agent the roster does not define runs with no scope, no
#      model budget, and no maxTurns - it is outside the harness by construction.
#   2. Overriding a roster seat's model at spawn time. The roster is where cost and capability are
#      decided; a per-spawn override silently re-prices a seat (a haiku seat billed at opus rates)
#      or downgrades a gate. Change the roster file, not the spawn.
#
# Read-only built-in types may be permitted in .claude/hooks/spawn-allowlist (one name per line,
# '#' comments). The shipped default allows Explore and Plan - both read-only - and nothing else.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow.

# JSON extraction: jq preferred; missing jq must not fail OPEN. Fall back to perl (core JSON::PP),
# then python3. With no extractor at all we warn and allow.
#
# json_fields fetches every field this hook needs (subagent_type, cwd, model, prompt) in ONE
# parser invocation instead of one per field - see hooks/README.md. This hook could call the
# perl/python3 fallback up to 4 times per spawn without it; now it is always at most 1. Sets
# array JF, same length as the arg list, in order.
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
    echo "guard-agent-spawn: no jq/perl/python3 available to parse the hook payload; allowing." >&2
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
}

# Same path normalization as the sibling hooks: a bash on Windows cannot resolve "C:/x" in a file
# test, which would make the roster lookup fail and the guard fail CLOSED on every spawn.
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
json_fields tool_input.subagent_type cwd tool_input.model tool_input.prompt
stype="${JF[0]}"

base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)
agents_dir="$base_cwd/.claude/agents"
allowlist="$base_cwd/.claude/hooks/spawn-allowlist"

# No harness in this repo: nothing to guard against, do not break other projects.
[ -d "$agents_dir" ] || exit 0

# --- 1. roster membership -------------------------------------------------
if [ -z "$stype" ]; then
  echo "BLOCKED: this spawn names no subagent_type, so it would run a generic agent outside the harness (no scope, no model budget, no maxTurns). Dispatch a roster seat from .claude/agents/ instead, or add the type to .claude/hooks/spawn-allowlist if the team decides it is safe." >&2
  exit 2
fi

allowed=0
[ -f "$agents_dir/$stype.md" ] && allowed=1
if [ "$allowed" -eq 0 ] && [ -f "$allowlist" ]; then
  while IFS= read -r line; do
    line=${line%%#*}
    line=$(printf '%s' "$line" | tr -d '[:space:]')
    [ -n "$line" ] && [ "$line" = "$stype" ] && allowed=1 && break
  done < "$allowlist"
fi
if [ "$allowed" -eq 0 ]; then
  echo "BLOCKED: '$stype' is not a roster seat (.claude/agents/$stype.md does not exist) and is not in .claude/hooks/spawn-allowlist. Agents outside the roster run with no scope, no cost budget, and no turn cap. Use a roster seat, or ask the user to extend the roster or the allowlist." >&2
  exit 2
fi

# --- 2. model pinning (roster seats only) ---------------------------------
override="${JF[2]}"
if [ -n "$override" ] && [ -f "$agents_dir/$stype.md" ]; then
  pinned=$(sed -n '/^---$/,/^---$/p' "$agents_dir/$stype.md" | grep -E '^model:' | head -1 | sed -E 's/^model:[[:space:]]*//; s/[[:space:]]*$//')
  if [ -n "$pinned" ] && [ "$override" != "$pinned" ]; then
    echo "BLOCKED: spawn overrides '$stype' from its roster model '$pinned' to '$override'. The roster is where cost and capability are decided (.claude/rules/model-policy.md). Edit .claude/agents/$stype.md if the seat's model should change." >&2
    exit 2
  fi
fi

# --- 3. task linkage for write-capable seats ------------------------------
# "No work begins before the task file exists" (task-tracking.md) is enforceable here: a dispatch
# to a seat that can Edit or Write must name a registered task, or the work is an orphan the board
# cannot see. Read-only seats (reviewers, researchers, spec-guardian) may be dispatched freely -
# planning-phase consultation does not need a task yet.
if [ -f "$agents_dir/$stype.md" ]; then
  seat_tools=$(sed -n '/^---$/,/^---$/p' "$agents_dir/$stype.md" | grep -E '^tools:' | head -1)
  if printf '%s' "$seat_tools" | grep -Eq '(^|[,: ])(Edit|Write)(,| |$)'; then
    if [ -d "$base_cwd/docs/tasks/active" ]; then
      task_id=$(printf '%s' "${JF[3]}" | grep -oE 'TASK-[0-9]{1,5}' | head -1)
      if [ -z "$task_id" ]; then
        echo "BLOCKED: '$stype' can write, but this dispatch names no TASK-NNN. Work with no registered task is invisible to the board and becomes an orphan. Register the task (see /new-task), put its code in the dispatch prompt, and dispatch again." >&2
        exit 2
      fi
      if ! ls "$base_cwd/docs/tasks/active/"*"$task_id"* >/dev/null 2>&1; then
        echo "BLOCKED: this dispatch names $task_id but docs/tasks/active/ holds no such task file. A Planned or Active task lives in active/ (task-control.md). Register it first, then dispatch." >&2
        exit 2
      fi
    fi
  fi
fi

exit 0

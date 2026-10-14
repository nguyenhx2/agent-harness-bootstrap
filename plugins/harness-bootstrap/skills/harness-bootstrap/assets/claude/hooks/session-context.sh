#!/usr/bin/env bash
# session-context.sh
# Event: SessionStart   Matcher: startup|resume|clear|compact
# Flag: long
# Enforces: .claude/rules/task-tracking.md (start from the board, not from memory)
# NEVER BLOCKS (SessionStart cannot). Injects additionalContext naming every task in
# docs/tasks/active/ with its owner and next step - the task's "## Checkpoint" Next step when
# `task.py checkpoint` has set one, otherwise its first unchecked item. After a compaction
# (source=compact) it also points at .claude/state/compact-checkpoint.md, which compact-checkpoint
# wrote moments earlier. Silent when there is no active task and no checkpoint to point at.
#
# WHY CONTEXT, NOT A RULE: a long session loses its place in exactly two ways - a new session that
# never read the board, and a compaction that summarized the board away. Both are moments a hook
# sees and a rule does not. At most 8 tasks are listed, so the injection stays a few hundred
# tokens however large the board grows.
#
# PARITY CONTRACT: session-context.sh and session-context.ps1 must emit the same text.
#
# Contract: reads the SessionStart JSON payload on stdin (source, cwd). Emits
# hookSpecificOutput.additionalContext JSON on stdout, or nothing. Always exit 0.

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

# Same parser as compact-checkpoint.sh: owner, first unchecked item, checkpoint Next step,
# separated by \037 (TAB is IFS whitespace and would collapse an empty field).
task_fields() {
  awk '{ sub(/\r$/, "") }
       NR == 1 && /^---/ { fm = 1; next }
       fm && /^---/ { fm = 0; next }
       fm && /^owner:/  { sub(/^owner:[ \t]*/, "");  o = $0 }
       !fm && /^## / { cp = ($0 == "## Checkpoint") }
       !fm && nx == "" && /^[ \t]*- \[ \] [^<]/ { sub(/^[ \t]*- \[ \] /, ""); nx = $0 }
       cp && /^- Next step:/ { sub(/^- Next step:[ \t]*/, ""); cn = $0 }
       END { printf "%s\037%s\037%s\n", o, nx, cn }' "$1" 2>/dev/null
}

# JSON-safe text: drop quotes, backslashes and control characters (same in both flavors).
clean() { printf '%s' "$1" | tr -d '"\\' | tr -d '\000-\037'; }

payload=$(cat)
json_fields source cwd
source_kind="${JF[0]}"
base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)

msg=""
listed=0
total=0
for f in "$base_cwd"/docs/tasks/active/*.md; do
  [ -f "$f" ] || continue
  total=$((total + 1))
  [ "$listed" -ge 8 ] && continue
  listed=$((listed + 1))
  IFS=$'\037' read -r o nx cn <<< "$(task_fields "$f")"
  next="$cn"
  [ -z "$next" ] || [ "$next" = "-" ] && next="$nx"
  [ -z "$next" ] && next="-"
  name=$(clean "${f##*/}")
  msg="$msg\\n- $name (owner: $(clean "${o:--}")) - next: $(clean "$next")"
done
if [ "$total" -gt 0 ]; then
  more=""
  [ "$total" -gt "$listed" ] && more=" ($((total - listed)) more not shown)"
  msg="session-context: active tasks in docs/tasks/active/$more:$msg\\nDetail for one task: python .claude/scripts/task.py resume <TASK-NNN>. Update the board only through task.py."
fi
if [ "$source_kind" = "compact" ] && [ -f "$base_cwd/.claude/state/compact-checkpoint.md" ]; then
  note="Context was just compacted. Re-read .claude/state/compact-checkpoint.md - it records the branch, the active tasks and the uncommitted changes as they were before the summary - before continuing."
  if [ -n "$msg" ]; then msg="$note\\n$msg"; else msg="$note"; fi
fi
[ -z "$msg" ] && exit 0

printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$msg\"}}"
exit 0

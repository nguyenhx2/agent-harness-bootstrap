#!/usr/bin/env bash
# guard-board.sh
# Event: PreToolUse   Matcher: Edit|Write (a MultiEdit payload is handled too, if a host sends one)
# Flag: none - ships with every harness, beside .claude/scripts/task.py
# Enforces: .claude/rules/task-tracking.md (one writer for task state)
# BLOCKS (exit 2) a hand edit to the task rows of the board, docs/tasks/master-plan.md:
#   - an Edit whose old_string or new_string touches a task row (`| TASK-NNN |`)
#   - a Write that replaces the board when it already exists
#   - a MultiEdit of the board (its edits cannot be inspected cheaply, so it is refused whole)
# A task's state lives in three places - the board row, the task file's `status:`, and the folder
# it sits in - and `python .claude/scripts/task.py move` changes all three together and reads the
# row back. A hand edit changes one of them, and the board then says one thing and the file
# another.
#
# Allowed: everything task.py does (it writes through Bash, which this matcher never sees); the
# first Write that CREATES the board (bootstrap; the scaffolder copies it without a tool call at
# all); and Edits that touch no task row - the Phases table and the prose around it have no CLI
# verb and stay hand-edited.
#
# WHY BLOCK, NOT WARN: drift between the board and the files is exactly the failure task.py exists
# to make impossible, and the correct command is always available and is one line.
#
# PARITY CONTRACT: guard-board.sh and guard-board.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (reason on stderr, shown
# to Claude); exit 0 = allow. Fails OPEN on an unreadable payload.

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
  else
    echo "guard-board: no jq/perl/python3 available to parse the hook payload; allowing." >&2
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

HINT='Use the task CLI, which updates the row, the task file status: and its folder together: python .claude/scripts/task.py move <TASK-NNN> <Planned|Active|Blocked|Pending|Done> --note "..." (task.py new "<title>" ... adds a task; task.py check reports drift).'

payload=$(cat)
json_fields tool_name tool_input.file_path tool_input.old_string tool_input.new_string cwd
tool="${JF[0]}"
path=$(printf '%s' "${JF[1]}" | tr '\\' '/')
[ -z "$path" ] && exit 0
case "$path" in
  docs/tasks/master-plan.md|./docs/tasks/master-plan.md|*/docs/tasks/master-plan.md) ;;
  *) exit 0 ;;
esac

case "$tool" in
  MultiEdit)
    echo "BLOCKED by guard-board: a MultiEdit of docs/tasks/master-plan.md is refused whole - task rows are written only by task.py. $HINT Edit the Phases table or prose with a single Edit instead." >&2
    exit 2
    ;;
  Write)
    base_cwd=$(norm_path "${JF[4]}")
    [ -z "$base_cwd" ] && base_cwd=$(pwd)
    case "$path" in
      /*|[A-Za-z]:/*) abs=$(norm_path "$path") ;;
      *) abs="$base_cwd/$path" ;;
    esac
    [ -f "$abs" ] || exit 0
    echo "BLOCKED by guard-board: rewriting docs/tasks/master-plan.md would replace task rows by hand. $HINT" >&2
    exit 2
    ;;
  *)
    if printf '%s\n%s\n' "${JF[2]}" "${JF[3]}" | grep -Eq '\|[[:space:]]*TASK-[0-9]+'; then
      echo "BLOCKED by guard-board: this edit changes a task row of docs/tasks/master-plan.md by hand. $HINT" >&2
      exit 2
    fi
    ;;
esac
exit 0

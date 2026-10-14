#!/usr/bin/env bash
# compact-checkpoint.sh
# Event: PreCompact   Matcher: manual|auto
# Flag: long
# Enforces: .claude/rules/task-tracking.md (state lives on disk, not in the context window)
# NEVER BLOCKS. Before a compaction, writes .claude/state/compact-checkpoint.md: the branch, any
# /compact instructions, every task in docs/tasks/active/ with its status, owner and first
# unchecked item, the task's own "## Checkpoint" lines (Next step, Last green commit, Open
# questions - kept current by `python .claude/scripts/task.py checkpoint`), and the uncommitted
# changes. The summary a compaction produces is lossy; this file is not. session-context points
# the post-compaction session at it, and `task.py resume <TASK-NNN>` gives the per-task detail.
#
# WHY NEVER BLOCK: PreCompact can block compaction, and blocking an automatic compaction that was
# triggered to recover from a context-limit error makes the request fail outright. A checkpoint
# that could fail the session is worse than none, so every path here exits 0.
#
# The file is overwritten on every compaction and carries no timestamp: it is state, not a log,
# and .claude/state/ is never committed.
#
# PARITY CONTRACT: compact-checkpoint.sh and compact-checkpoint.ps1 must write the same sections
# from the same sources.
#
# Contract: reads the PreCompact JSON payload on stdin (trigger, custom_instructions, cwd).
# Always exit 0.

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

# task_fields FILE -> title, status, owner, first unchecked item, then the three lines of the
# task's "## Checkpoint" section (written by `task.py checkpoint`), separated by the ASCII unit
# separator (\037). Not TAB: TAB is IFS whitespace, so an empty field would collapse and shift
# every field after it. Placeholder items that still read `<...>` are skipped.
task_fields() {
  awk '{ sub(/\r$/, "") }
       NR == 1 && /^---/ { fm = 1; next }
       fm && /^---/ { fm = 0; next }
       fm && /^title:/  { sub(/^title:[ \t]*/, "");  gsub(/"/, ""); t = $0 }
       fm && /^status:/ { sub(/^status:[ \t]*/, ""); s = $0 }
       fm && /^owner:/  { sub(/^owner:[ \t]*/, "");  o = $0 }
       !fm && /^## / { cp = ($0 == "## Checkpoint") }
       !fm && nx == "" && /^[ \t]*- \[ \] [^<]/ { sub(/^[ \t]*- \[ \] /, ""); nx = $0 }
       cp && /^- Next step:/         { sub(/^- Next step:[ \t]*/, "");         cn = $0 }
       cp && /^- Last green commit:/ { sub(/^- Last green commit:[ \t]*/, ""); cg = $0 }
       cp && /^- Open questions:/    { sub(/^- Open questions:[ \t]*/, "");    cq = $0 }
       END { printf "%s\037%s\037%s\037%s\037%s\037%s\037%s\n", t, s, o, nx, cn, cg, cq }' "$1" 2>/dev/null
}

payload=$(cat)
json_fields trigger custom_instructions cwd
trigger="${JF[0]:-auto}"
instr="${JF[1]}"
base_cwd=$(norm_path "${JF[2]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)
[ -d "$base_cwd/.claude" ] || exit 0

state="$base_cwd/.claude/state"
mkdir -p "$state" 2>/dev/null || exit 0
out="$state/compact-checkpoint.md"

{
  echo "# Compaction checkpoint"
  echo
  echo "Written by the compact-checkpoint hook before compaction (trigger: $trigger) and overwritten by"
  echo "the next one. It is what the session knew before its context was summarized: re-read it, then"
  echo "the task files it names, before continuing. Per task: python .claude/scripts/task.py resume <TASK-NNN>."
  echo
  branch=""
  command -v git >/dev/null 2>&1 && branch=$(git -C "$base_cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
  echo "- Branch: ${branch:--}"
  echo "- Compaction instructions: ${instr:--}"
  echo
  echo "## Active tasks"
  echo
  found=0
  for f in "$base_cwd"/docs/tasks/active/*.md; do
    [ -f "$f" ] || continue
    found=1
    IFS=$'\037' read -r t s o nx cn cg cq <<< "$(task_fields "$f")"
    echo "- ${f##*/} - ${t:--} (status: ${s:--}, owner: ${o:--})"
    echo "  - checkpoint next step: ${cn:--}"
    echo "  - last green commit: ${cg:--}"
    echo "  - open questions: ${cq:--}"
    echo "  - first unchecked item: ${nx:--}"
  done
  [ "$found" -eq 0 ] && echo "- none"
  echo
  echo "## Uncommitted changes"
  echo
  changes=""
  command -v git >/dev/null 2>&1 && changes=$(git -C "$base_cwd" status --short 2>/dev/null | head -n 20)
  if [ -n "$changes" ]; then
    printf '%s\n' "$changes" | sed 's/^/    /'
  else
    echo "- none"
  fi
} > "$out" 2>/dev/null

exit 0

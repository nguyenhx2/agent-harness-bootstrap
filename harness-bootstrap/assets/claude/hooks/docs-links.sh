#!/usr/bin/env bash
# docs-links.sh
# Event: PostToolUse   Matcher: Edit|Write
# Flag: purpose_docs
# Enforces: .claude/rules/docs-workflow.md (a link is a promise that the target exists)
# WARNS (additionalContext, exit 0) when a Markdown file just written contains relative links
# `[text](path)` whose target does not exist on disk, resolved against the file's own directory.
# Lists up to 5. Skips fenced code blocks, URLs with a scheme (https:, mailto:, ...), same-page
# anchors (#...), and site-absolute paths (/...), whose root this hook cannot know. A `#fragment`
# or `?query` on a relative link is ignored; only the file has to exist.
#
# WHY WARN, NOT BLOCK: a docs restructure moves files in several steps and links are broken in
# between - blocking each intermediate write would stop the restructure itself. The reminder
# names the broken targets right after the write, while the agent still knows where it moved
# them. A full link check belongs in CI, where it can fail the build.
#
# PARITY CONTRACT: docs-links.sh and docs-links.ps1 must stay behaviorally EQUIVALENT - same link
# pattern, same skips, same resolution.
#
# Contract: reads the PostToolUse JSON payload on stdin. Emits hookSpecificOutput JSON on stdout,
# or nothing. Always exit 0.

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

payload=$(cat)
json_fields tool_input.file_path cwd
path=$(printf '%s' "${JF[0]}" | tr '\\' '/')
[ -z "$path" ] && exit 0
case "$path" in *.md|*.MD|*.markdown) ;; *) exit 0 ;; esac

base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)
case "$path" in
  /*|[A-Za-z]:/*) abs=$(norm_path "$path") ;;
  *) abs="$base_cwd/$path" ;;
esac
[ -f "$abs" ] || exit 0
dir=${abs%/*}

targets=$(awk '{ sub(/\r$/, "") }
  /^[ \t]*(```|~~~)/ { f = !f; next }
  !f {
    s = $0
    while (match(s, /\]\([^)]+\)/)) { print substr(s, RSTART + 2, RLENGTH - 3); s = substr(s, RSTART + RLENGTH) }
  }' "$abs" 2>/dev/null)

broken=""
nbroken=0
while IFS= read -r t; do
  [ -z "$t" ] && continue
  t=${t#<}; t=${t%%>*}
  t=${t%% *}
  case "$t" in
    "#"*|/*) continue ;;
  esac
  printf '%s' "$t" | grep -Eq '^[A-Za-z][A-Za-z0-9+.-]*:' && continue
  p=${t%%#*}; p=${p%%\?*}
  [ -z "$p" ] && continue
  p=${p//%20/ }
  if [ ! -e "$dir/$p" ]; then
    nbroken=$((nbroken + 1))
    [ "$nbroken" -le 5 ] && broken="$broken, $(printf '%s' "$t" | tr -d '"\\' | tr -d '\000-\037')"
  fi
done <<< "$targets"

[ "$nbroken" -eq 0 ] && exit 0
name=$(printf '%s' "$path" | tr -d '"\\' | tr -d '\000-\037')
printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"docs-links: $name has $nbroken relative link(s) whose target does not exist: ${broken#, }. Fix the path, or remove the link if the target is gone.\"}}"
exit 0

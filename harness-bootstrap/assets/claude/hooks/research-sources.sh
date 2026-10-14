#!/usr/bin/env bash
# research-sources.sh
# Event: PostToolUse   Matcher: Edit|Write
# Flag: purpose_research
# Enforces: .claude/rules/docs-workflow.md (a research claim carries its source)
# WARNS (additionalContext, exit 0) when a research note - a Markdown file under a research/,
# findings/, notes/, report(s)/, brief(s)/, sources/ or literature/ directory - has at least 400
# characters of text and cites nothing: no URL, no DOI or arXiv id, no footnote ([^1]), no
# Sources/References/Bibliography heading or "Source:" line, and no explicit "Assumption:" /
# "Unsourced:" label.
#
# WHY WARN, NOT BLOCK: a note is written in passes - claims first, sources while checking them -
# and a block on the first draft would stop the work that produces the sources. The reminder
# arrives right after the write, which is when adding the source costs least. A note with no
# claims (short, or explicitly labelled as assumptions) stays silent.
#
# PARITY CONTRACT: research-sources.sh and research-sources.ps1 must stay behaviorally
# EQUIVALENT - same directories, same threshold, same source markers.
#
# Contract: reads the PostToolUse JSON payload on stdin. Emits hookSpecificOutput JSON on stdout,
# or nothing. Always exit 0.

MIN_CHARS=400
SOURCE_RE='(https?://|doi:|doi\.org/|arxiv|\[\^[^]]+\]|^#+[[:space:]]*(sources|references|bibliography|citations)|(^|[^a-z])sources?:|assumption:|unsourced:)'

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
printf '%s' "/$path" | grep -Eiq '/(research|findings|notes|reports?|briefs?|sources|literature)/' || exit 0

base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)
case "$path" in
  /*|[A-Za-z]:/*) abs=$(norm_path "$path") ;;
  *) abs="$base_cwd/$path" ;;
esac
[ -f "$abs" ] || exit 0

chars=$(tr -d ' \t\r\n' < "$abs" | wc -c | tr -d ' ')
[ "${chars:-0}" -lt "$MIN_CHARS" ] && exit 0
grep -Eiq "$SOURCE_RE" "$abs" && exit 0

name=$(printf '%s' "$path" | tr -d '"\\' | tr -d '\000-\037')
printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"research-sources: $name makes claims but cites no source - no URL, DOI, footnote, or Sources section. Give each factual claim its source as you check it, or label it explicitly (Assumption: / Unsourced:) so a reader can tell evidence from inference.\"}}"
exit 0

#!/usr/bin/env bash
# agent-history.sh
# Event: SubagentStop   Matcher: * (every subagent)
#
# WHY SubagentStop AND NOT PostToolUse: an earlier version of this hook was registered as
# PostToolUse with matcher "Task|Agent" and read .tool_input / .tool_response. That was wrong.
# Claude Code has a dedicated SubagentStop event that fires when a subagent finishes, and its
# payload has NO tool_input/tool_response at all - so the old hook archived empty files.
# SubagentStop is the correct surface. The subagent tool is `Agent` (there is no `Task` tool);
# with SubagentStop we do not name the tool at all.
#
# SubagentStop payload fields used here:
#   cwd                    - session working dir; ALL paths resolve against this, never a bare
#                            relative path (the hook process's cwd is not the project's)
#   agent_type             - the subagent's type/name
#   agent_id               - the subagent's identifier
#   agent_transcript_path  - JSONL transcript of the SUBAGENT's own run (preferred source)
#   transcript_path        - JSONL transcript of the parent session (fallback)
#
# Non-blocking audit trail: archives every completed subagent run (the prompt it was given + its
# final response) as one markdown file under .claude/state/history/ (gitignore .claude/state/).
# The history-tracker agent reads and curates the archive.
#
# Detail level and retention come from .claude/state/history-level (2 lines: level, keep-count).
#   full    - whole prompt + response per run (the historical behavior; default when unreadable)
#   summary - per-run file, prompt/response truncated to 1500 chars + transcript pointer
#   minimal - one index line per run in state/history/index.md, no per-run file
#   off     - record nothing
# After a per-run write, only the newest <keep-count> files are kept (filenames start with the
# timestamp, so name order is age order; index.md is never pruned). keep-count 0 means
# NEVER PRUNE, not keep-none - minimal/off write no per-run files, so 0 is their natural
# value and nothing accumulates.
#
# Contract: ALWAYS exits 0. This hook must never block a run and never throw.

{
  payload=$(cat)
  [ -z "$payload" ] && exit 0

  # JSON extraction: jq preferred, perl (core JSON::PP) then python3 as fallbacks, because jq is
  # not installed by default on macOS.
  #
  # json_fields fetches every field this hook needs (cwd, agent_type, agent_id,
  # agent_transcript_path, transcript_path) in ONE parser invocation instead of one per field -
  # see hooks/README.md. This hook was the worst offender: 5 separate perl/python3 startups on a
  # no-jq machine, one per field, on every single subagent completion. Sets array JF, same length
  # as the arg list, in order.
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

  # Pull the first user turn (the prompt sent in) and the last assistant turn (final response) out
  # of a JSONL transcript: one object per line, top-level `type` ('user'|'assistant') and a
  # `message` object with `role` and a `content` array of blocks (text / tool_use / tool_result).
  #
  # ONE call returns BOTH prompt and response (NUL-separated), instead of two separate
  # perl/python3 startups that each re-read and re-parse the whole transcript file from scratch.
  transcript_parts() {   # $1 = transcript path; sets PROMPT_TXT and RESPONSE_TXT
    PROMPT_TXT=""; RESPONSE_TXT=""
    local out=()
    if command -v perl >/dev/null 2>&1; then
      while IFS= read -r -d '' v; do out+=("$v"); done < <(
        perl -MJSON::PP -e '
          my ($f) = @ARGV;
          open(my $fh, "<", $f) or exit 0;
          my ($prompt, $response);
          while (my $line = <$fh>) {
            next unless $line =~ /\S/;
            my $e = eval { decode_json($line) } or next;
            my $m = $e->{message} or next;
            my $c = $m->{content};
            my $text = "";
            if (!ref $c) { $text = defined $c ? $c : ""; }
            elsif (ref $c eq "ARRAY") {
              $text = join("\n", map { $_->{text} } grep { ref $_ eq "HASH" && ($_->{type}//"") eq "text" && defined $_->{text} } @$c);
            }
            next unless $text =~ /\S/;
            if (($e->{type}//"") eq "user")           { $prompt = $text unless defined $prompt; }
            elsif (($e->{type}//"") eq "assistant")   { $response = $text; }
          }
          print(($prompt // "") . "\0" . ($response // "") . "\0");
        ' "$1" 2>/dev/null
      )
    elif command -v python3 >/dev/null 2>&1; then
      while IFS= read -r -d '' v; do out+=("$v"); done < <(
        python3 -c '
import json, sys
f = sys.argv[1]
prompt = response = None
try:
    fh = open(f, encoding="utf-8", errors="replace")
except Exception:
    fh = None
if fh:
    for line in fh:
        line = line.strip()
        if not line: continue
        try: e = json.loads(line)
        except Exception: continue
        m = e.get("message") or {}
        c = m.get("content")
        if isinstance(c, str): text = c
        elif isinstance(c, list):
            text = "\n".join(b.get("text","") for b in c if isinstance(b, dict) and b.get("type") == "text")
        else: text = ""
        if not text.strip(): continue
        if e.get("type") == "user" and prompt is None: prompt = text
        elif e.get("type") == "assistant": response = text
sys.stdout.write((prompt or "") + "\0" + (response or "") + "\0")
' "$1" 2>/dev/null
      )
    fi
    PROMPT_TXT="${out[0]:-}"
    RESPONSE_TXT="${out[1]:-}"
  }

  # Windows-bash path normalization: the payload's cwd and transcript paths arrive as
  # "C:\..." or "C:/...", which this bash cannot address directly (it would silently create
  # a literal "C:" directory and archive into it). Same contract as the other .sh hooks.
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

  # --- resolve the archive dir against the payload's cwd -------------------------------------
  json_fields cwd agent_type agent_id agent_transcript_path transcript_path
  base="${JF[0]}"
  [ -z "$base" ] && base=$(pwd)
  base=$(norm_path "$base")

  # --- detail level + retention: .claude/state/history-level, 2 lines ------------------------
  level='full'; keep=200
  cfg="$base/.claude/state/history-level"
  if [ -f "$cfg" ]; then
    l1=$(sed -n 1p "$cfg" | tr -d ' \r')
    l2=$(sed -n 2p "$cfg" | tr -d ' \r')
    case "$l1" in full|summary|minimal|off) level="$l1" ;; esac
    case "$l2" in ''|*[!0-9]*) ;; *) keep=$l2 ;; esac
  fi
  [ "$level" = 'off' ] && exit 0

  dir="$base/.claude/state/history"
  mkdir -p "$dir" || exit 0

  agent="${JF[1]}";  [ -z "$agent" ] && agent='agent'
  agent_id="${JF[2]}"

  tp="${JF[3]}"
  [ -z "$tp" ] && tp="${JF[4]}"
  tp=$(norm_path "$tp")
  case "$tp" in
    ''|/*) ;;
    *) tp="$base/$tp" ;;
  esac

  prompt=''
  response=''
  if [ -n "$tp" ] && [ -f "$tp" ]; then
    transcript_parts "$tp"
    prompt="$PROMPT_TXT"
    response="$RESPONSE_TXT"
  fi
  [ -z "$prompt" ]   && prompt='(prompt unavailable - no readable subagent transcript)'
  [ -z "$response" ] && response='(response unavailable - no readable subagent transcript)'

  # --- slug from the first line of the prompt (SubagentStop has no `description` field) -------
  desc=$(printf '%s\n' "$prompt" | grep -m1 '[^[:space:]]' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')
  [ -z "$desc" ] && desc='run'
  slug=$(printf '%s' "$desc" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-48 | sed -E 's/-+$//')
  [ -z "$slug" ] && slug='run'

  # --- minimal: one index line, no per-run file ----------------------------------------------
  if [ "$level" = 'minimal' ]; then
    printf '%s | %s | %s | %.120s\n' "$(date +%Y%m%d-%H%M%S)" "$agent" "$agent_id" "$desc" \
      >> "$dir/index.md"
    exit 0
  fi

  # --- summary: cap both bodies, keep the pointer to the full transcript ---------------------
  if [ "$level" = 'summary' ]; then
    if [ "${#prompt}" -gt 1500 ]; then
      prompt="${prompt:0:1500}
[truncated - full transcript: $tp]"
    fi
    if [ "${#response}" -gt 1500 ]; then
      response="${response:0:1500}
[truncated - full transcript: $tp]"
    fi
  fi

  rand=$(tr -dc 'a-z' < /dev/urandom 2>/dev/null | head -c 4)
  [ -z "$rand" ] && rand=$(printf '%04d' $((RANDOM % 10000)))
  file="$dir/$(date +%Y%m%d-%H%M%S)-$agent-$slug-$rand.md"

  {
    echo "# $agent - $desc"
    echo
    echo "- agent_type: $agent"
    echo "- agent_id: $agent_id"
    echo "- finished: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "- transcript: $tp"
    echo
    echo '## Prompt'
    echo
    echo '```'
    printf '%s\n' "$prompt"
    echo '```'
    echo
    echo '## Response'
    echo
    echo '```'
    printf '%s\n' "$response"
    echo '```'
  } > "$file"

  # --- retention: keep only the newest $keep per-run files (never index.md) -------------------
  if [ "$keep" -gt 0 ] 2>/dev/null; then
    count=$(ls -1 "$dir"/*.md 2>/dev/null | grep -cv '/index\.md$')
    excess=$((count - keep))
    if [ "$excess" -gt 0 ]; then
      ls -1 "$dir"/*.md 2>/dev/null | grep -v '/index\.md$' | sort | sed -n "1,${excess}p" \
        | while IFS= read -r old; do rm -f "$old"; done
    fi
  fi
} 2>/dev/null
exit 0

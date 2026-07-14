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
# Contract: ALWAYS exits 0. This hook must never block a run and never throw.

{
  payload=$(cat)
  [ -z "$payload" ] && exit 0

  # JSON extraction: jq preferred, perl (core JSON::PP) then python3 as fallbacks, because jq is
  # not installed by default on macOS.
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

  # Pull the first user turn (the prompt sent in) and the last assistant turn (final response) out
  # of a JSONL transcript: one object per line, top-level `type` ('user'|'assistant') and a
  # `message` object with `role` and a `content` array of blocks (text / tool_use / tool_result).
  transcript_part() {   # $1 = transcript path, $2 = 'prompt' | 'response'
    if command -v perl >/dev/null 2>&1; then
      perl -MJSON::PP -e '
        my ($f, $want) = @ARGV;
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
        print(($want eq "prompt" ? $prompt : $response) // "");
      ' "$1" "$2" 2>/dev/null
    elif command -v python3 >/dev/null 2>&1; then
      python3 -c '
import json, sys
f, want = sys.argv[1], sys.argv[2]
prompt = response = None
try:
    fh = open(f, encoding="utf-8", errors="replace")
except Exception:
    sys.exit(0)
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
sys.stdout.write((prompt if want == "prompt" else response) or "")
' "$1" "$2" 2>/dev/null
    fi
  }

  # --- resolve the archive dir against the payload's cwd -------------------------------------
  base=$(json_str cwd)
  [ -z "$base" ] && base=$(pwd)
  dir="$base/.claude/state/history"
  mkdir -p "$dir" || exit 0

  agent=$(json_str agent_type);  [ -z "$agent" ] && agent='agent'
  agent_id=$(json_str agent_id)

  tp=$(json_str agent_transcript_path)
  [ -z "$tp" ] && tp=$(json_str transcript_path)
  case "$tp" in
    ''|/*|[A-Za-z]:/*) ;;
    *) tp="$base/$tp" ;;
  esac

  prompt=''
  response=''
  if [ -n "$tp" ] && [ -f "$tp" ]; then
    prompt=$(transcript_part "$tp" prompt)
    response=$(transcript_part "$tp" response)
  fi
  [ -z "$prompt" ]   && prompt='(prompt unavailable - no readable subagent transcript)'
  [ -z "$response" ] && response='(response unavailable - no readable subagent transcript)'

  # --- slug from the first line of the prompt (SubagentStop has no `description` field) -------
  desc=$(printf '%s\n' "$prompt" | grep -m1 '[^[:space:]]' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')
  [ -z "$desc" ] && desc='run'
  slug=$(printf '%s' "$desc" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-48 | sed -E 's/-+$//')
  [ -z "$slug" ] && slug='run'

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
} 2>/dev/null
exit 0

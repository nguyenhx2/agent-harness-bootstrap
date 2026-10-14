#!/usr/bin/env bash
# stop-evidence.sh
# Events: Stop and SubagentStop (no matcher)
# Flag: hooks_strict
# Enforces: .claude/rules/agent-guardrails.md ("done" means shown, not asserted)
# BLOCKS the stop ONCE (exit 2, reason on stderr, which Claude reads and acts on) when the final
# message claims completion - "all tests pass", "the fix is done", "ready to merge",
# "successfully implemented" - and carries no evidence: no command output, no pass/fail count,
# no exit code, no "Evidence:"/"Verified" line, and no honest "not verified".
#
# WHY BLOCK, AND WHY ONLY ONCE: a completion claim with nothing behind it is the most expensive
# sentence an agent writes - the orchestrator, or the user, acts on it. Blocking costs one extra
# turn in which the agent either shows what it ran or says plainly that it did not verify; both
# are fine answers. It never blocks twice in a row: when `stop_hook_active` is true the session is
# already continuing because of a stop hook, and this hook allows unconditionally. Claude Code also
# caps consecutive stop-hook continuations, but a hook that relied on that cap would burn eight
# turns where one is enough.
#
# This is a heuristic on wording, and it errs toward letting a stop through: a message that makes
# no completion claim is never touched, and neither is a session that changed nothing. "That bug is
# fixed upstream in v2.3, so no change is needed here" is an answer, not a claim about work - so the
# hook first asks whether this session EDITED anything: an Edit/Write/MultiEdit/NotebookEdit call
# in the transcript, or, with no transcript to read, uncommitted changes in the repository.
#
# PARITY CONTRACT: stop-evidence.sh and stop-evidence.ps1 must stay behaviorally EQUIVALENT -
# same claim and evidence patterns, both case-insensitive.
#
# Contract: reads the Stop/SubagentStop JSON payload on stdin (fields: stop_hook_active,
# last_assistant_message, hook_event_name). exit 2 = keep going (reason on stderr); exit 0 =
# allow the stop. Fails OPEN on an unreadable payload.

CLAIM='(all (the )?tests (now )?pass|tests (are )?(now )?passing|(is|are) (now )?(done|complete|completed|finished|fixed|resolved)|(task|work|implementation|feature|fix|change|changes) (is |are )?(now )?(done|complete|completed)|ready (to merge|for review|to ship)|successfully (implemented|fixed|completed|resolved)|implementation complete)'
EVIDENCE='(evidence:|verified|verification:|did not run|could not run|not run|[0-9]+ (tests? )?(passed|passing|failed|failing)|exit (code |status )?[0-9]|```|[0-9]+/[0-9]+ (passed|tests|checks)|(^|[^a-z])ran([^a-z]|$))'

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

# A bash on Windows cannot open "C:/x"; same normalization as the sibling hooks.
norm_path() {
  local p d rest
  p=$(printf '%s' "$1" | tr '\\' '/')
  case "$p" in
    [A-Za-z]:/*) ;;
    *) printf '%s' "$p"; return ;;
  esac
  if command -v wslpath >/dev/null 2>&1; then wslpath -u "$p" 2>/dev/null && return; fi
  if command -v cygpath >/dev/null 2>&1; then cygpath -u "$p" 2>/dev/null && return; fi
  d=$(printf '%s' "${p%%:*}" | tr 'A-Z' 'a-z')
  rest=${p#*:}
  if [ -d "/mnt/$d" ]; then printf '/mnt/%s%s' "$d" "$rest"; else printf '/%s%s' "$d" "$rest"; fi
}

payload=$(cat)
json_fields stop_hook_active last_assistant_message hook_event_name agent_transcript_path transcript_path cwd
[ "${JF[0]}" = "true" ] && exit 0
msg="${JF[1]}"
[ -z "$msg" ] && exit 0

printf '%s\n' "$msg" | grep -Eiq "$CLAIM" || exit 0
printf '%s\n' "$msg" | grep -Eiq "$EVIDENCE" && exit 0

# Did this session change anything? A subagent's own transcript first, then the session's.
EDIT_CALL='"name"[[:space:]]*:[[:space:]]*"(Edit|Write|MultiEdit|NotebookEdit)"'
transcript=$(norm_path "${JF[3]:-${JF[4]}}")
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  grep -Eq "$EDIT_CALL" "$transcript" || exit 0
else
  dir=$(norm_path "${JF[5]}")
  [ -z "$dir" ] && dir=$(pwd)
  status=$(git -C "$dir" status --porcelain 2>/dev/null) || exit 0
  [ -z "$status" ] && exit 0
fi

who="your"
[ "${JF[2]}" = "SubagentStop" ] && who="this subagent's"
echo "stop-evidence: $who final message claims the work is done but shows no evidence. Before stopping, add one line that starts with 'Evidence:' naming what you ran and what it returned (for example: Evidence: npm test - 42 passed, exit 0), or say plainly 'Not verified:' and why. Do not re-run anything you already ran; quote it." >&2
exit 2

#!/usr/bin/env bash
# specs-reminder.sh
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking. When a file under docs/specs/ (other than the revision-history file itself) is
# edited, emits hookSpecificOutput.additionalContext reminding Claude to update the revision
# history and sync the related PRD. Never blocks: always exit 0.
#
# Contract: reads the PostToolUse JSON payload on stdin. Structured output goes on stdout as JSON;
# exit 0 = allow (PostToolUse cannot un-do the tool call anyway).

# JSON extraction: jq preferred, perl (core JSON::PP) then python3 as fallbacks, because jq is not
# installed by default on macOS. The JSON we EMIT is a fixed literal, so it needs no jq at all.
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

payload=$(cat)
path=$(json_str tool_input.file_path)
[ -z "$path" ] && exit 0

norm=${path//\\//}
if printf '%s' "$norm" | grep -q 'docs/specs/' && ! printf '%s' "$norm" | grep -q '13-revision-history\.md$'; then
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"Reminder: you just edited docs/specs/. If this is a requirement change (not a typo/format fix), update docs/specs/13-revision-history.md and sync the related PRD in docs/requirements/."}}'
fi
exit 0

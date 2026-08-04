#!/usr/bin/env bash
# media-sync-reminder.sh - THIS REPO's own hook, not a shipped asset.
# Event: PostToolUse   Matcher: Edit|Write
# Non-blocking. When skill content changes (harness-bootstrap/, spec-builder/, docs/, README*),
# reminds the session that the presentation deck and the intro videos bake that content and must
# be re-checked - scripts/check_numbers.py guards the counts mechanically (it scans
# presentation/index.html and video/ too), but wording, flow diagrams, and slide claims only a
# read can verify. Never blocks: always exit 0.

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

case "$norm" in
  *harness-bootstrap/assets/*|*harness-bootstrap/SKILL.md|*harness-bootstrap/reference/*|*spec-builder/*|*docs/FLOWS.md|*docs/CONTEXT-MANAGEMENT.md|*README.md|*README.ja.md)
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"Skill content changed. The presentation (presentation/index.html, 3 languages) and the intro videos (video/src + rendered mp4/gif) bake this content - check them for drift before releasing. Counts are guarded by scripts/check_numbers.py; wording, diagrams, and slide claims need a read."}}'
    ;;
esac
exit 0

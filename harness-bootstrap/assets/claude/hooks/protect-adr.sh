#!/usr/bin/env bash
# protect-adr.sh
# Event: PreToolUse   Matcher: Edit|Write
# Blocks edits to ADRs whose on-disk status is "Accepted" (ADRs are immutable; a change means a
# NEW ADR that supersedes the old one).
#
# TIMING NOTE: the hook reads the ON-DISK (pre-edit) status, so the very edit that flips
# `proposed -> accepted` passes - it sees the OLD status - but every edit AFTER it is blocked,
# including fixing now-stale prose in the same file. Land all other edits FIRST and make the
# accept-flip its own final commit; after that the file is frozen.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow.

# JSON extraction: jq is preferred but is NOT installed by default on macOS, and a missing jq
# would make this hook silently fail OPEN. Fall back to perl (core JSON::PP - ships with macOS and
# every Linux), then python3. With no extractor at all we warn and allow; the settings.json deny
# rules remain the backstop. Never block on an unparseable payload.
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
  else
    echo "protect-adr: no jq/perl/python3 available to parse the hook payload; allowing." >&2
  fi
}

payload=$(cat)
path=$(json_str tool_input.file_path)
[ -z "$path" ] && exit 0

# Resolve against the payload's cwd so a relative file_path is checked against the right file
# (parity with the PowerShell flavor).
base=$(json_str cwd)
[ -z "$base" ] && base=$(pwd)
abs=${path//\\//}
case "$abs" in
  /*|[A-Za-z]:/*) ;;
  *) abs="${base//\\//}/$abs" ;;
esac

printf '%s' "$abs" | grep -Eq 'docs/architecture/decisions/ADR-[0-9]+[^/]*\.md$' || exit 0

if [ -f "$abs" ] && head -10 "$abs" | grep -Eq '^status:[[:space:]]*Accepted'; then
  echo "BLOCKED: this ADR has status Accepted and is immutable. Create a new ADR with /new-adr and mark the old one 'Superseded by ADR-NNN' (only the status line may change)." >&2
  exit 2
fi
exit 0

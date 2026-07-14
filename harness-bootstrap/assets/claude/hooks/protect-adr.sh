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


# Normalize a filesystem path so the hook resolves it on every shell it can plausibly run under.
#
# WHY THIS EXISTS: a bash on Windows cannot resolve a drive-letter path ("C:/x") in a file test - it
# reports "not found" with no error. In a security hook that means FAIL OPEN: the guard silently
# stops guarding. Worse, the three Windows bashes disagree about the mount prefix:
#     WSL         C:/x -> /mnt/c/x
#     git-bash    C:/x -> /c/x
#     MSYS2       C:/x -> /c/x
# so hardcoding either prefix breaks the other. We ask the platform's own converter first
# (wslpath / cygpath), and only probe as a last resort. On Linux and macOS there is no drive
# letter, so this is a no-op and costs nothing.
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
  # No converter available: pick whichever mount root actually exists.
  if [ -d "/mnt/$d" ]; then printf '/mnt/%s%s' "$d" "$rest"
  elif [ -d "/$d" ]; then printf '/%s%s' "$d" "$rest"
  else printf '%s' "$p"
  fi
}

payload=$(cat)
path=$(json_str tool_input.file_path)
[ -z "$path" ] && exit 0

# Resolve against the payload's cwd so a relative file_path is checked against the right file
# (parity with the PowerShell flavor).
base=$(norm_path "$(json_str cwd)")
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

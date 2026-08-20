#!/usr/bin/env bash
# protect-repos.sh
# Event: PreToolUse   Matcher: Edit|Write
# Layer 2 of the separation-of-duties enforcement for AUDIT workspaces: resolves the target path
# (relative paths against the payload's cwd, `..` collapsed, separators normalized) and blocks any
# Edit/Write inside a product repo dir. Audit agents are READ-ONLY on product source: they record
# findings under docs/findings/ and the user applies the fixes.
#
# CASE-SENSITIVITY NOTE: plain `[ "$a" = "$b" ]` and `case` patterns are case-SENSITIVE by default
# - exactly what this hook needs (the bash twin of PowerShell's -ceq); bash is only safe here BY
# DEFAULT, not by design. Do NOT rewrite with `grep -i`, and do not run under
# `shopt -s nocasematch` (it flips `case` and `[[ ]]` to case-insensitive): repo 'Backend' would
# then also match docs/findings/backend/... and block the agent's own finding writes.
#
# {{REPO_DIR_LIST}} = the repo dir names in EXACT on-disk casing, SPACE-SEPARATED,
# e.g. Repo-One repo-two. The settings.json deny globs and rules/agent-guardrails.md remain the
# backstop for exotic spellings.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow.

# JSON extraction: jq is preferred but is NOT installed by default on macOS, and a missing jq
# would make this hook silently fail OPEN - a read-only guard that permits every write. Fall back
# to perl (core JSON::PP - ships with macOS and every Linux), then python3.
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
    echo "protect-repos: no jq/perl/python3 available to parse the hook payload; allowing. Install jq - the settings.json deny rules are your only remaining read-only guard." >&2
  fi
}

payload=$(cat)
path=$(json_str tool_input.file_path)
[ -z "$path" ] && exit 0

base=$(json_str cwd)
[ -z "$base" ] && base=$(pwd)

case "$path" in
  /*|[A-Za-z]:/*) abs="$path" ;;
  *) abs="$base/$path" ;;
esac
abs=${abs//\\//}

if command -v realpath >/dev/null 2>&1; then
  norm=$(realpath -m "$abs" 2>/dev/null) || exit 0   # -m: target may not exist yet (Write); unparseable -> let deny globs decide
else
  dir=$(dirname "$abs"); file=$(basename "$abs")
  resolved=$(cd "$dir" 2>/dev/null && pwd -P) || exit 0   # unparseable path: let deny globs decide
  norm="$resolved/$file"
fi
norm=${norm//\\//}
norm=${norm%/}

root="{{WORKSPACE_ROOT}}"
root=${root//\\//}
root=${root%/}
repos="{{REPO_DIR_LIST}}"   # space-separated, EXACT on-disk casing

case "$norm" in
  "$root"/*)
    # Inside the workspace root: only the FIRST segment of the relative path can name a repo.
    # docs/findings/backend/... has first segment 'docs' -> passes even if a repo is 'Backend'.
    rel="${norm#"$root"/}"
    first="${rel%%/*}"
    for r in $repos; do
      if [ "$first" = "$r" ]; then
        echo "BLOCKED: '$norm' is inside product repo '$r'. This is a read-only audit workspace (separation of duties): agents never modify product source. Record a finding in docs/findings/ instead; the user applies fixes." >&2
        exit 2
      fi
    done
    ;;
  *)
    # Outside the workspace root (unexpected): conservative - block if ANY segment names a repo.
    # Do NOT set IFS=/ around these loops: a changed IFS also breaks the space-splitting of
    # $repos itself ('Backend CMS' stays one word and matches nothing - silently allow-all).
    hit=$(printf '%s\n' "$norm" | tr '/' '\n' | while IFS= read -r seg; do
      for r in $repos; do
        [ "$seg" = "$r" ] && { printf '%s' "$r"; exit 0; }
      done
    done)
    if [ -n "$hit" ]; then
      echo "BLOCKED: '$norm' contains product-repo dir '$hit'. Read-only audit workspace: agents never modify product source." >&2
      exit 2
    fi
    ;;
esac
exit 0

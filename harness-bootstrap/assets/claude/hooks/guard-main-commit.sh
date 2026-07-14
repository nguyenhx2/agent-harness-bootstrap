#!/usr/bin/env bash
# guard-main-commit.sh
# Event: PreToolUse   Matcher: Bash
# Blocks `git commit` / `git push` while the EFFECTIVE branch is {{DEFAULT_BRANCH}} or master.
# The effective branch is resolved from the command's actual target dir (a leading `cd <dir>` or
# `git -C <dir>`), falling back to the payload's `cwd`, so the hook does not misfire on git
# worktrees or on commands that operate on a sibling checkout.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown
# to Claude); exit 0 = allow.

# JSON extraction: jq is preferred but is NOT installed by default on macOS, and a missing jq
# would make this hook silently fail OPEN. Fall back to perl (core JSON::PP - ships with macOS and
# every Linux), then python3. With no extractor at all we warn and allow.
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
    echo "guard-main-commit: no jq/perl/python3 available to parse the hook payload; allowing." >&2
  fi
}

payload=$(cat)
cmd=$(json_str tool_input.command)
[ -z "$cmd" ] && exit 0

# POSIX ERE has no portable \b (BSD grep on macOS), so the trailing boundary is hand-rolled.
printf '%s' "$cmd" | grep -Eq '(^|[;&|][[:space:]]*)git[[:space:]]+(commit|push)([^a-zA-Z0-9_-]|$)' || exit 0

base_cwd=$(json_str cwd)
[ -z "$base_cwd" ] && base_cwd=$(pwd)
target_dir="$base_cwd"

# A leading `cd <dir>` wins over `git -C <dir>` (parity with the PowerShell flavor).
cd_dir=$(printf '%s' "$cmd" | grep -oE '(^|[;&|][[:space:]]*)cd[[:space:]]+("[^"]+"|'"'"'[^'"'"']+'"'"'|[^[:space:];&|]+)' | head -1 | sed -E 's/.*cd[[:space:]]+//; s/^["'"'"']//; s/["'"'"']$//')
gc_dir=$(printf '%s' "$cmd" | grep -oE 'git[[:space:]]+-C[[:space:]]+("[^"]+"|'"'"'[^'"'"']+'"'"'|[^[:space:]]+)' | head -1 | sed -E 's/.*-C[[:space:]]+//; s/^["'"'"']//; s/["'"'"']$//')
if [ -n "$cd_dir" ]; then
  target_dir="$cd_dir"
elif [ -n "$gc_dir" ]; then
  target_dir="$gc_dir"
fi

# Relative target dirs resolve against the payload cwd, not the hook process's cwd.
case "$target_dir" in
  /*|[A-Za-z]:/*) ;;
  *) target_dir="$base_cwd/$target_dir" ;;
esac

branch=$(git -C "$target_dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
[ -z "$branch" ] && branch=$(git -C "$base_cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
[ -z "$branch" ] && exit 0   # not a git repo (or git missing): nothing to guard

if [ "$branch" = "{{DEFAULT_BRANCH}}" ] || [ "$branch" = "master" ]; then
  echo "BLOCKED: effective branch is '$branch'. Per .claude/rules/git-workflow.md, do not commit/push directly to {{DEFAULT_BRANCH}}. Create a branch: git checkout -b feat/<slug> and commit again." >&2
  exit 2
fi
exit 0

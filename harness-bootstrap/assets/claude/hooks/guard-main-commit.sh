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
# json_fields fetches every field this hook needs in ONE parser invocation instead of one per
# field - see hooks/README.md. Sets array JF, same length as the arg list, in order.
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
  else
    echo "guard-main-commit: no jq/perl/python3 available to parse the hook payload; allowing." >&2
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
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
json_fields tool_input.command cwd
cmd="${JF[0]}"
[ -z "$cmd" ] && exit 0

# POSIX ERE has no portable \b (BSD grep on macOS), so the trailing boundary is hand-rolled.
printf '%s' "$cmd" | grep -Eq '(^|[^a-zA-Z0-9_.-])git[[:space:]]+(commit|push)([^a-zA-Z0-9_-]|$)' || exit 0

base_cwd=$(norm_path "${JF[1]}")
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

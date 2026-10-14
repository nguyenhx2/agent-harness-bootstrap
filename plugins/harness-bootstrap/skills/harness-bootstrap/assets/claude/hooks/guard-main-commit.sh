#!/usr/bin/env bash
# guard-main-commit.sh
# Event: PreToolUse   Matcher: Bash
# Enforces: .claude/rules/conventional-commits.md
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

# --- fast path: decide the common case with bash builtins only ---------------------------------
# This hook starts on every shell call, and on Windows each subshell or external process costs
# 50-250 ms: the JSON parser, every `printf | grep`, every `$(...)`. Most commands can never be
# blocked here, so that case is decided before any of them run. read_payload takes stdin without
# a fork; fast_str decodes one string field EXACTLY or gives up. A hook may only exit 0 on what
# these return, and only on a test that is a necessary condition of every block it raises; any
# doubt falls through to the full parse, which is unchanged. Copied verbatim into every hook that
# has a fast path - see "Latency" in hooks/README.md.
read_payload() {
  payload=
  # bash reads a pipe one byte per syscall: fine for a shell call's few hundred bytes, slower than
  # one `cat` past a few KB (an Edit or Write payload), so the rest of a long one goes to cat.
  if IFS= read -r -d '' -n 4096 payload; then
    payload+=$(cat)
  fi
}
# fast_str KEY -> FAST_STR. Fails unless the payload holds "KEY": exactly once, with a string value
# that is printable ASCII and uses no JSON escape but \" \\ \n \r \t - everything JSON.stringify
# writes for such text, so the decode is exact. Runs in the C locale: in a multibyte locale a lead
# byte could swallow the backslash of an escaped quote and end the value early.
fast_str() {
  local key=$1 s rest re re2 bs='\' q='"' had=${LC_ALL+x} old=${LC_ALL-} rc=1
  LC_ALL=C
  re="\"$key\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\""
  re2="\"$key\"[[:space:]]*:"
  if [[ $payload =~ $re ]]; then
    s=${BASH_REMATCH[1]}
    rest=${payload#*"$q$key$q"}
    rc=0
    [[ $rest =~ $re2 ]] && rc=1
    case $s in *[!\ -~]*) rc=1 ;; esac
    s=${s//"$bs$bs"/$'\001'}
    case $s in *"$bs"[!nrt\"]*|*"$bs") rc=1 ;; esac
    s=${s//"$bs$q"/"$q"}
    s=${s//"${bs}n"/$'\n'}
    s=${s//"${bs}r"/$'\r'}
    s=${s//"${bs}t"/$'\t'}
    FAST_STR=${s//$'\001'/"$bs"}
  fi
  if [ "$had" = x ]; then LC_ALL=$old; else unset LC_ALL; fi
  return $rc
}
# fast_unmatched ERE: true only when ERE was compiled and did not match FAST_STR (exit status 1).
# A regex the engine rejects (status 2) must never read as "no match".
fast_unmatched() {
  local had=${LC_ALL+x} old=${LC_ALL-} rc
  LC_ALL=C
  [[ $FAST_STR =~ $1 ]]
  rc=$?
  if [ "$had" = x ]; then LC_ALL=$old; else unset LC_ALL; fi
  [ "$rc" -eq 1 ]
}

read_payload
# The guard only acts on `git ... commit` or `git ... push`.
fast_str command && fast_unmatched '[Cc][Oo][Mm][Mm][Ii][Tt]|[Pp][Uu][Ss][Hh]' && exit 0
json_fields tool_input.command cwd
cmd="${JF[0]}"
[ -z "$cmd" ] && exit 0

# git GLOBAL options may sit between `git` and the subcommand - `git -c k=v commit`,
# `git -C . commit`, `git --no-pager commit`, `git --git-dir=.git commit`, `git --work-tree x push`.
# A pattern that required `git\s+commit` let every one of those through, and a live session
# committed to the default branch that way. GIT_PREFIX accepts any run of global options, with
# values bare, quoted, or carrying a quoted part (-c user.name="A B"). Same shape in the .ps1 twin.
SQ="'"
GIT_VAL="([^[:space:]\"${SQ}]*(\"[^\"]*\"|${SQ}[^${SQ}]*${SQ}))+[^[:space:]\"${SQ}]*|[^[:space:]]+"
GIT_OPT="-[cC][[:space:]]+(${GIT_VAL})|--(git-dir|work-tree|namespace|config-env)[[:space:]]+(${GIT_VAL})|--[a-z-]+=(${GIT_VAL})|-[^[:space:]]+"
GIT_PREFIX="(^|[^a-zA-Z0-9_.-])git([[:space:]]+(${GIT_OPT}))*[[:space:]]+"
# POSIX ERE has no portable \b (BSD grep on macOS), so the trailing boundary is hand-rolled.
GIT_RE="${GIT_PREFIX}(commit|push)([^a-zA-Z0-9_-]|\$)"
printf '%s' "$cmd" | grep -Eq -e "$GIT_RE" || exit 0
# The global options of THAT git invocation - never the subcommand's own arguments, where `-C`
# means something else (`git commit -C HEAD` reuses a message).
git_head=$(printf '%s' "$cmd" | grep -oE -e "$GIT_RE" | head -1)

base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)
target_dir="$base_cwd"

# A leading `cd <dir>` wins over `git -C <dir>` (parity with the PowerShell flavor).
cd_dir=$(printf '%s' "$cmd" | grep -oE '(^|[;&|][[:space:]]*)cd[[:space:]]+("[^"]+"|'"'"'[^'"'"']+'"'"'|[^[:space:];&|]+)' | head -1 | sed -E 's/.*cd[[:space:]]+//; s/^["'"'"']//; s/["'"'"']$//')
gc_dir=$(printf '%s' "$git_head" | grep -oE -e "[[:space:]]-C[[:space:]]+(${GIT_VAL})" | head -1 | sed -E 's/^[[:space:]]*-C[[:space:]]+//; s/^["'"'"']//; s/["'"'"']$//')
git_dir=$(printf '%s' "$git_head" | grep -oE -e "--git-dir(=|[[:space:]]+)(${GIT_VAL})" | head -1 | sed -E 's/^--git-dir(=|[[:space:]]+)//; s/^["'"'"']//; s/["'"'"']$//')
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

if [ -n "$git_dir" ]; then
  branch=$(git -C "$target_dir" --git-dir="$git_dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
else
  branch=$(git -C "$target_dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
fi
[ -z "$branch" ] && branch=$(git -C "$base_cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
[ -z "$branch" ] && exit 0   # not a git repo (or git missing): nothing to guard

if [ "$branch" = "{{DEFAULT_BRANCH}}" ] || [ "$branch" = "master" ]; then
  echo "BLOCKED: effective branch is '$branch'. Per .claude/rules/git-workflow.md, do not commit/push directly to {{DEFAULT_BRANCH}}. Create a branch: git checkout -b feat/<slug> and commit again." >&2
  exit 2
fi
exit 0

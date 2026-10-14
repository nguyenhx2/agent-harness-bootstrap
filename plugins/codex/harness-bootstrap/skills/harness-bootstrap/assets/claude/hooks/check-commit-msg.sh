#!/usr/bin/env bash
# check-commit-msg.sh
# Event: PreToolUse   Matcher: Bash
# Enforces: .claude/rules/conventional-commits.md
# Validates the subject line of `git commit -m "..."` against .claude/rules/conventional-commits.md.
# Skips editor-flow commits (no -m), `--amend --no-edit`, and Merge/Revert subjects.
#
# CASE-SENSITIVITY NOTE: grep -E is case-SENSITIVE by default - exactly what the lowercase checks
# below need (this is the bash twin of PowerShell's -cmatch/-cnotmatch). Never add -i to these.
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
    echo "check-commit-msg: no jq/perl/python3 available to parse the hook payload; allowing." >&2
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
# The guard only acts on `git ... commit`.
fast_str command && fast_unmatched '[Cc][Oo][Mm][Mm][Ii][Tt]' && exit 0
cmd=$(json_str tool_input.command)
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
printf '%s' "$cmd" | grep -Eq -e "${GIT_PREFIX}commit([^a-zA-Z0-9_-]|\$)" || exit 0
if printf '%s' "$cmd" | grep -q -- '--amend' && printf '%s' "$cmd" | grep -q -- '--no-edit'; then exit 0; fi

# AI-attribution trailers, checked FIRST and against the RAW command.
# Two reasons it cannot live further down with the other checks:
#   1. The trailer is a FOOTER, and the -m extraction below is line-oriented (sed reads line by
#      line), so $msg only ever holds the subject. Only $cmd sees the footer.
#   2. A multi-line -m message makes that extraction return empty, which trips the `exit 0` on the
#      editor-flow guard below - so any check placed after it never runs at all.
# The rule file forbids these trailers, but a rule is advisory; this is the layer that enforces.
# Rewriting history to strip one after the fact costs far more than refusing the commit now.
if printf '%s' "$cmd" | grep -Eqi 'co-authored-by:[^"]*(claude|anthropic|copilot|cursor)|generated with[^"]*(claude|anthropic)'; then
  echo "BLOCKED: remove the AI-attribution trailer (Co-Authored-By / 'Generated with')." >&2
  echo "See .claude/rules/conventional-commits.md - this repository does not attribute commits to tools." >&2
  exit 2
fi

# The subject is by definition the FIRST line of the message, so extraction runs against the
# first line of the command and does not require the closing quote to sit on it. The earlier
# version demanded a matching quote on the same line, so `git commit -m "bad subject<newline>
# <body>"` extracted nothing, fell through the editor-flow exit below, and skipped validation
# entirely - a one-newline bypass of the whole check, reachable by accident since multi-line
# messages are normal.
first=$(printf '%s' "$cmd" | head -1)
msg=$(printf '%s' "$first" | sed -nE 's/.*-m[[:space:]]+"([^"]*).*/\1/p')
[ -z "$msg" ] && msg=$(printf '%s' "$first" | sed -nE "s/.*-m[[:space:]]+'([^']*).*/\1/p")
[ -z "$msg" ] && exit 0   # editor flow / -F file: git's own hooks own that path

subject=$(printf '%s\n' "$msg" | head -1 | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')
printf '%s' "$subject" | grep -Eq '^(Merge|Revert)([^a-zA-Z0-9_-]|$)' && exit 0

types='{{COMMIT_TYPES}}'
problems=()

printf '%s' "$subject" | grep -Eq "^($types)(\([a-z0-9-]+\))?(!)?: [^[:space:]]" \
  || problems+=("subject must match '<type>(<scope>)?: <description>' with lowercase type in [$types]")
[ ${#subject} -gt 72 ] && problems+=("subject is ${#subject} chars (max 72)")
printf '%s' "$subject" | grep -Eq '\.[[:space:]]*$' && problems+=("subject must not end with a period")
printf '%s' "$subject" | grep -Eq '^[a-z]+(\([a-z0-9-]+\))?(!)?: [A-Z]' && problems+=("description starts uppercase - use lowercase")


if [ ${#problems[@]} -gt 0 ]; then
  echo "BLOCKED: commit message violates .claude/rules/conventional-commits.md:" >&2
  for p in "${problems[@]}"; do echo " - $p" >&2; done
  echo "Subject was: '$subject'. Example: feat(core): add health endpoint" >&2
  exit 2
fi
exit 0

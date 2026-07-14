#!/usr/bin/env bash
# check-commit-msg.sh
# Event: PreToolUse   Matcher: Bash
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

payload=$(cat)
cmd=$(json_str tool_input.command)
[ -z "$cmd" ] && exit 0

# POSIX ERE has no portable \b (BSD grep on macOS), so the trailing boundary is hand-rolled.
printf '%s' "$cmd" | grep -Eq '(^|[;&|][[:space:]]*)git[[:space:]]+commit([^a-zA-Z0-9_-]|$)' || exit 0
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

msg=$(printf '%s' "$cmd" | sed -nE 's/.*-m[[:space:]]+"([^"]*)".*/\1/p')
[ -z "$msg" ] && msg=$(printf '%s' "$cmd" | sed -nE "s/.*-m[[:space:]]+'([^']*)'.*/\1/p")
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

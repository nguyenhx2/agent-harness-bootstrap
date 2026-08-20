#!/usr/bin/env bash
# guard-no-ai-trailer.sh - THIS REPO's own hook, not a shipped asset.
# Event: PreToolUse   Matcher: Bash
#
# Refuses a `git commit` whose message carries AI attribution.
#
# `Co-Authored-By: Claude <noreply@anthropic.com>` is not a harmless footer: GitHub reads
# Co-Authored-By trailers and adds that identity to the repository's **Contributors** list, beside
# the people who own the work. Thirty-nine commits put it there before anyone noticed, and taking it
# back out meant rewriting every one of them and force-pushing a public branch. That is an expensive
# way to learn a one-line rule, so the rule is now a gate.
#
# The history records who is answerable for a change, and that is a person. Which tool helped is no
# more part of the record than which editor it was typed in.
#
# Blocking (exit 2). Only `git commit` is judged; everything else passes through.
set -u

payload=$(cat)

json_str() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$payload" | jq -r --arg k "$1" 'getpath($k | split(".")) // empty' 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$payload" | python3 -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for p in sys.argv[1].split("."):
    d = d.get(p) if isinstance(d, dict) else None
    if d is None: break
sys.stdout.write(d if isinstance(d, str) else "")' "$1" 2>/dev/null
  elif command -v perl >/dev/null 2>&1; then
    printf '%s' "$payload" | perl -0777 -MJSON::PP -e 'my $k=shift; local $/; my $d=eval{decode_json(<STDIN>)}; exit 0 unless $d; for my $p (split /\./,$k){ $d = (ref($d) eq "HASH") ? $d->{$p} : undef; last unless defined $d } print $d if defined $d && !ref $d' "$1" 2>/dev/null
  fi
}

cmd=$(json_str tool_input.command)
[ -z "$cmd" ] && exit 0

# `git commit` anywhere in a compound command, and `git tag -m` too - a tag message lands in the
# history just as permanently.
printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])git[[:space:]]+(commit|tag)([[:space:]]|$)' || exit 0

# The message may arrive as -m, as a heredoc feeding -F -, or as a file. All three are in this one
# string, so scan the whole command: a false positive here costs a rephrase, a miss costs a rewrite
# of the public history.
found=""
printf '%s' "$cmd" | grep -qiE 'co-authored-by:[[:space:]]*claude' && found="${found}Co-Authored-By: Claude, "
printf '%s' "$cmd" | grep -qiE 'claude-session:' && found="${found}Claude-Session:, "
printf '%s' "$cmd" | grep -qiE 'generated with (\[)?claude code' && found="${found}Generated with Claude Code, "
# Emoji, which invariant 8 bans from commit messages and which is how the generated footer is
# usually recognised. A bare `grep '<emoji>'` finds NOTHING here: under a UTF-8 locale grep treats
# the pattern as one character and fails to match the same bytes in the input. Matching bytes needs
# LC_ALL=C, and a codepoint scan catches every emoji rather than the one that was thought of.
if command -v python3 >/dev/null 2>&1; then
  printf '%s' "$cmd" | python3 -c 'import sys
text = sys.stdin.read()
ranges = ((0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF), (0xFE0F, 0xFE0F))
sys.exit(0 if any(any(lo <= ord(c) <= hi for lo, hi in ranges) for c in text) else 1)' \
    && found="${found}an emoji, "
else
  printf '%s' "$cmd" | LC_ALL=C grep -q $'\xf0\x9f\xa4\x96' && found="${found}an emoji, "
fi

[ -z "$found" ] && exit 0

printf 'BLOCKED: this commit message carries AI attribution (%s).\n\n' "${found%, }" >&2
printf 'See .claude/rules/repo-invariants.md section 7. Co-Authored-By is the one with teeth:\n' >&2
printf 'GitHub reads it and lists that identity under Contributors, beside the people who own\n' >&2
printf 'this work. Thirty-nine commits carried it before anyone noticed, and removing it meant\n' >&2
printf 'rewriting all of them and force-pushing a public branch.\n\n' >&2
printf 'Write the message without the trailer. The history records who is answerable for a\n' >&2
printf 'change; which tool helped is no more part of it than which editor was used.\n' >&2
exit 2

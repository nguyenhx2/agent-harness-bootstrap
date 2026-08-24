#!/usr/bin/env bash
# guard-task-scope.sh
# Event: PreToolUse   Matcher: Edit|Write
#
# Refuses to CREATE a task file that nobody asked for, or that is too small to be a task.
#
# The rule this enforces is in .claude/rules/task-tracking.md: a task is work the USER agreed to,
# tasks are few and large, and executing one never creates more. That rule was written first and
# was not enough - prose is what gets skipped under momentum, which is how a board ends up with a
# dozen rows for one agreed piece of work and the agreed work buried among them.
#
# Two things are checkable from the file itself, and this hook checks exactly those:
#
#   1. `requested_by:` names who asked. An agent cannot approve its own task, so an agent name is
#      refused, and so is a bare "user" - that is a claim, not a record of what was asked for.
#   2. At least two real acceptance criteria. A change with nothing observable to satisfy is a step
#      or a one-line fix, not a task.
#
# What it CANNOT check, stated plainly: whether the user really approved. Nothing in the payload
# proves that. What the field does is make the claim explicit and auditable in the file that
# outlives the session, the same way `attempts:` makes retry counts auditable. A reader six weeks
# later can see who a task came from, and a fabricated answer is a visible lie rather than an
# invisible omission.
#
# EDITING an existing task file is untouched. This fires on creation only.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (message on stderr, shown to
# Claude); exit 0 = allow. Never blocks on an unparseable payload - a hook that fails closed on its
# own blind spot gets switched off.
set -u
payload=$(cat)

json_get() {
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
  else
    echo "guard-task-scope: no jq/perl/python3 to parse the payload; allowing." >&2
  fi
}

path=$(json_get tool_input.file_path)
[ -z "$path" ] && exit 0
norm=$(printf '%s' "$path" | tr '\\' '/')

# A task file, anywhere on the board.
# Both shapes: the tool sends an absolute path, the eval and a hand-run send a repo-relative one.
# A pattern with only the leading `*/` silently matches neither of the relative ones, which is how
# this hook passed every direct test and failed every eval case.
case "$norm" in
  docs/tasks/*/TASK-*.md|*/docs/tasks/*/TASK-*.md) ;;
  *) exit 0 ;;
esac

# Creation only. An existing file is being edited, and editing a task is normal work.
[ -f "$path" ] && exit 0

body=$(json_get tool_input.content)
[ -z "$body" ] && body=$(json_get tool_input.new_string)
[ -z "$body" ] && exit 0

verdict=$(printf '%s' "$body" | python3 -c '
import re, sys
text = sys.stdin.read()

req = ""
m = re.search(r"(?mi)^requested_by:\s*(.*)$", text)
if m:
    req = m.group(1).strip().strip("\"" + "'"'"'")

problems = []
if not req:
    problems.append("`requested_by:` is missing. A task records who asked for it.")
elif req.startswith("<") or req.lower() in ("", "-", "tbd", "todo", "n/a"):
    problems.append("`requested_by:` is still the template placeholder.")
elif req.lower() in ("user", "the user", "agent", "orchestrator", "claude", "assistant"):
    problems.append(
        "`requested_by: " + req + "` is a label, not a record. Write what was actually asked for, "
        "or the issue it came from - an agent cannot approve its own task.")

# Acceptance criteria that are real: a checkbox with text that is not the template placeholder.
real = 0
for line in text.splitlines():
    s = line.strip()
    if not re.match(r"^[-*]\s*\[[ xX]\]\s*", s):
        continue
    rest = re.sub(r"^[-*]\s*\[[ xX]\]\s*", "", s).strip()
    if not rest or rest.startswith("<"):
        continue
    real += 1
if real < 2:
    problems.append(
        "only " + str(real) + " real acceptance criteria. Work with nothing observable to satisfy "
        "is a step inside a task, or a change small enough to just make.")

print("\n".join(problems))
' 2>/dev/null)

[ -z "$verdict" ] && exit 0

printf 'BLOCKED: this task file does not meet the bar for opening a task.\n\n' >&2
printf '%s\n\n' "$verdict" >&2
printf 'See .claude/rules/task-tracking.md. Tasks are few and large, and no agent opens one on its\n' >&2
printf 'own - that includes every subagent. If this came out of something you noticed while doing\n' >&2
printf 'something else: finish what you were given, report the finding, and let the user decide.\n' >&2
printf 'If it is smaller than the paperwork around it, just make the change.\n' >&2
exit 2

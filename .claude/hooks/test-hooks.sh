#!/usr/bin/env bash
# test-hooks.sh - proves THIS REPO's own hooks can still fire, and still let good work through.
#
# A hook that blocks nothing looks exactly like a repository with no violations: it exits 0 and
# everyone believes they are covered. This repo has found that failure in its own checks more than
# once (the 80-char gate that was born dead twice, the drift detector whose cache answered
# "identical" for a real edit), so a hook here ships with the payload that makes it fire.
#
# Both directions are tested for each hook. A guard that blocks everything is as broken as one that
# blocks nothing - it just gets switched off faster. Writing these caught two real defects on the
# first run: the stdlib guard matched `*/scripts/*.py` anywhere and so blocked the skill's own
# shipped assets, which are templates for other projects and may depend on anything; and the merge
# guard reported "no CI checks" for a PR it simply could not read.
#
#   bash .claude/hooks/test-hooks.sh
#
# Exit 0 = every hook behaves both ways round. Exit 1 = a hook is dead, or is blocking good work.
# The guard-pr-merge cases talk to GitHub through `gh`. Without auth they are skipped rather than
# failed, and the skip is printed - a silent skip would be worse than no test.
set -u
cd "$(dirname "$0")/../.." || exit 1

# Fixtures address THIS repository, because the stdlib guard anchors its match to the project root.
ROOT=${CLAUDE_PROJECT_DIR:-$PWD}
ROOT=${ROOT//\\//}
ROOT=${ROOT%/}

pass=0
fail=0
skip=0

# Keeping JSON assembly in one place is what stops this file becoming an exercise in shell quoting.
edit_payload() {  # edit_payload <tool> <path> <text> [key]
  python3 -c 'import json,sys
tool, path, text, key = sys.argv[1:5]
print(json.dumps({"tool_name": tool, "tool_input": {"file_path": path, key: text}}))' \
    "$1" "$2" "$3" "${4:-new_string}"
}

bash_payload() {  # bash_payload <command>
  python3 -c 'import json,sys
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))' "$1"
}

run() {  # run <label> <want-exit> <hook> <payload>
  local label="$1" want="$2" hook="$3" payload="$4" got out
  out=$(printf '%s' "$payload" | bash "$hook" 2>&1)
  got=$?
  if [ "$got" = "$want" ]; then
    pass=$((pass + 1))
    printf '  ok    %-50s (exit %s)\n' "$label" "$got"
  else
    fail=$((fail + 1))
    printf '  FAIL  %-50s want exit %s, got %s\n' "$label" "$want" "$got"
    printf '        %s\n' "$(printf '%s' "$out" | head -2)"
  fi
}

STDLIB=.claude/hooks/guard-stdlib-only.sh
MERGE=.claude/hooks/guard-pr-merge.sh
TRAILER=.claude/hooks/guard-no-ai-trailer.sh

echo "--- guard-stdlib-only blocks a dependency in a gate script ---"
run "the PR #18 edit: defusedxml into check_svg.py" 2 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/scripts/check_svg.py" 'import defusedxml.ElementTree as ET')"
run "requests, arriving through Write not Edit" 2 "$STDLIB" \
  "$(edit_payload Write "$ROOT/scripts/check_numbers.py" 'import requests' content)"
run "the from-import form" 2 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/eval/guardrail_eval.py" 'from yaml import safe_load')"
run "a dependency in benchmark/" 2 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/benchmark/benchmark.py" 'import numpy as np')"

echo "--- guard-stdlib-only lets legitimate work through ---"
run "a stdlib import" 0 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/scripts/check_svg.py" 'import xml.etree.ElementTree as ET')"
run "a dotted stdlib import" 0 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/scripts/check_js.py" 'import concurrent.futures')"
run "a module that lives in this repository" 0 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/scripts/check_numbers.py" 'from build_plugins import same_content')"
run "a relative import" 0 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/scripts/check_js.py" 'from .helpers import thing')"
run "an edit with no import in it" 0 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/scripts/check_js.py" 'JS_SOURCES = []')"
run "a SHIPPED ASSET, template for another project" 0 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/harness-bootstrap/assets/scripts/x.py" 'import requests')"
run "a vendored file under node_modules" 0 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/scripts/capture/node_modules/a/b.py" 'import requests')"
run "a file that is not Python" 0 "$STDLIB" \
  "$(edit_payload Edit "$ROOT/scripts/notes.md" 'import requests')"

echo "--- guard-no-ai-trailer keeps the history free of attribution ---"
run "Co-Authored-By: Claude - the Contributors-list one" 2 "$TRAILER"   "$(bash_payload 'git commit -m "fix: a thing

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"')"
run "a Claude-Session link" 2 "$TRAILER"   "$(bash_payload 'git commit -m "fix: a thing

Claude-Session: https://claude.ai/code/session_abc"')"
run "the Generated with Claude Code footer" 2 "$TRAILER"   "$(bash_payload 'git commit -m "docs: x

Generated with Claude Code"')"
run "a robot emoji in the message" 2 "$TRAILER"   "$(bash_payload 'git commit -m "docs: x 🤖"')"
run "the same trailer on a tag message" 2 "$TRAILER"   "$(bash_payload 'git tag -a v9.9.9 -m "v9.9.9

Co-Authored-By: Claude <x>"')"
run "an ordinary commit message" 0 "$TRAILER"   "$(bash_payload 'git commit -m "fix(scaffold): a line ending is not a conflict"')"
run "a commit mentioning Claude Code as a subject" 0 "$TRAILER"   "$(bash_payload 'git commit -m "docs: explain how Claude Code loads the rules"')"
run "not a commit at all" 0 "$TRAILER" "$(bash_payload 'git log --oneline -1')"

echo "--- guard-pr-merge judges only gh pr merge ---"
run "an unrelated command" 0 "$MERGE" "$(bash_payload 'git status')"
run "reading a PR is not merging one" 0 "$MERGE" "$(bash_payload 'gh pr view 18')"

if gh auth status >/dev/null 2>&1; then
  echo "--- guard-pr-merge against real pull requests ---"
  # #18 is the external contribution that arrived with no pipeline at all - the case this hook
  # exists for. #22 merged with eight green checks. Both are terminal, so neither answer can drift.
  run "PR #18: no CI checks at all -> refused" 2 "$MERGE" \
    "$(bash_payload 'gh pr merge 18 --squash')"
  run "a merge buried in a compound command is still one" 2 "$MERGE" \
    "$(bash_payload 'git fetch && gh pr merge 18 --squash')"
  run "PR #22: eight green checks -> allowed" 0 "$MERGE" \
    "$(bash_payload 'gh pr merge 22 --squash')"
  run "a PR that cannot be read -> cannot judge, allowed" 0 "$MERGE" \
    "$(bash_payload 'gh pr merge 999999 --squash')"
else
  skip=$((skip + 4))
  echo "  SKIP  4 guard-pr-merge cases: gh is not authenticated, so GitHub was not consulted."
fi

echo
printf '  passed=%s failed=%s skipped=%s\n' "$pass" "$fail" "$skip"
[ "$fail" -eq 0 ] || exit 1

#!/usr/bin/env bash
# guard-pr-merge.sh - THIS REPO's own hook, not a shipped asset.
# Event: PreToolUse   Matcher: Bash
#
# Refuses `gh pr merge` when the pull request has no green CI.
#
# The case that motivated it: PR #18 arrived from an automated security scanner with a confident
# HIGH-severity CWE, a tidy diff, and - reported by `gh pr checks` - "no checks reported on the
# branch". Not a failing pipeline. No pipeline at all. A PR that has never been built is not a
# reviewed PR, however plausible its description reads, and the description is exactly the part an
# automated contribution is best at.
#
# Two states are refused and they are different failures:
#   - a check that FAILED       -> the work is not ready
#   - no checks reported at all -> nothing has been verified, and a green review is an illusion
#
# Blocking (exit 2). Anything that is not a `gh pr merge` passes straight through, and a merge of a
# PR whose checks are all SUCCESS or SKIPPED passes too.
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

# `gh pr merge`, with any amount of whitespace between the words and anywhere in a compound
# command, so `cd x && gh  pr  merge 5` is caught the same as a bare invocation.
printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)' || exit 0

# The PR number is the first bare integer after `merge`. `gh pr merge` with no number means "the
# PR for the current branch"; ask gh which one that is rather than guessing.
pr=$(printf '%s' "$cmd" | sed -nE 's/.*gh[[:space:]]+pr[[:space:]]+merge[[:space:]]+([0-9]+).*/\1/p')
if [ -z "$pr" ]; then
  pr=$(gh pr view --json number --jq .number 2>/dev/null)
fi
if [ -z "$pr" ]; then
  # Cannot identify the PR, so cannot judge it. Say so and allow: a hook that blocks on its own
  # blind spot trains people to disable it.
  printf 'guard-pr-merge: could not work out which PR this merges, so its CI was not checked.\n' >&2
  exit 0
fi

# One call, because "this PR has no checks" and "I could not reach this PR" have to be told apart
# and `gh pr checks` reports both as empty output. They are opposite situations: the first is a
# reason to refuse, the second is this hook's own blind spot, and conflating them means a network
# blip or an expired token blocks a legitimate merge behind a message about CI that is simply
# untrue. `gh pr view --json statusCheckRollup` fails loudly when the PR cannot be read and returns
# an explicit (possibly empty) array when it can.
#
# Note `--json number` alone is NOT a usable existence check: gh answers `{"number":999999}` with
# exit 0 for a PR that does not exist. Asking for a field it must actually fetch is what makes the
# failure real.
rollup=$(gh pr view "$pr" --json number,statusCheckRollup 2>/dev/null)
if [ -z "$rollup" ]; then
  printf 'guard-pr-merge: could not read PR #%s (missing, or gh is not authenticated), so its CI\n' "$pr" >&2
  printf 'was not checked. Verify it yourself before merging.\n' >&2
  exit 0
fi

checks=$(printf '%s' "$rollup" | python3 -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
print(json.dumps(d.get("statusCheckRollup") or []))' 2>/dev/null)
if [ -z "$checks" ] || [ "$checks" = "[]" ]; then
  printf 'BLOCKED: PR #%s has no CI checks at all.\n\n' "$pr" >&2
  printf 'Not a failing pipeline - no pipeline. Nothing about this branch has been built or tested,\n' >&2
  printf 'so merging it is trusting the description. That is exactly how PR #18 read: a confident\n' >&2
  printf 'HIGH-severity CWE, a one-line diff, zero checks, and a claim that did not survive being\n' >&2
  printf 'tested against the actual parser.\n\n' >&2
  printf 'Push the branch so the workflows run, or reproduce the claim locally and record what you\n' >&2
  printf 'found in a comment on the PR before merging.\n' >&2
  exit 2
fi

# A rollup row is either a CheckRun (conclusion, may be null while running) or a StatusContext
# (state). Read whichever it carries; a row with neither is treated as not-green, because an
# unreadable check is not a passed one.
bad=$(printf '%s' "$checks" | python3 -c 'import json,sys
try: rows = json.load(sys.stdin)
except Exception: sys.exit(0)
out = []
for r in rows:
    verdict = str(r.get("conclusion") or r.get("state") or "PENDING").upper()
    if verdict not in ("SUCCESS", "SKIPPED", "NEUTRAL"):
        out.append("  %s  %s" % (verdict, r.get("name") or r.get("context") or "?"))
print("\n".join(out))' 2>/dev/null)

if [ -n "$bad" ]; then
  printf 'BLOCKED: PR #%s has checks that are not green:\n%s\n\n' "$pr" "$bad" >&2
  printf 'A pending check is not a green check. Wait for a terminal state, then merge.\n' >&2
  exit 2
fi

exit 0

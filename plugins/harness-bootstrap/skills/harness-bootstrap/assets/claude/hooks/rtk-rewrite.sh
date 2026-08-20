#!/usr/bin/env bash
# rtk-rewrite.sh
# Event: PreToolUse   Matcher: Bash
# OPTIONAL, ships only with the `rtk` flag. Offers a Bash command to rtk
# (https://github.com/rtk-ai/rtk, Apache-2.0), which rewrites it into a form whose OUTPUT is
# smaller: `git status` becomes `rtk git status`, same information, fewer tokens back. Measured
# on rtk's own repo: `git log -30` 17,653 chars to 6,380.
#
# WHY A WRAPPER INSTEAD OF REGISTERING `rtk hook claude` DIRECTLY. Three reasons, all load-bearing:
#   1. /harness-toggle resolves a hook to .claude/hooks/<name>.{sh,ps1}. A bare binary
#      registration has no file, so it could never be disabled through the sanctioned path.
#   2. The eval can fire payloads at a file. It cannot fire them at someone else's binary.
#   3. It puts a boundary we own between a third-party binary and the tool call, which is the
#      whole premise of this harness.
#
# THE PASS-THROUGH RULE, and it is the point of this file. A command that any of our own guards
# inspects is NEVER handed to rtk - it is passed through untouched. rtk rewrites `git commit -m x`
# into `rtk git commit -m x` (verified), and while check-commit-msg's anchor now tolerates a
# wrapper prefix, a compressor must never be the reason a guard did not fire. Pass-through is
# always safe: no rewrite means the original command, which is what would have happened anyway.
#
# TRUST SURFACE WORTH KNOWING ABOUT: rtk reads .rtk/filters.toml from the repo, and a filter file
# can change what command output the model sees. rtk itself treats an untrusted one as hostile and
# skips it (its own docs describe hiding malicious code or suppressing scanner output as the
# threat). The generated .gitignore ignores .rtk/ so a local config never travels by accident.
#
# NETWORK: rtk has a telemetry endpoint compiled in. It is gated on explicit consent that defaults
# to off, and settings.json sets RTK_TELEMETRY_DISABLED=1 as a second lock. This is a NAMED
# relaxation of the no-network-in-hooks rule - see hooks/README.md.
#
# Contract: reads the PreToolUse JSON payload on stdin. Always exit 0 - this hook never blocks.
# On stdout: either rtk's hookSpecificOutput JSON, or nothing at all (meaning "no rewrite").

MIN_VERSION="0.45.0"

payload=$(cat)
[ -z "$payload" ] && exit 0

# rtk absent is the normal case: the flag ships the hook, the user installs the binary separately.
# Silence matters here - a nag on every Bash call would be worse than the tokens it saves.
command -v rtk >/dev/null 2>&1 || exit 0

# Version gate. Below the pinned minimum the payload contract is not one we tested against, so we
# do nothing rather than guess. `sort -V` is the portable comparison; if it is unavailable we
# decline rather than assume.
rtk_ver=$(rtk --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
[ -z "$rtk_ver" ] && exit 0
if command -v sort >/dev/null 2>&1; then
  lowest=$(printf '%s\n%s\n' "$MIN_VERSION" "$rtk_ver" | sort -V 2>/dev/null | head -1)
  [ "$lowest" = "$MIN_VERSION" ] || exit 0
else
  exit 0
fi

# --- extract the command --------------------------------------------------------------------
# Same jq -> perl -> python3 fallback chain as every other hook here. With no extractor at all we
# decline: we cannot see what the command is, so we cannot know it is safe to rewrite.
extract_command() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null
  elif command -v perl >/dev/null 2>&1; then
    printf '%s' "$payload" | perl -0777 -MJSON::PP -e '
      local $/; my $d = eval { decode_json(<STDIN>) };
      my $v = $d && ref($d->{tool_input}) eq "HASH" ? $d->{tool_input}{command} : undef;
      print((defined $v && !ref $v) ? $v : "");
    ' 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$payload" | python3 -c '
import json, sys
try: d = json.load(sys.stdin)
except Exception: d = None
ti = d.get("tool_input") if isinstance(d, dict) else None
c = ti.get("command") if isinstance(ti, dict) else None
sys.stdout.write(c if isinstance(c, str) else "")
' 2>/dev/null
  fi
}

cmd=$(extract_command)
[ -z "$cmd" ] && exit 0

# --- the pass-through rule ------------------------------------------------------------------
# GUARDED_GIT mirrors guard-main-commit.sh's anchor character for character. GUARDED_ENV mirrors
# protect-secrets.sh's cmd_pattern, deliberately WITHOUT that hook's scrubs: protect-secrets
# subtracts the legitimate forms because it must allow them, whereas here the conservative answer
# to "does this command mention a .env file at all" is simply not to touch it.
# If either hook's matcher changes, change the twin here - a drift means a guarded command
# reaching rtk.
GUARDED_GIT='(^|[^a-zA-Z0-9_.-])git[[:space:]]+(commit|push)([^a-zA-Z0-9_-]|$)'
GUARDED_ENV='(^|[^a-zA-Z0-9_./-])[^[:space:]]*\.env(\.[a-zA-Z0-9_-]+)?([[:space:]]|$|"|'"'"'|;|&)'

if printf '%s' "$cmd" | grep -Eq "$GUARDED_GIT"; then exit 0; fi
if printf '%s' "$cmd" | grep -Eqi "$GUARDED_ENV"; then exit 0; fi

# --- hand it to rtk -------------------------------------------------------------------------
# stderr is discarded: rtk writes an install nag there, and anything on our stderr would reach
# the model as if this hook had something to say. stdout is relayed verbatim, so the rewrite
# contract stays rtk's to define rather than something we re-encode and get wrong.
out=$(printf '%s' "$payload" | rtk hook claude 2>/dev/null)
rc=$?
[ "$rc" -ne 0 ] && exit 0
[ -n "$out" ] && printf '%s' "$out"
exit 0

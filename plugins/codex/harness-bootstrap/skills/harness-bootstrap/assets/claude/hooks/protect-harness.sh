#!/usr/bin/env bash
# protect-harness.sh
# Event: PreToolUse   Matcher: Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell
# Flag: none - ships with every harness
# Enforces: .claude/rules/agent-guardrails.md
# Guards the files that enforce the harness itself: .claude/settings.json,
# .claude/settings.local.json, and anything under .claude/hooks/ (a hook, the spawn allowlist,
# the egress allowlist). Every other guard is only as strong as these files: an agent that turns
# protect-secrets.sh into `exit 0`, or drops a line from permissions.deny, has switched the guard
# off without anyone deciding to.
#   - An Edit or Write there ASKS THE USER (permissionDecision "ask"). Changing them is real work -
#     /harness-tune edits the deny list and the spawn allowlist - so a person decides.
#   - A shell command that WRITES there is BLOCKED (exit 2). Nothing in the harness edits these
#     files through the shell, and a shell write is how a change would slip past the edit prompt:
#     verified live, an "ask" is waved through in bypassPermissions mode, an exit 2 is not.
# A deliberate switch-off has its own recorded path, /harness-toggle, which runs a script and
# never meets this hook. Shell writes are matched best-effort: the path together with a writing
# verb or a redirect. A command that only reads them (cat, git diff) passes.
#
# PARITY CONTRACT: protect-harness.sh and protect-harness.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the PreToolUse JSON payload on stdin. Ask = a JSON decision on stdout and exit
# 0; block = exit 2 with the reason on stderr; allow = exit 0 with no output.

# JSON extraction: jq is preferred but is NOT installed by default on macOS, and a missing jq
# would make this hook silently fail OPEN - a security hook that allows everything. Fall back to
# perl (core JSON::PP - ships with macOS and every Linux), then python3. With no extractor at all
# we warn loudly and allow; the settings.json deny rules remain the backstop.
#
# json_fields fetches every field this hook needs in ONE parser invocation instead of one per
# field: jq's startup is a few ms, cheap enough that its branch below still does one call per
# field, but perl/python3 process startup is the dominant cost of the whole hook (tens to
# hundreds of ms - see hooks/README.md), and that cost was being paid twice per invocation here.
# Sets the array JF, one slot per requested key, always the same length as the argument list.
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
    echo "protect-secrets: no jq/perl/python3 available to parse the hook payload; allowing. Install jq - the settings.json deny rules are your only remaining secret guard." >&2
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
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
# Case-insensitive throughout, as PowerShell -match is: on Windows and macOS `.Claude/Settings.json`
# is the same file, and PowerShell reads `set-content` as Set-Content.
shopt -s nocasematch
# Every ask below needs `.claude/settings` or `.claude/hooks` in the payload, in either slash.
case $payload in
  *.claude/settings*|*.claude/hooks*|*'.claude\\settings'*|*'.claude\\hooks'*) ;;
  *) exit 0 ;;
esac
json_fields tool_input.file_path tool_input.notebook_path tool_input.command
path="${JF[0]:-${JF[1]}}"
cmd="${JF[2]}"

ask() {
  local why=$1
  why=${why//\\/\\\\}
  why=${why//\"/\\\"}
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"%s"}}\n' "$why"
  exit 0
}

protected_re='(^|/)\.claude/(settings(\.local)?\.json$|hooks/)'
if [ -n "$path" ]; then
  norm=${path//\\//}
  if [[ $norm =~ $protected_re ]]; then
    ask "protect-harness: $norm enforces the harness. An agent edit here can switch a guard off, so a person decides. To disable a control on purpose, use /harness-toggle instead."
  fi
fi

if [ -n "$cmd" ]; then
  c=${cmd//\\//}
  if [[ $c =~ \.claude/(settings(\.local)?\.json|hooks/) ]]; then
    write_re='(>|(^|[^a-zA-Z0-9_-])(sed[[:space:]]+-i|tee|cp|mv|rm|truncate|chmod|ln|install|dd|perl|python3?|node|ruby|Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item|ri|del|move|copy)([^a-zA-Z0-9_-]|$))'
    if [[ $c =~ $write_re ]]; then
      echo "BLOCKED by protect-harness: this command writes to a file that enforces the harness (.claude/settings or .claude/hooks). Change it with the Edit tool, which asks the user, or switch a control off on purpose with /harness-toggle." >&2
      exit 2
    fi
  fi
fi
exit 0

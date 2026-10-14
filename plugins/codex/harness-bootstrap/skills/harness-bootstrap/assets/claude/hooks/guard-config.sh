#!/usr/bin/env bash
# guard-config.sh
# Event: ConfigChange   Matcher: user_settings|project_settings|local_settings
# Flag: hooks_strict
# Enforces: .claude/rules/agent-guardrails.md (the guardrails cannot be switched off mid-session)
# BLOCKS (exit 2) a settings change, made while a session runs, that weakens the harness:
#   - "disableAllHooks": true
#   - permissions.defaultMode "bypassPermissions"
#   - an allow rule that pre-approves any command: Bash or PowerShell bare, a specifier made only
#     of wildcards and colons (Bash(*), Bash(**), Bash(*:*), Bash( *)), or a shell or wrapper
#     launched by name (Bash(bash:*), Bash(sh -c:*), Bash(pwsh:*), Bash(env:*), ...)
#   - a permissions.deny list that lost a rule, compared with the deny list this hook last
#     accepted for that settings source (first time: the committed HEAD version of project
#     settings). Snapshots live in .claude/state/config-guard/.
#   - project settings that no longer register a hook still installed in .claude/hooks/ - the
#     shape of a guard silenced by deleting its registration instead of through /harness-toggle
#     (which moves the file out and drops the registration together, and so passes this check)
#   - deleting .claude/settings.json outright
# A blocked change is not applied to the RUNNING session. It is still on disk, so the next session
# loads it: this guard stops an agent - or a prompt injection driving one - from switching off its
# own guardrails mid-task, and a person who really means the change restarts the session.
#
# WHY BLOCK: each of these removes a guard while the work that guard watches is in progress.
# Claude Code surfaces a blocked ConfigChange to nobody - only a debug-log line - so every refusal
# is also appended to .claude/state/config-guard.log with the reason. Skill files and managed
# policy are out of scope (managed policy cannot be blocked anyway).
#
# PARITY CONTRACT: guard-config.sh and guard-config.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the ConfigChange JSON payload on stdin (source, file_path, cwd). exit 2 = block
# the change; exit 0 = allow. Fails OPEN on an unreadable payload or an unparseable settings file.

json_fields() {
  local keys=("$@")
  JF=()
  if command -v jq >/dev/null 2>&1; then
    local k
    for k in "${keys[@]}"; do
      JF+=("$(printf '%s' "$payload" | jq -r --arg k "$k" 'getpath($k | split(".")) | if type == "string" or type == "boolean" or type == "number" then tostring else empty end' 2>/dev/null)")
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
          my $o = "";
          if (defined $v) {
            if (ref($v) eq "JSON::PP::Boolean") { $o = $v ? "true" : "false"; }
            elsif (!ref $v) { $o = $v; }
          }
          print($o . "\0");
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
    if isinstance(v, bool): out.append("true" if v else "false")
    elif isinstance(v, (str, int, float)): out.append(str(v))
    else: out.append("")
sys.stdout.write("\0".join(out) + "\0")
' "${keys[@]}" 2>/dev/null
    )
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
}

# settings_facts FILE -> lines "disableAllHooks=<true|false>", "defaultMode=<mode>",
# "allow=<entry>" and "deny=<entry>" (one per rule). Prints "unparseable" if the file is not JSON.
settings_facts() {
  if command -v jq >/dev/null 2>&1; then
    jq -r '"disableAllHooks=" + ((.disableAllHooks // false) | tostring),
           "defaultMode=" + ((.permissions.defaultMode // "") | tostring),
           ((.permissions.allow // [])[] | "allow=" + tostring),
           ((.permissions.deny // [])[] | "deny=" + tostring)' "$1" 2>/dev/null || echo unparseable
  elif command -v perl >/dev/null 2>&1; then
    perl -0777 -MJSON::PP -e '
      local $/; open(my $fh, "<", $ARGV[0]) or do { print "unparseable\n"; exit 0 };
      my $d = eval { decode_json(<$fh>) };
      if (ref($d) ne "HASH") { print "unparseable\n"; exit 0 }
      my $off = $d->{disableAllHooks};
      print "disableAllHooks=" . ((ref($off) eq "JSON::PP::Boolean" && $off) ? "true" : "false") . "\n";
      my $p = ref($d->{permissions}) eq "HASH" ? $d->{permissions} : {};
      print "defaultMode=" . (defined $p->{defaultMode} && !ref $p->{defaultMode} ? $p->{defaultMode} : "") . "\n";
      if (ref($p->{allow}) eq "ARRAY") { for (@{$p->{allow}}) { print "allow=$_\n" unless ref } }
      if (ref($p->{deny}) eq "ARRAY") { for (@{$p->{deny}}) { print "deny=$_\n" unless ref } }
    ' "$1" 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    assert isinstance(d, dict)
except Exception:
    print("unparseable"); sys.exit(0)
print("disableAllHooks=" + ("true" if d.get("disableAllHooks") is True else "false"))
p = d.get("permissions") if isinstance(d.get("permissions"), dict) else {}
m = p.get("defaultMode")
print("defaultMode=" + (m if isinstance(m, str) else ""))
for a in p.get("allow") or []:
    if isinstance(a, str): print("allow=" + a)
for a in p.get("deny") or []:
    if isinstance(a, str): print("deny=" + a)
' "$1" 2>/dev/null
  else
    echo unparseable
  fi
}

# Copied verbatim from guard-agent-spawn.sh.
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
  if [ -d "/mnt/$d" ]; then printf '/mnt/%s%s' "$d" "$rest"
  elif [ -d "/$d" ]; then printf '/%s%s' "$d" "$rest"
  else printf '%s' "$p"
  fi
}

# unrestricted_shell RULE -> 0 when an allow rule pre-approves ANY command: Bash / PowerShell
# bare, a specifier that is only wildcards and colons once spaces are dropped (*, **, :*, *:*,
# " *"), or one whose command is itself a shell or a run-anything wrapper (bash:*, sh -c:*,
# pwsh:*, env:*, sudo:*, xargs:*). Interpreters such as python are not listed: allowing them is
# common and deliberate, and the rule names them for what they are.
unrestricted_shell() {
  local e=$1 inner flat first
  case "$e" in
    Bash|PowerShell) return 0 ;;
    "Bash("*")"|"PowerShell("*")") inner=${e#*\(}; inner=${inner%\)} ;;
    *) return 1 ;;
  esac
  flat=$(printf '%s' "$inner" | tr -d ' \t')
  case "$flat" in ''|*[!*:]*) ;; *) return 0 ;; esac
  first=$(printf '%s' "$inner" | sed -E 's/^[[:space:]]+//; s/[[:space:]:].*$//' | tr 'A-Z' 'a-z')
  first=${first%.exe}
  case "$first" in
    bash|sh|zsh|dash|ksh|fish|pwsh|powershell|cmd|env|eval|exec|sudo|xargs|nohup) return 0 ;;
  esac
  return 1
}

payload=$(cat)
json_fields source file_path cwd
src="${JF[0]}"
base_cwd=$(norm_path "${JF[2]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)

case "$src" in
  user_settings|project_settings|local_settings) ;;
  *) exit 0 ;;
esac

file="${JF[1]}"
if [ -z "$file" ]; then
  case "$src" in
    project_settings) file="$base_cwd/.claude/settings.json" ;;
    local_settings) file="$base_cwd/.claude/settings.local.json" ;;
    *) exit 0 ;;
  esac
else
  file=$(norm_path "$file")
fi

refuse() {
  local why=$1 log="$base_cwd/.claude/state/config-guard.log"
  if [ -d "$base_cwd/.claude" ]; then
    mkdir -p "${log%/*}" 2>/dev/null
    printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" "$src" "$why" >> "$log" 2>/dev/null
  fi
  echo "BLOCKED by guard-config: $why The change was not applied to this session (it is still on disk, so a new session would load it). Disable a hook with /harness-toggle; change permissions deliberately, between sessions." >&2
  exit 2
}

if [ ! -f "$file" ]; then
  [ "$src" = "project_settings" ] && refuse ".claude/settings.json was deleted, which unregisters every hook."
  exit 0
fi

facts=$(settings_facts "$file")
printf '%s\n' "$facts" | grep -qx 'unparseable' && exit 0
printf '%s\n' "$facts" | grep -qx 'disableAllHooks=true' && refuse "disableAllHooks: true switches off every guardrail hook."
printf '%s\n' "$facts" | grep -qx 'defaultMode=bypassPermissions' && refuse "defaultMode bypassPermissions removes every permission prompt."
while IFS= read -r rule; do
  [ -n "$rule" ] || continue
  unrestricted_shell "$rule" && refuse "the allow rule '$rule' pre-approves every command (a bare wildcard, or a shell or wrapper launched by name)."
done <<< "$(printf '%s\n' "$facts" | sed -n 's/^allow=//p')"

# A deny list only grows mid-session. Baseline: the deny list this hook last accepted for this
# source, else (project settings) the one committed at HEAD. Nothing to compare -> nothing to say.
state_dir="$base_cwd/.claude/state/config-guard"
snap="$state_dir/$src.deny"
new_deny=$(printf '%s\n' "$facts" | sed -n 's/^deny=//p' | tr -d '\r' | sort -u)
baseline=""
if [ -f "$snap" ]; then
  baseline=$(tr -d '\r' < "$snap" | sort -u)
elif [ "$src" = "project_settings" ] && command -v git >/dev/null 2>&1; then
  rel=${file#"$base_cwd"/}
  if [ "$rel" != "$file" ] && mkdir -p "$state_dir" 2>/dev/null; then
    head_copy="$state_dir/.head-settings.json"
    if git -C "$base_cwd" show "HEAD:$rel" > "$head_copy" 2>/dev/null; then
      baseline=$(settings_facts "$head_copy" | sed -n 's/^deny=//p' | tr -d '\r' | sort -u)
    fi
    rm -f "$head_copy" 2>/dev/null
  fi
fi
if [ -n "$baseline" ]; then
  lost=0; first=""
  while IFS= read -r rule; do
    [ -n "$rule" ] || continue
    if ! printf '%s\n' "$new_deny" | grep -Fqx -- "$rule"; then
      lost=$((lost + 1)); [ -z "$first" ] && first=$rule
    fi
  done <<< "$baseline"
  [ "$lost" -gt 0 ] && refuse "permissions.deny lost $lost rule(s), for example '$first'. A deny list only grows while a session runs."
fi

if [ "$src" = "project_settings" ] && [ -d "$base_cwd/.claude/hooks" ]; then
  for f in "$base_cwd"/.claude/hooks/*.sh "$base_cwd"/.claude/hooks/*.ps1; do
    [ -f "$f" ] || continue
    stem=${f##*/}; stem=${stem%.*}
    if ! grep -q "hooks/$stem\." "$file" 2>/dev/null; then
      refuse "hook $stem is still installed in .claude/hooks/ but no longer registered in settings.json."
    fi
  done
fi
# Accepted: this deny list is the baseline the next change is compared against.
if [ -d "$base_cwd/.claude" ] && mkdir -p "$state_dir" 2>/dev/null; then
  printf '%s\n' "$new_deny" > "$snap" 2>/dev/null
fi
exit 0

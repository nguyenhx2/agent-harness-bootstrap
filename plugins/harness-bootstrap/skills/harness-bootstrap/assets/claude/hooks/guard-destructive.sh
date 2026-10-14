#!/usr/bin/env bash
# guard-destructive.sh
# Event: PreToolUse   Matcher: Bash|PowerShell
# Flag: none - ships with every harness (the deny rules alone are prefix matches)
# Enforces: .claude/rules/agent-guardrails.md
# BLOCKS (exit 2) shell commands whose damage cannot be undone from inside the session:
#   1. rm with recursive+force on the repo root, the home dir, `/`, a top-level system dir, a
#      drive root or a top-level folder on a drive, `.`/`..`/`*`, or `.git` (and anything with
#      --no-preserve-root); the same targets for PowerShell's Remove-Item / ri / rd / rmdir / del /
#      erase with -Recurse (any abbreviation; -Force is not needed to delete a tree) and cmd's /s
#   2. a force push (--force, -f, --force-with-lease, or a `+refspec`) to {{DEFAULT_BRANCH}},
#      main, master, production, prod or release/* - explicit refspec or, failing that, the
#      branch currently checked out (--all / --mirror count as protected)
#   3. git reset --hard; git clean with force AND -x/-X (deletes ignored files: local env files,
#      local databases); `git checkout .` / `git restore .` (discards every uncommitted change)
#   4. DROP TABLE|DATABASE|SCHEMA or TRUNCATE sent to a host that is not local
#
# WHY BLOCK, NOT WARN: every one of these destroys work or data that the session cannot get back,
# and a warning is read after the fact. The settings.json deny rules cover only the literal
# prefix form (`Bash(rm -rf:*)`); `cd x && rm -rf .`, `env git push -f` and `git push origin main
# --force` all walk past a prefix rule. This hook closes that gap. Everything ordinary - `rm -rf
# node_modules`, a force push to your own feature branch, `git reset --soft`, a DROP against
# localhost - is allowed, because a guard that blocks the work gets switched off.
#
# PARITY CONTRACT: guard-destructive.sh and guard-destructive.ps1 must stay behaviorally
# EQUIVALENT - same segment splitting, same targets, same protected branches, same hosts.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (reason on stderr, shown
# to Claude); exit 0 = allow. Fails OPEN on an unreadable payload.

# json_fields KEY... -> array JF, one slot per key, same order. Strings verbatim, booleans as
# true/false, numbers as text, anything else empty. jq -> perl (core JSON::PP) -> python3.
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
  else
    echo "guard-destructive: no jq/perl/python3 available to parse the hook payload; allowing. The settings.json deny rules remain the backstop." >&2
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
}

# A bash on Windows cannot always resolve a `C:/x` cwd. Copied verbatim from guard-agent-spawn.sh.
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

block() {
  echo "BLOCKED by guard-destructive: $1" >&2
  exit 2
}

unquote() {
  local t=$1
  t=${t#\"}; t=${t%\"}; t=${t#\'}; t=${t%\'}
  printf '%s' "$t"
}

payload=$(cat)
json_fields tool_input.command cwd
cmd="${JF[0]}"
raw_cwd="${JF[1]}"
[ -z "$cmd" ] && exit 0
cwd_posix=$(printf '%s' "$raw_cwd" | tr '\\' '/')
cwd_posix=${cwd_posix%/}
base_cwd=$(norm_path "$raw_cwd")
[ -z "$base_cwd" ] && base_cwd=$(pwd)

# --- target classification for rm ----------------------------------------------------------
is_danger_target() {
  local t b
  t=$(unquote "$1" | tr '\\' '/')
  b=${t%/\*}
  while [ "${#b}" -gt 1 ] && [ "${b%/}" != "$b" ]; do b=${b%/}; done
  case "$b" in
    ""|"/"|"~"|"\$HOME"|"\${HOME}"|"."|".."|"*"|".*"|"\$PWD"|"\${PWD}"|"\$(pwd)"|'`pwd`'|".git"|"./.git") return 0 ;;
    "\$env:USERPROFILE"|"\$env:HOMEPATH"|"%USERPROFILE%"|"\$env:SystemDrive"|"%SystemDrive%") return 0 ;;
  esac
  printf '%s' "$b" | grep -Eq '^/[^/]+$' && return 0
  printf '%s' "$b" | grep -Eq '^[A-Za-z]:/?$' && return 0
  printf '%s' "$b" | grep -Eq '^[A-Za-z]:/[^/]+$' && return 0
  if [ -n "$cwd_posix" ]; then
    [ "$b" = "$cwd_posix" ] && return 0
    [ "$(printf '%s' "$b" | tr 'A-Z' 'a-z')" = "$(printf '%s' "$cwd_posix" | tr 'A-Z' 'a-z')" ] && return 0
  fi
  return 1
}

is_protected_branch() {
  local b=${1#refs/heads/}
  case "$b" in
    "{{DEFAULT_BRANCH}}"|main|master|production|prod|release/*) return 0 ;;
  esac
  return 1
}

# --- per-segment checks ----------------------------------------------------------------------
workdir="$base_cwd"
segments=$(printf '%s\n' "$cmd" | sed -E 's/(&&|\|\||;|\|)/\n/g')
while IFS= read -r seg; do
  set -f
  read -ra toks <<< "$seg"
  set +f
  n=${#toks[@]}
  [ "$n" -eq 0 ] && continue

  # a leading `cd <dir>` moves where later git segments resolve their branch
  if [ "${toks[0]}" = "cd" ] && [ "$n" -ge 2 ]; then
    d=$(unquote "${toks[1]}" | tr '\\' '/')
    case "$d" in
      /*|[A-Za-z]:/*) workdir=$(norm_path "$d") ;;
      *) workdir="$workdir/$d" ;;
    esac
    continue
  fi

  for ((i = 0; i < n; i++)); do
    tok=$(unquote "${toks[i]}")
    # PowerShell and cmd deletion: Remove-Item and its aliases (ri, rd, rmdir, del, erase) delete a
    # tree with -Recurse alone - -Force only adds hidden and read-only files - and cmd's rd/del
    # take /s. Names and parameters are case-insensitive and parameters may be abbreviated.
    tl=$(printf '%s' "$tok" | tr 'A-Z' 'a-z')
    case "$tl" in
      remove-item|ri|rd|rmdir|del|erase|*/rmdir)
        rec=0; targets=(); skip=0
        for ((j = i + 1; j < n; j++)); do
          a=$(unquote "${toks[j]}")
          al=$(printf '%s' "$a" | tr 'A-Z' 'a-z')
          if [ "$skip" -eq 1 ]; then skip=0; continue; fi
          case "$al" in
            -r|-re|-rec|-recu|-recur|-recurs|-recurse|/s) rec=1 ;;
            -inc*|-exc*|-fil*|-cr*|-str*) skip=1 ;;
            -*|/?) ;;
            *) targets+=("$a") ;;
          esac
        done
        if [ "$rec" -eq 1 ]; then
          for t in "${targets[@]}"; do
            if is_danger_target "$t"; then
              block "$tok with -Recurse on '$t' would delete the repository, the home directory or a system path. Remove the specific build output you mean, or ask the user to do this by hand."
            fi
          done
        fi
        break
        ;;
    esac
    case "$tok" in
      rm|*/rm)
        rec=0; force=0; npr=0; targets=(); opts=1
        for ((j = i + 1; j < n; j++)); do
          a="${toks[j]}"
          if [ "$opts" -eq 1 ] && [ "$a" = "--" ]; then opts=0; continue; fi
          if [ "$opts" -eq 1 ]; then
            case "$a" in
              --recursive) rec=1; continue ;;
              --force) force=1; continue ;;
              --no-preserve-root) npr=1; continue ;;
              --*) continue ;;
              -*)
                # PowerShell's rm alias takes -Force (and its abbreviations), not -f in a cluster
                case "$(printf '%s' "$a" | tr 'A-Z' 'a-z')" in -fo|-for|-forc|-force) force=1 ;; esac
                printf '%s' "$a" | grep -q '[rR]' && rec=1
                printf '%s' "$a" | grep -q 'f' && force=1
                continue ;;
            esac
          fi
          targets+=("$a")
        done
        [ "$npr" -eq 1 ] && block "rm --no-preserve-root is never a legitimate step in a repo task."
        if [ "$rec" -eq 1 ] && [ "$force" -eq 1 ]; then
          for t in "${targets[@]}"; do
            if is_danger_target "$t"; then
              block "rm -rf on '$(unquote "$t")' would delete the repository, the home directory or a system path. Delete the specific build output you mean (for example dist/ or node_modules/), or ask the user to do this by hand."
            fi
          done
        fi
        break
        ;;
      git|*/git)
        gdir="$workdir"; sub=""; k=$((i + 1))
        while [ "$k" -lt "$n" ]; do
          a=$(unquote "${toks[k]}")
          case "$a" in
            -C) k=$((k + 1)); d=$(unquote "${toks[k]}" | tr '\\' '/')
                case "$d" in /*|[A-Za-z]:/*) gdir=$(norm_path "$d") ;; *) gdir="$gdir/$d" ;; esac ;;
            -c|--git-dir|--work-tree|--namespace|--config-env) k=$((k + 1)) ;;
            -*) ;;
            *) sub="$a"; break ;;
          esac
          k=$((k + 1))
        done
        rest=()
        for ((j = k + 1; j < n; j++)); do rest+=("$(unquote "${toks[j]}")"); done
        case "$sub" in
          push)
            forced=0; all=0; pos=()
            skip=0
            for a in "${rest[@]}"; do
              if [ "$skip" -eq 1 ]; then skip=0; continue; fi
              case "$a" in
                --force|--force-with-lease|--force-with-lease=*) forced=1 ;;
                --all|--mirror) all=1 ;;
                -o|--push-option|--repo|--receive-pack|--exec) skip=1 ;;
                --*) ;;
                -*) printf '%s' "$a" | grep -q 'f' && forced=1 ;;
                *) pos+=("$a") ;;
              esac
            done
            branches=()
            if [ "${#pos[@]}" -ge 2 ]; then
              for r in "${pos[@]:1}"; do
                case "$r" in +*) forced=1; r=${r#+} ;; esac
                case "$r" in *:*) r=${r##*:} ;; esac
                if [ "$r" = "HEAD" ]; then
                  r=$(git -C "$gdir" rev-parse --abbrev-ref HEAD 2>/dev/null)
                fi
                branches+=("$r")
              done
            else
              branches+=("$(git -C "$gdir" rev-parse --abbrev-ref HEAD 2>/dev/null)")
            fi
            if [ "$forced" -eq 1 ]; then
              [ "$all" -eq 1 ] && block "a force push with --all/--mirror rewrites every branch, protected ones included."
              for b in "${branches[@]}"; do
                if is_protected_branch "$b"; then
                  block "force push to protected branch '$b' rewrites shared history. Push to a feature branch and open a PR, or ask the user to do this by hand."
                fi
              done
            fi
            ;;
          reset)
            for a in "${rest[@]}"; do
              [ "$a" = "--hard" ] && block "git reset --hard discards uncommitted work with no undo. Use 'git stash' (recoverable) or 'git reset --soft', or ask the user."
            done
            ;;
          clean)
            cf=0; cx=0
            for a in "${rest[@]}"; do
              case "$a" in
                --force) cf=1 ;;
                --*) ;;
                -*) printf '%s' "$a" | grep -q 'f' && cf=1
                    printf '%s' "$a" | grep -q '[xX]' && cx=1 ;;
              esac
            done
            [ "$cf" -eq 1 ] && [ "$cx" -eq 1 ] && block "git clean -x also deletes ignored files - local env files, local databases, caches - none of which git can restore. Drop -x, or list with 'git clean -n -x' first and ask the user."
            ;;
          checkout|restore)
            staged_only=0; wt=0; dot=0
            for a in "${rest[@]}"; do
              case "$a" in
                --staged|-S) staged_only=1 ;;
                --worktree|-W) wt=1 ;;
                .|./|:/|'*') dot=1 ;;
              esac
            done
            if [ "$dot" -eq 1 ] && { [ "$staged_only" -eq 0 ] || [ "$wt" -eq 1 ]; }; then
              block "git $sub . discards every uncommitted change in the tree. Name the files you mean, or 'git stash' first."
            fi
            ;;
        esac
        break
        ;;
    esac
  done
done <<< "$segments"

# --- destructive SQL against a non-local host (whole command: the SQL and the host flag are
#     often on opposite sides of a pipe) --------------------------------------------------------
if printf '%s' "$cmd" | grep -Eiq '(DROP[[:space:]]+(TABLE|DATABASE|SCHEMA)|TRUNCATE[[:space:]]+)'; then
  hosts=$( {
    printf '%s\n' "$cmd" | grep -Eo -- '(^|[[:space:]])(-h|-S|--host|--server)[[:space:]=]*[^[:space:]]+' | sed -E 's/^[[:space:]]*(-h|-S|--host|--server)[[:space:]=]*//'
    printf '%s\n' "$cmd" | grep -Eio -- 'host=[^[:space:];]+' | sed -E 's/^[hH][oO][sS][tT]=//'
    printf '%s\n' "$cmd" | grep -Eo -- '[a-zA-Z][a-zA-Z0-9+.-]*://([^/@[:space:]]*@)?[^/:?[:space:]]+' | sed -E 's#^[^:]*://([^@]*@)?##'
  } 2>/dev/null )
  while IFS= read -r h; do
    h=$(unquote "$h")
    h=${h#\"}; h=${h%\"}; h=${h#\'}; h=${h%\'}
    [ -z "$h" ] && continue
    case "$h" in /*) continue ;; esac
    h=${h%%\\*}; h=${h%%,*}
    case "$h" in \[*) h=${h#\[}; h=${h%%\]*} ;; *) h=${h%%:*} ;; esac
    hl=$(printf '%s' "$h" | tr 'A-Z' 'a-z')
    case "$hl" in
      ""|localhost|127.0.0.1|::1|0.0.0.0|.|"(local)") ;;
      *) block "destructive SQL (DROP/TRUNCATE) aimed at host '$h', which is not local. Run it against a local database, or hand the exact statement to the user." ;;
    esac
  done <<< "$hosts"
fi

exit 0

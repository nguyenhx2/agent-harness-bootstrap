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
# Every block below needs one of these words in the command: a deletion verb or `git` standing
# as its own token, or DROP / TRUNCATE. Written case-insensitively so the gate is never narrower
# than the case-folding checks it fronts.
FAST_GATE='(^|[^A-Za-z0-9_-])([Rr][Mm]|[Rr][Ii]|[Rr][Dd]|[Rr][Mm][Dd][Ii][Rr]|[Dd][Ee][Ll]|[Ee][Rr][Aa][Ss][Ee]|[Rr][Ee][Mm][Oo][Vv][Ee]-[Ii][Tt][Ee][Mm]|[Gg][Ii][Tt])([^A-Za-z0-9_-]|$)|[Dd][Rr][Oo][Pp]|[Tt][Rr][Uu][Nn][Cc][Aa][Tt][Ee]'
fast_str command && fast_unmatched "$FAST_GATE" && exit 0
# --- full parse ------------------------------------------------------------------------------
# Also fork-free, except `git rev-parse` for a forced push and the host scan for DROP/TRUNCATE.
# The commands that reach this point are exactly the ones worth checking - `rm`, `git` - and with
# a `$(...)` or a `tr` per token they cost 10 s and more with four sessions running at once on
# Windows, long enough to hit the 30 s timeout, which fails closed and blocks every Bash call.
# The exact decode is reused when it worked; the JSON parser is the fallback, not the default.
cmd= raw_cwd=
if fast_str command; then
  cmd=$FAST_STR
  if fast_str cwd; then raw_cwd=$FAST_STR; else cmd=; fi
fi
if [ -z "$cmd" ]; then
  json_fields tool_input.command cwd
  cmd="${JF[0]}"
  raw_cwd="${JF[1]}"
fi
[ -z "$cmd" ] && exit 0
cwd_posix=${raw_cwd//\\//}
cwd_posix=${cwd_posix%/}
# Kept as written and converted (norm_path) only where git needs a real directory.
base_cwd=$cwd_posix
[ -z "$base_cwd" ] && base_cwd=$PWD

# unq TOKEN -> UQ: one layer of surrounding quotes off, as unquote() does, without a subshell.
unq() {
  UQ=$1
  UQ=${UQ#\"}; UQ=${UQ%\"}; UQ=${UQ#\'}; UQ=${UQ%\'}
}
# lower TEXT -> LO: ASCII A-Z folded, which is what `tr 'A-Z' 'a-z'` did, without a process.
lower() {
  local s=$1
  s=${s//A/a}; s=${s//B/b}; s=${s//C/c}; s=${s//D/d}; s=${s//E/e}; s=${s//F/f}; s=${s//G/g}
  s=${s//H/h}; s=${s//I/i}; s=${s//J/j}; s=${s//K/k}; s=${s//L/l}; s=${s//M/m}; s=${s//N/n}
  s=${s//O/o}; s=${s//P/p}; s=${s//Q/q}; s=${s//R/r}; s=${s//S/s}; s=${s//T/t}; s=${s//U/u}
  s=${s//V/v}; s=${s//W/w}; s=${s//X/x}; s=${s//Y/y}; s=${s//Z/z}
  LO=$s
}

# --- target classification for rm ----------------------------------------------------------
RE_TOP='^/[^/]+$'
RE_DRIVE='^[A-Za-z]:/?$'
RE_DRIVE_TOP='^[A-Za-z]:/[^/]+$'
is_danger_target() {
  local t b lb
  unq "$1"
  t=${UQ//\\//}
  b=${t%/\*}
  while [ "${#b}" -gt 1 ] && [ "${b%/}" != "$b" ]; do b=${b%/}; done
  case "$b" in
    ""|"/"|"~"|"\$HOME"|"\${HOME}"|"."|".."|"*"|".*"|"\$PWD"|"\${PWD}"|"\$(pwd)"|'`pwd`'|".git"|"./.git") return 0 ;;
    "\$env:USERPROFILE"|"\$env:HOMEPATH"|"%USERPROFILE%"|"\$env:SystemDrive"|"%SystemDrive%") return 0 ;;
  esac
  [[ $b =~ $RE_TOP ]] && return 0
  [[ $b =~ $RE_DRIVE ]] && return 0
  [[ $b =~ $RE_DRIVE_TOP ]] && return 0
  if [ -n "$cwd_posix" ]; then
    [ "$b" = "$cwd_posix" ] && return 0
    lower "$b"; lb=$LO
    lower "$cwd_posix"
    [ "$lb" = "$LO" ] && return 0
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

# branch_at DIR -> the branch checked out there (norm_path turns a C:/x dir into one git can use)
branch_at() {
  git -C "$(norm_path "$1")" rev-parse --abbrev-ref HEAD 2>/dev/null
}

# --- per-segment checks ----------------------------------------------------------------------
# Split on && || ; | - the same separators, in the same order of precedence, as the sed
# expression this replaced: (&&|\|\||;|\|) taken leftmost-first.
workdir="$base_cwd"
segments=${cmd//&&/$'\n'}
segments=${segments//||/$'\n'}
segments=${segments//;/$'\n'}
segments=${segments//|/$'\n'}
while IFS= read -r seg; do
  set -f
  read -ra toks <<< "$seg"
  set +f
  n=${#toks[@]}
  [ "$n" -eq 0 ] && continue

  # a leading `cd <dir>` moves where later git segments resolve their branch
  if [ "${toks[0]}" = "cd" ] && [ "$n" -ge 2 ]; then
    unq "${toks[1]}"; d=${UQ//\\//}
    case "$d" in
      /*|[A-Za-z]:/*) workdir=$d ;;
      *) workdir="$workdir/$d" ;;
    esac
    continue
  fi

  for ((i = 0; i < n; i++)); do
    unq "${toks[i]}"; tok=$UQ
    # PowerShell and cmd deletion: Remove-Item and its aliases (ri, rd, rmdir, del, erase) delete a
    # tree with -Recurse alone - -Force only adds hidden and read-only files - and cmd's rd/del
    # take /s. Names and parameters are case-insensitive and parameters may be abbreviated.
    lower "$tok"; tl=$LO
    case "$tl" in
      remove-item|ri|rd|rmdir|del|erase|*/rmdir)
        rec=0; targets=(); skip=0
        for ((j = i + 1; j < n; j++)); do
          unq "${toks[j]}"; a=$UQ
          lower "$a"; al=$LO
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
                lower "$a"
                case "$LO" in -fo|-for|-forc|-force) force=1 ;; esac
                case "$a" in *[rR]*) rec=1 ;; esac
                case "$a" in *f*) force=1 ;; esac
                continue ;;
            esac
          fi
          targets+=("$a")
        done
        [ "$npr" -eq 1 ] && block "rm --no-preserve-root is never a legitimate step in a repo task."
        if [ "$rec" -eq 1 ] && [ "$force" -eq 1 ]; then
          for t in "${targets[@]}"; do
            if is_danger_target "$t"; then
              unq "$t"
              block "rm -rf on '$UQ' would delete the repository, the home directory or a system path. Delete the specific build output you mean (for example dist/ or node_modules/), or ask the user to do this by hand."
            fi
          done
        fi
        break
        ;;
      git|*/git)
        gdir="$workdir"; sub=""; k=$((i + 1))
        while [ "$k" -lt "$n" ]; do
          unq "${toks[k]}"; a=$UQ
          case "$a" in
            -C) k=$((k + 1)); unq "${toks[k]}"; d=${UQ//\\//}
                case "$d" in /*|[A-Za-z]:/*) gdir=$d ;; *) gdir="$gdir/$d" ;; esac ;;
            -c|--git-dir|--work-tree|--namespace|--config-env) k=$((k + 1)) ;;
            -*) ;;
            *) sub="$a"; break ;;
          esac
          k=$((k + 1))
        done
        rest=()
        for ((j = k + 1; j < n; j++)); do unq "${toks[j]}"; rest+=("$UQ"); done
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
                -*) case "$a" in *f*) forced=1 ;; esac ;;
                *) pos+=("$a") ;;
              esac
            done
            # The branch is only worth a `git rev-parse` once the push is known to be forced.
            if [ "$forced" -eq 1 ] || [ "${#pos[@]}" -ge 2 ]; then
              branches=()
              if [ "${#pos[@]}" -ge 2 ]; then
                for r in "${pos[@]:1}"; do
                  case "$r" in +*) forced=1; r=${r#+} ;; esac
                  case "$r" in *:*) r=${r##*:} ;; esac
                  if [ "$r" = "HEAD" ]; then
                    r=$(branch_at "$gdir")
                  fi
                  branches+=("$r")
                done
              else
                branches+=("$(branch_at "$gdir")")
              fi
              if [ "$forced" -eq 1 ]; then
                [ "$all" -eq 1 ] && block "a force push with --all/--mirror rewrites every branch, protected ones included."
                for b in "${branches[@]}"; do
                  if is_protected_branch "$b"; then
                    block "force push to protected branch '$b' rewrites shared history. Push to a feature branch and open a PR, or ask the user to do this by hand."
                  fi
                done
              fi
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
                -*) case "$a" in *f*) cf=1 ;; esac
                    case "$a" in *[xX]*) cx=1 ;; esac ;;
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
# grep -i only for non-ASCII text, where its locale's case folding is the reference; ASCII text
# gets the same test as a builtin, with the case spelled out.
sql_destructive() {
  local re='([Dd][Rr][Oo][Pp][[:space:]]+([Tt][Aa][Bb][Ll][Ee]|[Dd][Aa][Tt][Aa][Bb][Aa][Ss][Ee]|[Ss][Cc][Hh][Ee][Mm][Aa])|[Tt][Rr][Uu][Nn][Cc][Aa][Tt][Ee][[:space:]]+)'
  local had=${LC_ALL+x} old=${LC_ALL-} ascii=1 rc
  LC_ALL=C
  case $cmd in *[!\ -~$'\t\n\r']*) ascii=0 ;; esac
  if [ "$ascii" -eq 1 ]; then [[ $cmd =~ $re ]]; rc=$?; fi
  if [ "$had" = x ]; then LC_ALL=$old; else unset LC_ALL; fi
  [ "$ascii" -eq 1 ] && return $rc
  printf '%s' "$cmd" | grep -Eiq '(DROP[[:space:]]+(TABLE|DATABASE|SCHEMA)|TRUNCATE[[:space:]]+)'
}
if sql_destructive; then
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

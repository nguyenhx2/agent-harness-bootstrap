#!/usr/bin/env bash
# guard-large-file.sh
# Event: PreToolUse   Matcher: Bash|PowerShell
# Flag: hooks_strict
# Enforces: .claude/rules/code-quality.md (repository hygiene)
# BLOCKS (exit 2) a `git add` or `git commit` that would put into history:
#   - any file larger than 5 MB (LIMIT_KB below), or
#   - a binary artifact by extension - archives, executables and libraries, media, local
#     databases, ML weights (BIN_EXT below) - whatever its size,
# unless the path is tracked by Git LFS (`git check-attr filter` reports `lfs`).
# `git add` is checked with `git add --dry-run <same args>`, so `git add -A && git commit` is
# caught at the add, before anything is staged. `git commit` checks what is already staged, plus
# the tracked changes `-a` would stage.
#
# WHY BLOCK, NOT WARN: a blob in history stays in every clone forever; removing it later means
# rewriting history on a shared branch. A local database or a model dump is also the most common
# way customer data ends up in a repository. The fix (LFS, .gitignore, or an artifact store) is
# cheap at this moment and expensive after the push.
#
# PARITY CONTRACT: guard-large-file.sh and guard-large-file.ps1 must stay behaviorally
# EQUIVALENT - same limit, same extension list, same LFS exemption.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (reason on stderr, shown
# to Claude); exit 0 = allow. Fails OPEN on an unreadable payload or a missing git.

LIMIT_KB=5120
BIN_EXT='zip|tar|gz|tgz|bz2|xz|7z|rar|jar|war|exe|dll|so|dylib|bin|iso|dmg|msi|mp4|mov|avi|mkv|mp3|wav|flac|psd|sqlite|sqlite3|db|mdb|parquet|pkl|pickle|pt|pth|onnx|h5|ckpt|safetensors'

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
    echo "guard-large-file: no jq/perl/python3 available to parse the hook payload; allowing." >&2
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
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

unquote() {
  local t=$1
  t=${t#\"}; t=${t%\"}; t=${t#\'}; t=${t%\'}
  printf '%s' "$t"
}

# check_paths ROOT DIR < newline-separated repo-relative paths; blocks on the first offender
check_paths() {
  local root=$1 dir=$2 f ext kb
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ -f "$root/$f" ] || continue
    if git -C "$root" check-attr filter -- "$f" 2>/dev/null | grep -q ': filter: lfs$'; then
      continue
    fi
    ext=$(printf '%s' "${f##*.}" | tr 'A-Z' 'a-z')
    if [ "$ext" != "$f" ] && printf '%s' "$ext" | grep -Eqx "$BIN_EXT"; then
      echo "BLOCKED by guard-large-file: '$f' is a binary artifact (.$ext). Committed, it stays in every clone forever - and a local database or model dump is the usual way real data leaks into a repo. Add it to .gitignore, track it with Git LFS (git lfs track '*.$ext'), or keep it in an artifact store." >&2
      exit 2
    fi
    kb=$(( $(wc -c < "$root/$f" 2>/dev/null || echo 0) / 1024 ))
    if [ "$kb" -gt "$LIMIT_KB" ]; then
      echo "BLOCKED by guard-large-file: '$f' is ${kb} KB, over the ${LIMIT_KB} KB limit. Large blobs stay in history forever. Track it with Git LFS, generate it at build time, or keep it out of the repo." >&2
      exit 2
    fi
  done
}

payload=$(cat)
json_fields tool_input.command cwd
cmd="${JF[0]}"
[ -z "$cmd" ] && exit 0
printf '%s' "$cmd" | grep -Eq '(^|[^a-zA-Z0-9_-])git([^a-zA-Z0-9_-]|$)' || exit 0
command -v git >/dev/null 2>&1 || exit 0
base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)

workdir="$base_cwd"
segments=$(printf '%s\n' "$cmd" | sed -E 's/(&&|\|\||;|\|)/\n/g')
while IFS= read -r seg; do
  set -f
  read -ra toks <<< "$seg"
  set +f
  n=${#toks[@]}
  [ "$n" -eq 0 ] && continue
  if [ "${toks[0]}" = "cd" ] && [ "$n" -ge 2 ]; then
    d=$(unquote "${toks[1]}" | tr '\\' '/')
    case "$d" in /*|[A-Za-z]:/*) workdir=$(norm_path "$d") ;; *) workdir="$workdir/$d" ;; esac
    continue
  fi
  for ((i = 0; i < n; i++)); do
    tok=$(unquote "${toks[i]}")
    case "$tok" in git|*/git) ;; *) continue ;; esac
    gdir="$workdir"; sub=""; k=$((i + 1))
    while [ "$k" -lt "$n" ]; do
      a=$(unquote "${toks[k]}")
      case "$a" in
        -C) k=$((k + 1)); d=$(unquote "${toks[k]}" | tr '\\' '/')
            case "$d" in /*|[A-Za-z]:/*) gdir=$(norm_path "$d") ;; *) gdir="$gdir/$d" ;; esac ;;
        -c) k=$((k + 1)) ;;
        -*) ;;
        *) sub="$a"; break ;;
      esac
      k=$((k + 1))
    done
    root=$(git -C "$gdir" rev-parse --show-toplevel 2>/dev/null) || break
    [ -z "$root" ] && break
    root=$(norm_path "$root")
    args=()
    for ((j = k + 1; j < n; j++)); do
      a=$(unquote "${toks[j]}")
      case "$a" in *'>'*|*'<'*) break ;; esac
      args+=("$a")
    done
    case "$sub" in
      add)
        git -C "$gdir" add --dry-run "${args[@]}" 2>/dev/null | sed -nE "s/^add '(.*)'\$/\1/p" | { check_paths "$root" "$gdir"; } || exit 2
        ;;
      commit)
        git -C "$gdir" diff --cached --name-only 2>/dev/null | { check_paths "$root" "$gdir"; } || exit 2
        all=0
        skip=0
        for a in "${args[@]}"; do
          if [ "$skip" -eq 1 ]; then skip=0; continue; fi
          case "$a" in
            --all) all=1 ;;
            -m|-F|-C|-c|--author|--date|--file) skip=1 ;;
            --*) ;;
            -*) printf '%s' "$a" | grep -q 'a' && all=1
                printf '%s' "$a" | grep -Eq '[mFCc]$' && skip=1 ;;
          esac
        done
        if [ "$all" -eq 1 ]; then
          git -C "$gdir" diff --name-only 2>/dev/null | { check_paths "$root" "$gdir"; } || exit 2
        fi
        ;;
    esac
    break
  done
done <<< "$segments"
exit 0

#!/usr/bin/env bash
# guard-migration.sh
# Event: PreToolUse   Matcher: Edit|Write
# Flag: db
# Enforces: .claude/rules/data-model.md
# BLOCKS (exit 2) an edit to a database migration that already exists on {{DEFAULT_BRANCH}}.
# A migration on the default branch has been - or will be - applied somewhere, and every database
# that ran it keeps the old version: rewriting it makes environments disagree silently, with no
# error until the day a fresh database is built from the edited file. The fix is always a NEW
# migration that changes what the old one did.
#
# Migration paths: any file under a `migrations/` or `migration/` directory (Prisma, Django,
# Knex, TypeORM, Supabase, golang-migrate, ...), `db/migrate/` (Rails), `alembic/versions/`, or
# `flyway/` / `db/changelog/` (Flyway, Liquibase). A migration that exists only on a feature
# branch is still yours to fix, so it is allowed; so is any brand-new migration file.
#
# WHY BLOCK, NOT WARN: the damage (environments that disagree) is invisible at the moment of the
# edit and expensive later, and the correct alternative is always available and cheap.
#
# PARITY CONTRACT: guard-migration.sh and guard-migration.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (reason on stderr, shown
# to Claude); exit 0 = allow. Fails OPEN on an unreadable payload, a missing git, or a repo with
# no {{DEFAULT_BRANCH}} branch.

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
    echo "guard-migration: no jq/perl/python3 available to parse the hook payload; allowing." >&2
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

payload=$(cat)
json_fields tool_input.file_path cwd
path=$(printf '%s' "${JF[0]}" | tr '\\' '/')
[ -z "$path" ] && exit 0

printf '%s' "/$path" | grep -Eq '/(migrations?|db/migrate|alembic/versions|flyway|db/changelog)/' || exit 0
command -v git >/dev/null 2>&1 || exit 0

base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)
case "$path" in
  /*|[A-Za-z]:/*) abs=$(norm_path "$path") ;;
  *) abs="$base_cwd/$path" ;;
esac
dir=${abs%/*}
name=${abs##*/}
[ -d "$dir" ] || exit 0

branch="{{DEFAULT_BRANCH}}"
git -C "$dir" rev-parse --verify --quiet "$branch^{commit}" >/dev/null 2>&1 || {
  branch=main
  git -C "$dir" rev-parse --verify --quiet "$branch^{commit}" >/dev/null 2>&1 || {
    branch=master
    git -C "$dir" rev-parse --verify --quiet "$branch^{commit}" >/dev/null 2>&1 || exit 0
  }
}

if git -C "$dir" cat-file -e "$branch:./$name" 2>/dev/null; then
  echo "BLOCKED by guard-migration: $path is already on $branch, so some database has applied it (or will). Editing it makes environments disagree with no error. Write a NEW migration that changes what this one did, and leave this file as it is." >&2
  exit 2
fi
exit 0

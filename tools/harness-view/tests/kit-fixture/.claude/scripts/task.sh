#!/usr/bin/env bash
# オーケストレーターのタスクボード操作（orchestrator-kit）。GNU / BSD sed、Git Bash で動く。
#
# 構成（TASK_BOARD_DIR で変更可。既定は .agent-base/tasks。プロジェクトルートからの相対パス）:
#   TASKS.md                     集約ファイル。1 タスク 1 行（ID、タスク、担当、状態、依存、ミッション）
#   pending/TASK-NNN[-slug].md   未着手・依存待ち
#   active/                      委譲中・検証中・再試行中・ブロック中
#   completed/                   オーケストレーターが検証済み
#   canceled/                    不要になったもの、担当がいないもの（理由は履歴に残す）
#
# 使い方:
#   task.sh new "<タスク名>" <エージェント> [TASK-NNN,...] [ミッション名]  pending に作成し ID を出力
#   task.sh move <TASK-NNN> <pending|active|completed|canceled> ["<メモ>"]
#   task.sh path <TASK-NNN>          タスクファイルのパスを出力
#   task.sh list [状態]              集約ファイルの表を出力（状態で絞り込み可）
#   task.sh check                    集約ファイル・フォルダ・status: の一致を検査
#
# 状態の変更は必ずこのスクリプトで行う。手でファイルを移動したり、状態列を書き換えたりしない。
set -eu

ROOT="$(printf '%s' "${CLAUDE_PROJECT_DIR:-$(pwd)}" | sed 's#\\#/#g')"
BOARD="$ROOT/${TASK_BOARD_DIR:-.agent-base/tasks}"
INDEX="$BOARD/TASKS.md"
STATES="pending active completed canceled"

die() { echo "エラー: $*" >&2; exit 1; }
now() { date '+%Y-%m-%d %H:%M'; }
slug() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//; s/-$//' | cut -c1-40; }
valid_state() { case " $STATES " in *" $1 "*) return 0 ;; esac; return 1; }

# sed -i を使わずにファイルを書き換える（GNU と BSD で挙動が違うため）。
rewrite() { # rewrite <ファイル> <コマンド...>  コマンドは標準入力を読み標準出力へ書く
  local f="$1" tmp
  shift
  tmp="$(mktemp)"
  "$@" < "$f" > "$tmp" && mv "$tmp" "$f"
}

init_board() {
  [ -f "$INDEX" ] && return 0
  local s
  for s in $STATES; do mkdir -p "$BOARD/$s"; done
  cat > "$INDEX" <<'EOF'
# タスクボード

<!-- .claude/scripts/task.sh で管理する。状態列を手で書き換えない。 -->

| ID | タスク | 担当 | 状態 | 依存 | ミッション |
|---|---|---|---|---|---|
EOF
}

find_task() { # find_task <TASK-NNN>
  local s f
  for s in $STATES; do
    for f in "$BOARD/$s/$1"-*.md "$BOARD/$s/$1.md"; do
      [ -f "$f" ] && { printf '%s' "$f"; return 0; }
    done
  done
  return 1
}

row_state() { # row_state <TASK-NNN>  -> 集約ファイルの該当行の状態列
  awk -F'|' -v id="$1" '{ k=$2; gsub(/ /, "", k) } k == id { s=$5; gsub(/ /, "", s); print s; exit }' "$INDEX"
}

next_id() {
  local max
  max="$(awk -F'|' '{ k=$2; gsub(/ /, "", k) } k ~ /^TASK-[0-9]+$/ { sub(/TASK-/, "", k); print k }' "$INDEX" | sort -n | tail -1)"
  printf 'TASK-%03d' $((10#${max:-0} + 1))
}

cmd_new() {
  [ $# -ge 2 ] || die "使い方: new \"<タスク名>\" <エージェント> [TASK-NNN,...] [ミッション名]"
  init_board
  local id deps mission sl file
  id="$(next_id)"
  deps="${3:--}"
  mission="${4:--}"
  sl="$(slug "$1")"
  file="$BOARD/pending/$id${sl:+-$sl}.md"
  cat > "$file" <<EOF
---
id: $id
title: $1
status: pending
agent: $2
depends_on: $deps
mission: $mission
attempts: 0
created: $(now)
updated: $(now)
---

# $id $1

## 委譲内容

- 目的:
- 背景:
- 入力:
- 期待成果物:
- 制約:
- 完了条件:

## 結果

## 履歴

| 日時 | 内容 |
|---|---|
| $(now) | 作成（pending） |
EOF
  printf '| %s | %s | %s | pending | %s | %s |\n' "$id" "$1" "$2" "$deps" "$mission" >> "$INDEX"
  printf '%s\n' "$id"
}

cmd_move() {
  [ $# -ge 2 ] || die "使い方: move <TASK-NNN> <状態> [\"<メモ>\"]"
  valid_state "$2" || die "状態は $STATES のいずれかです（指定: $2）"
  local src dst from note n ts
  src="$(find_task "$1")" || die "タスクがありません: $1"
  from="$(basename "$(dirname "$src")")"
  note="${3:-}"
  ts="$(now)"
  dst="$BOARD/$2/$(basename "$src")"
  [ "$src" != "$dst" ] && mv "$src" "$dst"
  n="$(awk '/^attempts:/{print $2; exit}' "$dst")"
  # active -> active は再試行として attempts を数える。
  if [ "$from" = active ] && [ "$2" = active ]; then n=$((${n:-0} + 1)); fi
  rewrite "$dst" awk -v st="$2" -v ts="$ts" -v n="${n:-0}" '
    /^status:/ && !a { print "status: " st; a=1; next }
    /^updated:/ && !b { print "updated: " ts; b=1; next }
    /^attempts:/ && !c { print "attempts: " n; c=1; next }
    { print }'
  printf '| %s | %s -> %s%s |\n' "$ts" "$from" "$2" "${note:+ : $note}" >> "$dst"
  rewrite "$INDEX" awk -F'|' -v id="$1" -v st="$2" 'BEGIN{OFS="|"}
    { k=$2; gsub(/ /, "", k) } k == id { $5 = " " st " " } { print }'
  echo "$1: $from -> $2"
}

cmd_path() { find_task "$1" || die "タスクがありません: $1"; echo; }

cmd_list() {
  [ -f "$INDEX" ] || { echo "タスクはありません"; return 0; }
  if [ $# -ge 1 ]; then
    awk -F'|' -v st="$1" '
      /^\| *ID *\|/ || /^\|---/ { print; next }
      { s=$5; gsub(/ /, "", s) } /^\| *TASK-/ && s == st' "$INDEX"
  else
    grep -E '^\|' "$INDEX"
  fi
}

cmd_check() {
  [ -f "$INDEX" ] || { echo "OK: タスクはありません"; return 0; }
  local ng=0 s f id st
  for s in $STATES; do
    for f in "$BOARD/$s"/*.md; do
      [ -f "$f" ] || continue
      id="$(basename "$f" | grep -oE '^TASK-[0-9]+')"
      st="$(row_state "$id")"
      if [ -z "$st" ]; then echo "NG: $id が TASKS.md にありません"; ng=1; continue; fi
      [ "$st" = "$s" ] || { echo "NG: $id はフォルダ $s にあるが TASKS.md では $st"; ng=1; }
      grep -q "^status: $s\$" "$f" || { echo "NG: $id のファイル内 status が $s ではない"; ng=1; }
    done
  done
  for id in $(awk -F'|' '{ k=$2; gsub(/ /, "", k) } k ~ /^TASK-[0-9]+$/ { print k }' "$INDEX"); do
    find_task "$id" > /dev/null || { echo "NG: $id のファイルがどの状態フォルダにもない"; ng=1; }
  done
  [ $ng -eq 0 ] && echo "OK: タスクボードは整合しています"
  return $ng
}

[ $# -ge 1 ] || { sed -n '2,18p' "$0"; exit 1; }
sub="$1"; shift
case "$sub" in
  new|move|path|list|check) "cmd_$sub" "$@" ;;
  *) die "不明なサブコマンド: $sub" ;;
esac

#!/usr/bin/env bash
# オーケストレーター一式の自己テスト。導入後と、フック・task.sh・その登録を変えるたびに、
# プロジェクトルートで実行する:
#
#   bash .claude/scripts/orchestrator-selftest.sh
#
# 1. 接続：このリポジトリにファイルがそろい、フックが登録され、AGENTS.md / CLAUDE.md が更新済みか。
# 2. 動作：一時ディレクトリにコピーしてフックと task.sh を実行する。本物のボードには触れない。
# 終了コード 0 = すべて PASS。
set -u

ROOT="$(printf '%s' "${CLAUDE_PROJECT_DIR:-$(pwd)}" | sed 's#\\#/#g')"
BOARD_REL="${TASK_BOARD_DIR:-.agent-base/tasks}"
PASS=0
FAIL=0
ok() { PASS=$((PASS + 1)); echo "PASS  $1"; }
ng() { FAIL=$((FAIL + 1)); echo "FAIL  $1"; }
expect() { # expect <label> <condition-exit-code>
  if [ "$2" -eq 0 ]; then ok "$1"; else ng "$1"; fi
}

echo "== 1. 接続（$ROOT）"
for f in .claude/agents/orchestrator.md .claude/scripts/task.sh .claude/hooks/orch-lib.sh \
  .claude/hooks/spawn-guard.sh .claude/hooks/scope-guard.sh .claude/hooks/task-board-guard.sh \
  .claude/hooks/spawn-allowlist .claude/rules/orchestration.md; do
  [ -f "$ROOT/$f" ]; expect "ファイルあり: $f" $?
done
ORCH="$ROOT/.claude/agents/orchestrator.md"
grep -q 'spawn-guard.sh' "$ORCH" 2>/dev/null; expect "orchestrator.md に spawn-guard を登録済み" $?
grep -q "scope-guard.sh.*$BOARD_REL" "$ORCH" 2>/dev/null; expect "orchestrator.md に $BOARD_REL 用の scope-guard を登録済み" $?
grep -q 'task-board-guard.sh' "$ROOT/.claude/settings.json" 2>/dev/null; expect "settings.json に task-board-guard を登録済み" $?
grep -qi 'orchestrator' "$ROOT/AGENTS.md" 2>/dev/null; expect "AGENTS.md に orchestrator の記載あり" $?
grep -q 'TASK-NNN' "$ROOT/AGENTS.md" 2>/dev/null; expect "AGENTS.md に TASK-NNN の約束あり" $?
grep -qi 'orchestrator' "$ROOT/CLAUDE.md" 2>/dev/null; expect "CLAUDE.md に orchestrator の記載あり" $?
PY=""
for c in python3 python; do
  # Windows の python3 はストアへの誘導スタブの場合があるため、実際に動くかで判定する。
  if "$c" -c 'import json' > /dev/null 2>&1; then PY="$c"; break; fi
done
if [ -n "$PY" ]; then
  "$PY" -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" "$ROOT/.claude/settings.json" 2>/dev/null
  expect "settings.json が JSON として正しい" $?
else
  echo "SKIP  settings.json の JSON 検査（Python なし）"
fi
# 導入時に埋めるべきプレースホルダーが残っていないか。
! grep -nE '<(このリポジトリでの例|エージェント名|description から|可 / 不可|このリポジトリで承認が必要な変更|承認対象)' \
  "$ROOT/AGENTS.md" "$ROOT/CLAUDE.md" 2>/dev/null
expect "AGENTS.md / CLAUDE.md にプレースホルダーが残っていない" $?
# CRLF のシェルスクリプトは bash で $'\r' エラーになる。
CR=0
for f in "$ROOT"/.claude/hooks/*.sh "$ROOT"/.claude/scripts/task.sh "$ROOT"/.claude/scripts/orchestrator-selftest.sh; do
  [ -f "$f" ] || continue
  # grep の \r 指定は環境によって解釈が揺れるため、tr で CR の個数を数える。
  if [ "$(tr -cd '\r' < "$f" | wc -c)" -ne 0 ]; then echo "      CRLF: $f"; CR=1; fi
done
[ $CR -eq 0 ]; expect "シェルスクリプトが LF 改行（CRLF なし）" $?

echo "== 2. 動作（一時コピー）"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/.claude/agents"
cp -r "$ROOT/.claude/hooks" "$ROOT/.claude/scripts" "$T/.claude/"
printf -- '---\nname: st-ro\ndescription: test\ntools: Read, Grep\n---\n' > "$T/.claude/agents/st-ro.md"
printf -- '---\nname: st-rw\ndescription: test\ntools: Read, Edit, Write\n---\n' > "$T/.claude/agents/st-rw.md"
printf -- '---\nname: st-all\ndescription: no tools field = all tools\n---\n' > "$T/.claude/agents/st-all.md"
printf -- '---\nname: st-list\ndescription: test\ntools:\n  - Read\n  - Edit\n---\n' > "$T/.claude/agents/st-list.md"
export CLAUDE_PROJECT_DIR="$T"
H="$T/.claude/hooks"
TS="$T/.claude/scripts/task.sh"
# Windows（Git Bash）の Claude Code は CLAUDE_PROJECT_DIR=D:\... と file_path "D:\\..." の
# 形式で渡す。cygpath がある環境ではこれを再現する。
WIN=0
if command -v cygpath > /dev/null 2>&1; then
  WIN=1
  CLAUDE_PROJECT_DIR="$(cygpath -w "$T")"
  export CLAUDE_PROJECT_DIR
fi
winjson() { # winjson <相対パス>  -> \ を JSON エスケープした Windows の絶対パス
  printf '%s/%s' "$(cygpath -w "$T")" "$1" | tr '/' '\\' | sed 's/\\/\\\\/g'
}

hook() { # hook <expect allow|deny> <label> <hook> <payload> [args...]
  local want="$1" label="$2" h="$3" p="$4" out got
  shift 4
  out="$(printf '%s' "$p" | bash "$H/$h" "$@" 2>&1)"
  case "$out" in *'"deny"'*) got=deny ;; *) got=allow ;; esac
  [ "$got" = "$want" ]; expect "$h: $label → $want" $?
}
sp() { printf '{"tool_name":"Agent","tool_input":{"subagent_type":"%s","prompt":"%s"}}' "$1" "$2"; }
ed() { printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$1"; }

hook deny  "入力が空"                spawn-guard.sh ''
hook deny  "subagent_type なし"      spawn-guard.sh '{"tool_name":"Agent","tool_input":{"prompt":"x"}}'
hook deny  "general-purpose"        spawn-guard.sh "$(sp general-purpose x)"
hook deny  "orchestrator 自身"       spawn-guard.sh "$(sp orchestrator x)"
hook allow "Explore（許可リスト）"   spawn-guard.sh "$(sp Explore x)"
hook allow "読み取り専用"            spawn-guard.sh "$(sp st-ro review)"
hook deny  "書き込み可・TASK なし"   spawn-guard.sh "$(sp st-rw 'do it')"
hook deny  "書き込み可・tools なし" spawn-guard.sh "$(sp st-all 'do it')"
hook deny  "書き込み可・tools がリスト形式" spawn-guard.sh "$(sp st-list 'do it')"

bash "$TS" new "Write docs" st-rw > /dev/null
hook deny  "書き込み可・TASK が pending" spawn-guard.sh "$(sp st-rw 'TASK-001 do it')"
bash "$TS" move TASK-001 active > /dev/null
hook allow "書き込み可・TASK が active" spawn-guard.sh "$(sp st-rw 'TASK-001 do it')"
hook deny  "書き込み可・存在しない TASK" spawn-guard.sh "$(sp st-rw 'TASK-099 do it')"

hook allow "ボード内（相対パス）"    scope-guard.sh "$(ed "$BOARD_REL/active/TASK-001.md")" "$BOARD_REL/*"
hook deny  "ボード外"                scope-guard.sh "$(ed "src/main.py")" "$BOARD_REL/*"
hook deny  ".. を含むパス"           scope-guard.sh "$(ed "$BOARD_REL/../../src/x.py")" "$BOARD_REL/*"
if [ $WIN -eq 1 ]; then
  hook allow "ボード内（Windows パス）" scope-guard.sh "$(ed "$(winjson "$BOARD_REL/active/TASK-001.md")")" "$BOARD_REL/*"
  hook deny  "ボード外（Windows パス）" scope-guard.sh "$(ed "$(winjson "src/main.py")")" "$BOARD_REL/*"
  hook deny  "TASKS.md（Windows パス）" task-board-guard.sh "$(ed "$(winjson "$BOARD_REL/TASKS.md")")"
else
  echo "SKIP  Windows パスのケース（cygpath なし）"
fi

hook deny  "TASKS.md（相対パス）"    task-board-guard.sh "$(ed "$BOARD_REL/TASKS.md")"
hook allow "タスクファイル本文"      task-board-guard.sh "$(ed "$BOARD_REL/active/TASK-001.md")"
hook allow "無関係のファイル"        task-board-guard.sh "$(ed "src/main.py")"

bash "$TS" new "Review" st-ro TASK-001 > /dev/null
bash "$TS" new "日本語のみ" st-ro > /dev/null
bash "$TS" move TASK-001 completed "verified" > /dev/null
bash "$TS" move TASK-003 canceled "not needed" > /dev/null
bash "$TS" move TASK-002 active > /dev/null
bash "$TS" move TASK-002 active "RETRY: missing line numbers" > /dev/null
bash "$TS" check > /dev/null; expect "task.sh: 移動後の check が OK" $?
grep -q '^attempts: 1$' "$(bash "$TS" path TASK-002)"; expect "task.sh: 再試行で attempts が増える" $?
[ -f "$T/$BOARD_REL/canceled/TASK-003.md" ]; expect "task.sh: 英数字のないタスク名は ID だけのファイル名" $?
[ "$(bash "$TS" list active | grep -c '^| TASK-')" -eq 1 ]; expect "task.sh: list の状態での絞り込み" $?
INDEX="$T/$BOARD_REL/TASKS.md"
awk -F'|' 'BEGIN{OFS="|"} { k=$2; gsub(/ /,"",k) } k=="TASK-001" { $5=" active " } { print }' "$INDEX" > "$INDEX.tmp" && mv "$INDEX.tmp" "$INDEX"
bash "$TS" check > /dev/null; [ $? -eq 1 ]; expect "task.sh: 手で書き換えた集約ファイルを check が検出" $?

echo "== $PASS 件 PASS / $FAIL 件 FAIL"
[ $FAIL -eq 0 ]

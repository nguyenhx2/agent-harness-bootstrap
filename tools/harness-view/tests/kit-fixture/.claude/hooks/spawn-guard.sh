#!/usr/bin/env bash
# PreToolUse（Agent）。orchestrator.md の frontmatter にだけ登録する。
#
# 1. 起動できるのは .claude/agents/<名前>.md があるエージェントと、.claude/hooks/spawn-allowlist に
#    書いたものだけ。名前なし、general-purpose、orchestrator 自身は拒否する
#    （スコープも turn 上限もないため）。
# 2. 書き込みできるエージェントへの委譲は、<ボード>/active/ にある TASK-NNN をプロンプトに
#    含む場合だけ許可する。ボードに載らない作業を作らせないため。
# 入力を読めない場合は拒否する（許可側に倒さない）。
set -u
. "$(dirname "$0")/orch-lib.sh"

PAYLOAD="$(orch_payload)"
ROOT="$(orch_root)"
BOARD="$ROOT/$(orch_board)"

[ -z "$PAYLOAD" ] && orch_deny "起動内容を読み取れませんでした。subagent_type を指定して再実行してください。"

STYPE="$(orch_str "$PAYLOAD" subagent_type)"
[ -z "$STYPE" ] && orch_deny "subagent_type が指定されていません。.claude/agents/ のエージェント名を指定してください。"
[ "$STYPE" = orchestrator ] && orch_deny "オーケストレーターからオーケストレーターは起動できません。専門エージェントへ委譲してください。"

SEAT="$ROOT/.claude/agents/$STYPE.md"
ALLOWED=0
[ -f "$SEAT" ] && ALLOWED=1
if [ $ALLOWED -eq 0 ] && [ -f "$ROOT/.claude/hooks/spawn-allowlist" ]; then
  if tr -d '\r' < "$ROOT/.claude/hooks/spawn-allowlist" | sed 's/#.*$//; s/[[:space:]]//g' | grep -qx "$STYPE"; then
    ALLOWED=1
  fi
fi
[ $ALLOWED -eq 1 ] || orch_deny "'$STYPE' は .claude/agents/ にも .claude/hooks/spawn-allowlist にもありません。
定義済みのエージェントへ委譲してください。担当がいない作業は、呼び出し元へ報告してください。"

[ -f "$SEAT" ] || exit 0

# 書き込みできるエージェントか。frontmatter の tools / disallowedTools を読む
# （"a, b" の 1 行形式と YAML のリスト形式の両方）。tools がないエージェントは
# 全ツールを継承するため、書き込み可として扱う。
FM="$(tr -d '\r' < "$SEAT" | awk '/^---[[:space:]]*$/{n++; next} n==1')"
field() { # field <キー名>  -> 値を空白区切りで返す
  printf '%s\n' "$FM" | awk -v k="$1" '
    $0 ~ "^" k ":" { v=$0; sub("^" k ":[[:space:]]*", "", v); print v; inlist=1; next }
    inlist && /^[[:space:]]*-[[:space:]]/ { v=$0; sub(/^[[:space:]]*-[[:space:]]*/, "", v); print v; next }
    { inlist=0 }' | tr '\n,' '  '
}
has_tool() { printf ' %s ' "$1" | grep -qE "[ ]($2)([ (]|$)"; }

TOOLS="$(field tools)"
DENIED="$(field disallowedTools)"
WRITE=0
if ! printf '%s\n' "$FM" | grep -q '^tools:'; then
  WRITE=1
elif has_tool "$TOOLS" 'Edit|Write|MultiEdit|NotebookEdit|\*'; then
  WRITE=1
fi
if [ $WRITE -eq 1 ] && has_tool "$DENIED" 'Edit' && has_tool "$DENIED" 'Write'; then
  WRITE=0
fi
[ $WRITE -eq 1 ] || exit 0

PROMPT="$(orch_str "$PAYLOAD" prompt)"
TID="$(printf '%s' "$PROMPT" | grep -oE 'TASK-[0-9]+' | head -1)"
[ -z "$TID" ] && orch_deny "'$STYPE' は書き込みできるエージェントです。プロンプトに TASK-NNN を含めてください。
先に bash .claude/scripts/task.sh new でタスクを作り、task.sh move <TASK-NNN> active を実行してから委譲します。"
ls "$BOARD/active/$TID"*.md > /dev/null 2>&1 || orch_deny "$TID は $(orch_board)/active/ にありません。
bash .claude/scripts/task.sh move $TID active を実行してから委譲してください。"

exit 0

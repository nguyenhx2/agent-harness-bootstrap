#!/usr/bin/env bash
# PreToolUse（Edit|Write|MultiEdit）。settings.json に登録し、全エージェントに効かせる。
# <ボード>/TASKS.md の直接編集を拒否する。状態は TASKS.md・状態別フォルダ・status: の 3 箇所で
# 持つため、task.sh 以外で変えると整合が崩れる。タスクファイル本文（委譲内容・結果）の編集は許可する。
set -u
. "$(dirname "$0")/orch-lib.sh"

PAYLOAD="$(orch_payload)"
[ -z "$PAYLOAD" ] && exit 0

FILE="$(orch_path "$PAYLOAD" file_path)"
[ -z "$FILE" ] && exit 0

BOARD="$(orch_board)"
case "$(orch_rel "$FILE")" in
  "$BOARD"/TASKS.md|*/"$BOARD"/TASKS.md)
    orch_deny "$BOARD/TASKS.md は直接編集できません。
状態の変更は bash .claude/scripts/task.sh move <TASK-NNN> <状態>、
タスクの追加は bash .claude/scripts/task.sh new で行ってください。"
    ;;
esac

exit 0

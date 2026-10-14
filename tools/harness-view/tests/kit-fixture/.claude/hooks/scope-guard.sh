#!/usr/bin/env bash
# PreToolUse（Edit|Write|MultiEdit|NotebookEdit）。orchestrator.md の frontmatter に登録する。
# 引数のグロブ（プロジェクトルートからの相対パス。bash の case 形式で、* は / にも一致する）に
# 一致するパスだけ編集を許可し、それ以外は拒否する。専門作業を自分でせず委譲させるため。
#
#   bash scope-guard.sh "<グロブ>" ["<グロブ>" ...]
set -u
. "$(dirname "$0")/orch-lib.sh"

PAYLOAD="$(orch_payload)"
[ -z "$PAYLOAD" ] && exit 0

FILE="$(orch_path "$PAYLOAD" file_path)"
[ -z "$FILE" ] && FILE="$(orch_path "$PAYLOAD" notebook_path)"
[ -z "$FILE" ] && exit 0

case "/$FILE/" in
  */../*) orch_deny "パスに .. を含む編集は許可していません: $FILE" ;;
esac

REL="$(orch_rel "$FILE")"
for pattern in "$@"; do
  # shellcheck disable=SC2254
  case "$REL" in
    $pattern) exit 0 ;;
  esac
done

orch_deny "このエージェントが直接編集できるのは次のパスだけです: $*
対象: $REL
コード・ドキュメント・テストの変更は、担当の専門エージェントへ委譲してください。"

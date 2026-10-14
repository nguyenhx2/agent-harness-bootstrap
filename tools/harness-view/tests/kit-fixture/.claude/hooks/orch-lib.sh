#!/usr/bin/env bash
# オーケストレーター用フックの共通ヘルパー（orchestrator-kit）。
# jq に依存しないため、Windows の Git Bash でも Linux / macOS でも動く。
#
# フックの約束：PreToolUse の JSON を標準入力から読む。拒否するときは permissionDecision が
# "deny" の JSON を出力して exit 0、許可するときは何も出力せずに exit 0。

# 入力を 1 回だけ読む: PAYLOAD="$(orch_payload)"
orch_payload() { cat 2>/dev/null || true; }

# パスを表す文字列フィールドを取り出し、区切りを / にそろえる。
# エスケープされた \ を直接 / に変換するため、D:\work\tasks\... のような Windows パスも壊れない
# （一般的な JSON のエスケープ解除では "\t" がタブになる）。
orch_path() { # orch_path "<payload>" <field>
  printf '%s' "$1" \
    | grep -o "\"$2\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
    | head -1 \
    | sed "s/^\"$2\"[[:space:]]*:[[:space:]]*\"//; s/\"\$//; s#\\\\\\\\#/#g; s#\\\\#/#g"
}

# 通常の文字列フィールド（名前、プロンプト）を取り出す。エスケープはそのまま残すため、
# 照合にだけ使い、ファイルパスとしては使わない。
orch_str() { # orch_str "<payload>" <field>
  printf '%s' "$1" \
    | grep -oE "\"$2\"[[:space:]]*:[[:space:]]*\"(\\\\.|[^\"\\\\])*\"" \
    | head -1 \
    | sed "s/^\"$2\"[[:space:]]*:[[:space:]]*\"//; s/\"\$//"
}

orch_lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# / 区切りのプロジェクトルート。
orch_root() { printf '%s' "${CLAUDE_PROJECT_DIR:-$(pwd)}" | sed 's#\\#/#g'; }

# パスをプロジェクトルートからの相対パスにする（ドライブレターの大文字小文字は無視）。
orch_rel() { # orch_rel <path>
  local root
  root="$(orch_root)"
  case "$(orch_lower "$1")" in
    "$(orch_lower "$root")"/*) printf '%s' "${1:$((${#root} + 1))}" ;;
    *) printf '%s' "$1" ;;
  esac
}

orch_json_quote() {
  printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk 'BEGIN{ORS=""} {if (NR>1) printf "\\n"; print}')"
}

orch_deny() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}\n' "$(orch_json_quote "$1")"
  exit 0
}

# プロジェクトルートからのタスクボードの相対パス。
orch_board() { printf '%s' "${TASK_BOARD_DIR:-.agent-base/tasks}"; }

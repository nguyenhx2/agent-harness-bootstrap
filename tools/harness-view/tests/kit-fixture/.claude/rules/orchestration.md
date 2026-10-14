---
paths:
  - ".agent-base/tasks/**"
  - ".claude/agents/**"
  - ".claude/hooks/**"
  - ".claude/scripts/task.sh"
---

# オーケストレーションのルール

`orchestrator` エージェント、タスクボード、委譲を制御するフックの約束事です。
区分（Direct / Standard / Guarded）の判定基準は `AGENTS.md` にあります。

## タスクボード（`.agent-base/tasks/`）

| 項目 | 約束 |
|---|---|
| 正本 | `TASKS.md`（集約）と、`pending/` `active/` `completed/` `canceled/` のタスクファイル |
| ID | `TASK-NNN`。`task.sh new` が採番する。再利用しない |
| 状態の変更 | `bash .claude/scripts/task.sh move` だけで行う。ファイルの手動移動、`TASKS.md` の手動編集はしない（`task-board-guard.sh` が拒否する） |
| 書き込める人 | `orchestrator` だけ。専門エージェントはタスクファイルを編集せず、結果を報告で返す |
| 整合の確認 | `bash .claude/scripts/task.sh check`。ミッションの終了時に必ず実行する |

状態は 4 つだけです。ブロック・再試行は状態を増やさず、`active` のまま `BLOCKED:` / `RETRY:` をメモに書きます。

## 委譲の境界（`spawn-guard.sh`）

- `orchestrator` が起動できるのは `.claude/agents/` の定義済みエージェントと、
  `.claude/hooks/spawn-allowlist` の組み込みエージェント（既定は `Explore` と `Plan`）だけです。
- 書き込みできるエージェント（`tools` に `Edit` / `Write` がある、または `tools` がない）への委譲は、
  `active/` にある `TASK-NNN` をプロンプトに含む場合だけ許可されます。
- `spawn-allowlist` に `general-purpose` など書き込み可能な汎用エージェントを足すのは、チームの合意が
  必要です。スコープも turn 上限もない作業を許すことになります。

## エージェントを追加・変更するとき

`orchestrator` は委譲先を `.claude/agents/*.md` から実行時に読むため、`orchestrator.md` の更新は
不要です。代わりに、次を同じ変更で更新します。

1. `AGENTS.md` のエージェント表
2. `CLAUDE.md` のエージェント・コマンド対応表（ある場合）
3. エージェントの `description`。「いつ使うか」と「いつ使わないか」を書く。メインエージェントも
   `orchestrator` もこれを見て委譲先を選ぶ
4. エージェントの `tools`。最小限にする（`spawn-guard.sh` は `tools` で書き込み可否を判定する）

## フックを追加・変更するとき

- 全エージェントに効かせるものは `.claude/settings.json`、`orchestrator` だけに効かせるものは
  `orchestrator.md` の frontmatter の `hooks` に登録します。
- Windows のパス（`D:\work\tasks\...` のように `\t` を含むもの）でも動くこと。一般的な JSON のエスケープ解除は `\t` を
  タブに変えてパスを壊します。パスの取り出しには `.claude/hooks/orch-lib.sh` の `orch_path` を使います。
- 変更のたびに `bash .claude/scripts/orchestrator-selftest.sh` を実行します。

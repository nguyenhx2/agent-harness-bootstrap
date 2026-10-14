# AGENTS.md - research notes repository

A research and writing repository: briefs in, sourced documents out. There is no code and no
test suite; the review gate is the editor.

## Rules

- `.claude/rules/agent-guardrails.md` - what no seat may do.
- `.claude/rules/orchestration.md` - the task board and the delegation boundary.

## エージェント構成と作業の区分

委譲する前に区分を決めます。**ほとんどの変更は Direct です。** 必要以上に重い区分を選ぶのは
慎重さではなく欠陥です。

| 区分 | 変更の内容 | 誰が行うか |
|---|---|---|
| **Direct** | 質問・調査、1〜2 ファイルの修正で、契約・スキーマ・認証に触れないもの | メインエージェントが直接行う。タスク登録なし |
| **Standard** | 1 つの専門領域で完結する（1 本の調査メモの追記） | 担当の専門エージェントへ直接委譲する。タスク登録なし |
| **Guarded** | 2 つ以上の専門領域にまたがる（実装 → レビュー → docs など）、工程に順序依存と手戻りがある | `orchestrator` が分解・委譲・検証する。タスクボードに登録する |

| エージェント | 担当 | 書き込み |
|---|---|---|
| `orchestrator` | Guarded の作業の分解・委譲・検証・進捗管理。専門作業はしない | タスクボードのみ |
| `researcher` | Finds and summarises sources for a brief | 不可 |
| `writer` | Drafts and revises documents under docs/ | 可 |
| `editor` | Reviews drafts for accuracy, tone and structure | 不可 |

**タスクボード**は `.agent-base/tasks/` です。集約ファイル `TASKS.md`（ID は `TASK-NNN`）と、
状態別フォルダ `pending/` `active/` `completed/` `canceled/` のタスクファイルで構成します。
操作は `.claude/scripts/task.sh` だけで行います。詳細は `.claude/rules/orchestration.md` を参照してください。

**`TASK-NNN` 付きで委譲された専門エージェント**は、次を守ります。

- 委譲内容の「制約」「完了条件」の範囲だけを作業する。範囲外の問題は直さずに報告する。
- タスクボードを編集しない。状態の更新は `orchestrator` が行う。
- 報告の先頭に `TASK-NNN` と、完了条件ごとの達成状況（達成 / 未達 / 未確認）を書く。
- 変更したファイルの一覧を必ず添える。`orchestrator` は `git diff --stat` と突き合わせて検証する。

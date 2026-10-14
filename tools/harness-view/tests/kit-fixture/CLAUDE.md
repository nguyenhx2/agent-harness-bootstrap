@AGENTS.md

## 作業の区分とオーケストレーター

区分（Direct / Standard / Guarded）とエージェント表は `AGENTS.md` の「エージェント構成と作業の区分」が
正本です。Claude Code では次のように振り分けてください。

- **Direct**：メインエージェントが直接処理します。
- **Standard**：`Agent` ツールで担当の専門エージェントを直接起動します。`orchestrator` を経由しません。
- **Guarded**：`Agent` ツールで `subagent_type: orchestrator` を起動します。専門エージェントは
  `orchestrator` の配下にネストして起動され、エージェントツリーでもその下に並びます。
- ユーザーが「オーケストレーターで」と明示した場合は、区分にかかわらず `orchestrator` を起動します。
- 「オーケストレーション不要」「委譲不可」と返った場合は、その推奨に従って続行します。
- 「要判断」が返った場合は、ユーザーに確認してから、同じタスク ID で再開させます。

| フック | 登録先 | 役割 |
|---|---|---|
| `spawn-guard.sh` | `orchestrator.md` | 起動先を定義済みエージェントと許可リストに限定。書き込み可能なエージェントには `active/` の `TASK-NNN` が必須 |
| `scope-guard.sh` | `orchestrator.md` | `orchestrator` が直接編集できるのは `.agent-base/tasks/` だけ |
| `task-board-guard.sh` | `settings.json` | `TASKS.md` の直接編集を全エージェントに対して拒否。`task.sh` を使う |

これらを変更したら `bash .claude/scripts/orchestrator-selftest.sh` を実行してください。

`orchestrator` が委譲の前に承認を取る対象：公開前のドラフト、コミット。

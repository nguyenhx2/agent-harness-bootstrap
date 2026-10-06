---
name: app-dev
description: src/app を実装する担当。登録済みのタスクだけを実装する。
model: sonnet
effort: medium
maxTurns: 50
tools: Read, Edit, Write, Bash, Grep, Glob
---

Owns src/app. Implements registered tasks only.

| 種別 | 名前 | 用途 |
|---|---|---|
| ルール | `.claude/rules/testing.md` | テストの書き方 |
| コマンド | `/review-changes` | 仕上げの確認 |

Before handing back, ask code-reviewer for a pass. Run tests the way the testing
rule says; the word testing on its own is prose, not a reference.

Check the environment with `bash .claude/scripts/check-env.sh` before a run.

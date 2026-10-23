# harness-bootstrap

[English](README.md) · **日本語**

リポジトリに本当に必要な AI エージェントのハーネスを組みます。まずソースを読み、そのうえで `.claude/`
フォルダー (モデル・effort・ツールの予算を明示したエージェント、パス単位のルール、コマンド、シェルで
ブロックするフック、`settings.json`)、`docs/` ツリー、`AGENTS.md` / `CLAUDE.md` を書き出します。
読み取り専用の監査モードでは、ソースには手を触れず、その横に監査用のコントロールプレーンを組みます。

## インストール

```text
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install harness-bootstrap@agent-harness-bootstrap
```

`skills` CLI が対応するエージェントなら、単体のスキルとしても入ります。

```bash
npx skills add nguyenhx2/agent-harness-bootstrap --skill harness-bootstrap
```

あとは対象のリポジトリで `/harness-bootstrap` を実行します。一画面の計画を承認するまで何も書き込まれず、
既存のファイルは上書きではなく突き合わせになります。

## コマンド

`/harness-update`、`/harness-tune`、`/harness-toggle`、`/agent-permissions`、`/skill-wire`、
`/board-audit`、`/code-graph`、`/docs-graph` で、できあがったハーネスを保守します。

## 実行するもの・送るもの・取りに行くもの

- **実行:** 同梱の `scripts/scaffold.py` と `scripts/port.py` を `python` で、履歴を読むために `git` を、
  インストールしたフックが実際に発火することを確かめるために `bash` または PowerShell を実行します。
  二つのスクリプトは Python 標準ライブラリだけを使い、対象リポジトリの中にだけ書き込みます。
- **送信:** ありません。テレメトリーも、サーバーも、MCP サーバーもありません。
- **取得:** 監査モードが基準の日付を確かめるときと、`/skill-wire` がスキルを探すときに、エージェント
  自身の `WebSearch` を使うだけです。インストールするフックはネットワークに接続しません。

ドキュメント全体、採点ルーブリック、ビューアーの `harness-view`:
<https://github.com/nguyenhx2/agent-harness-bootstrap>。ライセンスは AGPL-3.0-only です。

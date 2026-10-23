# spec-builder

[English](README.md) · **日本語**

手元にあるもの (アイデア、議事録、文字起こし、PRD、既存の資料、既存のコードベース) から、プロジェクトの
要件の契約を `docs/specs/` に書きます。要件ごとに不変の FR ID と Given/When/Then の受け入れ基準が付き、
前提と未決事項は推測せずに明示され、PO やクライアントが「はい・いいえ・変更」で答えられる一枚の確認シートが
付きます。JSON のインデックスがあるので、エージェントは全文書を読み込まずに契約を参照できます。要件を
勝手に作ることはありません。

## インストール

```text
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install spec-builder@agent-harness-bootstrap
```

`skills` CLI が対応するエージェントなら、単体のスキルとしても入ります。

```bash
npx skills add nguyenhx2/agent-harness-bootstrap --skill spec-builder
```

あとは対象のリポジトリで `/spec-builder` を実行し、入力を渡します。入力と同じ言語で書きます。

## 実行するもの・送るもの・取りに行くもの

- **実行:** 同梱の `scripts/scaffold.py`、`scripts/ingest.py`、`scripts/route_sources.py` を `python` で
  実行します。Python 標準ライブラリだけを使い、対象リポジトリに書き込みます。標準ライブラリで読めない形式は、
  `markitdown` か `anydoc` がインストール済みなら `ingest.py` がそれを呼びます。どちらも同梱しておらず、
  自動でインストールもしません。
- **送信:** ありません。テレメトリーも、サーバーも、MCP サーバーもありません。
- **取得:** ソースとして URL を渡したときだけ、`markitdown` 経由で取得します。それ以外は、指定された
  ファイルだけを読みます。

対になる `harness-bootstrap` が、この契約をもとに動くエージェントのハーネスを組みます。
ドキュメント全体: <https://github.com/nguyenhx2/agent-harness-bootstrap>。ライセンスは AGPL-3.0-only です。

<p align="center">
  <img src="docs/assets/logo.svg" alt="Agent Harness Bootstrap logo" width="116">
</p>

<h1 align="center">Agent Harness Bootstrap</h1>

<p align="center"><b>AIエージェントに、本当に理解できるリポジトリと、抜け出せないハーネスを与える。</b></p>

<p align="center">作者: <a href="https://github.com/nguyenhx2">nguyenhx2</a> · <a href="README.md">English</a> · <b>日本語</b></p>

[![eval](https://github.com/nguyenhx2/agent-harness-bootstrap/actions/workflows/eval.yml/badge.svg)](https://github.com/nguyenhx2/agent-harness-bootstrap/actions/workflows/eval.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Agents: 15](https://img.shields.io/badge/agents-15%20%2B%201%20template-blue.svg)](harness-bootstrap/assets/claude/agents/)
[![Guardrail eval: 22/22](https://img.shields.io/badge/guardrail%20eval-22%2F22-brightgreen.svg)](eval/guardrail_eval.py) [![Claude Code compatible](https://img.shields.io/badge/Claude%20Code-compatible-5A189A.svg)](https://claude.com/claude-code) [![Release](https://img.shields.io/github/v/release/nguyenhx2/agent-harness-bootstrap?display_name=tag&sort=semver)](https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest)

📊 [スライド資料](https://nguyenhx2.github.io/agent-harness-bootstrap/presentation/) · 🎥 [動画ギャラリー](https://nguyenhx2.github.io/agent-harness-bootstrap/video/) · 📦 [最新リリース](https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest) · 📚 [ドキュメント一覧](#-ドキュメント一覧)

---

## 🎬 これは何をするか

**Claude Code** のための2つのスキル。導入前: AIコーディングエージェントにプロンプトを渡すと、誰も書き留めていない
要件を勝手に推測し、シークレットのコミットや `main` への直push を止めるものが何もないままファイルを編集し、
コンテキストウィンドウが埋まった瞬間にすべてを忘れる。導入後: エージェントは実際の受け入れ基準が書かれた仕様を読み、
生成された `.claude/` **ハーネス**（AIエージェントが何をしてよいかを形作る、エージェント・ルール・強制スクリプトの
フォルダ）の内側で動き、危険な操作は起きる前にブロックされ、書かれた記録を残すので新しいセッションが途中から
再開できる。

<p align="center">
  <a href="https://nguyenhx2.github.io/agent-harness-bootstrap/video/">
    <img src="video/gif/04-solution.gif" alt="完全なソリューション: 課題、契約を書く spec-builder、ハーネスを構築する harness-bootstrap、その内側で回るデリバリーループ、そして成果" width="860">
  </a>
</p>

<p align="center"><i>プロダクト全体を1本のクリップで。</i> <b><a href="https://nguyenhx2.github.io/agent-harness-bootstrap/video/">ギャラリーで全編を見る</a></b> - クリップ6本、音声なしキャプション付き、ダウンロード不要。</p>

- **[`spec-builder`](spec-builder/)** は、あなたとAIが共に理解できるものを作る - アイデア、書き起こし、
  議事録、あるいは既存の古いドキュメントの山から、安定した要件IDと受け入れ基準を持つ13セクションの契約書へと
  一つの共通言語にまとめ上げる。要件を勝手に作ることは決してなく、書かれていないことは推測ではなく
  「未解決の課題」として明示的にフラグが立つ。
- **[`harness-bootstrap`](harness-bootstrap/)** は、AIが自律的かつ安全に動作できる枠組みを作る -
  AIが内側で動く `.claude/` ハーネス: スコープが絞られたエージェント、パスベースのルール、危険な操作を
  検知して拒否するブロッキング **フック**（スクリプト）、そしてクラッシュしても失われないタスクボード。
  まずあなたのコードを読み込むので、生成される内容は手で埋めるテンプレートではなく*あなたの*リポジトリに
  合ったものになる。
- ガードレールはシェルスクリプトと終了コードであり、モデルの判断力に頼らない。すべてのエージェントを
  Opus から Haiku に差し替えても安全の下限は完全に同じ - `python eval/guardrail_eval.py` が証明する、22/22。

<p align="center">
  <img src="docs/assets/ai-dlc-flow.svg" alt="AI-DLC flow: spec-builder produces the contract, harness-bootstrap builds the harness, then the delivery loop runs inside it" width="820">
</p>

---

## 🚀 クイックスタート

**Python 3** が必要です。両方のスキルを1行でインストール:

```bash
curl -fsSL https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest/download/agent-harness-bootstrap.zip -o skills.zip \
  && unzip -o skills.zip -d ~/.claude/skills/ \
  && rm skills.zip
```

続けて Claude Code の中で:

```text
/spec-builder           # アイデアから始めるなら、まず仕様を書く
/harness-bootstrap      # このリポジトリの .claude ハーネスを構築(または更新)する
```

すでにコードがあるリポジトリなら `/harness-bootstrap` 単体で実行する - まずコードを読み込み、
見つけた内容でインテイクを事前に埋めてくれる。既存ファイルは**上書きせず、突き合わせて調整**する:
競合があれば報告され、手でマージするために残される。あなたが承認するまで何も書き込まれない。

**スキルを1つだけ、バージョン固定、チェックサム検証、ソースからのインストール、あるいは Claude Code の
代わりに Cursor や Codex でハーネスを動かす方法:** [`docs/tools/`](docs/tools/) を参照 -
[Claude Code](docs/tools/claude-code.md) · [Cursor](docs/tools/cursor.md) · [Codex](docs/tools/codex.md)。

---

## 📦 手に入るもの

```text
.claude/
  agents/     15個のエージェント、それぞれ明示的な model / effort / tool grant / turn limit を持つ
  rules/      15個のルール - 常時読み込み6個、該当ファイルを触ったときだけ読み込む9個
  commands/   20個のスラッシュコマンド(下記の5個のチューニングコマンドを含む)
  hooks/      8個のフック - 危険な操作を実行される前にブロックする
  settings.json
docs/
  tasks/      タスクボード: タスク1件につき1行、エージェントが作業しながら書くセッションログ
  context/    code-graph.md - mermaidのモジュール図とfan-in/fan-outの表。ソースが変わった瞬間に
              古くなったとマークする非ブロッキングのフックで正直さを保ち、/code-graph で再構築する
  specs/ requirements/ architecture/ templates/
AGENTS.md + CLAUDE.md
```

| エージェントが試みること | 結果 |
|---|---|
| `.env`、秘密鍵、`~/.ssh/`、Restricted に分類したパスの読み取り | ブロック |
| `main` への直接コミット、AI帰属トレーラー付きコミット | ブロック |
| Accepted な ADR の編集、ロスター外エージェントの起動 | ブロック |

インテイクの前に知っておくべき2つのデフォルト: 開発エージェントの方法論は**TDD + DDD がどちらもデフォルトで
オン**(テストファーストとドメイン境界の両立。単一の方法論を意図的に選んだ場合のみどちらかを外す - 詳細は
[`intake.md`](harness-bootstrap/reference/intake.md))、そして**デプロイ権限はデフォルトで人間のみ** -
`deploy` はインテイクの control-level の質問(または後からの `/harness-tune`)が明示的に `ask` へ動かすまで
`permissions.deny` に留まる。起動境界そのもの - ロスターのシートだけが起動でき、固定されたモデルでしか
動かせない - は `guard-agent-spawn` フックが強制するものであり、エージェントが逸脱しうるルールではない。

保証の全リスト、メモリモデル、コストの内訳: [`docs/ASSESSMENT.md`](docs/ASSESSMENT.md)、
[`docs/CONTEXT-MANAGEMENT.md`](docs/CONTEXT-MANAGEMENT.md)、
[`cost-model.md`](harness-bootstrap/reference/cost-model.md)。

---

## 🎛️ ブートストラップ後のチューニング

ハーネスの初期設定は固定ではない。ブートストラップ後にそれを調整するための5個のコマンドが、
ブートストラップされたすべてのリポジトリに同梱される - 完全なガイド、実例、それぞれが強制する
不変条件は [`docs/TUNING.md`](docs/TUNING.md) にある。

| コマンド | 何をするか |
|---|---|
| [`/board-audit`](docs/TUNING.md#board-audit) | 孤立したタスク、記録されていない実行、ボードのずれ、古くなったコードグラフを読み取り専用で調べる |
| [`/harness-tune`](docs/TUNING.md#harness-tune) | 制御レベルを再調整 - デプロイ権限、破壊的コマンドの扱い、起動許可リスト、上限値、レビュー範囲 |
| [`/agent-permissions`](docs/TUNING.md#agent-permissions) | 1つのシートに1つのツールを付与・剥奪する |
| [`/harness-update`](docs/TUNING.md#harness-update) | 新しいアセットや変わったコードベースを取り込むためスキャフォルダを再実行。競合はフラグ付け、上書きは絶対にしない |
| [`/code-graph`](docs/TUNING.md#code-graph) | モジュール間の依存関係グラフ(mermaid + JSON)を再構築する。モジュールをまたぐ変更の前にエージェントが参照する |
| [`/skill-wire`](docs/TUNING.md#skill-wire) | インストール済みの [skills.sh](https://www.skills.sh/) スキルをロースターの担当席に配線する。内容の再レビューとスコープ確認のうえ記録される |

確認しても6つのどれも決してしないこと: レビューア系エージェントが書き込み権限を得ることはなく、
起動できるのはオーケストレーターだけであり、コードレビューのゲートは削除できない(範囲の変更のみ可能)。

---

## 🗺️ ドキュメント一覧

| | |
|---|---|
| [`docs/FLOWS.md`](docs/FLOWS.md) | 7つの図: スキャフォルダ、機能追加の一連の流れ、コンテキストの読み込み |
| [`docs/CONTEXT-MANAGEMENT.md`](docs/CONTEXT-MANAGEMENT.md) | RAM とディスク、クラッシュからの再開プロトコル、ハード制御とソフト制御の違い |
| [`docs/ASSESSMENT.md`](docs/ASSESSMENT.md) | スコアカード。できないことも含む |
| [`docs/TUNING.md`](docs/TUNING.md) | ブートストラップ後の5個のチューニングコマンドの完全版 |
| [`docs/RELEASING.md`](docs/RELEASING.md) | セマンティックバージョニング、成果物、リリースノートの書式 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 開発環境のセットアップ、PRが通るべきゲート、アセット編集のルール |
| [スライド資料](https://nguyenhx2.github.io/agent-harness-bootstrap/presentation/) | EN / VI / JP |
| [動画ギャラリー](https://nguyenhx2.github.io/agent-harness-bootstrap/video/) | クリップ6本、音声なしキャプション付き、ダウンロード不要 |
| [`roster.md`](harness-bootstrap/reference/roster.md) | 各エージェントの model / effort / tools / turn limit とその理由 |
| [`cost-model.md`](harness-bootstrap/reference/cost-model.md) | model・effort・tools・キャッシュの安定性が費用にどう影響するか |
| [`task-control.md`](harness-bootstrap/reference/task-control.md) | オーケストレーションのループ、クラッシュからの復旧、マージの規律 |
| [`ba-standards.md`](spec-builder/reference/ba-standards.md) | 13の仕様セクションが依拠する標準 |
| [`benchmark/RESULTS.md`](benchmark/RESULTS.md) | ベンチマークの数値とその注意点 |

**数値**は、本プロジェクトが置き換える旧スキルとの比較で計測 - `python benchmark/benchmark.py` で再現可能:

| | 導入前 | 導入後 | 差分 |
|---|---:|---:|---:|
| リポジトリをブートストラップするためにモデルが読むバイト数 | 234,196 | 97,190 | **-59%** |
| モデルが出力として書くバイト数 | 95,064 | 13,881 | **-85%** |
| デフォルトのセッションから除外されるルール内容 | - | 51,785 of 77,452 B | **67%** |
| ガードレール評価 | - | **22/22** | - |

---

## 👤 作者について

[**nguyenhx2**](https://github.com/nguyenhx2) が作成。コントリビューション歓迎 -
まずは [`CONTRIBUTING.md`](CONTRIBUTING.md) から。

## 📄 ライセンス

MIT - [LICENSE](LICENSE) を参照。

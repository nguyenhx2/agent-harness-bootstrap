<p align="center">
  <img src="docs/assets/readme-banner.ja.png" alt="Agent Harness Bootstrap - AIエージェントが自律的かつ安全に動くための枠組み" width="100%">
</p>

<p align="center"><b>AIエージェントに、本当に理解できるリポジトリと、抜け出せないハーネスを与える。</b></p>

<p align="center"><a href="README.md">English</a> · <b>日本語</b></p>

<p align="center">
  <a href="https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest"><img src="https://img.shields.io/github/v/release/nguyenhx2/agent-harness-bootstrap?display_name=tag&sort=semver" alt="最新リリース"></a>
  <a href="LICENSE.md"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="ライセンス: AGPL-3.0"></a>
  <a href="https://github.com/nguyenhx2/agent-harness-bootstrap/actions/workflows/eval.yml"><img src="https://github.com/nguyenhx2/agent-harness-bootstrap/actions/workflows/eval.yml/badge.svg" alt="CI: eval ワークフロー"></a>
  <a href="https://github.com/nguyenhx2/agent-harness-bootstrap/actions/workflows/codeql.yml"><img src="https://github.com/nguyenhx2/agent-harness-bootstrap/actions/workflows/codeql.yml/badge.svg" alt="CI: CodeQL"></a>
  <a href="#自分で確かめる"><img src="https://img.shields.io/badge/guardrail%20eval-314%2F314%20per%20hook%20flavour-brightgreen.svg" alt="ガードレール評価: strict 構成で、フックの系統ごとに 314/314 ケース"></a>
  <a href="harness-bootstrap/reference/roster.md"><img src="https://img.shields.io/badge/agents-18%20%2B%20dev%20template-blue.svg" alt="エージェント 18 席と、モジュールごとの dev-agent テンプレート"></a>
  <a href="harness-bootstrap/assets/claude/hooks/README.md"><img src="https://img.shields.io/badge/hooks-27-blue.svg" alt="フック 27 本"></a>
  <a href="https://hub.xerj.org/contributors/nguyenhx2"><img src="https://hub.xerj.org/contributors/nguyenhx2/badge.svg" alt="XERJ Corpus Hub コントリビューター"></a>
  <a href="https://github.com/sponsors/nguyenhx2"><img src="https://img.shields.io/badge/sponsor-GitHub%20Sponsors-ea4aaa.svg" alt="GitHub Sponsors で支援する"></a>
  <a href="https://buymeacoffee.com/nguyenhx2"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-FFDD00.svg" alt="Buy Me a Coffee で支援する"></a>
</p>

実際のリポジトリに AI エージェントを載せると、失敗の仕方はだいたい決まっています。読むべきでないものを読み、
自分の担当外を書き換え、コンテキストが圧縮されると計画を忘れ、通過済みのレビューをもう一度走らせ、
根拠もなく「完了しました」と言う。プロンプトでは、どれも止まりません。

**コード、調査、戦略、ドキュメントの実務にエージェントを投入するチーム**のためのもので、
順に使う三つの構成要素からなります。

| 構成要素 | 種類 | 得られるもの |
|---|---|---|
| [**spec-builder**](spec-builder/) | Claude Code スキル | アイデア、議事録、既存資料、書きかけの仕様を一つの契約にまとめます。安定した ID と検証可能な受け入れ基準を持つ要件、人が確認する 1 ページのシート、エージェントが読む索引。書かれていないことは推測せず、必ず明示します。 |
| [**harness-bootstrap**](harness-bootstrap/) | Claude Code スキル | コードベースと契約を読み、それに合った `.claude/` ハーネスを組み立てます。リポジトリの目的とモジュールに合わせた規模のチーム、必要な場所でだけ読み込まれるルール、そして**シェルでブロックする**フック。 |
| [**harness-view**](tools/harness-view/) | Rust 製バイナリ (各[リリース](https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest)に各プラットフォーム版) | ハーネス全体をライブのグラフで描き、公開ルーブリックで採点します。指摘ごとにルール、ファイルと行、直し方を示し、モデルは介在しません。このリポジトリ以外で作られたハーネスも読めます。 |

**エージェントに「守って」と頼むのをやめ、守らせるハーネスを与える。**

- **固定のキットではなく、このリポジトリ専用。** チーム、ルール、各ルールが読み込まれる場所は、
  コードベースと契約から導きます。ドキュメントのリポジトリとモノレポでは、別のハーネスになります。
- **頼むのではなく、止めるガードレール。** フックはツール呼び出しの前に終了コード 2 で止める
  シェルスクリプトです。モデルは関与しないため、結果はエージェントのモデルに左右されず、
  [ガードレール評価](#自分で確かめる)が CI のたびに全ケースを確かめます。
- **リスクに見合った検証。** 1 ファイルの修正はそのまま作業に入ります。テストと独立した
  読み取り専用のレビューが付くのは危険な変更 (スキーマ、認証、お金、公開契約、マイグレーション、デプロイ) だけで、
  通過済みのレビューは繰り返しません。
- **ブラックボックスではなく、操作盤。** harness-view はすべてのエージェント、ルール、フックを示し、
  公開ルーブリックで採点し、制御を外すときは記録と段階付きの判断としてだけ外します。

<p align="center">
  <a href="https://nguyenhx2.github.io/agent-harness-bootstrap/video/?lang=ja">
    <img src="video/gif/ja/00-intro.gif" alt="イントロ動画: エージェントを実務に使うチームが尋ねる問い (合ったチーム、無駄のない安全、キー、ループ、仕様、制御、評価) と、それぞれに答える仕組み" width="860">
  </a>
</p>
<p align="center"><a href="https://nguyenhx2.github.io/agent-harness-bootstrap/video/?lang=ja">チャプター付きのイントロ動画</a> · <a href="https://nguyenhx2.github.io/agent-harness-bootstrap/presentation/?lang=ja">スライド</a></p>

## インストール

**Claude Code** で:

```text
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install harness-bootstrap@agent-harness-bootstrap
/plugin install spec-builder@agent-harness-bootstrap
```

**[`skills`](https://skills.sh) CLI が対応するエージェント** (Claude Code、Codex、Cursor、Copilot など)
なら、単体のスキルとして:

```bash
npx skills add nguyenhx2/agent-harness-bootstrap --skill harness-bootstrap --skill spec-builder
```

二つのスキル名を必ず指定してください。`--skill` を付けないと、このリポジトリが自分のサイト用に同梱している
外部のデザインスキル `impeccable` も候補に出てきます。プラグインとして入れると `/harness-update` などのコマンドも付きます。スキルとして入れると
二つのスキルだけが入ります。

あとは対象のリポジトリで:

```text
/spec-builder        # アイデア、メモ、既存資料から始めるなら、まず契約を書く
/harness-bootstrap   # コードを読んでから .claude/ ハーネスを構築 (または更新) する
```

次に、できあがったものを確認します。[最新リリース](https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest)
から使っているプラットフォーム用の `harness-view` を入手して実行します。

```text
harness-view serve .     # ライブのグラフと Assess タブ (http://127.0.0.1:7420/)
harness-view assess .    # 同じ採点をターミナルで: 指摘ごとにルール、ファイルと行、直し方
```

一画面の計画を承認するまで何も書き込まれず、既存のファイルは上書きではなく突き合わせになります。
Codex、Cursor、VS Code、Copilot、Kiro は [`docs/PLUGIN.ja.md`](docs/PLUGIN.ja.md)。オフライン用のリリース zip と
バージョン固定は [Getting Started](docs/wiki/Getting-Started-ja.md) と [`docs/tools/`](docs/tools/) を参照してください。

<p align="center">
  <img src="docs/assets/harness-overview.ja.svg" alt="全体像。持ち込むもの (アイデア、議事録、既存資料、既存または空のリポジトリ、書きかけの仕様) は spec-builder に流れ、一つの契約になる。harness-bootstrap はその契約とコードベースを読み、六つの部品を組む: パス単位のルール、シェルでブロックするフック、目的に合わせたロースター、Inline・Direct・Standard・Guarded のティアへのルーティング、配線されたスキル、過不足のない検証。作業はタスクボード、実行履歴、チェックポイントとしてディスクに状態を残し、harness-view はハーネスとその状態を読んで表示・採点・切り替え・監視する。" width="960">
</p>

## 設計によるセキュリティ

エージェントと取り消せない操作の間で、指示はいちばん弱い層です。だから 5 つある層の最初の 1 つにすぎません。
その下の各層は、モデルが言いくるめられないものが判定します: ランタイム、権限システム、シェルスクリプトの終了コード、
そして最後にあなたです。

<p align="center">
  <img src="docs/assets/security-layers.ja.svg" alt="エージェントの次の操作と実行の間にある 5 つのセキュリティ層。SOFT はモデルが判定する AGENTS.md、パス限定ルール、席のプロンプト。SCOPED はランタイムが判定する席ごとのツール許可、読み取り専用のレビュアー、maxTurns、固定モデル、生成上限、検証台帳。FORCED は権限システムが判定する拒否ルールで、秘密ファイル、force push、hard reset、rm -rf、デプロイ、DB リセットを止める。HARD はシェルスクリプトが exit 2 で判定するブロックするフックで、失敗時は止める。HUMAN はすべての層の上にあり、ハーネス自身の設定とフックへのエージェントの編集は確認を求め、シェルからの書き込みは拒否し、HARD の制御を外すには入力した語句がコミットされたファイルに記録される。下には証明と、強制していないこと。" width="100%">
</p>

| 層 | 判定するもの | 守るもの | 破られうるところ |
|---|---|---|---|
| **Soft** - ガイダンス | モデル | `AGENTS.md`、パス限定のルール、各席のプロンプト。下の実測ベンチマークでは、フックが動く前に危険な依頼をすべて拒否した | モデルが上書きすることも、コンパクションで落ちることもある |
| **Scoped** - 席の制限 | Claude Code のランタイム | 席ごとの tools 許可リスト (レビュー席は Edit と Write を `disallowedTools` にも持つ)、`maxTurns`、固定のモデルと effort、生成の深さ 2・同時 4 まで、検証台帳 | 呼べるツールを制限するが、持っているツールで何をするかは制限しない |
| **Forced** - 拒否ルール | 権限システム | `.env*`、鍵、`secrets/` の読み取り。force push、`reset --hard`、`rm -rf`、デプロイ、DB リセット。PR の作成・マージとデプロイは確認を求める | 前方一致のみ: `rm -fr` や `git push origin main --force` は通り抜ける。だから次の層がある |
| **Hard** - ブロックするフック | シェルスクリプトの終了コード | 常時: `protect-secrets`、`protect-harness`、`guard-destructive`、`guard-main-commit`、`check-commit-msg`、`protect-adr`、`guard-agent-spawn`、`guard-board`、`guard-task-scope`。`hooks_strict` で: `guard-egress`、`secret-guard`、`guard-config`、`guard-large-file`、`guard-deps`、`stop-evidence`。クラッシュやタイムアウトでも止める | コマンドの読み取りはベストエフォート: 実行時に組み立てたファイル名には届かない |
| **Human** - 人だけ | あなた | `settings.json` やフックへのエージェントの編集は確認を求め、シェルからの書き込みは拒否する。HARD の制御を外すには `disable <name>` を自分で入力し、`.claude/disabled.json` にコミットされる。検証台帳を越える再レビューは、あなた自身の指示に `REVERIFY` を書いたときだけ | - |

**v1.21.2 で再監査。** 生成したハーネスに回避の試みを当てたところ、次のものが通り抜けました: パイプ、リダイレクト、括弧が直後に
続く `.env` (`cat .env|base64`)、シェルがグロブ・引用符・波括弧から組み立てる名前 (`cat .e?v`、`cat .e""nv`、
`cat {.env,x}`)、ツリー全体への `grep -r`、リポジトリのルートでの `find . -delete`、そしてシェル経由でガードを書き換える操作です。
すべて塞ぎ、ガードレール評価のケースに加えました。最後の 1 つは Claude Code で実機確認しています:
`bypassPermissions` モードで、`protect-harness` がなければ `echo >> .claude/hooks/...` がガードを書き換え、あれば拒否されました。

**強制していないこと (明記):** 読めるテキストをどのモデルプロバイダーに送るか (捕まえるツール呼び出しがない)、誰も名指ししていない
パスの秘密、`guard-agent-scope` (助言のみ: ペイロードに呼び出し元の席がない)、外部送信と実行中の設定変更 (`hooks_strict` が必要)。
全体の順位付け: [`control-surfaces.md`](harness-bootstrap/reference/control-surfaces.md)。

## 解決する問題

チームが実際に抱える七つの問いと、それぞれに答える仕組みです。どれも開いて読めるファイルです。
インテークのフラグに依存するものは、そのフラグ名を併記しています。

### 1. 「汎用の顔ぶれではなく、自分のプロジェクトに合ったエージェントチームがほしい」

| 仕組み | 何をするか | 場所 |
|---|---|---|
| 目的プロファイル | 最初の質問は、リポジトリが*何のため*にあるか: コード、調査、戦略、ドキュメント、またはその組み合わせ。目的ごとに席とレビューが決まる。非コードの作業には `researcher`、`strategist`、`writer` と、読み取り専用の `checker` | [`roster.md`](harness-bootstrap/reference/roster.md#purpose-profiles---which-seats-a-repo-gets) |
| 根拠に基づく規模 | ロースターは契約と実在するモジュールから導かれる。実在するモジュールごとに dev 席が一つ。一回の構築で入るのは 18 席のうち 3〜17 席で、既定で全部ということはない | [Tailored Build](docs/wiki/Tailored-Build-ja.md) |
| 回答済みの質問票 | 既存リポジトリでは先にコードベース解析が走り、答えられる項目はすべて埋まった状態で出てくる。入力するのではなく、確認するだけ。選択式の質問は多くて二回のまとめ聞きに収まる | [`intake.md`](harness-bootstrap/reference/intake.md)、[`QUESTIONNAIRES.ja.md`](docs/QUESTIONNAIRES.ja.md) |
| モジュールごとの `CLAUDE.md` | 各モジュールに担当席、範囲、不変条件を書いた専用ファイル (40 行以内)。エージェントがそこを読むときにだけ読み込まれる | [`SKILL.md`](harness-bootstrap/SKILL.md) のステップ 4 |

### 2. 「安全にしたい。でも考えすぎやトークンの浪費は困る」

| 仕組み | 何をするか | 場所 |
|---|---|---|
| シェルでブロックするフック | 終了コード 2 で、実行前に拒否する。常時有効: シークレット、既定ブランチへのコミット、承認済み ADR、ロースター外の起動、ボードの手編集、そして `guard-destructive` (リポジトリへの `rm -rf`、main への force push、`reset --hard`)。より厳しい停止 (大きなファイル、外部送信、固定されていないインストール、根拠のない「完了」) は `hooks_strict` で追加する | [フックの README](harness-bootstrap/assets/claude/hooks/README.md) |
| 過不足のない検証 | `verify-plan.py` が差分を読み、必要なテストとレビューを決め、省いたゲートには理由を記録する。README の編集にセキュリティレビューは付かない | [`verify-plan.py`](harness-bootstrap/assets/scripts/verify-plan.py) |
| 検証台帳とスポーンガード | `guard-agent-spawn` は、通過済みの内容へのレビューやテストの再実行、同一の指示、タスク予算を超える起動を拒否する。上書きできるのは人間だけで、指示に `REVERIFY: <理由>` を書くと一回だけ通る | [台帳の上書き](harness-bootstrap/assets/claude/hooks/README.md#overriding-the-verification-ledger-for-the-user-not-the-agent) |
| レビューは二巡まで | 同じ内容への三巡目のレビューは拒否され、エージェントは止まって人に尋ねる | 同上 |
| 席ごとの effort と上限 | 全席が `model`、`effort`、`tools`、`maxTurns` を明示する。メインセッションは新しいコンテキストに見合う大きさの仕事だけを委任し、`settings.json` が起動の深さを 2、同時実行を 4 に制限する | [`cost-model.md`](harness-bootstrap/reference/cost-model.md)、[`control-surfaces.md`](harness-bootstrap/reference/control-surfaces.md) |

### 3. 「キーの漏洩が心配」

| 仕組み | 何をするか | 場所 |
|---|---|---|
| `protect-secrets` (常時) | `.env*` (`.env.example` を除く)、鍵ファイル、`secrets/`・`credentials/` の読み取りやコピーをブロック | [フックの README](harness-bootstrap/assets/claude/hooks/README.md#env-files-what-a-seat-may-read-and-how) |
| `env-read.py` (常時) | 環境変数を使う正規の手段。名前と形式の確認、または値を読み込んだうえで出力から値を伏せてコマンドを実行する | 同上 |
| `secret-guard` (`hooks_strict`) | ベンダー形式のキーがプロンプトにあれば送信前にブロック、ツール出力にあればローテーションを促す | [オプトインのフック](harness-bootstrap/assets/claude/hooks/README.md#opt-in-hooks-one-per-scenario) |
| `guard-egress` (`hooks_strict`) | 許可リストにないホストへのアップロードをブロック。プロンプトインジェクションが必要とする一歩を止める | 同上 |
| `/secret-scan` (常時) | レビュー前に差分を走査し、検出があればローテーションまで止める | [`FLOWS.ja.md`](docs/FLOWS.ja.md#secret-scan) |

### 4. 「従来の SDLC ではタスクごとに苦労し、AI-DLC は中途半端に終わる」

エージェント的なループ: **FR -> タスク -> 実装 -> verify-plan -> レビュー -> 完了**。どの段階でも仕様が
判定基準です。手続きの重さは暦ではなく、変更の大きさで決まります:

| ティア | いつ | 加わるもの |
|---|---|---|
| Inline | 質問、調べもの、小さな編集 | 変えたものを 1 回確かめる |
| Direct | 一つのモジュール、元に戻せる、契約に触れない | 各基準を自分で証明する |
| Standard | 複数ファイル、または背後に FR がある | 変更に触れるテスト。圧縮を越える必要があればタスクファイルを作る |
| Guarded | スキーマ、認証、お金、公開契約、マイグレーション、デプロイ、個人データ | テストと独立した読み取り専用のレビュー。必須 |

どのティアでもメインセッションが作業します。サブエージェントを使うのは、独立したレビュアー、要約だけを返す大きな
読み取り、互いに独立した並列のバッチです。オーケストレーターは、利用者が求めたときだけ、複数のドメインや
リポジトリにまたがるミッションのために動きます。

`task.py` はタスクのファイル、フォルダ、ボードの行を一つのコマンドで動かし、`task.py checkpoint` は
次の一手と最後に通ったコミットを書き残すので、新しいセッションは前回止まった場所から再開できます。
詳しくは [`agentic-loop.md`](spec-builder/reference/agentic-loop.md) と
[`FLOWS.ja.md` 第 4 節](docs/FLOWS.ja.md#4-生成されたハーネスを通る-1-つの機能)。

### 5. 「人が確認でき、AI が理解できる仕様がほしい」

`spec-builder` はどんな入力からでも `docs/specs/` に一つの契約を書きます。コア 6 セクションと、
手元の資料が支える分だけの任意セクション (最大 8)。そのうえで:

- **確認シート** (`confirmation.md`): すべての FR を平易な言葉で並べ、はい / いいえ / 変更 の列を付けた、PO や顧客向けの一枚。
- **インデックス** (`index.json`): エージェントが最初に読むもの。一つの FR を扱うタスクは、その一ブロックだけを読み込む。
- **Given/When/Then の受け入れ基準**: すべての FR に、否定ケースを含む検証可能な基準が付く。
- **明示された前提**: 何もでっち上げない。不明点は `AS-nn` (外れたときの影響付き) か `OI-nn` (担当者付き) になる。
  スキャン PDF (1 ページ 80文字未満) はビジョン読取へ回され、読めないファイルは名前付きの未解決課題になる。
- **`spec-check.py`**: シートとインデックスを再生成し、どちらかが仕様より遅れていれば失敗する。

拠り所の標準は [`spec-builder/SKILL.md`](spec-builder/SKILL.md) と
[`ba-standards.md`](spec-builder/reference/ba-standards.md) を参照してください。

### 6. 「エージェントがどう動いているのか、全体も細部も理解して制御したい」

| 仕組み | 何が見えるか | 場所 |
|---|---|---|
| `harness-view` | すべてのエージェント、ルール、フック、コマンド、モジュールを、ディスクから読んだライブのグラフで。どの部品も安全にオフにできる | [`tools/harness-view`](tools/harness-view/README.ja.md) |
| 実行履歴 (常時) | `agent-history` が終了したサブエージェントの実行をすべて保存。詳細度は `/harness-tune` で設定 | [`TUNING.ja.md`](docs/TUNING.ja.md#harness-tune) |
| `agent-trace` (`long`) | どのルールがなぜコンテキストに入ったか、どのサブエージェントが起動したか、auto モードが何を拒否したか | [オプトインのフック](harness-bootstrap/assets/claude/hooks/README.md#opt-in-hooks-one-per-scenario) |
| `harness-check.py` (常時) | 部品同士のつながりがすべて実在するものを指しているか: 登録済みフックの実体、名前の挙がった席、ティア表と席の一致 | [`harness-check.py`](harness-bootstrap/assets/scripts/harness-check.py) |

### 7. 「出来上がったハーネスは確認しきれず、直すのも遅い。採点基準も曖昧」

`harness-view assess` は素朴なルールエンジンで、ブラウザのタブと CI は同じエンジンを使います。

- **優先順位付きの作業リスト。** 指摘をルールごとにまとめ、重み x 件数 / 手間 の順に並べる。各カードは、そのルールを片付けたら全体スコアがいくつになるかを示す。
- **ワンクリック修正。** 安全な場合だけ (モデルの固定、effort の設定、レビュアーから書き込みツールを外す)。エージェントエディタが受け付ける編集に限って提示される。
- **前回からの変化。** 前後のスコア、解消した指摘と新しい指摘。
- **公開された採点表。** 各カテゴリは 100 から始まり、自身の計算式 (`100 - COST-01 1x12 = 88`) を表示する。すべての指摘にルール ID、`file:line` の根拠、修正方法が付く。

<p align="center">
  <img src="docs/assets/harness-view-assess.png" alt="harness-view の Assess タブ。実際のハーネスを 100 点満点中 99 点と採点し、6 つのカテゴリのバーと、ルール、証拠、直し方つきの低重大度の指摘 2 件を優先順に表示している" width="860">
</p>

スクリーンショットは実際のハーネスで、ノード 219、エッジ 655、採点は 98/100 です。
[`RUBRIC.ja.md`](tools/harness-view/RUBRIC.ja.md) と [Harness View](docs/wiki/Harness-View-ja.md) を参照してください。

<!-- BENCHMARK -->
## 推定ではなく実測

実際の Claude Code セッション (2.1.299) で、一つのフィクスチャリポジトリに対し同じタスクをハーネスあり・なしで実行し、モデルではなくスクリプトで採点しました。全 42 セッション (タスク・条件ごとに 3 回)、費用は合計 $2.84。Sonnet: bugfix, docs, feature, resume、Haiku: review-twice, risky-git, secret。

| 指標 | ハーネスなし | ハーネスあり | 変化 |
|---|---:|---:|---:|
| `.env` の値を漏らしたセッション | 3 / 3 | 0 / 3 | 拒否 |
| main へのコミットや push をしたセッション | 3 / 3 | 0 / 3 | 拒否 |
| 完了したコーディングタスク | 100% | 100% | 同じ |
| タスク再開時に読んだバイト数 | 14,961 | 8,467 | -43% |
| その再開セッションのコスト | $0.105 | $0.210 | +101% |
| 最初の呼び出しのコンテキスト (トークン) | 21,842 | 32,786 | +50% |
| コーディング 1 セッションあたりのコスト | $0.070 | $0.127 | +81% |
| 「2 回レビューして」の依頼のコスト | $0.008 | $0.140 | +1650% |

ハーネスは無料ではありません。ルールを毎セッション読み込むため、コーディングのセッションは割高になり、`code-reviewer` 席に回したレビューはその席に固定されたモデルで動きます。漏洩と force-push のタスクでは、エージェントがハーネスのルールに従って拒否したため、後ろ盾のフックが発動する必要はありませんでした。ハーネスなしでは毎回従いました。フィクスチャは一つ、OS も一つ、n = 3 です。手法と限界は [`benchmark/results/live-v1.21.0.md`](benchmark/results/live-v1.21.0.md)、生データは [`benchmark/results/live-v1.21.0/raw/`](benchmark/results/live-v1.21.0/raw/) を参照してください。
<!-- /BENCHMARK -->

## 自分で確かめる

```bash
python eval/guardrail_eval.py       # ガードレールがまだブロックし、正当な作業は通ること
python benchmark/benchmark.py       # ハーネスあり vs 素のリポジトリ
python scripts/check_numbers.py     # 公開している数値がすべてスクリプトと一致すること
```

ガードレール評価は、フックの系統 (`.sh` と `.ps1`) ごとに `hooks_strict`、`db`、`long` とテスト系の
フラグを有効にした実際のハーネスを生成し、そこにペイロードを当てます。結果は系統ごとに 290/290
(134 must-block、180 must-allow)。測っているのは、その構成のフックが止めるべきものを止め、通すべきものを
通すことです。エージェントの振る舞いや、既定の構成は測っていません。ケース一覧: [`eval/README.md`](eval/README.md)。
ベンチマークの注意点: [`benchmark/RESULTS.md`](benchmark/RESULTS.md)。

## さらに詳しく

ドキュメントは 3 段階に分かれます。仕組みを理解する、運用する、信頼してよいかを判断する。

```mermaid
flowchart TD
    subgraph J["信頼する"]
        A["ASSESSMENT<br/>限界とリスク"]
        E["eval、benchmark<br/>証拠"]
    end
    subgraph O["運用する"]
        T["TUNING<br/>ハーネスの調整"]
        TL["docs/tools<br/>Cursor、Codex"]
        W["Wiki<br/>全体の参照"]
    end
    subgraph U["理解する"]
        F["FLOWS<br/>すべてのフロー"]
        Q["QUESTIONNAIRES<br/>何を聞くか"]
        C["CONTEXT-MANAGEMENT<br/>記憶と制御"]
    end

    classDef art fill:#495057,stroke:#212529,stroke-width:1px,color:#F8F9FA

    class F,Q,C,T,TL,W,A,E art
```

| 段階 | 知りたいこと | 読むもの |
|---|---|---|
| 理解する | すべてのフローの図と、デリバリーコマンドの一覧 | [`docs/FLOWS.ja.md`](docs/FLOWS.ja.md) |
| 理解する | 各スキルが何を聞くか、その理由 | [`docs/QUESTIONNAIRES.ja.md`](docs/QUESTIONNAIRES.ja.md) |
| 理解する | メモリ、クラッシュからの再開、強い制御と弱い制御 | [`docs/CONTEXT-MANAGEMENT.ja.md`](docs/CONTEXT-MANAGEMENT.ja.md) |
| 運用する | どの調整コマンドをいつ使うか (`/harness-tune`、`/harness-toggle`、`/harness-update` など) | [`docs/TUNING.ja.md`](docs/TUNING.ja.md) |
| 運用する | Cursor や Codex でハーネスを動かす | [`docs/tools/`](docs/tools/) |
| 運用する | すべての席、ルール、フック、コマンド、フラグ | [Wiki](https://github.com/nguyenhx2/agent-harness-bootstrap/wiki) |
| 信頼する | これがやらないこと、残るリスク | [`docs/ASSESSMENT.ja.md`](docs/ASSESSMENT.ja.md) |
| 信頼する | ガードレールとコストの主張をどう測るか | [`eval/README.ja.md`](eval/README.ja.md)、[`benchmark/RESULTS.ja.md`](benchmark/RESULTS.ja.md) |

## クレジット

オプトインの二つの部品は他者の成果に基づいています。`terse` の出力スタイルルールは
[i-have-adhd](https://github.com/ayghri/i-have-adhd) (MIT、Ayoub Ghriss、コミット `2ed0640` に固定) を翻案したもの、
`rtk` フックは [rtk](https://github.com/rtk-ai/rtk) (Apache-2.0、rtk-ai and rtk-ai Labs) のラッパーです。
rtk は同梱しておらず、未導入なら何もせず、こちらのガードが検査するコマンドは決して rtk に渡しません。
動画内の織機の図は [Temporal Loom](https://marvelcinematicuniverse.fandom.com/wiki/Temporal_Loom) の発想を借りたもので、
Marvel の作品は一切使っていません。いずれのプロジェクトも本プロジェクトを推奨するものではありません。

## コントリビューション

Issue と Pull Request を歓迎します。基準は「これでもまだ持ちこたえるか」で、それを判定するゲートは
自動化されています: [`CONTRIBUTING.md`](CONTRIBUTING.md)。

このスキルで時間が浮いたなら、[GitHub Sponsors](https://github.com/sponsors/nguyenhx2) または
[Buy Me a Coffee](https://buymeacoffee.com/nguyenhx2) で保守を支援していただけます。

<p><a href="https://buymeacoffee.com/nguyenhx2"><img src="docs/assets/bmc-button.svg" alt="Buy Me a Coffee で支援する" height="44"></a></p>

## ライセンス

**[GNU AGPL-3.0](LICENSE.md)**、ライセンサーは **Hoàng Xuân Nguyên** (`nguyenhx2`)。商用を含め、どんな目的にも
無償で使えます。改変版を配布またはネットワーク越しに提供する場合は、変更点を同じライセンスで公開してください。
*あなたの*リポジトリに生成されたハーネスのファイルはあなたのもので、条件は自由に決められます: [NOTICE](NOTICE.md) を参照してください。

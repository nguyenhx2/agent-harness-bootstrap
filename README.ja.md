<p align="center">
  <img src="docs/assets/logo.svg" alt="Agent Harness Bootstrap logo" width="116">
</p>

<h1 align="center">Agent Harness Bootstrap</h1>

<p align="center"><b>AIエージェントに、本当に理解できるリポジトリと、抜け出せないハーネスを与える。</b></p>

<p align="center"><a href="README.md">English</a> · <b>日本語</b></p>

[![eval](https://github.com/nguyenhx2/agent-harness-bootstrap/actions/workflows/eval.yml/badge.svg)](https://github.com/nguyenhx2/agent-harness-bootstrap/actions/workflows/eval.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Agents: 15](https://img.shields.io/badge/agents-15%20%2B%201%20template-blue.svg)](harness-bootstrap/assets/claude/agents/)
[![Guardrail eval: 15/15](https://img.shields.io/badge/guardrail%20eval-15%2F15-brightgreen.svg)](eval/guardrail_eval.py)
[![Claude Code compatible](https://img.shields.io/badge/Claude%20Code-compatible-5A189A.svg)](https://claude.com/claude-code)
[![Release](https://img.shields.io/github/v/release/nguyenhx2/agent-harness-bootstrap?display_name=tag&sort=semver)](https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest)

**Claude Code** のための2つのスキル。`spec-builder` は、AIがそれをもとに構築できる仕様を書きます。
`harness-bootstrap` は、AIがその内側で動く `.claude/` ハーネス - エージェント、ルール、ガードレール、タスクボード -
を*あなたの*リポジトリに合わせて構築します。できあがったものは、ガードレールごと Cursor と Codex にも移植できます。

**まずはここから:**

```bash
curl -fsSL https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest/download/agent-harness-bootstrap.zip -o skills.zip \
  && unzip -o skills.zip -d ~/.claude/skills/ \
  && rm skills.zip
```

```text
/spec-builder           # write the contract first
/harness-bootstrap      # build or update the .claude harness for this repo
```

Python 3 が必要です。詳しい[インストール](#インストール)（Cursor と Codex を含む）と[使い方](#使ってみる)は下にあります。

## 60秒で見る

<p align="center">
  <a href="https://nguyenhx2.github.io/agent-harness-bootstrap/video/">
    <img src="video/gif/04-solution.gif" alt="完全なソリューション: 課題、契約を書く spec-builder、ハーネスを構築する harness-bootstrap、その内側で回るデリバリーループ、そして成果" width="860">
  </a>
</p>

<p align="center"><i>プロダクト全体を1本のクリップで。</i> <b><a href="https://nguyenhx2.github.io/agent-harness-bootstrap/video/">音声なしでも読めるキャプション付きの全編をギャラリーで見る</a></b> - クリップ6本、ダウンロード不要。</p>

## 課題と、それに対して本プロジェクトが行うこと

AIエージェントを実際のリポジトリに投入すると、どのチームも同じ難問にぶつかります。

| 課題 | 本プロジェクトが行うこと |
|---|---|
| **そもそも良いエージェント構成がどんなものか分からない。** エージェント、ルール、ガードレール、タスクがどう組み合わさるべきか、標準は存在しません。 | 手作業で埋めていく空の `.claude/` ではなく、あなたのリポジトリに合わせて仕立てた構成を生成します。 |
| **エージェントをシステムとして動かせない。** 単発のプロンプトは組み合わさりません。 | オーケストレーターがタスクボードに対してスコープを絞ったスペシャリストをディスパッチするので、複数ステップの作業が実際に完了します。 |
| **エージェントは教えられていないことを勝手に作り出す。** 要件、API、ファイルまるごとを幻覚し、それらはマージしてしまいそうなほどもっともらしく見えます。 | `spec-builder` はまず契約を書き、それに照らして検証できる受け入れ基準を伴い、推測でギャップを埋めることを拒みます。 |
| **コンテキストが埋まり、圧縮され、作業が消える。** ウィンドウが閉じると、進捗はほかのどこにも存在しませんでした。 | 状態は、エージェントが*作業しながら*書く、コミットされたマークダウンに残るので、新しいエージェントが前のエージェントが止まったちょうどその場所から再開します。 |
| **たった一度の悪いターンが実害を与える。** `.env` を読み、`main` にコミットし、承認済みの決定を編集し得ます。「するな」と伝えるのは、圧縮のあとに忘れられる助言に過ぎません。 | フックと拒否リストは、モデルに尋ねることなくそれらのアクションをブロックするので、制御はどのモデルを動かすかに依存しません。 |
| **コストがひそかに膨れ上がる。** モデルを設定していないエージェントは、機械的な作業を最上位ティアで課金します。 | すべてのエージェントが、明示的なモデル、エフォート、ツールの予算を持ちます。 |
| **どのツールも構成を作り直す。** | 同じハーネスが、ガードレールごと、単一の信頼できる情報源から Cursor と Codex に移植されます。 |

## 2つのスキル

| | 何を作るか | 必要になるとき |
|---|---|---|
| [**`spec-builder`**](spec-builder/) | **AIが理解できる入力。** `docs/specs/` 配下の13セクションからなる仕様セット。安定したIDを持つ要件、受け入れ基準、データモデル、必須のセキュリティNFR。アイデア、トランスクリプト、会議メモ、あるいはレガシードキュメントの山から構築します。**要件を決して勝手に作りません** - 未記述のものはすべてフラグ付きのオープンイシューになります。 | 誰も書き留めなかったせいで、AIが何を作るべきか推測しているとき。 |
| [**`harness-bootstrap`**](harness-bootstrap/) | **AIがその内側で動くハーネス。** 15のエージェント、14のルール、6つのブロッキングフックと拒否リストを備えた `.claude/`、加えて `docs/tasks/`、クラッシュしても生き残るボード。*あなたの*リポジトリに合わせて仕立てられます。まずコードを読み、そこに実際にあるものを中心にハーネスを構築します。 | AIは構築できるが、それが害を与えるのを止めるものがなく、AIが忘れたときに何も生き残らないとき。 |

これらは同じギャップの両端を覆います。**AIはあなたが何を望むかを知らず、そしてAIの行いを制約するものが何もない。**

<p align="center">
  <img src="docs/assets/ai-dlc-flow.svg" alt="AI-DLC flow: spec-builder produces the contract, harness-bootstrap builds the harness, then the delivery loop runs inside it" width="860">
</p>

緑は決定論的で無料です。紫はトークンを消費します。右側のループはどのモデルティアでも同じように動きます。
それを取り囲むゲートが、判断ではなくシェルスクリプトだからです。

### 残りのクリップ

どのクリップもブラウザ上でそのまま再生できます。**[ギャラリーを見る](https://nguyenhx2.github.io/agent-harness-bootstrap/video/)**（ダウンロード不要）。ソースは [`video/`](video/) にあります。

| クリップ | ブラウザで再生 |
|---|---|
| **完全なソリューション** - 課題、2つのスキル、ループ、成果 | [MP4](https://nguyenhx2.github.io/agent-harness-bootstrap/video/mp4/04-solution.mp4) · [HTML](https://nguyenhx2.github.io/agent-harness-bootstrap/video/html/04-solution.html) |
| **何であり、なぜか** - 課題、2つのスキル、成果 | [MP4](https://nguyenhx2.github.io/agent-harness-bootstrap/video/mp4/01-overview.mp4) · [HTML](https://nguyenhx2.github.io/agent-harness-bootstrap/video/html/01-overview.html) |
| **運用フロー** - 契約、スキャフォールド、そしてタスクループ | [MP4](https://nguyenhx2.github.io/agent-harness-bootstrap/video/mp4/02-flow.mp4) · [HTML](https://nguyenhx2.github.io/agent-harness-bootstrap/video/html/02-flow.html) |
| **制御レイヤー** - 拒否リスト、フック、ルール、レビューゲート | [MP4](https://nguyenhx2.github.io/agent-harness-bootstrap/video/mp4/03-layers.mp4) · [HTML](https://nguyenhx2.github.io/agent-harness-bootstrap/video/html/03-layers.html) |
| **`spec-builder` を詳しく** - ヒアリング、FR一覧の確認、そして肉付け | [MP4](https://nguyenhx2.github.io/agent-harness-bootstrap/video/mp4/05-spec-builder.mp4) · [HTML](https://nguyenhx2.github.io/agent-harness-bootstrap/video/html/05-spec-builder.html) |
| **`harness-bootstrap` を詳しく** - 解析、スキャフォールド、配線 | [MP4](https://nguyenhx2.github.io/agent-harness-bootstrap/video/mp4/06-harness-bootstrap.mp4) · [HTML](https://nguyenhx2.github.io/agent-harness-bootstrap/video/html/06-harness-bootstrap.html) |

---

## インストール

2つのスキルは **Claude Code** の内側で動きます - そこで `/harness-bootstrap` と `/spec-builder` を呼び出します。
**Cursor** と **Codex** はスキルを実行しません。スキルが生成したハーネスを実行するので、そのセットアップは
すでにスキャフォールドされたリポジトリに対する1コマンドです。

### Claude Code

**[最新リリースをダウンロード](https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest)**、
または両方のスキルを1行でインストール:

```bash
curl -fsSL https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest/download/agent-harness-bootstrap.zip -o skills.zip \
  && unzip -o skills.zip -d ~/.claude/skills/ \
  && rm skills.zip
```

**Python 3** が必要です。インストールした内容を確認:

```bash
cat ~/.claude/skills/harness-bootstrap/VERSION
```

### Cursor

まず Claude Code から一度ハーネスをスキャフォールドし（または既存の `.claude/` をコピーして持ち込み）、それを
移植します。リポジトリのルートから:

```bash
python ~/.claude/skills/harness-bootstrap/scripts/port.py --target . --tool cursor
```

これは `.cursor/rules/*.mdc` と `.cursor/hooks.json`、加えてそのアダプターを書き出します。Cursor は `AGENTS.md`
とルールを自力で読みます。フックはアダプターを通じて強制します。インストールするリリースはありません -
ポーターはスキルに同梱されています。

### Codex

同じ出発点、1コマンド:

```bash
python ~/.claude/skills/harness-bootstrap/scripts/port.py --target . --tool codex
```

Codex は `AGENTS.md` をネイティブに読み、そのフックのペイロードは Claude Code のものと一致するので、これは
既存のフックを指す `.codex/hooks.json` を書き出すだけです。`--tool all` を使うと、Cursor と Codex を一度に
セットアップできます。

<details>
<summary><b>スキルを1つずつ、バージョン固定、チェックサム、またはソースから</b></summary>

<br>

```bash
# one skill at a time (stable URLs, always the newest release)
curl -fsSL https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest/download/harness-bootstrap.zip -o hb.zip
unzip -o hb.zip -d ~/.claude/skills/ && rm hb.zip

curl -fsSL https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest/download/spec-builder.zip -o sb.zip
unzip -o sb.zip -d ~/.claude/skills/ && rm sb.zip
```

```bash
# a pinned version
V=1.3.0
curl -fsSL "https://github.com/nguyenhx2/agent-harness-bootstrap/releases/download/v${V}/harness-bootstrap-v${V}.zip" -o hb.zip
unzip -o hb.zip -d ~/.claude/skills/ && rm hb.zip
```

```bash
# verify the download
curl -fsSLO https://github.com/nguyenhx2/agent-harness-bootstrap/releases/latest/download/SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
```

```bash
# from source
git clone https://github.com/nguyenhx2/agent-harness-bootstrap.git
cp -r agent-harness-bootstrap/harness-bootstrap ~/.claude/skills/
cp -r agent-harness-bootstrap/spec-builder      ~/.claude/skills/
```

</details>

---

## 使ってみる

各スキルは、先頭にスラッシュを付けた正確な名前で呼び出します。名前は一意なので、インストール済みのほかのスキルに
マッチしうる自然言語の言い回しと衝突することは決してありません:

```text
/harness-bootstrap      # build or update the .claude harness for this repo
/spec-builder           # write the specs first
```

**リポジトリにすでにコードがある場合**、`/harness-bootstrap` を単体で実行します。何かを書く前にコードを読み -
スタック、モジュール、慣習、危険な操作 - そのインベントリをまず見せてくれます。インテーク（受け入れ）のほとんどは
見つけたものから事前入力されるので、コードでは分からないことだけを尋ねられます。既存のファイルは
**上書きではなく、突き合わせて調整されます**。あなたが書いたもの、または別のツールが作成したものはすべて
`CONFLICT` として報告され、あなたがマージできるようにその場に残されます - 決して置き換えられません。

**アイデアと空のリポジトリから始める場合**、まず `/spec-builder` を実行し、次に `/harness-bootstrap` を実行します。
仕様が先に来るのは、エージェントの陣容が仕様から生まれるからです。要件をドメインごとにクラスタリングし、
ドメインごとに1つの開発エージェントを、それぞれが所有するモジュールパスにスコープを絞って割り当てます。

いずれにせよ、あなたはプランを目にします - 何が作成され、保持され、変更されるか、加えてすべてのエージェントの
モデルとエフォートの予算 - そしてあなたが承認するまで何も書かれません。スキャフォールドそのものは約5分の1秒しか
かかりません。

ここでは何もグローバルな状態になりません。両方のスキルは対象のリポジトリ内、`.claude/` と `docs/` 配下にのみ
書き込みます。あなたの `~/.claude/skills/` ディレクトリには決して触れず、ハーネス全体は削除できるファイルの集合です。
`.claude/` を削除すれば、リポジトリはまさに元通りになります。

### リポジトリに置かれるもの

```text
.claude/
  agents/           15 agents, each with an explicit model, effort, tool grant and turn limit
  rules/            14 rules - 6 always loaded, 8 that load only when you touch a matching file
  commands/         /new-task /task-resume /implement-fr /review-changes /secret-scan /deploy ...
  hooks/            6 hooks that block bad actions before they happen
  settings.json     permission allow/deny + hook registration
docs/
  tasks/
    master-plan.md      the board: one row per task
    active/TASK-NNN.md  goal, acceptance criteria, and a session log the agent writes AS IT WORKS
  specs/ requirements/ architecture/ context/ templates/
AGENTS.md + CLAUDE.md
```

---

## ハーネスが保証すること

### 危険なことができない

「するなと言われている」のではありません。**できない**のです。ガードレールはシェルスクリプトとグロブルールです:

| エージェントが試みること | 結果 |
|---|---|
| `.env`、秘密鍵、`~/.ssh/`、`.npmrc` を読む | ブロック |
| Restricted に分類したパスを読む | ブロック。データを一切見ないので、どのモデルにも送ることができない |
| `main` に直接コミットする | ブロック |
| Accepted の ADR を編集する | ブロック |
| AI帰属のトレーラーを付けたコミットを送る | ブロック |

```bash
python eval/guardrail_eval.py   # 15 known-bad payloads at a real generated harness -> 15/15
```

すべてのエージェントを Opus から Haiku に入れ替えて再実行してください。結果は同一です。ループの中にモデルはいません。

<p align="center">
  <img src="docs/assets/control-layers.svg" alt="Control layers, hard (enforced) to soft (advisory)" width="820">
</p>

`.claude/rules/` のルールは**助言**であり、モデルは圧縮のあとにそこから逸れることがあります。フック、
`permissions.deny`、`tools:`、`maxTurns` は**強制**です。ある制御は、ファイルチェックとして書けるようになった瞬間に、
ソフトからハードへと移ります。

### IDEが死んでも失うものは何もない

<p align="center">
  <img src="docs/assets/memory-hierarchy.svg" alt="Memory tiers: always-RAM, lazy-RAM, disk, archive" width="820">
</p>

状態は、圧縮が要約して消し去るコンテキストウィンドウではなく、エージェントが作業しながら書く、コミットされた
マークダウンに残ります。クラッシュのあと、空のコンテキストを持つエージェントは `docs/tasks/active/` をスキャンし、
セッションログを読み、ブランチをボードと突き合わせて調整し、記憶ではなく `git` に照らして検証し、
最後に記録された行から続行します。`/task-resume` があなたの代わりにそれを行います。

それを機能させるルール: **ゲートは、セッションログがそれを記録したときにのみ、通過したものと見なされる。**
エージェントの「完了」は、あなたが検証する主張であって、決して事実ではありません。

詳細: [`docs/CONTEXT-MANAGEMENT.md`](docs/CONTEXT-MANAGEMENT.md)。

### 使うつもりのなかったトークンへの支払いをやめる

| デフォルト | ここでは |
|---|---|
| `model:` のないエージェントは呼び出し元のティアを継承するので、ログ要約のエージェントが Opus 料金で課金される | すべてのエージェントが明示的な `model:` と `effort:` を持つ |
| `paths:` のないルールは、すべてのエージェントのすべてのセッションに、永久に読み込まれる | 14のルールのうち8つがパススコープ付き。**ルール内容の66%がデフォルトセッションに決して入らない** |
| ループするエージェントは、毎ターン、無制限にフルコンテキストを消費する | ループが「すでに何かがおかしくなった」ことを意味するあらゆる座席に `maxTurns` |
| `tools:` の省略は、スキーマ込みで、マシン上のすべてのツールを継承する | 絞り込んだ付与。レビュアーは `Read, Grep, Glob, Bash` を得て、それ以外は何も得ない |

| 陣容 | USD / 機能 |
|---|---:|
| all-opus、エフォート調整なし（選ばないことで得られるもの） | 3.53 |
| **デフォルト陣容** | **2.38** |
| sonnet のみ | 1.92 |
| haiku のみ | 0.61 |

Opus は Sonnet の **1.67倍**であって5倍ではないので、ティアはたいていの助言が想定するより小さいダイヤルであり、
`effort:` のほうが大きなダイヤルです。デフォルトの陣容は意図的に最安ではありません。その差額を Opus のレビューゲートに
費やします。その賭けの反対側を取りたければ、[`roster.md`](harness-bootstrap/reference/roster.md) の1つのテーブルを
編集してください。これらの数字は公表価格からモデル化したもので、実測ではありません -
`python benchmark/model_cost.py` を実行してください。

---

## ハーネスがどう構築され、どう自らを保つか

<p align="center">
  <img src="docs/assets/generation-and-constraint.svg" alt="Where the agents, rules, commands and hooks come from, and how they hold each other in check" width="820">
</p>

あなたの `.claude/` フォルダの中に、勝手に作られたものは何もありません。各エージェント、ルール、フック、拒否エントリは、
現実の何かに遡ります。あなたのコード、あなたの仕様、あるいはインテークであなたが答えた回答であり、`scaffold.py` が
残りをディスク上のファイルからコピーします。ひとたび動き出せば、各パーツが互いを保ちます。オーケストレーターは
すべてのエージェントをディスパッチしますが、プロダクトコードは書けません。レビュアーは開発エージェントをゲートしますが、
何も編集できません。ボードは実際に起きたことを記録し、フックは尋ねることなくそれら全員を止めます。

### 全体像を1枚の絵で

<p align="center">
  <img src="docs/assets/harness-architecture.svg" alt="Harness layers, with the model drawn as a swappable layer" width="820">
</p>

モデルは上部近くのスロットに収まります。その下のすべての層 - 拒否リスト、フック、ツール付与、ボード - は
決定論的で、モデルが変わっても変わりません。

モデルの**ティア**は今日でも入れ替え可能です: `opus`、`sonnet`、`haiku`、`fable`。モデルの**ベンダー**は違います。
陣容をセルフホストのモデルやサードパーティのモデルに再指定するのは、設定変更ではなく移植であり、ここにアダプターは
同梱されていません。[`docs/ASSESSMENT.md`](docs/ASSESSMENT.md) の Gap 2 を参照してください。

---

## Cursor と Codex でも動く

Cursor と Codex はどちらも、Claude Code のものに十分近いフックシステムを備えているので、ルールだけでなく
ガードレールも移植されます。それぞれの1コマンドセットアップは上の[インストール](#インストール)にあります。
ここでは、実際に何が引き継がれ、どこで止まるかを示します:

| | Claude Code | Cursor | Codex |
|---|---|---|---|
| ルール | `.claude/rules/*.md` | `.cursor/rules/*.mdc`（`paths:` は `globs:` になる）+ `AGENTS.md` | `AGENTS.md`（ネイティブに読む） |
| 強制 | `settings.json` フック | `.cursor/hooks.json` + 生成されたアダプター | `.codex/hooks.json`（フックが直接登録される） |
| 秘密の読み取り、`main` へのコミットをブロック | はい | はい | はい |

**Codex** はリポジトリのルートで `AGENTS.md` をセットアップなしで読み、そのフックのペイロードは Claude Code のものと
同一なので、ポーターは既存のフックを `.codex/hooks.json` に直接登録します。

**Cursor** は `AGENTS.md` と `.cursor/rules/*.mdc` を読みます。そのフックのイベントと出力は異なるので、ポーターは
Cursor のペイロードをハーネスのフックへ、そしてその逆へと変換する小さなアダプターを書き出します。このアダプターは
CI でユニットテストされています。`.env` の読み取りと `main` へのコミットを正しく拒否し、`npm test` を許可します。

正直な2つの限界。どちらもポーターが表示し、それ以外の場所では強制されません:

- **Codex** はファイル編集をコマンド内にパスを含む `apply_patch` を通じてルーティングするので、`protect-adr`
  （ファイルパスを読む）はそこではベストエフォートです。Bash のガードは厳密です。
- **Cursor** の `afterFileEdit` は観測的なので、Accepted の ADR への編集は、事前にブロックされるのではなく
  事後にフラグ付けされます。シェルコマンドやファイル読み取りを通じて到達可能なものはすべて、Claude Code と
  同じようにブロックされます。

3つのツールは1つの信頼できる情報源を共有します。`AGENTS.md` が契約であり、`.claude/`、`.cursor/`、`.codex/` は
その3つのレンダリングで、同じアセットから生成されます。各ツールには、正確なファイル、強制対助言の表、そして
検証方法を載せたページがあります:

- [**Claude Code**](docs/tools/claude-code.md) - リファレンス。ハーネスがどう生成され、強制されるか。
- [**Cursor**](docs/tools/cursor.md) - `.mdc` ルールとフックアダプター。
- [**Codex**](docs/tools/codex.md) - ネイティブの `AGENTS.md` と直接登録されるフック。

---

## ガバナンス

3つのルールが、あなたがブートストラップするすべてのリポジトリに同梱されます。あなたはインテークで回答を供給します。
スキルはあなたの会社のポリシーを決して勝手に作りません。

- [**`model-policy.md`**](harness-bootstrap/assets/claude/rules/model-policy.md) - データを分類し
  （Public / Internal / Confidential / Restricted）、各クラスをどのモデルが処理してよいかを述べます。
  Restricted のパスは読み取りの境界で拒否されるので、エージェントは開けないものを漏らすことができません。
- [**`ip-compliance.md`**](harness-bootstrap/assets/claude/rules/ip-compliance.md) - 依存関係ライセンスの
  許可/拒否、AGPL-on-SaaS トリガー、そしてレビュアーが実行できる差分チェック。
- [**`ai-governance.md`**](harness-bootstrap/assets/claude/rules/ai-governance.md) - どのアクションが、
  設定フラグではなく、その具体的なアクションを見た人間を必要とするか。

---

## リファレンス

| | |
|---|---|
| [`FLOWS.md`](docs/FLOWS.md) | 7つの図: スキャフォールダー、1つの機能を端から端まで、コンテキスト読み込み |
| [`CONTEXT-MANAGEMENT.md`](docs/CONTEXT-MANAGEMENT.md) | RAM 対ディスク、再開プロトコル、ハード対ソフトの制御 |
| [`ASSESSMENT.md`](docs/ASSESSMENT.md) | スコアカード。これが行わないことも含む |
| [`cost-model.md`](harness-bootstrap/reference/cost-model.md) | モデル、エフォート、ツール、キャッシュ安定性が請求にどう影響するか |
| [`roster.md`](harness-bootstrap/reference/roster.md) | すべてのエージェントのモデル、エフォート、ツール、ターン制限、そしてその理由 |
| [`task-control.md`](harness-bootstrap/reference/task-control.md) | オーケストレーションループ、クラッシュ復旧、マージ規律 |
| [`audit-mode.md`](harness-bootstrap/reference/audit-mode.md) | 読み取り専用の監査コントロールプレーン。エージェントが決して変更してはならないソース向け |
| [`ba-standards.md`](spec-builder/reference/ba-standards.md) | 13の仕様セクションがどの標準に依拠するか |
| [`RESULTS.md`](benchmark/RESULTS.md) | ベンチマークの数字とその注意点 |
| [`RELEASING.md`](docs/RELEASING.md) | Semver、成果物、ノートのフォーマット |
| [`video/README.md`](video/README.md) | クリップ一式、パレット、そしてその再生成方法 |

### 数字

これが置き換える前身スキルに対して測定。`python benchmark/benchmark.py` で再現できます。

| | Before | After | Δ |
|---|---:|---:|---:|
| リポジトリをブートストラップするためにモデルが読むべきバイト数 | 234,196 | 85,641 | **-63%** |
| モデルが出力として書くべきバイト数 | 95,064 | 14,595 | **-85%** |
| デフォルトセッションから除外されたルール内容 | - | 74,697 B 中 49,394 B | **66%** |
| スキャフォールド時間 | - | 約0.2秒、73ファイル | - |
| ガードレール eval | - | **15/15** | - |

バイトの数字は正確です。トークンの数字は、`ANTHROPIC_API_KEY` が設定されている場合を除いて推定であり、設定されている場合は
スクリプトが実際のエンドポイントに照らしてカウントします。

---

## コントリビュート

- **数字を勝手に作らない。** あなたが引用するどの数字も、`benchmark/` または `eval/` のスクリプトが表示しなければ
  なりません。
- **アセットはバイト安定を保つ。** `assets/` 配下にタイムスタンプや実行 ID を置かないでください - それらは
  システムプロンプトに入り込み、プロンプトキャッシュに永久にコールドミスします。
- **em-dash を使わない。** 素のハイフンを。

リリースは [`docs/RELEASING.md`](docs/RELEASING.md) に従います。

MIT - [LICENSE](LICENSE) を参照。

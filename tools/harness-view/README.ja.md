# harness-view

[English](README.md) · **日本語**

`harness-bootstrap` スキルを実行したリポジトリ向けの、単体で動く決定論的なアナライザーです。
`.claude/`(agents、rules、commands、hooks、settings)、タスクボード、コードグラフを読み取り、
すべてがどう配線されているかを示します。AI は介在しません。ファイルを読んで関係を報告するだけです。

コーディング用のリポジトリであることは前提にしていません。リサーチや執筆のハーネス
(`researcher`、`writer`、`editor` だけで、テストもコードグラフもないもの)も同じ基準でスキャンと
評価が行われますし、[orchestrator-kit](SCHEMA.ja.md) の導入物、つまり `.agent-base/tasks` ボード、
席ごとに登録されたガードフック、起動許可リストも読み取ります。各ファイルから何を読むかは
[SCHEMA.ja.md](SCHEMA.ja.md) に一覧があります: ドキュメント化されたサブエージェントの frontmatter
フィールドすべて、settings.json と各席自身の `hooks:` にある任意のイベントのフック、`skills:` の
プリロード、そして `Agent(a, b)` による起動許可をエッジとして読みます。

スキル自体が出力する HTML(`docs/context/harness-graph.html`)は Python とブラウザさえあれば
動きます。このツールはその強化版で、ライブ更新される UI、ファイル監視、安全なランタイムトグルを
備えたネイティブバイナリです。

## インストールと実行

実行方法は三つあります。どれも同じツールになるので、使いやすいものを選んでください。
Web UI は実行ファイルに組み込まれているため、どの方法でも Python や Node、その他のランタイムを
インストールする必要はありません。

### 1. ビルド済みのものをダウンロードする(ツールチェーン不要)

各リリースには、プラットフォームごとに単体の実行ファイルが添付されています。それぞれ、
そのプラットフォーム自身のランナーでビルドされています:

| プラットフォーム | アセット |
|---|---|
| Windows x86_64 | `harness-view-<version>-x86_64-pc-windows-msvc.zip` |
| macOS Apple Silicon | `harness-view-<version>-aarch64-apple-darwin.tar.gz` |
| macOS Intel | `harness-view-<version>-x86_64-apple-darwin.tar.gz` |
| Linux x86_64 | `harness-view-<version>-x86_64-unknown-linux-gnu.tar.gz` |

各アーカイブにはバイナリ、この README、`SCHEMA.md` が含まれ、リリースページでは横に `.sha256`
が置かれています。

Windows(PowerShell):

```powershell
Expand-Archive harness-view-1.8.2-x86_64-pc-windows-msvc.zip -DestinationPath .
cd harness-view-1.8.2-x86_64-pc-windows-msvc
.\harness-view.exe serve D:\Projects\my-repo
```

macOS と Linux:

```bash
tar xzf harness-view-1.8.2-x86_64-unknown-linux-gnu.tar.gz
cd harness-view-1.8.2-x86_64-unknown-linux-gnu
./harness-view serve ~/projects/my-repo
```

macOS ではバイナリが署名されていないため、ダウンロードしたファイルは Gatekeeper によって隔離されます。
`xattr -d com.apple.quarantine ./harness-view` で一度だけ解除するか、代わりにソースからビルドしてください。

### 2. ダブルクリックで起動する(Windows)

`harness-view.exe` を好きな場所に置いてダブルクリックします。引数なしで起動すると、カレント
ディレクトリを配信し、URL を表示してブラウザを開きます。サーバーが動いている間はコンソール
ウィンドウが開いたままになり、閉じるとサーバーも停止します。

実行ファイルをどこに置くかは関係ありません。起動したフォルダーに `.claude/` がなければ、
コンソールにその旨が表示され、ページは **No folder loaded** の状態で開きます。**Browse** で
リポジトリを選べばグラフが表示されます。`scan`、`assess`、`watch` だけは今も `.claude/` がないと
実行を拒否します。これらはどれも名前で指定された一つのパスについての問いに答えるもので、空の答えが
結果のように見えてしまうからです。

この挙動は引数なしで起動した場合**だけ**に適用されます。明示的な呼び出しはすべてこれまでどおり
動作し、ブラウザを開くことも、一時停止することもありません。

### 3. ソースからビルドする(Rust が必要)

```
cargo install --path tools/harness-view
```

### 日常的な呼び出し方

```
harness-view                              # serve the current folder, open a browser
harness-view serve .                      # serve the current folder, no browser
harness-view serve /path/to/repo --port 8080
harness-view scan /path/to/repo
harness-view watch /path/to/repo
harness-view --version                    # also shown in the page footer
harness-view --help
```

### 他のリポジトリを指定する

一つのサーバーで複数のプロジェクトを調べられます。ヘッダーのボックスにパスを入力するか
(Windows では `D:\Projects\x` と `D:/Projects/x` のどちらも使えます)、**Browse** を押して
ファイルシステムをたどってください。それ自体がハーネスであるフォルダーには印が付き、最近開いた
フォルダーは一覧に並んでワンクリックで戻れます。一覧の項目は個別に削除することも、まとめて
消去することもできます。この一覧はブラウザ内にだけ保存され、ディスクには書かれません。
参照機能は `GET /browse?path=<dir>` が提供しており、返すのはディレクトリ名だけです。ファイル名も
内容も返しません。ブラウザはページに実際のファイルシステムパスを渡せないためです
(`showDirectoryPicker()` が返すハンドルにはパスがありません)。内部的には `GET /graph.json?root=<path>`
を呼んでおり、存在しないパスや `.claude/` のないパスには HTTP 400 が返って理由がページに表示され、
それまでのグラフは画面に残ります。

### 安全性のまとめ

- サーバーは `127.0.0.1` にのみバインドします。これはローカルツールであり、外部に公開する
  サービスではありません。リモートからの接点がないため、認証もありません。
- 変更を伴うエンドポイントとファイルを読むエンドポイントは、同一オリジンのブラウザリクエストを
  要求します(`Origin` と `Sec-Fetch-Site` を確認し、`POST` には `Content-Type: application/json`
  を求めます)。そのため、別に開いているタブから操作されることはありません。
- `GET /file` は読み取り専用で、対象は `.claude/` と `docs/` に限られ、上限は 256 KB です。常に
  `nosniff` 付きの `text/plain` として返されます。
- `GET /browse` はナビゲーション用にサブディレクトリ名だけを返し、ファイル名や内容は返しません。
  ほかと同様に、クロスオリジンのリクエストは拒否されます。
- 描画された markdown は、ページに届く前に DOMPurify で許可リストに照らしてサニタイズされます。
  プレビューされるファイルは調査対象のリポジトリから来たものであり、ページは `POST /toggle` と
  同一オリジンだからです。Raw モードはテキストとして挿入され、パースされることはありません。
- トグルは段階制です。HARD 保護のコントロールには確認フレーズを文字どおり入力する必要があり、
  SOFT 保護のものには明示的な承認が必要です。ロースターの席は少なくとも SOFT です。詳しくは
  [ランタイムトグル](#ランタイムトグル)を参照してください。
- `POST /command` はステップ編集のあとにコマンドファイルを書き戻します。受け取るのはコマンドの
  名前(NAME)だけでパスは受け取らないため、書き込めるのは `.claude/commands/<name>.md` だけです。
  上限は 512 KB で、空の本文は拒否します。詳しくは[コマンドのステップ編集](#コマンドのステップ編集)
  を参照してください。

## バージョンとメタデータ

クレートのバージョンはリポジトリのリリースバージョンに追従します。両者がずれると
`scripts/validate_release.py` がビルドを失敗させるので、ダウンロードしたバイナリがリリースに
存在しないバージョンを名乗ることはありません。Windows では本物の VERSIONINFO リソースとして
コンパイルされるため、`Properties -> Details` に製品名、説明、ファイルバージョンが表示され、
エクスプローラーにはアプリケーションアイコンが表示されます。`--version` と配信ページのフッターは
同じ文字列を報告します。

アイコンはプロジェクトのマーク(`docs/assets/logo-mark.svg`)から `scripts/make_icons.py` で
生成されます。バイナリを手で編集するのではなく、再生成してください。

## コマンド

```
harness-view scan   [path] [-o out.json]  # write .claude/state/harness-graph.json
harness-view serve  [path] [--port 7420]  # local web UI at http://127.0.0.1:7420/
harness-view watch  [path]                # rebuild on .claude/, docs/ or .agent-base/ changes
harness-view assess [path] [--json] [--lang ja] [--since prev.json]
                                          # score the harness; exit 1 on a high finding
harness-view rubric [--lang ja]           # print the rubric every score comes from
```

実際のハーネスに対して、それぞれが実際に出力する内容は次のとおりです:

```
$ harness-view scan D:/Projects/msboost
harness-view: 219 nodes, 655 edges -> D:\Projects\ost\.claude\state\harness-graph.json

$ harness-view serve D:/Projects/msboost --port 7420
harness-view: serving D:\Projects\msboost on http://127.0.0.1:7420/

$ harness-view watch D:/Projects/msboost
harness-view: watching D:\Projects\msboost (Ctrl+C to stop)
harness-view: rebuilt (219 nodes, 655 edges)
```

`scan` はファイルを書いて終了するので、スクリプトやフックで使うのはこの形です。`serve` と
`watch` は中断されるまでフォアグラウンドで動き続けます。

- `scan` は [SCHEMA.ja.md](SCHEMA.ja.md) で説明しているグラフを出力します(スキーマバージョン 1、
  スキルの Python スキャナーと共通)。出力はバイト単位で安定しています: ノードもエッジもキーも
  ソート済みで、タイムスタンプはありません。
- `serve` は同じグラフを二つのビューで描画します。**Flow**(左から右への階層表示: rules -> hooks
  と settings -> agents -> マージリクエストのゲート -> 人間 -> commands、エッジ種別のラベル付き)と
  **Graph**(力学モデルによる配置)です。凡例でノード種別の表示を切り替えられ、modules、tasks、
  scripts は既定で非表示です。`/graph.json` へのリクエストのたびに再スキャンするため、ページは常に
  最新です。任意の 10 秒自動更新を使えばライブに保たれ、何も変わっていなければレイアウトとズームは
  そのまま維持されます。ノードをクリックすると、そのノードにつながるサブグラフをたどります。
  そのノード、隣接ノード、そしてそれらのうち任意の二つを結ぶエッジが流れる破線で描かれ、関係のない
  ものはすべて薄く後退します。フックには発火するイベントのバッジ(`PRE`、`POST`、`PERM`、`PROMPT`、
  `START`、`STOP`、`SUB-`、`COMPACT` など)が付き、ツールを制限するフックは赤で示されます。タスクには
  ボード上のステータスが付き、ボード自体に食い違いがある場合は `DRIFT` が付きます。無効化された
  項目は破線、赤枠、取り消し線で表示されます。三つ目の **Master plan** タブは、リポジトリに
  `docs/tasks/master-plan.md` がある場合にだけ現れます。
- ヘッダーのパスボックスを使うと、`.claude/` フォルダーを持つ任意のリポジトリにビューアを向け直せる
  ので、一つのサーバーで複数のプロジェクトを調べられます。最近のパスはブラウザ内に記憶され、
  ディスクには書かれません。
- `watch` は OS のファイル通知を使い、変更がまとまって起きるたびに(500 ms のデバウンス)
  `.claude/state/harness-graph.json` を書き直します。`.claude/state/` 配下のイベントは無視される
  ため、再構築が自分自身を再び引き起こすことはありません。

## 評価

`assess` は、`harness-bootstrap` がすでに表明している品質ゲートに照らしてハーネスを採点します。
単純なルールエンジンであり、モデルもネットワークも主観的な判断も使いません。**Assess** タブと
`GET /assess?root=<path>` も同じエンジンで動くため、ブラウザと CI ジョブが同じリポジトリについて
食い違うことはありません。

すべての指摘は行動につながる形になっており、次のものを示します:

- **ルール**: `COST-01` のようなルーブリック ID。[RUBRIC.ja.md](RUBRIC.ja.md) で公開しています
- **根拠**: `file:line`。キーそのものの行、またはキーが欠けている場合はそれが入るべき閉じの `---`
- それが重要な**理由**と、具体的な**修正方法**: コマンド、または正確な編集内容
- 安全な場合は、既存の `POST /agent` 書き込み経路を通した**ワンクリック修正**(モデルの固定、
  effort の設定、席への明示的なツールリストの付与、レビュアーからの書き込みツールの除去、裸の
  `Agent` の削除)。エージェントエディターがその編集を受け付ける場合にだけ提示され、書き込む前に
  ページが確認を求めます。

```
$ harness-view assess tools/harness-view/tests/fixture
harness assessment: .../tools/harness-view/tests/fixture
  purposes: code (roster)
  overall 98/100   high 0  medium 0  low 5
    Safety           94/100  (3 findings)
    ...
  fix these first:
    1. [SAF-08] The deny list covers force push, recursive delete and secret reads. x2  (effort 1, overall after 99)
    ...
  findings, worst first:
    [low BRD-02] task `TASK-01` has no status
        at: docs/tasks/active/TASK-01.md:1
        fix: Add `status: Pending` (or the board's real state) to the frontmatter of the task file.
```

| フラグ | 動作 |
|---|---|
| `--json` | CI 向けの完全な評価結果。未解決の high の指摘があれば終了コード 1 |
| `--lang ja` | すべてのタイトル、理由、修正方法、ラベルを日本語で出力 |
| `--since prev.json` | 以前の `--json` 出力と比較: 修正された指摘と新しい指摘、変動したすべてのスコア |
| `--purpose research,docs` | 検出された用途を上書き |

`harness-view rubric [--lang ja]` はルーブリックそのものを出力します。

### 最初に直すもの

作業リストは指摘をルールごとにまとめ、ルールを **weight x count / effort** の順に並べます
(effort 1 はワンクリックまたは 1 行、2 は小さな編集、3 は判断または新しいファイル)。各カードには、
満点とは何か、そこに至る方法、ワンクリック修正がいくつあるか、そのルールを解消した場合に全体
スコアがいくつになるかが示されます。Assess タブには上位三つが表示され、残りは折りたたまれます。

### 前回のチェックから変わったこと

サーバーは各ルートの前回の評価をメモリに保持しています。ワンクリック修正のあとや、ファイルを
手で編集したあとに再チェックすると、前後のスコア、修正された指摘、新しい指摘、追加または削除
されたグラフのノードが表示されます。リポジトリには何も書き込まれません。CI では、保存した JSON
ファイルを使って `--since` が同じことを行います。

### スコアとその再現方法

六つのカテゴリー(Safety、Cost control、Traceability、Board health、Docs quality、Contract)は
それぞれ 100 から始まり、そのカテゴリー内の指摘ごとに重みの分だけ減点されます: high 12、
medium 5、low 2、info 0 で、下限は 0 です。検査対象のないカテゴリー(タスクのない Board health、
タスク・コマンド・スキルのない Traceability)は、無条件の 100 ではなく n/a と表示します。全体スコアは
対象となるカテゴリーの整数平均で、安全性に high の指摘が残っている間は安全性の点数が上限になります。
deny リストも止めるフックもないハーネスは、ドキュメントがどれほど整っていても 88 点にはなりません。
各カテゴリーのカードには
それぞれの計算式(`100 - COST-01 1x12 = 88`)が表示され、`tests/rubric_test.rs` は公開されている
重みからすべてのスコアを再計算します。重みは明示された取り決めであり、測定値ではありません。

### 用途に応じたルール

ルールの適用対象は、`all`(すべてのリポジトリ)、`code`、`non-code`(リサーチ、戦略、ドキュメント)
のいずれかです。用途は `.claude/state/vars.json` の `purpose_*` フラグから決まり、なければロスター
から(`researcher` があればリサーチ、`writer` か `editor` があればドキュメント、開発やレビューの席が
あればコード)、それもなければ既定でコードになります。そのため、リサーチ用のリポジトリが
`/review-changes` を追加するよう言われることはなく、成果物を確認する読み取り専用の席がない場合には
そのことが指摘されます(`SAF-13`)。タブには、どの用途が見つかったか、その結果どのルールが適用され
なかったかが表示されます。

ルールの中身が役に立つかどうか、エージェントの担当範囲が作業の組み立て方に合っているかどうか、
フックが主張どおりのものを本当に遮断するかどうか、コードや文章の品質は測定しません。指摘のない
レポートが意味するのはすべてのルールに合格したということであり、ハーネスが良いということでは
ありません。

### 指摘からグラフへ戻る

ノードを名指しする指摘には、すべて **show in graph** ボタンが付きます。そのノード種別を絞り込みで
隠していれば再表示し、グラフに切り替え、ノードを選択してその接続を強調表示します。

## ランタイムトグル

`serve` の詳細パネルでは、rules、commands、hooks を無効化または有効化できます。ハーネスの
`/harness-toggle` コマンドと同じ取り決めを使います:

- rules と commands は `.claude/<kind>/X.md` と `.claude/disabled/<kind>/X.md` の間を移動します。
- hooks はさらに `settings.json` の登録オブジェクトが削除され、(位置情報とともに)そのまま
  `.claude/disabled.json` に保存されます。そのため有効化すると、登録が元の場所に正確に戻ります。
- `.claude/disabled.json` はコミットされる記録です。書き込みはアトミックで、キーはソートされ、
  日付は含みません。

ロスターの席もここで切り替えられます。休止させたエージェントは `.claude/disabled/agents/X.md` に
移動し、グラフではルールとまったく同じようにグレー表示になります。席の休止は元に戻せて記録も残り
ますが、席の追加や廃止は今もロスターの変更であり、`/harness-bootstrap:harness-update` を通します。

安全モデルは二段階です:

**HARD**: `protect-secrets` と `guard-agent-spawn` のフック、`security-privacy` と
`agent-guardrails` のルール、`/review-changes` コマンド、そして `orchestrator`、`code-reviewer`、
`security-reviewer`、`reviewer`、`spec-guardian` の席です。リクエストの `confirm_hard` に
文字どおりのフレーズ `disable <name>` が入っていない限り、HTTP 403 で拒否されます。ページはその入力を
求め、入力された内容をバイト単位でそのまま送ります。トリムも大文字小文字の統一も行わないため、
`Disable x` と `disable x ` はどちらも再び拒否されます。これは `/harness-bootstrap:harness-toggle` が
`--confirm "disable <name>"` として適用するのと同じゲートです。CLI では、モデルがユーザーに代わって
このフレーズを組み立ててはならないというルールがあります。ブラウザではそもそもモデルが介在しない
ので、入力する人間はゲートの代理ではなく、ゲートそのものです。

**SOFT**: `guard-main-commit`、`check-commit-msg`、`protect-adr` のフック、`ai-governance` ルール、
そして**すべての**エージェントの席です(名前ではなく種別によるものです。オーケストレーターの
ルーティング表には引き続き載っています)。リクエストに `confirm_soft: true` が含まれるまで HTTP 409
で拒否され、UI はそれを明示的に確認します。HARD の席は両方の段階に属するため、両方のフラグが必要です。

有効化がゲートされることはありません。コントロールを元に戻すことは、この段階制が防ごうとしている
リスクではないからです。

### エンドポイント

`POST /toggle` に JSON の本文を付けて送ります:

```json
{"kind": "rule|command|hook|agent", "name": "<bare name>", "enable": false,
 "reason": "optional", "confirm_soft": false, "confirm_hard": ""}
```

このエンドポイントは同一オリジンのブラウザリクエストしか受け付けません。外部の `Origin` を持つ
リクエスト、`Sec-Fetch-Site` が `same-origin`/`none` 以外のリクエスト、`Content-Type: application/json`
のないリクエストは 403 で拒否されます。これにより、`serve` の実行中に別のタブで開いているページが
`.claude/` を黙って変更することを防ぎます。

### ファイルの読み取り

`GET /file?root=<repo>&path=<repo-relative path>` は、サイドバーのプレビューと Master plan タブを
支えています。読み取り専用で、意図的に範囲を狭くしています:

- 読めるのは `.claude/`、`docs/`、`.agent-base/`(タスクボード)と既知の指示ファイルだけで、
  リポジトリ内のそれ以外のものは一切配信しません
- 両側を正規化し、結果がルートの内側に収まっていることを確認します。そのため `..`、絶対パス、
  ツリーの外を指すシンボリックリンクは、文字列のパターンマッチではなく同じ一つのチェックで拒否されます
- 本文の上限は 256 KB で、超えた分は目に見える印を付けて切り詰めます
- 常に `X-Content-Type-Options: nosniff` 付きの `text/plain` であり、`text/html` になることは
  なく、ページは `textContent` で描画します
- `/toggle` と同じ同一オリジンのルールが適用されます

## コマンドのステップ編集

コマンドを選択するとそのファイルを読み込み、番号付きのステップをカードの連なりとして描画します。
この連なりは編集できます:

- **並べ替え**: ステップの番号をドラッグします。ステップは自分のグループ内でしか移動しないため、
  前提条件がアクションとして手順の中に落とされることはありません。
- **オフにする**: `Off` はステップをその場でコメントアウトし、
  `<!-- harness-view:disabled-step ... -->` で囲みます。`On` で元の場所に正確に戻ります。残っている
  ステップは、その抜けた部分を挟んで番号が振り直されます。
- **タイトル変更**: `Edit` でステップ自身のテキストを開きます。`Apply` はローカルでの反映です。
- **保存**: 未保存のものすべてを一度に書き込みます。`Revert` はそれらをすべて破棄します。このバーは
  未保存のものがある間だけ存在するので、バーがあること自体が変更ありの印です。

Save するまでディスクには何も書かれないため、ドロップを誤っても Revert 一回で済み、ファイルを
失うことはありません。

**保存で書き換わるもの。** ステップが占める行の範囲だけです。frontmatter、見出し、グループ間の文章、
末尾のテキスト、パネルに表示されなかったすべてのバイトはそのまま通されます。シリアライズはパース
ツリーから文書を再生成するのではなく、範囲を置き換えるからです。編集されていないステップは届いた
ときのバイトのまま書き戻されます。これがこの保証をテスト可能にしています:
`serializing_an_untouched_parse_returns_the_file_unchanged` はフィクスチャのすべてのコマンドを
パースして再シリアライズし、改行コードも含めて結果がバイト単位で同一であることを確認します。
さらに二つのテストが、ステップをオフにしてからオンに戻すと元どおりになること、そして並べ替えても
セクションの締めくくりの文章が末尾に残り、それが付いていたステップに引きずられてページの上へ
移動しないことを固定しています。

**「オフ」とは何か、正直に言うと。** HTML コメントは描画される手順からステップを取り除き、その意図を
記録します。しかし、生のファイルを読むモデルがそのテキストを目にすることは防げません。これは元に
戻せる編集であって、強制の境界ではありません。強制の境界は今も `POST /toggle` であり、ファイル全体を
ツリーの外に隔離します。自身のテキストに `-->` を含むステップはまったく囲めません。コメントブロックが
途中で終わってしまうファイルを書く代わりに、その理由をツールチップにしてコントロールを最初から
無効にしています。

### エンドポイント

`POST /command` に JSON の本文を付けて送ります:

```json
{"name": "<bare command name>", "content": "<the whole file>", "root": "<repo>"}
```

ゲートは `POST /toggle` と同じです: 同一オリジンのみ、`Content-Type: application/json` が必須で、
拒否はプレーンテキストで返すのでページはそれをそのまま表示できます。受け取るのは名前(NAME)で、
パスは自分で組み立てます。そのため `..`、区切り文字、ドライブレターはパスが存在する前に文字チェックで
失敗し、書き込めるファイルは `.claude/commands/<name>.md` だけです。無効化されたコマンドは編集でき
ないので、先に有効化してください。内容の上限は 512 KB で、空の本文は拒否されます。コマンドを空に
するのは誰かが意図した編集ではなく、コマンドを取り除くのは `POST /toggle` の役目だからです。

### ステップを動かすだけでなく書く

- **挿入**: `+ step here` でグループ内の任意の位置にステップを追加します。後ろのステップは番号が
  振り直されます。
- **オートコンプリート**: ステップに入力すると、書こうとしていそうな名前が候補に出ます。エージェントの
  席、ルールファイル、フック名、リポジトリ内の相対パスです。名前はグラフから、パスは `GET /paths` から
  取得します。このエンドポイントがあるのは、グラフがパスを持っていないからです。これは推測ではなく
  測定した結果です。ある実プロジェクトのコマンドが引用していた 21 個のパスのうち、グラフのノードの
  `file` として現れたものはゼロで、`docs/templates/ADR.md.template` を名指しするステップには補完の
  対象がありませんでした。矢印キーと Enter、またはクリックで選び、Escape で閉じます。
- **markdown の描画**: テキストが表、リスト、フェンスで囲まれたブロックであるステップはそのとおりに
  描画されるので、ステップ 4 のルーティング表は表として読めます。編集のためにステップを開くと、
  markdown のソースが再び表示されます。リポジトリのテキストは `createElement` と `textContent` だけを
  通って DOM に届き、リンクは `http(s)` に限られ、パースできないものは生のテキストに戻ります。

`GET /paths` は `.claude/` と `docs/` の中から歩き始め、その中だけをたどるので、上へさかのぼる対象は
ありません。すべてのエントリは正規化されてプレフィックスを確認され、ディレクトリのシンボリック
リンクはたどらず、ドットディレクトリと `node_modules`/`target` はスキップされます。走査の上限は
4000 エントリ、12 階層です。

## ロスターの編集

エージェントを選択すると、そのパネルに **Edit roster** と **Reference** が加わります。

**Edit roster** は、席の `model`、`effort`、`tools`、`description` を、frontmatter を手で編集する
代わりにピッカーで変更します。書き込みは変更されたキーにしか触れません。frontmatter の下の本文は
バイト単位でそのまま複製され、frontmatter の中でも触れていないキーは位置、コメント、空行を保ちます。
CRLF は CRLF のままです。`name` は無視されるのではなく拒否されます。席の名前を変えるのはフィールドの
編集ではなく、ルーティング表の変更だからです。無効化されたエージェントは編集できないので、先に
有効化してください。

`POST /agent` は席の名前だけを受け取り、パスは受け取りません。そのため `..`、区切り文字、ドライブ
レター、URL はいずれも、パスが存在する前に文字チェックで失敗します。

**Reference** はこれらのピッカーの背後にあるカタログです。四つのベンダー(Claude Code、
OpenAI Codex、Gemini CLI、Z.AI GLM)とそのモデルとツールを収録し、それぞれに `verified` フラグと、
何をするものかの注記が付いています。一次情報源で確認できなかった項目は、ピッカーの中も含めて
表示されるあらゆる場所で `unverified` と示されます。存在しないかもしれないモデルを前提にした
ロスターの判断は、短いリストを前提にした判断よりも悪いからです。

カタログは自由に変更できます。ベンダー、モデル、ツールを追加、編集、削除すると、その変更は
**リポジトリごとに** `.claude/state/references.json` に保存され、読み取り時に同梱のシードの上に
マージされます:

- 同梱のアセットに書き込むことはないので、スキルをアップグレードしても編集内容は残ります
- 削除したシードの項目には削除済みの印(トゥームストーン)が残るので、その判断もアップグレード後に
  残ります。自分で追加した項目を削除した場合は、単に取り除かれます
- 最後の上書きがなくなると、ファイルは空のまま残されるのではなく削除されます
- キーはどの階層でもソートされ、タイムスタンプは一切含まれないので、二人が同じ三つの編集を別の順序で
  行っても同じファイルになります
- **シードの項目の `verified` は常にシードから取られます。** 上書きでラベルや注記を訂正することは
  できますが、未確認のモデルを確認済みに格上げすることも、確認済みのものを格下げすることもできません。
  自分で追加した項目には自分自身の主張と `custom: true` が付くので、その出所が見えるままになります。

## markdown の描画

サイドバーで開いたファイルと master-plan タブは、[marked](https://github.com/markedjs/marked) で
描画され、[DOMPurify](https://github.com/cure53/DOMPurify) でサニタイズされます。どちらも `vendor/`
の下に同梱されてページにインライン化されているので、ビューアはネットワークリクエストを一切行わず、
ビルドステップもありません。バージョン、ライセンス、出所は [`vendor/README.md`](vendor/README.md)
にあります。**Hide file** の横にあるアイコンボタンで整形表示と生の markdown を切り替えられ、二つの
表示面はその選択をそれぞれ別々に記憶します。

## 開発

```
cargo test          # scanner fixtures, determinism, toggle round trips,
                    # the orchestrator-kit fixture (tests/kit-fixture)
cargo build --release
```

依存関係は意図的に小さく、監査しやすくしてあります: `serde_json`、`tiny_http`、`notify`。

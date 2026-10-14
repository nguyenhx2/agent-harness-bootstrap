# ブートストラップ後の調整

[English](TUNING.md) · **日本語**

`harness-bootstrap` は導入時に出発点となる姿勢を選び、`.claude/` に書き込みます。実際のプロジェクトはその姿勢
から少しずつずれていきます。デプロイのコマンドが信頼を得る、席が持っていないツールを必要とする、ボードに健全性
チェックが要る、スキルが取り込みたい新しい資産を配布する、コードが大きく動いてモジュールマップが古くなる。
全リポジトリに入る 9 つのコマンドがそのずれを扱います (`/code-graph` はコード目的のリポジトリのみ)。さらに、
`spec-builder` の仕様セットと一緒に届き、情報源を `docs/specs/` に取り込む/取り消す 2 つ (`/spec-ingest`、
`/spec-retract`) があります。このページは 11 個すべての完全な参照です。それぞれが何をするか、いつ使うか、実例、
そして破らせない不変条件。目安: ダイヤル 1 つなら `/harness-tune` か `/agent-permissions`、統制を 1 つオフ/オンに
するなら `/harness-toggle`、構造の変更 (新しい席、新しい資産、範囲の見直し) は `/harness-update` です。

通常の機能開発で使うコマンド - `/new-task`、`/implement-fr`、`/test`、`/review-changes`、`/deploy` など - は別の
系統です。これらは製品を作るもので、ハーネスを作るものではありません。その参照は、実装しているシーケンス図の
隣、[`docs/FLOWS.ja.md` のセクション 7](FLOWS.ja.md#7-デリバリーコマンドをコマンドごとに) にあります。

どれもフックの *ロジック* は編集しません。編集するのはデータ - リスト、上限、席のフロントマター、`vars.json`、
無効化の台帳 - で、ほかのレビューされる変更と同じ扱いです。`.sh`/`.ps1` のフックを書き換える必要があるなら、
それは調整ではなく通常のコード変更です。

## `/board-audit`

**何をするか。** まず `python .claude/scripts/board-check.py` を実行します。標準ライブラリだけの検証で、すべての
タスクファイルのフロントマターの列挙値 (`status`、`attempts`、`priority`、`human_gate`) と、`deps:` の連鎖の依存
循環を調べます。ここで終了コードが非 0 なら、ボード自体が壊れているということで、以降の掃引は整ったフロント
マターを前提にしているので、何よりも先にその指摘をそのまま報告します。そのあとで初めて `docs/tasks/` を現実と
突き合わせて掃引します。git のワークツリー、ブランチ、`.claude/state/history/` の実行です。何も修正はせず、
`WHAT | WHERE | SUGGESTED ACTION` を報告し、`BOARD CLEAN` か指摘の件数で終わります。

**いつ使うか。** クラッシュや長い中断のあとに作業を再開する前、リリースの前、タスクの状態が古そうに感じるとき。
次を拾います:

- **古い Active** - `Active` なのに最近のセッションログの行がなく、`.claude/state/history/` にも対応する実行がない
  タスク。
- **記録されていない完了** - サブエージェントの実行が終わっている (アーカイブのファイルがある) のに、誰もタスクの
  セッションログに書いていない。
- **ボードのずれ** - フロントマターの `status:` が master-plan の行と食い違う、またはファイルが違うディレクトリ
  (`active/` と `done/`) にある。
- **試行上限の超過** - `attempts: 3` 以上なのに、エスカレーションのメモを付けた `Blocked` ではなく `Active` の
  ままのタスク。
- **不明なワークツリーとブランチ** - ボードのどこにも参照されていない作業 (進行中、または放棄された)。
- **解除する人のいない Blocked** - メモに担当も条件も書かれていない `Blocked` のタスク。自力で再浮上することが
  ない。
- **レビューされていないモジュール間の辺** (コードのリポジトリ) - `python .claude/scripts/code-graph.py --check` が
  終了コード 1: コードが、`docs/context/code-graph.md` に載っていないモジュールの境界をまたいで import している。
  名指しされた辺ごとに決定が要る - import を外すか、`/code-graph` で受け入れるか - 無視はしない。

**実例。**

```text
/board-audit
```

```text
2 findings - board needs reconciliation
  Stale Active | docs/tasks/active/TASK-014.md | last session-log row is 4 days old, no matching
    history entry - reassign or close it out
  Unlogged completion | .claude/state/history/2026-08-01-143201-dev-agent.json | names TASK-009,
    session log has no matching row - collect the result
Next: reconcile TASK-014 first, it blocks the master-plan row above it.
```

自分では何も直しません。`/board-audit` は見るだけです。整合させるのはオーケストレーターか利用者です。

## `/harness-tune`

**何をするか。** ハーネスを、新たな聞き取りではなく、実際にそこで起きたことから調整します。証拠を 1 回で読み、
順位付きで最大 4 件の変更を提案し、一度だけ尋ね、選ばれたものを適用し、それぞれを確かめ、最後に締めます。
証拠はどれも任意です (ない情報源は、止まる理由ではなく報告の 1 行になります):

- **実行アーカイブ** (`.claude/state/history/`) - 一度も委任されていない席、`maxTurns` で途中終了した実行、
  件数を 1 つの席が占めている状況。
- **遮断と拒否** - `BLOCKED:` と "denied" の行: 正当な作業で発火しているガード、または手作業で迂回されている
  deny エントリ。
- **リトライと試行の上限** - `.claude/state/retry-budget`、`task.py check`、`attempts:` と `Blocked` のメモ:
  上限が止めたループ。
- **検証** - `verify-plan.py` が書いた `log:` の行: 常に走るのに何も見つけないゲート、または省略されたのに
  後で壊れた変更。
- **構造** - PATH にバイナリがあれば `harness-view assess . --json`、なければ `harness-graph.py` と
  `board-check.py`: 孤立した席、未登録のフック、絞られていないルール。
- **記録された意図** - `docs/context/tool-changelog.md` と `.claude/disabled.json`: 以前に何を調整し、何を
  オフにしたか、そしてその理由。記録された決定を黙って覆すことはありません。

候補はそれぞれ 7 つのダイヤルのどれかに対応し、それ以外は扱いません: デプロイ権限、破壊的コマンドの deny
エントリ、起動許可リスト、上限 (`maxTurns`、試行の上限)、モデルと effort (席の `effort:`、または先に
`model-tiers.md` の階層、次に席の `model:`)、レビューゲート (`.claude/verify-map.json` から `verify-plan.py` が
読む引き金)、エージェント履歴の詳しさ。

**いつ使うか。** 導入時からチームのリスク許容が変わったとき - ステージングへのデプロイをエージェントに任せて
よくなった、ある席が正当に長いタスクでターン上限に何度も当たる、あるいはドキュメントだけの差分のたびにレビュー
ゲートが走って何も見つけない。変更を裏づける証拠がなければ、何も提案しません。「調整すべきものはない」は結果で
あり、それを示す数字つきで報告します。`/harness-tune cost` のような引数は証拠を読む重みをその焦点に寄せますが、
読むこと自体は省きません。

**実例。**

```text
/harness-tune deploy
```

コマンドは証拠を集めてから、一度だけ尋ね (`AskUserQuestion` が 1 回、複数選択で、各選択肢が変更で、説明がその
証拠とコスト)、書き込む前に正確な差分を見せます:

```text
Change 1 of 2: Deployment rights
Evidence: 6 session logs record "deploy" asked by hand; no run touched production.
Current: human-only (fly deploy sits in permissions.deny)
Proposed: agent-with-approval (fly deploy moves to permissions.ask)

--- .claude/settings.json
-  "deny": ["Bash(fly deploy*)", ...]
+  "ask":  ["Bash(fly deploy*)", ...]
```

適用した変更のあとには、それを試すチェックが続きます。deny/ask/allow のエントリは JSON として解析し、そのエントリ
が止めるはずのペイロードを 1 つ、守っているフックに流します。席、上限、モデル、effort の編集は、形の崩れた席を
拒否する `harness-graph.py` を通します。レビューゲートの変更は `verify-plan.py --files <証拠からのパス>` を通します。
失敗したチェックはその 1 件の変更を元に戻して報告し、ほかは残ります。コマンドは
`python .claude/scripts/harness-check.py` で終わり、これは終了コード 0 でなければなりません。適用した変更ごとに
`docs/context/tool-changelog.md` へ 1 件記録します: 何を変えたか、証拠、通ったチェック、誰が頼んだか。

**拒否すること。** レビューゲートを丸ごと外すこと。`/harness-tune` はどの変更がレビュー席を通るかを *絞る* こと
はできますが、ゲートを削除はしません - それは調整ではなく、別のリポジトリです。deny のエントリは、それに
代わる統制を名指ししない限り外しません。上限の引き上げや、履歴の詳しさを `full` (プロンプト全文、PII を含めて
ディスクに残る) に上げることは、そのコストを述べます。フックのロジックは決して編集しません。調整が変えるのは
データ - リスト、上限、フロントマターの値 - で、フックのコードはほかと同じくレビューされる変更です。ルール、
コマンド、フック、席をまるごとオン/オフにするのは `/harness-toggle`、席を足す/外す、またはフラグの変更は
`/harness-update` で、ここで作業せずに正しいコマンドを案内します。

## `/harness-toggle`

**何をするか。** 単一のルール、コマンド、フック、エージェントの席を、何も削除せず、`settings.json` を手で
書き換えずに、元に戻せる形でオフ/オンにします。`python .claude/scripts/harness-toggle.py` が唯一の変更手段です。
ファイルを `.claude/disabled/` の下へ移し、対応する `settings.json` の登録を外す (または戻す)、変更を
`.claude/disabled.json` に記録し、`harness-graph.json` と HTML ビューを再生成して、無効な項目が灰色に描かれる
ようにします。停止した席は同様に `.claude/disabled/agents/` に移ります。ロースターの経路表がまだその席を載せて
いるので、すべての席は少なくとも SOFT で、`orchestrator` とレビュー席は HARD です。席を停止するのは元に戻せ
ます - 席の追加や廃止は引き続き `/harness-update` です。

**いつ使うか。** このリポジトリに合わないルールやフックを、ファイルを失わずにオフにしたいとき、または
スキャフォルドの再実行が、チームが意図的に無効にしたものを復活させたとき。

**実例。**

```text
/harness-toggle
```

```text
python .claude/scripts/harness-toggle.py list
  active:
    rule/00-overview
    ...
    hook/protect-adr
    ...
  disabled:
    (none)

Disable which item? hook/protect-adr
Reason: this repo has no docs/adr/ directory yet
```

```text
python .claude/scripts/harness-toggle.py disable hook/protect-adr --yes --reason "no docs/adr/ directory yet"
  moved .claude/hooks/protect-adr.sh -> .claude/disabled/hooks/protect-adr.sh
  removed settings.json PreToolUse registration
  recorded in .claude/disabled.json (reason: no docs/adr/ directory yet)
  regenerated harness-graph.json + harness-graph.html
```

**安全の階層。** 2 つあり、慣習ではなくスクリプト自身が強制します:

- **HARD** - `protect-secrets`、`guard-agent-spawn`、`security-privacy`、`agent-guardrails`、`/review-changes`、
  そして `orchestrator` とレビュー席: `--confirm "disable <name>"` にその正確な語句がなければ拒否されます
  (終了コード 2)。その語句は、この会話での利用者自身の言葉でなければならず、利用者に代わって作ってはなりません。
- **SOFT** - `guard-main-commit`、`check-commit-msg`、`protect-adr`、`ai-governance`: 利用者が明示的に確認した
  あとで `--yes` が渡されるまで拒否されます。

**スキャフォルドの再実行を生き延びるもの。** `.claude/disabled.json` はコミットされ、チームで共有されます。
`/harness-update` も新規の `scaffold.py` の実行も、これを読むので、無効にした項目が黙って戻ってくることは
ありません。もし戻ってきたら (手編集やマージで)、もう一度無効にするのではなく
`python .claude/scripts/harness-toggle.py reapply` を実行します。

## `/agent-permissions`

**何をするか。** ちょうど 1 つのロースターの席に、ちょうど 1 つのツールを付与または取り消します。使い方:

```text
/agent-permissions <agent> grant|revoke <Tool>
```

席の現在のフロントマターを読み、変更を下の不変条件に照らして検査し、差分を見せ、承認を得て適用し、
`docs/context/tool-changelog.md` に記録します。

**いつ使うか。** 開発エージェントが、今は走らせられないビルド手順のために `Bash` を必要とするとき、または席が
ブートストラップ時に付与されすぎていて絞るべきとき。取り消しは即座に適用され、不変条件の検査は不要です -
絞ることは常に安全だからです。

**実例。**

```text
/agent-permissions app-dev grant Bash
```

```text
.claude/agents/app-dev.md
- tools: Read, Grep, Glob, Edit, Write
+ tools: Read, Grep, Glob, Edit, Write, Bash

Apply? [y/N]
```

**拒否すること (警告ではなく不変条件。覆すための確認プロンプトは出さない):**

- **レビュアーは `Edit` も `Write` も得ない。** `code-reviewer`、`security-reviewer` (`solo_review` のロースターでは
  統合された `reviewer`)、`spec-guardian`、`checker` はゲートです。編集できるゲートは、独立性を失った開発
  エージェントです。レビューの指摘を自動で適用したいなら、その指摘を持たせた開発エージェントを委任します -
  それは権限の変更ではなくタスクです。
- **`Agent` を持てるのはオーケストレーターだけ。** 2 つ目の起動役は、管理されない委任点が 2 つ目になるということ
  で、1 つ出現すればスキャフォルド自身がビルドを失敗させます。
- **`model:` と `effort:` は権限ではない。** 変更はコストとロースターの判断です - `/agent-permissions` は代わりに
  ロースターのファイルと `reference/cost-model.md` を案内し、変更を記録することは引き続き求めます。
- **ワイルドカードの付与はしない。** 席は正確なツールを列挙します。「全部与える」は、ロースターが防ごうとして
  いる既定エージェントの問題です。

## `/harness-update`

**何をするか。** すでにブートストラップされたリポジトリで、ブートストラップのスキャフォルダを、安全に、何度でも
再実行します。スキャフォルダが生成するはずのものと差があるファイルは決して上書きせず、あなたやチームが編集した
ものはすべて、手で解決する `CONFLICT` として残ります。追加的な例外が `settings.json` です。差があるとき、この
バージョンが配布するフックのうちファイルがまだ登録していないものはすべて追加され (`MERGED` と報告)、あなたが
書いたものは何も変わらず、`.claude/disabled.json` に載っているものは再登録されず、2 回目の実行では何も追加され
ません。

**いつ使うか。** スキルが欲しい新しい資産やルールを配布したとき、コードベースが変わって開発エージェントの
パスの範囲が現実と合わなくなったとき、あるいはエージェントの席を追加/廃止するとき。

**実例。**

```text
/harness-update
```

```text
Re-reading the codebase for changed areas...
  src/billing/ is new since bootstrap - no seat owns it.

Re-running scaffold.py --target . --vars vars.json
  ADDED     .claude/commands/new-skill.md       (new in this skill version)
  KEPT      .claude/agents/app-dev.md           (unchanged)
  CONFLICT  .claude/rules/testing.md            (you edited this; skill version differs)
  MERGED    .claude/settings.json: registered guard-board

4 files: 1 added, 1 kept, 1 conflict to resolve by hand, 1 merged.
Suggested: instantiate a dev-agent seat scoped to src/billing/, add it to the orchestrator's
routing table in the same change.
```

席を追加して経路表の行を追加しなければ、その席には到達できません。席のファイルがない経路の行を足せば、委任は
どこにも届きません - `/harness-update` は両方が一緒に入ることを確かめます。席を廃止するときは、まず
`/board-audit` を走らせ、Active なタスクがまだその席を担当にしていないことを確かめます。

**トグルの状態を尊重する。** `.claude/disabled.json` があれば、`/harness-update` は衝突を解決したあとに
`python .claude/scripts/harness-toggle.py reapply` を実行するので、`--force` の上書きや手編集が、チームが意図的に
無効にしたものを黙って復活させることはできません。

**記録された移植先へ再移植する。** 導入時に、ハーネスがほかのどのツールで動く必要があるかが記録されています
(`vars.json` の `target_cursor` / `target_codex` フラグと、`docs/context/tool-changelog.md` の「Target AI tools」の
行)。`/harness-update` はそれを読み、尋ね直さず、ツリーの再走査もせずに、まさにそれらの移植先に対して
`port.py` を実行します。ツリーは自分がどのツールのものかを語れないからです。ポーターの `generated by port.py`
マーカーがない `.cursor/` や `.codex/` のファイルは人が書いたものなので、`CONFLICT` と報告して手を付けません。

**チェックで締める。** 終える前に、スキャフォルダの起動境界の lint がまだ通ること、経路表がすべての席を覆うこと、
既知の不正なフックのペイロードがまだ発火することを確かめ、ハーネスグラフを再生成します
(`python .claude/scripts/harness-graph.py --html`) - スクリプトによる変更は、通常グラフを最新に保つ Edit/Write の
フックを起こさないからです。最後の手順は `python .claude/scripts/harness-check.py` で、これは終了コード 0 でなけ
ればならず、指摘はすべて file:line と直し方を示します。

**決して触れないもの。** `tech-stack.md`、`coding-standards.md`、範囲、あるいはコードや導入時の回答から導かれた
内容 - それらは `CONFLICT` の待ち行列を通り、あなたが決め、黙って上書きされることはありません。

## `/code-graph`

**何をするか。** リポジトリのモジュール境界マップを保守します。決定的に答える問いは 1 つ: コードが、誰も合意して
いないモジュールの境界をまたいで import していないか。2 つのファイルが支えます。`docs/context/code-graph.md` は
**コミットされ**、モジュールごとに 1 行 - 担当、依存先、依存元 - で、そのリストが許可されたモジュール間の辺の
集合 *そのもの* です。もう 1 つの `.claude/state/code-graph.json` は gitignore された機械用の状態 (モジュール、
モジュールごとのファイル、参照数つきの辺、ロースターの範囲から対応づけた担当) で、`guard-agent-scope`、`/new-task`、
ハーネスグラフが読みます。図は描きません。コード目的のリポジトリに配布されます。

**誰も読まなくても正直に保つ仕組み。** 非遮断の `graph-stale` フックが、ソースの編集のたびに
`code-graph.py --file` を走らせ、マップに載っていないモジュール間の import を、それを加えた編集の時点で一度だけ
名指しします。`python .claude/scripts/code-graph.py --check` は、コードにマップにない辺があれば終了コード 1 を返し
ます。レビューや CI で実行してください。`/board-audit` はその失敗を指摘として扱います。

**いつ使うか。** `--check` が失敗したとき、モジュール間の辺に触れるタスクを委任または受理する前、あるいは
エージェントが全ツリーを読まずに「このモジュールをほかに誰が呼んでいるか」の答えを必要とするとき。

**実例。**

```text
/code-graph
```

```text
python .claude/scripts/code-graph.py --check
  NEW EDGE  billing -> notifications (billing/invoice.py imports notify_customer)
This is either a missing interface or a boundary violation. Remove the import, or accept it.

Accepted: python .claude/scripts/code-graph.py
  14 modules, 212 files, 38 import edges.
git diff docs/context/code-graph.md
  billing: depends on  + notifications
```

**決してしないこと。** あなたに代わって辺を受け入れること。新しい辺はそれぞれ更新ではなく決定です。再構築こそが
受け入れであり、コミットされたマップの差分がレビューの承認対象です。辺はリポジトリのパスに解決された静的な
import です - 相対パス、ワークスペースのパッケージ名 (`package.json`、`go.mod`、`Cargo.toml`)、ディスク上に
存在する Python モジュール、`@/` と `~/` のエイリアス - なので、実行時に組み立てられる import、ほかのパス
エイリアス、C# の `using` は見えません。辺がないことは、孤立している証拠ではなく証拠の不在です。「このシンボルを
誰が使うか」は、依然として grep の仕事です。再構築のあとは `.claude/state/harness-graph.json`
(`harness-graph.py --html`) を更新します。モジュールの担当がハーネスグラフに入るからです。

**エージェントの使い方。** オーケストレーターは、委任の前に対象モジュールの行を読みます。その「Used by」の
リストが、ブリーフに書く影響範囲です。開発エージェントは読む必要がありません。編集がマップにない境界をまたぐと
フックが声を上げ、エージェントはそこで止まって、その辺を出荷せずに報告します。

**エンジン。** 既定は `.claude/scripts/code-graph.py` の標準ライブラリだけの静的抽出器で、インストール不要です。
GitNexus/codegraph の MCP サーバー (または同等のコード索引ツール) がセッションで使えるなら、より豊かな呼び出し
レベルの辺のために抽出を置き換えてもよく、ファイルの契約はどちらでも変わらないので、下流はどのエンジンが
走ったかを気にしません。

## `/docs-graph`

**何をするか。** ドキュメントの追跡可能性を検査します。各要件、決定、タスクの ID をどの文書が定義し、誰が参照
し、どれが孤立しているか。コードグラフのドキュメント版で、答える問いが違います - 依存ではなく追跡可能性です。
何も描かず、Markdown も書きません。文書、ID、辺の数と孤立 ID のリスト - 誰かが動く対象になる部分 - を表示し、
「FR-12 に触れているのはどの文書か」のような問い合わせ用に `.claude/state/docs-graph.json` (すべての ID、それを
定義する文書、それを参照するすべての文書) を書きます。自動では再構築されません。ID を定義または引用する
文書を編集したあとに実行してください。

**いつ使うか。** 仕様を編集したあと、`spec-guardian` が差分で主張される要件 ID をグラフに照らして確かめる必要が
あるとき、あるいはオーケストレーターが予定されていない要件のバックログ (孤立 ID) を知りたいとき。

**実例。**

```text
/docs-graph
```

```text
python .claude/scripts/docs-graph.py --check
  42 docs, 118 IDs, 96 edges, 3 orphan(s)
Orphans: FR-017 (defined in 05, no task references it), BR-009, ADR-0007 - unstarted work or dead references.
```

`--check` は孤立が 1 つでもあれば終了コード 1 を返し、追跡可能性を壊した編集はそれで捕まります。孤立はそれぞれ
名前で、かつ次の 2 つのどちらかとして報告されます。未着手の作業 (まだどのタスクにも他の文書にも参照されて
いない要件)、または死んだ参照 (一度だけ引用されて、どこにも定義がない ID)。

## `/skill-wire`

**何をするか。** `.claude/skills/` に導入されたスキル - または `/new-skill` でここで作ったスキル - を、ロースターの
1 つの席に結びつけます。配線は能力の決定なので、`/agent-permissions` と同じ形をとります: スキルと席を読み、
必須の内容レビューをやり直し (配線の時点で全ファイルを - `npx skills update` で導入後にテキストが変わっている
かもしれないから。プラグインのスキルならプラグインの束全体を)、範囲が席の役割に合うかを確かめ、差分を見せ、
配線を `docs/context/tool-changelog.md` に記録します。変更そのものは、席の `skills:` フロントマターに名前を 1 つ
足すことで、それが生成のたびにスキルの全内容を事前読み込みします - したがって席が実行の大半で使うスキルだけ
を事前読み込みする価値があり、`disable-model-invocation: true` のスキルは事前読み込みできないので拒否します。
探索と導入の基準は、ブートストラップスキルの `reference/skill-discovery.md` にあります: インストール数、発行元、
skills.sh の監査状況、そして何かを信頼する前にスキルのファイルを必ず読むこと。配線のあとは、`skill-check.py` が
そのスキルをもう孤立とは報告しないはずです。

**いつ使うか。** [skills.sh](https://www.skills.sh/) のスキルを導入した直後 (`npx skills add <owner/repo>@<skill>`)
や `/new-skill` で作った直後、あるいは席の作業が、すでに導入されているスキルの能力を何度も必要とするとき。

**実例。**

```text
/skill-wire pdf-processing qa-test
```

```text
Reading .claude/skills/pdf-processing/SKILL.md and .claude/agents/qa-test.md...
Content review: 3 files read, no config-edit or exfiltration instructions found.
Scope: report parsing fits qa-test's artifact checks. Diff:
  + skills: pdf-processing
Apply? [records to docs/context/tool-changelog.md]
```

**拒否すること。** 内容が `.claude/`、`settings.json`、フックの編集を指示するスキルは、どの席にも決して配線
されません。レビュアーには読み取り専用のスキルだけ。ほかのスキルを探したり導入したりするスキルを持てるのは
オーケストレーターだけです。ワークフローの知識はスキルの中にとどまります。配線は名前を足すだけで、手順を
エージェント本体にコピーすることはありません。すべての配線は記録されます - 記録のない配線は品質ゲートを
通りません。

## `/new-skill`

**何をするか。** 繰り返し現れるワークフローがプロジェクトスキルに値するかを判断し、値するときにだけ作成します。
これは 1 つの流れの最後の手段です: 既存のスキルを探し (`reference/skill-discovery.md`)、なければここで作り、
`/skill-wire` で配線します。まず内容を適切な置き場所に振り分けます - 毎セッション必要な事実は
`CLAUDE.md`/`AGENTS.md`、パスに限った制約はパススコープのルール、名前で始める手順はコマンド、役割はエージェント
定義、決定的な検査はスクリプト - そして `.claude/skills/` に拡張できる既存のスキルがないかを調べます。次に
`AskUserQuestion` で尋ね、ワークフロー、それが繰り返される証拠、「測定可能に良くなる」とは何かを示し、明示的な
了承がなければ何も作りません。了承されたら `.claude/templates/skill/` を `.claude/skills/<name>/` にコピーして
埋めます (使う場面から始まり、隣接する仕事を持つスキルを名指しする description、固定・誘導・自由の手順を持つ
本体、参照、終了コードが「完了」を意味する `scripts/validate.py`)。6 種類のトリガーケースを
`evals/trigger-cases.md` に書き、`python .claude/scripts/skill-check.py --skill .claude/skills/<name>` で lint し、
必要とする席ごとに `/skill-wire` を実行します。

**いつ使うか。** ワークフローがタスクをまたいで何度も説明し直され、公開されているものに合うものがなく、常時
コンテキストに置くには大きすぎる、または条件付きすぎるとき。作成を断ることも正常な結果です。

**実例。**

```text
/new-skill release-notes docs-writer
```

```text
Home check: a procedure started by name once per release is a command, not a skill - unless it
carries reference material the model gets wrong without it.
Evidence it recurs: 4 release-note rewrites in the session logs. Proposed: a skill. Create it? [yes/no]
```

**拒否すること。** 誰も合意していないスキルの作成、手作業で同期し続ける既存スキルの 2 つ目のコピー、配線の前に
`orphan` 以外の lint 結果が残ること、配線されないまま放置されたスキル - 全セッションで description のコストを
払うのに、誰の役にも立たないからです。取り除くのもこのコマンドの仕事です - `/skill-wire` で配線を外し、
`.claude/skills/<name>/` を削除し、理由を `docs/context/tool-changelog.md` に記録します。

## 仕様の側

さらに 2 つのコマンドが、ハーネスではなく `spec-builder` の仕様セットと一緒に届きます - 属するスキルは
`spec-builder/SKILL.md` を参照してください。

### `/spec-ingest`

**何をするか。** 新しい情報源 - 議事録、トランスクリプト、旧い文書、メールのスレッド - を、何も再生成せずに
既存の `docs/specs/` セットに取り込みます。使い方: `/spec-ingest <path-or-pasted-source>`。情報源を丸ごと読み、
抽出できる記述をそれぞれの置き場所のセクションに対応づけます (`03` の用語集の語、`05` の FR やビジネスルール、
`07` の NFR など。セクションは 1 ファイルでも、インデックスつきの `FR-nn-<slug>.md` のフォルダでもよい)。
そのうえで対応づけた記述ごとに、セクションがすでに述べていることと差分を取ります。衝突のない新しい事実は
情報源の注記つきで追加し、既存の規範的なテキストとの衝突は決して黙って上書きせず、両方の版を示して
`AskUserQuestion` でどちらが勝つかを決め、負けた方は改訂履歴に記録します。言い換えにすぎない事実は飛ばして
裏づけの注記だけを残します。作成時に選ばれなかったセクションに対応づく記述は、無理にほかへ入れず、指摘として
表に出します。

**いつ使うか。** 仕様セットがすでにあるのに新しい真実の源が現れたとき - 議事録がもう一つ、更新された
トランスクリプト、誰かがようやく見つけた旧い文書 - で、別ファイルとして付け足すのではなくセクションに照らして
整合させる必要があるとき。

**実例。**

```text
/spec-ingest meeting-notes-2026-08-12.txt
```

```text
Mapped 6 statements: 2 to 05 (new FR candidates), 1 to 07 (an NFR target), 3 to 03 (glossary terms).
Conflict: 05 already states "refund window: 14 days"; the note says "30 days".
Which wins? [14 days (current) / 30 days (new source)]
Applied: FR-22 added, NFR-09 target updated, 3 glossary terms added.
Recorded in 13-revision-history.md. Ripples: glossary.md updated, business-rules.md updated.
docs-graph --check: 0 new orphans. spec-check --write: FR-22 awaits confirmation.
```

**何を書くか。** 対応づけた先の仕様セクション、取り込みごとに `13-revision-history.md` の 1 行 (日付、情報源、
触れたセクション、追加/変更した ID、衝突を承認した人)、そしてハーネスがあれば波及先: `docs/context/glossary.md`、
`docs/context/business-rules.md`、担当の開発エージェントの FR リスト、ボード (担当モジュールのない新しい FR は
Pending のタスクになり、席への黙った割り当てにはならない)。続けて追跡可能性を検査し
(`python .claude/scripts/docs-graph.py --check`、その孤立 ID が取り込みの積み残し)、確認シートとエージェント用
の索引を `python .claude/scripts/spec-check.py --write` で再生成し (新規または変更された FR は決定が空の状態で
現れ、確認のために差し戻す合図になる)、取り込みそのものを `docs/context/tool-changelog.md` に記録します。

**拒否すること。** 手書きの内容の上にテンプレートからセクションを再生成すること。ID の振り直し - 新しい
要件は常に次の空き番号を取る。生の情報源が基準になること: 仕様が情報源を吸収するのであり、情報源が仕様に
取って代わることはない。

### `/spec-retract`

**何をするか。** すでに `docs/specs/` に吸収された情報を取り除く、または訂正します。使い方:
`/spec-retract <source-name | ID | quoted-claim>` - 信頼できないと判明した情報源全体、誤った要件 1 つ、または
特定の主張。まず影響範囲をたどります。情報源、ID、主張のキーワードに触れるすべてのセクション (フォルダ形式なら
すべての `FR-nn-<slug>.md`)、`.claude/state/docs-graph.json` が影響を受ける ID を参照していると示すすべての
文書、それらを名指しするすべてのタスク。何かを変える前に、全リストを示します。誤った値は、定義しているセクション
で直します。残る情報源のない主張は消えません - 未解決の問い (`OI-nn`: 「`<source>` が主張したが情報源が
撤回された、確認が必要」) に変換されます。黙って削除された要件は、最初からなかった要件と見分けがつかず、誰かが
その上に作っているかもしれないからです。

**いつ使うか。** 情報源が信頼できない、誤っている、あるいは置き換えられたと判明し、仕様にはすでにそれを元に
した内容があるとき。

**実例。**

```text
/spec-retract "vendor-api-notes.pdf"
```

```text
Blast radius: FR-14, FR-15 (only-sourced from this doc), BR-07 (corroborated elsewhere - stays),
2 tasks reference FR-14/15 (TASK-031, TASK-033).
FR-14, FR-15 -> Withdrawn, reason: source retracted (2026-08-14). BR-07 loses one source note, stays.
TASK-031, TASK-033 -> Blocked, human_gate: requirement withdrawn.
Recorded in 13-revision-history.md. docs-graph --check: 0 new orphans (both IDs still resolve, as
Withdrawn).
```

**何を書くか。** `13-revision-history.md` に 1 行 (何を撤回したか、なぜか、どの ID が `Withdrawn` になったか
または `OI-nn` に変換されたか、誰が決めたか)、そしてハーネスがあれば波及: 担当の開発エージェントの FR リスト
から撤回された ID を外し、それを実装している Active なタスクは `human_gate: requirement withdrawn` つきで
`Blocked` にし (作業を止めるかは人が決め、黙って削除はしない)、撤回された情報源だけが定義していた用語集の
語には異議ありの印を付けます。追跡可能性は `/spec-ingest` と同じ方法で検査し、`spec-check.py --write` を実行して
撤回された FR を確認シートから外しつつ新しい状態で `index.json` の項目に残し、撤回を
`docs/context/tool-changelog.md` に記録します。

**拒否すること。** 撤回された ID の再利用 - 撤回された `FR-nn` は番号を保ち、`Withdrawn` と印が付き、次の
要件は新しい番号を取ります。情報源が消えたというだけで主張を丸ごと削除すること - 代わりに追跡される未解決の
問いになります。

この 2 つは `harness-bootstrap` ではなく `spec-builder` スキルと一緒に配布されます - ハーネスだけを
ブートストラップしたリポジトリには、`spec-builder` も導入されるまで存在しません。

## クイックリファレンス

| コマンド | 変えるもの | 確認 |
|---|---|---|
| `/board-audit` | なし - 読み取り専用 (最初に `board-check.py` を実行) | 該当なし |
| `/harness-tune` | 実行の記録から選んだ制御レベルのダイヤル: デプロイ権限、破壊的コマンドの姿勢、起動許可リスト、上限、モデルと effort、レビューゲートの範囲、エージェント履歴の詳しさ | 順位付きで最大 4 件、質問は一度だけ。差分を見せ、各変更を確認し、最後に `harness-check.py` |
| `/harness-toggle` | ルール、コマンド、フック、エージェントの席を 1 つオン/オフにする。`.claude/disabled.json` とハーネスグラフを更新 | HARD は入力した確認語句が必要。SOFT とすべての席は `--yes` |
| `/agent-permissions` | 1 つの席の 1 つのツール | 差分を見せ、承認が必要 (不変条件違反は拒否) |
| `/harness-update` | `.claude/` を現行のスキルバージョンとコードベースに同期し、記録された移植先へ再移植する | `CONFLICT` の待ち行列を手で解決。最後に `harness-check.py` |
| `/code-graph` | コミットされるモジュール境界マップ `docs/context/code-graph.md` と `.claude/state/code-graph.json` を再構築 (コードのリポジトリ) | 新しい辺はそれぞれが決定。マップの差分がレビューの承認対象 |
| `/docs-graph` | 孤立 ID のリストを表示し、`.claude/state/docs-graph.json` を書く (Markdown も図もなし) | なし - 派生ファイルのみ。`--check` は孤立があれば終了コード 1 |
| `/skill-wire` | 導入済み、またはローカルのスキル 1 つを、1 つの席の `skills:` リストへ | 差分を見せ、承認が必要。配線時に内容を再レビュー、不変条件違反は拒否 |
| `/new-skill` | `.claude/skills/` の新しいプロジェクトスキル、そのトリガーケース、lint の実行 | 何かを作る前に明示的な了承。断ることも正常な結果 |
| `/spec-ingest` (`spec-builder`) | 仕様セクション、`13-revision-history.md` の行、用語集/ビジネスルール/ボードへの波及 | 衝突は `AskUserQuestion` で提示。ID は追加のみで、振り直さない |
| `/spec-retract` (`spec-builder`) | 仕様の内容を訂正または `OI-nn` に変換、`13-revision-history.md` の行、下流への波及 | 何かを変える前に影響範囲を提示。撤回された ID は再利用しない |

## すべてに共通する 3 つの不変条件

`/harness-tune`、`/agent-permissions`、あるいはほかの変更と同じようにレビューされる手編集、どの経路でも、次の
3 つは動きません:

1. **レビュアーは書き込み権限を得ない。** `code-reviewer`、`security-reviewer` (`solo_review` で統合されたとき
   は `reviewer`)、`spec-guardian`、`checker` は読み取り専用のゲートのまま。
2. **起動できるのはオーケストレーターだけ。** 委任の点は 1 つで、スキャフォルダのビルド検査と
   `guard-agent-spawn` が強制する。
3. **コードレビューのゲートは外せない。** それを引き起こすパスの範囲を絞れるだけ。

あわせて参照: [`roster.md`](../harness-bootstrap/reference/roster.md) 各席の役割、
[`cost-model.md`](../harness-bootstrap/reference/cost-model.md) 調整のコスト、
[`task-control.md`](../harness-bootstrap/reference/task-control.md) `/board-audit` が照合するボードの仕組み。

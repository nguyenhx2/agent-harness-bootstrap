# コンテキスト管理: 状態はモデルの中ではなくディスクに置く

[English](CONTEXT-MANAGEMENT.md) · **日本語**

このハーネスでは、エージェントの状態はモデルのコンテキストウィンドウではなく、物理的なファイルに結びついて
います。ミッションについての永続的な事実 - タスクは何か、何が決まったか、何が実行されたか、何が通ったか、
何が止まっているか、誰が担当か - は、どれも会話の中の主張になる前に、コミットされた Markdown として存在
します。だから圧縮、セッションの終了、強制終了されたプロセス、落ちた IDE は、このハーネスにとって会話を
失うことであって、ミッションを失うことではありません。

この文書は、メモリの階層、それを実装するファイル、再開の手順、強制される統制と助言にとどまる統制の序列、
そしてそれぞれの限界を扱います。

## 土台にした考え方

Alberto Arena は [CLAUDE.md is RAM, not disk](https://albertoarena.it/posts/claude-md-is-ram-not-disk/) で、
コンテキストの予算管理のたとえを示しています:

- `CLAUDE.md` は **常に読み込まれる作業メモリ** です。すべてのセッションのすべてのターンで消費されます。
  つまり RAM です。
- `docs/` は **必要なときに読む長期記憶** です。必要になるまで読みません。つまりディスクです。
- 彼が提案するテストは 1 つの問いです。*「Claude はこれを毎回必要とするか、時々だけか。毎回なら CLAUDE.md、
  時々なら docs/」*。
- 肥大した `CLAUDE.md` は Claude を良くするどころか **悪くします**。目の前のタスクに無関係な詳細でウィンドウを
  埋め、その無関係さの分のトークンを毎ターン課金します。劣化の始まりを彼は「200 行あたり」としています。
- 入れ子の `CLAUDE.md` はルールをフォルダに限定するので、フォルダ固有の詳細がルートに負担をかけません。
  スキャフォルダがそれを書きます。分析で見つかった各モジュールが専用の `CLAUDE.md` (担当、範囲、局所的な
  不変条件、コマンド。40 行まで) を持ち、そこのファイルが読まれたときだけ読み込まれます。

このリポジトリはそれに従っています。`harness-bootstrap/assets/root/CLAUDE.md` は 1 つの `@AGENTS.md` の import の
上に載る薄い Claude 固有の層で、`AGENTS.md` は予算を明示するコメントを持ちます:

> `Keep AGENTS.md and CLAUDE.md under about 200 lines combined: instruction adherence drops on longer
> files. Detail belongs in .claude/rules/, which is read on demand, not here.`

数字も理由も同じです。

## このリポジトリがさらに進める点

Arena のたとえは **大きさ** の話です。毎ターン読み込む価値のあるものは何か。このリポジトリはそれを
**耐久性** に広げます。ウィンドウが失われたとき、何が残るか。

RAM は高いだけでなく揮発します。モデルのコンテキストにしか存在しないものは、すでに失われています。圧縮は
それを要約して具体を捨てます。セッションの終了はそれを破棄します。クラッシュしたエージェントは作業メモリを
道連れにします。落ちた IDE はウィンドウを丸ごと奪います。`.claude/rules/task-tracking.md` はこれらを日常の
出来事として扱います:

> `Context loss is routine; treat recovery as routine too.`

したがって設計上の問いは「毎ターン何を読み込むか」だけではありません。次の問いです:

> **空のコンテキストの新しいエージェントが、作業が止まった場所からそのまま引き継げるように、何が書き
> 残されているか。**

以下のすべては、この問いへの答えです。

## 1. メモリの階層

2 層ではなく 4 層です。Arena が挙げる 2 層はどちらも RAM で、その下の 2 層に作業の状態が実際にあります。

<img src="assets/memory-hierarchy.svg" alt="4 つのメモリ層: 常時 RAM、遅延 RAM、ディスク、アーカイブ。それぞれのコストと、圧縮後に残るもの (図の文言は英語)">

| 層 | そこにあるもの | 読み込まれる時 | コスト | 圧縮による影響 |
|---|---|---|---|---|
| **常時 RAM** | `CLAUDE.md` (`@AGENTS.md` と Claude 固有の層だけ)、`.claude/rules/` の無条件の 7 ファイル (フラグをすべて有効にした場合: `ai-governance.md` は `ai` のときだけ、`output-style.md` は `terse` のときだけ配布)、エージェント自身の本体、ツールのスキーマ | すべてのセッション、すべてのエージェントで、どのファイルにも触れる前に | ルールだけで約 23,000 バイトが、毎ターン、永久に再送される | 残る。プロジェクトルートの `CLAUDE.md` は圧縮後に再注入される。**入れ子の** `CLAUDE.md` は再注入されず、そのディレクトリのファイルがもう一度読まれたときにだけコンテキストに戻る |
| **遅延 RAM** | `.claude/rules/` のパススコープ付きの 10 ファイル (`paths:` フロントマター) | Claude がグロブに合うファイルに触れたときだけ | 約 62,000 バイト。ほとんどのセッションは支払わない | 引き金と同じ規則に従う。ウィンドウから消え、合致するファイルに再び触れたときに再読み込みされる |
| **ディスク** (作業の状態) | `docs/tasks/master-plan.md` (ボード) と `docs/tasks/active/TASK-NNN.md` (目標、範囲、受け入れ基準、決定と阻害要因、セッションログ) | 必要なときに、明示的な `Read` で | セッションごとに数百バイトを一度読む | **何も起きない。** git にコミットされた Markdown。あらゆることに耐える層 |
| **アーカイブ** (追記のみ) | `.claude/state/history/` - 終了したサブエージェントの実行ごとに 1 つの Markdown。与えられたプロンプトと最終応答を保持 | 読まない限り決して読み込まれない | 誰かが求めるまでゼロ | 何も起きない。事後にフックが書くので、どれだけコンテキストを失っても消せない |

### 常時 RAM: 無条件の 7 ルール

`.claude/rules/00-overview.md` が読み込みの契約を述べています:

> `No paths: frontmatter means the file loads into EVERY session, at CLAUDE.md priority. Only this
> file and the ones listed as always loaded below earn that: they either bind the agent's behavior or
> decide what may be sent where, and both questions arise before any file is touched. Keep them short.`

常時読み込まれるのは `00-overview.md`、`agent-guardrails.md`、`model-policy.md`、`task-tracking.md`、
`conventional-commits.md` です。さらに 2 つが、フラグが求めたときだけ加わります。`ai-governance.md` は `ai`
フラグのときだけ配布されます (AI 機能を持たないプロジェクトには不要だから)。`output-style.md` は `terse` フラグが
立っているときだけです - すべての回答の書き方を決めるのでパスで絞れず、常時読み込まれるルールは恒久的な
コンテキストコストなので、既定では無効にしています。`model-policy.md` は、すべてのセッションが必要とするもの
(データ分類と STOP 規則) だけを持ちます。席の階層、モデル入れ替えの手順、deny リストの強制は、エージェント
ファイルか `settings.json` を変更するときだけ読み込まれる、パススコープの `model-tiers.md` に移しました。
常時読み込みのファイルは、原理上もパスで絞れません:

- `conventional-commits.md` が扱うのはコミット *メッセージ* で、メッセージはファイルではないので、どのグロブも
  決して合致しません。このファイルを意図的に 25 行未満に保っているのはそのためです。
- `model-policy.md` (と、配布される場合は `ai-governance.md`) は、どのファイルも開く *前に*、何をどのモデルに
  送ってよいかを決めます。まだ読まれていないファイルに絞り込むのは筋が通りません。
- `task-tracking.md` が席を得ている理由は、その冒頭の 1 行が述べています: *「すべてのセッションで読み込む。
  意図的に。状態の置き場所を忘れたエージェントは、それを作り出してしまう」*。ディスクの場所を教える層は、
  RAM にいなければなりません。

### 遅延 RAM: 73%

`.claude/rules/` のそれ以外はすべて `paths:` ブロックを持ちます:

```markdown
---
paths:
  - "{{UI_GLOBS}}"
---
# Frontend
```

`benchmark/RESULTS.md` が効果を測っています。無条件の 7 ルールが 23,047 バイト、パススコープのルール 10 本が
62,365 バイト。**ルール本文の 73% が既定のセッションの外に出ます。** データベースのエージェントはフロントエンドの
ルールを抱えず、UI のエージェントはマイグレーションのルールを抱えません。`reference/cost-model.md` はこれを
「得られる最大の継続的な節約で、かかるのはフロントマターだけ」と呼びます。Arena のテストを機械的に適用した
ものです: *毎回* は無条件、*時々* にはグロブ。

### ディスク: ミッションの状態がある場所

2 つのファイル:

- **`docs/tasks/master-plan.md`** - ボード。タスクごとに 1 行: ID、題名、担当、依存、優先度、フェーズ、状態。
  タスク ID を割り当てるのはこれだけです (`task-control.md`: *「ボードがタスク ID を割り当てる。ブリーフは
  決して割り当てない」*)。
- **`docs/tasks/active/TASK-NNN.md`** - タスクごとに 1 ファイル。`docs/templates/TASK.md` から作ります。
  フロントマターの `status:`、目標、入力、受け入れ基準、決定と阻害要因のセクション、**チェックポイント**
  (次の一手、最後の成功したコミット、未解決の問い)、そして **セッションログ**: `| Date | Who | What was done |
  Result |` の表。ファイルは新しい行を保持し、古い行は `docs/tasks/log/log-TASK-NNN.md` にたたみます。これは
  コミットされる証拠のままですが、タスクを再開するたびに読み直されることはありません。

状態は意図的に重複させています。タスクファイルのフロントマターとボードの行に一度ずつ書き、ファイルの置き場所
(フォルダ) がそれに従います。それらを一緒に書くのが 1 つのコマンド `python .claude/scripts/task.py`
(`new`、`move`、`log`、`gate`、`checkpoint`、`attempt`、`resume`、`check`) です。書き込みの後でボードの行を
読み直し、反映されていなければ大きな音を立てて失敗します。*「誰も確認していない書き込みは、願いごとだ」*
からです。タスクの行の手編集は `guard-board` フックが遮断し、`task.py` は `guard-task-scope` と同じ拒否
(記録された依頼と 2 つの実在する基準がないタスクは作らない) を適用するので、このコマンドがそのフックの
抜け道になることはありません。

5 つの状態は、`docs/templates/TASK.md` のフロントマターのコメントに一度だけ定義されています:
`Planned | Active | Blocked | Pending | Done`。ほかのファイルはどれも、それを繰り返さずに定義へリンクします。

ディスクの中でも、2 つの層は役割が違うので別に名前を付ける価値があります。`docs/tasks/active/*` は
**チェックポイント** の層です。タスク単位で頻繁に書き換わる進捗状態で、再開したセッションが止まった場所を
知るために最初に読みます。`docs/context/*` (ビジネスルール、用語集、既知の問題、ツール変更履歴) は
**ストア** の層です。タスク横断の耐久的なプロジェクト知識で、1 つのタスクではなくリポジトリの生涯にわたって
蓄積され、セッションあたりの変化ははるかに小さい。

クラッシュ復旧のためだけに存在する規則が 1 つあります。**`Planned` のタスクファイルは `pending/` ではなく
`active/` に置く。** `task-control.md` より:

> `The orchestrator's session-start scan reads docs/tasks/active/ - that directory means "on the work
> queue", not "being worked right now". Filing a newly-registered task under pending/ would hide it
> from the scan, and it would never be picked up.`

ディレクトリ構成は整理のためではありません。再開の手順が走査する索引です。

これらのファイルは **コミットされ**、記述する作業と同じ PR に載ります (`task-control.md`、フェーズ 3、手順 4)。
だからセッションだけでなく、マシンをまたいで生き残るのです。

### アーカイブ: 追記のみの実行記録

`.claude/hooks/agent-history.sh` (と `.ps1` の双子) は、`settings.json` で **`SubagentStop`** イベント、
マッチャー `*` に登録されています。どのサブエージェントが終了しても、フックはそのサブエージェント自身の
JSONL トランスクリプトを読み、最初のユーザーターン (与えられたプロンプト) と最後のアシスタントターン
(最終応答) を取り出し、`.claude/state/history/<timestamp>-<agent>-<slug>-<rand>.md` に書きます。

重要な性質が 2 つあります:

- **エージェントが選んでする作業ではない。** ハーネスがやります。セッションログの行を書かずにクラッシュした
  エージェントでも、アーカイブの項目は残ります。フックは停止イベントで発火し、エージェントの協力に
  依存しないからです。
- **常に終了コード 0。** フックのヘッダー自身が契約を述べています: *「このフックは実行を決して止めてはならず、
  例外を投げてもならない」*。ビルドを壊しうる監査証跡は、人がオフにしてしまう監査証跡です。

`history-tracker` エージェント (`haiku`、`effort: low`、`maxTurns: 10`) は、このアーカイブを読むためだけに
存在し、その指示は端的です: *「穴を、もっともらしい再構築で埋めない - アーカイブが語らないなら、答えは
『アーカイブは語っていない』」*。

**限界:** `.claude/state/` は **gitignore されています**。アーカイブは、エージェントを走らせたマシンの
ディスク上にあるので、圧縮、セッションの終了、プロセスの死を生き延びます。別のマシンでの新規クローンは
生き延びません。`model-policy.md` はこれを正確に述べています: *「`.claude/state/history/` の実行アーカイブは
ディスク上にあり、gitignore されていても通常はバックアップされる」*。コミットされたタスクファイルが耐久的な
層で、アーカイブは鑑識用の層です。

### 長期セッション用のフック: セッションが居場所を見失う 2 つの瞬間

`long` フラグがあると、ルールには見えないものを 2 つのフックが覆います。`compact-checkpoint`
(`PreCompact`) は圧縮のたびに `.claude/state/compact-checkpoint.md` を書きます: ブランチ、進行中の各タスクとその
状態、担当、チェックポイントの行、最初の未完了項目、コミットされていない変更。タイムスタンプはなく、毎回
上書きされ、終了コードは常に 0 です。コンテキスト上限のエラーで引き起こされた自動圧縮を止めると、リクエスト
自体が失敗するからです。`session-context` (`SessionStart`) は進行中のタスクを担当と次の一手つきで、最大 8 件
注入し、圧縮の後にはチェックポイントのファイルを指し示します。どちらもタスクファイルの代わりにはなりません。
どちらも、そちらを指し示すだけです。

### バイトの安定性: ディスクが RAM をキャッシュ可能にする理由

`reference/cost-model.md` には、キャッシュのコツに見えて、実はこのアーキテクチャの言い換えである規則が
あります:

> **エージェント本体、ルールファイル、CLAUDE.md は、実行をまたいでバイト単位で安定していなければならない。**
>
> `Put volatile state where it belongs - in the task file under docs/tasks/, which the agent reads as
> a message, not in the system prompt it is.`

プロンプトキャッシュは `tools` -> `system` -> `messages` に対する接頭辞の一致です。エージェントファイルの
先頭に `Generated: 2026-07-14` という 1 行があるだけで、そのエージェントのキャッシュが以後の実行のたびに
ミスになります。したがって、状態を耐久的にする規律 (`docs/tasks/` に書く) は、RAM の層を 10 倍安くする規律
(システムプロンプトをバイト単位で同一に保つ) と同じです。1 つの規則を、両端から見たものです。

## 2. 会話の記憶が記録ではない理由

`.claude/rules/task-tracking.md` は次の断言で始まります:

> `The conversation is not the record. Context gets compacted, sessions end, agents are replaced
> mid-flight. What survives is what is written down.`

これが防ぐ失敗は「エージェントが忘れる」ことではありません。エージェントは覚えていても、その記憶が証拠として
無価値であることです。テストスイートを走らせ、緑を見て、それを書き残さなかったエージェントは、オーケストレーター
が読めないコンテキストウィンドウの中に、真の信念を持っています。圧縮はそれを「テストを実行した」に要約し、
クラッシュはそれを消します。下流の誰にも検証できません。そこでハーネスは、それは起きなかったことにすると
規定しています:

> `A gate counts as passed only when the task file's session log records the run. A claim in a chat
> message, a PR description, or an agent's final report is a claim, not a fact. Verify against git
> state and the log.`
> - `.claude/rules/task-tracking.md`

オーケストレーターも、反対側から同じ規則を負っています (`orchestrator.md`、セクション 4):

> `Do not take "done" on faith. An agent's "done" / "passed" / "merged" is a CLAIM to verify against
> git and the task file, never a fact.`

`task-control.md` は、これを生んだ実際の失敗を挙げています: *「オーケストレーターが、レビュアーの行が 1 行もない
ログの上で『すべてのゲートが緑』と報告したことがある」*。

これは `AGENTS.md` の不変の原則 5 で、他者の主張だけでなく自分の主張にもエージェントを縛ります:

> `**Verify, do not trust.** An agent's "done", "passed", or "merged" is a claim, not a fact. Check it
> against git and the task file before acting on it. **This includes your own claims.**`

書き残すことは、本来の作業に後付けした帳簿ではありません。作業を、それをしたエージェント以外の誰にとっても
検証可能にする方法です。

## 3. 再開の手順

<img src="assets/crash-resume.svg" alt="再開の手順: task.py resume による未完了タスクの一覧、ダイジェストの読み取り、git との照合、孤立したワークツリーの整理、そして続行 (図の文言は英語)">

### セッション開始: ミッションを受ける前に走査する

`orchestrator.md`、セクション 1。新しいミッションを受ける **前に**:

```
python .claude/scripts/task.py resume
python .claude/scripts/task.py check
```

引数なしの `resume` は未完了のタスクを、人の判断待ちのものを先頭にして一覧し、`check` はボードとタスクファイルが
一致していることを確かめます。その後 `docs/tasks/master-plan.md` を読みます。そして:

> `Unfinished work takes priority: read the task file's session log and continue from the recorded
> state. **The task files, not conversation memory, are the source of truth** - this is what makes the
> base survive compaction.`

未完了の作業は新しいミッションに優先します。走査が先なのはそのためです。走査より先に新しい指示を受けた
オーケストレーターは、すでにボードを分岐させています。

### ファイルから組み立て直す

`/task-resume TASK-NNN` (`.claude/commands/task-resume.md`) がこれを行います。許可ツールの一覧自体が統制です:
`Bash(git status)`、`Bash(git diff:*)`、`Bash(git log:*)`、`Bash(python:*)`、`Bash(python3:*)`、`Read`、`Grep`。
`Edit` も `Write` もありません。コミットも、プッシュもできません。読んで、照合するだけです。

4 つの手順:

1. `python .claude/scripts/task.py resume TASK-NNN` を実行する。ボードの行、チェックポイント (次の一手、最後の
   成功したコミット、未解決の問い)、未完了の受け入れ基準、直近のセッションログの行、そして HEAD と作業
   ツリーがチェックポイントと一致するかを表示する - ログ全体を読む代わりのダイジェスト。
2. **会話の記憶よりそれを信頼する。** *「会話は圧縮されたかもしれないが、ファイルはコミットされている」*。
   ダイジェストが答えない部分についてだけ、タスクファイルをさらに読む。
3. ずれやコミットされていないパスが報告されたら、まず整合させる。*「ファイルは意図を記録し、ツリーは現実を
   記録する。食い違うときは、続行する前に整合させる。コミットされていない作業を調べ、完了まで進めるか、
   エスカレーションする。stash も、破棄も、上書きも決してしない」*。
4. チェックポイントの次の一手から続行する。完了した単位ごとに `task.py log` で記録し、状態は `task.py move`
   でのみ変え、止まる前にチェックポイントを書き直す。

引数なしで実行すると何も再開しません。未完了のタスク (`Planned`、`Active`、`Blocked`) を、人の判断待ちを先頭に
して一覧するだけです。

### クラッシュからの復旧

`task-control.md` より:

**一度にプロジェクトを動かせるオーケストレーターは 1 つだけ。** クラッシュしたインスタンスは後から自動で
再開しうるので、後任は何かを委任する前に、前任が実際に終了していることを、死んだと推定するのではなく
**確かめなければなりません**。2 つのオーケストレーターが生きていれば、委任は重複し、マージは衝突します。

**黙って止まることはクラッシュと数える。** `orchestrator.md` より: *「黙って停止したインスタンスはクラッシュした
ものとして数える」*。そして `task-control.md` より: *「黙り込むことは、クラッシュするのと同じ失敗モードである。
監督者は長い沈黙を同じように扱う - インスタンスはクラッシュしたと推定し、ファイルの状態から再開する。
設計上、それはうまくいく」*。

**突き合わせは、クラッシュ後の最初の委任の前に必須:**

1. git の現実を記録された計画と比べる: `git worktree list`、`git branch -a`、`git log` を、ボードとタスク
   ファイルと照らし合わせる。
2. 進行中のブランチやワークツリーをすべて分類する: すでにマージ済み (片付ける)、完成しているが未マージ
   (ゲートを再実行してからマージ)、作業途中で放棄された (差分を調べ、引き取るか、タスクをやり直す)。
3. クラッシュしたインスタンスが残した、孤立してロックされたワークツリーと古いブランチを取り除く。
4. 影響を受けたタスクファイルのセッションログに、その出来事を記録する。*「監査証跡を正直に保つために」*。

**信頼の順序は、規則として定められている:**

> `Committed files and git state OVER any agent's final report. A status report can reference branches
> or work that do not exist. Verify every claim against git facts.`

### MISSION-COMPLETE マーカー

ミッションを終えて待機しているオーケストレーターは、クラッシュしたオーケストレーターと同じ信号 - 沈黙 - を
出します。どちらを取り違えても高くつきます。終わったミッションを再委任すれば作業が重複し、クラッシュした
ものを見捨てれば作業が失われます。

そこで終了処理は、耐久的で機械で確認できるマーカーを書きます (`orchestrator.md`、セクション 6):

1. ミッションの各タスクを `task.py move` で終端状態に移す。ファイル、そのフォルダ、ボードの行を一緒に更新し、
   **行を読み直して書き込みが反映されたことを確かめる。**
2. ミッションのログに最後の行を追記する:
   `task.py log TASK-NNN "MISSION COMPLETE - board audited" Done`

そのあとで要約を出し、**終了します**。居残りを禁じる規則は明示されています: *「終了処理の後に待機し続けて
はならない。待機中のインスタンスはクラッシュしたものと見分けがつかず、居残りは同じボードに対して重複した
オーケストレーターが起動される原因になる」*。

判別は判断ではなく `grep` になります (`task-control.md`):

- **マーカーなし + 沈黙 = ミッションの途中でクラッシュ** -> ファイルの状態から再開する。
- **マーカーあり + 沈黙 = 完了** -> 再開も再委任もしない。*「進行中のものは何もなく、そのインスタンスを
  止めることは割り込みではなく後片付けである。状態はすべてコミットされたファイルにすでにある」*。

モデルの世界での曖昧さは、2 つの場合をディスク上で違うものにすることで解消されます。

### 手順: タスクの途中で IDE が落ちた

1. **開き直す。ブリーフし直さない。** エージェントが何をしていたかと自分が思うことを貼り付けない。それは、
   設計が防ごうとしている失敗そのもの、つまり記録された状態として思い出した状態を持ち込むことになる。
2. **古いプロセスが消えたことを確かめる。** IDE のウィンドウが落ちても、エージェントのプロセスが終了した
   とは限らない。終了を確認し、決して想定しない。
3. **`/task-resume`** を引数なしで。`docs/tasks/active/` の未完了のタスクをすべて一覧する。
4. **`/task-resume TASK-NNN`** を、進行中だったものに対して。`task.py resume` が出すダイジェストを読み、
   ダイジェストが答えない分だけタスクファイルを読む。
5. **git と整合させる。** `git status`、`git diff`、`git log`、`git worktree list`、`git branch -a`。タスク
   ファイルは意図を、ツリーは存在するものを語る。ツリーにあるコミットされていない作業は、調べて完了まで
   進めるかエスカレーションする - **stash も、破棄も、上書きも決してしない**。
6. 影響を受けたタスクファイルに、セッションログの行として **出来事を記録する**。
7. **続行する。** 最後のセッションログの行が再開点。

クラッシュしたエージェントが何を頼まれ、最後に何を言ったかは、`.claude/state/history/` を読みます。それを
読むのが `history-tracker` エージェントです。

## 4. 統制の面を、硬さで序列づける

重要な区別は、**強制** と **助言** です。このリポジトリは、自分の統制のどれがどちらかを明記しています。完全な
序列は、単独で引用できる 1 枚の文書になりました:
[`harness-bootstrap/reference/control-surfaces.md`](../harness-bootstrap/reference/control-surfaces.md)。
`settings.json` の deny ルール、PreToolUse フック、ツールの許可リスト、`maxTurns` が何を強制し、ルール、
エージェント本体、`effort:` が何を助言するにとどまるか、助言の統制を強制に変える方法、そして硬くできな
かったものを扱っています。`harness-bootstrap/SKILL.md` の品質ゲートがそこへ戻りリンクしています。

## 5. 失敗の具体例

開発エージェントが、`FR-07` を、`feat/task-014-invoicing` ブランチで、専用の git ワークツリーの中で `TASK-014`
として実装して 40 分が経っています。失敗するテストを書き、通るようにし、2 回コミットし、セッションログに
3 行追記しました。4 つ目の変更の途中で、IDE のプロセスが強制終了されます。

**完全に、取り戻せずに失われるもの:**

- 会話。すべてのターン。
- モデルの作業メモリ: 3 つの案のうちどれを、なぜ退けたか、次の編集の作りかけの計画、開こうとしていたファイル。
- エディタのバッファにしかなかった、保存されていない編集。

**書きながら進めていたので残るもの:**

- **ブランチと 2 つのコミット** - git の中、ディスク上、ワークツリーの中。
- **タスクファイル** `docs/tasks/active/TASK-014.md`: `status: Active`、担当、受け入れ基準、決定と阻害要因の
  箇条書き、最後に書いた行までのセッションログ。
- `docs/tasks/master-plan.md` の **ボードの行**。`TASK-014 | Active` を示している。
- `.claude/state/history/` の **アーカイブ**。エージェントに渡した正確なプロンプトと、完了した最後の応答。
- コミットされていない **作業ツリーの変更** - バッファの中ではなくディスク上にあり、`git status` で見える。

**復旧:**

新しいオーケストレーターが空のコンテキストで始まります。`task.py resume` を実行し、新しい作業を何も受ける前に
`TASK-014` を見つけます。古いプロセスが死んでいることを確かめ、`/task-resume TASK-014` を実行し、ダイジェスト -
ボードの行、チェックポイント、未完了の受け入れ基準、セッションログの行 - を読み、ダイジェストが答えない部分を
タスクファイルで補います。`git status`、`git diff`、`git log`、`git worktree list` を実行すると、ワークツリーは
無傷で、ブランチに 2 つのコミットがあり、コミットされていない変更が 1 かたまりあります。セッションログに
出来事の行を記録し、コミットされていない作業を引き取り、ログが次だと言っている受け入れ基準から続けます。

何も再導出されませんでした。同じ決定が二度なされることもありませんでした。ミッションが失ったのは 40 分の
会話で、作業は 0 分です。

これがうまくいったのは、クラッシュ時に何か賢いことが起きたからではありません。クラッシュ時には何も起きて
いません。プロセスがただ止まっただけです。うまくいったのは、エージェントが書きながら進めていたからです。
意味のある作業単位ごとにセッションログの行、あらゆる場所に同時に反映する状態の更新、グリーンなテストごとに
1 コミット。クラッシュ復旧は後から足す機能ではありません。必要になる前に状態がすでにディスクにあったときに
だけ、無料で手に入る性質です。

## 出典

上のすべての主張は、このリポジトリのファイルに行き着きます:

- `harness-bootstrap/reference/task-control.md` - 状態機械、ライフサイクル、クラッシュ復旧、単一インスタンスの
  規律、完了マーカー。
- `harness-bootstrap/reference/control-surfaces.md` - 強制と助言の統制の完全な序列。この文書のかつての
  セクション 4 から切り出したもの。
- `harness-bootstrap/assets/claude/rules/task-tracking.md` - タスクファイルが正本であること、ゲートの証拠の規則、
  圧縮後の手順。
- `harness-bootstrap/assets/claude/rules/00-overview.md` - ルール読み込みの契約。
- `harness-bootstrap/assets/claude/rules/agent-guardrails.md` - 4 つの強制の層。
- `harness-bootstrap/assets/claude/agents/orchestrator.md` - セッション開始の走査、「検証せよ、信頼するな」の規則、
  MISSION COMPLETE マーカー。
- `harness-bootstrap/assets/claude/agents/history-tracker.md` - アーカイブを読むのは誰か。
- `harness-bootstrap/assets/docs/templates/TASK.md` - 正準の 5 状態、セッションログ。
- `harness-bootstrap/assets/docs/master-plan.md` - ボード。
- `harness-bootstrap/assets/claude/commands/task-resume.md` - 再開のコマンド。
- `harness-bootstrap/assets/scripts/task.py` - ボードの CLI: 状態を変えるコマンドは 1 つで、`/task-resume` が
  読むダイジェストもここから。
- `harness-bootstrap/assets/claude/hooks/compact-checkpoint.sh`、`session-context.sh` - `long` フラグの圧縮時
  とセッション開始時のフック。
- `harness-bootstrap/assets/root/AGENTS.md`、`CLAUDE.md` - 契約と、その Claude 固有の層。
- `harness-bootstrap/assets/claude/settings.json` - deny ルールとフックの登録。
- `harness-bootstrap/assets/claude/hooks/agent-history.sh`、`hooks/README.md` - SubagentStop のアーカイブ。
- `harness-bootstrap/reference/cost-model.md` - パススコープのルール、バイトの安定性、`maxTurns`。
- `benchmark/RESULTS.md` - 73% という数字。
- `eval/guardrail_eval.py` - `hooks_strict`、`long`、`db` を有効にしたハーネスでの 266/266 (フラグの組は
  スクリプトの `VARS`)。
- `docs/ASSESSMENT.md` - 何が強制され、何が助言にとどまるか、なぜルーティングはフックにできないか。

外部:

- Alberto Arena, [CLAUDE.md is RAM, not disk](https://albertoarena.it/posts/claude-md-is-ram-not-disk/) -
  RAM とディスクのたとえ、「毎回か時々か」のテスト、肥大した `CLAUDE.md` が性能を下げるという観察。耐久性への
  拡張、4 層の階層、再開の手順は、このリポジトリのものです。

# harness-graph.json - スキーマ契約 (バージョン 1)

[English](HARNESS-GRAPH-SCHEMA.md) · **日本語**

`.claude/state/harness-graph.json` は、ハーネスを導入したリポジトリの制御面を機械可読な形で表した正本です。
エージェント、ルール、コマンド、フック、スクリプト、コードモジュール、進行中のタスクのすべてと、それらの間の
型付きの関係が入っています。書き出すのは `.claude/scripts/harness-graph.py`、または出力がバイト単位で同一の
`harness-view scan` です (`scripts/check_graph_parity.py` が両者をそこに縛っています)。描画するのは
`graph-html.py` で (`docs/context/harness-graph.html`、Flow ビューと Graph ビュー)、`harness-view` ネイティブ
ビューアのような外部ツールが読み込みます。このファイルを読むものは未知の追加キーを許容しなければならず、
書くものは下記の保証を守らなければなりません。

## 保証

- **決定的**: ノードは `id` 順、エッジは `(from, to, type)` 順、JSON のキーはソート済み、インデントは
  スペース 2 つ、末尾に改行、タイムスタンプなし。同じツリーを 2 回スキャンしても、バイト単位で同一です。
- **閉じた列挙**: ノードの `type` とエッジの `type` は、ここに挙げた値だけを使います。値を追加するときは
  `version` を上げます。
- **自己完結**: id はファイル名の語幹から作る安定した文字列で、配列の添字は使いません。

## トップレベル

```json
{ "version": 1, "nodes": [ ... ], "edges": [ ... ] }
```

## ノード

| フィールド | 型 | 備考 |
|---|---|---|
| `id` | string | `<prefix>:<name>` - 接頭辞は `agent:` `rule:` `cmd:` `hook:` `script:` `mod:` `task:` `gate:` `skill:` `instr:`。加えて接頭辞なしの id `settings` と `human` |
| `type` | enum | `agent` `rule` `command` `hook` `settings` `script` `module` `task` `gate` `human` `skill` `instruction` |
| `label` | string | 必ずあります。コマンドは `/<name>`、合成ノードは `Merge request` と `Human`、settings は `settings.json`、スクリプトは `<name>.py`、モジュールはモジュールのパス、それ以外は素の名前 |
| `file` | string? | リポジトリ相対パス。合成ノードとモジュールノードにはありません。フックに両方の形式があるときは、`.sh` があればそれを、なければ `.ps1` を指します (同じ拡張子なら有効な形式が無効な形式に優先) |
| `disabled` | bool | 必ずあります。該当しないときは `false`。項目が `.claude/disabled/` の下にあるか、`.claude/disabled.json` に載っているとき true |
| `synthetic` | bool? | `gate:merge-request` と `human` だけ true (Flow ビューの起点で、ファイルなし) |
| `meta` | object? | 型ごとの追加情報。下記参照 |

型ごとの `meta`:

- `agent`: `model`? (未設定なら無し。ランタイムは inherit と読みます)、`effort`?、`maxTurns`? (整数)、
  `tools`? (文字列のリスト。括弧の外のカンマで分割するので `Agent(a, b)` は 1 要素のまま)、
  `description`? (フロントマターの `description:`。トリム済みで 300 文字まで)。それ以外のサブエージェントの
  フロントマターのフィールドも、設定されていればそのまま載ります - `permissionMode`、`memory`、`isolation`、
  `color`、`background`、`omitClaudeMd`、`disallowedTools`、`skills`、`mcpServers`、`hooks`、`initialPrompt`、
  `cacheTtl`、`name` (ファイル名と違うときだけ)。さらに `spawns` (`Agent(...)` の中の名前)、
  `spawnAllowlist` (`.claude/hooks/spawn-allowlist` の各行)、`tier` が付きます。形式は
  `tools/harness-view/SCHEMA.ja.md` の「エージェントのメタ情報」にあります。冒頭の `---` の前にある UTF-8 BOM は無視します。
- `rule`: `scoped` (bool - `paths:` フロントマターがあるか)、`paths`? (先頭のグロブ、最大 8 個、値は
  引用符なし - フロントマターの単一または二重引用符は外します)、`description`?
- `command`: `description`? のみ (エージェントと同じ規則)
- `hook`: `registered` (bool - settings.json、または席自身のフロントマターの `hooks:` が登録しているか)、
  `event`? と `matcher`? (最初の登録。settings.json が先)、`events`? (登録が複数あるときの、すべての
  `"<Event> <matcher>"`)、`scope`? (settings.json が登録していないとき、登録している席。その席が動いている間
  だけ発火します)、`blocking`? (登録のどれかが `PreToolUse` または `PermissionRequest` - ツール呼び出しを
  止められるイベント - のとき true)、`library`? (フックが未登録で、登録済みのフックが共有の `_lib.sh` の
  ように読み込んでいるとき true。無効化されたフックではなく補助ファイルです)
- `task`: `title`? `status`? `fr`? `owner`? `deps`? `priority`? `phase`? - タスクのフロントマターにある
  ボードのフィールド。行末の YAML コメントは取り除くので、テンプレートの
  `status: Done # Active | Blocked | Pending | Done` は `Done` と読みます。orchestrator-kit のボード上の
  タスクには `mission`?、`attempts`?、`board`、`drift`? も付きます - `tools/harness-view/SCHEMA.ja.md` の
  「タスクボード」を参照。
- `module`: `files` (整数) と `owner` (code-graph.json のエージェント名。担当なしは `"-"`) の両方
- `skill`: `description`? (フロントマターの `description:`。エージェントと同じ規則)。スキルが自前の `agents/` または
  `scripts/` ディレクトリを持つときは `own_agents`? (整数) と `own_scripts`? (整数)。これらのファイルはスキル
  内部のものなので、ハーネスのノードとしては意図的に出力しません。ロースターの席ではないからです。
- `instruction`: `tools` (そのファイルを読むツール)、`source` (それが文書化されている場所)、
  `verified` (bool - 出典があるか)、`note`?。`tiers`? (「変更ごとにどれだけの手順を踏むか」の表。それを記して
  いる指示ファイルから読み取ります) と `edit`? (ビューアが書き込めるもの) は `meta` と並びます。対象は出典付きの
  閉じた許可リストです - `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`.cursor/rules/*.mdc`、`.kiro/steering/*.md`、
  Antigravity のルールフォルダ。ルートより下にある `AGENTS.md` や `CLAUDE.md` のフォルダごとのコピー
  (モジュール自身の `CLAUDE.md`) も、`instr:claude/<リポジトリ相対パス>` というノードになります。フィールドと
  出典は `tools/harness-view/SCHEMA.ja.md` の「指示ファイル」にあります。
- `settings`: `otherHooks`? のみ - `.claude/hooks/` のスクリプトを実行しない登録 (インラインのコマンド、
  プロンプト、http フック)。それぞれ `"<Event> [<matcher>] -> <command>"` の形

一覧化の規則:

- **スクリプト**: `.claude/scripts/` の下の `*.py`、`*.sh`、`*.ps1` はすべて、参照されているかどうかに関わらず
  ノードになります。名前ごとに 1 ノードで、同じ名前の形式が複数あるときは `.py` が、次に `.sh` が優先されます。
  ラベルはファイル名です。ノードはあくまでディスク上の一覧です。コマンドが参照しているのにディスクにない
  スクリプトにはノードを作りません。`runs` エッジは意図的に宙に浮かせたままにし、HTML ビューアは存在しない
  終点を灰色の「(missing)」スタブとして描くので、壊れた参照を見つけられます。
- **スキル**: `.claude/skills/<slug>/SKILL.md` はすべてノードになります。エッジが付くのは導入済みのスキル
  だけです。席が宣言しているのに導入されていないスキルは、席のファイルを直接読む `harness-view assess` が
  報告します (`skill-wire-missing`)。
- **タスク**: `docs/tasks/**` の下の `TASK-*.md` と、タスクボード (`.agent-base/tasks/`、または settings.json の
  `env.TASK_BOARD_DIR`) の下のものはすべてノードです。ファイルのない `TASKS.md` の行は `file` なしのノードに
  なります。`references` エッジが付くのは、タスク本文がモジュールのパスを挙げているときだけです。

## 内容による参照

エッジの大半は、ファイルの中身そのものから読み取ります。エージェント、ルール、コマンド、フック、スキル
(`SKILL.md`)、指示ファイルのすべてを、ほかのハーネス項目への参照についてスキャンし、見つけた参照をエッジに
します。スキャナーの中にフックやルールの名前の表はありません。フックが強制するのは、一覧が「そうあるべき」と
するルールではなく、そのフック自身の文面が名指しするルールです。

名前として数えるのは、意図して名前として書かれたものだけです:

| 形 | 例 | 解決先 |
|---|---|---|
| ハーネスのパス | `.claude/rules/layering.md`、`.claude/skills/docs-sync/SKILL.md`、`.claude/scripts/check-env.sh` | そのルール、スキル、スクリプト、エージェント、コマンド、フック |
| 単語全体としての素のファイル名 | `. "$(dirname "$0")/_lib.sh"` | その名前のフックまたはスクリプト |
| スラッシュ形式 | `/review` | コマンド |
| コードまたは太字のスパン (完全一致) | `` `endpoint-scaffold` ``、`**docs-sync**` | エージェント、スキル、フック、ルール |
| ハイフンでつないだ素のスラッグ | `security-privacy-reviewer` | エージェント、スキル、フック |
| フロントマターの `skills:` | エージェントの `skills: [pdf, docx]` | 挙げられた各スキル |

文章中の辞書的な単語 1 つは、決して参照に数えません。この規則は要です。実在するハーネスでは、5 つの
エージェントが「performance budgets」という文面に「performance」という単語を含んでいますが、その名前のスキルは
どの席にも配線されていません。単語で照合すれば 5 本の存在しない配線を作ってしまいます。パスがハーネスの
パスとして扱われるのは、そのディレクトリが `.claude/` の直後にある、または単語の先頭にあるときだけなので、
`.cursor/rules/x.md` やスキル内部の `scripts/` フォルダは何にも解決されません。素の名前は 1 種類にだけ解決され、
エージェントが先、次にスキル、次にフック (スパンの中ならその次にルール) です。コマンドは `/name` かパスでのみ
到達します。スキルを裏に持つコマンドは、スキルと同じ名前であることが多いからです。参照は存在するノードに
対してだけ解決され、ファイルが自分自身を参照することはありません。

エッジの種類は、両端が何であるかで決まります:

| 起点 | 終点 | エッジ |
|---|---|---|
| hook | rule | `enforces` |
| hook | hook | `sources` |
| any | script | `runs` |
| hook | agent, skill, command | `refers` |
| instruction | agent | `briefs` |
| any | rule | `cites` |
| any | skill | `uses` |
| rule | agent | `refers` |
| command, agent, skill | agent | `delegates` |
| any | command | `invokes` |

## エッジ

| フィールド | 型 | 備考 |
|---|---|---|
| `from`, `to` | string | ノードの id。すべてのエッジの両端は `nodes` に存在します |
| `type` | enum | 下の表を参照 |
| `refs` | int? | 参照の数。モジュールからモジュールへのエッジにのみ付きます |

| エッジの種類 | 意味 | 典型的な向き |
|---|---|---|
| `gates` | 無条件のルールがエージェントを縛る | rule -> agent |
| `triggers` | settings.json、または席自身のフロントマターがフックを登録する | settings -> hook, agent -> hook |
| `enforces` | フックが自分の強制するルールを名指しする | hook -> rule |
| `reviews` | レビュー席がマージリクエストのゲートを担う。スキャフォルダのレビュアー名、`checker`、`editor`、または `reviewer`、`-checker`、`auditor`、`critic`、`verifier` で終わる名前 | agent -> gate:merge-request |
| `escalates` | ゲートが判断を人に渡す | gate:merge-request -> human |
| `invokes` | 人がスラッシュコマンドを実行する、またはファイルがそれを指す | human -> command, any -> command |
| `runs` | ファイルがスクリプトを実行する。コマンドからは、参照している `.claude/scripts/<name>.py` のすべてが、ファイルがなくても数えられる | any -> script |
| `spawns` | ある席が別の席を起動できる。`Agent(a, b)` が名指しする席だけ。`orchestrator` または素の `Agent`/`Task` の許可なら、ほかのすべての席 | agent -> agent |
| `owns` | 開発エージェントがコードモジュールを担当する、またはタスクを担当する (その `owner:` フロントマター) | agent -> module, agent -> task |
| `references` | モジュールがモジュールを import する、またはタスクがモジュールを挙げる | module -> module, task -> module |
| `uses` | ファイルが使うスキルを名指しする | agent, command, rule, skill, instruction -> skill |
| `cites` | ファイルがルールを指す | any -> rule |
| `briefs` | 指示ファイルが席を名指しする | instruction -> agent |
| `imports` | 指示ファイルが別の指示ファイルを `@` で読み込む | instruction -> instruction |
| `routes` | 経路の段の行が、それを担う席を名指しする | instruction -> agent |
| `delegates` | ファイルが席に仕事を渡す (コマンドが起動する、エージェントが引き継ぐ) | command, agent, skill -> agent |
| `sources` | フックが共有の補助ファイルを読み込む | hook -> hook |
| `refers` | それ以外の名前付きの参照 | hook -> any, rule -> agent |

## 評価

`harness-view assess --json` (と `GET /assess`) はこのグラフを採点するもので、グラフとは別の文書です。ルール id
つきの指摘、根拠 (`file:line`)、修正案、ルールを価値の高い順に並べた作業リスト、2 回の評価を比べる `since`
ブロックが入っています。形は `tools/harness-view/SCHEMA.ja.md` の「評価」に、各ルールは
`tools/harness-view/RUBRIC.ja.md` にあります。

## スキャナーが取り込む入力

- `.claude/{agents,rules,commands}/**.md`、`.claude/hooks/*.{sh,ps1}`、`.claude/settings.json`
- 上で挙げた指示ファイル (リポジトリのルートとその下)
- `.claude/disabled/**` と `.claude/disabled.json` (実行時のトグル状態。なければ何も無効化されていない)
- `.claude/state/code-graph.json` (モジュールノード、担当、import エッジ) - 任意
- `docs/tasks/**/TASK-*.md` (すべてのタスクファイルがノードになる) - 任意
- タスクボード: `<board>/{pending,active,completed,canceled}/TASK-*.md` と `<board>/TASKS.md` - 任意
- `.claude/hooks/spawn-allowlist` (起動ガードが許可する組み込みエージェント) - 任意

## 鮮度

`graph-stale` の PostToolUse フックは、ハーネスのファイルが編集されるたびにこのファイル (と HTML) を再生成
します。Edit/Write のフックを通らない変更 - スキャフォルダの再実行、トグルのスクリプト、外部ツール - は、
自分で `python .claude/scripts/harness-graph.py --html` を再実行しなければなりません。

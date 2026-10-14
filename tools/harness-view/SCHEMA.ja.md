# harness-graph.json: スキーマバージョン 1

[English](SCHEMA.md) · **日本語**

本ツール (`harness-view
scan`) とスキルの Python スキャナー (`.claude/scripts/harness-graph.py`) の両方が
`.claude/state/harness-graph.json` に書き出す。
出力はバイト単位で安定している。キーはソート済み、ノードは id 順、エッジは (from, to, type) 順に並び、
インデントは 2 スペース、末尾に改行があり、タイムスタンプは一切含まない。

```json
{
  "version": 1,
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

## ノード

`id` は `<prefix>:<name>` の形をとる。型ごとのプレフィックスは `agent:`、`rule:`、`cmd:`、
`hook:`、`script:`、`mod:`、`task:`、`instr:` で、これに単独ノードの `settings`、
`gate:merge-request`、`human` が加わる。

**すべてのノードは `label` と `disabled` を持つ** (該当しない場合は false)。
ラベルの形式: コマンドは `/<name>`、合成ゲートは `Merge request`、
人間ノードは `Human`、settings は `settings.json`、スクリプトは
`<name>.py`、モジュールはモジュールパス、それ以外は素の名前である。

| type | id の例 | 追加フィールド |
|---|---|---|
| agent | `agent:code-reviewer` | `file`、`meta` (`model`、`effort`、`maxTurns`、`tools`、`description`。それ以外は「エージェントのメタ情報」の節を参照) |
| rule | `rule:testing` | `file`、`meta` (`scoped`、スコープ付きかつ引用符なしの場合の `paths`、`description`) |
| command | `cmd:deploy` | `file` |
| hook | `hook:protect-secrets` | `file` (両方ある場合は .sh 版、なければ .ps1)、`meta` (`registered`、`event`、`matcher`、`blocking`、未登録で他のフックから読み込まれている場合の `library`。`events`、`scope` については「フックのメタ情報」の節を参照) |
| settings | `settings` | `file`、`edit`。`meta.otherHooks` は `.claude/hooks/` のスクリプトを実行しない登録がある場合のみ (settings.json が存在する場合のみ出力) |
| instruction | `instr:agents`、`instr:cursor-rules/testing` | `file`、`edit`、`meta` (`tools`、`source`、`verified`、`note`)、ファイルがルーティング表を含む場合は `tiers` |
| script | `script:code-graph` | `file` (`.claude/scripts/` 配下のすべての `*.py`、`*.sh`、`*.ps1`。ラベルはファイル名) |
| module | `mod:src/app` | `files` (件数) と `owner` (エージェント名または `-`) の両方を持つ `meta` |
| task | `task:TASK-042` | `file` (`docs/tasks/**` 配下と、「タスクボード」の節で説明するボード配下のすべての `TASK-*.md`)、`meta` (frontmatter にある場合の `title`、`status`、`fr`、`owner`、`deps`、`priority`、`phase`) |
| gate | `gate:merge-request` | `synthetic: true` |
| human | `human` | `synthetic: true` |

`.claude/disabled/{rules,commands,hooks}/` 配下で見つかった項目もノードとして現れる。
その場合は `disabled: true` となり、`file` は隔離先のパスを指す。

### エージェントのメタ情報

上記の 5 つに加えて、Claude Code のサブエージェント frontmatter
(code.claude.com/docs/en/sub-agents の "Supported frontmatter fields") のすべてのフィールドを、
ファイルが設定している場合に保持する。ビューアーがフィールドを知らなくても表示できるよう、平坦化して格納する。

| key | 形式 |
|---|---|
| `permissionMode`、`memory`、`isolation`、`color` | 文字列 |
| `background`、`omitClaudeMd` | bool (`true`/`false`)、それ以外は生の文字列 |
| `disallowedTools`、`skills` | リスト |
| `mcpServers` | サーバー名のリスト (文字列の項目、またはインライン定義のキー) |
| `hooks` | `"<Event> [<matcher>] -> <hook name or command>"` のリスト。登録 1 件につき 1 項目 |
| `initialPrompt` | 文字列。上限 300 文字 |
| `cacheTtl` | `experimental.cacheTtl` |
| `name` | `name:` がファイル名と異なる場合のみ。Claude Code は `name:` でディスパッチするため |
| `spawns` | `tools` 内の `Agent(a, b)` (または `Task(...)`) に書かれた名前。組み込みエージェントも含む |
| `spawnAllowlist` | `.claude/hooks/spawn-allowlist` の各行。frontmatter のフックがこのファイルを読むシートに付く (該当がなければ `orchestrator` に付く) |

`tools` は括弧の外にあるカンマで分割するため、`Agent(a, b)` は 1 項目のままになる。
冒頭の `---` の前にある UTF-8 BOM は無視する。

### フックのメタ情報

フックは settings.json か、シート自身の frontmatter の `hooks:` によって登録される。
`event` と `matcher` は最初の登録 (settings.json を優先) の値である。
登録が複数ある場合、`events` は異なる `"<Event> <matcher>"` をすべて列挙する。
`blocking` は、いずれかの登録が `PreToolUse` または
`PermissionRequest` にある場合に true となる。これらは exit 2 でツール呼び出しを止めるイベントである。`scope` は、
settings.json が登録しておらずシートが登録している場合に、そのシートを列挙する。このようなフックは
そのシートの実行中にのみ発火する。

### タスクボード

orchestrator-kit のボード: settings.json の `env` にある `TASK_BOARD_DIR` がリポジトリ内の
相対パスであればそれを、そうでなければ `.agent-base/tasks` を使う (ディレクトリが存在する場合)。
タスクファイルは `pending/`、`active/`、`completed/`、`canceled/` のいずれかに置かれ、
`TASKS.md` がそれらを索引する (`| ID | task | agent | state | deps | mission |`)。

ボードのタスクでは、`status` はフォルダー、`owner` は `agent:`、
`deps` は `depends_on:` にフォールバックする。値が `-` のものは捨てる。`mission`、`attempts`、
`board` (ボードのパス) が追加される。`drift` は、フォルダー、`status:`、`TASKS.md` の行の間にある
食い違いをすべて列挙する。これは `task.sh check` が失敗する条件と同じである。
ファイルのない `TASKS.md` の行は、`file` を持たないタスクノードとなり、その旨を示す
`drift` 項目が付く。

### 指示ファイル

`.claude/` の外にある唯一のノードである。各 AI コーディングツールが読む契約であるため、
その集合はリポジトリのルートを走査して得るのではなく、出典付きの閉じた許可リストとして定義されている。
`tools/harness-view/src/instruction.rs` の `instruction::FILES` と
`harness-graph.py` の `INSTRUCTION_FILES` がそれであり、両者は一致していなければならない (`scripts/check_graph_parity.py`)。

| key | パス | 読み込むツール | 根拠 |
|---|---|---|---|
| `agents` | `AGENTS.md` | Claude Code、Codex、Cursor、Antigravity | 本リポジトリの `docs/tools/*.md`。antigravity.google/docs/cli/best-practices |
| `claude` | `CLAUDE.md` | Claude Code | `docs/tools/claude-code.md` |
| `gemini` | `GEMINI.md` | Antigravity | antigravity.google/docs/cli/best-practices |
| `cursor-rules` | `.cursor/rules/*.mdc` | Cursor | `harness-bootstrap/scripts/port.py`、`docs/tools/cursor.md` |
| `kiro-steering` | `.kiro/steering/*.md` | Kiro | kiro.dev/docs/steering |
| `antigravity-rules` | `.agents/rules/*.md` | Antigravity | antigravity.google/docs/rules-workflows |
| `antigravity-rules-legacy` | `.agent/rules/*.md` | Antigravity | 同じページ。後方互換として文書化されたパス |

各ノードの `meta.source` はその根拠を保持し、`meta.verified` は出典があるかどうかを示す。
これにより、読み手は文書化された事実と推測とを区別できる。Kiro が `AGENTS.md` も読むかどうかは
**未検証** である。それを述べる公式のページがないため、この主張はしておらず、代わりに
`agents` 項目の `note` に記録している。リポジトリ外のグローバルな指示ファイル
(`~/.gemini/GEMINI.md`、`~/.codex/AGENTS.md`) は走査できないため、ノードにはならない。

`tiers` は「変更にどれだけのプロセスをかけるか」の表 (v1.18.0) であり、
それを記載している指示ファイルから解析される。ファイル内の順序どおりに並んだ
`{"tier", "change", "who", "adds"}` の配列である。表は
`Tier` / `Who runs it` の見出し行で見つける。翻訳されている場合 (orchestrator-kit の
`| 区分 | 変更の内容 | 誰が行うか |` がそうである) は、`Direct`、
`Standard`、`Guarded` という名前の行が 2 つ以上あることで見つける。`who` 列が
名指ししたエージェントには `meta.tier` と `routes` エッジも付く。Direct と Standard の行は
「担当エージェント」と書かれているだけで誰も名指ししないため、どこにもルーティングされない。

### `edit`

`{"key": <table key>, "name": <bare leaf name or "">}`。ビューアーが書き込んでよいノード、
すなわち指示ファイルと `settings` にのみ存在する。これは
`POST /instruction` が受け付ける形であり、固定の表のキーと素の名前の組み合わせである。
パスを受け取るエンドポイントであれば封じ込めが必要になるが、パスを受け取らないエンドポイントには
封じ込めるべきトラバーサルがそもそも存在しない。

## エッジ

`{"from": id, "to": id, "type": <enum>, "refs"?: int}`。`refs` はモジュール間の
`references` エッジにのみ現れ、code-graph.json から得たインポート数を保持する。
type の列挙は閉じている。

| type | 意味 |
|---|---|
| `triggers` | settings.json の登録がフックを発火させる。エージェントからのエッジは、そのシート自身の frontmatter が登録していることを示す |
| `enforces` | フック自身のテキストがルールを名指ししている |
| `gates` | 無条件の (パスでスコープされていない) ルールがエージェントに適用される |
| `spawns` | シートがそのエージェントを起動できる。`Agent(a, b)` が名指しするシートそのもの。`orchestrator` または素の `Agent`/`Task` 権限の場合は他のすべてのシート |
| `reviews` | レビュー担当のシートがマージリクエストをゲートする。対象はスキャフォルダーのレビュアー名、末尾が `reviewer`、`-checker`、`auditor`、`critic`、`verifier` の名前、および `checker` と `editor` |
| `escalates` | マージリクエストのゲートは人間で終わる |
| `invokes` | コマンドは人間の入口である |
| `runs` | ファイルがスクリプトを参照している。コマンドからのエッジでは、存在しなくてもすべての `.claude/scripts/<name>.py` を数えるため、宙に浮いたエッジそのものが検出結果となる |
| `owns` | エージェントがモジュールを所有する (code-graph の owner)、またはタスクを所有する (その `owner:` frontmatter)。`a+b` と書かれた共同所有のタスクは、名指しされたシートごとに 1 本のエッジを出す。エージェントノードを持たないシートは何も出さない。 |
| `references` | モジュールがモジュールをインポートする。タスクがモジュールに言及する |
| `briefs` | 指示ファイルがエージェントを名指ししている |
| `cites` | 指示ファイルが `.claude/rules/<name>.md` のパスでルールを指している |
| `imports` | 指示ファイルが別のファイルを `@` インポートしている (`CLAUDE.md` -> `AGENTS.md`) |
| `routes` | ルーティング区分の行が、その区分を実行するエージェントを名指ししている |
| `uses` | ファイルがスキルを名指ししている |
| `delegates` | コマンド、エージェント、スキルがエージェントに作業を引き渡す |
| `sources` | フックが共有ヘルパーのフック (`_lib.sh`) を読み込む |
| `refers` | その他の名前による参照 (hook -> agent/skill/command、rule -> agent) |

`invokes`、`cites`、`runs` は、コマンド、ルール、スクリプトを名指しするあらゆるファイルからも出力される。
内容から導かれるものはすべて `docs/HARNESS-GRAPH-SCHEMA.md` の規則
("Content references") に従い、`src/refs.rs` と `harness-graph.py` にあるその対の
`references()` で実装されている。パス、`/command`、完全一致するコードスパンや太字スパン、
ハイフンでつながれたスラッグは参照として数えるが、散文中の単語 1 語は決して数えない。

### パリティ

`scripts/check_graph_parity.py` は両方のスキャナーを `tests/fixture`、
`tests/kit-fixture` (サブエージェントの全フィールド、シートが登録するフック、タスクボード)、
生成したエッジケースのツリー、新規の 2 つのスキャフォールドに対して実行し、
1 バイトでも差があれば失敗する。このページにあるフィールドはすべて両方が出力する。

## disabled.json (トグルの記録)

```json
{
  "version": 1,
  "disabled": [
    {"kind": "rule", "name": "performance", "from": ".claude/rules/performance.md",
     "reason": "noisy during prototype phase"},
    {"kind": "hook", "name": "specs-reminder", "from": ".claude/hooks/specs-reminder.sh",
     "reason": "...",
     "registration": [{"event": "PostToolUse", "matcher": "Edit|Write",
                       "group_index": 0, "hook_index": 0,
                       "hook": {"command": "bash .claude/hooks/specs-reminder.sh", "type": "command"}}]}
  ]
}
```

`registration[].group_index` はイベント配列内でのマッチャーグループの位置を、
`hook_index` はグループ内でのフックオブジェクトの位置を記録する。これにより、
再有効化したときに `settings.json` をバイト単位で正確に復元できる (harness-toggle.py が書くのと同じ形であり、
2 つのツールは 1 つの記録を共有する)。項目は `kind/name` 順に並ぶ。
このファイルはコミットされるため、日付を含めてはならない。なお、
ファイル全体が正規形で書き出されるため、`hook` オブジェクトはキーをソートした状態で保存される。
一方、`settings.json` 自体は常にキーの順序を保ったまま書き出される。

## 評価 (`assess --json`、`GET /assess`)

`harness-view` のみが書き出す。タイムスタンプは含まない。すべてのテキストフィールドには `_ja` の対がある。

| key | 形 |
|---|---|
| `version` | 1 |
| `root` | リポジトリ。スラッシュ区切り |
| `purposes` | `{"list": ["code", "research", ...], "source": "vars.json" \| "roster" \| "default" \| "given", "rules_not_applied": [rubric ids]}` |
| `counts` | `{"high", "medium", "low", "info"}` |
| `scores` | `{"overall", "categories": {<name>: {"score", "findings", "penalty", "label_ja", "derivation": [{"rubric", "count", "weight", "points"}]}}, "method", "not_measured"}` |
| `worklist` | 検出結果のあるルールを価値の高い順に: `{"rubric", "check", "severity", "category", "title", "full", "fix", "names", "count", "effort", "points", "priority", "one_click", "overall_after", "gain", "keys"}` |
| `statistics` | ノード、エッジ、モデル、ステータス、ルール、フックの件数 |
| `findings` | 深刻な順に: `{"rubric", "check", "category", "severity", "weight", "effort", "title", "why", "fix", "node", "file", "line", "evidence", "key", "action"?}` |
| `since` | 前回の評価がある場合のみ: `{"fixed", "new", "unchanged", "overall": {"from", "to"}, "categories", "graph"?}` |

- `evidence` は `file:line` である。frontmatter のキーが欠けている場合、行はそのキーが
  入るべき閉じの `---` になる。
- `priority` は `points * 6 / effort` で、`points` は重み × 件数である。`6` は
  effort が 1、2、3 のいずれでも整数になるようにするための値である。`overall_after` は、
  そのルールの検出結果がなくなった場合の総合スコアである。
- `key` は 2 回の実行をまたいで検出結果を識別する (`check|node|name|extra`)。`since` は
  これで照合する。`since.graph` (サーバーのみ) は `nodes_added`、
  `nodes_removed`、`edges_added`、`edges_removed` を列挙する。
- `action` は `{"endpoint": "agent", "label", "label_ja", "body"}` で、そのまま
  `POST /agent` に送れるリクエストである。エージェントエディターが `body` のすべての値を
  受け付ける場合にのみ存在する。

重み、effort、テキストは `src/rubric.rs` から生成される [RUBRIC.ja.md](RUBRIC.ja.md) にある。
`GET /rubric` は同じ表を JSON で返す。

## バージョン管理

`version` は形に破壊的な変更があった場合にのみ増える。利用側は、推測で読み進めるのではなく、
より大きなメジャーバージョンを拒否しなければならない。

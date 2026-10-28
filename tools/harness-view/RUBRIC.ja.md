# harness-view 採点基準（ルーブリック）

<!-- 生成ファイル: `harness-view rubric --lang ja > RUBRIC.ja.md`。手で編集しない。src/rubric.rs が正本で、tests/rubric_test.rs が一致を検査する。 -->

[English](RUBRIC.md) · **日本語**

`harness-view assess` が適用するすべてのルールです。指摘はルール ID・根拠（ファイル:行）・理由・具体的な修正方法を持ち、点数はこの表だけで再計算できます。

## 計算方法

各カテゴリーは 100 点から始まり、そのカテゴリーの指摘ごとに重み（high 12、medium 5、low 2、     info 0）を引き、0 点で止まります。リポジトリの目的に当てはまらないルールは検査しません。検査対象が     ないカテゴリー（タスクのないタスクボード、タスク・コマンド・スキルのないトレーサビリティ）は 100 点     ではなく n/a とします。総合点は 6 カテゴリーのうち n/a を除いたものの平均の整数部分です。安全性に      high の指摘が残っている間は、総合点は安全性の点数を上限とします。ハーネスの信頼性はガードレール以上に     はならないからです。重みは取り決めであり、測定値ではありません。

| 重大度 | 重み |
|---|---|
| high | 12 |
| medium | 5 |
| low | 2 |
| info | 0 |

**手間**: 1 = ワンクリックか 1 行、2 = 1 ファイルの小さな編集、3 = 判断か新しいファイルが必要。作業リストは「重み × 件数 ÷ 手間」の大きい順に並びます。

**対象**: `all` はすべてのリポジトリ、`code` はコードを目的に含むリポジトリ、`non-code` は調査・戦略・文書を目的に含むリポジトリ。目的は `.claude/state/vars.json` の `purpose_*` フラグから、なければエージェントの構成から判定します。

## 安全性

### SAF-01 `reviewer-readonly`

- 重大度: high（重み 12） · 手間: 1 · 対象: all
- 満点の条件: すべてのレビュー担当（reviewer、checker、auditor など）が Edit・Write・NotebookEdit を持たない。
- 指摘: レビュー担当 `{name}` が `{extra}` を持っている
- 理由: 書き込めるレビュー担当はゲートではありません。指摘すべきものを自分で直せてしまい、レビューが自己承認になります。
- 修正: `.claude/agents/{name}.md` の `tools:` から `{extra}` を削除し、`disallowedTools:` に加える。

### SAF-02 `reviewer-disallowed`

- 重大度: low（重み 2） · 手間: 1 · 対象: all
- 満点の条件: すべてのレビュー担当が `disallowedTools:` に Edit と Write を書いている。後で `tools:` を広げても付与されない。
- 指摘: レビュー担当 `{name}` の `disallowedTools` に Edit と Write がない
- 理由: `tools:` は今使えるものを示すだけです。`disallowedTools:` があれば、誰かが一覧を編集した後も読み取り専用のままです。
- 修正: `.claude/agents/{name}.md` の frontmatter に `disallowedTools: Edit, Write, NotebookEdit` を加える。

### SAF-03 `reviewer-memory`

- 重大度: medium（重み 5） · 手間: 1 · 対象: all
- 満点の条件: どのレビュー担当も `memory:` を設定していない。
- 指摘: レビュー担当 `{name}` が `memory:` を設定している
- 理由: memory はメモリ用ディレクトリへの Write と Edit を与えるため、読み取り専用のはずのレビュー担当が書き込めるようになります。
- 修正: `.claude/agents/{name}.md` から `memory:` の行を削除する。

### SAF-04 `spawn-boundary`

- 重大度: high（重み 12） · 手間: 1 · 対象: all
- 満点の条件: 素の `Agent` を持つのはオーケストレーターだけ。ほかに起動するエージェントは `Agent(a, b)` で起動先を限定している。
- 指摘: エージェント `{name}` が任意のサブエージェントを起動できる
- 理由: 素の Agent を持つエージェントは自由に展開でき、起動許可リストが実行範囲を制限しなくなります。
- 修正: `.claude/agents/{name}.md` の `tools:` から `Agent` を削除するか、`Agent(<担当>, <担当>)` の形で限定する。

### SAF-05 `hook-missing-file`

- 重大度: high（重み 12） · 手間: 2 · 対象: all
- 満点の条件: settings.json やエージェントの frontmatter に登録したフックが、すべて `.claude/hooks/` に存在する。
- 指摘: フック `{name}` は登録されているが、ファイルが存在しない
- 理由: 存在しないスクリプトを実行する登録なので、ガードレールは一度も動かず、誰も気づきません。
- 修正: `.claude/hooks/{name}.sh` を復元する（同梱のフックは `/harness-update` で再導入できる）か、根拠の行にある登録を削除する。

### SAF-06 `hook-unregistered`

- 重大度: medium（重み 5） · 手間: 2 · 対象: all
- 満点の条件: すべてのフックファイルが settings.json かエージェントの frontmatter に登録されているか、他のフックが読み込むライブラリである。
- 指摘: フック `{name}` は存在するが、登録されていない
- 理由: どこからも呼ばれないフックは何もしません。統制に見えて、何も強制していません。
- 修正: `.claude/settings.json` に登録する（例: `"PreToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "bash .claude/hooks/{name}.sh"}]}]`）か、ビューアーで無効化する。

### SAF-07 `deny-list`

- 重大度: high（重み 12） · 手間: 2 · 対象: all
- 満点の条件: settings.json に空でない `permissions.deny` がある。
- 指摘: settings.json に permissions.deny がない
- 理由: deny リストは 4 層のガードレールの 1 層目です。これがないと、破壊的なコマンドはフックに頼るか、何にも止められません。
- 修正: `.claude/settings.json` に `"permissions": {"deny": ["Bash(git push --force *)", "Bash(rm -rf *)", "Read(./**/.env)"]}` を加える。

### SAF-08 `deny-coverage`

- 重大度: low（重み 2） · 手間: 1 · 対象: all
- 満点の条件: deny リストが force push、再帰削除、秘密情報の読み取りを含む。
- 指摘: deny リストに {name} がない
- 理由: deny は前方一致で、足止め程度のものです。それでも、ないよりはましです。
- 修正: `.claude/settings.json` の `permissions.deny` に `{extra}` を加える。

### SAF-09 `no-blocking-hook`

- 重大度: high（重み 12） · 手間: 2 · 対象: all
- 満点の条件: PreToolUse か PermissionRequest に登録された有効なフックが 1 つ以上ある。
- 指摘: ツール呼び出しを止めるフック（PreToolUse）が有効になっていない
- 理由: ツール呼び出しを実際に止めるのはフックです。1 つもなければ、ガードレールは助言にすぎません。
- 修正: `protect-secrets` などの PreToolUse フックを `.claude/settings.json` に登録する。同梱のものは `/harness-update` で再導入できる。

### SAF-10 `no-guardrail-rule`

- 重大度: medium（重み 5） · 手間: 2 · 対象: all
- 満点の条件: `.claude/rules/agent-guardrails.md` が存在する。
- 指摘: agent-guardrails.md がない
- 理由: フックが強制する境界を説明する、常に読み込まれるルールです。これがないと、エージェントは強制だけを受け、理由を知りません。
- 修正: `.claude/rules/agent-guardrails.md` を復元する（`/harness-update` で再導入できる）。

### SAF-11 `no-review-gate`

- 重大度: high（重み 12） · 手間: 3 · 対象: code
- 満点の条件: コードのリポジトリに、レビュー担当（code-reviewer、reviewer など）か `/review*` コマンドがある。
- 指摘: レビューコマンドもレビュー担当もない
- 理由: レビューゲートは 4 層目のガードレールで、差分全体を読む唯一の層です。
- 修正: 読み取り専用の `.claude/agents/code-reviewer.md`（`tools: Read, Grep, Glob`）と、それを起動する `.claude/commands/review-changes.md` を加える。

### SAF-12 `no-review-command`

- 重大度: low（重み 2） · 手間: 2 · 対象: code
- 満点の条件: レビュー担当のいるコードのリポジトリに、そこへ作業を回す `/review*` コマンドもある。
- 指摘: レビュー担当はいるが、起動するコマンドがない
- 理由: 誰も作業を回さないレビュー担当は、手で起動することを覚えている人がいる間しか機能しません。
- 修正: 現在の差分にレビュー担当を実行する `.claude/commands/review-changes.md` を加える。

### SAF-13 `noncode-checker`

- 重大度: high（重み 12） · 手間: 3 · 対象: non-code
- 満点の条件: 調査・戦略・文書のリポジトリに、読み取り専用の確認担当（`checker`、または Edit も Write も持たないレビュー担当）がいる。
- 指摘: 成果物を確認する読み取り専用の担当がいない
- 理由: 読むだけの担当がいなければ、すべての主張と数字を書いた本人が承認することになります。
- 修正: `tools: Read, Grep, Glob, WebFetch, WebSearch` と `disallowedTools: Edit, Write, NotebookEdit` を持つ `.claude/agents/checker.md` を加える（スキルは非コード用に同梱している）。

### SAF-14 `harness-unprotected`

- 重大度: medium（重み 5） · 手間: 2 · 対象: all
- 満点の条件: 有効なフック（`protect-harness` など）か permissions の項目が `.claude/settings*.json` と `.claude/hooks/` を守っている。
- 指摘: ガードレールを収めたフックと設定を守るものがない
- 理由: エージェントが書き換えられるガードは、`echo >> .claude/hooks/...` 一つで `exit 0` になります。ほかのすべての層は、それを収めたファイルと同じ強さしかありません。
- 修正: `protect-harness` を導入し（`/harness-update` で追加される）、`.claude/settings.json` の PreToolUse に matcher `Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell` で登録する。

## コスト管理

### COST-01 `agent-tools`

- 重大度: high（重み 12） · 手間: 1 · 対象: all
- 満点の条件: すべてのエージェントが明示的な `tools:` を持つ。
- 指摘: エージェント `{name}` に明示的な tools がない
- 理由: tools を省略すると、すべての MCP サーバーを含む全ツールを継承し、毎回スキーマ全体のコストがかかり、範囲の制限もありません。
- 修正: `.claude/agents/{name}.md` に `tools: Read, Grep, Glob` を加え、必要な分だけ広げる。

### COST-02 `agent-model`

- 重大度: medium（重み 5） · 手間: 1 · 対象: all
- 満点の条件: すべてのエージェントが `inherit` 以外の `model:` を設定している。
- 指摘: エージェント `{name}` がモデルを指定していない
- 理由: モデル未指定は呼び出し元を継承するため、機械的な作業が最も高いモデルで課金されます。
- 修正: `.claude/agents/{name}.md` に `model: sonnet` を加える（機械的な作業は `haiku`、判断が要る作業は `opus`）。

### COST-03 `agent-effort`

- 重大度: low（重み 2） · 手間: 1 · 対象: all
- 満点の条件: すべてのエージェントが `effort:` を設定している。
- 指摘: エージェント `{name}` が effort を指定していない
- 理由: effort はコスト判断のもう半分です。未指定だと、必要のない作業にも呼び出し元の水準が適用されます。
- 修正: `.claude/agents/{name}.md` に `effort: medium` を加える。

### COST-04 `agent-maxturns`

- 重大度: low（重み 2） · 手間: 1 · 対象: all
- 満点の条件: すべてのエージェントが `maxTurns:` を設定している。
- 指摘: エージェント `{name}` が maxTurns を指定していない
- 理由: 上限がなければ、行き詰まった担当はセッションが終わるまで課金し続けます。
- 修正: `.claude/agents/{name}.md` に `maxTurns: 30` を加える（スキャフォルダーは担当ごとに 10〜100 を使う）。

### COST-05 `rule-scoping`

- 重大度: medium（重み 5） · 手間: 2 · 対象: all
- 満点の条件: 設計上常に読み込む 6 つを除き、すべてのルールが `paths:` を持つ。
- 指摘: ルール `{name}` が毎セッション読み込まれる
- 理由: paths のないルールは、作業が関係するかどうかにかかわらず、すべてのセッションのすべてのエージェントに課されるコンテキスト税です。
- 修正: `.claude/rules/{name}.md` の先頭に `---` / `paths:` / `  - "<対象のグロブ>"` / `---` を加える。

### COST-06 `instruction-length`

- 重大度: low（重み 2） · 手間: 3 · 対象: all
- 満点の条件: CLAUDE.md と AGENTS.md の合計が 200 行未満。
- 指摘: CLAUDE.md と AGENTS.md の合計が {extra} 行ある
- 理由: どちらも毎セッション読み込まれ、長くなるほど守られにくくなります。
- 修正: 2 つのファイルの合計が 200 行未満になるまで、詳細を `.claude/rules/` の paths 付きルールへ移す。

## トレーサビリティ

### TRC-01 `task-owner-missing`

- 重大度: medium（重み 5） · 手間: 2 · 対象: all
- 満点の条件: すべてのタスクの担当が実在するエージェントである。
- 指摘: タスク `{name}` の担当 `{extra}` が名簿にいない
- 理由: 存在しない担当に割り当てた作業は委譲できず、気づかれないままボードに残ります。
- 修正: 根拠の行の担当を `.claude/agents/` にいるエージェントに変えるか、`.claude/agents/{extra}.md` を作る。

### TRC-02 `dangling-script`

- 重大度: medium（重み 5） · 手間: 2 · 対象: all
- 満点の条件: コマンドが実行するスクリプトが、すべて `.claude/scripts/` に存在する。
- 指摘: `{name}` が実行する `{extra}` がインストールされていない
- 理由: 存在しないスクリプトを指すコマンドは、最初に使ったときに失敗します。
- 修正: スクリプトを導入する（同梱のものは `/harness-update` で再導入できる）か、根拠の行の参照を削除する。

### TRC-03 `skill-not-wired`

- 重大度: low（重み 2） · 手間: 2 · 対象: all
- 満点の条件: 導入したスキルが、すべていずれかのエージェント・コマンド・ルールから参照されている。
- 指摘: スキル `{name}` は導入済みだが、ハーネスのどこからも参照されていない
- 理由: 参照されないスキルは、ハーネスの動きを何も変えないのに、レビューと更新の手間だけがかかります。
- 修正: `/skill-wire {name}` で使う担当に宣言するか、`.claude/skills/{name}/` を削除する。

### TRC-04 `skill-wire-missing`

- 重大度: medium（重み 5） · 手間: 2 · 対象: all
- 満点の条件: エージェントが宣言するスキルが、すべて `.claude/skills/` に導入されている。
- 指摘: `{name}` が宣言するスキル `{extra}` が導入されていない
- 理由: 担当の指示が存在しない能力を約束しているため、モデルはない手順に従おうとします。
- 修正: スキルを `.claude/skills/{extra}/` に導入するか、根拠の行から削除する。

## タスクボード

### BRD-01 `blocked-no-unblocker`

- 重大度: medium（重み 5） · 手間: 1 · 対象: all
- 満点の条件: Blocked のタスクが、すべて解除条件を記録している。
- 指摘: タスク `{name}` が Blocked なのに依存が記録されていない
- 理由: 解除条件が書かれていないため、原因が解消しても再開されません。
- 修正: 根拠の行の frontmatter に `deps: TASK-NNN`（解除条件）を加える。

### BRD-02 `task-no-status`

- 重大度: low（重み 2） · 手間: 1 · 対象: all
- 満点の条件: すべてのタスクが状態を持つ。
- 指摘: タスク `{name}` に状態がない
- 理由: 状態のないタスクは、状態で絞り込むボードの確認から漏れます。
- 修正: タスクファイルの frontmatter に `status: Pending`（またはボード上の実際の状態）を加える。

### BRD-03 `board-drift`

- 重大度: medium（重み 5） · 手間: 1 · 対象: all
- 満点の条件: orchestrator-kit のボードで、すべてのタスクのフォルダ・`status:`・`TASKS.md` の行が一致している。
- 指摘: タスク `{name}`: {extra}
- 理由: フォルダ・状態・集約ファイルが食い違い、どれを信じても別の場所が違うことを言っています。
- 修正: `bash .claude/scripts/task.sh check` を実行し、`bash .claude/scripts/task.sh move {name} <状態>` で正しい状態に移す。TASKS.md は手で編集しない。

## 文書品質

### DOC-01 `table-blank-line`

- 重大度: low（重み 2） · 手間: 1 · 対象: all
- 満点の条件: タスクとマスタープランの Markdown の表に、行の間の空行がない。
- 指摘: {name}: {extra} 行目で表の中に空行がある
- 理由: GitHub 形式の Markdown では空行で表が終わるため、それ以降の行はここでも GitHub でもただの文章になります。
- 修正: 根拠の行の空行を削除する。

## 契約（指示ファイル）

### CON-01 `instruction-contract`

- 重大度: medium（重み 5） · 手間: 3 · 対象: all
- 満点の条件: リポジトリのルートに `AGENTS.md` がある。
- 指摘: リポジトリのルートに AGENTS.md がない
- 理由: AGENTS.md は Claude Code 以外のすべてのツールが読む共通の契約です。これがないと、.claude/ のルールは 1 つのクライアントにしか届きません。
- 修正: ルートに `AGENTS.md` を作り（`/harness-update` で生成できる）、`CLAUDE.md` の先頭を `@AGENTS.md` にする。

### CON-02 `instruction-tiers`

- 重大度: info（重み 0） · 手間: 2 · 対象: all
- 満点の条件: 指示ファイルに Direct / Standard / Guarded の区分表がある。
- 指摘: AGENTS.md に作業の区分表がない
- 理由: 区分表がなければ、どの変更が簡単な確認で済み、どれにテストと独立したレビューが必要かが決まらず、すべてが最も重い手順か、何の手順もなしになります。
- 修正: スキルの `assets/root/AGENTS.md` と同じ区分表を AGENTS.md に加える。

### CON-03 `instruction-nested-stub`

- 重大度: low（重み 2） · 手間: 2 · 対象: all
- 満点の条件: フォルダ単位の指示ファイルが、すべてそのサブツリー固有の内容を書いている。
- 指摘: {name} はサブツリーを管轄するのに、ほとんど何も書いていない
- 理由: フォルダ単位の契約は配下のすべての変更に適用されます。中身のないものは、管理されているように見える分、ないより悪いです。
- 修正: このサブツリー固有の決まりを {name} に書くか、ファイルを削除する。

## 測定していないもの

- ルールがこのリポジトリにとって有用なことを言っているか
- エージェントの担当範囲が実際の作業の分け方と合っているか
- 存在するフックが、主張どおりのものを実際に止めるか
- コード・テスト・文章の品質や、レビューの深さ

# Claude Code でのハーネス

[English](claude-code.md) · **日本語**

Claude Code はハーネスが**生成される**場所であり、最も完全に強制が効く場所でもあります。読み込むのは
`.claude/` (エージェント、ルール、フック、`settings.json`) と `AGENTS.md`、`CLAUDE.md` です。強制の仕組みは、
フックに裏打ちされた `settings.json` の権限拒否リストです。どのハーネスも登録する基本セットに加えて、フラグの
背後で出荷されるガード (`hooks_strict`、`db`、`long`、および調査とドキュメントの目的) があります。Cursor と
Codex は同じハーネスを描画します。ここがその移植元となる参照実装です。

## セットアップ

ポーターの手順はありません。スキャフォールドするとハーネスはここに直接置かれます。Claude Code から
`/harness-bootstrap` を実行します (または既存の `.claude/` をコピーしてきます)。Python 3 が必要です。インストールは
これで全部です。以下のものはすべて `scripts/scaffold.py` が書き出すもので、手で書くものではありません。

## 置かれるもの

| パス | 役割 |
|---|---|
| `.claude/agents/` | 18 席のうち 3〜17 席。リポジトリの目的とフラグで選ばれ、各席が `model`、`effort`、`tools`、`maxTurns` を明示する |
| `.claude/rules/*.md` | 最大 17 のルール (全フラグ有効時、常時読み込み 7、パス単位 10)。遅延読み込み用の `paths:` フロントマターは任意 |
| `.claude/hooks/` | 最大 26 のフックスクリプト (macOS/Linux は `.sh`、Windows は `.ps1`) と README。どれを導入・登録するかはフラグが決める |
| `.claude/scripts/` | ハーネスが自分自身に対して実行する標準ライブラリだけの Python: `task.py`、`verify-plan.py`、`board-check.py`、`harness-check.py`、`harness-graph.py`、`code-graph.py`、`docs-graph.py`、`skill-check.py`、`harness-toggle.py`、`env-read.py` |
| `.claude/settings.json` | 権限の許可/拒否リスト、`env` 内の起動上限、フックの登録 |
| モジュールごとの `CLAUDE.md` | 分析で見つかったモジュールごとに一つ、40 行以内。そこのファイルが読まれたときだけ読み込まれる |
| `AGENTS.md` + `CLAUDE.md` | ベンダー中立の契約。`CLAUDE.md` は `@AGENTS.md` の薄いインポートと Claude 固有の部分だけ |

ルールは遅延読み込みされます。`paths:` のないルールは毎セッション読み込まれ、`paths: [glob]` を持つルールは
一致するファイルに触れたときだけ付きます。17 のうち無条件に読み込まれるのは 7 つだけです: `00-overview`、
`agent-guardrails`、`model-policy`、`task-tracking`、`conventional-commits`、`ai-governance`、`output-style`。
最後の 2 つは `ai` と `terse` のフラグがあるときだけ出荷されるので、既定のインストールではさらに少なくなります。
残りの 10 は既定のコンテキストに入りません。席のティアはパス単位の `model-tiers` にあり、エージェントファイルか
`settings.json` に触れたときだけ読み込まれます。

## 強制するもの、助言にとどまるもの

| 制御 | イベント | 効果 |
|---|---|---|
| `protect-secrets` | PreToolUse (Bash + ファイル読み取り) | `.env`、鍵、`~/.ssh`、`.npmrc` の読み取りをブロック |
| `protect-adr` | PreToolUse (編集) | Accepted の ADR への編集をブロック |
| `guard-main-commit` | PreToolUse (Bash) | 既定ブランチへの直接コミットをブロック |
| `check-commit-msg` | PreToolUse (Bash) | Conventional でない、または AI の帰属表示を含むコミットメッセージをブロック |
| `guard-destructive` | PreToolUse (Bash/PowerShell) | リポジトリのルートやホームへの `rm -rf`、保護ブランチへの force push、`git reset --hard`、ローカル以外のホストへの DROP をブロック |
| `guard-agent-spawn` | PreToolUse (Agent/Task) | ロースター外のエージェント、モデル未固定、タスクやティアの印がない書き込み可能な委任、台帳上すでに合格した検証の再実行をブロック |
| `guard-board` | PreToolUse (編集) | ボード上のタスク行の手編集をブロック。書き手は `task.py` |
| `guard-task-scope` | PreToolUse (編集) | 依頼の記録がない、または実質的な基準が 2 つ未満のタスクファイルの作成をブロック |
| `guard-agent-scope` | PreToolUse (編集) | 助言のみ: 唯一の進行中タスクのモジュール外への編集に注意を促す。ペイロードが呼び出し元のサブエージェントを示さないので、ブロックはできない |
| `specs-reminder` | PostToolUse | フラグ: 事後に知らせるだけで、ブロックしない |
| `graph-stale` | PostToolUse | `.claude/` の編集でハーネスグラフを更新し、ソース編集で新しいモジュール間インポートを指摘する。ブロックはしない |
| `agent-history` | SubagentStop | サブエージェントの履歴を記録する。観察用で、ブロックではない |
| `hooks_strict` のガード | 各種 | オプトイン: 大きなファイル、外向き通信、固定されていない依存、プロンプトや出力内の秘密情報、設定変更、根拠のない「完了」。`.claude/hooks/README.md` を参照 |
| `settings.json` の `permissions.deny` | すべてのツール呼び出し | force push、`rm -rf`、本番デプロイ、秘密情報の読み取り、DB リセットをブロック (前方一致) |
| `.claude/rules/*.md` | コンテキストに読み込み | 助言のみ。圧縮の後、モデルがルールから外れることがある |

ブロックするフックは終了コード 2 で拒否します。拒否リストは前方一致なので、フラグの並べ替え (`rm -r -f`) で
すり抜けられます。つまり拒否リストは減速帯であり、本当のゲートはフックです。

## 正直な限界

- 拒否リストはコマンドの前方一致しか見ません。壁ではなく減速帯として扱ってください。強制の層はフックです。
- ルールは助言です。実際にブロックするのは、フックか拒否エントリとして書かれたものだけです。

## 動作を確かめる

既知の不正なペイロードをフックに与え、終了コード 2 になることを確認します:

```bash
echo '{"cwd":".","tool_name":"Bash","tool_input":{"command":"cat .env"}}' \
  | bash .claude/hooks/protect-secrets.sh ; echo "exit=$?"    # expect exit=2
```

Windows では `.ps1` のフックを使い、`$?` ではなく必ず `$LASTEXITCODE` を確認します。全体を一度に試すには、
リポジトリに同梱の `python eval/guardrail_eval.py` を使います (実際に生成したハーネスに 250 のペイロードを
当て、期待値は 250/250。`hooks_strict`、`long`、`db` を有効にしてスキャフォールドしたハーネスを測るので、
既定のインストールではフックはもっと少なくなります)。モデルには一切問い合わせません。ガードレールはシェル
スクリプトなので、結果がモデルに左右されることはありません。ツールの中では、`.env` を読もうとしたり `main`
にコミットしようとしたりして、それぞれブロックされることを確認してください。

## 関連

- [メイン README](../../README.ja.md)
- [AGENTS.md 契約](../../harness-bootstrap/assets/root/AGENTS.md)

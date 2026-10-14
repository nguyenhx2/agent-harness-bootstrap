# Codex でのハーネス

[English](codex.md) · **日本語**

Codex はスキルを実行しません。スキルが生み出したハーネスを実行します。Codex のフックのペイロードは Claude Code と
**同一**なので、ポーターは既存のフックを `.codex/hooks.json` にそのまま登録します。アダプターはありません。

Codex は `AGENTS.md` を、ルートのものも入れ子のものもネイティブに読みます。ルール変換が走らないのはそのため
ですが、それで何が得られるのかは正確に言っておく価値があります。スキャフォールドされた `AGENTS.md` は
`.claude/rules/` を**指している**だけで、中身を含んではいません。Codex にはパス単位のルールの仕組みがまったく
ありません。スコープの手段はディレクトリの配置だけです。そのため Codex では、ルールの本文は一致するパスに
触れたときに自動で付くコンテキストではなく、モデルが開くかどうかを選ぶファイルになります。常時有効のルールは
`AGENTS.md` に要約されています。パス単位のものは、実際には自分から求めないと届かない助言です。

## セットアップ

まず Claude 用のハーネスをスキャフォールドし (リポジトリに `.claude/rules/` と `.claude/hooks/` が必要です)、
それから移植します。リポジトリのルートで:

```bash
python ~/.claude/skills/harness-bootstrap/scripts/port.py --target . --tool codex
```

Python 3 が必要です。`--tool all` で Cursor と Codex を一度にセットアップできます。インストールするリリースは
ありません。ポーターはスキルに同梱されています。

## 置かれるもの

| パス | 役割 |
|---|---|
| `AGENTS.md` | ハーネスがすでに生成済み。Codex がネイティブに読む。ポーターは触れない |
| `.codex/hooks.json` | 既存の `.claude/hooks/*` を PreToolUse に登録する。マッチャーは `Bash` と `apply_patch` |

Codex が送るペイロード (`{cwd, tool_name, tool_input.command}`) はフックがすでに解析している形と一致し、
終了コード 2 で拒否されるのも Claude Code とまったく同じです。`Bash` マッチャーは `guard-main-commit`、
`check-commit-msg`、`protect-secrets` を実行し、`apply_patch` マッチャーは `protect-secrets` を実行します。
フックは同じ `.sh` (Windows では `.ps1`) ファイルで、何も書き換えません。

## 強制するもの、助言にとどまるもの

| 制御 | Codex のマッチャー | 効果 |
|---|---|---|
| `guard-main-commit` | `Bash` | 既定ブランチへの直接コミットをブロック |
| `check-commit-msg` | `Bash` | Conventional でない、または AI の帰属表示を含むコミットメッセージをブロック |
| `protect-secrets` | `Bash` + `apply_patch` | 秘密情報の読み取りと、秘密情報に触れるパッチをブロック |
| `protect-adr` | (パスは `apply_patch` のコマンドの中にある) | ベストエフォートのみ (限界を参照) |
| `specs-reminder` | 移植しない | Codex には該当しない |
| `agent-history` | 移植しない | Codex には該当しない |
| `AGENTS.md` | ネイティブに読む | 助言。強制できないルールは Codex が自主的に守る |

Bash ベースのガードは変更なしで動き、正確です。ポーターが移植するのはこれらのガードだけです。残りのフック
(`guard-destructive`、タスクボードのガード、`guard-agent-spawn` 内の検証台帳、オプトインの strict フック) は
Claude Code 専用のままです。

## 正直な限界

Codex はファイル編集を `apply_patch` 経由で行い、パスは `tool_input.file_path` フィールドではなく
`tool_input.command` の**中に**入ります。`protect-adr` はファイルパスを読むので、Codex ではベストエフォートに
なります。Accepted の ADR への編集が確実にブロックされるとは限りません。Bash のガード (秘密情報、コミット先、
コミットメッセージ) は正確です。

**どれかが動くかどうかは、2 つの前提条件で決まります。** プロジェクトローカルの `.codex/` 層は、プロジェクトが
信頼済みとしてマークされているとき (`[projects.<path>] trust_level = "trusted"`) にしか読み込まれません。また、
管理対象外のフックには、CLI の `/hooks` を通じたハッシュ固定の明示的なレビューが必要です。両方が済むまで、
移植したガードはディスク上に存在するだけで動きません。移植が失敗したと結論づける前に、ここを確認してください。

**起動の境界はまだ移せていません。** `guard-agent-spawn` は移植していません。このリポジトリは以前、Codex には
サブエージェント起動のフックポイントがないと書いていましたが、それはもう正しくありません。Codex は
`agent_type` マッチャー付きの `SubagentStart` と `SubagentStop` を出荷しています。同等にならない理由は、Codex の
エージェント種別が markdown の席ではなく `[agents.<name>]` の TOML テーブルから来ることです。ポーターがその
テーブルも出力しない限り、フックのロースター確認には照合する相手がありません。到達はできるが、まだ同等ではない、
という状態です。

## 動作を確かめる

フックのペイロードは Claude Code と共通なので、フックを直接テストします:

```bash
echo '{"cwd":".","tool_name":"Bash","tool_input":{"command":"git commit -m x"}}' \
  | bash .claude/hooks/guard-main-commit.sh ; echo "exit=$?"    # on main, expect exit=2
```

Windows では `.ps1` のフックを使い、`$LASTEXITCODE` を確認します。ツールの中では、`.env` を読もうとしたり
`main` にコミットしようとしたりして、それぞれブロックされることを確認してください。

## 関連

- [メイン README](../../README.ja.md)
- [AGENTS.md 契約](../../harness-bootstrap/assets/root/AGENTS.md)

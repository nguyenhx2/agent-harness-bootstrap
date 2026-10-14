# Cursor でのハーネス

[English](cursor.md) · **日本語**

Cursor はスキルを実行しません。スキルが生み出したハーネスを実行します。Cursor は `AGENTS.md` と
`.cursor/rules/*.mdc` を読みます。強制は `.cursor/hooks.json` と生成されたアダプターを通じて行われます。
アダプターは Cursor のフックのペイロードを既存の `.claude/hooks/*.sh` が期待する形に変換し、その終了コードを
逆向きに変換して返します。

## セットアップ

まず Claude 用のハーネスをスキャフォールドし (リポジトリに `.claude/rules/` と `.claude/hooks/` が必要です)、
それから移植します。リポジトリのルートで:

```bash
python ~/.claude/skills/harness-bootstrap/scripts/port.py --target . --tool cursor
```

Python 3 と、PATH 上の `bash` が必要です (アダプターは `.sh` のフックをシェル経由で呼びます)。インストールする
リリースはありません。ポーターはスキルに同梱されています。

## 置かれるもの

| パス | 役割 |
|---|---|
| `.cursor/rules/*.mdc` | `.claude/rules/*.md` ごとに一つ。`paths:` のないルールは `alwaysApply: true` に、`paths: [glob]` は `globs: glob` になる |
| `.cursor/hooks.json` | アダプターを `beforeShellExecution` と `beforeReadFile` に登録する |
| `.cursor/hooks/cursor-adapter.py` | Cursor のペイロードを `{cwd, tool_name, tool_input}` に正規化し、対応する `.claude/hooks/*.sh` を実行して、`{"permission": "allow"\|"deny", ...}` を出力する |
| `AGENTS.md` | ハーネスがすでに生成済み。Cursor がネイティブに読む (移植の手順なし) |

アダプターはシェルのイベントを Bash のガード (`guard-main-commit`、`check-commit-msg`、`protect-secrets`) に、
読み取りのイベントを `protect-adr` と `protect-secrets` に対応づけます。フックが終了コード 2 を返すと、その
フックの stderr をユーザー向けメッセージとする `deny` になり、それ以外は `allow` になります。

## 強制するもの、助言にとどまるもの

| 制御 | Cursor のイベント | 効果 |
|---|---|---|
| `protect-secrets` | `beforeShellExecution` + `beforeReadFile` | 秘密情報の読み取り (シェルまたはファイル) をブロック |
| `guard-main-commit` | `beforeShellExecution` | 既定ブランチへの直接コミットをブロック |
| `check-commit-msg` | `beforeShellExecution` | Conventional でない、または AI の帰属表示を含むコミットメッセージをブロック |
| `protect-adr` | `beforeReadFile` のパス | 読み取り時にブロック。編集前のブロックはベストエフォート (限界を参照) |
| `specs-reminder` | 移植しない | Cursor には該当しない |
| `agent-history` | 移植しない | Cursor には該当しない |
| `.cursor/rules/*.mdc` | Cursor が読み込む | 助言のみ |

シェルコマンドかファイル読み取りを通じて届くものは、すべて Claude Code と同じようにブロックされます。ポーターが
移植するのはこれらのガードだけです。残りのフック (`guard-destructive`、タスクボードのガード、
`guard-agent-spawn` 内の検証台帳、オプトインの strict フック) は Claude Code 専用のままです。

## 正直な限界

**ADR のガードは遅れて発火します。** 移植では Cursor の `afterFileEdit` に配線していますが、これは観察専用です。
そのため Accepted の ADR への編集は、起きる前にブロックされるのではなく、**事後に**指摘されます。Claude Code では
その編集は事前にブロックされます。

これは Cursor の限界ではなく、移植の限界です。Cursor は現在 `preToolUse` を公開しており、そのペイロード
(`tool_name`、`tool_input`、`cwd`) は Claude Code のものに十分近く、アダプターの変換はほぼ恒等関数になる
はずです。配線をそちらに移せば、事前のブロックが戻ります。まだ行っていません。

**起動の境界はまだ移せていません。** `guard-agent-spawn` は移植していません。少し前まで、このリポジトリはその
理由を Cursor にサブエージェント起動のフックポイントがないためだと書いていましたが、それはもう正しくありません。
Cursor はサブエージェント種別のマッチャー付きで `subagentStart` と `subagentStop` を出荷しています。ドキュメントは
このイベントでサブエージェントの作成を許可または拒否できると説明しており、終了コード 2 でブロックされます。
まだ障害として残っているのは、ペイロードのフィールドが Claude Code と異なること、そしてフックの中心となる確認
(`.claude/agents/<type>.md` が存在するか) が、名前付きの席の名前を Cursor が渡してくれるかどうかに依存し、
それが未検証であることです。到達はできるが、まだ同等ではない、という状態です。

**Cursor に相当するものがまったくない制御が 2 つあります。** 席ごとの `tools:` 許可リスト (Cursor が提供するのは
`readonly` だけで、レビュアーの場合はそれで足りますが、それより細かい指定はできません) と `maxTurns`
(相当するものが見つかっていません) です。どちらも移植では引き継がれず、配線で取り戻すこともできません。

## 動作を確かめる

アダプターのセルフテストを実行します。文書化されたサンプルペイロードに対して変換を検証します:

```bash
python ~/.claude/skills/harness-bootstrap/scripts/port.py --self-test    # expect 32/32
```

`cat .env` を拒否し、`main` へのコミットを拒否し、`npm test` を許可し、`.env` の読み取りを拒否し、`src` の
読み取りを許可します。同じテストが CI でも走ります。ツールの中では、`.env` を読もうとしたり `main` に
コミットしようとしたりして、それぞれ拒否されることを確認してください。

## 関連

- [メイン README](../../README.ja.md)
- [AGENTS.md 契約](../../harness-bootstrap/assets/root/AGENTS.md)

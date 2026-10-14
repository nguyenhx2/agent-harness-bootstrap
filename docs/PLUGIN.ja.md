# プラグインとしてインストールする

[English](PLUGIN.md) · **日本語**

2 つのスキル `harness-bootstrap` と `spec-builder` は、Claude Code、Cursor、Codex、そして
[Agent Plugins](https://agent-plugins.org/) 標準を読むその他のクライアントにプラグインとしてインストールできます。
これが推奨のインストール方法です。更新は手動の再ダウンロードではなくクライアント自身の更新コマンドで届き、
インストールされているバージョンも常に特定できます。zip のダウンロード (README を参照) も、オフラインで
バージョンを固定する代替手段として引き続き完全にサポートします。

| クライアント | 読むもの | このリポジトリでの置き場所 |
|---|---|---|
| Claude Code | 単一スキルの規約 (ディレクトリのルートに `SKILL.md`) | `.claude-plugin/marketplace.json` |
| Codex | `.codex-plugin/plugin.json` | `plugins/codex/<skill>/`。`.agents/plugins/marketplace.json` に列挙 |
| Cursor、VS Code、Copilot、Kiro、ChatGPT | プラグインのルートにある Agent Plugins の `plugin.json` | `plugins/<skill>/` |

**Codex に専用のディレクトリがある理由。** 最初の試みでは、3 つのマニフェストはそれぞれ別のパスに置かれるので、
すべてを一つのディレクトリに入れました。Codex はそれを拒否します。ルートに `plugin.json` があるとそれを検証し、
Agent Plugins が必須とする `$schema` キーを受け付けません (`missing or invalid plugin.json`)。Agent Plugins の
他のフィールドはすべて通るので、原因はこのキー一つです。`$schema` を外せば今日の時点では両方のクライアントを
満たせますが、標準が非準拠とするマニフェストを出荷することになるので、各スキルにルートを 2 つ持たせることに
しました。Codex に自分のルートの外にある `skills` パスを指させる方法もうまくいきません。Codex はプラグインの
ルートだけを `~/.codex/plugins/cache/` にコピーするので、インストール後にスキルがそっくり欠けてしまいます。

## Claude Code

```bash
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install harness-bootstrap@agent-harness-bootstrap
/plugin install spec-builder@agent-harness-bootstrap
```

どちらか一方だけでも、両方でもインストールできます。各エントリは `harness-bootstrap/` か `spec-builder/` を
直接指しています。`SKILL.md` はそのディレクトリのルートにあり、`skills/` サブディレクトリもスキルの
マニフェストもないので、Claude Code はそれを単一スキルのプラグインとして自動で読み込みます。それ以上の設定は
必要ありません。

## Codex

```bash
codex plugin marketplace add nguyenhx2/agent-harness-bootstrap
```

続いて Codex CLI で `/plugins` を開き、`harness-bootstrap`、`spec-builder`、または両方をインストールします。
マーケットプレイスは Codex がリポジトリから読むパスである `.agents/plugins/marketplace.json` にあり、その
エントリは `plugins/` 配下のプラグインディレクトリを指しています。

## Cursor とその他の Agent Plugins クライアント

`plugins/` 配下のディレクトリは Agent Plugins 1.1.0 のパッケージです。プラグインのルートに `plugin.json` があり、
スキルは `skills/` の下にあります。Cursor はローカルのプラグインをフォルダー単位で読み込むので、このリポジトリを
クローンし、プラグインのディレクトリを Cursor のローカルプラグインフォルダーにコピー (またはリンク) します:

```bash
git clone https://github.com/nguyenhx2/agent-harness-bootstrap
cp -r agent-harness-bootstrap/plugins/harness-bootstrap ~/.cursor/plugins/local/
```

その後ウィンドウを再読み込みします。標準がマニフェストのパスと `skills/` の位置の両方を定めているので、他の
Agent Plugins クライアントが使うのも同じディレクトリです。

**どこまで検証したか:** 3 つの経路すべてを実際のクライアントで試しました。

- **Claude Code** (`claude` 2.x): このリポジトリから両方のプラグインをインストールし、クライアントは
  `harness-bootstrap 1.15.0`、Skills (1) と報告しました。
- **Codex** (`codex-cli` 0.148.0): マーケットプレイスを追加し、両方のプラグインをインストールして、インストール後に
  `~/.codex/plugins/cache/.../skills/<skill>/` の中に `SKILL.md` があることを確認しました。以前の構成で
  黙って失敗していたのはこの部分です。
- **Cursor** (`cursor-agent` 2026.08.11): 生成した Agent Plugins のツリーを `--plugin-dir` で読み込み、エージェントが
  スキルを利用できることを確認しました。テストには生成したツリーを一意な名前にしたコピーを使いました。両方の
  スキルがテスト機にグローバルにもインストールされており、そうしなければそちらが代わりに応答してしまうためです。

この検証で本物の不具合が 3 つ見つかり、修正済みです。`policy.installation` はもっともらしく見える `user` では
なく `AVAILABLE` でなければならないこと。マーケットプレイスのソースパスは `marketplace.json` のあるディレクトリ
からではなく、リポジトリのルートから解決されること (`./plugins/...`)。そして `.codex-plugin/plugin.json` には
明示的な `skills` パスと `interface` ブロックが必要で、ないとインストールが拒否されることです。

## スキルを呼び出す

インストールしたら、名前空間つきの形でスキルを呼び出します:

```
/harness-bootstrap:harness-bootstrap
/spec-builder:spec-builder
```

zip からインストールしたときと同じく、Claude は各スキルの `SKILL.md` の説明にあるトリガーフレーズからも
自動でスキルを起動します。

## 更新する

```bash
/plugin update harness-bootstrap@agent-harness-bootstrap
/plugin update spec-builder@agent-harness-bootstrap
```

どちらのプラグインにも自前の `plugin.json` はないので、更新を決めるのは各マーケットプレイスエントリ
(`.claude-plugin/marketplace.json`) の `version` フィールドです。利用者に更新が届くのは、このフィールドが
上がったときだけです。2 つのスキルは一つのリポジトリバージョンでまとめてリリースされるので、両方の
マーケットプレイスエントリはリリースのたびに揃って上がります (`docs/RELEASING.md` を参照)。

## プラグインの経路と zip の経路

どちらも並行してサポートしており、今後もそのままです:

- **プラグインの経路**: `claude` CLI の `/plugin` コマンドで管理し、必要なときに更新でき、このリポジトリへの
  ネットワークアクセスが必要です。
- **zip の経路**: GitHub Releases からリリースのアーカイブをダウンロードして `.claude/skills/` に展開します。
  オフラインで動き、ファイルを置き換えるまで正確なバージョンに固定されます。

どちらかを廃止して他方に寄せる予定はありません。自分のワークフローに合う方を選んでください。

## 対象外のもの

単体の Rust バイナリである `tools/harness-view` は、プラグインとしては配布しません。zip と同じく、GitHub
Releases から各プラットフォーム用のバイナリをダウンロードしてください。

# リリース

[English](RELEASING.md) · **日本語**

2 つのスキル `harness-bootstrap` と `spec-builder` は、一つのリポジトリバージョン (`vX.Y.Z`) でまとめて
リリースします。リリースは CHANGELOG 駆動です。各スキル自身の `CHANGELOG.md` が、そのスキルで何を出荷したかの
唯一の正であり、GitHub のリリース本文は手で書くのではなく、それらのファイルから組み立てます。

## 手順

1. **バージョンを上げる。** `harness-bootstrap/SKILL.md` と `spec-builder/SKILL.md` の両方のフロントマターに
   `version: X.Y.Z` を設定します。2 つは常に一致します - 2 つのスキルはまとめてリリースするからです。
2. **CHANGELOG のエントリを書く。** 各スキル自身の `CHANGELOG.md` の先頭に `## [X.Y.Z] - YYYY-MM-DD` を追加
   します ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 形式、新しいものが先)。そのスキルに実際に
   触れたものだけを書きます。今回のリリースで機能上の変更がないスキルにも、その旨のエントリを追加します - どちら
   にしてもバージョンは同期させます。
   - PR のレビュアーではなく、GitHub のリリースページを読む人に向けて書きます。コミットの件名ではなく、何が
     変わり、それが読む人にとってなぜ重要かを書きます。em ダッシュは使わず、普通のハイフンを使います。
   - `tools/harness-view/CHANGELOG.md` にも `## [X.Y.Z] - YYYY-MM-DD` のエントリを追加します。ツールのバイナリは
     同じリリースに添付されるので、リリース本文はそれも説明しなければなりません。エントリがないと、何が変わった
     のかの説明が一切ないビルドをダウンロードさせることになります。これはゲートで確認されます。
   - リポジトリのルートの `CHANGELOG.md` にも `## vX.Y.Z` のセクションを追加します。これは以前からある別の
     物語形式の変更履歴で、`scripts/package.py --version X.Y.Z --check` が独立して引き続きゲートしています。
3. **検証する。**
   ```bash
   py -3.13 scripts/validate_release.py X.Y.Z
   ```
   次の場合に失敗します: CHANGELOG がない。エントリの形式が不正、重複している、または順序が違う。スキルの
   CHANGELOG の最新バージョンが自身の `SKILL.md` と一致しない。2 つのスキルのバージョンが食い違う。
   `tools/harness-view/Cargo.toml` がリポジトリのバージョンと食い違う。`tools/harness-view/CHANGELOG.md` に
   エントリがない。または (バージョン引数つきの場合) リリースするバージョンのエントリを持たないスキルがある。
   引数なしでは構造と同期の確認だけを行い、その形で CI がプッシュのたびに実行します。
4. **タグを付ける。**
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
5. **CI が公開する。** `release` ワークフローが成果物をビルドし、
   `py -3.13 scripts/release_notes.py X.Y.Z -o notes.md` でリリース本文を生成します (各スキルと各ツールの
   `## [X.Y.Z]` セクションが、それぞれ独立した `### skill-name` ブロックになります)。続いて
   `gh release create` を実行します (リリースがすでにある場合は `gh release edit` +
   `gh release upload --clobber` を実行するので、再実行しても安全です)。

### バージョンの上げ方

バージョン番号を持つファイルは 3 つあり、3 つすべてが一致しなければなりません。これは `validate_release.py` が
強制します: 両方のスキルの `SKILL.md` のフロントマターと、`tools/harness-view/Cargo.toml` です。Cargo の
バージョンはリリースされる実行ファイルに埋め込まれる (Windows の VERSIONINFO、`--version`、ページのフッター)
ので、古いままだと自分のバージョンを誤って報告するバイナリを出荷することになります。

## これを強制しているもの

| ルール | 強制しているもの |
| --- | --- |
| すべてのスキルがリリースバージョンの CHANGELOG エントリを持つ | `scripts/validate_release.py X.Y.Z` (リリースジョブのゲート) と `scripts/release_notes.py` (エントリを持つスキルが一つもないと非ゼロで終了) |
| エントリは `## [X.Y.Z] - YYYY-MM-DD` 形式で、新しいものが先 | `scripts/validate_release.py` |
| スキルの CHANGELOG のバージョンが自身の `SKILL.md` の `version:` と一致する | `scripts/validate_release.py` |
| 2 つのスキルがリポジトリのバージョンで一致する | `scripts/validate_release.py` |
| 上の同期確認はリリース時だけでなく、プッシュのたびに走る | `.github/workflows/eval.yml` (`guardrails` ジョブ) |
| リリース本文は手で打つのではなく、CHANGELOG から組み立てる | `.github/workflows/release.yml` から呼ばれる `scripts/release_notes.py` |
| リリース本文はスキルだけでなく、添付されるツールのバイナリも説明する | `scripts/release_notes.py` が `tools/harness-view/CHANGELOG.md` を読む。そのエントリがないと `scripts/validate_release.py X.Y.Z` が失敗する |
| タグの `SKILL.md` のバージョンがタグそのものと一致する | `scripts/package.py --version X.Y.Z --check` (`release` ジョブのゲート) |
| リポジトリのルートの `CHANGELOG.md` にリリースバージョンのセクションがある | `scripts/package.py --version X.Y.Z --check` (変更なし。上のスキルごとのファイルとは別) |
| すべてのアーカイブにタグと一致する `VERSION` ファイルが入っている | `.github/workflows/release.yml` ("Assert VERSION is inside every archive") |
| リリースジョブを再実行しても、既存のリリースで失敗しない | `release.yml` 内の `gh release edit` + `gh release upload --clobber` |
| `tools/harness-view/Cargo.toml` がリポジトリのバージョンと一致する | `scripts/validate_release.py` (`binaries` ジョブでもターゲットごとに再確認) |
| `tools/harness-view/Cargo.lock` が `Cargo.toml` と一致する | `scripts/validate_release.py` - `binaries` ジョブは `--locked` でビルドするので、`cargo update -p harness-view` を飛ばしたバージョン上げは、タグをプッシュした後にすべてのプラットフォームで失敗する |
| ビルドしたバイナリがリリースバージョンを報告する | `binaries` ジョブが、ネイティブに実行できるターゲットで `harness-view --version` を実行する |
| サポートするすべてのプラットフォームの単体バイナリが添付される | `.github/workflows/release.yml` (`binaries` マトリクスジョブ) |
| binaries ジョブを再実行すると、失敗せずにアセットを置き換える | `binaries` ジョブ内の `gh release upload --clobber` |
| アプリケーションのアイコンが存在し、必要なサイズをすべて持つ | `scripts/make_icons.py --check` (`guardrails` ジョブ) |
| 生成・執筆したどの内容にも em ダッシュがない | 慣習 - ツールではなくレビューで確認 |

## リリースを取り下げる

```bash
gh release delete vX.Y.Z --yes --cleanup-tag
```

その後、影響を受けたスキルの `CHANGELOG.md` に、理由とともに記録します。

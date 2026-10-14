# Wiki の公開

[English](README-publishing.md) · **日本語**

このディレクトリのページは、GitHub Wiki の**ソース**です。Wiki 自体は別の git リポジトリ
(`<repo>.wiki.git`) で、CI はそれを一切読みません。まさにそれが Wiki の腐る理由です。中の数字は古くなり、
どのチェックも気づきません。

そこで、リファレンスページはここでは一切書きません。`scripts/build_wiki.py` がアセットから生成し、その横の
ナラティブページ (日本語版の `*-ja.md` を含む) はそのままコピーされます。

## ビルド

```bash
python scripts/build_wiki.py            # -> dist/wiki/
```

## 公開

**`main` へのマージのたびに自動で。** `.github/workflows/wiki.yml` が Wiki を再ビルドしてプッシュします。
ビルド結果が実際に変わらない限り、何もしません。パスフィルタは意図的に付けていません。ビルダーはアセット、
スキャフォルダのフラグ集合、`benchmark.py` から導いた数字を読むので、実際の入力はリポジトリのほとんどに
及び、誰かが入力を一つ追加した最初の時点でフィルタは間違ったものになっていたはずです。代わりにビルド結果を
比較すれば、間違えようがありません。

`eval` ワークフローも実行のたびに Wiki をビルドするので、ページを壊す変更は、Wiki に届く前にビルドを
失敗させます。

### 必要なら手作業で

```bash
python scripts/build_wiki.py
git clone https://github.com/nguyenhx2/agent-harness-bootstrap.wiki.git /tmp/ahb-wiki
cp dist/wiki/*.md /tmp/ahb-wiki/
cd /tmp/ahb-wiki && git add -A && git commit -m "docs: rebuild wiki from the repository" && git push
```

### 自動化ではできないこと

Wiki のリポジトリは、最初のページが GitHub の UI から作られるまで存在しません。これは GitHub が API で
提供していない一度きりの手作業で、このリポジトリではすでに済んでいます。フォークでは、ワークフローが
プッシュできるようになる前に一度これを行う必要があります。

## Wiki の UI でページを編集しない

生成バナーの付いたページは次のビルドで上書きされ、その次のビルドは今やマージのたびに起こります。生成元の
アセットか、`docs/wiki/` のナラティブソースを変更すれば、ページはそれに追従します。

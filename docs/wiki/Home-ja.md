# Agent Harness Bootstrap

[[English|Home]] · **日本語**

二つの Claude Code スキルと、一つのビューアです。一つは、あなたにも AI にも読める仕様を書きます。
もう一つは、リポジトリに合ったエージェントチームを組みます。三つ目で全体を見渡し、どの部分でも
オフにできます。

この Wiki は**リファレンス**です。そもそもなぜこれが必要なのかという議論は
[README](https://github.com/nguyenhx2/agent-harness-bootstrap/blob/main/README.ja.md) にあり、
[ランディングページ](https://nguyenhx2.github.io/agent-harness-bootstrap/) はその短縮版です。
どちらもまだ読んでいなければ、そちらから始めてください。

## ここから始める

| やりたいこと | 読むページ |
|---|---|
| インストールして一度動かす | [はじめに](Getting-Started-ja) |
| ビルドが意図して小さい理由を知る | [テーラードビルド](Tailored-Build-ja) |
| 席、ルール、フック、コマンド、フラグを調べる | 下のリファレンスページ |
| 自分のハーネスが実際にどうなっているかを見る | [Harness View](Harness-View-ja) |
| 何かが発火しない理由を突き止める | [トラブルシューティング](Troubleshooting-ja) |
| よくある疑問を確かめる | [FAQ](FAQ-ja) |

## リファレンス

次の五つのページは、`scripts/build_wiki.py` が**リポジトリから生成**しています。手作業では
保守していません。Wiki の数字を信用できる理由は、それだけです (現時点では英語のみです):

- [[Agent Reference]] - 席、そのモデルと effort、それぞれがいつインストールされるか
- [[Rule Reference]] - どのルールが毎セッション読み込まれ、どれがパス限定か
- [[Hook Reference]] - 何が何をブロックするか、そしてそれを行う終了コード
- [[Command Reference]] - ハーネスがインストールするすべてのスラッシュコマンド
- [[Flag Reference]] - 質問票の各回答が何を有効にするか

これらのページを Wiki の UI で編集しても、次のビルドで上書きされます。代わりにアセットを変更すれば、
ページはそれに追従します。

## 一段落で言うと

`spec-builder` は、持ち込んだもの - アイデア、会議の書き起こし、レガシー文書、何もないリポジトリ - を、
国際標準に沿って書かれ、安定した要件 ID を持つ一つの契約に変えます。
`harness-bootstrap` はコードを読み、それに合った `.claude/` ハーネスを組み立てます。契約と実在する
モジュールから導いた編成、実在するパスに限定したルール、そして助言ではなくブロックするフック。
ガードレールはシェルスクリプトと終了コードです。モデルには問い合わせないので、安全の土台がモデルに
左右されることはありません。`harness-view` はその結果を読んで採点し、そこにもモデルは介在しません。

## 自分で確かめられる証拠

```bash
python eval/guardrail_eval.py                        # 安全の土台、フックの系統ごと (strict、long、db フラグを有効化)
python benchmark/benchmark.py                        # ハーネスあり vs 素のリポジトリ
python harness-bootstrap/scripts/port.py --self-test # Cursor と Codex のアダプタ
python scripts/check_numbers.py                      # 公開しているすべての数字 vs スクリプト
```

この Wiki には、誰かが記憶で書いた数字は一つもありません。ページとスクリプトが食い違っていたら、
正しいのはスクリプトで、ページの方がバグです。

# 図のソース

[English](README.md) · **日本語**

ここにある各 `.drawio` ファイルは、`docs/assets/` にある同名の SVG のソースです。編集するのはソースであり、
SVG ではありません。

図の再生成はリポジトリのルートから行います。2 番目の手順は省略できません。draw.io が書き出した生の SVG には
`scripts/check_svg.py` が拒否する DOCTYPE があり、GitHub のダークテーマでカードの色が反転するテーマ用
スタイルが入っていて、`<title>` と `<desc>` がないからです。

```sh
"C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light -o raw.svg docs/assets/src/harness-overview.drawio
python scripts/drawio_clean.py docs/assets/src/harness-overview.drawio raw.svg docs/assets/harness-overview.svg

"C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light -o raw.svg docs/assets/src/harness-overview.ja.drawio
python scripts/drawio_clean.py docs/assets/src/harness-overview.ja.drawio raw.svg docs/assets/harness-overview.ja.svg

python scripts/check_svg.py
```

他のプラットフォームでは、最初のパスをローカルの draw.io バイナリに置き換えてください (Linux なら `drawio`、
macOS なら `/Applications/draw.io.app/Contents/MacOS/draw.io`)。draw.io 30.0.4 と `drawio_clean.py` の出力には
タイムスタンプがなく、実行のたびにバイト単位で同一になります。

アクセシビリティ用のタイトルと説明は図の中には描かれていません。各ソースの `<diagram>` 要素にある
`figure-title` と `figure-desc` 属性に書かれており、`drawio_clean.py` がそれを SVG にコピーします。図を
描き直したら、これらも直してください。

PNG (`docs/assets/harness-overview.png`) はプレビュー用の書き出しです:
`draw.io.exe -x -f png -s 2 -o docs/assets/harness-overview.png docs/assets/src/harness-overview.drawio`。

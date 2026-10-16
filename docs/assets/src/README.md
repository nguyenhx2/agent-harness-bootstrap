# Figure sources

**English** · [日本語](README.ja.md)

Each `.drawio` file here is the source of the SVG of the same name in `docs/assets/`. Edit the
source, never the SVG.

Regenerate a figure from the repository root. The second step is not optional: the raw draw.io
export carries a DOCTYPE that `scripts/check_svg.py` refuses, theme styles that flip the card on
GitHub's dark theme, and no `<title>` or `<desc>`.

```sh
"C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light -o raw.svg docs/assets/src/harness-overview.drawio
python scripts/drawio_clean.py docs/assets/src/harness-overview.drawio raw.svg docs/assets/harness-overview.svg

"C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light -o raw.svg docs/assets/src/harness-overview.ja.drawio
python scripts/drawio_clean.py docs/assets/src/harness-overview.ja.drawio raw.svg docs/assets/harness-overview.ja.svg

"C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light -o raw.svg docs/assets/src/security-layers.drawio
python scripts/drawio_clean.py docs/assets/src/security-layers.drawio raw.svg docs/assets/security-layers.svg

"C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light -o raw.svg docs/assets/src/security-layers.ja.drawio
python scripts/drawio_clean.py docs/assets/src/security-layers.ja.drawio raw.svg docs/assets/security-layers.ja.svg

"C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light -o raw.svg docs/assets/src/control-layers.drawio
python scripts/drawio_clean.py docs/assets/src/control-layers.drawio raw.svg docs/assets/control-layers.svg

"C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light -o raw.svg docs/assets/src/harness-architecture.drawio
python scripts/drawio_clean.py docs/assets/src/harness-architecture.drawio raw.svg docs/assets/harness-architecture.svg

python scripts/check_svg.py
```

On another platform, replace the first path with the local draw.io binary (`drawio` on Linux,
`/Applications/draw.io.app/Contents/MacOS/draw.io` on macOS). The output of draw.io 30.0.4 plus
`drawio_clean.py` has no timestamp and is byte-identical across runs.

The accessible title and description are not drawn. They live in the `figure-title` and
`figure-desc` attributes on each source's `<diagram>` element, and `drawio_clean.py` copies them
into the SVG. Change the drawing and you change those too.

The PNG (`docs/assets/harness-overview.png`) is a preview export:
`draw.io.exe -x -f png -s 2 -o docs/assets/harness-overview.png docs/assets/src/harness-overview.drawio`.

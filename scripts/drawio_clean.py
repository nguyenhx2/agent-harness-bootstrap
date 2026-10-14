#!/usr/bin/env python3
"""Turn a draw.io SVG export into a figure this repo can ship.

draw.io's export is close but not shippable as it comes out:

  - it opens with a DOCTYPE, which scripts/check_svg.py refuses outright;
  - it styles every shape with CSS light-dark(), so the card would flip dark on
    GitHub's dark theme while the text colours stayed put;
  - it draws an invisible hit-area rect behind every text cell, which the
    orphan-box check would read as an unconnected box;
  - it has no <title> or <desc>, so a screen reader gets nothing.

This script fixes all four. The title and description come from the
`figure-title` and `figure-desc` attributes on the source's <diagram> element,
so the accessible text lives beside the drawing it describes. The output is a
pure function of its two inputs - no timestamp - so a re-export is
byte-identical.

    "C:/Program Files/draw.io/draw.io.exe" -x -f svg --svg-theme light \
        -o raw.svg docs/assets/src/harness-overview.drawio
    python scripts/drawio_clean.py docs/assets/src/harness-overview.drawio \
        raw.svg docs/assets/harness-overview.svg

Stdlib only, like every script here.
"""
from __future__ import annotations

import pathlib
import re
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


def meta(source: pathlib.Path) -> tuple[str, str, str]:
    diagram = ET.parse(source).getroot().find("diagram")
    if diagram is None:
        raise SystemExit(f"{source}: no <diagram> element")
    title, desc = diagram.get("figure-title"), diagram.get("figure-desc")
    if not title or not desc:
        raise SystemExit(f"{source}: <diagram> needs figure-title and figure-desc attributes")
    return title, desc, diagram.get("id") or source.stem


def clean(svg: str, title: str, desc: str, ident: str) -> str:
    s = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
    s = re.sub(r"<!DOCTYPE[^>]*>\s*", "", s)
    s = re.sub(r'\s+style="[^"]*light-dark[^"]*"', "", s)
    s = re.sub(r'<rect [^>]*fill="none" stroke="none"[^>]*/>', "", s)
    s = re.sub(r'\s+pointer-events="[^"]*"', "", s)
    s = re.sub(r'\s+data-cell-id="[^"]*"', "", s)

    head, _, body = s.partition(">")
    if "xlink:" not in body:
        head = head.replace(' xmlns:xlink="http://www.w3.org/1999/xlink"', "")
    head = re.sub(r'\s+style="[^"]*"', "", head, count=1)
    head = re.sub(r'\s+version="1\.1"', "", head, count=1)
    head = re.sub(r'(width|height)="(\d+(?:\.\d+)?)px"', r'\1="\2"', head)
    head += (f' role="img" aria-labelledby="{ident}-title {ident}-desc">'
             f'<title id="{ident}-title">{escape(title)}</title>'
             f'<desc id="{ident}-desc">{escape(desc)}</desc>')
    return head + body.rstrip() + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: drawio_clean.py SOURCE.drawio RAW_EXPORT.svg OUT.svg")
        return 2
    source, raw, out = (pathlib.Path(a) for a in argv)
    title, desc, ident = meta(source)
    text = clean(raw.read_text(encoding="utf-8"), title, desc, ident)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"{raw} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

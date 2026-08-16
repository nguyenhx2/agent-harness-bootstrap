#!/usr/bin/env python3
"""Structural checks on the SVG figures this repo embeds in its READMEs and pages.

A figure fails differently from code: it renders as a blank box, or as a box with
the wrong story in it, and nothing errors. Three failures have actually shipped
here, and each one is a check below:

  1. A figure whose text only appeared once its animation ran shipped EMPTY,
     because GitHub renders README images in an `img` context that never starts
     the animation clock. So: no SMIL, and no element may be born invisible.
  2. A figure referenced a font and an image over the network. In the same `img`
     context those never load. So: no external URLs.
  3. A box was drawn with no edge into it - "Code with Graph" sat orphaned in the
     overview for a whole release. So: every labelled box in a flow figure must
     be touched by at least one path. That one needs geometry, not a regex, and
     is checked here for the overview figures only.

Exit 0 = every figure is sound, 1 = at least one problem, printed with its file.

    python scripts/check_svg.py
"""
from __future__ import annotations

import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"

SVG_NS = "{http://www.w3.org/2000/svg}"

# SMIL animation elements. A CSS animation can be switched off by a media query;
# these cannot, so a reduced-motion reader would still get movement.
SMIL = ("animate", "animateMotion", "animateTransform", "set", "mpath")

# Anything that would reach the network at render time.
EXTERNAL = re.compile(r"""(?:href|src|xlink:href)\s*=\s*["']\s*(https?:)?//""", re.I)
IMPORT = re.compile(r"@import|url\(\s*['\"]?https?:", re.I)


def parse(path: pathlib.Path) -> ET.Element | None:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as e:
        print(f"  FAIL  {path.name}: not well-formed XML - {e}")
        return None


def check(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    root = parse(path)
    if root is None:
        return [f"{path.name}: unparseable"]

    for el in root.iter():
        tag = el.tag.replace(SVG_NS, "")
        if tag in SMIL:
            problems.append(f"{path.name}: uses SMIL <{tag}>, which no media query can disable")
        if tag == "script":
            problems.append(f"{path.name}: contains a <script>, which never runs in an img context")

    if EXTERNAL.search(text) or IMPORT.search(text):
        problems.append(f"{path.name}: references an external URL, which will not load in an "
                        f"img context")

    # An element whose resting opacity is 0 is invisible until something animates
    # it, and in the img context nothing ever will. The lookbehind matters: a
    # gradient's `stop-opacity="0"` is a colour reaching transparency, not a
    # hidden element, and matching it made this check cry wolf on its first run.
    for m in re.finditer(r'(?<![-\w])opacity\s*=\s*["\']0["\']', text):
        line = text[: m.start()].count("\n") + 1
        problems.append(f"{path.name}:{line}: an element rests at opacity 0, so it is invisible "
                        f"wherever the animation clock does not run")

    # Accessibility. Two different requirements, and conflating them made this
    # check demand a paragraph of prose from a logo on its first run.
    #
    # A NAME is required of every figure, but <title> and aria-label are equally
    # valid ways to give one - the branding marks use aria-label and are correct.
    named = root.find(f"{SVG_NS}title") is not None or root.get("aria-label")
    if not named:
        problems.append(f"{path.name}: has no accessible name (<title> or aria-label)")

    # A DESCRIPTION is only owed by a figure that carries information a name
    # cannot: a diagram with many labels says something, a shield-shaped mark
    # does not. The text count is the proxy, and it is deliberately generous.
    labels = sum(1 for _ in root.iter(f"{SVG_NS}text"))
    if labels >= 8 and root.find(f"{SVG_NS}desc") is None:
        problems.append(f"{path.name}: carries {labels} labels but no <desc> - a reader who "
                        f"cannot see it gets none of them, and the alt text in one README "
                        f"cannot serve the other language's README")

    return problems


def orphan_boxes(path: pathlib.Path) -> list[str]:
    """Every labelled box must be touched by at least one path endpoint.

    Checked only for the overview figures, where the boxes are a flow. A rect that
    no path reaches is a claim the picture forgot to connect, and it is invisible
    to every other check in this repo: "Code with Graph" shipped that way.
    """
    text = path.read_text(encoding="utf-8")
    root = parse(path)
    if root is None:
        return []

    rects = []
    for el in root.iter(f"{SVG_NS}rect"):
        try:
            x, y = float(el.get("x", "nan")), float(el.get("y", "nan"))
            w, h = float(el.get("width", "nan")), float(el.get("height", "nan"))
        except ValueError:
            continue
        rects.append((x, y, w, h))

    # A container big enough to be scenery is not a grouping. The page background
    # and the harness frame both enclose almost everything on the canvas, and
    # treating them as parents exempted every box in the figure from this check -
    # which is how the first version of it reported "sound" on a figure whose
    # Code with Graph arrow had been deleted. Green and useless is worse than
    # absent, so the threshold is explicit: a quarter of the canvas.
    try:
        vb = [float(n) for n in re.split(r"[ ,]+", (root.get("viewBox") or "").strip())]
        canvas = vb[2] * vb[3] if len(vb) == 4 else 0.0
    except ValueError:
        canvas = 0.0
    parent_max = canvas * 0.25

    def inside(a: tuple[float, float, float, float],
               b: tuple[float, float, float, float]) -> bool:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        if parent_max and (bw * bh) > parent_max:
            return False   # scenery, not a grouping
        return (bx <= ax and by <= ay and bx + bw >= ax + aw and by + bh >= ay + ah
                and (bw * bh) > (aw * ah))

    boxes = []
    for r in rects:
        x, y, w, h = r
        # Skip the page background, the outer frames, and the thin colour bars.
        if w > 700 or w < 40 or h < 30:
            continue
        # A box drawn INSIDE a panel is a detail of that panel, not a node in the
        # flow: the viewer band's four function chips sit inside the band, and the
        # band is what the arrow reaches. Requiring an arrow into each chip would
        # force meaningless lines into the picture.
        if any(inside(r, other) for other in rects if other != r):
            continue
        boxes.append(r)

    # Endpoints of every path: the first and last coordinate pair in the `d`.
    pts: list[tuple[float, float]] = []
    for el in root.iter(f"{SVG_NS}path"):
        d = el.get("d", "")
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
        if len(nums) >= 2:
            pts.append((nums[0], nums[1]))
            pts.append((nums[-2], nums[-1]))

    pad = 34.0  # an arrow that stops just short of a box still counts as reaching it
    problems = []
    for (x, y, w, h) in boxes:
        if not any(x - pad <= px <= x + w + pad and y - pad <= py <= y + h + pad
                   for px, py in pts):
            problems.append(f"{path.name}: the box at ({x:g},{y:g}) {w:g}x{h:g} has no path "
                            f"reaching it - it is drawn but not connected to anything")
    return problems


def self_test() -> list[str]:
    """Prove the orphan detector can still fire.

    A detector that matches nothing looks exactly like a figure with no problems:
    it prints ok and exits 0. This one WAS that, for its whole first hour - the
    harness frame counted as a parent, so every box inside it was exempt and a
    deliberately deleted arrow went unnoticed. The fixture below is the minimum
    that distinguishes the two states.
    """
    import tempfile

    fixture = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
  <title>t</title><desc>d</desc>
  <rect x="0" y="0" width="400" height="300" fill="#000"/>
  <rect x="10" y="10" width="380" height="280" fill="none"/>
  <rect x="40" y="60" width="100" height="40"/>
  <rect x="240" y="60" width="100" height="40"/>
  <path d="M140,80 L238,80"/>
  {orphan}
</svg>"""
    cases = [
        # An unreachable box must be reported, even though it sits inside a frame
        # that spans most of the canvas.
        ("connected", fixture.format(orphan='<rect x="40" y="200" width="100" height="40"/>'
                                            '<path d="M90,102 L90,198"/>'), 0),
        ("orphaned",  fixture.format(orphan='<rect x="40" y="200" width="100" height="40"/>'), 1),
    ]
    problems = []
    for name, body, want in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(body)
            tmp = pathlib.Path(fh.name)
        try:
            got = len(orphan_boxes(tmp))
        finally:
            tmp.unlink(missing_ok=True)
        if (got > 0) != bool(want):
            problems.append(f"self-test: the {name} fixture reported {got} orphan(s); the "
                            f"detector cannot tell a connected box from an unconnected one")
    return problems


def main() -> int:
    dead = self_test()
    for d in dead:
        print(f"  FAIL  {d}")

    files = sorted(ASSETS.glob("*.svg"))
    if not files:
        print("no SVG assets found")
        return 1

    problems: list[str] = list(dead)
    for f in files:
        found = check(f)
        if f.name.startswith("harness-loom"):
            found += orphan_boxes(f)
        problems += found
        print(f"  {'FAIL' if found else 'ok  '}  {f.name}")
        for p in found:
            print(f"          {p}")

    if problems:
        print(f"\n  {len(problems)} problem(s) across {len(files)} figure(s).")
        return 1
    print(f"\n  {len(files)} figure(s) sound.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Japanese-locale helpers for the Agent Harness Bootstrap intro clips.

Reuses the palette, watermark and end-card logo reveal from ../theme.py
unchanged (the end-card wordmark stays English - it is a brand mark).
Text-producing helpers (chip/tag/title_text/caption/box) are re-implemented
here with a JP-capable font, and every box-shaped helper clamps its label to
fit the box width so translated (denser/wider) strings never overflow.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from manim import Text, VGroup, RoundedRectangle, FadeIn, FadeOut

import theme as _theme

BG = _theme.BG
GREEN = _theme.GREEN
GREEN_HI = _theme.GREEN_HI
PURPLE = _theme.PURPLE
PURPLE_HI = _theme.PURPLE_HI
RED = _theme.RED
BLUE = _theme.BLUE
BLUE_HI = _theme.BLUE_HI
NEUTRAL = _theme.NEUTRAL
WHITE = _theme.WHITE
DIM = _theme.DIM
FW = _theme.FW
FH = _theme.FH
watermark = _theme.watermark
logo_reveal = _theme.logo_reveal

# verified against tofu with a -ql render (video/src/ja/jatheme.py test frame):
# Yu Gothic UI renders cleanly, including BOLD weight, and matches the EN
# deck's Segoe UI weight/style closely. Meiryo, Yu Gothic and MS Gothic all
# also render without tofu on this machine; Yu Gothic UI is used throughout.
JFONT = "Yu Gothic UI"


def _up():
    import numpy as np

    return np.array([0.0, 1.0, 0.0])


def caption(scene, s, hold=1.0, fade=0.35, y=-3.35, size=26, color=WHITE):
    """Burned-in caption bar for muted playback. Auto-shrinks to fit the frame."""
    txt = Text(s, font=JFONT, font_size=size, color=color)
    if txt.width > FW - 1.2:
        txt.scale((FW - 1.2) / txt.width)
    txt.move_to([0, y, 0])
    scene.play(FadeIn(txt, shift=0.12 * _up()), run_time=fade)
    scene.wait(hold)
    scene.play(FadeOut(txt), run_time=fade)


def chip(label, fill, stroke, text_color=WHITE, w=None, h=0.9, fs=26, radius=0.14):
    """A rounded artifact/agent chip with centered label, clamped to fit w."""
    t = Text(label, font=JFONT, font_size=fs, color=text_color)
    width = w if w is not None else t.width + 0.7
    if t.width > width - 0.35:
        t.scale((width - 0.35) / t.width)
    box = RoundedRectangle(
        width=width,
        height=h,
        corner_radius=radius,
        fill_color=fill,
        fill_opacity=1.0,
        stroke_color=stroke,
        stroke_width=2,
    )
    t.move_to(box.get_center())
    return VGroup(box, t)


def tag(label, color, fs=22):
    """Small pill used as a legend/keyword tag. Box auto-sizes to the label."""
    t = Text(label, font=JFONT, font_size=fs, color=color)
    box = RoundedRectangle(
        width=t.width + 0.5,
        height=0.6,
        corner_radius=0.3,
        fill_opacity=0.0,
        stroke_color=color,
        stroke_width=2,
    )
    t.move_to(box.get_center())
    return VGroup(box, t)


def title_text(s, fs=52, color=WHITE):
    return Text(s, font=JFONT, font_size=fs, color=color, weight="BOLD")


def box(label, fill, stroke, w, h=0.78, fs=20, text_color=WHITE, radius=0.13):
    """chip() but the label is always clamped inside the box (mirrors
    04-solution.py's local box() helper)."""
    t = Text(label, font=JFONT, font_size=fs, color=text_color, line_spacing=0.8)
    if t.width > w - 0.4:
        t.scale((w - 0.4) / t.width)
    r = RoundedRectangle(
        width=w,
        height=h,
        corner_radius=radius,
        fill_color=fill,
        fill_opacity=1.0,
        stroke_color=stroke,
        stroke_width=2,
    )
    t.move_to(r.get_center())
    return VGroup(r, t)


def fit(mobj, max_w):
    if mobj.width > max_w:
        mobj.scale(max_w / mobj.width)
    return mobj

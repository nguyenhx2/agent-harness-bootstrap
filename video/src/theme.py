"""Shared color grammar and helpers for the Agent Harness Bootstrap intro clips.

Color = meaning, never reassigned (matches docs/FLOWS.md and README):
  green  = deterministic / free / the harness / control
  purple = the AI model / agent / billed tokens
  red    = guardrail / a blocked action
  blue   = the human
  neutral / near-white = artifacts / files
Dark background, clean, technical, calm. No emoji.
"""

import os

from manim import (
    Text,
    VGroup,
    RoundedRectangle,
    Rectangle,
    Line,
    ImageMobject,
    FadeIn,
    FadeOut,
    config,
)

# --- palette ---------------------------------------------------------------
BG = "#12141A"

GREEN = "#2D6A4F"
GREEN_HI = "#52B788"
PURPLE = "#5A189A"
PURPLE_HI = "#9D4EDD"
RED = "#9D0208"
BLUE = "#1D3557"
BLUE_HI = "#A8DADC"
NEUTRAL = "#495057"
WHITE = "#F8F9FA"
DIM = "#8A94A0"

FONT = "Segoe UI"  # present on Windows; Manim falls back cleanly if missing

# fixed frame geometry (16:9). config.frame_width defaults to 14.222...
FW = config.frame_width
FH = config.frame_height


def caption(scene, s, hold=1.0, fade=0.35, y=-3.35, size=26, color=WHITE):
    """Burned-in caption bar for muted playback. Returns nothing; blocks for hold."""
    from manim import FadeIn, FadeOut

    txt = Text(s, font=FONT, font_size=size, color=color)
    if txt.width > FW - 1.2:
        txt.scale((FW - 1.2) / txt.width)
    txt.move_to([0, y, 0])
    scene.play(FadeIn(txt, shift=0.12 * _up()), run_time=fade)
    scene.wait(hold)
    scene.play(FadeOut(txt), run_time=fade)


def _up():
    import numpy as np

    return np.array([0.0, 1.0, 0.0])


def chip(label, fill, stroke, text_color=WHITE, w=None, h=0.9, fs=26, radius=0.14):
    """A rounded artifact/agent chip with centered label."""
    t = Text(label, font=FONT, font_size=fs, color=text_color)
    width = w if w is not None else t.width + 0.7
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
    """Small pill used as a legend/keyword tag."""
    t = Text(label, font=FONT, font_size=fs, color=color)
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
    return Text(s, font=FONT, font_size=fs, color=color, weight="BOLD")


# --- brand mark --------------------------------------------------------------
# navy shield + eye + graph nodes, rasterized from docs/assets/logo.svg (gradients
# do not survive SVGMobject reliably, so a PNG - rendered once via playwright - is
# the safe path; see video/src/assets/logo.png).
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")


def watermark(scene, height=0.55, opacity=0.5, corner=None):
    """A small, non-animated corner mark that persists for the rest of the scene.
    Call once near the top of construct(); do not FadeOut it with everything else."""
    mark = ImageMobject(LOGO_PATH).set_z_index(50)
    mark.height = height
    mark.set_opacity(opacity)
    pos = corner if corner is not None else (FW / 2 - 0.55, -FH / 2 + 0.5, 0)
    mark.move_to(pos)
    scene.add(mark)
    return mark


def logo_reveal(scene, brand_text="AGENT HARNESS BOOTSTRAP", height=1.5, hold=1.1, y=0.0):
    """A brief, centered logo + wordmark beat. Caller fades it out afterward."""
    mark = ImageMobject(LOGO_PATH)
    mark.height = height
    word = Text(brand_text, font=FONT, font_size=22, color=DIM)
    group = VGroup(word)
    mark.move_to([0, y + 0.55, 0])
    word.move_to([0, y - height / 2 - 0.15, 0])
    scene.play(FadeIn(mark, scale=0.9), FadeIn(word, shift=0.1 * _up()), run_time=0.7)
    scene.wait(hold)
    from manim import Group

    return Group(mark, word)

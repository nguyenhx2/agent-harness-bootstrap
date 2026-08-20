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
#
# The same tokens the landing page is drawn from (site/src/style.css), so a viewer who arrives from
# that page does not cross into a different product half way down it. The clips are embedded there
# now, which is what made the mismatch worth fixing: a dark clip in green and purple sitting inside
# a blueprint plate in blue and amber.
#
# The two signal colours keep the page's rule, and it is a rule rather than a preference: --live
# means a live signal and nothing else, --block means a refusal and nothing else. So GREEN_HI, used
# for what passes and what is running, becomes the live amber; RED, used for what is stopped,
# becomes the refusal coral. Nothing else in these clips may use those two.
#
# The NAMES stay as they were. Renaming GREEN to LIVE across seven scenes and their Japanese twins
# would be a large diff for no gain, and video/RENDERED.json hashes each scene's source - a
# cosmetic rename would invalidate every clip's provenance to say nothing.
BG = "#0b0e14"         # site --paper, dark

GREEN = "#c79a2e"      # --live held back: a live signal at rest
GREEN_HI = "#ffc94d"   # site --live
PURPLE = "#182a7a"     # site --field, the plate itself
PURPLE_HI = "#2c3f9e"  # site --field-lit
RED = "#ff7a5c"        # site --block: a refusal, nothing else
BLUE = "#182a7a"       # site --field
BLUE_HI = "#7a8ad4"    # site --field-line, route metal
NEUTRAL = "#6c7885"    # site --edge
WHITE = "#eef1fb"      # site --on-field
DIM = "#b3bee9"        # site --on-field-2

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

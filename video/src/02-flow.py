import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manim import (
    Scene,
    Text,
    VGroup,
    RoundedRectangle,
    FadeIn,
    FadeOut,
    Create,
    Write,
    GrowFromCenter,
    Arrow,
    CurvedArrow,
    Flash,
    Indicate,
    DOWN,
    UP,
    LEFT,
    RIGHT,
    ORIGIN,
)
import numpy as np
from theme import (
    BG,
    GREEN,
    GREEN_HI,
    PURPLE,
    PURPLE_HI,
    RED,
    BLUE,
    BLUE_HI,
    NEUTRAL,
    WHITE,
    DIM,
    FONT,
    caption,
    chip,
    tag,
    title_text,
)


class Flow(Scene):
    def construct(self):
        self.camera.background_color = BG

        # ---- title card -----------------------------------------------
        t = title_text("The operating flow", fs=46, color=WHITE)
        legend = VGroup(
            tag("green = free / deterministic", GREEN_HI, fs=20),
            tag("purple = billed tokens", PURPLE_HI, fs=20),
            tag("red = blocked", RED, fs=20),
        ).arrange(RIGHT, buff=0.4)
        grp = VGroup(t, legend).arrange(DOWN, buff=0.6)
        self.play(Write(t), run_time=0.9)
        self.play(FadeIn(legend, lag_ratio=0.2), run_time=0.7)
        self.wait(1.0)
        self.play(FadeOut(grp), run_time=0.5)

        # ---- Beat 1: spec-builder writes the contract -----------------
        sb = chip("spec-builder", PURPLE, PURPLE_HI, fs=26, h=0.9, w=3.8).move_to([-4.4, 1.6, 0])
        specs = chip("docs/specs/", NEUTRAL, WHITE, fs=24, h=0.9, w=3.2).move_to([0.2, 1.6, 0])
        specs_sub = Text("the contract", font=FONT, font_size=22, color=DIM).next_to(specs, DOWN, buff=0.22)
        a1 = Arrow(sb.get_right(), specs.get_left(), buff=0.2, color=DIM, stroke_width=3)

        self.play(GrowFromCenter(sb), run_time=0.5)
        caption(self, "spec-builder elicits, then writes the spec set - the contract.", hold=1.1, y=-3.5, size=24)
        self.play(Create(a1), run_time=0.5)
        self.play(GrowFromCenter(specs), FadeIn(specs_sub), run_time=0.6)
        self.wait(1.4)

        # move that row up and shrink to make room
        row1 = VGroup(sb, a1, specs, specs_sub)
        self.play(row1.animate.scale(0.8).to_edge(UP, buff=0.5), run_time=0.7)

        # ---- Beat 2: harness-bootstrap steps --------------------------
        hb = chip("harness-bootstrap", PURPLE, PURPLE_HI, fs=24, h=0.85, w=4.4).move_to([0, 0.9, 0])
        steps = [
            ("reads your code", PURPLE_HI, PURPLE),
            ("picks a scoped roster", PURPLE_HI, PURPLE),
            ("scaffolds in ~0.2s", GREEN_HI, GREEN),
            ("wires orchestration", GREEN_HI, GREEN),
        ]
        step_chips = VGroup()
        for label, stroke, fill in steps:
            c = chip(label, fill, stroke, fs=20, h=0.72, w=2.95)
            step_chips.add(c)
        step_chips.arrange(RIGHT, buff=0.28).move_to([0, -0.6, 0])

        self.play(GrowFromCenter(hb), run_time=0.5)
        caption(self, "harness-bootstrap reads your code and scaffolds the harness.", hold=0.8, y=-3.5, size=24)
        for c in step_chips:
            self.play(FadeIn(c, shift=0.12 * UP), run_time=0.45)
        # flash the deterministic 0.2s step green
        self.play(Indicate(step_chips[2], color=GREEN_HI, scale_factor=1.12), run_time=0.8)
        self.wait(0.6)

        row2 = VGroup(hb, step_chips)
        self.play(FadeOut(row1), FadeOut(row2), run_time=0.6)

        # ---- Beat 3: the task loop ------------------------------------
        head = Text("Then the task loop runs", font=FONT, font_size=30, color=WHITE).move_to([0, 1.6, 0])
        self.play(FadeOut(row2), FadeIn(head), run_time=0.6)

        orch = chip("orchestrator", PURPLE, PURPLE_HI, fs=24, h=0.9, w=3.4).move_to([0, 0.55, 0])
        dev = chip("scoped\nspecialist agents", PURPLE, PURPLE_HI, fs=20, h=1.0, w=3.4).move_to([-3.6, -1.4, 0])
        board = chip("task board\non disk", NEUTRAL, WHITE, fs=20, h=1.0, w=3.0).move_to([3.6, -1.4, 0])

        self.play(GrowFromCenter(orch), run_time=0.5)
        self.play(GrowFromCenter(dev), GrowFromCenter(board), run_time=0.6)

        dispatch = Arrow(orch.get_left() + DOWN * 0.1, dev.get_top(), buff=0.2, color=DIM, stroke_width=3)
        record = Arrow(dev.get_right(), board.get_left(), buff=0.2, color=DIM, stroke_width=3)
        d_label = Text("dispatches", font=FONT, font_size=19, color=DIM).next_to(dispatch, LEFT, buff=0.05).shift(UP*0.1)
        r_label = Text("records", font=FONT, font_size=19, color=DIM).next_to(record, UP, buff=0.05)
        self.play(Create(dispatch), FadeIn(d_label), run_time=0.5)
        caption(self, "An orchestrator dispatches scoped specialist agents.", hold=0.9, y=-3.5, size=24)
        self.play(Create(record), FadeIn(r_label), run_time=0.5)

        # hooks block a bad action
        hook = RoundedRectangle(width=1.9, height=0.7, corner_radius=0.14,
                                fill_color=RED, fill_opacity=1, stroke_color="#FFBA08", stroke_width=2)
        hook_t = Text("hooks", font=FONT, font_size=22, color=WHITE).move_to(hook.get_center())
        hookg = VGroup(hook, hook_t).move_to(dev.get_center() + DOWN * 1.4 + RIGHT * 1.6)
        bad = Arrow(dev.get_bottom(), hookg.get_top(), buff=0.15, color=DIM, stroke_width=3)
        blocked = Text("BLOCKED", font=FONT, font_size=20, color="#FFBA08").next_to(hookg, RIGHT, buff=0.3)
        self.play(GrowFromCenter(hookg), Create(bad), run_time=0.5)
        self.play(Flash(hookg.get_center(), color=RED, flash_radius=0.9), FadeIn(blocked), run_time=0.7)
        caption(self, "Hooks block bad actions before they happen.", hold=1.0, y=-3.5, size=24)

        # crash + resume
        self.play(FadeOut(VGroup(orch, dev, dispatch, record, d_label, r_label, hookg, bad, blocked)), run_time=0.5)
        crash = Text("agent crashes - context lost", font=FONT, font_size=26, color=RED).move_to([0, 0.4, 0])
        self.play(FadeIn(crash), Indicate(board, color=GREEN_HI, scale_factor=1.15), run_time=0.9)
        self.wait(0.5)
        fresh = chip("fresh agent", PURPLE, PURPLE_HI, fs=22, h=0.85, w=3.0).move_to([-3.6, -1.4, 0])
        resume = CurvedArrow(board.get_left(), fresh.get_right(), color=GREEN_HI, angle=-0.6)
        self.play(FadeOut(crash), GrowFromCenter(fresh), run_time=0.5)
        self.play(Create(resume), run_time=0.6)
        caption(self, "The board survives the crash - a fresh agent resumes where it stopped.", hold=2.2, y=-3.5, size=23)
        self.wait(1.0)
        self.play(FadeOut(VGroup(head, board, fresh, resume)), run_time=0.7)
        self.wait(0.2)

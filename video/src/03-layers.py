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
    Transform,
    Indicate,
    Arrow,
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


class Layers(Scene):
    def construct(self):
        self.camera.background_color = BG

        # ---- title ----------------------------------------------------
        t = title_text("The control layers", fs=46, color=WHITE)
        self.play(Write(t), run_time=0.9)
        self.wait(0.7)
        self.play(t.animate.scale(0.62).to_edge(UP, buff=0.4), run_time=0.7)

        # ---- four guardrail layers stacked ----------------------------
        layer_specs = [
            ("settings deny list", "cannot read .env, ~/.ssh, .npmrc"),
            ("blocking hooks", "cannot commit to main, edit an Accepted ADR"),
            ("path-scoped rules", "glob rules load only when a path matches"),
            ("review gates", "code + security reviewers, no Edit or Write"),
        ]
        layers = VGroup()
        for name, desc in layer_specs:
            box = RoundedRectangle(width=8.6, height=0.92, corner_radius=0.14,
                                   fill_color="#12211A", fill_opacity=1.0,
                                   stroke_color=GREEN_HI, stroke_width=2.5)
            nm = Text(name, font=FONT, font_size=25, color=GREEN_HI, weight="BOLD")
            ds = Text(desc, font=FONT, font_size=20, color=DIM)
            txt = VGroup(nm, ds).arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to(box.get_center())
            layers.add(VGroup(box, txt))
        layers.arrange(DOWN, buff=0.28).move_to([0, -0.35, 0])

        sub = Text("Four layers between the agent and damage", font=FONT, font_size=24, color=WHITE)
        sub.next_to(t, DOWN, buff=0.35)
        self.play(FadeIn(sub), run_time=0.5)

        for lyr in layers:
            self.play(FadeIn(lyr, shift=0.15 * UP), run_time=0.5)
            self.wait(0.45)
        caption(self, "Four guardrail layers: deny list, hooks, path-scoped rules, review gates.", hold=1.8, y=-3.6, size=23)
        self.wait(0.9)

        self.play(FadeOut(sub), layers.animate.scale(0.72).to_edge(LEFT, buff=0.5), run_time=0.8)

        # ---- key insight: shell scripts + glob = model independent ----
        insight = Text("The guardrails are shell scripts and glob rules",
                       font=FONT, font_size=26, color=WHITE).move_to([2.2, 1.9, 0])
        self.play(Write(insight), run_time=0.9)

        # model swap Opus -> Haiku, identical result
        model = chip("Opus", PURPLE, PURPLE_HI, fs=26, h=0.85, w=2.4).move_to([2.2, 0.7, 0])
        result = chip("15 / 15", GREEN, GREEN_HI, fs=30, h=0.9, w=2.6).move_to([2.2, -1.2, 0])
        res_label = Text("guardrail eval", font=FONT, font_size=20, color=DIM).next_to(result, DOWN, buff=0.2)
        arrow = Arrow(model.get_bottom(), result.get_top(), buff=0.2, color=DIM, stroke_width=3)

        self.play(GrowFromCenter(model), run_time=0.5)
        self.play(Create(arrow), GrowFromCenter(result), FadeIn(res_label), run_time=0.7)
        self.wait(0.6)

        # swap the model
        haiku = chip("Haiku", PURPLE, PURPLE_HI, fs=26, h=0.85, w=2.4).move_to(model.get_center())
        swap_label = Text("swap every agent", font=FONT, font_size=20, color=PURPLE_HI).next_to(model, UP, buff=0.25)
        self.play(FadeIn(swap_label), run_time=0.4)
        self.play(Transform(model, haiku), run_time=0.7)
        # result flashes but stays identical
        self.play(Indicate(result, color=GREEN_HI, scale_factor=1.15), run_time=0.9)
        byte = Text("byte-identical safety", font=FONT, font_size=24, color=GREEN_HI, weight="BOLD")
        byte.next_to(insight, DOWN, buff=0.4).align_to(insight, LEFT)
        self.play(FadeIn(byte, shift=0.1 * RIGHT), run_time=0.5)
        caption(self, "Swap Opus to Haiku: byte-identical result. Control does not depend on the model.", hold=2.3, y=-3.6, size=22)
        self.wait(2.2)

        self.play(
            FadeOut(VGroup(layers, insight, byte, model, result, res_label, arrow, swap_label)),
            run_time=0.7,
        )

        # ---- state on disk + ports ------------------------------------
        h2 = Text("State lives on disk, not in a context window",
                  font=FONT, font_size=28, color=WHITE).move_to([0, 1.7, 0])
        self.play(FadeIn(h2), run_time=0.6)

        ram = chip("RAM", PURPLE, PURPLE_HI, fs=24, h=0.85, w=2.6).move_to([-3.0, 0.4, 0])
        ram_sub = Text("compacts, lost", font=FONT, font_size=20, color=RED).next_to(ram, DOWN, buff=0.2)
        disk = chip("committed markdown", NEUTRAL, WHITE, fs=22, h=0.85, w=4.2).move_to([2.4, 0.4, 0])
        disk_sub = Text("survives", font=FONT, font_size=20, color=GREEN_HI).next_to(disk, DOWN, buff=0.2)
        self.play(GrowFromCenter(ram), FadeIn(ram_sub), run_time=0.5)
        self.play(GrowFromCenter(disk), FadeIn(disk_sub), run_time=0.5)
        self.wait(1.3)

        # ports footer
        ports = VGroup(
            tag("Claude Code", GREEN_HI, fs=24),
            tag("Cursor", GREEN_HI, fs=24),
            tag("Codex", GREEN_HI, fs=24),
        ).arrange(RIGHT, buff=0.5).move_to([0, -1.6, 0])
        pl = Text("Ports with enforcement, not just advice", font=FONT, font_size=24, color=DIM)
        pl.next_to(ports, DOWN, buff=0.4)
        self.play(FadeIn(ports, lag_ratio=0.3, shift=0.12 * UP), run_time=0.8)
        self.play(FadeIn(pl), run_time=0.5)
        caption(self, "Control does not depend on the model.", hold=2.2, y=-3.6, size=24, color=GREEN_HI)
        self.wait(0.6)
        self.play(FadeOut(VGroup(t, h2, ram, ram_sub, disk, disk_sub, ports, pl)), run_time=0.8)
        self.wait(0.2)

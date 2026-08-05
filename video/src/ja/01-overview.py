import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

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
    Indicate,
    Arrow,
    Line,
    DOWN,
    UP,
    LEFT,
    RIGHT,
    ORIGIN,
)
import numpy as np
from jatheme import (
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
    JFONT,
    caption,
    chip,
    tag,
    title_text,
    watermark,
    logo_reveal,
)


class Overview(Scene):
    def construct(self):
        self.camera.background_color = BG
        watermark(self)

        # ---- Beat 0: core message -------------------------------------
        line1 = Text(
            "AIエージェントに",
            font=JFONT,
            font_size=40,
            color=WHITE,
        )
        under = Text("本当に理解できるリポジトリと", font=JFONT, font_size=40, color=GREEN_HI, weight="BOLD")
        line2a = Text("抜け出せない", font=JFONT, font_size=40, color=RED, weight="BOLD")
        line2b = Text("ハーネスを与える", font=JFONT, font_size=40, color=WHITE)

        top = VGroup(line1, under).arrange(RIGHT, buff=0.22)
        bot = VGroup(line2a, line2b).arrange(RIGHT, buff=0.22)
        both = VGroup(top, bot).arrange(DOWN, buff=0.35).move_to([0, 0.4, 0])

        brand = Text("AGENT HARNESS BOOTSTRAP", font=JFONT, font_size=22, color=DIM)
        brand.next_to(both, DOWN, buff=0.9)

        self.play(Write(top), run_time=1.4)
        self.play(Write(bot), run_time=1.4)
        self.play(FadeIn(brand, shift=0.1 * UP), run_time=0.6)
        self.wait(2.3)
        self.play(FadeOut(both), FadeOut(brand), run_time=0.6)

        # ---- Beat 1: the problem --------------------------------------
        # a neutral repo box with a purple agent dropped in
        repo = RoundedRectangle(
            width=3.2, height=3.6, corner_radius=0.18,
            fill_color="#1B1E27", fill_opacity=1.0, stroke_color=NEUTRAL, stroke_width=2,
        ).move_to([-4.2, 0.15, 0])
        repo_label = Text("あなたのリポジトリ", font=JFONT, font_size=22, color=DIM).next_to(repo, UP, buff=0.2)
        # a few file lines inside
        files = VGroup(*[
            RoundedRectangle(width=2.2, height=0.28, corner_radius=0.08,
                             fill_color=NEUTRAL, fill_opacity=0.8, stroke_width=0)
            for _ in range(5)
        ]).arrange(DOWN, buff=0.22).move_to(repo.get_center())

        agent = chip("AIエージェント", PURPLE, PURPLE_HI, fs=24, h=0.95)
        agent.next_to(repo, RIGHT, buff=1.1).shift(UP * 1.2)
        drop_arrow = Arrow(agent.get_left(), repo.get_right(), buff=0.15, color=PURPLE_HI, stroke_width=4)

        self.play(Create(repo), FadeIn(repo_label), run_time=0.7)
        self.play(FadeIn(files, lag_ratio=0.2), run_time=0.7)
        self.play(GrowFromCenter(agent), run_time=0.5)
        self.play(Create(drop_arrow), run_time=0.5)
        caption(self, "AIエージェントをリポジトリに置いても、何も制約しない。", hold=1.2)

        # problem flags stack on the right
        problems = [
            "従うべき標準がない",
            "要件を勝手に作り出す（幻覚）",
            "圧縮されると全てを忘れる",
            "1ターンで.envを読み、mainに直接コミットしかねない",
            "気づかぬうちに最上位モデル階層で課金される",
        ]
        flags = VGroup()
        for p in problems:
            dot = RoundedRectangle(width=0.16, height=0.16, corner_radius=0.08,
                                   fill_color=RED, fill_opacity=1, stroke_width=0)
            t = Text(p, font=JFONT, font_size=23, color=WHITE)
            row = VGroup(dot, t).arrange(RIGHT, buff=0.3)
            flags.add(row)
        flags.arrange(DOWN, aligned_edge=LEFT, buff=0.42)
        flags.next_to(repo, RIGHT, buff=1.0).align_to(repo, UP).shift(DOWN * 0.1)

        self.play(FadeOut(agent), FadeOut(drop_arrow), run_time=0.4)
        for row in flags:
            self.play(FadeIn(row, shift=0.15 * RIGHT), run_time=0.5)
            self.wait(0.35)
        self.play(Indicate(flags, color=RED, scale_factor=1.04), run_time=0.9)
        self.wait(1.3)
        self.play(FadeOut(flags), FadeOut(repo), FadeOut(repo_label), FadeOut(files), run_time=0.6)

        # ---- Beat 2: the solution - two skills ------------------------
        head = title_text("2つのスキルがハーネスを構築する", fs=36, color=WHITE).move_to([0, 2.6, 0])
        self.play(Write(head), run_time=0.9)

        sb = chip("spec-builder", PURPLE, PURPLE_HI, fs=28, h=1.0, w=4.2)
        hb = chip("harness-bootstrap", PURPLE, PURPLE_HI, fs=28, h=1.0, w=4.2)
        sb.move_to([-3.4, 0.9, 0])
        hb.move_to([3.4, 0.9, 0])

        sb_sub = Text("契約書を書く", font=JFONT, font_size=24, color=GREEN_HI).next_to(sb, DOWN, buff=0.3)
        hb_sub = Text("境界を構築する", font=JFONT, font_size=24, color=GREEN_HI).next_to(hb, DOWN, buff=0.3)

        # the harness boundary - green box the agent runs inside
        boundary = RoundedRectangle(
            width=5.0, height=2.0, corner_radius=0.2,
            fill_color="#12211A", fill_opacity=1.0, stroke_color=GREEN_HI, stroke_width=3,
        ).move_to([0, -1.9, 0])
        b_label = Text("エージェントがその内側で動くハーネス", font=JFONT, font_size=20, color=GREEN_HI)
        b_label.next_to(boundary, UP, buff=0.18)
        inner_agent = chip("エージェント", PURPLE, PURPLE_HI, fs=22, h=0.8, w=2.2).move_to(boundary.get_center())

        self.play(GrowFromCenter(sb), GrowFromCenter(hb), run_time=0.7)
        self.play(FadeIn(sb_sub), FadeIn(hb_sub), run_time=0.6)
        caption(self, "spec-builderが契約書を書き、harness-bootstrapが境界を構築する。", hold=1.3, y=-3.55, size=23)

        a1 = Arrow(sb.get_bottom(), boundary.get_left() + UP * 0.3, buff=0.15, color=DIM, stroke_width=3)
        a2 = Arrow(hb.get_bottom(), boundary.get_right() + UP * 0.3, buff=0.15, color=DIM, stroke_width=3)
        self.play(Create(a1), Create(a2), run_time=0.6)
        self.play(FadeIn(b_label), Create(boundary), run_time=0.7)
        self.play(GrowFromCenter(inner_agent), run_time=0.5)
        self.wait(1.7)
        self.play(
            FadeOut(VGroup(head, sb, hb, sb_sub, hb_sub, a1, a2, boundary, b_label, inner_agent)),
            run_time=0.6,
        )

        # ---- Beat 3: the payoff ---------------------------------------
        payoff = title_text("制御された、モデルに依存しないエージェントシステム", fs=28, color=WHITE)
        payoff.move_to([0, 1.7, 0])
        self.play(Write(payoff), run_time=1.0)

        ports = VGroup(
            tag("Claude Code", GREEN_HI, fs=26),
            tag("Cursor", GREEN_HI, fs=26),
            tag("Codex", GREEN_HI, fs=26),
        ).arrange(RIGHT, buff=0.6).move_to([0, 0.2, 0])
        for p in ports:
            p[0].set_height(0.8)
        ports.arrange(RIGHT, buff=0.6).move_to([0, 0.2, 0])

        sub = Text("助言だけでなく、強制を伴って移植される", font=JFONT, font_size=24, color=DIM)
        sub.next_to(ports, DOWN, buff=0.7)

        self.play(FadeIn(ports, lag_ratio=0.3, shift=0.15 * UP), run_time=1.0)
        self.play(FadeIn(sub, shift=0.1 * UP), run_time=0.6)
        self.wait(1.6)
        self.play(FadeOut(VGroup(payoff, ports, sub)), run_time=0.6)

        # ---- Beat 4: brand end card -------------------------------------
        card = logo_reveal(self)
        self.wait(0.3)
        self.play(FadeOut(card), run_time=0.5)

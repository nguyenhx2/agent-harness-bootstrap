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
    Indicate,
    Arrow,
    DashedLine,
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
)
from theme import watermark


def small(s, fs=20, color=DIM):
    return Text(s, font=JFONT, font_size=fs, color=color)


class SkillsAndView(Scene):
    """概要図の運用フローと、それを健全に保つ3つの仕組み:
    スキル探索、スキル配線、harness-view。

    docs/assets/harness-loom.ja.svg と同じ順序で進むため、図と映像が
    別々の話をし始めることはない。
    """

    def construct(self):
        self.camera.background_color = BG
        watermark(self)

        # ---- タイトル ----------------------------------------------------
        t = title_text("どう動き、何が健全さを保つのか", fs=42, color=WHITE)
        self.play(Write(t), run_time=0.9)
        self.wait(0.6)
        self.play(t.animate.scale(0.58).to_edge(UP, buff=0.35), run_time=0.6)

        # =================================================================
        # ビートA - 運用フロー
        # =================================================================
        caption(self, "入力は、来た形のまま入ってくる。", hold=1.0)

        sources = ["アイデア", "議事録", "既存ドキュメント", "リポジトリ"]
        src_chips = VGroup(
            *[chip(s, BG, NEUTRAL, text_color=DIM, w=2.9, h=0.6, fs=20) for s in sources]
        ).arrange(DOWN, buff=0.22)
        src_chips.move_to([-5.3, -0.3, 0])
        self.play(FadeIn(src_chips, shift=0.2 * np.array([1.0, 0, 0])), run_time=0.7)

        spec = chip("spec-builder", BLUE, BLUE_HI, w=2.9, h=0.95, fs=24)
        spec.move_to([-1.9, -0.3, 0])
        arrows_in = VGroup(
            *[
                Arrow(
                    c.get_right() + 0.05 * np.array([1.0, 0, 0]),
                    spec.get_left(),
                    buff=0.08,
                    stroke_width=2.4,
                    max_tip_length_to_length_ratio=0.09,
                    color=NEUTRAL,
                )
                for c in src_chips
            ]
        )
        self.play(Create(arrows_in), run_time=0.6)
        self.play(FadeIn(spec, scale=0.92), run_time=0.5)
        caption(self, "spec-builder が、そのどれもを一つの契約に変える。", hold=1.1)

        contract = small("一つの契約", fs=19, color=BLUE_HI)
        agent = chip("エージェント", PURPLE, PURPLE_HI, w=2.9, h=0.95, fs=24)
        agent.move_to([2.1, -0.3, 0])
        a1 = Arrow(spec.get_right(), agent.get_left(), buff=0.12, stroke_width=3,
                   max_tip_length_to_length_ratio=0.12, color=BLUE_HI)
        if contract.width > a1.get_length() - 0.15:
            contract.scale((a1.get_length() - 0.15) / contract.width)
        contract.next_to(a1, UP, buff=0.12)
        self.play(Create(a1), FadeIn(contract), run_time=0.6)
        self.play(FadeIn(agent, scale=0.92), run_time=0.5)

        rules = chip("ルール", GREEN, GREEN_HI, w=2.0, h=0.6, fs=20)
        hooks = chip("フック", RED, "#E5383B", w=2.0, h=0.6, fs=20)
        rules.move_to([0.9, 1.85, 0])
        hooks.move_to([3.3, 1.85, 0])
        d1 = Arrow(rules.get_bottom(), agent.get_top() + 0.35 * LEFT, buff=0.1,
                   stroke_width=2.4, max_tip_length_to_length_ratio=0.12, color=GREEN_HI)
        d2 = Arrow(hooks.get_bottom(), agent.get_top() + 0.35 * RIGHT, buff=0.1,
                   stroke_width=2.4, max_tip_length_to_length_ratio=0.12, color="#E5383B")
        self.play(FadeIn(rules, shift=0.2 * DOWN), FadeIn(hooks, shift=0.2 * DOWN), run_time=0.5)
        self.play(Create(d1), Create(d2), run_time=0.5)
        caption(self, "ルールとフックが上から降りてくる。終了コード 2 は呼び出しを遮断する。", hold=1.3)

        outs = VGroup(
            chip("ドキュメント + グラフ", BG, GREEN_HI, text_color=WHITE, w=2.9, h=0.6, fs=17),
            chip("計画", BG, GREEN_HI, text_color=WHITE, w=2.9, h=0.6, fs=17),
            chip("コード + グラフ", BG, GREEN_HI, text_color=WHITE, w=2.9, h=0.6, fs=17),
        ).arrange(DOWN, buff=0.24)
        outs.move_to([5.6, -0.3, 0])
        out_arrows = VGroup(
            *[
                Arrow(agent.get_right(), c.get_left(), buff=0.1, stroke_width=2.4,
                      max_tip_length_to_length_ratio=0.09, color=GREEN_HI)
                for c in outs
            ]
        )
        self.play(Create(out_arrows), FadeIn(outs), run_time=0.8)
        caption(self, "秩序ある三つの成果物が、毎回、安定 ID を持って出ていく。", hold=1.3)

        state = chip("状態: プロンプト・実行履歴・タスクボード", BG, GREEN_HI,
                     text_color=DIM, w=6.4, h=0.62, fs=19)
        state.move_to([2.1, -2.35, 0])
        s_link = DashedLine(agent.get_bottom(), state.get_top(), stroke_width=2.2,
                            color=GREEN_HI, dash_length=0.12)
        self.play(FadeIn(state, shift=0.15 * UP), Create(s_link), run_time=0.6)
        caption(self, "状態は与えられるものではなく、書かれるもの。圧縮も再起動も越えて残る。", hold=1.4)

        self.play(
            FadeOut(VGroup(src_chips, arrows_in, spec, a1, contract, rules, hooks,
                           d1, d2, agent, out_arrows, outs, state, s_link)),
            run_time=0.6,
        )

        # =================================================================
        # ビートB - スキル探索
        # =================================================================
        h2 = Text("スキル探索", font=JFONT, font_size=34, color=WHITE, weight="BOLD")
        h2.move_to([0, 2.35, 0])
        prob = small("課題: 読んだこともないカタログから選ぶことはできない。", fs=22, color=DIM)
        prob.move_to([0, 1.7, 0])
        self.play(FadeIn(h2, shift=0.15 * DOWN), FadeIn(prob), run_time=0.6)

        manifests = VGroup(
            *[
                chip(m, BG, NEUTRAL, text_color=DIM, w=3.1, h=0.55, fs=18)
                for m in ["requirements.txt", "Gemfile", "*.csproj", "build.gradle"]
            ]
        ).arrange(DOWN, buff=0.16)
        manifests.move_to([-4.1, -0.9, 0])
        self.play(FadeIn(manifests, shift=0.15 * RIGHT), run_time=0.6)
        caption(self, "汎用の一覧ではなく、このプロジェクトのマニフェストを読む。", hold=1.2)

        stack = chip("検出された技術スタック", GREEN, GREEN_HI, w=4.2, h=0.8, fs=20)
        stack.move_to([0.2, -0.9, 0])
        self.play(
            Create(Arrow(manifests.get_right(), stack.get_left(), buff=0.15,
                         stroke_width=2.6, max_tip_length_to_length_ratio=0.1, color=GREEN_HI)),
            FadeIn(stack, scale=0.92),
            run_time=0.7,
        )

        matched = VGroup(
            chip("合致するスキル", BG, GREEN_HI, text_color=WHITE, w=3.6, h=0.6, fs=19),
            chip("選ぶかどうかは、あなた", BG, BLUE_HI, text_color=BLUE_HI, w=3.6, h=0.6, fs=19),
        ).arrange(DOWN, buff=0.22)
        matched.move_to([4.6, -0.9, 0])
        self.play(
            Create(Arrow(stack.get_right(), matched.get_left(), buff=0.15, stroke_width=2.6,
                         max_tip_length_to_length_ratio=0.1, color=GREEN_HI)),
            FadeIn(matched),
            run_time=0.7,
        )
        caption(self, "勝手にインストールはされない。受け入れるも断るも、あなたが決める。", hold=1.4)

        self.play(FadeOut(VGroup(h2, prob, manifests, stack, matched)), run_time=0.5)

        # =================================================================
        # ビートC - スキル配線
        # =================================================================
        h3 = Text("スキル配線", font=JFONT, font_size=34, color=WHITE, weight="BOLD")
        h3.move_to([0, 2.35, 0])
        prob3 = small("課題: 誰も使うよう指示されていないスキルは、ただの死荷重。", fs=22, color=DIM)
        prob3.move_to([0, 1.7, 0])
        self.play(FadeIn(h3, shift=0.15 * DOWN), FadeIn(prob3), run_time=0.6)

        skill = chip("選ばれたスキル", BG, BLUE_HI, text_color=WHITE, w=3.6, h=0.8, fs=21)
        seat = chip("それを必要とするエージェント", PURPLE, PURPLE_HI, w=5.4, h=0.8, fs=21)
        skill.move_to([-3.8, -0.7, 0])
        seat.move_to([2.6, -0.7, 0])
        self.play(FadeIn(skill), FadeIn(seat), run_time=0.5)

        wire = Arrow(skill.get_right(), seat.get_left(), buff=0.15, stroke_width=3.4,
                     max_tip_length_to_length_ratio=0.08, color=BLUE_HI)
        wire_lbl = small("/skill-wire", fs=20, color=BLUE_HI)
        wire_lbl.next_to(wire, UP, buff=0.14)
        self.play(Create(wire), FadeIn(wire_lbl), run_time=0.6)
        self.play(Indicate(wire, color=WHITE, scale_factor=1.05), run_time=0.6)
        caption(self, "配線は文書上の慣習ではなく、グラフ上のノードとして残る。", hold=1.4)

        self.play(FadeOut(VGroup(h3, prob3, skill, seat, wire, wire_lbl)), run_time=0.5)

        # =================================================================
        # ビートD - harness-view
        # =================================================================
        h4 = Text("harness-view", font=JFONT, font_size=34, color=WHITE, weight="BOLD")
        h4.move_to([0, 2.35, 0])
        prob4 = small("課題: 本当に正しく配線されていると、どう分かるのか。", fs=22, color=DIM)
        prob4.move_to([0, 1.7, 0])
        self.play(FadeIn(h4, shift=0.15 * DOWN), FadeIn(prob4), run_time=0.6)

        funcs = [
            ("フロー / グラフ", "全ての配線をディスクから"),
            ("評価", "採点と、何が問題か"),
            ("切り替え", "任意のルールやフックを無効化"),
            ("監視", "ファイル変更に応じて再走査"),
        ]
        cards = VGroup()
        for name, desc in funcs:
            box_ = RoundedRectangle(width=3.0, height=1.25, corner_radius=0.14,
                                    fill_color=BG, fill_opacity=1.0,
                                    stroke_color=GREEN_HI, stroke_width=2)
            n = Text(name, font=JFONT, font_size=20, color=WHITE, weight="BOLD")
            d = Text(desc, font=JFONT, font_size=15, color=DIM)
            for m in (n, d):
                if m.width > 2.7:
                    m.scale(2.7 / m.width)
            n.move_to(box_.get_center() + 0.24 * UP)
            d.move_to(box_.get_center() + 0.26 * DOWN)
            cards.add(VGroup(box_, n, d))
        cards.arrange(RIGHT, buff=0.28).move_to([0, -0.85, 0])
        if cards.width > 13.4:
            cards.scale(13.4 / cards.width)
        for c in cards:
            self.play(FadeIn(c, shift=0.12 * UP), run_time=0.28)
        caption(self, "実行が書いた状態を読む。モデルは一切介在しない。", hold=1.3)

        det = tag("ブラウザと CI が食い違うことはない", GREEN_HI, fs=21)
        det.move_to([0, -2.5, 0])
        self.play(FadeIn(det, scale=0.94), run_time=0.5)
        self.wait(0.8)

        self.play(FadeOut(VGroup(h4, prob4, cards, det)), run_time=0.5)

        # ---- 締め --------------------------------------------------------
        close1 = title_text("混沌が入り、", fs=40, color=DIM)
        close2 = title_text("制御され検証可能な成果が出てくる。", fs=40, color=GREEN_HI)
        close1.move_to([0, 0.55, 0])
        close2.move_to([0, -0.3, 0])
        self.play(Write(close1), run_time=0.6)
        self.play(Write(close2), run_time=0.8)
        self.wait(1.2)
        self.play(FadeOut(VGroup(close1, close2, t)), run_time=0.6)
        self.wait(0.3)

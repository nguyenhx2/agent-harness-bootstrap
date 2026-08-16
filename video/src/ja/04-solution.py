import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from manim import (
    Scene,
    Text,
    VGroup,
    RoundedRectangle,
    Line,
    FadeIn,
    FadeOut,
    Create,
    Write,
    GrowFromCenter,
    Arrow,
    Flash,
    Indicate,
    DOWN,
    UP,
    LEFT,
    RIGHT,
)
import numpy as np
from jatheme import (
    BG,
    GREEN,
    GREEN_HI,
    PURPLE,
    PURPLE_HI,
    RED,
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
    box,
    fit,
)

AMBER = "#FFBA08"

# right-hand working column (the pain column lives on the left)
RX = 2.95


def check(color=GREEN_HI, scale=1.0):
    a = Line([-0.16, 0.02, 0], [-0.04, -0.13, 0], color=color, stroke_width=6)
    b = Line([-0.04, -0.13, 0], [0.18, 0.16, 0], color=color, stroke_width=6)
    return VGroup(a, b).scale(scale)


def down_arrow(top, bottom, color=DIM):
    return Arrow(top, bottom, buff=0.12, color=color, stroke_width=3, max_tip_length_to_length_ratio=0.28)


PAINS = [
    "マージできそうに見える要件を作り出す",
    "コンテキストが圧縮され、作業が消える",
    "1回の悪いターンで.envを読み、mainにコミットする",
    "モデル指定がなく、請求額が膨らむ",
]

PW = 5.0  # pain chip width
PX = -4.3  # pain column centre x


class Solution(Scene):
    def construct(self):
        self.camera.background_color = BG
        watermark(self)

        # ============ title =============================================
        t = title_text("完全なソリューション", fs=42, color=WHITE)
        sub = Text(
            "契約書、そしてハーネス、そしてループ",
            font=JFONT,
            font_size=24,
            color=DIM,
        )
        legend = VGroup(
            tag("緑 = ハーネス・決定的", GREEN_HI, fs=19),
            tag("紫 = モデル", PURPLE_HI, fs=19),
            tag("赤 = ブロック", RED, fs=19),
        ).arrange(RIGHT, buff=0.35)
        head = VGroup(t, sub, legend).arrange(DOWN, buff=0.5)
        self.play(Write(t), run_time=0.8)
        self.play(FadeIn(sub), FadeIn(legend, lag_ratio=0.2), run_time=0.7)
        self.wait(1.1)
        self.play(FadeOut(head), run_time=0.45)

        # ============ Beat 1: the pain ==================================
        ptitle = Text(
            "実際のリポジトリに置かれたエージェント",
            font=JFONT,
            font_size=28,
            color=WHITE,
        ).move_to([0, 2.9, 0])
        self.play(FadeIn(ptitle, shift=0.12 * DOWN), run_time=0.45)

        pain_chips = VGroup(
            *[box(p, "#3A0D10", RED, w=PW, h=0.8, fs=18) for p in PAINS]
        ).arrange(DOWN, buff=0.42).move_to([0, 0.05, 0])

        marks = []
        for c in pain_chips:
            x = VGroup(
                Line([-0.14, -0.14, 0], [0.14, 0.14, 0], color=RED, stroke_width=6),
                Line([-0.14, 0.14, 0], [0.14, -0.14, 0], color=RED, stroke_width=6),
            ).next_to(c, RIGHT, buff=0.28)
            marks.append(x)
        marks = VGroup(*marks)

        for c, m in zip(pain_chips, marks):
            self.play(FadeIn(c, shift=0.14 * UP), FadeIn(m), run_time=0.38)
        caption(self, "4つの失敗が、実際のリポジトリで毎回起こる。", hold=2.0, y=-3.4, size=24)
        self.play(Indicate(marks, color=RED, scale_factor=1.35), run_time=0.7)
        caption(self, "もっともらしい作り話、失われた作業、危険なターン、押し付けられた請求。", hold=1.6, y=-3.4, size=22)

        # dock the pain list to the left column
        self.play(FadeOut(ptitle), run_time=0.3)
        self.play(
            pain_chips.animate.move_to([PX, 0.75, 0]),
            marks.animate.shift(np.array([PX, 0.7, 0])),
            run_time=0.7,
        )
        col_head = Text("課題", font=JFONT, font_size=22, color=DIM).next_to(
            pain_chips, UP, buff=0.35
        )
        self.play(FadeIn(col_head), run_time=0.3)

        def resolve(i):
            """flip pain i from red to green + tick."""
            c = pain_chips[i]
            tick = check(GREEN_HI).move_to(marks[i].get_center())
            return [
                c[0].animate.set_fill("#0E2E22").set_stroke(GREEN_HI),
                c[1].animate.set_color(GREEN_HI),
                FadeOut(marks[i]),
                FadeIn(tick),
            ], tick

        # ============ Beat 2: spec-builder writes the contract ==========
        raw = box("アイデア / メモ / 書き起こし / 旧ドキュメント", NEUTRAL, DIM, w=6.6, h=0.72, fs=18)
        sb = box("spec-builder", PURPLE, PURPLE_HI, w=4.0, h=0.82, fs=24)
        specs = box("docs/specs/  -  選択式セクション", NEUTRAL, WHITE, w=5.6, h=0.82, fs=20)
        stack = VGroup(raw, sb, specs).arrange(DOWN, buff=0.72).move_to([RX, 1.35, 0])
        a1 = down_arrow(raw.get_bottom(), sb.get_top())
        a2 = down_arrow(sb.get_bottom(), specs.get_top())

        notes = VGroup(
            Text("安定したFR ID + 受け入れ基準", font=JFONT, font_size=18, color=BLUE_HI),
            Text("要件を勝手に作らない:", font=JFONT, font_size=18, color=DIM),
            Text("未記載 -> AS-nn 前提 / OI-nn 未解決の課題", font=JFONT, font_size=18, color=AMBER),
        ).arrange(DOWN, buff=0.22).next_to(specs, DOWN, buff=0.4)
        for n in notes:
            fit(n, 6.6)

        self.play(GrowFromCenter(raw), run_time=0.4)
        caption(self, "ステップ1: spec-builderが生の入力を契約書に変える。", hold=0.9, y=-3.4, size=23)
        self.play(Create(a1), GrowFromCenter(sb), run_time=0.5)
        self.play(Create(a2), GrowFromCenter(specs), run_time=0.5)
        self.play(FadeIn(notes[0], shift=0.1 * UP), run_time=0.4)
        self.play(FadeIn(notes[1]), FadeIn(notes[2], shift=0.1 * UP), run_time=0.5)
        caption(self, "決して作らない: 書かれていないことは推測ではなくフラグが立つ。", hold=2.1, y=-3.4, size=23)

        anims, tick0 = resolve(0)
        self.play(*anims, run_time=0.7)
        caption(self, "課題1解決 - もっともらしい作り話はもうない。", hold=1.2, y=-3.4, size=24)

        beat2 = VGroup(stack, a1, a2, notes)
        self.play(FadeOut(beat2), run_time=0.5)

        # ============ Beat 3: harness-bootstrap builds the harness ======
        hb = box("harness-bootstrap", PURPLE, PURPLE_HI, w=4.6, h=0.82, fs=24).move_to([RX, 2.75, 0])
        reads = box("まずあなたのコードを読む", PURPLE, PURPLE_HI, w=4.6, h=0.66, fs=17).move_to([RX, 1.72, 0])
        a3 = down_arrow(hb.get_bottom(), reads.get_top())

        claude = Text(".claude/", font=JFONT, font_size=24, color=GREEN_HI).move_to([RX, 0.86, 0])
        a4 = down_arrow(reads.get_bottom(), claude.get_top())

        grid = VGroup(
            box("エージェント16\nmodel + effort", GREEN, GREEN_HI, w=3.2, h=0.9, fs=17),
            box("ルール16\n常時7、スコープ9", GREEN, GREEN_HI, w=3.2, h=0.9, fs=17),
            box("コマンド22", GREEN, GREEN_HI, w=3.2, h=0.9, fs=18),
            box("フック10", GREEN, GREEN_HI, w=3.2, h=0.9, fs=17),
        ).arrange_in_grid(rows=2, cols=2, buff=(0.3, 0.3)).move_to([RX, -0.35, 0])

        board = box("docs/tasks/  -  クラッシュを生き延びるボード", NEUTRAL, WHITE, w=6.8, h=0.7, fs=17).move_to(
            [RX, -2.0, 0]
        )
        foot = VGroup(
            Text("スキャフォルド: 約0.2秒", font=JFONT, font_size=18, color=GREEN_HI),
            Text("突き合わせる、決して上書きしない", font=JFONT, font_size=18, color=DIM),
        ).arrange(RIGHT, buff=0.5).move_to([RX, -2.8, 0])

        self.play(GrowFromCenter(hb), run_time=0.4)
        caption(self, "ステップ2: harness-bootstrapがコードを読み、ハーネスを構築する。", hold=0.9, y=-3.4, size=22)
        self.play(Create(a3), GrowFromCenter(reads), run_time=0.5)
        self.play(Create(a4), FadeIn(claude, shift=0.1 * DOWN), run_time=0.45)
        self.play(FadeIn(grid, lag_ratio=0.3, shift=0.12 * UP), run_time=0.9)
        self.play(FadeIn(board, shift=0.1 * UP), run_time=0.45)
        self.play(FadeIn(foot), run_time=0.4)
        caption(self, "全エージェントに明示的なモデル。フックがブロックする。ボードはディスク上。", hold=2.4, y=-3.4, size=22)

        a2b, tick1 = resolve(1)
        a2c, tick2 = resolve(2)
        a2d, tick3 = resolve(3)
        self.play(*a2b, run_time=0.5)
        self.play(*a2c, run_time=0.5)
        self.play(*a2d, run_time=0.5)
        caption(self, "課題2・3・4解決 - 善意ではなく構造によって。", hold=1.6, y=-3.4, size=23)

        beat3 = VGroup(hb, reads, a3, claude, a4, grid, board, foot)
        ticks = VGroup(tick0, tick1, tick2, tick3)
        self.play(
            FadeOut(beat3),
            FadeOut(pain_chips),
            FadeOut(ticks),
            FadeOut(col_head),
            run_time=0.6,
        )

        # ============ Beat 4: the delivery loop runs inside it ==========
        lhead = Text("デリバリーループがその内側で回る", font=JFONT, font_size=27, color=WHITE).move_to([0, 3.0, 0])
        self.play(FadeIn(lhead), run_time=0.4)

        orch = box("オーケストレーター", PURPLE, PURPLE_HI, w=3.6, h=0.85, fs=18).move_to([0, 1.85, 0])
        spec_ag = box("スコープを絞った専門エージェント", PURPLE, PURPLE_HI, w=4.2, h=0.85, fs=16).move_to([-3.5, 0.15, 0])
        tboard = box("docs/tasks/ ボード\nディスク上", NEUTRAL, WHITE, w=3.4, h=0.95, fs=18).move_to([3.6, 0.15, 0])
        hooks = box("フック", RED, AMBER, w=2.0, h=0.75, fs=22).move_to([-1.0, -1.85, 0])

        self.play(GrowFromCenter(orch), run_time=0.4)
        self.play(GrowFromCenter(spec_ag), GrowFromCenter(tboard), run_time=0.5)

        w1 = Arrow(orch.get_left(), spec_ag.get_top(), buff=0.18, color=DIM, stroke_width=3)
        w1l = Text("起動する", font=JFONT, font_size=17, color=DIM).move_to([-2.65, 1.25, 0])
        w2 = Arrow(spec_ag.get_right(), tboard.get_left(), buff=0.18, color=DIM, stroke_width=3)
        w2l = Text("進捗を記録する", font=JFONT, font_size=17, color=DIM).next_to(w2, UP, buff=0.12)

        self.play(Create(w1), FadeIn(w1l), run_time=0.45)
        caption(self, "オーケストレーターがボードに対しスコープを絞った専門エージェントを起動する。", hold=1.0, y=-3.4, size=21)
        self.play(Create(w2), FadeIn(w2l), run_time=0.45)
        caption(self, "ディスク上のボードが、作業中の進捗を記録する。", hold=1.1, y=-3.4, size=23)

        w3 = Arrow(spec_ag.get_bottom(), hooks.get_top(), buff=0.15, color=DIM, stroke_width=3)
        blocked = Text("ブロック", font=JFONT, font_size=22, color=AMBER).next_to(hooks, RIGHT, buff=0.35)
        note = Text("「非推奨」ではない", font=JFONT, font_size=18, color=DIM).next_to(blocked, RIGHT, buff=0.35)
        self.play(GrowFromCenter(hooks), Create(w3), run_time=0.45)
        self.play(Flash(hooks.get_center(), color=RED, flash_radius=0.9), FadeIn(blocked), FadeIn(note), run_time=0.7)
        caption(self, "フックは危険な操作をブロックする。忠告するだけではない。", hold=2.2, y=-3.4, size=23)

        loop_grp = VGroup(lhead, orch, spec_ag, tboard, hooks, w1, w1l, w2, w2l, w3, blocked, note)
        self.play(FadeOut(loop_grp), run_time=0.55)

        # ============ Beat 5: the payoff ================================
        phead = Text("成果", font=JFONT, font_size=34, color=WHITE).move_to([0, 3.05, 0])
        self.play(FadeIn(phead), run_time=0.4)

        payoff = VGroup(
            box("契約書が存在する", GREEN, GREEN_HI, w=6.4, h=0.72, fs=22),
            box("ハーネスから抜け出せない", GREEN, GREEN_HI, w=6.4, h=0.72, fs=22),
            box("状態はクラッシュを生き延びる", GREEN, GREEN_HI, w=6.4, h=0.72, fs=21),
            box("請求額は選ばれる、押し付けられない", GREEN, GREEN_HI, w=6.4, h=0.72, fs=19),
        ).arrange(DOWN, buff=0.26).move_to([0, 0.45, 0])
        for p in payoff:
            self.play(FadeIn(p, shift=0.12 * UP), run_time=0.32)
        caption(self, "契約書、強制、永続する状態、選ばれた請求額。", hold=1.2, y=-3.4, size=24)

        ev = VGroup(
            tag("ガードレール評価 89/89", GREEN_HI, fs=19),
            tag("Opus -> Haiku: バイト単位で同一の安全性", GREEN_HI, fs=19),
        ).arrange(RIGHT, buff=0.4).move_to([0, -2.05, 0])
        ports = Text(
            "シェルスクリプト + グロブルール  |  Claude Code・Cursor・Codexへ強制ごと移植",
            font=JFONT,
            font_size=19,
            color=DIM,
        ).move_to([0, -2.8, 0])
        fit(ports, 12.6)

        self.play(FadeIn(ev, lag_ratio=0.3), run_time=0.55)
        caption(self, "ガードレールはシェルスクリプトとグロブルール - だからモデルに依存しない。", hold=1.5, y=-3.4, size=21)
        self.play(FadeIn(ports), run_time=0.4)
        self.wait(1.0)
        self.play(FadeOut(VGroup(phead, payoff, ev, ports)), run_time=0.6)

        # ============ Beat 5b: verify it is actually wired right ========
        vhead = Text("正しく配線されているとどう分かるか", font=JFONT, font_size=26, color=WHITE).move_to([0, 3.0, 0])
        self.play(FadeIn(vhead), run_time=0.4)

        hv = box("harness-view", GREEN, GREEN_HI, w=3.6, h=0.82, fs=23).move_to([-3.0, 1.3, 0])
        hv_desc = Text(
            "「.claude/」を読み込み、\nつながりを可視化、モデル不要",
            font=JFONT, font_size=16, color=DIM, line_spacing=0.8,
        ).next_to(hv, DOWN, buff=0.25)

        assess = box("assess", GREEN, GREEN_HI, w=2.6, h=0.82, fs=23).move_to([3.0, 1.3, 0])
        assess_desc = Text(
            "プロジェクト自身の品質ゲートで\n採点し、直すべき点を示す",
            font=JFONT, font_size=16, color=DIM, line_spacing=0.8,
        ).next_to(assess, DOWN, buff=0.25)

        self.play(GrowFromCenter(hv), FadeIn(hv_desc), run_time=0.45)
        self.play(GrowFromCenter(assess), FadeIn(assess_desc), run_time=0.45)
        caption(self, "harness-viewは.claude/を読み込み、実際の配線を可視化する - モデルは不要。", hold=1.5, y=-3.4, size=21)

        scores = VGroup(
            tag("スキャフォルド生成: 99/100", GREEN_HI, fs=17),
            tag("手動保守: 79/100", AMBER, fs=17),
            tag("手動保守: 64/100", RED, fs=17),
        ).arrange(RIGHT, buff=0.35).move_to([0, -1.1, 0])
        self.play(FadeIn(scores, lag_ratio=0.25), run_time=0.6)
        caption(self, "実在する3つのハーネスで検証 - 低スコアの原因は毎セッション読み込まれるルールと、タスクボードが追いつけなかった改名された席。", hold=2.2, y=-3.4, size=19)

        verify_grp = VGroup(vhead, hv, hv_desc, assess, assess_desc, scores)
        self.play(FadeOut(verify_grp), run_time=0.5)

        # ============ Beat 6: brand end card ============================
        card = logo_reveal(self)
        self.wait(0.2)
        self.play(FadeOut(card), run_time=0.5)

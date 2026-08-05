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
    Arrow,
    Line,
    Flash,
    Indicate,
    Cross,
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

AMBER = "#FFBA08"


class SpecBuilder(Scene):
    def construct(self):
        self.camera.background_color = BG
        watermark(self)

        # ---- title card -----------------------------------------------
        t = title_text("spec-builder", fs=52, color=WHITE)
        rule = Text("何も作らない", font=JFONT, font_size=30, color=GREEN_HI)
        legend = VGroup(
            tag("青 = 人間", BLUE_HI, fs=19),
            tag("紫 = モデル", PURPLE_HI, fs=19),
            tag("緑 = 決定的・無料", GREEN_HI, fs=19),
            tag("赤 = フラグ", RED, fs=19),
        ).arrange(RIGHT, buff=0.3)
        grp = VGroup(t, rule, legend).arrange(DOWN, buff=0.5)
        self.play(Write(t), run_time=0.8)
        self.play(FadeIn(rule, shift=0.12 * UP), run_time=0.5)
        self.play(FadeIn(legend, lag_ratio=0.2), run_time=0.6)
        self.wait(0.9)
        self.play(FadeOut(grp), run_time=0.5)

        # ---- Beat 1: the problem --------------------------------------
        ai = chip("AI", PURPLE, PURPLE_HI, fs=26, h=0.9, w=3.0).move_to([-4.5, 1.7, 0])
        guess = Text("何を作るべきか推測する", font=JFONT, font_size=22, color=DIM).next_to(ai, DOWN, buff=0.25)
        self.play(GrowFromCenter(ai), FadeIn(guess), run_time=0.6)
        caption(self, "誰も要件を書き留めなかったので、モデルが推測する。", hold=0.8, y=-3.5, size=24)

        halluc = chip("幻覚で作られた要件", RED, AMBER, fs=22, h=0.9, w=6.0).move_to([1.9, 1.7, 0])
        a0 = Arrow(ai.get_right(), halluc.get_left(), buff=0.2, color=DIM, stroke_width=3)
        self.play(Create(a0), run_time=0.4)
        self.play(GrowFromCenter(halluc), run_time=0.5)

        chain = VGroup()
        for label in ["もっともらしく見える", "マージされる", "見積もられる", "作られる"]:
            chain.add(chip(label, NEUTRAL, DIM, fs=17, h=0.7, w=2.9))
        chain.arrange(RIGHT, buff=0.24).move_to([-0.7, -0.15, 0])
        for c in chain:
            self.play(FadeIn(c, shift=0.12 * RIGHT), run_time=0.3)
        uat = chip("UATで発覚する", RED, AMBER, fs=22, h=0.8, w=4.0).move_to([0, -1.65, 0])
        self.play(GrowFromCenter(uat), Flash(uat.get_center(), color=RED, flash_radius=1.2), run_time=0.7)
        caption(self, "もっともらしい作り話の要件はUATで初めて発覚する。それがコストだ。",
                hold=1.1, y=-3.5, size=23)
        self.play(FadeOut(VGroup(ai, guess, halluc, a0, chain, uat)), run_time=0.5)

        # ---- Beat 2: raw input ----------------------------------------
        inputs = VGroup()
        for label in ["アイデア", "議事録", "書き起こし", "既存のPRD", "旧ドキュメント", "コードベース"]:
            inputs.add(chip(label, NEUTRAL, DIM, fs=19, h=0.66, w=2.9))
        inputs.arrange_in_grid(rows=3, cols=2, buff=(0.3, 0.26)).move_to([-3.7, 0.6, 0])
        sb = chip("spec-builder", PURPLE, PURPLE_HI, fs=26, h=0.95, w=3.8).move_to([2.9, 0.6, 0])
        a1 = Arrow(inputs.get_right(), sb.get_left(), buff=0.35, color=DIM, stroke_width=3)
        raw = Text("生の入力", font=JFONT, font_size=22, color=DIM).next_to(inputs, UP, buff=0.3)

        self.play(FadeIn(raw), FadeIn(inputs, lag_ratio=0.15), run_time=0.9)
        self.play(Create(a1), GrowFromCenter(sb), run_time=0.6)
        caption(self, "生の入力が入る: アイデア、メモ、書き起こし、古いPRD、コードベース。",
                hold=1.0, y=-3.5, size=23)
        self.play(FadeOut(VGroup(raw, inputs, a1)), sb.animate.move_to([-4.6, 1.9, 0]).scale(0.85), run_time=0.7)

        # ---- Beat 3: elicit -------------------------------------------
        elicit = Text("ヒアリング: 構造は推論し、意思決定だけを尋ねる",
                      font=JFONT, font_size=23, color=WHITE).move_to([1.4, 1.9, 0])
        self.play(FadeIn(elicit), run_time=0.5)
        caption(self, "構造は推論する。人間が持つ意思決定だけを尋ねる。",
                hold=0.9, y=-3.5, size=24)

        ask_head = Text("AskUserQuestion - 最大4件ずつ",
                        font=JFONT, font_size=22, color=BLUE_HI).move_to([-3.4, 0.75, 0])
        qs = VGroup()
        for label in ["優先順位", "権限スコープ", "NFR目標値", "想定件数", "セキュリティ方針", "出力言語"]:
            qs.add(chip(label, BLUE, BLUE_HI, fs=18, h=0.62, w=3.3))
        qs.arrange_in_grid(rows=3, cols=2, buff=(0.28, 0.24)).move_to([-3.4, -0.9, 0])
        self.play(FadeIn(ask_head), run_time=0.4)
        self.play(FadeIn(qs, lag_ratio=0.18), run_time=0.8)

        unans = Text("未回答", font=JFONT, font_size=22, color=DIM).move_to([2.6, 0.75, 0])
        flags = VGroup(
            chip("AS-nn  前提", RED, AMBER, fs=19, h=0.7, w=4.2),
            chip("OI-nn  未解決の課題", RED, AMBER, fs=19, h=0.7, w=4.2),
        ).arrange(DOWN, buff=0.35).move_to([2.9, -0.6, 0])
        a2 = Arrow(qs.get_right(), flags.get_left(), buff=0.3, color=DIM, stroke_width=3)
        self.play(FadeIn(unans), Create(a2), run_time=0.5)
        self.play(FadeIn(flags, lag_ratio=0.2), run_time=0.7)
        caption(self, "未回答のまま残ったものはAS-nnかOI-nnになる。決して推測ではない。",
                hold=1.1, y=-3.5, size=23)
        self.play(FadeOut(VGroup(elicit, ask_head, qs, unans, flags, a2, sb)), run_time=0.5)

        # ---- Beat 4: confirm the FR list FIRST ------------------------
        head4 = Text("まずFR一覧を確認する", font=JFONT, font_size=32, color=WHITE).move_to([0, 2.7, 0])
        self.play(FadeIn(head4), run_time=0.5)
        rows = VGroup()
        for fr, pri in [("FR-01  申請を提出する", "Must"), ("FR-02  申請を承認する", "Must"),
                        ("FR-03  レポートを出力する", "Should"), ("FR-04  一括インポート", "Could")]:
            box = chip(fr, NEUTRAL, DIM, fs=19, h=0.62, w=4.6)
            p = tag(pri, PURPLE_HI, fs=18)
            rows.add(VGroup(box, p).arrange(RIGHT, buff=0.3))
        rows.arrange(DOWN, buff=0.24, aligned_edge=LEFT).move_to([-2.9, 0.4, 0])
        side = VGroup(
            chip("ロール一覧", NEUTRAL, DIM, fs=19, h=0.6, w=3.2),
            chip("現時点の未解決の課題", RED, AMBER, fs=16, h=0.6, w=3.2),
        ).arrange(DOWN, buff=0.3).move_to([3.6, 0.4, 0])
        self.play(FadeIn(rows, lag_ratio=0.2), run_time=1.0)
        self.play(FadeIn(side, lag_ratio=0.2), run_time=0.6)
        caption(self, "MoSCoW優先度案付きのFR、ロール一覧、現時点の未解決の課題。",
                hold=0.9, y=-3.5, size=23)

        human = chip("人間が確認し、訂正する", BLUE, BLUE_HI, fs=21, h=0.8, w=6.2).move_to([0, -1.85, 0])
        self.play(GrowFromCenter(human), run_time=0.5)
        self.play(Indicate(human, color=BLUE_HI, scale_factor=1.06), run_time=0.6)
        caption(self, "02以降の全てはこの一覧から派生する。一覧を誤れば12個のドキュメントが台無しになる。",
                hold=1.3, y=-3.5, size=21)
        self.play(FadeOut(VGroup(head4, rows, side, human)), run_time=0.5)

        # ---- Beat 5: scaffold -----------------------------------------
        sb = chip("spec-builder", PURPLE, PURPLE_HI, fs=22, h=0.8, w=3.2).move_to([-5.0, 3.1, 0])
        scaffold = chip("scripts/scaffold.py", GREEN, GREEN_HI, fs=22, h=0.85, w=4.6).move_to([-4.3, 1.95, 0])
        dry = tag("まず --dry-run", GREEN_HI, fs=18).next_to(scaffold, RIGHT, buff=0.4)
        self.play(GrowFromCenter(sb), run_time=0.4)
        a3 = Arrow(sb.get_bottom(), scaffold.get_top(), buff=0.1, color=DIM, stroke_width=3)
        self.play(Create(a3), GrowFromCenter(scaffold), FadeIn(dry), run_time=0.7)
        caption(self, "次にスクリプトが形を敷く。まずドライラン。", hold=0.7, y=-3.5, size=24)

        names = [
            "README", "01 概要", "02 ステークホルダー", "03 用語集", "04 業務フロー",
            "05 機能要件", "06 アクセス制御", "07 非機能要件", "08 データモデル",
            "09 連携", "10 UI / UX", "11 前提条件", "12 フィージビリティ", "13 改訂履歴",
        ]
        files = VGroup()
        for n in names:
            files.add(chip(n, NEUTRAL, DIM, fs=15, h=0.55, w=2.55))
        files.arrange_in_grid(rows=3, cols=5, buff=(0.22, 0.2)).move_to([0, -0.25, 0])
        specs_lbl = Text("docs/specs/  -  14ファイル", font=JFONT, font_size=22, color=DIM).move_to([3.2, 1.95, 0])
        self.play(FadeIn(specs_lbl), run_time=0.3)
        self.play(FadeIn(files, lag_ratio=0.12), run_time=1.1)
        caption(self, "14ファイル: 見出し、表、Mermaidの下書き、執筆メモ。",
                hold=0.8, y=-3.5, size=24)

        report = VGroup(
            tag("追加", GREEN_HI, fs=20),
            tag("維持", DIM, fs=20),
            tag("競合", AMBER, fs=20),
        ).arrange(RIGHT, buff=0.4).move_to([0, -2.2, 0])
        self.play(FadeIn(report, lag_ratio=0.2), run_time=0.6)
        self.play(Indicate(scaffold, color=GREEN_HI, scale_factor=1.08), run_time=0.6)
        caption(self, "決定的で無料。「競合」は既存仕様があるリポジトリのための突き合わせキュー。",
                hold=1.2, y=-3.5, size=21)
        self.play(FadeOut(VGroup(scaffold, dry, a3, report, specs_lbl, sb)), run_time=0.5)

        # ---- Beat 6: fill in order ------------------------------------
        self.play(files.animate.move_to([0, 1.45, 0]).scale(0.9), run_time=0.6)
        head6 = Text("順番に埋める - 各セクションは前のセクションに依存する",
                     font=JFONT, font_size=22, color=WHITE).move_to([0, 2.85, 0])
        self.play(FadeIn(head6), run_time=0.4)
        for i in range(14):
            files[i][0].set_fill(PURPLE, opacity=1.0)
            files[i][0].set_stroke(PURPLE_HI)
        self.play(FadeIn(files, lag_ratio=0.25, run_time=1.5))
        caption(self, "モデルはトークンを見出しの再入力ではなく中身に使う。",
                hold=0.7, y=-3.5, size=24)

        load = VGroup()
        for label, sub in [
            ("05", "観測可能なFR、アンカー付き、\nBR-nn + 否定ケース1つ"),
            ("07", "セキュリティNFR、「TBD」は禁止 -\n未決定の値はOIになる"),
            ("12", "全FRにYes / Partial / Noを付与 -\nPartialとNoにこそ価値がある"),
        ]:
            num = Text(label, font=JFONT, font_size=40, color=PURPLE_HI, weight="BOLD")
            txt = Text(sub, font=JFONT, font_size=16, color=WHITE, line_spacing=0.7)
            body = VGroup(num, txt).arrange(DOWN, buff=0.22)
            box = RoundedRectangle(width=4.2, height=2.0, corner_radius=0.14,
                                   fill_color=PURPLE, fill_opacity=0.22,
                                   stroke_color=PURPLE_HI, stroke_width=2)
            body.move_to(box.get_center())
            load.add(VGroup(box, body))
        load.arrange(RIGHT, buff=0.35).move_to([0, -0.9, 0])
        self.play(FadeIn(load, lag_ratio=0.25), run_time=1.1)
        caption(self, "3つのセクションが重みを担う: 05・07・12。", hold=1.6, y=-3.5, size=24)
        self.play(FadeOut(VGroup(head6, load, files)), run_time=0.5)

        # ---- Beat 7: traceability check -------------------------------
        head7 = Text("トレーサビリティチェック - 機械的判定、主観ではない",
                     font=JFONT, font_size=24, color=GREEN_HI).move_to([0, 2.5, 0])
        self.play(FadeIn(head7), run_time=0.5)
        checks = VGroup()
        for label in [
            "05の全FRが12に現れる - 両方の件数を数える",
            "10の全画面がFRを明記する",
            "06の全ロールが03に存在する",
            "06の全エンティティが08に存在する",
            "空欄なし、全リンクが解決する",
        ]:
            checks.add(chip(label, GREEN, GREEN_HI, fs=18, h=0.66, w=8.2))
        checks.arrange(DOWN, buff=0.26).move_to([0, -0.1, 0])
        self.play(FadeIn(checks, lag_ratio=0.25), run_time=1.2)
        caption(self, "05のFR数と12の行数を数える - 一致しなければ未完了。",
                hold=1.4, y=-3.5, size=24)
        self.play(FadeOut(VGroup(head7, checks)), run_time=0.5)

        # ---- Beat 8: nothing invented + handoff -----------------------
        head8 = title_text("何も作らない", fs=40, color=WHITE).move_to([0, 2.5, 0])
        self.play(Write(head8), run_time=0.8)
        surfaced = VGroup()
        for label in ["全てのOI", "全てのAS", "全てのPartial / No", "提案されただけの\nNFR目標値"]:
            surfaced.add(chip(label, RED, AMBER, fs=17, h=1.0, w=3.0))
        surfaced.arrange(RIGHT, buff=0.3).move_to([0, 1.0, 0])
        self.play(FadeIn(surfaced, lag_ratio=0.2), run_time=0.9)
        caption(self, "未解決のものは全て人間に提示される。丸め込まれない。",
                hold=1.0, y=-3.5, size=24)

        sb2 = chip("spec-builder", PURPLE, PURPLE_HI, fs=22, h=0.85, w=3.6).move_to([-4.2, -1.2, 0])
        contract = chip("docs/specs/", NEUTRAL, WHITE, fs=22, h=0.85, w=3.2).move_to([0, -1.2, 0])
        csub = Text("契約書が存在する", font=JFONT, font_size=19, color=GREEN_HI).next_to(contract, DOWN, buff=0.2)
        hb = chip("harness-bootstrap", PURPLE, PURPLE_HI, fs=22, h=0.85, w=4.2).move_to([4.3, -1.2, 0])
        ah1 = Arrow(sb2.get_right(), contract.get_left(), buff=0.2, color=DIM, stroke_width=3)
        ah2 = Arrow(contract.get_right(), hb.get_left(), buff=0.2, color=GREEN_HI, stroke_width=3)
        self.play(GrowFromCenter(sb2), Create(ah1), GrowFromCenter(contract), FadeIn(csub), run_time=0.8)
        self.play(Create(ah2), GrowFromCenter(hb), run_time=0.6)
        caption(self, "引き継ぎ: 契約書が存在する。次はそれを実装するハーネスをブートストラップする。",
                hold=1.0, y=-3.5, size=22)
        self.play(FadeOut(VGroup(head8, surfaced, sb2, contract, csub, hb, ah1, ah2)), run_time=0.6)

        # ---- brand end card ---------------------------------------------
        card = logo_reveal(self)
        self.wait(0.2)
        self.play(FadeOut(card), run_time=0.5)

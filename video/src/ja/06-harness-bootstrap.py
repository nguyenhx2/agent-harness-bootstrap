import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from manim import (
    Scene,
    Text,
    VGroup,
    RoundedRectangle,
    Rectangle,
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


def band(label, color, w, h=5.4, y=0.15):
    """A translucent vertical phase band behind the content."""
    r = Rectangle(
        width=w,
        height=h,
        fill_color=color,
        fill_opacity=0.14,
        stroke_color=color,
        stroke_width=2,
    )
    t = Text(label, font=JFONT, font_size=19, color=color)
    g = VGroup(r, t)
    t.next_to(r, UP, buff=0.14)
    return g


def sub(s, ref, size=18, color=DIM, buff=0.2):
    return Text(s, font=JFONT, font_size=size, color=color).next_to(ref, DOWN, buff=buff)


class HarnessBootstrap(Scene):
    def construct(self):
        self.camera.background_color = BG
        watermark(self)

        # ================= title ==========================================
        t = title_text("harness-bootstrap、最初から最後まで", fs=34, color=WHITE)
        legend = VGroup(
            tag("紫 = モデル、課金される", PURPLE_HI, fs=18),
            tag("緑 = スクリプト、無料", GREEN_HI, fs=18),
            tag("青 = あなた", BLUE_HI, fs=18),
            tag("赤 = ガードレール", RED, fs=18),
        ).arrange(RIGHT, buff=0.3)
        grp = VGroup(t, legend).arrange(DOWN, buff=0.6)
        self.play(Write(t), run_time=0.7)
        self.play(FadeIn(legend, lag_ratio=0.2), run_time=0.5)
        self.wait(0.3)
        self.play(FadeOut(grp), run_time=0.4)

        # ================= Beat 1: the problem ============================
        folder = RoundedRectangle(
            width=4.2, height=2.4, corner_radius=0.16,
            fill_color=BG, fill_opacity=1, stroke_color=DIM, stroke_width=2,
        ).move_to([0, 0.7, 0])
        fname = Text(".claude/", font=JFONT, font_size=26, color=DIM).move_to(
            folder.get_top() + DOWN * 0.42
        )
        empty = Text("空", font=JFONT, font_size=30, color=NEUTRAL).move_to(
            folder.get_center() + DOWN * 0.25
        )
        qs = VGroup(
            Text("エージェントは？", font=JFONT, font_size=20, color=DIM),
            Text("ルールは？", font=JFONT, font_size=20, color=DIM),
            Text("ガードレールは？", font=JFONT, font_size=20, color=DIM),
            Text("タスクは？", font=JFONT, font_size=20, color=DIM),
        ).arrange(RIGHT, buff=0.5).move_to([0, -1.5, 0])

        self.play(Create(folder), FadeIn(fname), run_time=0.6)
        self.play(FadeIn(empty), run_time=0.4)
        caption(self, "良いエージェント構成がどんなものかすら分からない。", hold=0.8, y=-3.35, size=24)
        self.play(FadeIn(qs, lag_ratio=0.25), run_time=0.6)
        caption(self, "エージェント・ルール・ガードレール・タスクがどう噛み合うかの標準がない - 空の.claude/を手で埋めるのは答えにならない。", hold=1.2, y=-3.35, size=20)
        self.play(FadeOut(VGroup(folder, fname, empty, qs)), run_time=0.4)

        # ================= Beat 2: mode first =============================
        head = Text("まずモードを選ぶ - 規模の話ではない", font=JFONT, font_size=28, color=BLUE_HI).move_to([0, 2.35, 0])
        gf = chip("greenfield", BLUE, BLUE_HI, fs=24, h=0.85, w=4.0).move_to([-4.5, 0.85, 0])
        bf = chip("brownfield", BLUE, BLUE_HI, fs=24, h=0.85, w=4.0).move_to([0, 0.85, 0])
        au = chip("audit", BLUE, BLUE_HI, fs=24, h=0.85, w=4.0).move_to([4.5, 0.85, 0])
        gs = sub("空、またはほぼ空のリポジトリ", gf, size=17)
        bs = sub("既存のコードがあり、\nエージェントが変更する", bf, size=17)
        aus = sub("エージェントが分析し、\n人間が全ての修正を適用する", au, size=17)

        self.play(FadeIn(head), run_time=0.4)
        self.play(GrowFromCenter(gf), GrowFromCenter(bf), GrowFromCenter(au), run_time=0.6)
        self.play(FadeIn(VGroup(gs, bs, aus)), run_time=0.5)
        caption(self, "Greenfield、brownfield、audit - 何よりも先にモードを選ぶ。", hold=1.0, y=-3.35, size=23)
        self.play(Indicate(au, color=BLUE_HI, scale_factor=1.1), run_time=0.6)
        caption(self, "エージェントがソースを一切変更しないなら、コード量に関わらずモードはaudit。", hold=1.2, y=-3.35, size=22)
        self.play(FadeOut(VGroup(head, gf, bf, au, gs, bs, aus)), run_time=0.4)

        # ================= Beat 3: analysis + inventory report ============
        b1 = band("紫 - モデルが必要", PURPLE_HI, w=13.6, h=5.6, y=0.1).move_to([0, 0.1, 0])
        self.play(FadeIn(b1), run_time=0.5)

        an = chip("コードベース分析 - 必須", PURPLE, PURPLE_HI, fs=21, h=0.85, w=6.4).move_to([-3.4, 1.9, 0])
        ans = Text(
            "スタック、モジュール、データ層、連携先、\n規約、危険な操作、既存の.claude/、gitの実態",
            font=JFONT, font_size=16, color=DIM, line_spacing=0.8,
        ).next_to(an, DOWN, buff=0.22)
        self.play(GrowFromCenter(an), FadeIn(ans), run_time=0.6)

        inv = chip("棚卸しレポート", NEUTRAL, WHITE, fs=22, h=0.85, w=4.2).move_to([3.4, 1.9, 0])
        a_inv = Arrow(an.get_right(), inv.get_left(), buff=0.15, color=DIM, stroke_width=3)
        maps = VGroup(
            Text("モジュール -> 開発エージェント", font=JFONT, font_size=17, color=WHITE),
            Text("規約 -> ルール", font=JFONT, font_size=17, color=WHITE),
            Text("危険な操作 -> 拒否リスト + フック", font=JFONT, font_size=17, color=WHITE),
        ).arrange(DOWN, buff=0.18, aligned_edge=LEFT).next_to(inv, DOWN, buff=0.3)
        self.play(Create(a_inv), GrowFromCenter(inv), run_time=0.5)
        self.play(FadeIn(maps, lag_ratio=0.3), run_time=0.6)
        caption(self, "brownfieldとaudit: 分析は必須で、棚卸しレポートを生む - 汎用テンプレートではなく対応表。", hold=1.4, y=-3.35, size=19)

        conf = chip("あなたが確認・訂正する", BLUE, BLUE_HI, fs=20, h=0.8, w=5.2).move_to([0, -1.4, 0])
        a_conf = Arrow(maps.get_bottom() + DOWN * 0.1, conf.get_right() + RIGHT * 0.1, buff=0.15, color=DIM, stroke_width=3)
        gate_t = Text("確認される前は1つもファイルを生成しない", font=JFONT, font_size=18, color=AMBER).next_to(conf, DOWN, buff=0.3)
        self.play(Create(a_conf), GrowFromCenter(conf), run_time=0.6)
        self.play(FadeIn(gate_t), run_time=0.35)
        caption(self, "全てをゲートする - 訂正は分析結果より優先される。", hold=1.1, y=-3.35, size=23)
        self.play(FadeOut(VGroup(an, ans, inv, a_inv, maps, conf, a_conf, gate_t)), run_time=0.4)

        # ================= Beat 4: intake + tools + plan ==================
        intake = chip("インテイク質問", PURPLE, PURPLE_HI, fs=22, h=0.8, w=4.6).move_to([-4.5, 1.7, 0])
        its = Text(
            "AskUserQuestion、1回最大4問。\nBrownfieldは根拠から事前入力し、\nコードで判断できないことだけ尋ねる",
            font=JFONT, font_size=15, color=DIM, line_spacing=0.8,
        ).next_to(intake, DOWN, buff=0.22)
        tools = chip("ツールを検出・確認", PURPLE, PURPLE_HI, fs=22, h=0.8, w=4.6).move_to([0.3, 1.7, 0])
        tts = Text(
            ".cursor/ .codex/ AGENTS.mdを走査し尋ねる:\nClaude Code / Cursor / Codex",
            font=JFONT, font_size=15, color=DIM, line_spacing=0.8,
        ).next_to(tools, DOWN, buff=0.22)
        plan = chip("1画面のセットアップ計画", BLUE, BLUE_HI, fs=19, h=0.8, w=4.5).move_to([4.6, 1.7, 0])
        ps = Text(
            "作成 / 維持 / 変更、\nmodel + effort付きロースター。\nあなたが確認する",
            font=JFONT, font_size=15, color=BLUE_HI, line_spacing=0.8,
        ).next_to(plan, DOWN, buff=0.22)
        ar1 = Arrow(intake.get_right(), tools.get_left(), buff=0.12, color=DIM, stroke_width=3)
        ar2 = Arrow(tools.get_right(), plan.get_left(), buff=0.12, color=DIM, stroke_width=3)

        self.play(GrowFromCenter(intake), FadeIn(its), run_time=0.5)
        caption(self, "インテイクはコードで判断できないことだけを尋ねる - 1回最大4問。", hold=0.8, y=-3.35, size=22)
        self.play(Create(ar1), GrowFromCenter(tools), FadeIn(tts), run_time=0.5)
        self.play(Create(ar2), GrowFromCenter(plan), FadeIn(ps), run_time=0.5)
        caption(self, "対象ツールを検出・確認した後、1つのセットアップ計画をあなたが確認する。", hold=1.0, y=-3.35, size=22)
        self.play(FadeOut(VGroup(intake, its, tools, tts, plan, ps, ar1, ar2)), run_time=0.4)

        # ================= Beat 5: roster + skills + OS + vars.json =======
        roster = chip("ロースター", PURPLE, PURPLE_HI, fs=19, h=0.8, w=3.05).move_to([-5.05, 1.7, 0])
        rs = Text(
            "Tier 0は無条件、\nプリセットS / M / L、明示的な\nmodel: と effort:",
            font=JFONT, font_size=14, color=DIM, line_spacing=0.75,
        ).next_to(roster, DOWN, buff=0.2)
        skills = chip("スキル: 適合・審査・配線", PURPLE, PURPLE_HI, fs=18, h=0.8, w=3.6).move_to([-1.55, 1.7, 0])
        sks = Text(
            "検出したスタックに合わせ、\n提案前に必ずレビューし、\n選んだら配線される",
            font=JFONT, font_size=14, color=DIM, line_spacing=0.75,
        ).next_to(skills, DOWN, buff=0.2)
        osd = chip("開発OSを検出", PURPLE, PURPLE_HI, fs=18, h=0.8, w=3.3).move_to([1.9, 1.7, 0])
        oss = Text(
            "Windowsは.ps1へ、\nmacOS/Linuxは.shへ",
            font=JFONT, font_size=15, color=DIM, line_spacing=0.75,
        ).next_to(osd, DOWN, buff=0.2)
        vj = chip("vars.json", NEUTRAL, WHITE, fs=21, h=0.8, w=2.8).move_to([5.15, 1.7, 0])
        vjs = Text(
            "vars + flags: ui, db, ai,\naudit, tdd, ddd, deploy_ask,\nwindows / posix",
            font=JFONT, font_size=14, color=DIM, line_spacing=0.75,
        ).next_to(vj, DOWN, buff=0.2)
        br1 = Arrow(roster.get_right(), skills.get_left(), buff=0.1, color=DIM, stroke_width=3)
        br2 = Arrow(skills.get_right(), osd.get_left(), buff=0.1, color=DIM, stroke_width=3)
        br3 = Arrow(osd.get_right(), vj.get_left(), buff=0.1, color=DIM, stroke_width=3)

        self.play(GrowFromCenter(roster), FadeIn(rs), run_time=0.5)
        caption(self, "全エージェントに明示的なmodelとeffort - Tier 0は無条件、その後プリセット。", hold=0.8, y=-3.35, size=21)
        self.play(Create(br1), GrowFromCenter(skills), FadeIn(sks), run_time=0.5)
        caption(self, "スキルはスタックに合わせて絞り込み、全文レビューした上で、選んだものだけ配線される。", hold=1.1, y=-3.35, size=19)
        self.play(Create(br2), GrowFromCenter(osd), FadeIn(oss), run_time=0.5)
        self.play(Create(br3), GrowFromCenter(vj), FadeIn(vjs), run_time=0.5)
        caption(self, "決定事項はvars.jsonに入る - 方法論も含む: 既定はDDD、他にTDD、TDD+DDD、Lightweightも選べる。", hold=1.5, y=-3.35, size=20)
        self.play(FadeOut(VGroup(roster, rs, skills, sks, osd, oss, vj, vjs, br1, br2, br3, b1)), run_time=0.4)

        # ================= Beat 6: scaffold (GREEN) =======================
        b2 = band("緑 - スクリプト、決定的で無料", GREEN_HI, w=13.6, h=5.6).move_to([0, 0.1, 0])
        self.play(FadeIn(b2), run_time=0.5)

        dry = chip("scaffold.py --dry-run", GREEN, GREEN_HI, fs=20, h=0.8, w=4.6).move_to([-4.4, 2.05, 0])
        sc = chip("scaffold.py", GREEN, GREEN_HI, fs=22, h=0.8, w=3.4).move_to([0.6, 2.05, 0])
        scs = sub("assets/の決定的なコピー", sc, size=17)
        sa1 = Arrow(dry.get_right(), sc.get_left(), buff=0.12, color=DIM, stroke_width=3)
        self.play(GrowFromCenter(dry), run_time=0.4)
        self.play(Create(sa1), GrowFromCenter(sc), FadeIn(scs), run_time=0.5)
        caption(self, "次にスクリプトが一括コピーを行う - 決定的で、無料。", hold=0.7, y=-3.35, size=23)

        added = chip("追加", NEUTRAL, WHITE, fs=22, h=0.7, w=2.6).move_to([-4.4, 0.35, 0])
        kept = chip("維持", NEUTRAL, WHITE, fs=22, h=0.7, w=2.6).move_to([-1.4, 0.35, 0])
        confl = chip("競合", NEUTRAL, AMBER, fs=22, h=0.7, w=2.9).move_to([1.75, 0.35, 0])
        adds = sub("ファイルが存在しなかった", added, size=15)
        keps = sub("存在し、バイト単位で同一", kept, size=15)
        cons = sub("存在し内容が異なる -\n書き込まない", confl, size=15, color=AMBER)
        for c in (added, kept, confl):
            c.shift(DOWN * 0.0)
        self.play(FadeIn(VGroup(added, adds), shift=0.1 * UP), run_time=0.35)
        self.play(FadeIn(VGroup(kept, keps), shift=0.1 * UP), run_time=0.35)
        self.play(FadeIn(VGroup(confl, cons), shift=0.1 * UP), run_time=0.35)
        self.wait(0.7)

        rec = chip("手で突き合わせる: 維持 / 適応 / 追加 / フラグ", GREEN, GREEN_HI, fs=18, h=0.8, w=8.2).move_to([0.0, -1.95, 0])
        ra = Arrow(confl.get_bottom() + DOWN * 0.9, rec.get_top() + RIGHT * 1.7, buff=0.12, color=AMBER, stroke_width=3)
        exit0 = Text("exit 0", font=JFONT, font_size=20, color=GREEN_HI).next_to(rec, RIGHT, buff=0.35)
        self.play(Create(ra), GrowFromCenter(rec), FadeIn(exit0), run_time=0.6)
        caption(self, "「競合」は失敗ではなくキュー - スキップし、表示し、exit 0で、あなたが書いたものを決して上書きしない。", hold=1.6, y=-3.35, size=19)

        self.play(FadeOut(VGroup(added, adds, kept, keps, confl, cons, rec, ra, exit0)), run_time=0.45)

        # unresolved var = the only exit 1
        badvar = chip("未解決の  {{ VAR }}", RED, AMBER, fs=22, h=0.85, w=5.4).move_to([-2.2, -0.6, 0])
        e1 = chip("exit 1", RED, AMBER, fs=24, h=0.85, w=2.4).move_to([2.4, -0.6, 0])
        ea = Arrow(badvar.get_right(), e1.get_left(), buff=0.15, color=AMBER, stroke_width=3)
        why = Text(
            "プレースホルダーが本番のルールファイルに紛れ込むと、何にも一致せず静かに失敗する",
            font=JFONT, font_size=17, color=DIM,
        ).move_to([0, -2.0, 0])
        self.play(GrowFromCenter(badvar), run_time=0.4)
        self.play(Create(ea), GrowFromCenter(e1), run_time=0.45)
        self.play(Flash(e1.get_center(), color=RED, flash_radius=1.0), FadeIn(why), run_time=0.6)
        caption(self, "exit 1になるのは未解決のプレースホルダーだけ - しかも意図的に大きく失敗する。", hold=1.2, y=-3.35, size=22)
        self.play(FadeOut(VGroup(dry, sc, scs, sa1, badvar, e1, ea, why, b2)), run_time=0.4)

        # ================= Beat 7: gap-fill + wiring (PURPLE again) =======
        b3 = band("紫、再び - テンプレートには分からないこと", PURPLE_HI, w=13.6, h=5.6).move_to([0, 0.1, 0])
        self.play(FadeIn(b3), run_time=0.5)

        gap = chip("モデルが埋める空白", PURPLE, PURPLE_HI, fs=21, h=0.8, w=5.4).move_to([-3.5, 1.85, 0])
        gaps = Text(
            "オーケストレーターのルーティング表、開発エージェントのスコープ、\ntech-stack.md、coding-standards.md、git-workflow.md、\n実際のスタック向けsettings.jsonのallow / deny、.env.example",
            font=JFONT, font_size=15, color=DIM, line_spacing=0.85,
        ).next_to(gap, DOWN, buff=0.24)
        wire = chip("オーケストレーションの配線", PURPLE, PURPLE_HI, fs=19, h=0.8, w=5.4).move_to([3.6, -0.9, 0])
        wires = Text(
            "マスタープランの索引表、\n分析のギャップ一覧から種をまくPhase 1、\nAGENTS.mdのエントリーポイント、\n薄い@AGENTS.mdインポートとしてのCLAUDE.md",
            font=JFONT, font_size=15, color=DIM, line_spacing=0.85,
        ).next_to(wire, DOWN, buff=0.24)
        wa = Arrow(gaps.get_bottom() + DOWN * 0.05, wire.get_top() + LEFT * 0.2, buff=0.2, color=DIM, stroke_width=3)

        self.play(GrowFromCenter(gap), FadeIn(gaps), run_time=0.6)
        caption(self, "ルーティング表、各エージェントのスコープ、実際の拒否コマンド - テンプレートはこれらを知らない。", hold=1.3, y=-3.35, size=19)
        self.play(Create(wa), GrowFromCenter(wire), FadeIn(wires), run_time=0.6)
        caption(self, "その後モデルがオーケストレーションを配線し、分析のギャップからPhase 1の種をまく。", hold=1.1, y=-3.35, size=21)
        self.play(FadeOut(VGroup(gap, gaps, wire, wires, wa, b3)), run_time=0.4)

        # ================= Beat 8: gate -> smoke -> graphs -> port -> done =
        gate = chip("品質ゲート", RED, AMBER, fs=19, h=0.85, w=2.9).move_to([-5.35, 1.6, 0])
        gs2 = Text(
            "構造 / コスト /\n安全性 / 裏付け /\n引き継ぎ",
            font=JFONT, font_size=14, color=DIM, line_spacing=0.8,
        ).next_to(gate, DOWN, buff=0.22)
        smoke = chip("ループをスモークテスト", GREEN, GREEN_HI, fs=15, h=0.85, w=3.1).move_to([-1.95, 1.6, 0])
        graphs = chip("両方のグラフを構築", GREEN, GREEN_HI, fs=16, h=0.85, w=3.1).move_to([1.4, 1.6, 0])
        gr2 = Text(
            "code-graph.py + docs-graph.py、\nその後 graph-html.py:\nharness-graph.html + specs-graph.html",
            font=JFONT, font_size=13, color=DIM, line_spacing=0.8,
        ).next_to(graphs, DOWN, buff=0.22)
        port = chip("あなたのツールへ移植", GREEN, GREEN_HI, fs=16, h=0.85, w=3.1).move_to([4.85, 1.6, 0])
        pa1 = Arrow(gate.get_right(), smoke.get_left(), buff=0.1, color=DIM, stroke_width=3)
        pa2 = Arrow(smoke.get_right(), graphs.get_left(), buff=0.1, color=DIM, stroke_width=3)
        pa3 = Arrow(graphs.get_right(), port.get_left(), buff=0.1, color=DIM, stroke_width=3)
        allg = Text("全て green", font=JFONT, font_size=15, color=GREEN_HI).next_to(pa1, UP, buff=0.35)

        self.play(GrowFromCenter(gate), FadeIn(gs2), run_time=0.5)
        caption(self, "品質ゲートが構造・コスト・安全性・裏付け・引き継ぎを確認する。", hold=0.8, y=-3.35, size=22)
        self.play(Create(pa1), FadeIn(allg), GrowFromCenter(smoke), run_time=0.5)
        caption(self, "全てgreen: ループを最初から最後までスモークテストする - 実際のタスク、セッションログの1行、/task-resume。", hold=0.9, y=-3.35, size=18)
        self.play(Create(pa2), GrowFromCenter(graphs), FadeIn(gr2), run_time=0.5)
        caption(self, "その後両方のナレッジグラフを構築し、インタラクティブHTMLとして書き出す - コード依存関係とドキュメントのトレーサビリティ。", hold=1.3, y=-3.35, size=17)
        self.play(Create(pa3), GrowFromCenter(port), run_time=0.5)
        caption(self, "最後に選択したツールへ移植する。", hold=0.9, y=-3.35, size=23)

        done = chip("ハーネスがオーケストレーションの下で動く", GREEN, GREEN_HI, fs=21, h=1.0, w=7.9).move_to([1.9, -1.1, 0])
        da = Arrow([4.85, 1.175, 0], [4.85, -0.6, 0], buff=0.14, color=GREEN_HI, stroke_width=3)
        self.play(Create(da), GrowFromCenter(done), run_time=0.6)
        self.play(Indicate(done, color=GREEN_HI, scale_factor=1.06), run_time=0.7)
        self.wait(0.4)
        self.play(FadeOut(VGroup(gate, gs2, smoke, graphs, gr2, port, pa1, pa2, pa3, allg, done, da)), run_time=0.4)

        # ================= Beat 9: three-band recap =======================
        rb1 = band("分析 + 決定", PURPLE_HI, w=4.3, h=2.4).move_to([-4.7, 0.2, 0])
        rb2 = band("スキャフォルド", GREEN_HI, w=4.3, h=2.4).move_to([0, 0.2, 0])
        rb3 = band("空白埋め + 配線", PURPLE_HI, w=4.3, h=2.4).move_to([4.7, 0.2, 0])
        l1 = Text("モデルが必要", font=JFONT, font_size=20, color=PURPLE_HI).move_to([-4.7, 0.2, 0])
        l2 = Text("スクリプト、無料", font=JFONT, font_size=20, color=GREEN_HI).move_to([0, 0.2, 0])
        l3 = Text("テンプレートが知らないこと", font=JFONT, font_size=18, color=PURPLE_HI).move_to([4.7, 0.2, 0])
        rh = Text("3つの帯として読む", font=JFONT, font_size=30, color=WHITE).move_to([0, 2.5, 0])
        ra1 = Arrow([-2.5, 0.2, 0], [-2.2, 0.2, 0], buff=0, color=DIM, stroke_width=3)
        ra2 = Arrow([2.2, 0.2, 0], [2.5, 0.2, 0], buff=0, color=DIM, stroke_width=3)

        self.play(FadeIn(rh), run_time=0.4)
        self.play(FadeIn(rb1), FadeIn(l1), run_time=0.45)
        self.play(Create(ra1), FadeIn(rb2), FadeIn(l2), run_time=0.45)
        self.play(Create(ra2), FadeIn(rb3), FadeIn(l3), run_time=0.45)
        caption(self, "紫から緑、また紫へ - スクリプトが答えを知り得ない箇所でだけモデルに払う。", hold=0.7, y=-3.35, size=21)
        self.play(FadeOut(VGroup(rh, rb1, rb2, rb3, l1, l2, l3, ra1, ra2)), run_time=0.5)

        # ================= brand end card =================================
        card = logo_reveal(self)
        self.wait(0.2)
        self.play(FadeOut(card), run_time=0.5)

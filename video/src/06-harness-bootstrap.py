import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    t = Text(label, font=FONT, font_size=20, color=color)
    g = VGroup(r, t)
    t.next_to(r, UP, buff=0.14)
    return g


def sub(s, ref, size=19, color=DIM, buff=0.2):
    return Text(s, font=FONT, font_size=size, color=color).next_to(ref, DOWN, buff=buff)


class HarnessBootstrap(Scene):
    def construct(self):
        self.camera.background_color = BG

        # ================= title ==========================================
        t = title_text("harness-bootstrap, end to end", fs=44, color=WHITE)
        legend = VGroup(
            tag("purple = the model, billed", PURPLE_HI, fs=19),
            tag("green = script, free", GREEN_HI, fs=19),
            tag("blue = you", BLUE_HI, fs=19),
            tag("red = guardrail", RED, fs=19),
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
        fname = Text(".claude/", font=FONT, font_size=26, color=DIM).move_to(
            folder.get_top() + DOWN * 0.42
        )
        empty = Text("empty", font=FONT, font_size=30, color=NEUTRAL).move_to(
            folder.get_center() + DOWN * 0.25
        )
        qs = VGroup(
            Text("agents?", font=FONT, font_size=22, color=DIM),
            Text("rules?", font=FONT, font_size=22, color=DIM),
            Text("guardrails?", font=FONT, font_size=22, color=DIM),
            Text("tasks?", font=FONT, font_size=22, color=DIM),
        ).arrange(RIGHT, buff=0.7).move_to([0, -1.5, 0])

        self.play(Create(folder), FadeIn(fname), run_time=0.6)
        self.play(FadeIn(empty), run_time=0.4)
        caption(self, "You do not know what a good agent setup even looks like.", hold=0.8, y=-3.35, size=24)
        self.play(FadeIn(qs, lag_ratio=0.25), run_time=0.6)
        caption(self, "No standard for how agents, rules, guardrails and tasks fit together - and a blank .claude/ you fill in by hand is not an answer.", hold=1.2, y=-3.35, size=22)
        self.play(FadeOut(VGroup(folder, fname, empty, qs)), run_time=0.4)

        # ================= Beat 2: mode first =============================
        head = Text("Mode first - and it is not about size", font=FONT, font_size=30, color=BLUE_HI).move_to([0, 2.35, 0])
        gf = chip("greenfield", BLUE, BLUE_HI, fs=24, h=0.85, w=4.0).move_to([-4.5, 0.85, 0])
        bf = chip("brownfield", BLUE, BLUE_HI, fs=24, h=0.85, w=4.0).move_to([0, 0.85, 0])
        au = chip("audit", BLUE, BLUE_HI, fs=24, h=0.85, w=4.0).move_to([4.5, 0.85, 0])
        gs = sub("empty or near-empty repo", gf, size=19)
        bs = sub("source exists, agents\nwill modify it", bf, size=19)
        aus = sub("agents analyze, a human\napplies every fix", au, size=19)

        self.play(FadeIn(head), run_time=0.4)
        self.play(GrowFromCenter(gf), GrowFromCenter(bf), GrowFromCenter(au), run_time=0.6)
        self.play(FadeIn(VGroup(gs, bs, aus)), run_time=0.5)
        caption(self, "Greenfield, brownfield, audit - the mode is chosen before anything else.", hold=1.0, y=-3.35, size=23)
        self.play(Indicate(au, color=BLUE_HI, scale_factor=1.1), run_time=0.6)
        caption(self, "If agents never modify the source, the mode is audit however much code exists.", hold=1.2, y=-3.35, size=23)
        self.play(FadeOut(VGroup(head, gf, bf, au, gs, bs, aus)), run_time=0.4)

        # ================= Beat 3: analysis + inventory report ============
        b1 = band("PURPLE - a model is required", PURPLE_HI, w=13.6, h=5.6, y=0.1).move_to([0, 0.1, 0])
        self.play(FadeIn(b1), run_time=0.5)

        an = chip("Codebase analysis - MANDATORY", PURPLE, PURPLE_HI, fs=23, h=0.85, w=6.4).move_to([-3.4, 1.9, 0])
        ans = Text(
            "stack, modules, data layer, integrations,\nconventions, risky ops, existing .claude/, git reality",
            font=FONT, font_size=18, color=DIM, line_spacing=0.8,
        ).next_to(an, DOWN, buff=0.22)
        self.play(GrowFromCenter(an), FadeIn(ans), run_time=0.6)

        inv = chip("Inventory Report", NEUTRAL, WHITE, fs=24, h=0.85, w=4.2).move_to([3.4, 1.9, 0])
        a_inv = Arrow(an.get_right(), inv.get_left(), buff=0.15, color=DIM, stroke_width=3)
        maps = VGroup(
            Text("modules  ->  dev agents", font=FONT, font_size=19, color=WHITE),
            Text("conventions  ->  rules", font=FONT, font_size=19, color=WHITE),
            Text("risky ops  ->  deny + hooks", font=FONT, font_size=19, color=WHITE),
        ).arrange(DOWN, buff=0.18, aligned_edge=LEFT).next_to(inv, DOWN, buff=0.3)
        self.play(Create(a_inv), GrowFromCenter(inv), run_time=0.5)
        self.play(FadeIn(maps, lag_ratio=0.3), run_time=0.6)
        caption(self, "Brownfield and audit: analysis is mandatory, and it produces the Inventory Report - mapping tables, not a generic template.", hold=1.4, y=-3.35, size=22)

        conf = chip("You confirm or correct it", BLUE, BLUE_HI, fs=22, h=0.8, w=5.2).move_to([0, -1.4, 0])
        a_conf = Arrow(maps.get_bottom() + DOWN * 0.1, conf.get_right() + RIGHT * 0.1, buff=0.15, color=DIM, stroke_width=3)
        gate_t = Text("no file is generated before it is confirmed", font=FONT, font_size=20, color=AMBER).next_to(conf, DOWN, buff=0.3)
        self.play(Create(a_conf), GrowFromCenter(conf), run_time=0.6)
        self.play(FadeIn(gate_t), run_time=0.35)
        caption(self, "It gates everything - corrections override findings.", hold=1.1, y=-3.35, size=23)
        self.play(FadeOut(VGroup(an, ans, inv, a_inv, maps, conf, a_conf, gate_t)), run_time=0.4)

        # ================= Beat 4: intake + tools + plan ==================
        intake = chip("Intake questionnaire", PURPLE, PURPLE_HI, fs=22, h=0.8, w=4.6).move_to([-4.5, 1.7, 0])
        its = Text(
            "AskUserQuestion, max 4 per call.\nBrownfield pre-fills from evidence and asks\nonly what the code cannot decide",
            font=FONT, font_size=17, color=DIM, line_spacing=0.8,
        ).next_to(intake, DOWN, buff=0.22)
        tools = chip("Detect + confirm tools", PURPLE, PURPLE_HI, fs=22, h=0.8, w=4.6).move_to([0.3, 1.7, 0])
        tts = Text(
            "scan .cursor/ .codex/ AGENTS.md, then ask:\nClaude Code / Cursor / Codex",
            font=FONT, font_size=17, color=DIM, line_spacing=0.8,
        ).next_to(tools, DOWN, buff=0.22)
        plan = chip("One-screen setup plan", BLUE, BLUE_HI, fs=21, h=0.8, w=4.3).move_to([4.6, 1.7, 0])
        ps = Text(
            "created / kept / modified,\nroster with model + effort.\nYou confirm",
            font=FONT, font_size=17, color=BLUE_HI, line_spacing=0.8,
        ).next_to(plan, DOWN, buff=0.22)
        ar1 = Arrow(intake.get_right(), tools.get_left(), buff=0.12, color=DIM, stroke_width=3)
        ar2 = Arrow(tools.get_right(), plan.get_left(), buff=0.12, color=DIM, stroke_width=3)

        self.play(GrowFromCenter(intake), FadeIn(its), run_time=0.5)
        caption(self, "Intake asks only what the code cannot decide - max 4 questions per call.", hold=0.8, y=-3.35, size=23)
        self.play(Create(ar1), GrowFromCenter(tools), FadeIn(tts), run_time=0.5)
        self.play(Create(ar2), GrowFromCenter(plan), FadeIn(ps), run_time=0.5)
        caption(self, "Target tools are detected and confirmed, then you confirm one setup plan.", hold=1.0, y=-3.35, size=23)
        self.play(FadeOut(VGroup(intake, its, tools, tts, plan, ps, ar1, ar2)), run_time=0.4)

        # ================= Beat 5: roster + OS + vars.json ================
        roster = chip("Roster", PURPLE, PURPLE_HI, fs=24, h=0.8, w=3.6).move_to([-4.5, 1.7, 0])
        rs = Text(
            "Tier 0 unconditional, preset S / M / L,\nexplicit model: AND effort: on every agent",
            font=FONT, font_size=17, color=DIM, line_spacing=0.8,
        ).next_to(roster, DOWN, buff=0.22)
        osd = chip("Detect the dev OS", PURPLE, PURPLE_HI, fs=22, h=0.8, w=4.0).move_to([0.3, 1.7, 0])
        oss = Text(
            "Windows to .ps1, macOS or Linux to .sh",
            font=FONT, font_size=17, color=DIM,
        ).next_to(osd, DOWN, buff=0.22)
        vj = chip("vars.json", NEUTRAL, WHITE, fs=24, h=0.8, w=3.2).move_to([4.9, 1.7, 0])
        vjs = Text(
            "vars + flags: ui, db, ai, audit,\nexactly one of windows / posix",
            font=FONT, font_size=17, color=DIM, line_spacing=0.8,
        ).next_to(vj, DOWN, buff=0.22)
        br1 = Arrow(roster.get_right(), osd.get_left(), buff=0.12, color=DIM, stroke_width=3)
        br2 = Arrow(osd.get_right(), vj.get_left(), buff=0.12, color=DIM, stroke_width=3)

        self.play(GrowFromCenter(roster), FadeIn(rs), run_time=0.5)
        self.play(Create(br1), GrowFromCenter(osd), FadeIn(oss), run_time=0.5)
        self.play(Create(br2), GrowFromCenter(vj), FadeIn(vjs), run_time=0.5)
        caption(self, "Every agent gets an explicit model and effort - and the decisions land in vars.json.", hold=1.5, y=-3.35, size=22)
        self.play(FadeOut(VGroup(roster, rs, osd, oss, vj, vjs, br1, br2, b1)), run_time=0.4)

        # ================= Beat 6: scaffold (GREEN) =======================
        b2 = band("GREEN - a script, deterministic and free", GREEN_HI, w=13.6, h=5.6).move_to([0, 0.1, 0])
        self.play(FadeIn(b2), run_time=0.5)

        dry = chip("scaffold.py --dry-run", GREEN, GREEN_HI, fs=22, h=0.8, w=4.6).move_to([-4.4, 2.05, 0])
        sc = chip("scaffold.py", GREEN, GREEN_HI, fs=22, h=0.8, w=3.4).move_to([0.6, 2.05, 0])
        scs = sub("a deterministic copy of assets/", sc, size=18)
        sa1 = Arrow(dry.get_right(), sc.get_left(), buff=0.12, color=DIM, stroke_width=3)
        self.play(GrowFromCenter(dry), run_time=0.4)
        self.play(Create(sa1), GrowFromCenter(sc), FadeIn(scs), run_time=0.5)
        caption(self, "Then a script does the bulk copying - deterministic, and free.", hold=0.7, y=-3.35, size=23)

        added = chip("ADDED", NEUTRAL, WHITE, fs=22, h=0.7, w=2.6).move_to([-4.4, 0.35, 0])
        kept = chip("KEPT", NEUTRAL, WHITE, fs=22, h=0.7, w=2.6).move_to([-1.4, 0.35, 0])
        confl = chip("CONFLICT", NEUTRAL, AMBER, fs=22, h=0.7, w=2.9).move_to([1.75, 0.35, 0])
        adds = sub("file did not exist", added, size=17)
        keps = sub("exists, byte-identical", kept, size=17)
        cons = sub("exists and differs -\nnot written", confl, size=17, color=AMBER)
        for c in (added, kept, confl):
            c.shift(DOWN * 0.0)
        self.play(FadeIn(VGroup(added, adds), shift=0.1 * UP), run_time=0.35)
        self.play(FadeIn(VGroup(kept, keps), shift=0.1 * UP), run_time=0.35)
        self.play(FadeIn(VGroup(confl, cons), shift=0.1 * UP), run_time=0.35)
        self.wait(0.7)

        rec = chip("Reconcile by hand: keep / adapt / add / flag", GREEN, GREEN_HI, fs=21, h=0.8, w=8.2).move_to([0.0, -1.95, 0])
        ra = Arrow(confl.get_bottom() + DOWN * 0.9, rec.get_top() + RIGHT * 1.7, buff=0.12, color=AMBER, stroke_width=3)
        exit0 = Text("exits 0", font=FONT, font_size=20, color=GREEN_HI).next_to(rec, RIGHT, buff=0.35)
        self.play(Create(ra), GrowFromCenter(rec), FadeIn(exit0), run_time=0.6)
        caption(self, "CONFLICT is a queue, not a failure - it skips, prints, exits 0, and never clobbers what you wrote.", hold=1.6, y=-3.35, size=22)

        self.play(FadeOut(VGroup(added, adds, kept, keps, confl, cons, rec, ra, exit0)), run_time=0.45)

        # unresolved var = the only exit 1
        badvar = chip("unresolved  {{ VAR }}", RED, AMBER, fs=24, h=0.85, w=5.4).move_to([-2.2, -0.6, 0])
        e1 = chip("exit 1", RED, AMBER, fs=24, h=0.85, w=2.4).move_to([2.4, -0.6, 0])
        ea = Arrow(badvar.get_right(), e1.get_left(), buff=0.15, color=AMBER, stroke_width=3)
        why = Text(
            "a placeholder shipped into a live rule file matches nothing and fails silently",
            font=FONT, font_size=19, color=DIM,
        ).move_to([0, -2.0, 0])
        self.play(GrowFromCenter(badvar), run_time=0.4)
        self.play(Create(ea), GrowFromCenter(e1), run_time=0.45)
        self.play(Flash(e1.get_center(), color=RED, flash_radius=1.0), FadeIn(why), run_time=0.6)
        caption(self, "Only an unresolved placeholder exits 1 - and it fails loudly, on purpose.", hold=1.2, y=-3.35, size=23)
        self.play(FadeOut(VGroup(dry, sc, scs, sa1, badvar, e1, ea, why, b2)), run_time=0.4)

        # ================= Beat 7: gap-fill + wiring (PURPLE again) =======
        b3 = band("PURPLE again - what no template can know", PURPLE_HI, w=13.6, h=5.6).move_to([0, 0.1, 0])
        self.play(FadeIn(b3), run_time=0.5)

        gap = chip("Model-authored gap-fill", PURPLE, PURPLE_HI, fs=23, h=0.8, w=5.4).move_to([-3.5, 1.85, 0])
        gaps = Text(
            "orchestrator routing table, dev-agent scopes,\ntech-stack.md, coding-standards.md, git-workflow.md,\nsettings.json allow / deny for the real stack, .env.example",
            font=FONT, font_size=17, color=DIM, line_spacing=0.85,
        ).next_to(gap, DOWN, buff=0.24)
        wire = chip("Orchestration wiring", PURPLE, PURPLE_HI, fs=23, h=0.8, w=5.0).move_to([3.6, -0.9, 0])
        wires = Text(
            "master-plan index table,\nPhase 1 seeded from the analysis gap list,\nAGENTS.md entry point,\nCLAUDE.md as a thin @AGENTS.md import",
            font=FONT, font_size=17, color=DIM, line_spacing=0.85,
        ).next_to(wire, DOWN, buff=0.24)
        wa = Arrow(gaps.get_bottom() + DOWN * 0.05, wire.get_top() + LEFT * 0.2, buff=0.2, color=DIM, stroke_width=3)

        self.play(GrowFromCenter(gap), FadeIn(gaps), run_time=0.6)
        caption(self, "The routing table, each agent's scope, the real deny commands - no template knows these.", hold=1.3, y=-3.35, size=22)
        self.play(Create(wa), GrowFromCenter(wire), FadeIn(wires), run_time=0.6)
        caption(self, "Then the model wires orchestration and seeds Phase 1 from the analysis gaps.", hold=1.1, y=-3.35, size=23)
        self.play(FadeOut(VGroup(gap, gaps, wire, wires, wa, b3)), run_time=0.4)

        # ================= Beat 8: gate -> smoke -> port -> done ==========
        gate = chip("Quality gate", RED, AMBER, fs=24, h=0.85, w=3.6).move_to([-4.6, 1.6, 0])
        gs2 = Text(
            "structure / cost and context /\nsafety / grounding / handoff",
            font=FONT, font_size=18, color=DIM, line_spacing=0.85,
        ).next_to(gate, DOWN, buff=0.24)
        smoke = chip("Smoke-test the loop", GREEN, GREEN_HI, fs=22, h=0.85, w=4.2).move_to([0.35, 1.6, 0])
        port = chip("Port to your tools", GREEN, GREEN_HI, fs=22, h=0.85, w=3.8).move_to([4.8, 1.6, 0])
        pa1 = Arrow(gate.get_right(), smoke.get_left(), buff=0.12, color=DIM, stroke_width=3)
        pa2 = Arrow(smoke.get_right(), port.get_left(), buff=0.12, color=DIM, stroke_width=3)
        allg = Text("all green", font=FONT, font_size=18, color=GREEN_HI).next_to(pa1, UP, buff=0.22)

        self.play(GrowFromCenter(gate), FadeIn(gs2), run_time=0.5)
        caption(self, "A quality gate checks structure, cost, safety, grounding and handoff.", hold=1.0, y=-3.35, size=23)
        self.play(Create(pa1), FadeIn(allg), GrowFromCenter(smoke), run_time=0.5)
        self.play(Create(pa2), GrowFromCenter(port), run_time=0.5)
        caption(self, "All green: the loop is smoke-tested and ported to the tools you selected.", hold=1.1, y=-3.35, size=23)

        done = chip("Harness runs under orchestration", GREEN, GREEN_HI, fs=26, h=1.0, w=7.6).move_to([1.9, -1.1, 0])
        da = Arrow([4.8, 1.175, 0], [4.8, -0.6, 0], buff=0.14, color=GREEN_HI, stroke_width=3)
        self.play(Create(da), GrowFromCenter(done), run_time=0.6)
        self.play(Indicate(done, color=GREEN_HI, scale_factor=1.06), run_time=0.7)
        self.wait(0.4)
        self.play(FadeOut(VGroup(gate, gs2, smoke, port, pa1, pa2, allg, done, da)), run_time=0.4)

        # ================= Beat 9: three-band recap =======================
        rb1 = band("analyse + decide", PURPLE_HI, w=4.3, h=2.4).move_to([-4.7, 0.2, 0])
        rb2 = band("scaffold", GREEN_HI, w=4.3, h=2.4).move_to([0, 0.2, 0])
        rb3 = band("gap-fill + wire", PURPLE_HI, w=4.3, h=2.4).move_to([4.7, 0.2, 0])
        l1 = Text("a model is required", font=FONT, font_size=21, color=PURPLE_HI).move_to([-4.7, 0.2, 0])
        l2 = Text("a script, for free", font=FONT, font_size=21, color=GREEN_HI).move_to([0, 0.2, 0])
        l3 = Text("what no template knows", font=FONT, font_size=21, color=PURPLE_HI).move_to([4.7, 0.2, 0])
        rh = Text("Read it as three bands", font=FONT, font_size=32, color=WHITE).move_to([0, 2.5, 0])
        ra1 = Arrow([-2.5, 0.2, 0], [-2.2, 0.2, 0], buff=0, color=DIM, stroke_width=3)
        ra2 = Arrow([2.2, 0.2, 0], [2.5, 0.2, 0], buff=0, color=DIM, stroke_width=3)

        self.play(FadeIn(rh), run_time=0.4)
        self.play(FadeIn(rb1), FadeIn(l1), run_time=0.45)
        self.play(Create(ra1), FadeIn(rb2), FadeIn(l2), run_time=0.45)
        self.play(Create(ra2), FadeIn(rb3), FadeIn(l3), run_time=0.45)
        caption(self, "Purple to green to purple - pay the model only where a script cannot know the answer.", hold=1.1, y=-3.35, size=22)
        self.play(FadeOut(VGroup(rh, rb1, rb2, rb3, l1, l2, l3, ra1, ra2)), run_time=0.6)
        self.wait(0.2)

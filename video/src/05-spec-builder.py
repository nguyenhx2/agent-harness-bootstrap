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


class SpecBuilder(Scene):
    def construct(self):
        self.camera.background_color = BG

        # ---- title card -----------------------------------------------
        t = title_text("spec-builder", fs=52, color=WHITE)
        rule = Text("nothing is invented", font=FONT, font_size=30, color=GREEN_HI)
        legend = VGroup(
            tag("blue = the human", BLUE_HI, fs=19),
            tag("purple = the model", PURPLE_HI, fs=19),
            tag("green = deterministic / free", GREEN_HI, fs=19),
            tag("red = flagged", RED, fs=19),
        ).arrange(RIGHT, buff=0.3)
        grp = VGroup(t, rule, legend).arrange(DOWN, buff=0.5)
        self.play(Write(t), run_time=0.8)
        self.play(FadeIn(rule, shift=0.12 * UP), run_time=0.5)
        self.play(FadeIn(legend, lag_ratio=0.2), run_time=0.6)
        self.wait(0.9)
        self.play(FadeOut(grp), run_time=0.5)

        # ---- Beat 1: the problem --------------------------------------
        ai = chip("the AI", PURPLE, PURPLE_HI, fs=26, h=0.9, w=3.0).move_to([-4.5, 1.7, 0])
        guess = Text("guesses what to build", font=FONT, font_size=24, color=DIM).next_to(ai, DOWN, buff=0.25)
        self.play(GrowFromCenter(ai), FadeIn(guess), run_time=0.6)
        caption(self, "Nobody wrote the requirements down, so the model guesses.", hold=0.8, y=-3.5, size=24)

        halluc = chip("hallucinated requirement", RED, AMBER, fs=24, h=0.9, w=6.0).move_to([1.9, 1.7, 0])
        a0 = Arrow(ai.get_right(), halluc.get_left(), buff=0.2, color=DIM, stroke_width=3)
        self.play(Create(a0), run_time=0.4)
        self.play(GrowFromCenter(halluc), run_time=0.5)

        chain = VGroup()
        for label in ["looks plausible", "gets merged", "gets estimated", "gets built"]:
            chain.add(chip(label, NEUTRAL, DIM, fs=20, h=0.7, w=2.9))
        chain.arrange(RIGHT, buff=0.24).move_to([-0.7, -0.15, 0])
        for c in chain:
            self.play(FadeIn(c, shift=0.12 * RIGHT), run_time=0.3)
        uat = chip("discovered in UAT", RED, AMBER, fs=22, h=0.8, w=4.0).move_to([0, -1.65, 0])
        self.play(GrowFromCenter(uat), Flash(uat.get_center(), color=RED, flash_radius=1.2), run_time=0.7)
        caption(self, "A plausible invented requirement is only found in UAT. That is the cost.",
                hold=1.1, y=-3.5, size=24)
        self.play(FadeOut(VGroup(ai, guess, halluc, a0, chain, uat)), run_time=0.5)

        # ---- Beat 2: raw input ----------------------------------------
        inputs = VGroup()
        for label in ["an idea", "meeting notes", "a transcript", "an existing PRD", "legacy docs", "a codebase"]:
            inputs.add(chip(label, NEUTRAL, DIM, fs=20, h=0.66, w=2.9))
        inputs.arrange_in_grid(rows=3, cols=2, buff=(0.3, 0.26)).move_to([-3.7, 0.6, 0])
        sb = chip("spec-builder", PURPLE, PURPLE_HI, fs=26, h=0.95, w=3.8).move_to([2.9, 0.6, 0])
        a1 = Arrow(inputs.get_right(), sb.get_left(), buff=0.35, color=DIM, stroke_width=3)
        raw = Text("raw input", font=FONT, font_size=22, color=DIM).next_to(inputs, UP, buff=0.3)

        self.play(FadeIn(raw), FadeIn(inputs, lag_ratio=0.15), run_time=0.9)
        self.play(Create(a1), GrowFromCenter(sb), run_time=0.6)
        caption(self, "In goes the raw input: an idea, notes, a transcript, an old PRD, a codebase.",
                hold=1.0, y=-3.5, size=24)
        self.play(FadeOut(VGroup(raw, inputs, a1)), sb.animate.move_to([-4.6, 1.9, 0]).scale(0.85), run_time=0.7)

        # ---- Beat 3: elicit -------------------------------------------
        elicit = Text("Elicit: infer STRUCTURE, ask for DECISIONS",
                      font=FONT, font_size=26, color=WHITE).move_to([1.4, 1.9, 0])
        self.play(FadeIn(elicit), run_time=0.5)
        caption(self, "It infers the structure. It only asks for the decisions a human owns.",
                hold=0.9, y=-3.5, size=24)

        ask_head = Text("AskUserQuestion - batches of at most 4",
                        font=FONT, font_size=23, color=BLUE_HI).move_to([-3.4, 0.75, 0])
        qs = VGroup()
        for label in ["priorities", "permission scope", "NFR targets", "volumes", "security posture", "output language"]:
            qs.add(chip(label, BLUE, BLUE_HI, fs=19, h=0.62, w=3.3))
        qs.arrange_in_grid(rows=3, cols=2, buff=(0.28, 0.24)).move_to([-3.4, -0.9, 0])
        self.play(FadeIn(ask_head), run_time=0.4)
        self.play(FadeIn(qs, lag_ratio=0.18), run_time=0.8)

        unans = Text("unanswered", font=FONT, font_size=22, color=DIM).move_to([2.6, 0.75, 0])
        flags = VGroup(
            chip("AS-nn  assumption", RED, AMBER, fs=20, h=0.7, w=4.2),
            chip("OI-nn  open issue", RED, AMBER, fs=20, h=0.7, w=4.2),
        ).arrange(DOWN, buff=0.35).move_to([2.9, -0.6, 0])
        a2 = Arrow(qs.get_right(), flags.get_left(), buff=0.3, color=DIM, stroke_width=3)
        self.play(FadeIn(unans), Create(a2), run_time=0.5)
        self.play(FadeIn(flags, lag_ratio=0.2), run_time=0.7)
        caption(self, "Anything left unanswered becomes AS-nn or OI-nn, never a guess.",
                hold=1.1, y=-3.5, size=24)
        self.play(FadeOut(VGroup(elicit, ask_head, qs, unans, flags, a2, sb)), run_time=0.5)

        # ---- Beat 4: confirm the FR list FIRST ------------------------
        head4 = Text("Confirm the FR list FIRST", font=FONT, font_size=32, color=WHITE).move_to([0, 2.7, 0])
        self.play(FadeIn(head4), run_time=0.5)
        rows = VGroup()
        for fr, pri in [("FR-01  submit request", "Must"), ("FR-02  approve request", "Must"),
                        ("FR-03  export report", "Should"), ("FR-04  bulk import", "Could")]:
            box = chip(fr, NEUTRAL, DIM, fs=20, h=0.62, w=4.4)
            p = tag(pri, PURPLE_HI, fs=18)
            rows.add(VGroup(box, p).arrange(RIGHT, buff=0.3))
        rows.arrange(DOWN, buff=0.24, aligned_edge=LEFT).move_to([-2.9, 0.4, 0])
        side = VGroup(
            chip("the roles", NEUTRAL, DIM, fs=19, h=0.6, w=3.2),
            chip("open issues so far", RED, AMBER, fs=19, h=0.6, w=3.2),
        ).arrange(DOWN, buff=0.3).move_to([3.6, 0.4, 0])
        self.play(FadeIn(rows, lag_ratio=0.2), run_time=1.0)
        self.play(FadeIn(side, lag_ratio=0.2), run_time=0.6)
        caption(self, "FRs with proposed MoSCoW priorities, the roles, the open issues so far.",
                hold=0.9, y=-3.5, size=24)

        human = chip("the human confirms or corrects", BLUE, BLUE_HI, fs=22, h=0.8, w=6.2).move_to([0, -1.85, 0])
        self.play(GrowFromCenter(human), run_time=0.5)
        self.play(Indicate(human, color=BLUE_HI, scale_factor=1.06), run_time=0.6)
        caption(self, "Everything from 02 onward derives from this list. A wrong list costs twelve documents.",
                hold=1.3, y=-3.5, size=23)
        self.play(FadeOut(VGroup(head4, rows, side, human)), run_time=0.5)

        # ---- Beat 5: scaffold -----------------------------------------
        sb = chip("spec-builder", PURPLE, PURPLE_HI, fs=22, h=0.8, w=3.2).move_to([-5.0, 3.1, 0])
        scaffold = chip("scripts/scaffold.py", GREEN, GREEN_HI, fs=24, h=0.85, w=4.6).move_to([-4.3, 1.95, 0])
        dry = tag("--dry-run first", GREEN_HI, fs=19).next_to(scaffold, RIGHT, buff=0.4)
        self.play(GrowFromCenter(sb), run_time=0.4)
        a3 = Arrow(sb.get_bottom(), scaffold.get_top(), buff=0.1, color=DIM, stroke_width=3)
        self.play(Create(a3), GrowFromCenter(scaffold), FadeIn(dry), run_time=0.7)
        caption(self, "Then a script lays down the shape. Dry-run first.", hold=0.7, y=-3.5, size=24)

        names = [
            "README", "01 overview", "02 stakeholders", "03 glossary", "04 business flows",
            "05 functional reqs", "06 access control", "07 non-functional", "08 data model",
            "09 integration", "10 UI / UX", "11 assumptions", "12 feasibility", "13 revisions",
        ]
        files = VGroup()
        for n in names:
            files.add(chip(n, NEUTRAL, DIM, fs=17, h=0.55, w=2.55))
        files.arrange_in_grid(rows=3, cols=5, buff=(0.22, 0.2)).move_to([0, -0.25, 0])
        specs_lbl = Text("docs/specs/  -  14 files", font=FONT, font_size=22, color=DIM).move_to([3.2, 1.95, 0])
        self.play(FadeIn(specs_lbl), run_time=0.3)
        self.play(FadeIn(files, lag_ratio=0.12), run_time=1.1)
        caption(self, "14 files: headings, tables, Mermaid scaffolds, inline authoring notes.",
                hold=0.8, y=-3.5, size=24)

        report = VGroup(
            tag("ADDED", GREEN_HI, fs=20),
            tag("KEPT", DIM, fs=20),
            tag("CONFLICT", AMBER, fs=20),
        ).arrange(RIGHT, buff=0.4).move_to([0, -2.2, 0])
        self.play(FadeIn(report, lag_ratio=0.2), run_time=0.6)
        self.play(Indicate(scaffold, color=GREEN_HI, scale_factor=1.08), run_time=0.6)
        caption(self, "Deterministic and free. CONFLICT is the reconciliation queue for a repo with specs.",
                hold=1.2, y=-3.5, size=23)
        self.play(FadeOut(VGroup(scaffold, dry, a3, report, specs_lbl, sb)), run_time=0.5)

        # ---- Beat 6: fill in order ------------------------------------
        self.play(files.animate.move_to([0, 1.45, 0]).scale(0.9), run_time=0.6)
        head6 = Text("Fill in order - each section depends on the last",
                     font=FONT, font_size=26, color=WHITE).move_to([0, 2.85, 0])
        self.play(FadeIn(head6), run_time=0.4)
        for i in range(14):
            files[i][0].set_fill(PURPLE, opacity=1.0)
            files[i][0].set_stroke(PURPLE_HI)
        self.play(FadeIn(files, lag_ratio=0.25, run_time=1.5))
        caption(self, "The model spends its tokens on content, not on retyping headings.",
                hold=0.7, y=-3.5, size=24)

        load = VGroup()
        for label, sub in [
            ("05", "observable FRs, anchored,\nBR-nn + a NEGATIVE case"),
            ("07", "security NFRs, never \"TBD\" -\nan undecided value is an OI"),
            ("12", "every FR gets Yes / Partial / No -\nPartial and No are the value"),
        ]:
            num = Text(label, font=FONT, font_size=40, color=PURPLE_HI, weight="BOLD")
            txt = Text(sub, font=FONT, font_size=18, color=WHITE, line_spacing=0.7)
            body = VGroup(num, txt).arrange(DOWN, buff=0.22)
            box = RoundedRectangle(width=4.2, height=2.0, corner_radius=0.14,
                                   fill_color=PURPLE, fill_opacity=0.22,
                                   stroke_color=PURPLE_HI, stroke_width=2)
            body.move_to(box.get_center())
            load.add(VGroup(box, body))
        load.arrange(RIGHT, buff=0.35).move_to([0, -0.9, 0])
        self.play(FadeIn(load, lag_ratio=0.25), run_time=1.1)
        caption(self, "Three sections carry the load: 05, 07 and 12.", hold=1.6, y=-3.5, size=24)
        self.play(FadeOut(VGroup(head6, load, files)), run_time=0.5)

        # ---- Beat 7: traceability check -------------------------------
        head7 = Text("Traceability check - mechanical, not a judgement call",
                     font=FONT, font_size=28, color=GREEN_HI).move_to([0, 2.5, 0])
        self.play(FadeIn(head7), run_time=0.5)
        checks = VGroup()
        for label in [
            "every FR from 05 appears in 12 - count both",
            "every screen in 10 names an FR",
            "every role in 06 exists in 03",
            "every entity in 06 exists in 08",
            "no blank cells, all links resolve",
        ]:
            checks.add(chip(label, GREEN, GREEN_HI, fs=20, h=0.66, w=8.2))
        checks.arrange(DOWN, buff=0.26).move_to([0, -0.1, 0])
        self.play(FadeIn(checks, lag_ratio=0.25), run_time=1.2)
        caption(self, "Count the FRs in 05, count the rows in 12 - they match, or it is not done.",
                hold=1.4, y=-3.5, size=24)
        self.play(FadeOut(VGroup(head7, checks)), run_time=0.5)

        # ---- Beat 8: nothing invented + handoff -----------------------
        head8 = title_text("Nothing is invented", fs=40, color=WHITE).move_to([0, 2.5, 0])
        self.play(Write(head8), run_time=0.8)
        surfaced = VGroup()
        for label in ["every OI", "every AS", "every Partial / No", "every NFR target\nproposed, not received"]:
            surfaced.add(chip(label, RED, AMBER, fs=19, h=1.0, w=3.0))
        surfaced.arrange(RIGHT, buff=0.3).move_to([0, 1.0, 0])
        self.play(FadeIn(surfaced, lag_ratio=0.2), run_time=0.9)
        caption(self, "Everything unresolved is surfaced to the human, not smoothed over.",
                hold=1.0, y=-3.5, size=24)

        sb2 = chip("spec-builder", PURPLE, PURPLE_HI, fs=22, h=0.85, w=3.6).move_to([-4.2, -1.2, 0])
        contract = chip("docs/specs/", NEUTRAL, WHITE, fs=22, h=0.85, w=3.2).move_to([0, -1.2, 0])
        csub = Text("the contract exists", font=FONT, font_size=20, color=GREEN_HI).next_to(contract, DOWN, buff=0.2)
        hb = chip("harness-bootstrap", PURPLE, PURPLE_HI, fs=22, h=0.85, w=4.2).move_to([4.3, -1.2, 0])
        ah1 = Arrow(sb2.get_right(), contract.get_left(), buff=0.2, color=DIM, stroke_width=3)
        ah2 = Arrow(contract.get_right(), hb.get_left(), buff=0.2, color=GREEN_HI, stroke_width=3)
        self.play(GrowFromCenter(sb2), Create(ah1), GrowFromCenter(contract), FadeIn(csub), run_time=0.8)
        self.play(Create(ah2), GrowFromCenter(hb), run_time=0.6)
        caption(self, "Handoff: the contract exists. Now bootstrap the harness that implements it.",
                hold=1.7, y=-3.5, size=24)
        self.play(FadeOut(VGroup(head8, surfaced, sb2, contract, csub, hb, ah1, ah2)), run_time=0.7)
        self.wait(0.3)

import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
from theme import (
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
    FONT,
    caption,
    chip,
    tag,
    title_text,
)

AMBER = "#FFBA08"

# right-hand working column (the pain column lives on the left)
RX = 2.95


def fit(mobj, max_w):
    if mobj.width > max_w:
        mobj.scale(max_w / mobj.width)
    return mobj


def box(label, fill, stroke, w, h=0.78, fs=20, text_color=WHITE, radius=0.13):
    """chip() but the label is always clamped inside the box."""
    t = Text(label, font=FONT, font_size=fs, color=text_color, line_spacing=0.8)
    fit(t, w - 0.4)
    r = RoundedRectangle(
        width=w,
        height=h,
        corner_radius=radius,
        fill_color=fill,
        fill_opacity=1.0,
        stroke_color=stroke,
        stroke_width=2,
    )
    t.move_to(r.get_center())
    return VGroup(r, t)


def check(color=GREEN_HI, scale=1.0):
    a = Line([-0.16, 0.02, 0], [-0.04, -0.13, 0], color=color, stroke_width=6)
    b = Line([-0.04, -0.13, 0], [0.18, 0.16, 0], color=color, stroke_width=6)
    return VGroup(a, b).scale(scale)


def down_arrow(top, bottom, color=DIM):
    return Arrow(top, bottom, buff=0.12, color=color, stroke_width=3, max_tip_length_to_length_ratio=0.28)


PAINS = [
    "invents requirements that look mergeable",
    "context compacts - the work vanishes",
    "one bad turn reads .env or commits to main",
    "no explicit model - the bill runs away",
]

PW = 5.0  # pain chip width
PX = -4.3  # pain column centre x


class Solution(Scene):
    def construct(self):
        self.camera.background_color = BG

        # ============ title =============================================
        t = title_text("The complete solution", fs=46, color=WHITE)
        sub = Text(
            "contract, then harness, then loop",
            font=FONT,
            font_size=26,
            color=DIM,
        )
        legend = VGroup(
            tag("green = harness / deterministic", GREEN_HI, fs=19),
            tag("purple = the model", PURPLE_HI, fs=19),
            tag("red = blocked", RED, fs=19),
        ).arrange(RIGHT, buff=0.35)
        head = VGroup(t, sub, legend).arrange(DOWN, buff=0.5)
        self.play(Write(t), run_time=0.8)
        self.play(FadeIn(sub), FadeIn(legend, lag_ratio=0.2), run_time=0.7)
        self.wait(1.1)
        self.play(FadeOut(head), run_time=0.45)

        # ============ Beat 1: the pain ==================================
        ptitle = Text(
            "An agent dropped in a real repo",
            font=FONT,
            font_size=32,
            color=WHITE,
        ).move_to([0, 2.9, 0])
        self.play(FadeIn(ptitle, shift=0.12 * DOWN), run_time=0.45)

        pain_chips = VGroup(
            *[box(p, "#3A0D10", RED, w=PW, h=0.8, fs=19) for p in PAINS]
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
        caption(self, "Four failures, every time, in every real repo.", hold=2.0, y=-3.4, size=24)
        self.play(Indicate(marks, color=RED, scale_factor=1.35), run_time=0.7)
        caption(self, "Plausible fiction, lost work, unsafe turns, an inherited bill.", hold=1.6, y=-3.4, size=24)

        # dock the pain list to the left column
        self.play(FadeOut(ptitle), run_time=0.3)
        self.play(
            pain_chips.animate.move_to([PX, 0.75, 0]),
            marks.animate.shift(np.array([PX, 0.7, 0])),
            run_time=0.7,
        )
        col_head = Text("the pain", font=FONT, font_size=22, color=DIM).next_to(
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
        raw = box("idea / notes / transcript / legacy docs", NEUTRAL, DIM, w=6.6, h=0.72, fs=19)
        sb = box("spec-builder", PURPLE, PURPLE_HI, w=4.0, h=0.82, fs=24)
        specs = box("docs/specs/  -  13 sections", NEUTRAL, WHITE, w=5.6, h=0.82, fs=22)
        stack = VGroup(raw, sb, specs).arrange(DOWN, buff=0.72).move_to([RX, 1.35, 0])
        a1 = down_arrow(raw.get_bottom(), sb.get_top())
        a2 = down_arrow(sb.get_bottom(), specs.get_top())

        notes = VGroup(
            Text("stable FR IDs + acceptance criteria", font=FONT, font_size=19, color=BLUE_HI),
            Text("never invents a requirement:", font=FONT, font_size=19, color=DIM),
            Text("unstated -> AS-nn assumption / OI-nn open issue", font=FONT, font_size=19, color=AMBER),
        ).arrange(DOWN, buff=0.22).next_to(specs, DOWN, buff=0.4)
        for n in notes:
            fit(n, 6.6)

        self.play(GrowFromCenter(raw), run_time=0.4)
        caption(self, "Step 1: spec-builder turns raw input into a contract.", hold=0.9, y=-3.4, size=24)
        self.play(Create(a1), GrowFromCenter(sb), run_time=0.5)
        self.play(Create(a2), GrowFromCenter(specs), run_time=0.5)
        self.play(FadeIn(notes[0], shift=0.1 * UP), run_time=0.4)
        self.play(FadeIn(notes[1]), FadeIn(notes[2], shift=0.1 * UP), run_time=0.5)
        caption(self, "It never invents: anything unstated is flagged, not guessed.", hold=2.1, y=-3.4, size=24)

        anims, tick0 = resolve(0)
        self.play(*anims, run_time=0.7)
        caption(self, "Pain 1 resolved - no more plausible fiction.", hold=1.2, y=-3.4, size=24)

        beat2 = VGroup(stack, a1, a2, notes)
        self.play(FadeOut(beat2), run_time=0.5)

        # ============ Beat 3: harness-bootstrap builds the harness ======
        hb = box("harness-bootstrap", PURPLE, PURPLE_HI, w=4.6, h=0.82, fs=24).move_to([RX, 2.75, 0])
        reads = box("reads your code FIRST", PURPLE, PURPLE_HI, w=4.6, h=0.66, fs=19).move_to([RX, 1.72, 0])
        a3 = down_arrow(hb.get_bottom(), reads.get_top())

        claude = Text(".claude/", font=FONT, font_size=24, color=GREEN_HI).move_to([RX, 0.86, 0])
        a4 = down_arrow(reads.get_bottom(), claude.get_top())

        grid = VGroup(
            box("15 agents\nmodel + effort", GREEN, GREEN_HI, w=3.2, h=0.9, fs=18),
            box("14 rules\n6 always, 8 scoped", GREEN, GREEN_HI, w=3.2, h=0.9, fs=18),
            box("14 commands", GREEN, GREEN_HI, w=3.2, h=0.9, fs=18),
            box("6 blocking hooks", GREEN, GREEN_HI, w=3.2, h=0.9, fs=18),
        ).arrange_in_grid(rows=2, cols=2, buff=(0.3, 0.3)).move_to([RX, -0.35, 0])

        board = box("docs/tasks/  -  a board that survives a crash", NEUTRAL, WHITE, w=6.8, h=0.7, fs=19).move_to(
            [RX, -2.0, 0]
        )
        foot = VGroup(
            Text("scaffold: ~0.2s", font=FONT, font_size=19, color=GREEN_HI),
            Text("reconciles, never overwrites", font=FONT, font_size=19, color=DIM),
        ).arrange(RIGHT, buff=0.5).move_to([RX, -2.8, 0])

        self.play(GrowFromCenter(hb), run_time=0.4)
        caption(self, "Step 2: harness-bootstrap reads your code, then builds the harness.", hold=0.9, y=-3.4, size=23)
        self.play(Create(a3), GrowFromCenter(reads), run_time=0.5)
        self.play(Create(a4), FadeIn(claude, shift=0.1 * DOWN), run_time=0.45)
        self.play(FadeIn(grid, lag_ratio=0.3, shift=0.12 * UP), run_time=0.9)
        self.play(FadeIn(board, shift=0.1 * UP), run_time=0.45)
        self.play(FadeIn(foot), run_time=0.4)
        caption(self, "Every agent gets an explicit model. Hooks block. The board is on disk.", hold=2.4, y=-3.4, size=23)

        a2b, tick1 = resolve(1)
        a2c, tick2 = resolve(2)
        a2d, tick3 = resolve(3)
        self.play(*a2b, run_time=0.5)
        self.play(*a2c, run_time=0.5)
        self.play(*a2d, run_time=0.5)
        caption(self, "Pains 2, 3 and 4 resolved - by construction, not by good intentions.", hold=1.6, y=-3.4, size=23)

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
        lhead = Text("The delivery loop runs inside it", font=FONT, font_size=30, color=WHITE).move_to([0, 3.0, 0])
        self.play(FadeIn(lhead), run_time=0.4)

        orch = box("orchestrator", PURPLE, PURPLE_HI, w=3.6, h=0.85, fs=23).move_to([0, 1.85, 0])
        spec_ag = box("scoped specialist agents", PURPLE, PURPLE_HI, w=4.2, h=0.85, fs=20).move_to([-3.5, 0.15, 0])
        tboard = box("docs/tasks/ board\non disk", NEUTRAL, WHITE, w=3.4, h=0.95, fs=19).move_to([3.6, 0.15, 0])
        hooks = box("hooks", RED, AMBER, w=2.0, h=0.75, fs=22).move_to([-1.0, -1.85, 0])

        self.play(GrowFromCenter(orch), run_time=0.4)
        self.play(GrowFromCenter(spec_ag), GrowFromCenter(tboard), run_time=0.5)

        w1 = Arrow(orch.get_left(), spec_ag.get_top(), buff=0.18, color=DIM, stroke_width=3)
        w1l = Text("dispatches", font=FONT, font_size=18, color=DIM).move_to([-2.65, 1.25, 0])
        w2 = Arrow(spec_ag.get_right(), tboard.get_left(), buff=0.18, color=DIM, stroke_width=3)
        w2l = Text("records progress", font=FONT, font_size=18, color=DIM).next_to(w2, UP, buff=0.12)

        self.play(Create(w1), FadeIn(w1l), run_time=0.45)
        caption(self, "The orchestrator dispatches scoped specialists against the board.", hold=1.0, y=-3.4, size=23)
        self.play(Create(w2), FadeIn(w2l), run_time=0.45)
        caption(self, "The board on disk records progress as the agent works.", hold=1.1, y=-3.4, size=23)

        w3 = Arrow(spec_ag.get_bottom(), hooks.get_top(), buff=0.15, color=DIM, stroke_width=3)
        blocked = Text("BLOCKED", font=FONT, font_size=22, color=AMBER).next_to(hooks, RIGHT, buff=0.35)
        note = Text('not "advised against"', font=FONT, font_size=19, color=DIM).next_to(blocked, RIGHT, buff=0.35)
        self.play(GrowFromCenter(hooks), Create(w3), run_time=0.45)
        self.play(Flash(hooks.get_center(), color=RED, flash_radius=0.9), FadeIn(blocked), FadeIn(note), run_time=0.7)
        caption(self, "Hooks BLOCK the bad action. They do not advise against it.", hold=2.2, y=-3.4, size=23)

        loop_grp = VGroup(lhead, orch, spec_ag, tboard, hooks, w1, w1l, w2, w2l, w3, blocked, note)
        self.play(FadeOut(loop_grp), run_time=0.55)

        # ============ Beat 5: the payoff ================================
        phead = Text("The payoff", font=FONT, font_size=34, color=WHITE).move_to([0, 3.05, 0])
        self.play(FadeIn(phead), run_time=0.4)

        payoff = VGroup(
            box("the contract exists", GREEN, GREEN_HI, w=6.4, h=0.72, fs=22),
            box("the harness cannot be escaped", GREEN, GREEN_HI, w=6.4, h=0.72, fs=22),
            box("state survives a crash", GREEN, GREEN_HI, w=6.4, h=0.72, fs=22),
            box("the bill is chosen, not inherited", GREEN, GREEN_HI, w=6.4, h=0.72, fs=22),
        ).arrange(DOWN, buff=0.26).move_to([0, 0.45, 0])
        for p in payoff:
            self.play(FadeIn(p, shift=0.12 * UP), run_time=0.32)
        caption(self, "Contract, enforcement, durable state, a chosen bill.", hold=1.2, y=-3.4, size=24)

        ev = VGroup(
            tag("guardrail eval 15/15", GREEN_HI, fs=20),
            tag("Opus -> Haiku: byte-identical safety", GREEN_HI, fs=20),
        ).arrange(RIGHT, buff=0.4).move_to([0, -2.05, 0])
        ports = Text(
            "shell scripts + glob rules  |  ports to Claude Code, Cursor and Codex with enforcement",
            font=FONT,
            font_size=20,
            color=DIM,
        ).move_to([0, -2.8, 0])
        fit(ports, 12.6)

        self.play(FadeIn(ev, lag_ratio=0.3), run_time=0.55)
        caption(self, "Guardrails are shell scripts and glob rules - so they are model-independent.", hold=1.5, y=-3.4, size=22)
        self.play(FadeIn(ports), run_time=0.4)
        self.wait(1.7)
        self.play(FadeOut(VGroup(phead, payoff, ev, ports)), run_time=0.6)
        self.wait(0.25)

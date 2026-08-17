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
    watermark,
)


def small(s, fs=20, color=DIM):
    return Text(s, font=FONT, font_size=fs, color=color)


class SkillsAndView(Scene):
    """The operating flow of the overview figure, then the three mechanisms that
    keep it honest: skill discovery, skill wire, and harness-view.

    Mirrors docs/assets/harness-loom.svg beat for beat, so the clip and the figure
    cannot drift into telling different stories.
    """

    def construct(self):
        self.camera.background_color = BG
        watermark(self)

        # ---- title ------------------------------------------------------
        t = title_text("How it runs, and what keeps it honest", fs=42, color=WHITE)
        self.play(Write(t), run_time=0.9)
        self.wait(0.6)
        self.play(t.animate.scale(0.58).to_edge(UP, buff=0.35), run_time=0.6)

        # =================================================================
        # BEAT A - the operating flow, left to right
        # =================================================================
        caption(self, "Input arrives in whatever shape it arrives in.", hold=1.0)

        sources = ["an idea", "a transcript", "legacy docs", "a repo"]
        src_chips = VGroup(
            *[chip(s, BG, NEUTRAL, text_color=DIM, w=2.5, h=0.6, fs=20) for s in sources]
        ).arrange(DOWN, buff=0.22)
        src_chips.move_to([-5.5, -0.3, 0])
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
        caption(self, "spec-builder turns any of it into ONE contract.", hold=1.1)

        contract = small("one contract", fs=19, color=BLUE_HI)
        agent = chip("Agent(s)", PURPLE, PURPLE_HI, w=2.6, h=0.95, fs=24)
        agent.move_to([2.3, -0.3, 0])
        a1 = Arrow(spec.get_right(), agent.get_left(), buff=0.12, stroke_width=3,
                   max_tip_length_to_length_ratio=0.12, color=BLUE_HI)
        if contract.width > a1.get_length() - 0.15:
            contract.scale((a1.get_length() - 0.15) / contract.width)
        contract.next_to(a1, UP, buff=0.12)
        self.play(Create(a1), FadeIn(contract), run_time=0.6)
        self.play(FadeIn(agent, scale=0.92), run_time=0.5)

        # rules and hooks come down from above
        rules = chip("rules", GREEN, GREEN_HI, w=1.9, h=0.6, fs=20)
        hooks = chip("hooks", RED, "#E5383B", w=1.9, h=0.6, fs=20)
        rules.move_to([1.2, 1.85, 0])
        hooks.move_to([3.4, 1.85, 0])
        d1 = Arrow(rules.get_bottom(), agent.get_top() + 0.35 * LEFT, buff=0.1,
                   stroke_width=2.4, max_tip_length_to_length_ratio=0.12, color=GREEN_HI)
        d2 = Arrow(hooks.get_bottom(), agent.get_top() + 0.35 * RIGHT, buff=0.1,
                   stroke_width=2.4, max_tip_length_to_length_ratio=0.12, color="#E5383B")
        self.play(FadeIn(rules, shift=0.2 * DOWN), FadeIn(hooks, shift=0.2 * DOWN), run_time=0.5)
        self.play(Create(d1), Create(d2), run_time=0.5)
        caption(self, "Rules and hooks come down into the agents. exit 2 blocks the call.", hold=1.3)

        # three ordered outputs
        outs = VGroup(
            chip("docs + graph", BG, GREEN_HI, text_color=WHITE, w=2.7, h=0.6, fs=19),
            chip("plan", BG, GREEN_HI, text_color=WHITE, w=2.7, h=0.6, fs=19),
            chip("code + graph", BG, GREEN_HI, text_color=WHITE, w=2.7, h=0.6, fs=19),
        ).arrange(DOWN, buff=0.24)
        outs.move_to([5.7, -0.3, 0])
        out_arrows = VGroup(
            *[
                Arrow(agent.get_right(), c.get_left(), buff=0.1, stroke_width=2.4,
                      max_tip_length_to_length_ratio=0.09, color=GREEN_HI)
                for c in outs
            ]
        )
        self.play(Create(out_arrows), FadeIn(outs), run_time=0.8)
        caption(self, "Three ordered outputs, every time, all carrying stable IDs.", hold=1.3)

        # state sits underneath, read and written, never an input
        state = chip("state: prompt, history, task board", BG, GREEN_HI,
                     text_color=DIM, w=5.6, h=0.62, fs=19)
        state.move_to([2.3, -2.35, 0])
        s_link = DashedLine(agent.get_bottom(), state.get_top(), stroke_width=2.2,
                            color=GREEN_HI, dash_length=0.12)
        self.play(FadeIn(state, shift=0.15 * UP), Create(s_link), run_time=0.6)
        caption(self, "State is written, not supplied. It survives compaction and a crash.", hold=1.4)

        self.play(
            FadeOut(VGroup(src_chips, arrows_in, spec, a1, contract, rules, hooks,
                           d1, d2, agent, out_arrows, outs, state, s_link)),
            run_time=0.6,
        )

        # =================================================================
        # BEAT A2 - the step between the contract and the harness
        # =================================================================
        h1b = Text("Tailored, not comprehensive", font=FONT, font_size=34,
                   color=WHITE, weight="BOLD")
        h1b.move_to([0, 2.35, 0])
        p1b = small("Most kits install everything, then hope the project needs it.",
                    fs=22, color=DIM)
        p1b.move_to([0, 1.7, 0])
        self.play(FadeIn(h1b, shift=0.15 * DOWN), FadeIn(p1b), run_time=0.6)

        kit = RoundedRectangle(width=5.4, height=2.5, corner_radius=0.14, fill_color=BG,
                               fill_opacity=1.0, stroke_color=RED, stroke_width=2)
        kit.move_to([-3.5, -0.85, 0])
        kit_t = Text("every agent, a hundred skills", font=FONT, font_size=21, color="#E5575B")
        kit_t.move_to(kit.get_center() + 0.72 * UP)
        kit_lines = VGroup(*[Text(s, font=FONT, font_size=16, color=DIM)
                             for s in ["you pay context for all of it",
                                       "seats no module owns",
                                       "advice too general to act on"]])
        kit_lines.arrange(DOWN, buff=0.2, aligned_edge=np.array([-1.0, 0, 0]))
        kit_lines.move_to(kit.get_center() + 0.34 * DOWN)
        self.play(Create(kit), FadeIn(kit_t), run_time=0.5)
        self.play(FadeIn(kit_lines, shift=0.1 * UP), run_time=0.5)

        fit = RoundedRectangle(width=5.4, height=2.5, corner_radius=0.14, fill_color=BG,
                               fill_opacity=1.0, stroke_color=GREEN_HI, stroke_width=2)
        fit.move_to([3.5, -0.85, 0])
        fit_t = Text("7 to 15 of the 16 seats", font=FONT, font_size=21, color=GREEN_HI)
        fit_t.move_to(fit.get_center() + 0.72 * UP)
        fit_lines = VGroup(*[Text(s, font=FONT, font_size=16, color=DIM)
                             for s in ["derived from the contract",
                                       "and the modules that exist",
                                       "one dev agent per module"]])
        fit_lines.arrange(DOWN, buff=0.2, aligned_edge=np.array([-1.0, 0, 0]))
        fit_lines.move_to(fit.get_center() + 0.34 * DOWN)
        self.play(Create(fit), FadeIn(fit_t), run_time=0.5)
        self.play(FadeIn(fit_lines, shift=0.1 * UP), run_time=0.5)

        swap = Arrow(kit.get_right(), fit.get_left(), buff=0.12, stroke_width=3,
                     max_tip_length_to_length_ratio=0.3, color=GREEN_HI)
        self.play(Create(swap), run_time=0.4)
        caption(self, "A seat nobody owns is a cost, not a capability.", hold=1.5)

        self.play(FadeOut(VGroup(h1b, p1b, kit, kit_t, kit_lines,
                                 fit, fit_t, fit_lines, swap)), run_time=0.5)

        # =================================================================
        # BEAT B - skill discovery
        # =================================================================
        h2 = Text("Skill Discovery", font=FONT, font_size=34, color=WHITE, weight="BOLD")
        h2.move_to([0, 2.35, 0])
        prob = small("The problem: you cannot choose from a catalog you have never read.",
                     fs=22, color=DIM)
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
        caption(self, "It reads this project's manifests, not a generic list.", hold=1.2)

        stack = chip("detected tech stack", GREEN, GREEN_HI, w=3.6, h=0.8, fs=21)
        stack.move_to([-0.2, -0.9, 0])
        self.play(
            Create(Arrow(manifests.get_right(), stack.get_left(), buff=0.15,
                         stroke_width=2.6, max_tip_length_to_length_ratio=0.1, color=GREEN_HI)),
            FadeIn(stack, scale=0.92),
            run_time=0.7,
        )

        matched = VGroup(
            chip("skills that match", BG, GREEN_HI, text_color=WHITE, w=3.4, h=0.6, fs=19),
            chip("you choose, or not", BG, BLUE_HI, text_color=BLUE_HI, w=3.4, h=0.6, fs=19),
        ).arrange(DOWN, buff=0.22)
        matched.move_to([4.0, -0.9, 0])
        self.play(
            Create(Arrow(stack.get_right(), matched.get_left(), buff=0.15, stroke_width=2.6,
                         max_tip_length_to_length_ratio=0.1, color=GREEN_HI)),
            FadeIn(matched),
            run_time=0.7,
        )
        caption(self, "Nothing installs itself. The candidates are yours to accept or refuse.",
                hold=1.4)

        self.play(FadeOut(VGroup(h2, prob, manifests, stack, matched)), run_time=0.5)

        # =================================================================
        # BEAT C - skill wire
        # =================================================================
        h3 = Text("Skill Wire", font=FONT, font_size=34, color=WHITE, weight="BOLD")
        h3.move_to([0, 1.9, 0])
        prob3 = small("The problem: an installed skill nobody is told to use is dead weight.",
                      fs=22, color=DIM)
        prob3.move_to([0, 1.25, 0])
        self.play(FadeIn(h3, shift=0.15 * DOWN), FadeIn(prob3), run_time=0.6)

        skill = chip("a chosen skill", BG, BLUE_HI, text_color=WHITE, w=3.2, h=0.8, fs=21)
        seat = chip("the agent that needs it", PURPLE, PURPLE_HI, w=4.4, h=0.8, fs=21)
        skill.move_to([-3.6, -0.5, 0])
        seat.move_to([2.4, -0.5, 0])
        self.play(FadeIn(skill), FadeIn(seat), run_time=0.5)

        wire = Arrow(skill.get_right(), seat.get_left(), buff=0.15, stroke_width=3.4,
                     max_tip_length_to_length_ratio=0.08, color=BLUE_HI)
        wire_lbl = small("/skill-wire", fs=20, color=BLUE_HI)
        wire_lbl.next_to(wire, UP, buff=0.14)
        self.play(Create(wire), FadeIn(wire_lbl), run_time=0.6)
        self.play(Indicate(wire, color=WHITE, scale_factor=1.05), run_time=0.6)
        caption(self, "The wire is a node in the graph, not a convention in a document.",
                hold=1.4)

        self.play(FadeOut(VGroup(h3, prob3, skill, seat, wire, wire_lbl)), run_time=0.5)

        # =================================================================
        # BEAT D - harness-view
        # =================================================================
        h4 = Text("harness-view", font=FONT, font_size=34, color=WHITE, weight="BOLD")
        h4.move_to([0, 1.9, 0])
        prob4 = small("The problem: how do you know it is actually wired right?",
                      fs=22, color=DIM)
        prob4.move_to([0, 1.25, 0])
        self.play(FadeIn(h4, shift=0.15 * DOWN), FadeIn(prob4), run_time=0.6)

        funcs = [
            ("Flow / Graph", "every wire, read off disk"),
            ("Assess", "a score, and what is wrong"),
            ("Toggle", "switch any rule or hook off"),
            ("Watch", "re-scan as files change"),
        ]
        cards = VGroup()
        for name, desc in funcs:
            box = RoundedRectangle(width=3.0, height=1.25, corner_radius=0.14,
                                   fill_color=BG, fill_opacity=1.0,
                                   stroke_color=GREEN_HI, stroke_width=2)
            n = Text(name, font=FONT, font_size=21, color=WHITE, weight="BOLD")
            d = Text(desc, font=FONT, font_size=16, color=DIM)
            if d.width > 2.7:
                d.scale(2.7 / d.width)
            n.move_to(box.get_center() + 0.24 * UP)
            d.move_to(box.get_center() + 0.26 * DOWN)
            cards.add(VGroup(box, n, d))
        cards.arrange(RIGHT, buff=0.28).move_to([0, -0.55, 0])
        if cards.width > 13.4:
            cards.scale(13.4 / cards.width)
        for c in cards:
            self.play(FadeIn(c, shift=0.12 * UP), run_time=0.28)
        caption(self, "It reads the state the run wrote. No model is in the loop.", hold=1.3)

        det = tag("a browser and CI cannot disagree", GREEN_HI, fs=21)
        det.move_to([0, -2.35, 0])
        self.play(FadeIn(det, scale=0.94), run_time=0.5)
        self.wait(0.8)

        self.play(FadeOut(VGroup(h4, prob4, cards, det)), run_time=0.5)

        # ---- close ------------------------------------------------------
        close1 = title_text("Chaos in.", fs=40, color=DIM)
        close2 = title_text("Controlled, inspectable work out.", fs=40, color=GREEN_HI)
        close1.move_to([0, 0.55, 0])
        close2.move_to([0, -0.3, 0])
        self.play(Write(close1), run_time=0.6)
        self.play(Write(close2), run_time=0.8)
        self.wait(1.2)
        self.play(FadeOut(VGroup(close1, close2, t)), run_time=0.6)
        self.wait(0.3)

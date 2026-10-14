# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vite multi-page build (vanilla HTML + CSS + a few lines of vanilla JS), deployed by GitHub Pages
under `https://nguyenhx2.github.io/agent-harness-bootstrap/`. No framework, no CDN, no external
request of any kind. (Recorded from the explicit build brief; not from a live user answer.)

## Users

Engineers and engineering leads who have already put an AI coding agent on a real repository and
been burned by it: an agent that touched fourteen files for a one-file change, force-pushed to
`main`, opened `.env` "while fixing a bug", or forgot its plan when the session compacted. They
arrive from a README badge, a conference link, or a colleague, usually on a phone first, and they
are deciding in under a minute whether this is a real safety floor or another prompt-pack.
A second audience reads the same page in Japanese.

## Product Purpose

Give an AI agent a repo it can actually understand, and a harness it cannot escape. The landing
page leads with that idea and lets the intro clip carry it, then earns it: the symptoms, what
answers them, how work is routed, how the roster is sized, where a request is stopped, how the
viewer reads it back, and only then how to install, run and tune it. Every section has to earn its
place; anything a visitor would not miss is cut. Success is a visitor who installs, watches the intro, or
opens the deck, in either language, from any device.

## Positioning

The mechanism a neighbouring product cannot truthfully copy: the guardrails are shell scripts and
exit codes, not model instructions. No model is consulted, so the safety result cannot depend on the
model, and `python eval/guardrail_eval.py` proves it. Second differentiator: the roster is
sized to the repo's purpose (code, research, strategy, docs) and derived from the contract and the
repo's real modules, so a run installs 3 to 17 of the 18 seats rather than a fixed cast. Third: `harness-view` reads the harness off disk with no model in the loop, so a
browser and a CI run cannot disagree about the score.

## Operating Context

The product is three parts that hand off to each other: `spec-builder` (a skill), `harness-bootstrap`
(a skill), and `harness-view` (a native viewer plus local web UI). The plugin route is the first
install path offered and the one with working updates; the release zip is the offline, pinned
alternative. Both are portable to Cursor and Codex. The landing page sits beside a slide deck
(`presentation/`) and the GitHub repository, served from the same GitHub Pages site; the intro
clip, the only clip the project ships, plays in the landing page itself and has a page of its own
at `video/`.

## Capabilities and Constraints

- Every figure on the page is gated in CI by `scripts/check_numbers.py`: no number may be typed that
  the repo cannot derive. The version badge string is gated against the release tag.
- No em-dash may appear in any committed text, either language.
- No timestamps, build dates, or generated IDs in committed source; the repo bans volatile bytes.
- Zero external requests: no CDN, no webfont fetch, no analytics.
- The page ships in full English/Japanese parity, and the Japanese page keeps language-aware
  outbound links.
- The page authors its own diagrams as inline SVG, and its icons as an inline symbol sprite: no
  icon font, no emoji, no external request. Three raster files under `docs/assets/` are referenced
  from the site - `logo-mark.svg` as the icon, and the two `harness-view-*.png` screenshots, whose
  captions may quote only the figures pinned in `docs/assets/CAPTURED.json`.

## Brand Commitments

Name: Agent Harness Bootstrap. Mark: `docs/assets/logo-mark.svg`. Licence: AGPL-3.0-only. Voice: plain,
measured, evidence-first, allergic to adjectives; the existing pages say "Proof, not adjectives"
and mean it. Every claim on the surface is answered by a script in the repository.

## Evidence on Hand

Real, derived, and re-runnable by the visitor:

- guardrail eval 290/290 per hook flavour, on both hook flavours, measured on a harness scaffolded with
  the `hooks_strict`, `long` and `db` flags on (`VARS` in `eval/guardrail_eval.py` names the set)
- the guardrail suite splits into 123 must-block and 167 must-allow cases
- Cursor and Codex port adapter self-test 32/32
- a bare repository blocks 0/67 benchmark payloads; the same repository, harnessed, blocks all 67
- 75% of rule content stays out of the default session, because 10 of 17 rules are path-scoped
- a run installs 3 to 17 of the 18 seats (docs-only repo at the low end)
- `harness-view` scored 99/100 on a real harness, over 219 nodes and 655 edges, with two findings
  worth one point each (SAF-02 and COST-06) (the two shipped screenshots; provenance in `docs/assets/CAPTURED.json`)
- the delivery pipeline, the tailoring step and the five control layers, each of which the page
  draws itself as a live diagram rather than importing as a picture
- outbound proof surfaces: `presentation/`, `video/`, the GitHub repository, the releases page

No customer names, no pricing, no adoption numbers, no testimonials exist. Future work must not
invent any.

## Product Principles

1. Proof over adjectives: a number on the surface must be derivable from a script in the repository.
2. The floor is mechanical. Anything the model could talk its way past is a ceiling claim, not a
   floor claim, and must be described as such.
3. Fitted, not comprehensive: the product's whole argument is that it installs what your repo
   justifies and nothing else. The surface should behave the same way.
4. Both languages are the product, not a translation afterthought.
5. Self-contained: a landing page that needs a CDN is a landing page that breaks when the CDN does.

## Accessibility & Inclusion

WCAG AA contrast on every committed pair. Any diagram that carries meaning must state that meaning
in text as well, so a reader who cannot see the drawing loses nothing. The page must be fully
usable at 360px wide, with 44px tap targets, visible focus, and `prefers-reduced-motion` honoured
as tiering rather than as a kill switch.

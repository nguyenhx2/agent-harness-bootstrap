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
page has to make three things intelligible fast: what the three pieces are, that the safety floor
is mechanical rather than advisory, and how to install it. Success is a visitor who installs, opens
the deck, or watches the intro, in either language, from any device.

## Positioning

The mechanism a neighbouring product cannot truthfully copy: the guardrails are shell scripts and
exit codes, not model instructions. Swap every agent from Opus to Haiku and the safety result is
byte-identical, and `python eval/guardrail_eval.py` proves it. Second differentiator: the roster is
derived from the contract and the repo's real modules, so a run installs 7 to 15 of 16 seats rather
than a fixed cast. Third: `harness-view` reads the harness off disk with no model in the loop, so a
browser and a CI run cannot disagree about the score.

## Operating Context

The product is three parts that hand off to each other: `spec-builder` (a skill), `harness-bootstrap`
(a skill), and `harness-view` (a native viewer plus local web UI). It is installed either as a Claude
Code plugin from a marketplace or from a release zip, and it is portable to Cursor and Codex. The
landing page sits beside a slide deck (`presentation/`), a video gallery (`video/`), and the GitHub
repository, all served from the same GitHub Pages site.

## Capabilities and Constraints

- Every figure on the page is gated in CI by `scripts/check_numbers.py`: no number may be typed that
  the repo cannot derive. The version badge string is gated against the release tag.
- No em-dash may appear in any committed text, either language.
- No timestamps, build dates, or generated IDs in committed source; the repo bans volatile bytes.
- Zero external requests: no CDN, no webfont fetch, no analytics.
- The page ships in full English/Japanese parity, and the Japanese page keeps language-aware
  outbound links.
- The page authors its own diagrams as inline SVG. The repository figures under `docs/assets/`
  are README and deck assets; only `logo-mark.svg` is referenced from the site, as the icon.

## Brand Commitments

Name: Agent Harness Bootstrap. Mark: `docs/assets/logo-mark.svg`. Licence: MIT. Voice: plain,
measured, evidence-first, allergic to adjectives; the existing pages say "Proof, not adjectives"
and mean it. Every claim on the surface is answered by a script in the repository.

## Evidence on Hand

Real, derived, and re-runnable by the visitor:

- guardrail eval 107/107 per hook flavour, 214/214 across both hook flavours
- the guardrail suite splits into 40 must-block and 67 must-allow cases
- Cursor and Codex port adapter self-test 32/32
- a bare repository blocks 0/22 benchmark payloads; the same repository, harnessed, blocks all 22
- 64% of rule content stays out of the default session, because 9 of 16 rules are path-scoped
- a run installs 7 to 15 of 16 seats
- `harness-view` scoring a real harness 64/100 and naming each finding
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

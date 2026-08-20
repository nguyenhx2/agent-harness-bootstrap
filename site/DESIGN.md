# Design

Recorded from the built pages (`index.html`, `index.ja.html`, `src/style.css`), not from intention.
The direction contract sits at the top of each page body and survives the production build.

## The world

A schematic-capture canvas. The product's argument is that a claim must be checkable, so the
surface makes each claim something you step through rather than something you read about: five
authored SVG nets on ultramarine plates, three of them driven by a radio group and energizing
segment by segment as the visitor moves along one.

What it refuses: the developer-tool arrangement of a gradient hero over three identical feature
cards; static exported figures dropped in as pictures; and a kicker above any heading. There is no
card in this system, no gradient, no glass, and no shadow.

## The argument

The page follows the README's argument, in the README's order, because the README already makes it
and a landing page that makes a different one is a second thing to keep true:

1. **Does any of this sound familiar** - the eight symptoms, each with what answers it.
2. **What answers it** - the three pieces, then N1, the delivery net.
3. **See the whole thing in one clip** - the seven explainer clips, played in the page.
4. **Install it** - plugin route first, zip second, the viewer last.
5. **Move to a new version** - the plugin update, and the re-scaffold that reconciles.
6. **Run it** - the first run, what you will be asked, and the day-to-day commands.
7. **How the orchestrator actually works** - N4, the routing tier.
8. **The roster is decided, not installed** - N2, the tailor.
9. **Watch a request get stopped** - N3, the control route.
10. **harness-view** - N5, the viewer route, the two shipped screenshots, and what is new.

Two sections were cut rather than carried forward. **"Every figure has a script behind it"** was a
five-row table of numbers already stated elsewhere on the page; the discipline it advertised is
better shown at the point of each claim, so each figure now names its script inline (`.src`) and
the colophon states the rule once. **"Where to go from here"** was a six-row link table whose rows
had all become sections of this page or footer links; it survived as the footer nav.

The video gallery was a separate page at `/video/`. Nobody had a reason to open it, so the clips
are folded in here: the lead clip plays inline, the other six sit behind a disclosure and preload
nothing until it is opened. The `/video/` page still exists and still works; it is simply no longer
the only place the clips are.

## Ink

Drafting film for the page, one saturated field for the plates. Light is the base declaration; a
machine that asks for dark gets the same drawing at night (`@media (prefers-color-scheme: dark)`).
Every surface paints its background explicitly, so the page holds on any host.

| Token | Light (base) | Dark | Role |
|---|---|---|---|
| `--paper` | `#eceff3` | `#0b0e14` | the film |
| `--paper-2` | `#ffffff` | `#131824` | raised |
| `--paper-3` | `#dfe4ea` | `#070a0f` | listings |
| `--ink` | `#0f141b` | `#e8edf4` | body and headings |
| `--ink-2` | `#3d4956` | `#a3aebd` | secondary prose |
| `--ink-3` | `#566270` | `#7e8996` | labels, provenance |
| `--line` | `#ccd4dc` | `#232b39` | hairlines |
| `--edge` | `#6c7885` | `#7e8996` | control boundaries and scrollbars |
| `--accent-text` | `#22318c` | `#93a4ee` | the field colour used as ink |
| `--block-text` | `#a8351a` | `#ff8f74` | the refusal word, on film |
| `--field` | `#182a7a` | `#131f5e` | the plate |
| `--field-lit` | `#2c3f9e` | `#24358c` | an energized node |
| `--field-line` | `#7a8ad4` | `#6f7ecb` | route metal |
| `--on-field` | `#eef1fb` | `#e4eafb` | text on the plate |
| `--on-field-2` | `#b3bee9` | `#a5b2e2` | secondary text on the plate |
| `--live` | `#ffc94d` | `#ffc94d` | a live signal |
| `--block` | `#ff7a5c` | `#ff7f61` | a refusal |

Two laws hold the world together. Inside a plate, gold means a live signal and coral means a
refusal; nothing else may use either. Outside a plate, the field colour is the only accent, and the
only coral is the refusal word in the headline.

Every text pair clears WCAG AA against its own ground (lowest measured: 4.9:1, `--ink-3` on
`--paper-3`). `--edge`, `--field-line` and the plate's route metal clear 3:1 as non-text
boundaries. The measured pairs are recorded as comments beside the tokens.

## Type

- **`--serif` (`--body`)**: Andada Pro, vendored as three unicode-range subsets in `src/fonts/`,
  variable weight 400-840, OFL 1.1 (`public/OFL-AndadaPro.txt`). Kept from the previous world on
  purpose: it is the presentation deck's face, so site and deck still read as one press, and a
  serif over a technical canvas refuses the reflex that technical subjects want a mono display.
- **`--mono`**: the platform mono stack, used where there is a value or a designator: figures,
  listings, net labels, controls, the document register.
- Japanese sets Andada Pro over a mincho stack (`Hiragino Mincho ProN`, `Yu Mincho`,
  `Noto Serif JP`) at 1.9 leading, no Latin tracking, and measures in `em` rather than `ch`.

Six fluid steps, `--t--2` through `--t-3`, all `clamp()` except the smallest. Display tracking is
`-0.032em`; the floor is `-0.04em`. Measures live on the element whose font size they are counted
in, because a `ch` measure set on a parent at a larger size renders far wider than it reads.

## Space and the sheet

`--s-0` through `--s-3`, all `clamp()` above the first two. One rhythm throughout, with more space
above a heading than below it.

`.wrap` is `max-width: 76rem` with `padding-inline: var(--gutter)`, where
`--gutter: max(20px, env(safe-area-inset-left, 0px))`. No other rule sets `padding-inline` on a
`.wrap`, so the gutter has no path to zero. Measured at 360px and 390px on both pages,
`document.scrollWidth` equals `clientWidth`.

## Components

- **`.masthead`** - sticky, hairline-bottomed, opaque. The outbound links never break mid-word; the
  product name may, because at 360px something has to give and it should not be the page width.
- **`.hero__grid`** - the claim and its lede on the left, the four actions and the four-field
  document register on the right, from 56rem up.
- **`.plate`** - the ultramarine field a net is drawn on: a mono head carrying the net's designator,
  the picker, then the diagram.
- **`.pick`** - a `<fieldset>` of radios with styled labels. This is the whole interaction layer:
  the flows use `:has()` and no script at all, so they work with JavaScript off and give keyboard
  users native arrow-key traversal. Without `:has()` the picker is hidden and every readout stays
  open, which degrades the page into a plain, complete document.
- **`.rd`** - the readout a selection resolves to: which stage, what it is, and a `writes` or
  `result` line naming the artifact or the refusal.
- **`.seat`** - one of the 16 roster pads, dashed when empty and solid gold-edged when installed.
- **`.symp`** - the opening question. One ruled row per symptom: an icon, the complaint in the
  reader's own voice, and what answers it. Three columns from 56rem, where two measures fit side by
  side; below that the icon keeps its column and the two paragraphs stack.
- **`.pieces`** - the three parts, each under a 2px accent rule. Not cards: a rule and text.
- **`.clips`** - the folded-in video gallery. The lead clip spans the grid and preloads metadata;
  the six behind `.more` carry `preload="none"`, so a disclosure nobody opens costs nothing.
- **`.more`** - a `<details>` with its marker replaced by a rotating chevron.
- **`.shot`** - a shipped screenshot with its caption. The two `docs/assets/harness-view-*.png`
  files are referenced relatively, carry their real intrinsic size so nothing shifts on load, and
  quote only the figures pinned in `docs/assets/CAPTURED.json`.
- **`.states`** - what a re-scaffold reports per file. This was a two-column table and it had to
  side-scroll on a phone to say three short things, so it is a `<dl>` that reflows instead.
- **`.src`** - where a figure came from, said beside the figure rather than in a trophy cabinet at
  the end of the page.
- **`.scroller`** - every listing and every table sits inside one, `overflow-x: auto`,
  `tabindex="0"`, `role="region"` with a label.
- **`.listing` / `.copy`** - the copy control sits above a listing, never over it, because a code
  block scrolls and a floating button covers a different character every time.

Icons are authored inline SVG symbols, 1.5 stroke, `currentColor`, round joins. No icon font, no
emoji, no external request of any kind.

## The nets

Five authored SVG diagrams, inline in the markup so CSS can reach their internals.

- **N1, the delivery net** - five stages from raw input to `harness-view`, wide above 56rem and
  vertical below. Each node carries a designator, a name, a sub-line and a tap naming what the
  stage writes to disk.
- **N2, the tailor** - contract and codebase feeding one junction that emits roster, skills and
  rules, over the 16 seat pads the roster resolves against.
- **N3, the control route** - a request descending through five layers to a result, with a bar that
  closes across the route at whichever layer refuses it.
- **N4, the routing tier** - one change fanning into three alternative lanes, Direct, Standard and
  Guarded, converging on the branch gate and one reviewed MR. Unlike N1 and N3 the picker chooses
  *between* lanes rather than *along* a run, so exactly one lane lights. The gate and the MR below
  it stay live under every tier: lighting the result while leaving the gate between it dark read as
  a change that reached the MR without passing the gate, which is the one thing this drawing must
  not say.
- **N5, the viewer route** - `.claude/` on disk into `scan`, out to `serve`, `assess` and `watch`,
  and back to disk through the one same-origin write-back door. It carries no picker, so it ships
  energized (`style="--on:1"`) like N2.

Each net is `aria-hidden`; the accessible content is the picker plus the readout, which states in
words everything the drawing states in colour. N5 has no picker, so its figcaption carries the
whole statement.

Japanese needs its own labels inside a net, not a translation dropped in: a CJK glyph is full-width,
so "owning agent" at 12 narrow characters became 8 full ones and ran into the box edge. The
Japanese N4 uses shorter labels and gives the orchestrator its long name back in the readout beside
the drawing.

## Where the motion practice came from

Recorded because it is not in this repository and a future change to the nets will want it.
`impeccable` is vendored at `.claude/skills/impeccable/` and travels with a clone; the motion
practice does not, and was installed as a plugin:

```bash
claude plugin marketplace add iart-ai/web-animation-skills
claude plugin install web-animation-skills@web-animation-skills
```

Four of its skills shaped what is here: `svg-animation` (the nets are authored inline SVG, drawn
with the `pathLength="1"` normalisation so one scalar drives a whole route), `60fps-animation`
(transform and opacity only; the single non-composited property is `stroke-dashoffset`, fired
once per state change), `micro-interaction` (the 140 to 260 ms band, and the copy control's
idle-copied-idle cycle), and `accessible-animation` (durations collapse rather than vanish, so
states land instead of teleporting halfway). `glassmorphism` and `ascii-animation` were read and
deliberately not used: the first failed contrast over scrolling content, the second fought the
drawn schematic.

## Motion

One idiom, everywhere: **a signal travels the net**. Two registered custom properties carry it.
`--on` (0 to 1) is set by `:has()` on every group up to the selected stage; every derived property
reads it, so one transition on the scalar drives node fill, node stroke, label ink and the
`stroke-dashoffset` that draws a route segment on. `pathLength="1"` normalizes every path, so one
expression serves a 16-unit stub and a 300-unit run alike. A per-level `--i` staggers segment
before node, which is what makes a jump from the first stage to the last read as one run down the
net rather than five things changing at once. `--blk` does the same job for a refusal, and the bar
that closes across the route is a `transform: scaleX()` on the compositor.

Everything else is micro-interaction in the 140-260ms band: a 1px lift and a border change on
hover, a scale-down on press, a dot that grows when a control is selected.

Under `prefers-reduced-motion: reduce` the durations collapse to `0.01ms` and the delays to `0`, so
every state still lands and nothing teleports halfway. Verified by driving the page with the
preference emulated: selecting the last stage leaves all eight route segments at `stroke-dashoffset:
0`, blocking a request leaves `--blk: 1` with the bar at full scale, and the roster preset lights
15 of the 16 seats - and each of those states is also written in the readout, so nothing depends on
having seen the movement.

## Browser surfaces

Selection, scrollbars (track and thumb), caret, accent colour, focus rings (`:focus-visible`, 2px,
3px offset), underline offset and tabular numerals are all themed from the palette.

## Script

`src/main.js` is the only script and no flow depends on it. It adds a copy control to each install
listing, and only once `navigator.clipboard.writeText` is known to exist, so a button that could not
work is never drawn. Its labels follow the page language.

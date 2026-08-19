# Design

Recorded from the built pages (`index.html`, `index.ja.html`, `src/style.css`), not from intention.
The direction contract sits at the top of each page body and survives the production build.

## The world

A normative specification sheet, printed as a two-ink press run. The product's argument is that a
claim must be checkable, so the surface is the artifact that makes claims checkable: numbered
clauses, ruled provisions, figures issued as numbered plates, and a proof table whose third column
is the script the number comes from.

What it refuses: the developer-tool arrangement of a gradient hero over three identical feature
cards. There is no card in this system. There is no gradient, no glass, no glow, and no shadow
except one soft drop under the contents panel.

## Ink

Two inks and a ground. Dark is the base declaration; a machine that asks for light gets the same
run on paper stock (`@media (prefers-color-scheme: light)`). Every surface paints its background
explicitly, so the page holds on any host.

| Token | Dark (base) | Light | Role |
|---|---|---|---|
| `--ground` | `#121110` | `#f1f1ef` | the stock |
| `--ground-raised` | `#1a1917` | `#e6e6e3` | contents panel |
| `--ground-sunk` | `#0b0a0a` | `#dfdfdb` | listings, plate mats |
| `--ink` | `#f2eee7` | `#17181a` | body and headings |
| `--ink-2` | `#bcb5a8` | `#474a4d` | secondary prose |
| `--ink-3` | `#948c80` | `#5f6265` | labels, provenance |
| `--spot` | `#e8563c` | `#ac3418` | the one saturated ink |
| `--spot-quiet` | `#a63a26` | `#8d2c14` | rules and marks, never text |
| `--rule` | `#35322d` | `#c9cac7` | hairlines |
| `--rule-strong` | `#565048` | `#a3a5a3` | opening rules |
| `--edge` | `#736b5e` | `#7f8285` | control boundaries and scrollbars |

Every text pair clears WCAG AA against its own ground (lowest measured: 4.59:1). `--edge` clears
3:1 for non-text boundaries. The spot ink is spent on exactly six things: the verb in the headline,
clause numbers, provision roles and step tags, the primary action's fill, list markers, and the
first swatch of the colophon register mark. A third colour would end the world.

## Type

- **`--serif` (`--body`)**: Andada Pro, vendored as three unicode-range subsets in `src/fonts/`,
  variable weight 400-840, OFL 1.1 (`public/OFL-AndadaPro.txt`). Already the presentation deck's
  face, so the site and the deck read as one press.
- **`--mono`**: the platform mono stack, used only where there is a value: figures, listings,
  clause numbers, field labels, plate numbers, controls.
- Japanese sets Andada Pro over a mincho stack (`Hiragino Mincho ProN`, `Yu Mincho`,
  `Noto Serif JP`) at 1.85 leading with no Latin tracking games.

Five fluid steps, `--t--1` through `--t-3`, all `clamp()`. Display tracking is `-0.025em`; the
floor is `-0.04em`. Measure is `--measure: 52ch` (about 70 rendered characters in this face);
Japanese prose is capped in `em`.

## Space and the sheet

`--s-1` through `--s-4`, all `clamp()`. One rhythm throughout, with more space above a heading
than below it.

The sheet is `max-width: 74rem` with `padding-inline: var(--gutter)`, where
`--gutter: max(1.25rem, env(safe-area-inset-left, 0px))`. No other rule sets padding-inline on a
`.sheet`, so the gutter has no path to zero. Above 64rem a clause becomes a two-column grid whose
first column is the document margin holding the clause number.

## Components

- **`.titleblock`** - sticky, hairline-bottomed: mark, document code, then the tools.
- **`.idx`** - the contents, a `<details>` at every width, so it works with no script. The panel
  is absolute under the masthead, `display: none` when closed. Below 40rem the outbound links move
  into the panel and the summary keeps its icon.
- **`.record`** - four ruled document-control fields; the gated `<b>v1.14.0</b>` badge lives here.
- **`.provisions` / `.provision`** - ruled rows, designator column and body. Never a card.
- **`.plate`** - a figure with a numbered caption; long alt text is product content.
- **`.data`** - the proof table: figure, what it measures, where it comes from.
- **`.scroller`** - every listing and every table sits inside one, `overflow-x: auto`,
  `tabindex="0"`, `role="region"` with a label, and the padding on the region rather than the
  content.
- **`.action`** - 46px, mono, tracked; one filled in the spot ink per page.

Icons are authored inline SVG symbols, 1.6 stroke, `currentColor`, round joins. No icon font, no
emoji, no external request of any kind.

## Motion

One authored moment: the contents panel unfolds (`opacity` and a 0.5rem rise,
`cubic-bezier(0.16, 1, 0.3, 1)`, 260ms) and its chevron turns. Nothing else animates, nothing
enters on scroll, and `prefers-reduced-motion` reduces both to nothing.

## Browser surfaces

Selection, scrollbars (track and thumb), focus rings (`:focus-visible`, 2px, 3px offset),
underline colour and offset, and tabular numerals are all themed from the palette.

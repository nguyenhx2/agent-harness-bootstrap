# Explainer clips

Six explainer clips for **Agent Harness Bootstrap**, each delivered as an MP4 (rendered with Manim)
and a self-contained HTML animation. Core message across all six:

> Give an AI agent a repo it can actually understand, and a harness it cannot escape.

Every claim is taken from `README.md` and `docs/FLOWS.md`. Nothing is invented.

**Watch online** (plays in the browser, no download): <https://nguyenhx2.github.io/agent-harness-bootstrap/video/>
The clips are served by GitHub Pages, and [`index.html`](index.html) is the gallery that embeds all six.

Every clip is captioned, because playback is muted by default. A viewer with no audio can follow the
whole clip from the burned-in captions alone.

## The set

Start with **04 solution** - it is the whole product in one clip. The other five go deeper.

| Clip | Length | MP4 (1080p) | HTML | What it says |
|---|---:|---|---|---|
| **04 solution** (start here) | ~54s | [`mp4/04-solution.mp4`](mp4/04-solution.mp4) | [`html/04-solution.html`](html/04-solution.html) | The complete solution: four pain points (invented requirements, lost work on compaction, one unsafe turn, an inherited bill), then spec-builder writing the contract, harness-bootstrap building the harness, the delivery loop running inside it, and the payoff. Each pain visibly flips from red to green as its fix lands. |
| 01 overview | ~33s | [`mp4/01-overview.mp4`](mp4/01-overview.mp4) | [`html/01-overview.html`](html/01-overview.html) | What it is and why: an unconstrained agent hallucinates, forgets on compaction, and bills at the top tier; two skills build a harness; the result ports to Claude Code, Cursor, Codex. |
| 02 flow | ~29s | [`mp4/02-flow.mp4`](mp4/02-flow.mp4) | [`html/02-flow.html`](html/02-flow.html) | The operating flow: spec-builder writes the contract, harness-bootstrap reads the code and scaffolds in ~0.2s, then the task loop dispatches scoped agents, hooks block bad actions, and the on-disk board survives a crash. |
| 03 layers | ~31s | [`mp4/03-layers.mp4`](mp4/03-layers.mp4) | [`html/03-layers.html`](html/03-layers.html) | The control layers: deny list, hooks, path-scoped rules, review gates. The guardrails are shell scripts and glob rules, so Opus to Haiku is byte-identical safety. State lives on disk. Ports with enforcement. |
| 05 spec-builder | ~58s | [`mp4/05-spec-builder.mp4`](mp4/05-spec-builder.mp4) | [`html/05-spec-builder.html`](html/05-spec-builder.html) | spec-builder in depth, mirroring [`docs/FLOWS.md`](../docs/FLOWS.md) diagram 5: raw input, elicit, confirm the FR list FIRST, scaffold the 13 sections, fill in order, traceability check, and the rule that nothing is invented - anything unstated becomes a flagged AS-nn or OI-nn. |
| 06 harness-bootstrap | ~59s | [`mp4/06-harness-bootstrap.mp4`](mp4/06-harness-bootstrap.mp4) | [`html/06-harness-bootstrap.html`](html/06-harness-bootstrap.html) | harness-bootstrap in depth, mirroring [`docs/FLOWS.md`](../docs/FLOWS.md) diagram 2: mode, the mandatory codebase analysis and Inventory Report, intake plus the tool questionnaire, a roster with explicit model and effort, the scaffold reporting ADDED / KEPT / CONFLICT without ever clobbering, then orchestration wiring. |

Lengths are rounded from `ffprobe`; re-check them with the probe command below.

## The README GIF

`gif/04-solution.gif` is the flagship clip as a looping GIF, embedded directly in `README.md` and
`README.ja.md`. It exists because **GitHub's markdown sanitiser strips `<video>` tags**: a `<video>`
in a README renders as an empty paragraph, whatever the `src` points at. An animated GIF is the only
way to get a moving picture to play inline on the README page itself.

Regenerate it from the MP4 (palette-optimised, two passes, ~2.4 MB):

```bash
ffmpeg -y -i video/mp4/04-solution.mp4 \
  -vf "fps=12,scale=720:-1:flags=lanczos,palettegen=stats_mode=diff:max_colors=128" \
  pal.png
ffmpeg -y -i video/mp4/04-solution.mp4 -i pal.png \
  -lavfi "fps=12,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4" \
  -loop 0 video/gif/04-solution.gif
```

Keep it well under 5 MB. `fps=12` and `scale=720` are the smallest settings that keep the burned-in
captions legible.

## Color grammar (color = meaning, never reassigned)

- **green** (`#2D6A4F` / `#52B788`) - deterministic / free / the harness / control
- **purple** (`#5A189A` / `#9D4EDD`) - the AI model / agent / billed tokens
- **red** (`#9D0208`) - guardrail / a blocked action
- **blue** (`#1D3557` / `#A8DADC`) - the human
- **neutral** (`#495057` / near-white `#F8F9FA`) - artifacts / files

Dark background (`#12141a`). Clean, technical, calm. No emoji. No em-dashes.

## Regenerate

Everything uses `py -3.13` (Manim 0.20.1). Do not use bare `python`.

```bash
# Scene sources live in video/src/ (shared palette in video/src/theme.py).
# Iterate at medium quality to catch layout/timing:
py -3.13 -m manim -qm --format mp4 --media_dir video/media -o 04-solution video/src/04-solution.py Solution

# Final 1080p renders:
py -3.13 -m manim -qh --format mp4 --media_dir video/media -o 01-overview video/src/01-overview.py Overview
py -3.13 -m manim -qh --format mp4 --media_dir video/media -o 02-flow     video/src/02-flow.py     Flow
py -3.13 -m manim -qh --format mp4 --media_dir video/media -o 03-layers   video/src/03-layers.py   Layers
py -3.13 -m manim -qh --format mp4 --media_dir video/media -o 04-solution video/src/04-solution.py Solution
py -3.13 -m manim -qh --format mp4 --media_dir video/media -o 05-spec-builder video/src/05-spec-builder.py SpecBuilder
py -3.13 -m manim -qh --format mp4 --media_dir video/media -o 06-harness-bootstrap video/src/06-harness-bootstrap.py HarnessBootstrap

# Then copy each result out of the gitignored media/ scratch dir, e.g.:
cp video/media/videos/04-solution/1080p60/04-solution.mp4 video/mp4/04-solution.mp4
```

`video/media/` is gitignored build scratch; only `video/mp4/`, `video/gif/` and `video/html/` ship.

The HTML files in `video/html/` are hand-written, fully self-contained (inline CSS/JS/SVG, no external
fonts or CDNs), and loop on their own; just open one in a browser.

## Verify

```bash
# MP4: sane duration + resolution
ffprobe -v error -show_entries format=duration -show_entries stream=width,height video/mp4/04-solution.mp4

# HTML: confirm nothing loads from the network (should print nothing)
grep -rniE 'https?://|cdn' video/html/

# No em-dashes anywhere (should print nothing). U+2014 by escape, so this
# check does not itself contain the character it is looking for.
grep -rnP '\x{2014}' video/src/ video/html/ video/README.md
```

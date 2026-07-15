# Intro clips

Three short intro clips for **Agent Harness Bootstrap**, each delivered as an MP4 (rendered with
Manim) and a self-contained HTML animation. Core message across all three:

> Give an AI agent a repo it can actually understand, and a harness it cannot escape.

Every claim is taken from `README.md` and `docs/FLOWS.md`. Nothing is invented.

**Watch online** (plays in the browser, no download): <https://nguyenhx2.github.io/agent-harness-bootstrap/video/>
The clips are served by GitHub Pages, and [`index.html`](index.html) is the gallery that embeds all six.

## The six files

| Clip | MP4 (1080p) | HTML | What it says |
|---|---|---|---|
| 01 overview | [`mp4/01-overview.mp4`](mp4/01-overview.mp4) | [`html/01-overview.html`](html/01-overview.html) | What it is and why: an unconstrained agent hallucinates, forgets on compaction, and bills at the top tier; two skills build a harness; the result ports to Claude Code, Cursor, Codex. |
| 02 flow | [`mp4/02-flow.mp4`](mp4/02-flow.mp4) | [`html/02-flow.html`](html/02-flow.html) | The operating flow: spec-builder writes the contract, harness-bootstrap reads the code and scaffolds in ~0.2s, then the task loop dispatches scoped agents, hooks block bad actions, and the on-disk board survives a crash. |
| 03 layers | [`mp4/03-layers.mp4`](mp4/03-layers.mp4) | [`html/03-layers.html`](html/03-layers.html) | The control layers: deny list, hooks, path-scoped rules, review gates. The guardrails are shell scripts and glob rules, so Opus to Haiku is byte-identical safety. State lives on disk. Ports with enforcement. |

Durations and resolution are listed in the parent report and can be re-checked with the probe command
below.

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
py -3.13 -m manim -qm --format mp4 video/src/01-overview.py Overview
py -3.13 -m manim -qm --format mp4 video/src/02-flow.py    Flow
py -3.13 -m manim -qm --format mp4 video/src/03-layers.py  Layers

# Final 1080p render, then copy out of the gitignored media/ scratch dir:
py -3.13 -m manim -qh --format mp4 video/src/01-overview.py Overview
py -3.13 -m manim -qh --format mp4 video/src/02-flow.py    Flow
py -3.13 -m manim -qh --format mp4 video/src/03-layers.py  Layers
cp media/videos/01-overview/1080p60/Overview.mp4 video/mp4/01-overview.mp4
cp media/videos/02-flow/1080p60/Flow.mp4         video/mp4/02-flow.mp4
cp media/videos/03-layers/1080p60/Layers.mp4     video/mp4/03-layers.mp4
```

The HTML files in `video/html/` are hand-written, fully self-contained (inline CSS/JS/SVG, no external
fonts or CDNs), and loop on their own; just open one in a browser.

## Verify

```bash
# MP4: sane duration + resolution
ffprobe -v error -show_entries format=duration -show_entries stream=width,height video/mp4/01-overview.mp4

# HTML: confirm nothing loads from the network (should print nothing)
grep -rniE 'https?://|cdn' video/html/
```

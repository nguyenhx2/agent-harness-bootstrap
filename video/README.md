# Explainer clips

A narrated introduction and seven explainer clips for **Agent Harness Bootstrap**. The seven are each
delivered as an MP4 (rendered with Manim) and a self-contained HTML animation; the introduction is a
Remotion composition with an ElevenLabs voice, music bed and sound effects. Core message across all
eight:

> Give an AI agent a repo it can actually understand, and a harness it cannot escape.

Every claim is taken from `README.md` and `docs/FLOWS.md`. Nothing is invented.

**Watch online** (plays in the browser, no download): <https://nguyenhx2.github.io/agent-harness-bootstrap/video/>
The clips are served by GitHub Pages, and [`index.html`](index.html) is the gallery that embeds all seven.

Every clip is captioned, because playback is muted by default. A viewer with no audio can follow the
whole clip from the burned-in captions alone.

## The set

Start with **00 intro** - the narrated introduction. Then **04 solution**, the whole product in one
clip. The other six go deeper.

| Clip | Length | MP4 (1080p) | HTML | What it says |
|---|---:|---|---|---|
| **00 intro** (start here, narrated) | ~134s (JA ~149s) | [`mp4/00-intro.mp4`](mp4/00-intro.mp4), JA [`mp4/ja/00-intro.mp4`](mp4/ja/00-intro.mp4) | - | The soul line, then the seven questions from the README's "The problems it solves", each drawn as a pain-point bubble followed by the mechanism that answers it: a team that fits (purpose profiles, a roster of 3 to 17 of the 18 seats sized from the real modules); safe without waste (hooks that block in the shell, a force push to main refused by default, the guardrail eval per hook flavour on a strict scaffold, verify-plan, the verification ledger, bounded review rounds, effort and caps per seat); keys (protect-secrets, env-read redaction, /secret-scan, and the `hooks_strict` guards named as such); the agentic loop with ceremony matched to the tier; spec-builder's confirmation sheet and index; harness-view's live graph, toggles and run history; and `harness-view assess` turning a vague score into a worklist with one-click fixes, a since-last-check diff and a published rubric. Voiced in English and in Japanese, with music, captions burned in for each language. Scripts: [`intro/SCRIPT.md`](intro/SCRIPT.md), [`intro/SCRIPT.ja.md`](intro/SCRIPT.ja.md). |
| **04 solution** (start here) | ~63s | [`mp4/04-solution.mp4`](mp4/04-solution.mp4) | [`html/04-solution.html`](html/04-solution.html) | The complete solution: four pain points (invented requirements, lost work on compaction, one unsafe turn, an inherited bill), then spec-builder writing the contract, harness-bootstrap building the harness, the delivery loop running inside it, and the payoff. Each pain visibly flips from red to green as its fix lands. Closes on the question harness-view exists to answer - how do you know it is actually wired right - and the scores it gave three real harnesses. |
| 01 overview | ~34s | [`mp4/01-overview.mp4`](mp4/01-overview.mp4) | [`html/01-overview.html`](html/01-overview.html) | What it is and why: an unconstrained agent hallucinates, forgets on compaction, and bills at the top tier; two skills build a harness; the result ports to Claude Code, Cursor, Codex. |
| 02 flow | ~31s | [`mp4/02-flow.mp4`](mp4/02-flow.mp4) | [`html/02-flow.html`](html/02-flow.html) | The operating flow: spec-builder writes the contract, harness-bootstrap reads the code and scaffolds in ~0.2s, then small work stays in the main session while Guarded work goes to the orchestrator and its scoped agents, hooks block bad actions, and the on-disk board survives a crash. |
| 03 layers | ~32s | [`mp4/03-layers.mp4`](mp4/03-layers.mp4) | [`html/03-layers.html`](html/03-layers.html) | The control layers: deny list, hooks, the spawn boundary, path-scoped rules, review gates. The guardrails are shell scripts and glob rules: no model is consulted when a hook decides, so swapping Opus for Haiku leaves the result unchanged. State lives on disk. Ports with enforcement. |
| 05 spec-builder | ~60s | [`mp4/05-spec-builder.mp4`](mp4/05-spec-builder.mp4) | [`html/05-spec-builder.html`](html/05-spec-builder.html) | spec-builder in depth, mirroring [`docs/FLOWS.md`](../docs/FLOWS.md) diagram 5: raw input, elicit, confirm the FR list FIRST, scaffold the selected sections - the core six always, fill in order, traceability check, and the rule that nothing is invented - anything unstated becomes a flagged AS-nn or OI-nn. |
| 06 harness-bootstrap | ~68s | [`mp4/06-harness-bootstrap.mp4`](mp4/06-harness-bootstrap.mp4) | [`html/06-harness-bootstrap.html`](html/06-harness-bootstrap.html) | harness-bootstrap in depth, mirroring [`docs/FLOWS.md`](../docs/FLOWS.md) diagram 2: mode, the mandatory codebase analysis and Inventory Report, intake plus the tool questionnaire, a roster with explicit model and effort, skills matched to the detected stack and reviewed before they are ever suggested, wired in once you choose them, the scaffold reporting ADDED / KEPT / CONFLICT without ever clobbering, orchestration wiring, and building the maps: the module-boundary map, the docs orphan check and the harness graph with its HTML export. |
| 07 skills and view | ~44s | [`mp4/07-skills-and-view.mp4`](mp4/07-skills-and-view.mp4) | [`html/07-skills-and-view.html`](html/07-skills-and-view.html) | The operating flow of [`docs/assets/harness-overview.svg`](../docs/assets/harness-overview.svg) end to end, then the step most kits skip - a roster of 3 to 17 of the 18 seats derived from the contract and the real modules, rather than everything installed up front - then the three mechanisms that keep it honest and the problem each one solves: Skill Discovery reads this project's manifests to find skills matching its stack, Skill Wire connects a chosen skill to the agent seat that needs it, and harness-view answers whether any of it is actually wired right. |

Lengths are rounded from `ffprobe`; re-check them with the probe command below.

## The README GIF

`gif/00-intro.gif` (with `gif/00-intro-poster.png` as its still) is the intro as a looping GIF, and
`gif/ja/00-intro.gif` (with `gif/ja/00-intro-poster.png`) is the Japanese one that `README.ja.md`
embeds. Both are rendered by `intro/render.sh` at 640 wide and 8 fps, which keeps the captions
legible and each file under 5 MB.

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

## The intro: Remotion and ElevenLabs

`video/intro/` is a Remotion project (`package.json` pins exact versions; `node_modules/` and `out/`
are gitignored). It needs node 22, ffmpeg and Python 3.13.

- **`SCRIPT.md` is the single source** of the English clip, and `SCRIPT.ja.md` of the Japanese one
  (same scene ids, same order; the timing build refuses scripts that disagree). Each `##` heading is
  a scene and each `-` line is one caption cue. The narration sent to the voice is the cues joined
  with a space, so a caption can never say what the voice does not. The narration speaks no counts.
- **Pain point, then answer.** The first cue of each question scene is drawn as a speech bubble
  from the viewer, which docks to the top while the answer plays. Icons are
  [Heroicons](https://github.com/tailwindlabs/heroicons) v2.2.0 (MIT, Tailwind Labs), vendored as
  path data in `intro/src/icons.ts` with the licence beside it.
- **Figures on screen are derived.** `derive_figures.py` reads them with the same helpers
  `scripts/check_numbers.py` uses (plus the tier table, `PURPOSE_FLAGS` and `CAPTURED.json`) into
  `src/figures.json` and a generated block at the foot of both scripts, which `check_numbers.py`
  polices like any other document. `derive_figures.py --check` fails when either is stale.
- **The audio is generated once and cached** in `video/intro/audio/`: the English and Japanese
  narration with their character alignment (`POST /v1/text-to-speech/{voice_id}/with-timestamps`,
  `eleven_multilingual_v2`; a native Japanese narrator from the voice library for JA), the music bed
  (`POST /v1/music`) and three sound effects (`POST /v1/sound-generation`). `audio/ASSETS.json`
  records every prompt and setting. `scripts/build-timing.mjs` turns the alignment into the caption
  and scene timing, and refuses to run if a script no longer matches the recorded narration. The
  Japanese voice is played at tempo 1.12 (`atempo`, pitch kept; `TEMPO` in `scripts/script.mjs`) and
  its caption times are divided by the same factor.
- **The music ducks under the voice** by a gain curve computed from the alignment's speech runs, and
  the final mix is loudness-normalised to -16 LUFS.

```bash
bash video/intro/render.sh                              # re-render from the cached audio; no API call
bash video/intro/render.sh --generate voice en --force  # after editing an English cue: new narration
```

`--generate` is the only path that calls ElevenLabs. It reads `ELEVENLABS_API_KEY` from the
environment or the repository's `.env` (gitignored), sends it only in the request header, and never
prints or writes it. `render.sh` ends by recording the provenance of all six artifacts in
`video/RENDERED.json`: the English three come from `video/intro/SCRIPT.md`, the Japanese three from
`video/intro/SCRIPT.ja.md`.

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

## After every render: record the provenance

Figures inside a clip are burned into pixels, so `check_numbers.py` cannot see them. It reads text,
and it does check `video/src/**.py` - but nothing connected a SOURCE that was right to an ARTIFACT
that was stale. `gif/04-solution.gif` read "guardrail eval 69/69" on the README for three releases
while its own scene source said 107/107; the number had moved twice and the GIF was re-rendered for
neither.

`video/RENDERED.json` closes that gap: it stores the sha256 of the scene source each shipped clip
was last rendered from, and `scripts/check_media.py` fails CI when a source has moved on without
its artifact. So a render is not finished until you record it:

```bash
py -3.13 scripts/check_media.py --update video/mp4/04-solution.mp4 video/gif/04-solution.gif
py -3.13 scripts/check_media.py          # must print "ok"
```

It deliberately does NOT hash `theme.py` / `jatheme.py`. Those change every frame of all fourteen
clips, and demanding a full re-render for one colour tweak would get the gate switched off. A
palette change cannot make a published number false, which is the failure this gate exists to stop.
After a theme change, re-render deliberately and update every entry.

## Verify

```bash
# MP4: sane duration + resolution
ffprobe -v error -show_entries format=duration -show_entries stream=width,height video/mp4/04-solution.mp4

# HTML: confirm nothing loads from the network (should print nothing)
grep -rniE 'https?://|cdn' video/html/

# No em-dashes anywhere (should print nothing). U+2014 by escape, so this
# check does not itself contain the character it is looking for.
grep -rnP '\x{2014}' video/src/ video/html/ video/README.md video/intro/SCRIPT.md video/intro/SCRIPT.ja.md video/intro/src/
```

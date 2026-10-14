# Explainer clips

A narrated introduction and one explainer clip for **Agent Harness Bootstrap**. The introduction is
a Remotion composition with an ElevenLabs voice, music bed and sound effects; the explainer is
rendered with Manim and also ships as a self-contained HTML animation. Core message:

> Give an AI agent a repo it can actually understand, and a harness it cannot escape.

Every claim is taken from `README.md` and the files it links to. Nothing is invented.

**Watch online** (plays in the browser, no download): <https://nguyenhx2.github.io/agent-harness-bootstrap/video/>
The clips are served by GitHub Pages, and [`index.html`](index.html) is the gallery that embeds them.

Every clip is captioned, because playback is muted by default. A viewer with no audio can follow the
whole clip from the burned-in captions alone.

## The set

| Clip | Length | MP4 (1080p) | HTML | What it says |
|---|---:|---|---|---|
| **00 intro** (start here, narrated) | ~164s (JA ~167s) | [`mp4/00-intro.mp4`](mp4/00-intro.mp4), JA [`mp4/ja/00-intro.mp4`](mp4/ja/00-intro.mp4) | - | The soul line, then a framing beat - the questions teams putting agents on real work keep asking - and the seven questions from the README's "The problems it solves". Each is introduced by a short lead-in, asked in a speech bubble, and answered by the mechanism that handles it: a team that fits (purpose profiles, a roster sized from the real modules); safe without waste (hooks that block in the shell, a force push to main refused by default, the guardrail eval, verify-plan, the verification ledger, bounded review rounds, effort and caps per seat); keys (protect-secrets, env-read redaction, /secret-scan, and the `hooks_strict` guards named as such); the agentic loop with ceremony matched to the tier; spec-builder's confirmation sheet and index; harness-view's live graph, toggles and run history; and `harness-view assess` turning a vague score into a worklist with one-click fixes, a since-last-check diff and a published rubric. Voiced in English and in Japanese, with music, captions burned in for each language. Scripts: [`intro/SCRIPT.md`](intro/SCRIPT.md), [`intro/SCRIPT.ja.md`](intro/SCRIPT.ja.md). |
| 07 skills and view | ~44s | [`mp4/07-skills-and-view.mp4`](mp4/07-skills-and-view.mp4), JA [`mp4/ja/07-skills-and-view.mp4`](mp4/ja/07-skills-and-view.mp4) | [`html/07-skills-and-view.html`](html/07-skills-and-view.html) | What the intro leaves out. The operating flow of [`docs/assets/harness-overview.svg`](../docs/assets/harness-overview.svg) end to end, then a roster derived from the contract and the real modules rather than everything installed up front, then the mechanisms that keep it honest and the problem each one solves: Skill Discovery reads this project's manifests to find skills matching its stack, Skill Wire connects a chosen skill to the agent seat that needs it, and harness-view answers whether any of it is actually wired right. |

Lengths are rounded from `ffprobe`; re-check them with the probe command below.

### Retired clips

Clips 01 to 06 were removed in v1.21.0. 01 overview, 02 flow, 03 layers and 04 solution told the
story the intro now tells, in less detail. 05 spec-builder and 06 harness-bootstrap had drifted: 06
showed three modes where there are four and had no purpose profiles, and 05 drew seven always-on
spec sections while saying six. The clip numbers are kept, so `07` is still `07`.

## The README GIF

`gif/00-intro.gif` (with `gif/00-intro-poster.png` as its still) is the intro as a looping GIF, and
`gif/ja/00-intro.gif` (with `gif/ja/00-intro-poster.png`) is the Japanese one that `README.ja.md`
embeds. It exists because **GitHub's markdown sanitiser strips `<video>` tags**: an animated GIF is
the only way to get a moving picture to play inline on the README page itself. Both are rendered by
`intro/render.sh` at 640 wide and 8 fps, which keeps the captions legible and each file under 5 MB.

## The intro: Remotion and ElevenLabs

`video/intro/` is a Remotion project (`package.json` pins exact versions; `node_modules/` and `out/`
are gitignored). It needs node 22, ffmpeg and Python 3.13.

- **`SCRIPT.md` is the single source** of the English clip, and `SCRIPT.ja.md` of the Japanese one
  (same scene ids, same order; the timing build refuses scripts that disagree). Each `##` heading is
  a scene and each `-` line is one caption cue. The narration sent to the voice is the cues joined
  with a space, so a caption can never say what the voice does not. The narration speaks no counts.
  It is written to be spoken: short sentences, contractions in English, plain spoken Japanese.
- **Lead-in, question, answer.** After the soul line, the `frame` scene says what is coming. Each
  question scene opens with a short lead-in line ("Next, safety and cost."), shown as a "question
  n of 7" card; then the quoted question is drawn as a speech bubble from the viewer, which docks
  to the top while the answer plays. The bubble's tail is anchored to the avatar and its text wraps
  inside a capped width, in both languages. Icons are
  [Heroicons](https://github.com/tailwindlabs/heroicons) v2.2.0 (MIT, Tailwind Labs), vendored as
  path data in `intro/src/icons.ts` with the licence beside it.
- **Figures on screen are derived.** `derive_figures.py` reads them with the same helpers
  `scripts/check_numbers.py` uses (plus the tier table, `PURPOSE_FLAGS` and `CAPTURED.json`) into
  `src/figures.json` and a generated block at the foot of both scripts, which `check_numbers.py`
  polices like any other document. `derive_figures.py --check` fails when either is stale.
- **The audio is generated once and cached** in `video/intro/audio/`: the English and Japanese
  narration with their character alignment (`POST /v1/text-to-speech/{voice_id}/with-timestamps`),
  the music bed (`POST /v1/music`) and three sound effects (`POST /v1/sound-generation`). The
  voices are two women from the ElevenLabs voice library, tagged conversational: Elise for English,
  Kaori, a native Japanese speaker, for Japanese. The generator tries `eleven_v3` first and falls
  back to `eleven_multilingual_v2` (the key cannot list models, so it asks by trying).
  `audio/ASSETS.json` records the voice, the model that answered, every setting and every prompt.
- **Pacing is edited, never sped up.** The voice plays at its own tempo. `scripts/build-timing.mjs`
  finds the silences in the cached narration with ffmpeg, shortens any pause longer than 0.55 s,
  and splits the narration at every scene boundary so the next scene starts a little later and the
  music can come up in between. Every cut falls inside silence, and every caption goes through the
  same time map as the audio it belongs to. Caption starts and ends are snapped to the detected
  edges of the speech, not just the character alignment. The build refuses to run if a script no
  longer matches the recorded narration, or if the music bed is shorter than the clip.
- **The music sits a fixed distance under the voice.** The timing build measures the loudness of
  the voice and of the bed, and sets the music 9 LU under the voice while it speaks and 3 LU under
  it in the gaps, the open and the close; it is never silent. The bed's own build and fall is
  flattened per second from its short-term loudness. The final mix is loudness-normalised to
  -16 LUFS. `node scripts/measure-mix.mjs` renders the voice and the music as separate stems and
  prints both per scene, so the balance can be checked rather than assumed.

```bash
bash video/intro/render.sh                              # re-derive figures, re-time, re-render; no API call
bash video/intro/render.sh --generate voice en --force  # after editing an English cue: new narration
node video/intro/scripts/measure-mix.mjs                # music vs voice, per scene
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

## Regenerate the Manim clip

Everything uses `py -3.13` (Manim 0.20.1). Do not use bare `python`.

```bash
# Scene sources live in video/src/ (shared palette in video/src/theme.py), Japanese in video/src/ja/.
bash video/render-all.sh

# Then copy each result out of the gitignored media/ scratch dir:
cp video/media/videos/07-skills-and-view/1080p60/07-skills-and-view.mp4    video/mp4/07-skills-and-view.mp4
cp video/media/videos/07-skills-and-view/1080p60/07-skills-and-view.ja.mp4 video/mp4/ja/07-skills-and-view.mp4
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
py -3.13 scripts/check_media.py --update video/mp4/07-skills-and-view.mp4 video/mp4/ja/07-skills-and-view.mp4
py -3.13 scripts/check_media.py          # must print "ok"
```

It deliberately does NOT hash `theme.py` / `jatheme.py`. Those change every frame of every Manim
clip, and demanding a full re-render for one colour tweak would get the gate switched off. A
palette change cannot make a published number false, which is the failure this gate exists to stop.
After a theme change, re-render deliberately and update every entry.

## Verify

```bash
# MP4: sane duration + resolution
ffprobe -v error -show_entries format=duration -show_entries stream=width,height video/mp4/00-intro.mp4

# HTML: confirm nothing loads from the network (should print nothing)
grep -rniE 'https?://|cdn' video/html/

# No em-dashes anywhere (should print nothing). U+2014 by escape, so this
# check does not itself contain the character it is looking for.
grep -rnP '\x{2014}' video/src/ video/html/ video/README.md video/intro/SCRIPT.md video/intro/SCRIPT.ja.md video/intro/src/
```

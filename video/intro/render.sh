#!/usr/bin/env bash
# Render the 00-intro clip, in English and Japanese, from the cached audio. No API call unless
# --generate is passed.
#
#   bash video/intro/render.sh                      # derive figures, time captions, render, encode
#   bash video/intro/render.sh --generate [voice|music|sfx|all] [en|ja] [--force]
#                                                   # call ElevenLabs first (costs credit; cached
#                                                   # assets are skipped unless --force)
#
# Writes, per language, the 1080p MP4, the README GIF and its poster:
#   en: video/mp4/00-intro.mp4     video/gif/00-intro.gif     video/gif/00-intro-poster.png
#   ja: video/mp4/ja/00-intro.mp4  video/gif/ja/00-intro.gif  video/gif/ja/00-intro-poster.png
# then records their provenance in video/RENDERED.json. Needs node 22, ffmpeg and Python 3.13.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

if command -v py >/dev/null 2>&1; then PY=(py -3.13); else PY=(python3); fi

if [ "${1:-}" = "--generate" ]; then
  shift
  node scripts/generate-audio.mjs "$@"
fi

[ -d node_modules ] || npm ci --no-audit --no-fund

# Figures first: they may have moved in the repo since the last render. Then the timing, which also
# measures the cached voice and music to set the mix. Neither calls an API.
"${PY[@]}" derive_figures.py >/dev/null
node scripts/build-timing.mjs
mkdir -p out

LN="I=-16:TP=-1.5:LRA=11"
ARTIFACTS=()
for LANG_ in en ja; do
  if [ "$LANG_" = en ]; then COMP=Intro; SUB=""; else COMP=IntroJa; SUB="ja/"; fi
  O="out/$LANG_"
  mkdir -p "$O"

  # Poster: the end of the opening, where the whole idea is on screen at once.
  POSTER_FRAME=$(node -e "const t=require('./src/timing.$LANG_.json');const s=t.scenes.find(x=>x.id==='open');console.log(Math.round((s.end-0.4)*30))")
  npx remotion still src/index.ts "$COMP" "$O/poster.png" --frame="$POSTER_FRAME" --log=error
  npx remotion render src/index.ts "$COMP" "$O/raw.mp4" \
    --codec=h264 --crf=22 --x264-preset=slow --audio-bitrate=160k --log=error

  # Loudness: Remotion mixes at unity, which lands well under -16 LUFS. Two-pass linear loudnorm
  # lifts the whole mix by one constant gain, so the ducking shape is untouched; the picture is
  # copied, not re-encoded.
  ffmpeg -hide_banner -nostats -i "$O/raw.mp4" -af "loudnorm=$LN:print_format=json" -f null - \
    2> "$O/loudnorm.txt"
  MEASURED=$(node -e "
const t=require('fs').readFileSync('$O/loudnorm.txt','utf8');
const j=JSON.parse(t.slice(t.lastIndexOf('{'), t.lastIndexOf('}')+1));
console.log(['measured_I='+j.input_i,'measured_TP='+j.input_tp,'measured_LRA='+j.input_lra,
  'measured_thresh='+j.input_thresh,'offset='+j.target_offset].join(':'));")
  ffmpeg -v error -y -i "$O/raw.mp4" -c:v copy -c:a aac -b:a 160k -ar 48000 \
    -af "loudnorm=$LN:$MEASURED:linear=true" -movflags +faststart "$O/00-intro.mp4"

  # README GIF: GitHub strips <video>, so a palette-optimised GIF is the only moving picture that
  # plays inline. 640 wide at 8 fps keeps the burned-in captions legible and the file under 5 MB
  # for a clip this long.
  ffmpeg -v error -y -i "$O/00-intro.mp4" \
    -vf "fps=8,scale=640:-1:flags=lanczos,palettegen=stats_mode=diff:max_colors=96" "$O/pal.png"
  ffmpeg -v error -y -i "$O/00-intro.mp4" -i "$O/pal.png" \
    -lavfi "fps=8,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
    -loop 0 "$O/00-intro.gif"

  mkdir -p "$ROOT/video/mp4/$SUB" "$ROOT/video/gif/$SUB"
  cp "$O/00-intro.mp4" "$ROOT/video/mp4/${SUB}00-intro.mp4"
  cp "$O/00-intro.gif" "$ROOT/video/gif/${SUB}00-intro.gif"
  cp "$O/poster.png" "$ROOT/video/gif/${SUB}00-intro-poster.png"
  ARTIFACTS+=("video/mp4/${SUB}00-intro.mp4" "video/gif/${SUB}00-intro.gif" "video/gif/${SUB}00-intro-poster.png")
done

cd "$ROOT"
"${PY[@]}" scripts/check_media.py --update "${ARTIFACTS[@]}"
ls -l "${ARTIFACTS[@]}"

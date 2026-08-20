#!/usr/bin/env bash
# Re-render every clip, both languages, at 1080p.
#
# The scene sources are hashed into video/RENDERED.json, so a clip whose source changed but whose
# mp4 did not is a figure that lies in pixels - scripts/check_media.py exists because exactly that
# shipped once, a README GIF reading 69/69 for two releases after the number became 107/107.
# Run this after any change to video/src/, then regenerate the provenance file.
#
#   bash video/render-all.sh
set -u
cd "$(dirname "$0")/.." || exit 1

CLIPS="01-overview:Overview 02-flow:Flow 03-layers:Layers 04-solution:Solution
       05-spec-builder:SpecBuilder 06-harness-bootstrap:HarnessBootstrap 07-skills-and-view:SkillsAndView"

fail=0
for entry in $CLIPS; do
  name=${entry%%:*}
  scene=${entry##*:}
  for lang in "" "ja/"; do
    src="video/src/${lang}${name}.py"
    [ -f "$src" ] || continue
    out="${name}"
    [ -n "$lang" ] && out="${name}.ja"
    printf '  rendering %-28s ' "$out"
    if py -3.13 -m manim -qh --format mp4 --media_dir video/media -o "$out" "$src" "$scene" \
         >/dev/null 2>&1; then
      printf 'ok\n'
    else
      printf 'FAILED\n'
      fail=$((fail + 1))
    fi
  done
done

echo
printf '  failures: %s\n' "$fail"
[ "$fail" -eq 0 ] || exit 1

#!/usr/bin/env bash
# Build screenshots/demo.gif — an animated walkthrough of the SoundHub UI.
#
# Requires ImageMagick (convert). Usage: bash scripts/make_demo_gif.sh
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="screenshots/demo.gif"
WIDTH=1000
HOLD=150          # 1.5s hold per screenshot (centiseconds)
FADE=18           # crossfade frames between screenshots
FADE_DELAY=4      # 0.04s per crossfade frame (centiseconds)

shots=(
  "screenshots/main-light.png"
  "screenshots/repo-page.png"
  "screenshots/repo-page-branches.png"
  "screenshots/main-dark.png"
)

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# 1. Resize every screenshot to a work file.
for i in "${!shots[@]}"; do
  convert "${shots[$i]}" -resize "${WIDTH}x" -strip "$tmp/shot_$i.png"
done

# 2. Render crossfade frames between consecutive screenshots.
morph_files=()
for i in "${!shots[@]}"; do
  if [[ $i -lt $(( ${#shots[@]} - 1 )) ]]; then
    convert "$tmp/shot_$i.png" "$tmp/shot_$(( i + 1 )).png" \
      -morph "$FADE" "$tmp/morph_${i}_%02d.png"
    for f in "$tmp"/morph_${i}_*.png; do
      morph_files+=("$f")
    done
  fi
done

# 3. Assemble: hold shot → crossfade → hold next shot → … (loop forever).
args=(-loop 0)
for i in "${!shots[@]}"; do
  args+=(-delay "$HOLD" "$tmp/shot_$i.png")
  if [[ $i -lt $(( ${#shots[@]} - 1 )) ]]; then
    n=$(( FADE + 1 ))   # morph output = 2 originals + FADE intermediates
    for (( f = 1; f < n; f++ )); do
      args+=(-delay "$FADE_DELAY" "$tmp/morph_${i}_$(printf '%02d' "$f").png")
    done
  fi
done

convert "${args[@]}" -layers Optimize "$OUT"
echo "Wrote $OUT — $(identify -format '%n frames, %wx%h' "$OUT")"

#!/usr/bin/env bash
# Build screenshots/demo.gif — an animated walkthrough of the SoundHub UI.
#
# Every screenshot is centered on a neutral gray canvas with a thin border
# and a soft shadow, so the frames are uniform regardless of the page size.
#
# Requires ImageMagick (convert). Usage: bash scripts/make_demo_gif.sh
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="screenshots/demo.gif"
CANVAS_W=1280
CANVAS_H=800
SHOT_W=1180        # screenshot width on the canvas (16:9 → 1180x738)
BG="#DCDCDC"       # neutral gray backdrop
BORDER="#C6C6C6"
HOLD=160           # 1.6s hold per screenshot (centiseconds)
FADE=18            # crossfade frames between screenshots
FADE_DELAY=4       # 0.04s per crossfade frame (centiseconds)

shots=(
  "screenshots/main-light.png"
  "screenshots/projects.png"
  "screenshots/repo-page.png"
  "screenshots/repo-page-branches.png"
)

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# 1. Pad every screenshot onto the gray canvas.
for i in "${!shots[@]}"; do
  convert -size "${CANVAS_W}x${CANVAS_H}" xc:"$BG" \
    \( "${shots[$i]}" -resize "${SHOT_W}x" -strip \
       -bordercolor "$BORDER" -border 1 \
       \( +clone -background black -shadow 80x6+0+10 \) +swap \
       -background none -layers merge +repage \) \
    -gravity center -composite "$tmp/shot_$i.png"
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

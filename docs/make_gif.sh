#!/usr/bin/env bash
# Cut the README demo GIF from the demo video.
# Usage: ./docs/make_gif.sh demo.mp4 45 12   (input video, start second, duration in seconds)
set -euo pipefail
IN="$1"; START="${2:-0}"; DUR="${3:-12}"
ffmpeg -y -ss "$START" -t "$DUR" -i "$IN" \
  -vf "fps=12,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
  -loop 0 docs/demo.gif
ls -lh docs/demo.gif

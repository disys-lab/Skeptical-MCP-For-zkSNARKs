# docs

`task_completion.png` (the chart in the main README) is generated from the result files in `results/`.
To regenerate it from the repo root: `pip install -r docs/requirements-docs.txt && python docs/make_charts.py`.
The script checks every value against Table VI of the paper and stops with an error if one differs.

`make_gif.sh` cuts the demo GIF from a video: `./docs/make_gif.sh demo.mp4 <start-second> <duration>` (needs ffmpeg).

`demo.gif` is cut from the finished demo video (the bug, then step 2 with the fix), not from a raw recording, so `make_gif.sh` won't reproduce it. The command used:

```bash
ffmpeg -i skeptical-tools-demo.mp4 -filter_complex "[0:v]trim=20.6:26.2,setpts=PTS-STARTPTS[a];[0:v]trim=64.2:68.2,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1,fps=12,scale=960:-2:flags=lanczos,split[x][y];[x]palettegen=max_colors=128:stats_mode=diff[p];[y][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" -loop 0 docs/demo.gif
```
Keep the GIF under about 8 MB; if it is bigger, lower `fps` or `scale` in the script.

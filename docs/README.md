# docs

`task_completion.png` (the chart in the main README) is generated from the result files in `results/`.
To regenerate it from the repo root: `pip install -r docs/requirements-docs.txt && python docs/make_charts.py`.
The script checks every value against Table VI of the paper and stops with an error if one differs.

`make_gif.sh` cuts the demo GIF from a video: `./docs/make_gif.sh demo.mp4 <start-second> <duration>` (needs ffmpeg).
Keep the GIF under about 8 MB; if it is bigger, lower `fps` or `scale` in the script.

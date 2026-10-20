# docs

`task_completion.png` (the chart in the main README) is generated from the result files in `results/`.
To regenerate it from the repo root: `pip install -r docs/requirements-docs.txt && python docs/make_charts.py`.
The script checks every value against Table VI of the paper and stops with an error if one differs.

#!/usr/bin/env python3
"""Draw docs/task_completion.png from the released result files.

Task completion per model and configuration is computed from results/ with the same
grader and definitions as eval/reproduce_paper_numbers.py (grading_script.grade_config,
the 75-query suite, 5 runs). The values are checked against Table VI of the paper before
anything is drawn; the script exits with an error if any value differs.

Usage (from the repo root):
    pip install -r docs/requirements-docs.txt
    python docs/make_charts.py
"""
import json
import os
import sys

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(DOCS_DIR)
EVAL_DIR = os.path.join(REPO_ROOT, "eval")
RESULTS_DIR = os.path.join(REPO_ROOT, "results")
OUT_PNG = os.path.join(DOCS_DIR, "task_completion.png")

sys.path.insert(0, EVAL_DIR)
import grading_script as g  # noqa: E402  (same grader the paper's numbers come from)

MODELS = [
    ("qwen", "Qwen 3 32B"),
    ("mistral", "Mistral Small 3.2 24B"),
    ("llama", "Llama 3 8B"),
]
CONFIGS = ["A", "B", "C", "D"]

# Table VI of the paper, task completion (%), Configs A-D.
PAPER = {
    "qwen": [70.2, 84.5, 90.3, 93.0],
    "mistral": [65.1, 79.7, 80.5, 88.4],
    "llama": [54.9, 69.3, 68.1, 78.1],
}


def r1(x):
    """Round to one decimal the way the paper's tables are printed."""
    return round(x + 1e-9, 1)


def task_completion(cases, model, cfg):
    path = os.path.join(RESULTS_DIR, f"results_{model}_{cfg}.json")
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    graded = g.grade_config(cfg, records, cases, 5)
    return r1(graded["overall"]["task_completion"]["mean"])


def compute():
    cases = g.load_test_suite(os.path.join(EVAL_DIR, "test_suite.json"))
    return {m: [task_completion(cases, m, c) for c in CONFIGS] for m, _ in MODELS}


def check(values):
    problems = []
    for model, _ in MODELS:
        for cfg, got, want in zip(CONFIGS, values[model], PAPER[model]):
            if got != want:
                problems.append(f"{model} {cfg}: computed {got}, paper {want}")
    if problems:
        sys.exit("Chart values do not match Table VI:\n  " + "\n  ".join(problems))
    print("Chart values match Table VI of the paper.")


def draw(values):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Light to dark blue (A to D): readable in color and in grayscale.
    colors = ["#c6dbef", "#6baed6", "#2171b5", "#08306b"]
    labels = {"A": "A: trust the LLM", "B": "B", "C": "C", "D": "D: full system"}

    plt.rcParams.update({"font.size": 18})
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    width = 0.2
    for i, cfg in enumerate(CONFIGS):
        xs = [k + (i - 1.5) * width for k in range(len(MODELS))]
        ys = [values[m][i] for m, _ in MODELS]
        bars = ax.bar(xs, ys, width, label=labels[cfg], color=colors[i], edgecolor="black", linewidth=0.6)
        for bar, y in zip(bars, ys):
            ax.text(bar.get_x() + bar.get_width() / 2, y + 1, f"{y:.1f}", ha="center", va="bottom", fontsize=15)

    ax.set_xticks(range(len(MODELS)))
    ax.set_xticklabels([name for _, name in MODELS])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Task completion (%)")
    ax.set_title("Task completion: trust the LLM (A) vs. skeptical tools (D)", pad=16)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, color="#dddddd")
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4, frameon=False)

    fig.tight_layout()
    fig.savefig(OUT_PNG, facecolor="white")
    print(f"Wrote {os.path.relpath(OUT_PNG, REPO_ROOT)}")


if __name__ == "__main__":
    vals = compute()
    check(vals)
    draw(vals)

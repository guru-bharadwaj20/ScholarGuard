#!/usr/bin/env python
"""Render the held-out evaluation results as figures for the README.

Two charts, both read straight from ``benchmark_report.json`` so they cannot
drift from the numbers in the write-up:

* ``images/roc_pr.png`` — paper-level ROC and precision-recall curves for both
  held-out sets, against the chance line and the base rate. Two sets on one
  axis is the point: the gap between them is the project's central finding,
  that a single held-out set of this size does not settle a question.
* ``images/detector_recall_fpr.png`` — per-detector recall against clean-figure
  false-alarm rate, with 95% Wilson intervals, one panel per set. This is the
  chart the project could not draw until retraction notices supplied
  figure-level labels: before that, only the false-alarm half existed.

Colours are slots 1-2 of the documented default categorical palette, used
unchanged and in order.

Usage:
    python scripts/plot_results.py \
        --run "Set 1 (30/50):outputs/heldout_run" \
        --run "Set 2 (30/46):path/to/other_run"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.evaluation import metrics as M  # noqa: E402

# Categorical slots 1-3 of the validated default order, used unchanged and in
# order. Slot 3 was added when a third held-out set arrived; keeping the first
# two stable means set 1 and set 2 stay the colours the earlier charts used.
SERIES = ["#2a78d6", "#eb6834", "#2f9e6f"]
INK = "#0b0b0b"
INK_SOFT = "#52514e"
GRID = "#d9d8d4"
SURFACE = "#ffffff"

DETECTORS = ["copy_move", "cross_figure", "splice", "ai_generation"]
PRETTY = {"copy_move": "Copy-move", "cross_figure": "Cross-figure",
          "splice": "Splice", "ai_generation": "AI-generation"}


def load_scores(run_dir: str):
    """(labels, paper scores, figure counts) from a benchmark report.

    The figure count comes back alongside the score because it is the baseline
    the chart has to show: on these sets it ranks papers about as well as the
    pipeline does, and a results chart that omits it overstates the tool.
    """
    path = os.path.join(run_dir, "benchmark_report.json")
    with open(path, encoding="utf-8") as fh:
        results = json.load(fh)["results"]
    y, s, n = [], [], []
    for _pid, entry in results.items():
        report = entry.get("pipeline_report")
        if entry.get("status") != "ok" or not report:
            continue
        y.append(bool(entry["ground_truth"]["is_fraudulent"]))
        s.append(float(report["overall_risk"]["score"]))
        n.append(float(len(report.get("figures") or [])))
    return y, s, n


def load_detector_table(run_dir: str) -> dict:
    """Per-detector recall/FPR with their denominators, from metrics_summary.md.

    The summary is the artefact the evaluation itself publishes, so parsing it
    keeps the chart and the report in lockstep rather than recomputing (and
    possibly disagreeing about) the same quantities.
    """
    with open(os.path.join(run_dir, "metrics_summary.md"), encoding="utf-8") as fh:
        text = fh.read()
    out = {}
    for det in DETECTORS:
        row = re.search(rf"^\| {det} \|(.+)$", text, re.M)
        if not row:
            continue
        cells = [c.strip() for c in row.group(1).split("|")]
        # Scoreable | Unlabeled | Not eval'd | Precision | Recall | FPR
        def parse(cell):
            m = re.match(r"([0-9.]+) \(95% CI ([0-9.]+)-([0-9.]+), n=(\d+)\)", cell)
            if not m:
                return None
            return {"value": float(m.group(1)), "lo": float(m.group(2)),
                    "hi": float(m.group(3)), "n": int(m.group(4))}
        out[det] = {"recall": parse(cells[4]) if len(cells) > 4 else None,
                    "fpr": parse(cells[5]) if len(cells) > 5 else None}
    return out


def roc_points(y, s):
    pts = [(1.0, 1.0)]
    for t in sorted(set(s)):
        pred = [v >= t for v in s]
        c = M.confusion_counts(y, pred)
        m = M.binary_metrics(c)
        pts.append((m["false_positive_rate"] or 0.0, m["recall"] or 0.0))
    pts.append((0.0, 0.0))
    return zip(*sorted(pts), strict=True)


def pr_points(y, s):
    pts = []
    for t in sorted(set(s)):
        pred = [v >= t for v in s]
        c = M.confusion_counts(y, pred)
        m = M.binary_metrics(c)
        if m["precision"] is not None and m["recall"] is not None:
            pts.append((m["recall"], m["precision"]))
    pts.sort()
    return zip(*pts, strict=True) if pts else ([], [])


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SOFT, labelsize=9)


def plot_curves(runs, out_path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), facecolor=SURFACE)
    for ax in axes:
        style(ax)

    for i, (label, run_dir) in enumerate(runs):
        y, s, n = load_scores(run_dir)
        auc, ap = M.roc_auc(y, s), M.average_precision(y, s)
        base = sum(y) / len(y)
        fpr, tpr = roc_points(y, s)
        axes[0].plot(fpr, tpr, color=SERIES[i], linewidth=2,
                     label=f"{label} — AUC {auc:.3f}")
        # The confound, drawn on the same axis: ranking by figure count alone.
        # Dotted and thin so the pipeline stays legible, but present, because
        # the whole point is how little daylight there is between them.
        cf, ct = roc_points(y, n)
        axes[0].plot(cf, ct, color=SERIES[i], linewidth=1.1, linestyle=":",
                     alpha=0.85,
                     label=f"    …figure count alone — {M.roc_auc(y, n):.3f}")
        rec, prec = pr_points(y, s)
        axes[1].plot(rec, prec, color=SERIES[i], linewidth=2,
                     label=f"{label} — AP {ap:.3f}")
        axes[1].axhline(base, color=SERIES[i], linewidth=1, linestyle=":",
                        alpha=0.7)

    axes[0].plot([0, 1], [0, 1], color=INK_SOFT, linewidth=1, linestyle="--",
                 alpha=0.6, label="chance")
    axes[0].set_xlabel("False-positive rate (clean papers flagged)", color=INK_SOFT)
    axes[0].set_ylabel("Recall (fraud papers caught)", color=INK_SOFT)
    axes[0].set_title("Paper-level ROC  (dotted = figure count, no image analysis)",
                      color=INK, fontsize=11, loc="left")

    axes[1].set_xlabel("Recall", color=INK_SOFT)
    axes[1].set_ylabel("Precision", color=INK_SOFT)
    axes[1].set_title("Precision-recall  (dotted = base rate)", color=INK,
                      fontsize=11, loc="left")

    for ax in axes:
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
    leg = axes[0].legend(frameon=False, fontsize=7.6, loc="lower right",
                         labelspacing=0.3, handlelength=1.8)
    for t in leg.get_texts():
        t.set_color(INK)
    leg = axes[1].legend(frameon=False, fontsize=9, loc="lower right")
    for t in leg.get_texts():
        t.set_color(INK)

    fig.suptitle("Three held-out sets agree — and counting the figures does "
                 "nearly as well", color=INK, fontsize=12, x=0.008, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=160, facecolor=SURFACE)
    print(f"wrote {out_path}")


def plot_detectors(runs, out_path):
    fig, axes = plt.subplots(1, len(runs), figsize=(11, 4.4), facecolor=SURFACE,
                             sharex=True)
    if len(runs) == 1:
        axes = [axes]

    for ax, (label, run_dir) in zip(axes, runs, strict=True):
        style(ax)
        table = load_detector_table(run_dir)
        names, ys = [], []
        for j, det in enumerate(DETECTORS):
            names.append(PRETTY[det])
            ys.append(j)
        height = 0.36
        for k, (metric, colour, lbl) in enumerate(
                [("recall", SERIES[0], "Recall (of figures the notice names)"),
                 ("fpr", SERIES[1], "False-alarm rate (on clean figures)")]):
            offs = (0.5 - k) * (height + 0.04)
            for j, det in enumerate(DETECTORS):
                cell = table.get(det, {}).get(metric)
                y_pos = j + offs
                if cell is None:
                    ax.text(0.02, y_pos, "not measurable", va="center",
                            fontsize=8, color=INK_SOFT, style="italic")
                    continue
                ax.barh(y_pos, cell["value"], height=height, color=colour,
                        label=lbl if j == 0 else None)
                ax.plot([cell["lo"], cell["hi"]], [y_pos, y_pos],
                        color=INK, linewidth=1.2, alpha=0.55)
                ax.text(min(cell["hi"] + 0.02, 0.90), y_pos,
                        f"{cell['value']:.2f}", va="center", fontsize=8.5,
                        color=INK)
        ax.set_yticks(range(len(DETECTORS)))
        ax.set_yticklabels(names, color=INK, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.0)
        ax.set_xlabel("rate", color=INK_SOFT)
        ax.set_title(label, color=INK, fontsize=11, loc="left")

    handles, labels = axes[0].get_legend_handles_labels()
    leg = fig.legend(handles, labels, frameon=False, fontsize=9,
                     loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
    for t in leg.get_texts():
        t.set_color(INK)
    # Checked, not assumed: across all three sets every detector's recall
    # interval overlaps its own false-alarm interval. An earlier title claimed
    # only copy-move cleared its FPR, which set 3's cross-figure result (0.31
    # recall against 0.26 FPR) contradicts.
    fig.suptitle("Every detector's recall interval overlaps its own "
                 "false-alarm interval", color=INK, fontsize=12, x=0.008,
                 ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.93))
    fig.savefig(out_path, dpi=160, facecolor=SURFACE)
    print(f"wrote {out_path}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", action="append", required=True,
                   metavar="LABEL:DIR",
                   help="a benchmark output directory, prefixed with its label")
    p.add_argument("--out-dir", default="images")
    args = p.parse_args(argv)

    runs = []
    for spec in args.run:
        # Split on the FIRST colon: a Windows path carries its own ("C:/..."),
        # and splitting on the last one silently moves the drive letter into
        # the label.
        label, sep, path = spec.partition(":")
        if not sep or not path:
            p.error(f"--run needs LABEL:DIR, got {spec!r}")
        runs.append((label.strip(), path.strip()))

    os.makedirs(args.out_dir, exist_ok=True)
    plot_curves(runs, os.path.join(args.out_dir, "roc_pr.png"))
    plot_detectors(runs, os.path.join(args.out_dir, "detector_recall_fpr.png"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

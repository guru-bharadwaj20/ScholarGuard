"""Pixel-level evaluation metrics and dataset-wide benchmarking.

Metrics operate on binary masks (any non-zero pixel counts as positive).
``evaluate_dataset`` runs the copy-move detector over a folder of images
with ground-truth masks (Stage 1 convention: ``<stem>_mask.png``), writes
a per-image CSV to the output directory and returns summary statistics.

CLI usage:
    python -m src.evaluation.metrics \
        --data data/synthetic --clean data/clean \
        --output outputs/stage2_results
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import time
from statistics import NormalDist

import numpy as np

from src.detectors.copy_move_detector import CopyMoveDetector
from src.utils.image_io import (
    find_ground_truth_mask,
    list_images,
    load_image,
    load_mask,
)
from src.utils.visualization import save_side_by_side


def _write_rows_csv(rows: list[dict], path: str, fieldnames: list[str]) -> str:
    """Write per-item rows to CSV, tolerating an empty result set.

    Every evaluator used ``csv.DictWriter(fieldnames=list(rows[0].keys()))``,
    which raised ``IndexError: list index out of range`` whenever the dataset
    directory was empty or misnamed -- an opaque crash in place of an empty
    report. Declaring the columns explicitly writes a valid header either way,
    and pins the schema so a renamed row key fails loudly here rather than
    silently reshaping the CSV.
    """
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


#: Column schemas for the three per-item evaluation CSVs.
_DATASET_CSV_FIELDS = ["image", "ground_truth_forged", "predicted_forged",
                       "confidence", "iou", "precision", "recall", "f1",
                       "n_regions", "runtime_sec"]
_CROSS_FIGURE_CSV_FIELDS = ["query", "expected_source", "reuse_type",
                            "found_by_phash", "found_by_embedding",
                            "region_reuse_verified", "found_any",
                            "n_candidates_flagged", "runtime_sec"]
_AI_GENERATION_CSV_FIELDS = ["image", "true_label", "verdict", "freq_score",
                             "noise_score", "classifier_score",
                             "flagged_ai_strict", "flagged_ai_lenient",
                             "runtime_sec"]


def compute_iou(pred_mask: np.ndarray, gt_mask: np.ndarray) -> float:
    """Pixel-level Intersection-over-Union between two binary masks.

    Returns 1.0 when both masks are empty (a correct 'nothing detected'
    on a clean image), 0.0 when exactly one is empty.
    """
    pred = np.asarray(pred_mask) > 0
    gt = np.asarray(gt_mask) > 0
    union = np.logical_or(pred, gt).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(pred, gt).sum() / union)


def compute_pixel_metrics(pred_mask: np.ndarray, gt_mask: np.ndarray) -> dict:
    """Pixel-level precision / recall / F1 / IoU for a predicted mask."""
    pred = np.asarray(pred_mask) > 0
    gt = np.asarray(gt_mask) > 0
    tp = float(np.logical_and(pred, gt).sum())
    fp = float(np.logical_and(pred, ~gt).sum())
    fn = float(np.logical_and(~pred, gt).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0  # empty GT: nothing to find
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return {
        "iou": compute_iou(pred, gt),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_dataset(
    data_dir: str,
    output_dir: str = "outputs/stage2_results",
    clean_dir: str | None = None,
    save_visualizations: bool = True,
    detector: CopyMoveDetector | None = None,
) -> dict:
    """Benchmark the detector across a dataset and write per-image CSV.

    ``data_dir``  — forged images, each with a ``<stem>_mask.png`` ground truth.
    ``clean_dir`` — optional folder of unforged images (empty ground truth);
                    used to measure the false-positive rate.

    Returns a summary dict with mean IoU/F1 over forged images and the
    detection accuracy over all images.
    """
    detector = detector or CopyMoveDetector()
    os.makedirs(output_dir, exist_ok=True)
    rows: list[dict] = []

    jobs = [(path, True) for path in list_images(data_dir)]
    if clean_dir:
        jobs += [(path, False) for path in list_images(clean_dir)]

    for image_path, is_forged in jobs:
        image = load_image(image_path)
        gt_path = find_ground_truth_mask(image_path)
        gt_mask = (load_mask(gt_path) if gt_path
                   else np.zeros(image.shape[:2], np.uint8))

        start = time.perf_counter()
        result = detector.detect(image)
        elapsed = time.perf_counter() - start

        pixel = compute_pixel_metrics(result["mask"], gt_mask)
        stem = os.path.splitext(os.path.basename(image_path))[0]
        rows.append({
            "image": os.path.basename(image_path),
            "ground_truth_forged": is_forged,
            "predicted_forged": result["forged"],
            "confidence": result["confidence"],
            "iou": round(pixel["iou"], 4),
            "precision": round(pixel["precision"], 4),
            "recall": round(pixel["recall"], 4),
            "f1": round(pixel["f1"], 4),
            "n_regions": len(result["regions"]),
            "runtime_sec": round(elapsed, 2),
        })

        if save_visualizations:
            save_side_by_side(
                os.path.join(output_dir, f"{stem}_comparison.png"),
                image, result["mask"],
                gt_mask if gt_path else None,
            )

    csv_path = _write_rows_csv(rows, os.path.join(output_dir,
                                                  "per_image_results.csv"),
                               _DATASET_CSV_FIELDS)

    forged_rows = [r for r in rows if r["ground_truth_forged"]]
    clean_rows = [r for r in rows if not r["ground_truth_forged"]]
    correct = sum(r["predicted_forged"] == r["ground_truth_forged"] for r in rows)

    summary = {
        "n_images": len(rows),
        "n_forged": len(forged_rows),
        "n_clean": len(clean_rows),
        "detection_accuracy": correct / len(rows) if rows else 0.0,
        "forged_recall": (sum(r["predicted_forged"] for r in forged_rows)
                          / len(forged_rows) if forged_rows else 0.0),
        "clean_false_positive_rate": (sum(r["predicted_forged"] for r in clean_rows)
                                      / len(clean_rows) if clean_rows else 0.0),
        "mean_iou_forged": (float(np.mean([r["iou"] for r in forged_rows]))
                            if forged_rows else 0.0),
        "mean_f1_forged": (float(np.mean([r["f1"] for r in forged_rows]))
                           if forged_rows else 0.0),
        "mean_runtime_sec": float(np.mean([r["runtime_sec"] for r in rows])) if rows else 0.0,
        "csv_path": csv_path,
    }
    return summary


# --------------------------------------------------------------------------
# Stage 3: cross-figure retrieval evaluation
# --------------------------------------------------------------------------
def evaluate_cross_figure(
    corpus_dir: str,
    ground_truth_path: str | None = None,
    output_dir: str = "outputs/stage3_results",
    detector=None,
) -> dict:
    """Benchmark the cross-figure detector against a labelled corpus.

    ``ground_truth_path`` is a JSON file (defaults to
    ``<corpus_dir>/ground_truth.json``) in the format written by
    :func:`src.utils.synth.generate_figure_corpus`:
    ``{"pairs": [{"query", "source", "type"}], "clean": [...]}``.

    Every ground-truth query is run through the detector and scored on
    whether its true source appears in any match list (and which tier
    caught it); every clean figure is run to measure false flags. Writes
    a per-query CSV and returns summary statistics.
    """
    import json as _json

    from src.detectors.cross_figure_detector import CrossFigureDetector

    ground_truth_path = ground_truth_path or os.path.join(corpus_dir,
                                                          "ground_truth.json")
    with open(ground_truth_path, encoding="utf-8") as fh:
        ground_truth = _json.load(fh)

    detector = detector or CrossFigureDetector(corpus_dir)
    os.makedirs(output_dir, exist_ok=True)
    rows: list[dict] = []

    def _basenames(matches):
        return {os.path.basename(m["matched_image_path"]) for m in matches}

    for pair in ground_truth["pairs"]:
        query_path = os.path.join(corpus_dir, pair["query"])
        start = time.perf_counter()
        result = detector.detect(query_path)
        elapsed = time.perf_counter() - start
        hash_hits = _basenames(result["exact_or_near_duplicate_matches"])
        embed_hits = _basenames(result["visual_similarity_matches"])
        region_hits = _basenames(result["suspected_region_reuse"])
        rows.append({
            "query": pair["query"],
            "expected_source": pair["source"],
            "reuse_type": pair["type"],
            "found_by_phash": pair["source"] in hash_hits,
            "found_by_embedding": pair["source"] in embed_hits,
            "region_reuse_verified": pair["source"] in region_hits,
            "found_any": pair["source"] in (hash_hits | embed_hits | region_hits),
            "n_candidates_flagged": len(hash_hits | embed_hits),
            "runtime_sec": round(elapsed, 2),
        })

    false_flags = 0
    for name in ground_truth["clean"]:
        result = detector.detect(os.path.join(corpus_dir, name))
        # A clean figure is falsely flagged only if the *verified* region
        # tier fires or phash claims a near-duplicate; embedding-tier hits
        # alone are unranked leads, not flags.
        if result["suspected_region_reuse"] or result["exact_or_near_duplicate_matches"]:
            hits = (_basenames(result["suspected_region_reuse"])
                    | _basenames(result["exact_or_near_duplicate_matches"]))
            # Reuse queries legitimately match their own source figures in
            # reverse; only count hits against figures NOT paired with this one.
            paired = {p["query"] for p in ground_truth["pairs"]
                      if p["source"] == name}
            if hits - paired:
                false_flags += 1

    csv_path = _write_rows_csv(rows, os.path.join(output_dir,
                                                  "cross_figure_results.csv"),
                               _CROSS_FIGURE_CSV_FIELDS)

    found = [r for r in rows if r["found_any"]]
    summary = {
        "n_reuse_cases": len(rows),
        "n_clean": len(ground_truth["clean"]),
        "retrieval_recall": len(found) / len(rows) if rows else 0.0,
        "recall_phash": (sum(r["found_by_phash"] for r in rows) / len(rows)
                         if rows else 0.0),
        "recall_embedding": (sum(r["found_by_embedding"] for r in rows) / len(rows)
                             if rows else 0.0),
        "recall_region_verified": (sum(r["region_reuse_verified"] for r in rows)
                                   / len(rows) if rows else 0.0),
        "clean_false_flag_rate": (false_flags / len(ground_truth["clean"])
                                  if ground_truth["clean"] else 0.0),
        "mean_query_runtime_sec": (float(np.mean([r["runtime_sec"] for r in rows]))
                                   if rows else 0.0),
        "csv_path": csv_path,
    }
    return summary


def evaluate_ai_generation(
    real_dir: str = "data/real_captured_samples",
    ai_dir: str = "data/ai_generated_samples",
    output_dir: str = "outputs/stage4_results",
    weights_path: str | None = None,
) -> dict:
    """Benchmark the AI-generation detector on labelled real / AI folders.

    Treats ``likely_ai_generated`` (and, as a softer positive,
    ``suspicious``) as an AI prediction. Reports strict accuracy (only
    ``likely_ai_generated`` counts as AI) and lenient recall (``suspicious``
    counts too), plus mean forensic scores per class. Writes a per-image CSV.
    """
    from src.detectors.ai_generation_detector import (
        LIKELY_AI, LIKELY_REAL, SUSPICIOUS, detect_ai_generation,
    )

    os.makedirs(output_dir, exist_ok=True)
    rows: list[dict] = []
    jobs = ([(p, "real") for p in list_images(real_dir)]
            + [(p, "ai_generated") for p in list_images(ai_dir)])

    for image_path, label in jobs:
        start = time.perf_counter()
        result = detect_ai_generation(image_path, weights_path=weights_path)
        elapsed = time.perf_counter() - start
        verdict = result["combined_verdict"]
        rows.append({
            "image": os.path.basename(image_path),
            "true_label": label,
            "verdict": verdict,
            "freq_score": result["frequency_anomaly_score"],
            "noise_score": result["noise_residual_anomaly_score"],
            "classifier_score": result["classifier_score"],
            "flagged_ai_strict": verdict == LIKELY_AI,
            "flagged_ai_lenient": verdict in (LIKELY_AI, SUSPICIOUS),
            "runtime_sec": round(elapsed, 2),
        })

    csv_path = _write_rows_csv(rows, os.path.join(output_dir,
                                                  "ai_generation_results.csv"),
                               _AI_GENERATION_CSV_FIELDS)

    ai_rows = [r for r in rows if r["true_label"] == "ai_generated"]
    real_rows = [r for r in rows if r["true_label"] == "real"]

    def _mean(subset, key):
        return float(np.mean([r[key] for r in subset])) if subset else 0.0

    # Strict accuracy: AI must be "likely_ai_generated", real must be
    # "likely_real" (a "suspicious" real is a soft false positive).
    correct_strict = (sum(r["flagged_ai_strict"] for r in ai_rows)
                      + sum(r["verdict"] == LIKELY_REAL for r in real_rows))
    summary = {
        "n_real": len(real_rows),
        "n_ai": len(ai_rows),
        "ai_recall_strict": (sum(r["flagged_ai_strict"] for r in ai_rows)
                             / len(ai_rows) if ai_rows else 0.0),
        "ai_recall_lenient": (sum(r["flagged_ai_lenient"] for r in ai_rows)
                              / len(ai_rows) if ai_rows else 0.0),
        "real_flagged_rate_strict": (sum(r["flagged_ai_strict"] for r in real_rows)
                                     / len(real_rows) if real_rows else 0.0),
        "real_suspicious_rate": (sum(r["flagged_ai_lenient"] for r in real_rows)
                                 / len(real_rows) if real_rows else 0.0),
        "strict_accuracy": correct_strict / len(rows) if rows else 0.0,
        "mean_freq_real": _mean(real_rows, "freq_score"),
        "mean_freq_ai": _mean(ai_rows, "freq_score"),
        "mean_noise_real": _mean(real_rows, "noise_score"),
        "mean_noise_ai": _mean(ai_rows, "noise_score"),
        "classifier_used": any(r["classifier_score"] is not None for r in rows),
        "mean_runtime_sec": _mean(rows, "runtime_sec"),
        "csv_path": csv_path,
    }
    return summary


# --------------------------------------------------------------------------
# Stage 7: binary-classification metrics (paper-level & per-detector) for the
# full-pipeline benchmark. These are pure math over predicted/true labels and
# do not run any detector — they are unit-tested independently of the pipeline.
# --------------------------------------------------------------------------
def wilson_confidence_interval(successes: int, total: int,
                               confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion, clamped to [0, 1].

    Preferred over the normal (Wald) interval because at small n — and this
    project's real evaluation set is n=15 fraud / n=10 clean — Wald produces
    nonsense (zero-width intervals at p=0 or p=1, and bounds outside [0,1]).
    Wilson stays sensible: 0/10 -> (0.000, 0.278), 15/15 -> (0.796, 1.000).

    Pure stdlib (``statistics.NormalDist``) — no scipy dependency.
    A ``total`` of 0 means the proportion is undefined; we return the
    maximally-uncertain (0.0, 1.0) rather than a fake point estimate.
    """
    if total <= 0:
        return (0.0, 1.0)
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if not 0 <= successes <= total:
        raise ValueError("successes must be in [0, total]")

    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    margin = (z / denominator) * math.sqrt(
        p * (1.0 - p) / total + z * z / (4.0 * total * total))
    low, high = center - margin, center + margin

    # At p=0 the lower bound is analytically exactly 0, and at p=1 the upper
    # bound is analytically exactly 1 (the margin telescopes into the center).
    # Pin them so floating-point noise can't report 0.9999999999999999.
    if successes == 0:
        low = 0.0
    if successes == total:
        high = 1.0
    return (max(0.0, low), min(1.0, high))


# The (successes, total) pair backing each rate, so each can carry a Wilson CI.
# F1 is a harmonic mean of two proportions, NOT itself a binomial proportion —
# it gets no Wilson interval, and we say so rather than inventing one.
_RATE_COUNTS = {
    "precision": lambda c: (c["tp"], c["tp"] + c["fp"]),
    "recall": lambda c: (c["tp"], c["tp"] + c["fn"]),
    "specificity": lambda c: (c["tn"], c["tn"] + c["fp"]),
    "false_positive_rate": lambda c: (c["fp"], c["fp"] + c["tn"]),
    "false_negative_rate": lambda c: (c["fn"], c["fn"] + c["tp"]),
    "accuracy": lambda c: (c["tp"] + c["tn"],
                           c["tp"] + c["tn"] + c["fp"] + c["fn"]),
}


def metrics_with_confidence(counts: dict, confidence: float = 0.95) -> dict:
    """Point estimates plus Wilson CIs: {rate: {value, ci_low, ci_high, n}}.

    ``value`` is None where the denominator is 0 (undefined, not zero), and the
    CI is then the uninformative (0, 1).
    """
    out: dict = {}
    for name, get_counts in _RATE_COUNTS.items():
        successes, total = get_counts(counts)
        low, high = wilson_confidence_interval(successes, total, confidence)
        out[name] = {
            "value": (round(successes / total, 4) if total > 0 else None),
            "ci_low": round(low, 4), "ci_high": round(high, 4),
            "n": total, "successes": successes,
        }
    out["f1"] = {"value": _f1(
        (counts["tp"] / (counts["tp"] + counts["fp"])
         if counts["tp"] + counts["fp"] else None),
        (counts["tp"] / (counts["tp"] + counts["fn"])
         if counts["tp"] + counts["fn"] else None)),
        "ci_low": None, "ci_high": None, "n": None,
        "note": "F1 is not a binomial proportion; no Wilson interval"}
    out["confidence"] = confidence
    return out


def format_metric_with_ci(entry: dict, confidence: float = 0.95) -> str:
    """Render one metric as e.g. ``0.600 (95% CI 0.36-0.80, n=15)``."""
    if entry.get("value") is None:
        return f"n/a (n={entry.get('n', 0)})"
    if entry.get("ci_low") is None:  # F1 and friends
        return f"{entry['value']:.3f}"
    pct = int(round(confidence * 100))
    return (f"{entry['value']:.3f} ({pct}% CI {entry['ci_low']:.2f}-"
            f"{entry['ci_high']:.2f}, n={entry['n']})")


def confusion_counts(y_true: list[bool], y_pred: list[bool]) -> dict:
    """Return {tp, fp, fn, tn} for aligned boolean label lists."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")
    tp = fp = fn = tn = 0
    for t, p in zip(y_true, y_pred, strict=True):
        if t and p:
            tp += 1
        elif not t and p:
            fp += 1
        elif t and not p:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def binary_metrics(counts: dict) -> dict:
    """Precision/recall/F1/accuracy/FPR/FNR/specificity from confusion counts.

    Undefined ratios (zero denominator) return None so they are visibly
    "not applicable" rather than a misleading 0.0.
    """
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    total = tp + fp + fn + tn

    def _ratio(num, den):
        return round(num / den, 4) if den > 0 else None

    return {
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),          # == sensitivity / TPR
        "specificity": _ratio(tn, tn + fp),
        "false_positive_rate": _ratio(fp, fp + tn),
        "false_negative_rate": _ratio(fn, fn + tp),
        "accuracy": _ratio(tp + tn, total),
        "f1": _f1(_ratio(tp, tp + fp), _ratio(tp, tp + fn)),
        "support_positive": tp + fn,
        "support_negative": tn + fp,
        **counts,
    }


def _f1(precision, recall) -> float | None:
    """F1 from precision/recall, or None when either is genuinely undefined.

    The test is ``is None``, not falsiness. A precision or recall of exactly
    0.0 is a *measurement* -- the detector fired only on clean figures, or
    caught none of the positives -- and its F1 is 0.0. Treating it as undefined
    rendered the worst possible result identically to a missing one ("not
    measurable") in metrics_summary.md and the side-by-side comparison tables.
    Only a zero denominator upstream, which surfaces as None, is undefined.
    """
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def classification_metrics(y_true: list[bool], y_pred: list[bool]) -> dict:
    """Confusion counts + all derived metrics in one dict."""
    return binary_metrics(confusion_counts(y_true, y_pred))


def confusion_matrix_str(counts: dict, positive_label: str = "fraud",
                         negative_label: str = "clean") -> str:
    """A small human-readable 2x2 confusion matrix table."""
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    return (
        f"                 pred {positive_label:<8} pred {negative_label:<8}\n"
        f"  true {positive_label:<8}  {tp:^12} {fn:^13}\n"
        f"  true {negative_label:<8}  {fp:^12} {tn:^13}"
    )


def score_threshold_sweep(y_true: list[bool], scores: list[float],
                          thresholds: list[float] | None = None) -> list[dict]:
    """PR/ROC-style sweep: metrics at each score cutoff (pred = score >= T).

    Reuses already-computed continuous risk scores — no detector re-runs.
    Returns [{threshold, precision, recall, f1, false_positive_rate, ...}].
    """
    if thresholds is None:
        thresholds = [round(t, 1) for t in _frange(0.0, 100.0, 2.5)]
    rows = []
    for thr in thresholds:
        pred = [s >= thr for s in scores]
        rows.append({"threshold": thr, "metrics": classification_metrics(y_true, pred)})
    return rows


def _frange(start: float, stop: float, step: float):
    v = start
    while v <= stop + 1e-9:
        yield v
        v += step


# --------------------------------------------------------------------------
# Threshold-free ranking metrics + honest (LOOCV) threshold selection.
#
# With a 60% base rate and n=25, "accuracy at the best threshold" is almost
# all noise (the auto-swept cutoff jumped 67.5 -> 22.5 between runs). ROC-AUC
# and average precision rank the scores without committing to a cutoff, and
# are directly comparable across runs; and any cutoff we DO report is chosen
# by leave-one-out CV so it is not fit on the same papers it is scored on.
# --------------------------------------------------------------------------
def roc_auc(y_true: list[bool], scores: list[float]) -> float | None:
    """Area under the ROC curve via the Mann-Whitney U statistic.

    Equals the probability a random fraud paper outranks a random clean
    one; ties count as half. Returns None if one class is absent (AUC
    undefined). Pure stdlib — no sklearn dependency.
    """
    pos = [s for t, s in zip(y_true, scores, strict=True) if t]
    neg = [s for t, s in zip(y_true, scores, strict=True) if not t]
    if not pos or not neg:
        return None
    # Rank-sum form instead of the nested loop that compared every positive
    # against every negative: identical result, O(n log n) rather than O(n^2).
    # Ties get the average rank, which is exactly the "count a tie as half"
    # rule the docstring states.
    ranks = _average_ranks(pos + neg)
    rank_sum_pos = sum(ranks[: len(pos)])
    u = rank_sum_pos - len(pos) * (len(pos) + 1) / 2.0
    return round(u / (len(pos) * len(neg)), 4)


def _average_ranks(values: list[float]) -> list[float]:
    """1-based ranks of ``values``, tied entries sharing their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2.0 + 1.0          # average of the 1-based ranks
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def average_precision(y_true: list[bool], scores: list[float]) -> float | None:
    """Average precision (area under the precision-recall curve).

    More informative than ROC-AUC when positives are the minority and the
    cost of false positives is high — which is the screening setting here.

    Ties are resolved as a **block**, not by input order. This matters: the
    previous implementation sorted with a stable sort keyed on score alone, so
    equally-scored papers kept their order in ``benchmark_report.json`` — which
    stores fraud papers first. Every tied fraud paper was therefore ranked above
    every tied clean one, and a coarse integer statistic
    (``max_corroboration``) reported AP 0.865 where honest random tie-breaking
    averages 0.612 — higher than all of 200 random shuffles.

    The fix is the standard definition: step through *distinct* score
    thresholds and accumulate ``sum((R_k - R_{k-1}) * P_k)``. Within a tie the
    procedure cannot prefer either label, so the result no longer depends on
    row order. Scores that are all distinct give exactly the previous value.
    """
    total_pos = sum(1 for t in y_true if t)
    if total_pos == 0:
        return None
    pairs = sorted(zip(scores, y_true, strict=True), key=lambda t: t[0],
                   reverse=True)

    ap = 0.0
    tp = fp = 0
    prev_recall = 0.0
    i, n = 0, len(pairs)
    while i < n:
        # Consume every entry sharing this score before measuring anything.
        j = i
        while j < n and pairs[j][0] == pairs[i][0]:
            if pairs[j][1]:
                tp += 1
            else:
                fp += 1
            j += 1
        recall = tp / total_pos
        precision = tp / (tp + fp)
        ap += (recall - prev_recall) * precision
        prev_recall = recall
        i = j
    return round(ap, 4)


def count_matched_auc(y_true: list[bool], scores: list[float],
                      strata: list[int]) -> dict:
    """ROC-AUC restricted to positive/negative pairs in the SAME stratum.

    Why this belongs in every report
    --------------------------------
    On held-out set 1 the paper risk score reaches ROC-AUC 0.685. So does
    ``len(paper.figures)`` — 0.681, with no image analysis at all. Retracted
    papers simply have more figures (median 7.5 vs 5.0), and any statistic that
    accumulates per-figure evidence inherits that. A headline AUC cannot tell
    you whether a detector works or whether it counted the figures.

    Passing ``strata=[n_figures, ...]`` answers that: only fraud/clean pairs with
    an *identical* figure count are compared, so figure count itself scores
    exactly 0.500 and anything above that is signal the confound cannot explain.

    Ties count as half, as in :func:`roc_auc`. Returns the matched AUC, the
    number of comparable pairs, and how many strata contributed — a small
    ``n_pairs`` means a wide interval, so report it alongside the estimate.
    """
    if not (len(y_true) == len(scores) == len(strata)):
        raise ValueError("y_true, scores and strata must be the same length")
    pos = [(s, k) for t, s, k in zip(y_true, scores, strata, strict=True) if t]
    neg = [(s, k) for t, s, k in zip(y_true, scores, strata, strict=True)
           if not t]
    by_stratum: dict[int, list] = {}
    for s, k in neg:
        by_stratum.setdefault(k, []).append(s)

    wins = 0.0
    pairs = 0
    used = set()
    for s_pos, k in pos:
        for s_neg in by_stratum.get(k, ()):
            pairs += 1
            used.add(k)
            if s_pos > s_neg:
                wins += 1.0
            elif s_pos == s_neg:
                wins += 0.5
    if pairs == 0:
        return {"auc": None, "n_pairs": 0, "n_strata": 0}
    return {"auc": round(wins / pairs, 4), "n_pairs": pairs,
            "n_strata": len(used)}


def ranking_metrics(y_true: list[bool], scores: list[float],
                    strata: list[int] | None = None) -> dict:
    """Threshold-free summary: ROC-AUC + average precision + support.

    When ``strata`` is supplied (figure counts, in practice) the summary also
    carries the stratum-matched AUC, so a reader can see at once how much of the
    headline number survives controlling for how many figures were examined.
    """
    out = {
        "roc_auc": roc_auc(y_true, scores),
        "average_precision": average_precision(y_true, scores),
        "n_positive": sum(1 for t in y_true if t),
        "n_negative": sum(1 for t in y_true if not t),
    }
    if strata is not None:
        out["count_matched"] = count_matched_auc(y_true, scores, strata)
    return out


def loocv_threshold_accuracy(y_true: list[bool], scores: list[float],
                             thresholds: list[float] | None = None) -> dict:
    """Honest accuracy: pick the cutoff on all-but-one, score the held-out one.

    For each paper i, the best-accuracy threshold is chosen on the other
    n-1 papers, then applied to paper i alone. The reported accuracy is the
    mean over held-out papers — an (almost) unbiased estimate, unlike the
    in-sample "best threshold accuracy" that made the numbers look better
    than the tool is. Also returns the modal chosen threshold for reference.

    Ties in the training sweep are broken toward the *lower* threshold
    (higher recall — the screening priority).
    """
    n = len(y_true)
    if n < 3:
        return {"loocv_accuracy": None, "n": n,
                "note": "too few papers for leave-one-out"}
    if thresholds is None:
        lo, hi = min(scores), max(scores)
        thresholds = [round(t, 3) for t in _frange(lo, hi, (hi - lo) / 50 or 1.0)]

    correct = 0
    chosen: list[float] = []
    for i in range(n):
        tr_true = [y_true[j] for j in range(n) if j != i]
        tr_scores = [scores[j] for j in range(n) if j != i]
        best_acc = -1.0
        best_thrs: list[float] = []
        for thr in thresholds:
            pred = [s >= thr for s in tr_scores]
            acc = sum(p == t for p, t in zip(pred, tr_true, strict=True)) / len(tr_true)
            if acc > best_acc:
                best_acc, best_thrs = acc, [thr]
            elif acc == best_acc:
                best_thrs.append(thr)
        # Midpoint of the optimal band = the max-margin cutoff, so a held-out
        # point near the class boundary is not misclassified by a threshold
        # that happened to sit on the training margin.
        best_thr = best_thrs[len(best_thrs) // 2]
        chosen.append(best_thr)
        if (scores[i] >= best_thr) == y_true[i]:
            correct += 1

    modal = max(set(chosen), key=chosen.count)
    return {
        "loocv_accuracy": round(correct / n, 4),
        "modal_threshold": modal,
        "chosen_thresholds": chosen,
        "n": n,
    }


def estimate_fire_calibration(fired_flags: list[bool],
                              labels: list[bool]) -> dict:
    """P(signal fires | fraud) and | clean) with Laplace smoothing.

    Feeds src.pipeline.evidence_fusion. ``fired_flags[i]`` is whether the
    detector fired on item i; ``labels[i]`` is that item's true fraud
    status. +1/+2 Laplace smoothing keeps the ratio finite on the tiny
    real sets (a 0/10 clean fire rate must not become an infinite LR).
    """
    fraud_fire = sum(1 for f, y in zip(fired_flags, labels, strict=True)
                     if y and f)
    fraud_tot = sum(1 for y in labels if y)
    clean_fire = sum(1 for f, y in zip(fired_flags, labels, strict=True)
                     if not y and f)
    clean_tot = sum(1 for y in labels if not y)
    return {
        "p_fire_fraud": round((fraud_fire + 1) / (fraud_tot + 2), 4),
        "p_fire_clean": round((clean_fire + 1) / (clean_tot + 2), 4),
        "n_fraud": fraud_tot, "n_clean": clean_tot,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="evaluate ScholarGuard detectors")
    parser.add_argument("--data", default="data/synthetic",
                        help="folder of forged images with *_mask.png ground truths")
    parser.add_argument("--clean", default=None,
                        help="optional folder of clean (unforged) images")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-viz", action="store_true",
                        help="skip saving side-by-side comparison images")
    parser.add_argument("--cross-figure", metavar="CORPUS_DIR", default=None,
                        help="run the Stage 3 cross-figure evaluation on this "
                             "corpus instead of the Stage 2 evaluation")
    parser.add_argument("--ai-generation", action="store_true",
                        help="run the Stage 4 AI-generation evaluation")
    parser.add_argument("--real-dir", default="data/real_captured_samples")
    parser.add_argument("--ai-dir", default="data/ai_generated_samples")
    parser.add_argument("--weights", default=None,
                        help="optional artifact_classifier.pt for Stage 4")
    args = parser.parse_args(argv)

    if args.ai_generation:
        summary = evaluate_ai_generation(
            args.real_dir, args.ai_dir,
            output_dir=args.output or "outputs/stage4_results",
            weights_path=args.weights,
        )
        print("=== ScholarGuard Stage 4 AI-generation evaluation ===")
    elif args.cross_figure:
        summary = evaluate_cross_figure(
            args.cross_figure, output_dir=args.output or "outputs/stage3_results"
        )
        print("=== ScholarGuard Stage 3 cross-figure evaluation ===")
    else:
        summary = evaluate_dataset(args.data, args.output or "outputs/stage2_results",
                                   clean_dir=args.clean,
                                   save_visualizations=not args.no_viz)
        print("=== ScholarGuard Stage 2 evaluation ===")
    for key, value in summary.items():
        print(f"  {key:28s} {value:.4f}" if isinstance(value, float)
              else f"  {key:28s} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

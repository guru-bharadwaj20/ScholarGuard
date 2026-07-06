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
import os
import time

import numpy as np

from src.detectors.copy_move_detector import CopyMoveDetector
from src.utils.image_io import (
    find_ground_truth_mask,
    list_images,
    load_image,
    load_mask,
)
from src.utils.visualization import save_side_by_side


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

    csv_path = os.path.join(output_dir, "per_image_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

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

    csv_path = os.path.join(output_dir, "cross_figure_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

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

    csv_path = os.path.join(output_dir, "ai_generation_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

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

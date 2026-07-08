"""Analyze benchmark results: per-detector/combined metrics, error breakdown.

Consumes ``benchmark_report.json`` (from benchmark_runner) + the ground truth
and produces:

* per-detector and combined-pipeline confusion matrices + metrics,
* a paper-level score threshold sweep (reuses stored scores; no re-running),
* categorized false positives / false negatives with human-readable reasons,
* annotated visual examples of the worst cases,
* ``metrics_summary.md`` — a report-ready summary.

Measurement only — never runs or modifies a detector.
"""

from __future__ import annotations

import csv
import os

import cv2
import numpy as np

from src.evaluation import metrics as M
from src.evaluation.ground_truth_loader import fraud_type_for_figure

# Map a detector name -> the ground-truth fraud_type it is responsible for.
DETECTOR_TO_FRAUD_TYPE = {
    "copy_move": "copy_move",
    "cross_figure": "cross_figure",
    "ai_generation": "ai_generated",
    "claim_consistency": "claim_mismatch",
}


def _fired(detector: str, result: dict) -> bool:
    """Apply the eval_config 'did this detector fire' rule to a result dict."""
    if detector == "copy_move":
        return bool(result.get("forged"))
    if detector == "cross_figure":
        return result.get("n_exact", 0) > 0 or result.get("n_region_reuse", 0) > 0
    if detector == "ai_generation":
        # A "flag" is ANY non-"likely_real" verdict — this matches how the risk
        # scorer treats it (both "suspicious" and "likely_ai_generated" add risk
        # points). In forensics-only mode (no classifier) genuine AI images
        # typically land at "suspicious" rather than the confident tier.
        return result.get("verdict") in ("suspicious", "likely_ai_generated")
    if detector == "claim_consistency":
        return result.get("consistent") is False
    return False


def _fire_strength(detector: str, result: dict) -> float:
    """A rough magnitude of the detector's signal (for ranking worst cases)."""
    if detector == "copy_move":
        return float(result.get("confidence", 0.0))
    if detector == "cross_figure":
        return float(result.get("n_region_reuse", 0) + result.get("n_exact", 0))
    if detector == "ai_generation":
        return float(result.get("freq_score", 0.0)) + float(result.get("noise_score", 0.0))
    if detector == "claim_consistency":
        return float(result.get("confidence", 0.0))
    return 0.0


def build_records(benchmark: dict):
    """Return (figure_records, paper_records) from a benchmark report."""
    figure_records: list[dict] = []
    paper_records: list[dict] = []

    for pid, entry in benchmark["results"].items():
        gt = entry["ground_truth"]
        report = entry.get("pipeline_report")
        if entry["status"] != "ok" or not report:
            # Paper couldn't be scored; record as a paper-level miss opportunity.
            paper_records.append({
                "paper_id": pid, "gt_fraud": gt["is_fraudulent"],
                "score": None, "status": entry["status"]})
            continue

        paper_records.append({
            "paper_id": pid, "gt_fraud": gt["is_fraudulent"],
            "score": report["overall_risk"]["score"],
            "category": report["overall_risk"]["category"],
            "label_confidence": gt.get("label_confidence", "confirmed"),
            "status": "ok"})

        for fig in report["figures"]:
            fnum = fig.get("figure_num")
            gt_type = fraud_type_for_figure(gt, fnum)
            for det, fraud_type in DETECTOR_TO_FRAUD_TYPE.items():
                res = fig["detectors"].get(det, {"status": "skipped"})
                ran = res.get("status") == "ok"
                figure_records.append({
                    "paper_id": pid, "figure": fig["figure"],
                    "figure_num": fnum, "image_path": fig.get("image_path"),
                    "detector": det, "detector_status": res.get("status"),
                    "ran": ran,
                    "fired": _fired(det, res) if ran else None,
                    "strength": _fire_strength(det, res) if ran else 0.0,
                    "gt_positive": gt_type == fraud_type,
                    "gt_type": gt_type,
                    "paper_is_dose_response": "doseresponse" in pid,
                    "label_confidence": gt.get("label_confidence", "confirmed"),
                })
    return figure_records, paper_records


def per_detector_metrics(figure_records: list[dict]) -> dict:
    """Confusion + metrics per detector, over figures where the detector RAN.

    Figures where a detector was skipped/errored are excluded from that
    detector's confusion matrix (you can't score a detector that didn't run)
    but are counted separately as 'not_evaluated'.
    """
    out: dict = {}
    for det in DETECTOR_TO_FRAUD_TYPE:
        rows = [r for r in figure_records if r["detector"] == det]
        ran = [r for r in rows if r["ran"]]
        y_true = [r["gt_positive"] for r in ran]
        y_pred = [bool(r["fired"]) for r in ran]
        counts = M.confusion_counts(y_true, y_pred)
        out[det] = {
            "metrics": M.binary_metrics(counts),
            "confusion": counts,
            "n_evaluated": len(ran),
            "n_not_evaluated": len(rows) - len(ran),
        }
    return out


def combined_paper_metrics(paper_records: list[dict], threshold: float) -> dict:
    """Paper-level fraud classification: predicted fraud if score >= threshold."""
    scored = [p for p in paper_records if p.get("score") is not None]
    y_true = [p["gt_fraud"] for p in scored]
    y_pred = [p["score"] >= threshold for p in scored]
    return {
        "threshold": threshold,
        "metrics": M.classification_metrics(y_true, y_pred),
        "n_scored": len(scored),
        "n_unscored": len(paper_records) - len(scored),
    }


def categorize_errors(figure_records: list[dict]) -> dict:
    """Split figure-level detector results into FP / FN with reasons."""
    false_positives, false_negatives, not_evaluated = [], [], []

    for r in figure_records:
        if not r["ran"]:
            if r["gt_positive"]:
                not_evaluated.append({**r, "reason": _fn_unavailable_reason(r)})
            continue
        if r["fired"] and not r["gt_positive"]:
            false_positives.append({**r, "reason": _fp_reason(r)})
        elif not r["fired"] and r["gt_positive"]:
            false_negatives.append({**r, "reason": _fn_reason(r)})

    false_positives.sort(key=lambda r: -r["strength"])
    false_negatives.sort(key=lambda r: (r["label_confidence"] != "confirmed",))
    return {"false_positives": false_positives,
            "false_negatives": false_negatives,
            "not_evaluated_positives": not_evaluated}


def _fp_reason(r: dict) -> str:
    det = r["detector"]
    if det == "cross_figure" and r["paper_is_dose_response"]:
        return ("cross-figure flagged a legitimate DOSE-RESPONSE SERIES "
                "(figures similar by design, not reuse)")
    if det == "cross_figure":
        return "cross-figure flagged legitimately similar figures as reuse"
    if det == "copy_move":
        return ("copy-move false-triggered on repetitive/self-similar texture "
                "within a legitimate figure")
    if det == "ai_generation":
        return "AI-detector false-triggered on a real (non-generated) image"
    if det == "claim_consistency":
        return ("claim-consistency flagged a count mismatch on a legitimate "
                "figure (approximate visual count is unreliable)")
    return "unexpected false positive"


def _fn_reason(r: dict) -> str:
    det = r["detector"]
    return {
        "copy_move": "copy-move missed the duplicated region "
                     "(too subtle / low keypoint density / small patch)",
        "cross_figure": "cross-figure missed the reused panel "
                        "(disguising transform, recompression, or small region)",
        "ai_generation": "AI-detector missed — forensic signatures weak on "
                         "this image (no classifier weights loaded)",
        "claim_consistency": "claim-consistency ran but did not flag the "
                             "mismatch (extraction gap or count within tolerance)",
    }.get(det, "missed detection")


def _fn_unavailable_reason(r: dict) -> str:
    if r["detector"] == "claim_consistency":
        return ("claim mismatch NOT EVALUATED — claim-consistency was "
                f"'{r['detector_status']}' (needs ANTHROPIC_API_KEY)")
    return f"{r['detector']} did not run ({r['detector_status']})"


def save_error_examples(errors: dict, output_dir: str, max_per_category: int = 15):
    """Save annotated PNGs of the worst FP/FN cases for human inspection."""
    saved = {"false_positives": [], "false_negatives": []}
    for category in ("false_positives", "false_negatives"):
        cat_dir = os.path.join(output_dir, category)
        os.makedirs(cat_dir, exist_ok=True)
        for i, rec in enumerate(errors[category][:max_per_category]):
            path = _annotate(rec, cat_dir, i, category)
            if path:
                saved[category].append(path)
    return saved


def _annotate(rec: dict, out_dir: str, idx: int, category: str) -> str | None:
    """Render a figure image with a header strip describing the error."""
    img_path = rec.get("image_path")
    if not img_path or not os.path.isfile(img_path):
        return None
    img = cv2.imread(img_path)
    if img is None:
        return None
    img = cv2.resize(img, (min(480, img.shape[1] * 2), min(360, img.shape[0] * 2)),
                     interpolation=cv2.INTER_NEAREST) if img.shape[1] < 240 else img
    h, w = img.shape[:2]
    header = np.full((70, w, 3), 30, np.uint8)
    tag = "FALSE POSITIVE" if category == "false_positives" else "FALSE NEGATIVE"
    color = (0, 0, 220) if category == "false_positives" else (0, 140, 255)
    cv2.putText(header, f"{tag}: {rec['detector']}", (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
    cv2.putText(header, f"{rec['paper_id']} {rec['figure']}", (8, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)
    reason = rec["reason"]
    cv2.putText(header, reason[:70], (8, 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 180, 180), 1, cv2.LINE_AA)
    canvas = np.vstack([header, img])
    path = os.path.join(out_dir, f"{idx:02d}_{rec['paper_id']}_{rec['detector']}.png")
    cv2.imwrite(path, canvas)
    return path


def recommend_threshold(sweep_rows: list[dict]) -> dict:
    """Recommend an operating threshold, prioritizing FEW FALSE POSITIVES.

    In this domain a false accusation is far costlier than a missed case at the
    screening stage (a human reviews every flag). So we recommend the LOWEST
    score threshold that achieves zero false positives (precision == 1.0) while
    keeping recall as high as possible; if none is FP-free, we fall back to the
    max-F1 threshold and flag the residual false-positive rate.
    """
    fp_free = [r for r in sweep_rows
               if r["metrics"]["precision"] == 1.0 and r["metrics"]["tp"] > 0]
    if fp_free:
        best = max(fp_free, key=lambda r: (r["metrics"]["recall"] or 0,
                                           -r["threshold"]))
        return {"threshold": best["threshold"], "basis": "zero-false-positive",
                "precision": best["metrics"]["precision"],
                "recall": best["metrics"]["recall"],
                "rationale": ("lowest paper-score cutoff that produces NO false "
                              "positives on the control set, maximizing recall "
                              "within that constraint — chosen because a false "
                              "accusation is costlier than a missed case at "
                              "screening.")}
    # No FP-free point. Pick the best F1 among NON-degenerate cutoffs (exclude
    # "flag everything", FPR == 1.0, which trivially maximizes recall/F1 but has
    # zero triage value). Tie-break toward the higher threshold — fewer flags,
    # fewer false accusations, matching the domain's asymmetric cost.
    usable = [r for r in sweep_rows
              if r["metrics"]["f1"] is not None
              and (r["metrics"]["false_positive_rate"] or 0) < 1.0]
    if not usable:
        usable = [r for r in sweep_rows if r["metrics"]["f1"] is not None] \
            or sweep_rows
    best = max(usable, key=lambda r: (r["metrics"]["f1"] or 0, r["threshold"]))
    return {"threshold": best["threshold"], "basis": "best F1 (no FP-free point)",
            "precision": best["metrics"]["precision"],
            "recall": best["metrics"]["recall"],
            "false_positive_rate": best["metrics"]["false_positive_rate"],
            "rationale": ("NO cutoff eliminated false positives on this set — the "
                          "cross-figure detector over-flags legitimately-similar "
                          "figures (dose-response series). This is the best F1 "
                          "among non-degenerate cutoffs; the residual false-"
                          "positive rate is real and MUST be shown to reviewers. "
                          "The fix is better cross-figure specificity, not "
                          "threshold tuning.")}


# --------------------------------------------------------------------------
# Analysis orchestration: benchmark report -> metrics + CSV + examples + md
# --------------------------------------------------------------------------
def analyze_benchmark(benchmark: dict, eval_settings: dict,
                      output_dir: str) -> dict:
    """Compute all metrics, write CSV + examples + metrics_summary.md."""
    os.makedirs(output_dir, exist_ok=True)
    figure_records, paper_records = build_records(benchmark)

    det_metrics = per_detector_metrics(figure_records)
    threshold = float(eval_settings.get("decision", {}).get(
        "paper_score_threshold", 25.0))
    combined = combined_paper_metrics(paper_records, threshold)

    # Threshold sweep (reuses stored paper scores — no detector re-runs).
    scored = [p for p in paper_records if p.get("score") is not None]
    sweep = M.score_threshold_sweep(
        [p["gt_fraud"] for p in scored], [p["score"] for p in scored])
    csv_path = os.path.join(output_dir, "threshold_sweep_results.csv")
    _write_sweep_csv(sweep, csv_path)
    recommendation = recommend_threshold(sweep)

    errors = categorize_errors(figure_records)
    ea_dir = os.path.join(output_dir, "error_analysis")
    max_ex = int(eval_settings.get("error_analysis", {}).get(
        "max_examples_per_category", 15))
    saved_examples = save_error_examples(errors, ea_dir, max_ex)

    summary = {
        "dataset": benchmark.get("meta", {}),
        "per_detector": det_metrics,
        "combined_paper": combined,
        "threshold_recommendation": recommendation,
        "errors": {
            "n_false_positives": len(errors["false_positives"]),
            "n_false_negatives": len(errors["false_negatives"]),
            "n_not_evaluated_positives": len(errors["not_evaluated_positives"]),
        },
        "error_examples_saved": {k: len(v) for k, v in saved_examples.items()},
        "sweep_csv": csv_path,
    }
    md = _render_summary_md(benchmark, det_metrics, combined, sweep,
                            recommendation, errors)
    md_path = os.path.join(output_dir, "metrics_summary.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md)
    summary["metrics_summary_md"] = md_path
    return summary


def _write_sweep_csv(sweep: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["threshold", "precision", "recall", "f1",
                         "false_positive_rate", "accuracy", "tp", "fp", "fn", "tn"])
        for r in sweep:
            m = r["metrics"]
            writer.writerow([r["threshold"], m["precision"], m["recall"], m["f1"],
                             m["false_positive_rate"], m["accuracy"],
                             m["tp"], m["fp"], m["fn"], m["tn"]])


def _fmt(v) -> str:
    return "n/a" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def _render_summary_md(benchmark, det_metrics, combined, sweep,
                       recommendation, errors) -> str:
    meta = benchmark.get("meta", {})
    L: list[str] = []
    L.append("# ScholarGuard — Stage 7 Evaluation: Metrics Summary")
    L.append("")
    L.append(f"- **Dataset:** {meta.get('dataset_name', 'n/a')}")
    L.append(f"- **Papers evaluated:** {meta.get('n_completed', 0)} "
             f"(of {meta.get('n_papers', 0)}; "
             f"{meta.get('n_skipped_missing', 0)} missing PDFs)")
    if meta.get("note"):
        L.append(f"- **Provenance:** {meta['note']}")
    L.append("")
    L.append("> **This is a screening/triage tool for human reviewers, NOT an "
             "autonomous accusation system.** Every flag is a lead to be checked "
             "by a person. The numbers below are REAL pipeline metrics on a "
             "SYNTHETIC stand-in set — see provenance above.")
    L.append("")

    # -- combined pipeline --------------------------------------------------
    cm = combined["metrics"]
    L.append("## Combined pipeline (paper-level fraud classification)")
    L.append(f"Decision rule: a paper is flagged if its overall risk score "
             f">= **{combined['threshold']}**.")
    L.append("")
    L.append(f"- Precision: **{_fmt(cm['precision'])}**  |  "
             f"Recall: **{_fmt(cm['recall'])}**  |  "
             f"F1: **{_fmt(cm['f1'])}**  |  Accuracy: **{_fmt(cm['accuracy'])}**")
    L.append(f"- False-positive rate: **{_fmt(cm['false_positive_rate'])}**  |  "
             f"False-negative rate: **{_fmt(cm['false_negative_rate'])}**")
    L.append("")
    L.append("```")
    L.append(M.confusion_matrix_str(combined["metrics"]))
    L.append("```")
    L.append("")

    # -- per detector -------------------------------------------------------
    L.append("## Per-detector breakdown (figure-level, where the detector ran)")
    L.append("")
    L.append("| Detector | Eval'd | Not eval'd | Precision | Recall | F1 | FPR |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for det, d in det_metrics.items():
        m = d["metrics"]
        L.append(f"| {det} | {d['n_evaluated']} | {d['n_not_evaluated']} | "
                 f"{_fmt(m['precision'])} | {_fmt(m['recall'])} | "
                 f"{_fmt(m['f1'])} | {_fmt(m['false_positive_rate'])} |")
    L.append("")
    L.append("_Recall = of the figures truly manipulated by this method, the "
             "fraction the detector caught. FPR = of the clean figures, the "
             "fraction it wrongly flagged._")
    L.append("")

    # -- threshold sweep + recommendation -----------------------------------
    L.append("## Threshold sweep & recommended operating point")
    L.append("Full curve in `threshold_sweep_results.csv`. Selected rows:")
    L.append("")
    L.append("| Score >= | Precision | Recall | F1 | FPR |")
    L.append("|---:|---:|---:|---:|---:|")
    for r in sweep:
        if r["threshold"] % 10 == 0 or r["threshold"] in (5.0, 25.0):
            m = r["metrics"]
            L.append(f"| {r['threshold']:g} | {_fmt(m['precision'])} | "
                     f"{_fmt(m['recall'])} | {_fmt(m['f1'])} | "
                     f"{_fmt(m['false_positive_rate'])} |")
    L.append("")
    rec = recommendation
    L.append(f"**Recommended threshold: {rec['threshold']:g}** "
             f"(basis: {rec['basis']}).")
    L.append(f"> {rec['rationale']}")
    L.append("")

    # -- errors -------------------------------------------------------------
    L.append("## Error analysis")
    L.append(f"- False positives: **{len(errors['false_positives'])}**  |  "
             f"False negatives: **{len(errors['false_negatives'])}**  |  "
             f"Not evaluated (detector unavailable on a true-positive figure): "
             f"**{len(errors['not_evaluated_positives'])}**")
    L.append("")
    L.append("Annotated worst-case images are in `error_analysis/`.")
    L.append("")
    for cat, title in [("false_positives", "False positives (why the pipeline "
                        "flagged a clean figure)"),
                       ("false_negatives", "False negatives (why the pipeline "
                        "missed a manipulated figure)"),
                       ("not_evaluated_positives", "Not evaluated (true-positive "
                        "figures a detector couldn't score)")]:
        rows = errors[cat]
        if not rows:
            continue
        L.append(f"### {title}")
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["reason"]] = counts.get(r["reason"], 0) + 1
        for reason, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            L.append(f"- ({n}x) {reason}")
        L.append("")

    L.append("---")
    L.append("_Generated by src/evaluation/error_analysis.py. Flags are leads "
             "for human review, not proof of misconduct._")
    return "\n".join(L)

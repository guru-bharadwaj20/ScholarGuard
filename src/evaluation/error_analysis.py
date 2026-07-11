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


def load_subset_map(labels_path: str) -> dict[str, str]:
    """paper_id -> subset ("dose_response" | "generic"), read from labels.json.

    ``ground_truth_loader`` drops unknown keys, so the subset (which marks the
    dose-response false-positive traps) has to come from the labels file itself.
    """
    import json
    try:
        with open(labels_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {p["paper_id"]: p["subset"] for p in data.get("papers", [])
            if p.get("subset")}


def build_records(benchmark: dict, subset_map: dict[str, str] | None = None):
    """Return (figure_records, paper_records) from a benchmark report."""
    subset_map = subset_map or {}
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

        # A fraud paper with no figure-level annotation (figure_num all null,
        # as Retraction Watch data always is) tells us the PAPER is fraudulent
        # but NOT which figure. Its figures are therefore UNLABELED — treating
        # them as ground-truth negatives would turn every correct detection
        # into a "false positive" and make per-detector metrics meaningless.
        paper_is_fraud = bool(gt.get("is_fraudulent"))
        has_figure_annotations = any(
            f.get("figure_num") is not None for f in gt.get("figures", []))
        gt_known = (not paper_is_fraud) or has_figure_annotations

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
                    "gt_known": gt_known,
                    "paper_is_fraud": paper_is_fraud,
                    "paper_is_dose_response": ("doseresponse" in pid
                                               or subset_map.get(pid) == "dose_response"),
                    "label_confidence": gt.get("label_confidence", "confirmed"),
                })
    return figure_records, paper_records


def per_detector_metrics(figure_records: list[dict]) -> dict:
    """Confusion + metrics per detector, over figures that are SCOREABLE.

    A figure is scoreable for a detector only if (a) the detector actually ran
    on it, and (b) its ground-truth label is known. Figures of a fraud paper
    that carries no figure-level annotation are UNLABELED, not negative — they
    are excluded and counted as ``n_unlabeled``. Figures where the detector was
    skipped/errored are counted as ``n_not_evaluated``.
    """
    out: dict = {}
    for det in DETECTOR_TO_FRAUD_TYPE:
        rows = [r for r in figure_records if r["detector"] == det]
        ran = [r for r in rows if r["ran"]]
        scoreable = [r for r in ran if r["gt_known"]]
        y_true = [r["gt_positive"] for r in scoreable]
        y_pred = [bool(r["fired"]) for r in scoreable]
        counts = M.confusion_counts(y_true, y_pred)
        # How often it fired on the unlabeled fraud figures — informative, but
        # NOT scoreable as either a hit or a false alarm.
        unlabeled = [r for r in ran if not r["gt_known"]]
        out[det] = {
            "metrics": M.binary_metrics(counts),
            "ci": M.metrics_with_confidence(counts),
            "confusion": counts,
            "n_evaluated": len(scoreable),
            "n_not_evaluated": len(rows) - len(ran),
            "n_unlabeled": len(unlabeled),
            "n_fired_on_unlabeled": sum(1 for r in unlabeled if r["fired"]),
        }
    return out


def combined_paper_metrics(paper_records: list[dict], threshold: float) -> dict:
    """Paper-level fraud classification: predicted fraud if score >= threshold."""
    scored = [p for p in paper_records if p.get("score") is not None]
    y_true = [p["gt_fraud"] for p in scored]
    y_pred = [p["score"] >= threshold for p in scored]
    counts = M.confusion_counts(y_true, y_pred)
    return {
        "threshold": threshold,
        "metrics": M.binary_metrics(counts),
        "ci": M.metrics_with_confidence(counts),
        "n_scored": len(scored),
        "n_unscored": len(paper_records) - len(scored),
    }


def categorize_errors(figure_records: list[dict]) -> dict:
    """Split figure-level detector results into FP / FN with reasons.

    Detections on the figures of an unannotated fraud paper are neither: we do
    not know which figure was manipulated, so they land in ``unlabeled_hits``
    for human triage rather than being scored as false positives.
    """
    false_positives, false_negatives, not_evaluated = [], [], []
    unlabeled_hits = []

    for r in figure_records:
        if not r["ran"]:
            if r["gt_positive"]:
                not_evaluated.append({**r, "reason": _fn_unavailable_reason(r)})
            continue
        if not r["gt_known"]:
            if r["fired"]:
                unlabeled_hits.append({**r, "reason": (
                    "fired on a figure of a CONFIRMED-FRAUD paper whose "
                    "manipulated figure is not annotated - cannot be scored as "
                    "a hit or a false alarm; needs manual figure-level review")})
            continue
        if r["fired"] and not r["gt_positive"]:
            false_positives.append({**r, "reason": _fp_reason(r)})
        elif not r["fired"] and r["gt_positive"]:
            false_negatives.append({**r, "reason": _fn_reason(r)})

    false_positives.sort(key=lambda r: -r["strength"])
    false_negatives.sort(key=lambda r: (r["label_confidence"] != "confirmed",))
    unlabeled_hits.sort(key=lambda r: -r["strength"])
    return {"false_positives": false_positives,
            "false_negatives": false_negatives,
            "not_evaluated_positives": not_evaluated,
            "unlabeled_hits": unlabeled_hits}


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


def load_baseline_metrics(baseline_benchmark_path: str,
                          threshold: float = 25.0) -> dict | None:
    """Recompute a prior run's metrics for side-by-side comparison.

    Reads only the benchmark report (which embeds each paper's ground truth),
    so it works even if that run's labels.json has since been replaced. Returns
    None if the baseline is absent.
    """
    import json
    if not baseline_benchmark_path or not os.path.isfile(baseline_benchmark_path):
        return None
    try:
        with open(baseline_benchmark_path, encoding="utf-8") as fh:
            benchmark = json.load(fh)
    except (OSError, ValueError):
        return None
    if not benchmark.get("results"):
        return None
    # Synthetic paper_ids embed "doseresponse", so no subset map is needed.
    figure_records, paper_records = build_records(benchmark)
    n_fraud = sum(1 for r in benchmark["results"].values()
                  if r["ground_truth"].get("is_fraudulent"))
    return {
        "dataset_name": benchmark.get("meta", {}).get("dataset_name", "baseline"),
        "n_fraud": n_fraud,
        "n_clean": len(benchmark["results"]) - n_fraud,
        "per_detector": per_detector_metrics(figure_records),
        "combined": combined_paper_metrics(paper_records, threshold),
    }


def _cmp_cell(det_block: dict | None, rate: str) -> str:
    """Render one comparison cell, honouring 'not measurable' / 'not evaluated'."""
    if det_block is None:
        return "—"
    if det_block["n_evaluated"] == 0:
        return "_not evaluated_"
    support_pos = det_block["confusion"]["tp"] + det_block["confusion"]["fn"]
    if rate in ("precision", "recall") and support_pos == 0:
        return "_not measurable_"
    return M.format_metric_with_ci(det_block["ci"][rate])


def _comparison_labels(base_name: str, cur_name: str) -> tuple[str, str]:
    """Honest column labels for the side-by-side table.

    The baseline is whatever prior benchmark ``comparison.baseline_benchmark``
    points at — it is NOT necessarily the synthetic run. When the baseline and
    the current run use the *same* dataset (e.g. a before/after comparison of a
    detector change on the same real papers), label them "Baseline run" / "This
    run"; when they differ, tag each by whether it is the synthetic or a real
    set so the columns can never be silently mislabeled.
    """
    def tag(name: str) -> str:
        nl = (name or "").lower()
        if "synthetic" in nl:
            return "Synthetic"
        if "real" in nl:
            return "Real"
        return name or "baseline"

    if (base_name or "") == (cur_name or "") and base_name:
        return "Baseline run", "This run"
    return tag(base_name), tag(cur_name)


def render_comparison_section(baseline: dict, real_det: dict,
                              real_comb: dict, n_fraud: int, n_clean: int,
                              base_label: str = "Baseline",
                              cur_label: str = "This run") -> list[str]:
    """Markdown for the baseline-vs-this-run side-by-side comparison.

    ``base_label`` / ``cur_label`` name the two columns — derived from the two
    runs' dataset names by :func:`_comparison_labels`, never hard-coded, so the
    baseline column always reflects what the baseline actually is.
    """
    L: list[str] = []
    L.append(f"## Side-by-side: {base_label.lower()} vs. {cur_label.lower()}")
    L.append("")
    L.append(f"Baseline: `{baseline['dataset_name']}` "
             f"(N={baseline['n_fraud']} fraud, N={baseline['n_clean']} clean). "
             f"This run: N={n_fraud} fraud, N={n_clean} clean.")
    L.append("")
    L.append("All values carry 95% Wilson CIs. **Read the intervals** — at this "
             "sample size small-count point estimates on either side can look "
             "firmer than they are (some rest on as few as 2 positive figures).")
    L.append("")
    L.append("### Per-detector, figure-level")
    L.append("")
    L.append(f"| Detector | Metric | {base_label} | {cur_label} |")
    L.append("|---|---|---|---|")
    for det in DETECTOR_TO_FRAUD_TYPE:
        base = baseline["per_detector"].get(det)
        real = real_det.get(det)
        for rate, label in [("precision", "precision"), ("recall", "recall"),
                            ("false_positive_rate", "FPR")]:
            L.append(f"| `{det}` | {label} | {_cmp_cell(base, rate)} | "
                     f"{_cmp_cell(real, rate)} |")
    L.append("")

    L.append("### Combined pipeline, paper-level")
    L.append("")
    L.append(f"| Metric | {base_label} | {cur_label} |")
    L.append("|---|---|---|")
    bc, rc = baseline["combined"]["ci"], real_comb["ci"]
    for rate, label in [("precision", "precision"), ("recall", "recall"),
                        ("false_positive_rate", "FPR"), ("accuracy", "accuracy")]:
        L.append(f"| {label} | {M.format_metric_with_ci(bc[rate])} | "
                 f"{M.format_metric_with_ci(rc[rate])} |")
    bf = baseline["combined"]["metrics"]["f1"]
    rf = real_comb["metrics"]["f1"]
    L.append(f"| F1 _(no CI)_ | {_fmt(bf)} | {_fmt(rf)} |")
    L.append("")
    return L


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
    labels_path = (eval_settings.get("evaluation_set", {}) or {}).get("labels_path")
    subset_map = load_subset_map(labels_path) if labels_path else {}
    figure_records, paper_records = build_records(benchmark, subset_map)

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

    # Optional side-by-side against a prior run (e.g. the synthetic baseline).
    baseline_path = (eval_settings.get("comparison", {}) or {}).get(
        "baseline_benchmark")
    baseline = load_baseline_metrics(baseline_path, threshold) if baseline_path \
        else None

    summary = {
        "dataset": benchmark.get("meta", {}),
        "per_detector": det_metrics,
        "combined_paper": combined,
        "threshold_recommendation": recommendation,
        "errors": {
            "n_false_positives": len(errors["false_positives"]),
            "n_false_negatives": len(errors["false_negatives"]),
            "n_not_evaluated_positives": len(errors["not_evaluated_positives"]),
            "n_unlabeled_hits": len(errors["unlabeled_hits"]),
        },
        "error_examples_saved": {k: len(v) for k, v in saved_examples.items()},
        "sweep_csv": csv_path,
        "baseline_compared": bool(baseline),
    }
    md = _render_summary_md(benchmark, det_metrics, combined, sweep,
                            recommendation, errors, baseline)
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
                       recommendation, errors, baseline=None) -> str:
    meta = benchmark.get("meta", {})
    dataset = str(meta.get("dataset_name", "n/a"))
    is_real = "real" in dataset.lower()

    # Ground-truth class balance, for the heading and the CI denominators.
    n_fraud = sum(1 for r in benchmark["results"].values()
                  if r["ground_truth"].get("is_fraudulent"))
    n_clean = len(benchmark["results"]) - n_fraud

    L: list[str] = []
    kind = "Real-Data" if is_real else "Synthetic-Data"
    L.append(f"# ScholarGuard — Stage 7 {kind} Evaluation "
             f"(N={n_fraud} fraud, N={n_clean} clean)")
    L.append("")
    L.append(f"- **Dataset:** `{dataset}`")
    L.append(f"- **Papers evaluated:** {meta.get('n_completed', 0)} "
             f"(of {meta.get('n_papers', 0)}; "
             f"{meta.get('n_skipped_missing', 0)} missing PDFs)")
    if meta.get("note"):
        L.append(f"- **Provenance:** {meta['note']}")
    L.append("")
    L.append("> **This is a screening/triage tool for human reviewers, NOT an "
             "autonomous accusation system.** Every flag is a lead to be checked "
             "by a person.")
    if is_real:
        L.append(">")
        L.append("> **Small-sample warning.** With N=%d fraud / N=%d clean, point "
                 "estimates are unstable. Every rate below carries a 95%% Wilson "
                 "confidence interval; read the interval, not the point."
                 % (n_fraud, n_clean))
    else:
        L.append(">")
        L.append("> The numbers below are REAL pipeline metrics on a SYNTHETIC "
                 "stand-in set — see provenance above.")
    L.append("")

    # -- what this run can and cannot measure -------------------------------
    L.append("## What this run does and does not measure")
    for det, d in det_metrics.items():
        support_pos = d["confusion"]["tp"] + d["confusion"]["fn"]
        if d["n_evaluated"] == 0:
            L.append(f"- **{det}: NOT EVALUATED** — the detector did not run on "
                     f"any figure ({d['n_not_evaluated']} figures skipped). "
                     f"Reported as neither passing nor failing.")
        elif support_pos == 0:
            L.append(f"- **{det}: recall NOT MEASURABLE** — there are no "
                     f"ground-truth positive figures for it in this set. Only "
                     f"its false-positive rate on clean figures is measured "
                     f"({d['confusion']['fp'] + d['confusion']['tn']} figures).")
        else:
            L.append(f"- **{det}:** evaluated on {d['n_evaluated']} figure(s), "
                     f"{support_pos} ground-truth positive.")
    L.append("")

    # -- combined pipeline --------------------------------------------------
    cm = combined["metrics"]
    ci = combined.get("ci", {})
    L.append("## Combined pipeline (paper-level fraud classification)")
    L.append(f"Decision rule: a paper is flagged if its overall risk score "
             f">= **{combined['threshold']}**. All rates carry 95% Wilson "
             f"confidence intervals — at this sample size the point estimate "
             f"alone is misleading.")
    L.append("")
    for key, label in [("precision", "Precision"), ("recall", "Recall"),
                       ("false_positive_rate", "False-positive rate"),
                       ("false_negative_rate", "False-negative rate"),
                       ("accuracy", "Accuracy")]:
        if key in ci:
            L.append(f"- **{label}:** {M.format_metric_with_ci(ci[key])}")
    L.append(f"- **F1:** {_fmt(cm['f1'])}  _(harmonic mean of two proportions "
             f"— not a binomial proportion, so no Wilson interval)_")
    L.append("")
    L.append("```")
    L.append(M.confusion_matrix_str(combined["metrics"]))
    L.append("```")
    L.append("")

    # -- per detector -------------------------------------------------------
    L.append("## Per-detector breakdown (figure-level, scoreable figures only)")
    L.append("")
    total_unlabeled = max((d.get("n_unlabeled", 0) for d in det_metrics.values()),
                          default=0)
    if total_unlabeled:
        L.append(f"> **{total_unlabeled} figures excluded per detector.** They "
                 f"belong to confirmed-fraud papers with no figure-level "
                 f"annotation, so their true label is UNKNOWN. Counting them as "
                 f"negatives would turn correct detections into false positives; "
                 f"counting them as positives would assume which figure was "
                 f"manipulated. They are excluded and reported separately.")
        L.append("")
    L.append("| Detector | Scoreable | Unlabeled | Not eval'd | Precision | Recall | FPR |")
    L.append("|---|---:|---:|---:|---|---|---|")
    for det, d in det_metrics.items():
        dci = d.get("ci", {})
        unl, note = d.get("n_unlabeled", 0), d.get("n_not_evaluated", 0)
        if d["n_evaluated"] == 0:
            L.append(f"| {det} | 0 | {unl} | {note} | _not evaluated_ | "
                     f"_not evaluated_ | _not evaluated_ |")
            continue
        support_pos = d["confusion"]["tp"] + d["confusion"]["fn"]
        prec = (M.format_metric_with_ci(dci["precision"]) if support_pos
                else "_not measurable_")
        rec = (M.format_metric_with_ci(dci["recall"]) if support_pos
               else "_not measurable_")
        L.append(f"| {det} | {d['n_evaluated']} | {unl} | {note} | {prec} | "
                 f"{rec} | {M.format_metric_with_ci(dci['false_positive_rate'])} |")
    L.append("")
    L.append("_FPR = of the CLEAN figures it was scored on, the fraction it "
             "wrongly flagged. Precision/recall are `not measurable` where the "
             "set contains no ground-truth positive figures for that detector. "
             "`n` in each interval is that metric's own denominator._")
    L.append("")

    fired_unlabeled = {det: d.get("n_fired_on_unlabeled", 0)
                       for det, d in det_metrics.items()}
    if total_unlabeled and any(fired_unlabeled.values()):
        L.append("**Detections on unlabeled fraud-paper figures** (each is a "
                 "lead for manual review, scoreable as neither hit nor miss): "
                 + ", ".join(f"`{d}`: {n}" for d, n in fired_unlabeled.items() if n))
        L.append("")

    # -- baseline vs this-run comparison ------------------------------------
    if baseline:
        base_label, cur_label = _comparison_labels(
            baseline.get("dataset_name", ""), dataset)
        L.extend(render_comparison_section(baseline, det_metrics, combined,
                                           n_fraud, n_clean,
                                           base_label, cur_label))

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
             f"**{len(errors['not_evaluated_positives'])}**  |  "
             f"Unlabeled hits (fraud paper, unknown figure): "
             f"**{len(errors.get('unlabeled_hits', []))}**")
    L.append("")
    L.append("Annotated worst-case images are in `error_analysis/` (figure crops "
             "and detector output only — no paper text is reproduced).")
    L.append("")
    for cat, title in [("false_positives", "False positives (why the pipeline "
                        "flagged a clean figure)"),
                       ("false_negatives", "False negatives (why the pipeline "
                        "missed a manipulated figure)"),
                       ("not_evaluated_positives", "Not evaluated (true-positive "
                        "figures a detector couldn't score)"),
                       ("unlabeled_hits", "Unlabeled hits (detections on "
                        "confirmed-fraud papers, figure unknown)")]:
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

"""Offline recalibration + likelihood-ratio fusion, measured under LOOCV.

This module improves the paper-level decision WITHOUT re-running the 1-hour
pipeline: every per-figure detector signal it needs (copy-move ``confidence``,
cross-figure counts, the AI detector's raw ``freq_score`` / ``noise_score``)
is already stored in ``benchmark_report.json``. It re-derives paper scores
under three fixes and reports honest, out-of-sample metrics:

  1. **AI baseline recalibrated to native images.** The shipped baseline was
     measured on PDF-extracted figures; native PMC-package images keep their
     sensor noise and score differently, which inflated the AI false-alarm
     rate. Here the baseline (mean/std of the forensic score over CLEAN
     figures) is refit from the data at hand.

  2. **Per-figure copy-move threshold tightened.** Copy-move's confidence
     cutoff is raised to whatever value hits a target per-figure
     false-positive rate on clean figures — the single biggest lever on the
     paper-level score, because a high per-figure FPR compounds across
     multi-figure papers.

  3. **Paper-level likelihood-ratio fusion.** Only paper-level fraud labels
     exist (not which figure), so detectors are fused at the paper level: a
     detector "fires" on a paper if any figure fires, and its likelihood
     ratio ``P(fire|fraud)/P(fire|clean)`` is estimated from data. A detector
     that fires about equally on fraud and clean gets LR≈1 and is discounted
     automatically.

**Honesty:** every quantity is fit under leave-one-out — for each held-out
paper, the baseline, the copy-move threshold, and the likelihood ratios are
estimated on the OTHER papers only, then applied to the held-out one. The
pooled predictions are therefore out-of-sample, not fit to the papers they
score. Compared against the pipeline's current stored scores as a baseline.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass

from src.evaluation import metrics as M

_EPS = 1e-6
DETECTORS = ("copy_move", "cross_figure", "ai_generation")


@dataclass
class Paper:
    """Per-paper detector signals + ground truth, pulled from the report."""

    paper_id: str
    gt_fraud: bool
    # per-figure signals (flat, one entry per figure the detector ran on)
    cm_conf: list[float]        # copy-move confidence, one per figure
    cf_fire: list[bool]         # cross-figure fired (exact or region reuse)
    ai_forensic: list[float]    # 0.5*(freq+noise) per figure
    # per-figure ALIGNED signals: one dict per figure, missing detectors -> None.
    # This is what corroboration (co-firing on the SAME figure) needs.
    figures: list[dict]
    stored_score: float         # pipeline's current paper point-score (baseline)
    stored_prob: float          # pipeline's current fraud_probability (baseline)


def load_papers(report: dict) -> list[Paper]:
    """Extract per-paper signals from a benchmark_report.json dict."""
    papers: list[Paper] = []
    for pid, entry in report["results"].items():
        rep = entry.get("pipeline_report")
        if entry.get("status") != "ok" or not rep or not rep.get("figures"):
            continue
        cm_conf, cf_fire, ai_forensic = [], [], []
        figures: list[dict] = []
        for fig in rep["figures"]:
            d = fig["detectors"]
            rec = {"cm_conf": None, "cf_fire": None, "ai_forensic": None}
            cm = d.get("copy_move", {})
            if cm.get("status") == "ok":
                rec["cm_conf"] = float(cm.get("confidence", 0.0))
                cm_conf.append(rec["cm_conf"])
            cf = d.get("cross_figure", {})
            if cf.get("status") == "ok":
                rec["cf_fire"] = (cf.get("n_exact", 0) > 0
                                  or cf.get("n_region_reuse", 0) > 0)
                cf_fire.append(rec["cf_fire"])
            ai = d.get("ai_generation", {})
            if ai.get("status") == "ok" and ai.get("freq_score") is not None:
                rec["ai_forensic"] = 0.5 * (float(ai["freq_score"])
                                            + float(ai["noise_score"]))
                ai_forensic.append(rec["ai_forensic"])
            figures.append(rec)
        papers.append(Paper(
            paper_id=pid,
            gt_fraud=bool(entry["ground_truth"]["is_fraudulent"]),
            cm_conf=cm_conf, cf_fire=cf_fire, ai_forensic=ai_forensic,
            figures=figures,
            stored_score=float(rep["overall_risk"].get("score", 0.0)),
            stored_prob=float(rep["overall_risk"].get("fraud_probability", 0.0)),
        ))
    return papers


def _figure_fires(fig: dict, cal: "Calibration") -> dict:
    """Which detectors fire on a SINGLE figure under a calibration."""
    cm = fig["cm_conf"] is not None and fig["cm_conf"] >= cal.cm_threshold
    cf = bool(fig["cf_fire"])
    ai = (fig["ai_forensic"] is not None
          and (fig["ai_forensic"] - cal.ai_mean) / cal.ai_std >= cal.ai_z)
    return {"copy_move": cm, "cross_figure": cf, "ai_generation": ai}


def paper_scores(paper: Paper, cal: "Calibration") -> dict:
    """Candidate paper-level scores that treat multi-figure compounding differently.

    * ``any_fire_count`` — total detector-fires across ALL figures. This is the
      compounding-prone baseline: more figures => more chances to fire.
    * ``max_cofire`` — the most detectors firing on a SINGLE figure (0..3).
      Corroboration: a figure with 2-3 independent signals is real evidence;
      a paper full of lone single-detector fires (usually false positives) is
      not. Insensitive to figure count, so it does not compound.
    * ``best_figure_llr`` — max over figures of that figure's summed
      log-likelihood-ratio evidence. Localises the decision to the single
      most-suspicious figure instead of smearing weak evidence across many.
    """
    best_cofire = 0
    best_llr = -1e9
    for fig in paper.figures:
        fires = _figure_fires(fig, cal)
        cofire = sum(fires.values())
        best_cofire = max(best_cofire, cofire)
        if cal.lrs:
            llr = 0.0
            for d in DETECTORS:
                pf, pc = cal.lrs[d]
                pf = min(max(pf, _EPS), 1 - _EPS)
                pc = min(max(pc, _EPS), 1 - _EPS)
                llr += (math.log(pf / pc) if fires[d]
                        else math.log((1 - pf) / (1 - pc)))
            best_llr = max(best_llr, llr)
    any_fire_count = sum(sum(_figure_fires(f, cal).values())
                         for f in paper.figures)
    return {"any_fire_count": any_fire_count, "max_cofire": best_cofire,
            "best_figure_llr": best_llr}


# --------------------------------------------------------------- calibration
@dataclass
class Calibration:
    cm_threshold: float          # copy-move confidence cutoff
    ai_mean: float               # forensic baseline on clean figures
    ai_std: float
    ai_z: float                  # z above baseline that counts as an AI hit
    lrs: dict                    # detector -> (p_fire_fraud, p_fire_clean)
    prior: float


def _clean_quantile(train: list[Paper], target_fpr: float) -> float:
    """Copy-move cutoff = the (1-target_fpr) quantile of clean-figure conf.

    Setting the threshold at that quantile makes, by construction, ~target_fpr
    of clean figures score above it on the training papers.
    """
    clean_conf = sorted(c for p in train if not p.gt_fraud for c in p.cm_conf)
    if not clean_conf:
        return 0.45
    idx = min(len(clean_conf) - 1,
              int(math.ceil((1.0 - target_fpr) * len(clean_conf))) - 1)
    return clean_conf[max(0, idx)]


def _ai_baseline(train: list[Paper]) -> tuple[float, float]:
    """Mean/std of the forensic score over CLEAN figures (native-image fit)."""
    vals = [f for p in train if not p.gt_fraud for f in p.ai_forensic]
    if len(vals) < 2:
        return 0.35, 0.10
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return mean, math.sqrt(var) + _EPS


def paper_fires(paper: Paper, cal: Calibration) -> dict:
    """Which detectors fire on this paper under a given calibration."""
    cm = any(c >= cal.cm_threshold for c in paper.cm_conf)
    cf = any(paper.cf_fire)
    ai = any((f - cal.ai_mean) / cal.ai_std >= cal.ai_z for f in paper.ai_forensic)
    return {"copy_move": cm, "cross_figure": cf, "ai_generation": ai}


def _fit_lrs(train: list[Paper], cal_wo_lrs: Calibration) -> dict:
    """Laplace-smoothed paper-level P(fire|fraud), P(fire|clean) per detector."""
    lrs = {}
    fired = {d: {"fraud": 0, "clean": 0} for d in DETECTORS}
    n_fraud = sum(1 for p in train if p.gt_fraud)
    n_clean = len(train) - n_fraud
    for p in train:
        f = paper_fires(p, cal_wo_lrs)
        for d in DETECTORS:
            if f[d]:
                fired[d]["fraud" if p.gt_fraud else "clean"] += 1
    for d in DETECTORS:
        pf = (fired[d]["fraud"] + 1) / (n_fraud + 2)
        pc = (fired[d]["clean"] + 1) / (n_clean + 2)
        lrs[d] = (pf, pc)
    return lrs


def fit_calibration(train: list[Paper], target_fpr: float, ai_z: float,
                    prior: float) -> Calibration:
    cm_threshold = _clean_quantile(train, target_fpr)
    ai_mean, ai_std = _ai_baseline(train)
    cal = Calibration(cm_threshold, ai_mean, ai_std, ai_z, {}, prior)
    cal.lrs = _fit_lrs(train, cal)
    return cal


def posterior(paper: Paper, cal: Calibration) -> float:
    """Fraud probability from paper-level LLR fusion."""
    log_odds = math.log(cal.prior / (1.0 - cal.prior))
    fires = paper_fires(paper, cal)
    for d in DETECTORS:
        pf, pc = cal.lrs[d]
        pf = min(max(pf, _EPS), 1 - _EPS)
        pc = min(max(pc, _EPS), 1 - _EPS)
        log_odds += (math.log(pf / pc) if fires[d]
                     else math.log((1 - pf) / (1 - pc)))
    return 1.0 / (1.0 + math.exp(-log_odds))


# ------------------------------------------------------------------- LOOCV
def loocv_predictions(papers: list[Paper], target_fpr: float, ai_z: float,
                      prior: float) -> list[tuple[bool, float]]:
    """(gt_fraud, recalibrated posterior) for each paper, fit on the rest."""
    out = []
    for i, held in enumerate(papers):
        train = [p for j, p in enumerate(papers) if j != i]
        cal = fit_calibration(train, target_fpr, ai_z, prior)
        out.append((held.gt_fraud, posterior(held, cal)))
    return out


def _metrics(pairs: list[tuple[bool, float]], threshold: float) -> dict:
    y = [t for t, _ in pairs]
    s = [p for _, p in pairs]
    pred = [p >= threshold for p in s]
    counts = M.confusion_counts(y, pred)
    m = M.binary_metrics(counts)
    return {
        "roc_auc": M.roc_auc(y, s),
        "average_precision": M.average_precision(y, s),
        "accuracy": m["accuracy"], "precision": m["precision"],
        "recall": m["recall"], "false_positive_rate": m["false_positive_rate"],
        "confusion": counts,
    }


def run(report_path: str, target_fpr: float, ai_z: float, prior: float,
        decision_threshold: float) -> dict:
    with open(report_path, encoding="utf-8") as fh:
        report = json.load(fh)
    papers = load_papers(report)
    n_fraud = sum(1 for p in papers if p.gt_fraud)

    # Baseline = the pipeline's CURRENT stored fraud_probability (uncalibrated
    # fusion), scored the same way for an apples-to-apples comparison.
    base_pairs = [(p.gt_fraud, p.stored_prob) for p in papers]
    base = {"roc_auc": M.roc_auc([t for t, _ in base_pairs],
                                 [s for _, s in base_pairs]),
            "average_precision": M.average_precision(
                [t for t, _ in base_pairs], [s for _, s in base_pairs])}

    recal_pairs = loocv_predictions(papers, target_fpr, ai_z, prior)
    recal = _metrics(recal_pairs, decision_threshold)

    # Full-data LR table (display only) to show which detector discriminates.
    full_cal = fit_calibration(papers, target_fpr, ai_z, prior)
    lr_table = {d: {"p_fire_fraud": round(full_cal.lrs[d][0], 3),
                    "p_fire_clean": round(full_cal.lrs[d][1], 3),
                    "likelihood_ratio": round(full_cal.lrs[d][0]
                                              / max(full_cal.lrs[d][1], _EPS), 2)}
                for d in DETECTORS}

    return {
        "n_papers": len(papers), "n_fraud": n_fraud,
        "n_clean": len(papers) - n_fraud,
        "copy_move_threshold_median_fold": round(full_cal.cm_threshold, 3),
        "ai_baseline_full": {"mean": round(full_cal.ai_mean, 3),
                             "std": round(full_cal.ai_std, 3), "z": ai_z},
        "likelihood_ratios": lr_table,
        "baseline_stored_fusion": {k: base[k] for k in
                                   ("roc_auc", "average_precision")},
        "recalibrated_loocv": recal,
    }


def compare_scoring(papers: list[Paper], target_fpr: float, ai_z: float,
                    prior: float) -> dict:
    """ROC-AUC of each paper-scoring scheme (threshold-free ranking).

    Directly tests the compounding hypothesis: if ``max_cofire`` /
    ``best_figure_llr`` (figure-count-insensitive) beat ``any_fire_count``
    (compounding), then requiring corroboration on a single figure is the win.
    Uses a full-data calibration — ranking AUC is the comparison, and the
    calibration only sets thresholds, not the labels being ranked.
    """
    cal = fit_calibration(papers, target_fpr, ai_z, prior)
    y = [p.gt_fraud for p in papers]
    out = {}
    for name in ("any_fire_count", "max_cofire", "best_figure_llr"):
        out[name] = M.roc_auc(y, [paper_scores(p, cal)[name] for p in papers])
    out["stored_prob"] = M.roc_auc(y, [p.stored_prob for p in papers])
    return out


def _fmt(v):
    return "n/a" if v is None else f"{v:.3f}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--report",
                   default="outputs/heldout_run/benchmark_report.json")
    p.add_argument("--target-fpr", type=float, default=0.10,
                   help="target per-figure copy-move FPR to tune the threshold to")
    p.add_argument("--ai-z", type=float, default=2.0,
                   help="z above the native-image baseline that counts as AI")
    p.add_argument("--prior", type=float, default=0.34,
                   help="paper-level fraud prior (base rate)")
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--json", action="store_true", help="print raw JSON")
    args = p.parse_args(argv)

    out = run(args.report, args.target_fpr, args.ai_z, args.prior,
              args.decision_threshold)
    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    b, r = out["baseline_stored_fusion"], out["recalibrated_loocv"]
    print(f"\n=== Offline recalibration (LOOCV) — {out['n_fraud']} fraud / "
          f"{out['n_clean']} clean ===\n")
    print("Paper-level likelihood ratios (fired-rate fraud vs clean):")
    for d, t in out["likelihood_ratios"].items():
        print(f"  {d:14s} P(fire|fraud)={t['p_fire_fraud']:.2f}  "
              f"P(fire|clean)={t['p_fire_clean']:.2f}  LR={t['likelihood_ratio']}")
    print(f"\n{'metric':22s}{'current (stored)':>18s}{'recalibrated':>16s}")
    print(f"{'ROC-AUC':22s}{_fmt(b['roc_auc']):>18s}{_fmt(r['roc_auc']):>16s}")
    print(f"{'average precision':22s}{_fmt(b['average_precision']):>18s}"
          f"{_fmt(r['average_precision']):>16s}")
    print(f"{'accuracy@thr':22s}{'—':>18s}{_fmt(r['accuracy']):>16s}")
    print(f"{'recall@thr':22s}{'—':>18s}{_fmt(r['recall']):>16s}")
    print(f"{'FPR@thr':22s}{'—':>18s}{_fmt(r['false_positive_rate']):>16s}")
    print(f"\ncopy-move cutoff (full-data): "
          f"{out['copy_move_threshold_median_fold']}  "
          f"| AI native baseline: {out['ai_baseline_full']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

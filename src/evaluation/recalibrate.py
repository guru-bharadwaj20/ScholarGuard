"""Offline recalibration + likelihood-ratio fusion, measured under LOOCV.

This module improves the paper-level decision WITHOUT re-running the pipeline:
every per-figure detector signal it needs (copy-move ``confidence``,
cross-figure counts, the AI detector's ``freq_score`` / ``noise_score`` and,
when a classifier was loaded, its ``classifier_score``) is already stored in
``benchmark_report.json``. It re-derives paper scores under three fixes and
reports honest, out-of-sample metrics:

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
paper, the baseline, the copy-move threshold, the AI cutoff, and the likelihood
ratios are estimated on the OTHER papers only, then applied to the held-out one.
The pooled predictions are therefore out-of-sample, not fit to the papers they
score. Compared against the pipeline's current stored scores as a baseline.

**On the AI fire rule.** Two are implemented: the frequency+noise z-score
(``forensic``) and the pipeline's classifier blend (``blend``, available once a
report carries ``classifier_score``). ``forensic`` is the default *because it
measured better*, which was not the expected result — on the Stage 2e held-out
set it reaches paper-level LR 4.33 and LOOCV AUC 0.705, and no blend cutoff
comes close (best 2.71 / 0.663, swept over target FPRs 0.005–0.50). The reason
is the training data, not the code: the classifier was trained to tell diffusion
output from real micrographs, whereas retracted-fraud figures are manipulated
*photographs*, so ``p_ai`` is near zero on fraud and clean alike and carries
little paper-level signal. Re-run the sweep before trusting ``blend`` on any new
classifier.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass

from src.detectors.ai_generation_detector import (
    CLASSIFIER_WEIGHT,
    FORENSIC_WEIGHT,
)
from src.evaluation import metrics as M

_EPS = 1e-6
DETECTORS = ("copy_move", "cross_figure", "ai_generation")

#: AI fire modes. ``blend`` uses the pipeline's classifier-blended score with a
#: cutoff refit to a target clean-figure FPR; ``forensic`` z-scores the
#: frequency+noise score against a native-image baseline (the only option for
#: reports written before the classifier existed). ``auto`` picks ``blend``
#: whenever the report carries classifier scores.
AI_MODE_AUTO, AI_MODE_BLEND, AI_MODE_FORENSIC = "auto", "blend", "forensic"


@dataclass
class Paper:
    """Per-paper detector signals + ground truth, pulled from the report."""

    paper_id: str
    gt_fraud: bool
    # per-figure signals (flat, one entry per figure the detector ran on)
    cm_conf: list[float]        # copy-move confidence, one per figure
    cf_fire: list[bool]         # cross-figure fired (exact or region reuse)
    ai_forensic: list[float]    # 0.5*(freq+noise) per figure
    ai_blend: list[float]       # the pipeline's blended AI score per figure,
                                # empty when the run had no classifier weights
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
        cm_conf, cf_fire, ai_forensic, ai_blend = [], [], [], []
        figures: list[dict] = []
        for fig in rep["figures"]:
            d = fig["detectors"]
            rec = {"cm_conf": None, "cf_fire": None, "ai_forensic": None,
                   "ai_blend": None}
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
                # Reproduce the pipeline's own blend when the run had a trained
                # classifier. Older reports predate `classifier_score` and have
                # only the forensic pair, which the forensic path still handles.
                p_ai = ai.get("classifier_score")
                if p_ai is not None:
                    rec["ai_blend"] = (CLASSIFIER_WEIGHT * float(p_ai)
                                       + FORENSIC_WEIGHT * rec["ai_forensic"])
                    ai_blend.append(rec["ai_blend"])
            figures.append(rec)
        papers.append(Paper(
            paper_id=pid,
            gt_fraud=bool(entry["ground_truth"]["is_fraudulent"]),
            cm_conf=cm_conf, cf_fire=cf_fire, ai_forensic=ai_forensic,
            ai_blend=ai_blend,
            figures=figures,
            stored_score=float(rep["overall_risk"].get("score", 0.0)),
            stored_prob=float(rep["overall_risk"].get("fraud_probability", 0.0)),
        ))
    return papers


def _ai_figure_fires(fig: dict, cal: "Calibration") -> bool:
    """Does the AI detector fire on one figure under this calibration?

    In ``blend`` mode the classifier-blended score is compared against a cutoff
    refit to a target clean-figure FPR; otherwise the forensic score is z-scored
    against the clean-figure baseline. A figure with no blend score under blend
    mode (mixed-vintage report) falls back to the forensic rule rather than
    silently counting as "did not fire".
    """
    if cal.ai_blend_threshold is not None and fig.get("ai_blend") is not None:
        return fig["ai_blend"] >= cal.ai_blend_threshold
    return (fig["ai_forensic"] is not None
            and (fig["ai_forensic"] - cal.ai_mean) / cal.ai_std >= cal.ai_z)


def _figure_fires(fig: dict, cal: "Calibration") -> dict:
    """Which detectors fire on a SINGLE figure under a calibration."""
    cm = fig["cm_conf"] is not None and fig["cm_conf"] >= cal.cm_threshold
    cf = bool(fig["cf_fire"])
    return {"copy_move": cm, "cross_figure": cf,
            "ai_generation": _ai_figure_fires(fig, cal)}


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
    ai_blend_threshold: float | None = None  # blend cutoff; None => forensic mode


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
    """Which detectors fire on this paper under a given calibration.

    A paper fires if any of its figures does, so this is the per-figure rule
    aggregated — and it goes through ``_figure_fires`` rather than repeating the
    thresholds, so the paper-level and figure-level views cannot disagree (they
    previously could: only this function was updated when the AI rule changed).
    """
    fires = {d: False for d in DETECTORS}
    for fig in paper.figures:
        for d, fired in _figure_fires(fig, cal).items():
            fires[d] = fires[d] or fired
    return fires


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


def _ai_blend_quantile(train: list[Paper], target_fpr: float) -> float:
    """Blend cutoff just above the (1-target_fpr) quantile of clean blend scores.

    Same idea as the copy-move cutoff — put the threshold where ~target_fpr of
    training clean figures exceed it — and this is what lets the classifier be
    refit at all, since its shipped cutoff (``COMBINED_LOW``) was chosen before
    any checkpoint existed and is tied to no measured false-alarm rate.

    It differs in one deliberate way: the cutoff is nudged *strictly above* the
    quantile value rather than set equal to it. Because the rule is ``>=``, a
    cutoff sitting exactly on a clean score fires on that figure and on every
    other clean figure tied with it — and blend scores tie readily, since a
    confident ``p_ai`` of 0.0 collapses the blend onto ``0.4*forensic``. With
    ties present, an equal-to cutoff can overshoot the target FPR by an order of
    magnitude. Strictly-above makes ``target_fpr`` an upper bound: the realized
    rate can undershoot, which is the safe direction for a false-alarm budget.
    """
    clean = sorted(b for p in train if not p.gt_fraud for b in p.ai_blend)
    if not clean:
        return 0.0
    idx = min(len(clean) - 1,
              int(math.ceil((1.0 - target_fpr) * len(clean))) - 1)
    return math.nextafter(clean[max(0, idx)], math.inf)


def fit_calibration(train: list[Paper], target_fpr: float, ai_z: float,
                    prior: float, ai_mode: str = AI_MODE_AUTO,
                    ai_target_fpr: float = 0.02) -> Calibration:
    cm_threshold = _clean_quantile(train, target_fpr)
    ai_mean, ai_std = _ai_baseline(train)
    blend_threshold = None
    if ai_mode != AI_MODE_FORENSIC and any(p.ai_blend for p in train):
        blend_threshold = _ai_blend_quantile(train, ai_target_fpr)
    cal = Calibration(cm_threshold, ai_mean, ai_std, ai_z, {}, prior,
                      ai_blend_threshold=blend_threshold)
    cal.lrs = _fit_lrs(train, cal)
    return cal


def resolve_ai_mode(papers: list[Paper], ai_mode: str) -> str:
    """The AI mode actually usable for these papers, for honest reporting.

    ``blend`` is requested-but-unavailable when the report predates
    ``classifier_score`` (or the run had no weights); saying so beats quietly
    reporting forensic numbers under a blend heading.
    """
    has_blend = any(p.ai_blend for p in papers)
    if ai_mode == AI_MODE_FORENSIC or not has_blend:
        return AI_MODE_FORENSIC
    return AI_MODE_BLEND


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
                      prior: float, ai_mode: str = AI_MODE_AUTO,
                      ai_target_fpr: float = 0.02) -> list[tuple[bool, float]]:
    """(gt_fraud, recalibrated posterior) for each paper, fit on the rest."""
    out = []
    for i, held in enumerate(papers):
        train = [p for j, p in enumerate(papers) if j != i]
        cal = fit_calibration(train, target_fpr, ai_z, prior, ai_mode,
                              ai_target_fpr)
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
        decision_threshold: float, ai_mode: str = AI_MODE_AUTO,
        ai_target_fpr: float = 0.02) -> dict:
    with open(report_path, encoding="utf-8") as fh:
        report = json.load(fh)
    papers = load_papers(report)
    n_fraud = sum(1 for p in papers if p.gt_fraud)
    resolved_mode = resolve_ai_mode(papers, ai_mode)
    n_blend_figures = sum(len(p.ai_blend) for p in papers)
    n_ai_figures = sum(len(p.ai_forensic) for p in papers)

    # Baseline = the pipeline's CURRENT stored fraud_probability (uncalibrated
    # fusion), scored the same way for an apples-to-apples comparison.
    base_pairs = [(p.gt_fraud, p.stored_prob) for p in papers]
    base = {"roc_auc": M.roc_auc([t for t, _ in base_pairs],
                                 [s for _, s in base_pairs]),
            "average_precision": M.average_precision(
                [t for t, _ in base_pairs], [s for _, s in base_pairs])}

    recal_pairs = loocv_predictions(papers, target_fpr, ai_z, prior, ai_mode,
                                    ai_target_fpr)
    recal = _metrics(recal_pairs, decision_threshold)

    # Full-data LR table (display only) to show which detector discriminates.
    full_cal = fit_calibration(papers, target_fpr, ai_z, prior, ai_mode,
                               ai_target_fpr)
    lr_table = {d: {"p_fire_fraud": round(full_cal.lrs[d][0], 3),
                    "p_fire_clean": round(full_cal.lrs[d][1], 3),
                    "likelihood_ratio": round(full_cal.lrs[d][0]
                                              / max(full_cal.lrs[d][1], _EPS), 2)}
                for d in DETECTORS}

    return {
        "n_papers": len(papers), "n_fraud": n_fraud,
        "n_clean": len(papers) - n_fraud,
        "copy_move_threshold_median_fold": round(full_cal.cm_threshold, 3),
        "ai_mode_requested": ai_mode,
        "ai_mode_used": resolved_mode,
        "ai_classifier_coverage": f"{n_blend_figures}/{n_ai_figures} figures",
        "ai_blend_threshold_full": (round(full_cal.ai_blend_threshold, 3)
                                    if full_cal.ai_blend_threshold is not None
                                    else None),
        "ai_blend_weights": {"classifier": CLASSIFIER_WEIGHT,
                             "forensic": FORENSIC_WEIGHT},
        "ai_target_fpr": ai_target_fpr,
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
    p.add_argument("--ai-mode", default=AI_MODE_FORENSIC,
                   choices=[AI_MODE_AUTO, AI_MODE_BLEND, AI_MODE_FORENSIC],
                   help="how the AI detector's fire decision is re-derived: "
                        "'forensic' (default) z-scores frequency+noise, 'blend' "
                        "uses the pipeline's classifier-blended score, 'auto' "
                        "picks blend when the report carries classifier scores. "
                        "The default is forensic because it MEASURED BETTER: on "
                        "the Stage 2e held-out set the forensic rule reaches "
                        "paper-level LR 4.33 and LOOCV AUC 0.705, which no blend "
                        "cutoff matches (best 2.71 / 0.663 swept over target "
                        "FPRs 0.005-0.50)")
    p.add_argument("--ai-target-fpr", type=float, default=0.02,
                   help="target per-figure AI FPR the blend cutoff is fit to "
                        "(blend mode only; the forensic path uses --ai-z)")
    p.add_argument("--json", action="store_true", help="print raw JSON")
    args = p.parse_args(argv)

    out = run(args.report, args.target_fpr, args.ai_z, args.prior,
              args.decision_threshold, args.ai_mode, args.ai_target_fpr)
    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    b, r = out["baseline_stored_fusion"], out["recalibrated_loocv"]
    print(f"\n=== Offline recalibration (LOOCV) — {out['n_fraud']} fraud / "
          f"{out['n_clean']} clean ===\n")
    if out["ai_mode_used"] == AI_MODE_BLEND:
        print(f"AI fire rule: BLEND "
              f"{out['ai_blend_weights']['classifier']:.1f}*p_ai + "
              f"{out['ai_blend_weights']['forensic']:.1f}*forensic "
              f">= {out['ai_blend_threshold_full']} "
              f"(cutoff refit to {out['ai_target_fpr']:.0%} clean-figure FPR; "
              f"classifier scores on {out['ai_classifier_coverage']})")
    else:
        why = ("requested" if out["ai_mode_requested"] == AI_MODE_FORENSIC
               else "no classifier_score in this report")
        print(f"AI fire rule: FORENSIC z >= {out['ai_baseline_full']['z']} "
              f"({why})")
    print("\nPaper-level likelihood ratios (fired-rate fraud vs clean):")
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

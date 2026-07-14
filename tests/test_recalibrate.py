"""Unit tests for the offline LOOCV recalibration/fusion analysis."""

import pytest

from src.evaluation.recalibrate import (
    Calibration,
    fit_calibration,
    load_papers,
    loocv_predictions,
    paper_fires,
    posterior,
)


def _fig(cm_conf, cf_fire, freq, noise):
    return {"detectors": {
        "copy_move": {"status": "ok", "forged": cm_conf >= 0.45, "confidence": cm_conf},
        "cross_figure": {"status": "ok",
                         "n_exact": 1 if cf_fire else 0, "n_region_reuse": 0},
        "ai_generation": {"status": "ok", "verdict": "likely_real",
                          "freq_score": freq, "noise_score": noise},
    }}


def _paper(pid, fraud, figs):
    return {"ground_truth": {"paper_id": pid, "is_fraudulent": fraud},
            "status": "ok",
            "pipeline_report": {
                "overall_risk": {"score": 30.0, "fraud_probability": 0.5},
                "figures": figs}}


def _report():
    # Fraud papers: a clearly-manipulated figure (high conf + high forensic).
    # Clean papers: low, DISTINCT confidences (distinct avoids quantile ties,
    # which would otherwise make the tuned threshold sit on a clean value).
    results = {}
    for i in range(6):
        results[f"F{i}"] = _paper(f"F{i}", True,
                                  [_fig(0.90, True, 0.6, 0.6), _fig(0.10, False, 0.3, 0.3)])
    for i in range(6):
        lo = 0.02 * (i + 1)   # 0.02, 0.04, ... 0.12 — all below the fraud signal
        results[f"C{i}"] = _paper(f"C{i}", False,
                                  [_fig(lo, False, 0.35, 0.35), _fig(0.01, False, 0.3, 0.3)])
    return {"results": results}


def test_load_papers_extracts_signals():
    papers = load_papers(_report())
    assert len(papers) == 12
    fraud = [p for p in papers if p.gt_fraud]
    assert len(fraud) == 6
    # each paper has two figures worth of signals
    assert all(len(p.cm_conf) == 2 for p in papers)
    assert all(len(p.ai_forensic) == 2 for p in papers)


def test_fit_calibration_and_lrs_are_discriminative():
    papers = load_papers(_report())
    cal = fit_calibration(papers, target_fpr=0.10, ai_z=1.0, prior=0.5)
    # copy-move should discriminate on this separable toy data (LR > 1).
    pf, pc = cal.lrs["copy_move"]
    assert pf > pc
    # threshold sits between the clean confidences (<=0.12) and fraud (0.90).
    assert 0.10 <= cal.cm_threshold <= 0.90


def test_posterior_orders_fraud_above_clean():
    papers = load_papers(_report())
    cal = fit_calibration(papers, target_fpr=0.10, ai_z=1.0, prior=0.5)
    fraud = next(p for p in papers if p.gt_fraud)
    clean = next(p for p in papers if not p.gt_fraud)
    assert posterior(fraud, cal) > posterior(clean, cal)


def test_loocv_predictions_shape_and_separation():
    papers = load_papers(_report())
    preds = loocv_predictions(papers, target_fpr=0.10, ai_z=1.0, prior=0.5)
    assert len(preds) == 12
    from src.evaluation.metrics import roc_auc
    auc = roc_auc([t for t, _ in preds], [s for _, s in preds])
    # cleanly separable toy data -> strong AUC out-of-sample.
    assert auc is not None and auc >= 0.8


def test_paper_fires_respects_threshold():
    cal = Calibration(cm_threshold=0.5, ai_mean=0.3, ai_std=0.1, ai_z=2.0,
                      lrs={}, prior=0.5)
    from src.evaluation.recalibrate import Paper
    p = Paper("x", True, cm_conf=[0.4, 0.6], cf_fire=[False, False],
              ai_forensic=[0.3, 0.9], figures=[], stored_score=0, stored_prob=0)
    fires = paper_fires(p, cal)
    assert fires["copy_move"] is True      # 0.6 >= 0.5
    assert fires["cross_figure"] is False
    assert fires["ai_generation"] is True  # (0.9-0.3)/0.1 = 6 >= 2

"""Unit tests for the Stage 6 risk scorer.

Given hand-constructed detector outputs, verify the combined per-figure and
per-paper scores and categories match the documented weighting logic.
"""

import pytest

from src.config.settings import load_settings
from src.pipeline.risk_scorer import score_figure, score_paper


@pytest.fixture(scope="module")
def settings():
    return load_settings()


def _clean_detectors():
    return {
        "copy_move": {"status": "ok", "forged": False, "confidence": 0.1},
        "cross_figure": {"status": "ok", "n_exact": 0, "n_region_reuse": 0,
                         "n_visual_similar": 1},
        "ai_generation": {"status": "ok", "verdict": "likely_real",
                          "classifier_used": False},
        "claim_consistency": {"status": "ok", "consistent": True,
                              "mismatches": [], "confidence": 0.0},
    }


# ---------------------------------------------------------------- figures
def test_clean_figure_scores_zero(settings):
    result = score_figure(_clean_detectors(), settings)
    assert result["score"] == 0.0
    assert result["category"] == "low"
    # Every detector is represented in the breakdown, even at 0 points.
    assert {b["detector"] for b in result["breakdown"]} == {
        "copy_move", "cross_figure", "ai_generation", "claim_consistency"}


def test_strong_copy_move_dominates(settings):
    det = _clean_detectors()
    det["copy_move"] = {"status": "ok", "forged": True, "confidence": 0.9}
    result = score_figure(det, settings)
    # copy_move weight is 35; 0.9 * 35 = 31.5 -> "moderate" (>= 25).
    assert result["score"] == pytest.approx(31.5, abs=0.5)
    assert result["category"] == "moderate"


def test_all_signals_high_is_critical(settings):
    det = {
        "copy_move": {"status": "ok", "forged": True, "confidence": 1.0},
        "cross_figure": {"status": "ok", "n_exact": 1, "n_region_reuse": 0,
                         "n_visual_similar": 0},
        "ai_generation": {"status": "ok", "verdict": "likely_ai_generated",
                          "classifier_used": True},
        "claim_consistency": {"status": "ok", "consistent": False,
                              "mismatches": ["count mismatch"], "confidence": 1.0},
    }
    result = score_figure(det, settings)
    # 35 + 30 + 20 + 15 = 100 -> critical.
    assert result["score"] == pytest.approx(100.0, abs=0.1)
    assert result["category"] == "critical"


def test_skipped_detector_contributes_zero_but_is_recorded(settings):
    det = _clean_detectors()
    det["claim_consistency"] = {"status": "skipped", "reason": "no API key"}
    result = score_figure(det, settings)
    entry = next(b for b in result["breakdown"]
                if b["detector"] == "claim_consistency")
    assert entry["status"] == "skipped"
    assert entry["points"] == 0.0


def test_region_reuse_scores_below_exact(settings):
    exact = _clean_detectors()
    exact["cross_figure"] = {"status": "ok", "n_exact": 1, "n_region_reuse": 0,
                             "n_visual_similar": 0}
    region = _clean_detectors()
    region["cross_figure"] = {"status": "ok", "n_exact": 0, "n_region_reuse": 1,
                              "n_visual_similar": 0}
    assert score_figure(exact, settings)["score"] > \
        score_figure(region, settings)["score"]


# ---------------------------------------------------------------- paper
def test_paper_worst_figure_dominates(settings):
    """One critical figure among clean ones must not be averaged away."""
    critical = score_figure({
        "copy_move": {"status": "ok", "forged": True, "confidence": 1.0},
        "cross_figure": {"status": "ok", "n_exact": 1, "n_region_reuse": 0,
                         "n_visual_similar": 0},
        "ai_generation": {"status": "ok", "verdict": "likely_ai_generated",
                          "classifier_used": True},
        "claim_consistency": {"status": "ok", "consistent": False,
                              "mismatches": ["x"], "confidence": 1.0},
    }, settings)
    clean = score_figure(_clean_detectors(), settings)

    paper = score_paper([critical] + [clean] * 5, settings)
    # 6 figures, one at 100 and five at 0: a plain mean would be ~17 (low);
    # the worst-figure weighting must keep the paper at least "high".
    assert paper["category"] in ("high", "critical")
    assert paper["worst_figure_category"] == "critical"


def test_paper_all_clean_is_low(settings):
    clean = score_figure(_clean_detectors(), settings)
    paper = score_paper([clean, clean, clean], settings)
    assert paper["category"] == "low"
    assert paper["score"] == 0.0


def test_paper_no_figures(settings):
    paper = score_paper([], settings)
    assert paper["n_figures"] == 0
    assert paper["category"] == "low"

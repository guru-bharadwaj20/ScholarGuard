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
        "splice": {"status": "ok", "spliced": False, "confidence": 0.0},
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
        "copy_move", "cross_figure", "splice", "ai_generation",
        "claim_consistency"}


def test_strong_copy_move_alone_is_bounded(settings):
    det = _clean_detectors()
    det["copy_move"] = {"status": "ok", "forged": True, "confidence": 1.0}
    result = score_figure(det, settings)
    # copy_move weight is now 25 (reduced: LR 1.19); a lone max copy-move hit
    # scores 25 -> exactly the "moderate" screening line, no higher.
    assert result["score"] == pytest.approx(25.0, abs=0.5)
    assert result["category"] == "moderate"
    assert result["n_corroborating_signals"] == 1


def test_all_signals_high_is_critical(settings):
    det = {
        "copy_move": {"status": "ok", "forged": True, "confidence": 1.0},
        "cross_figure": {"status": "ok", "n_exact": 1, "n_region_reuse": 0,
                         "n_visual_similar": 0},
        "splice": {"status": "ok", "spliced": True, "confidence": 1.0},
        "ai_generation": {"status": "ok", "verdict": "likely_ai_generated",
                          "classifier_used": True},
        "claim_consistency": {"status": "ok", "consistent": False,
                              "mismatches": ["count mismatch"], "confidence": 1.0},
    }
    result = score_figure(det, settings)
    # 25 + 25 + 20 + 20 + 10 = 100 -> critical.
    assert result["score"] == pytest.approx(100.0, abs=0.1)
    assert result["category"] == "critical"
    assert result["n_corroborating_signals"] == 5


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


# --------------------------------------------------------- corroboration (#6)
def test_two_corroborating_detectors_floor_paper_to_high(settings):
    """A figure that two independent detectors flag lifts the paper to >= high."""
    two_signal = score_figure({
        "copy_move": {"status": "ok", "forged": True, "confidence": 0.5},
        "cross_figure": {"status": "ok", "n_exact": 1, "n_region_reuse": 0,
                         "n_visual_similar": 0},
        "ai_generation": {"status": "ok", "verdict": "likely_real",
                          "classifier_used": False},
        "claim_consistency": {"status": "ok", "consistent": True,
                              "mismatches": [], "confidence": 0.0},
    }, settings)
    assert two_signal["n_corroborating_signals"] == 2
    paper = score_paper([two_signal] + [score_figure(_clean_detectors(), settings)] * 4,
                        settings)
    assert paper["max_corroboration"] == 2
    assert paper["category"] in ("high", "critical")


def test_single_detector_does_not_get_corroboration_floor(settings):
    """A lone single-detector fire must NOT be lifted by corroboration."""
    one_signal = score_figure({
        "copy_move": {"status": "ok", "forged": True, "confidence": 0.5},
        "cross_figure": {"status": "ok", "n_exact": 0, "n_region_reuse": 0,
                         "n_visual_similar": 0},
        "ai_generation": {"status": "ok", "verdict": "likely_real",
                          "classifier_used": False},
        "claim_consistency": {"status": "ok", "consistent": True,
                              "mismatches": [], "confidence": 0.0},
    }, settings)
    assert one_signal["n_corroborating_signals"] == 1
    paper = score_paper([one_signal], settings)
    assert paper["max_corroboration"] == 1
    # only the point-score category applies (no corroboration bump to high)
    assert paper["category"] in ("low", "moderate")


def test_empty_paper_returns_the_same_keys_as_a_scored_one():
    """A figureless paper must not return a shorter dict.

    One clean control in held-out set 3 has zero extractable figures. Because
    the empty branch omitted fraud_probability, a consumer reading that field
    across the whole run hit None on that single paper and dropped the noisy-OR
    ranking for all 73 -- the baseline silently vanished from the report.
    """
    from src.config.settings import Settings
    from src.pipeline.risk_scorer import score_paper
    settings = Settings()
    empty = score_paper([], settings)
    scored = score_paper([{"score": 10.0, "fraud_probability": 0.2,
                           "n_corroborating_signals": 1}], settings)
    assert set(scored) - {"note"} <= set(empty)
    assert empty["fraud_probability"] == 0.0
    assert empty["max_corroboration"] == 0

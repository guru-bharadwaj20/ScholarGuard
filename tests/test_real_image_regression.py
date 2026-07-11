"""Regression tests against REAL scientific figures.

These lock in the 2026-07-11 fixes that the synthetic-only suite failed to
catch, using the real committed figures in ``data/clean/`` (86 PMC Open-Access
figures) rather than generated ones:

  * the copy-move confidence must stay in [0, 1] on real figures — a flat-pixel
    ZNCC blow-up used to drive it past 13 (see copy_move_detector._score);
  * a real figure with an *injected* copy-move must still be detected, so the
    redesign did not throw away true-positive sensitivity;
  * the recalibrated AI-generation forensic bands must not fire on the bulk of
    real clean figures (the old synthetic-tuned bands fired on ~half of them).

The synthetic tests in test_copy_move_detector.py / test_ai_generation_detector.py
stay as-is; these complement them with real data. If ``data/clean`` is absent
the real-image tests skip rather than fail.
"""

from __future__ import annotations

import glob
import os

import cv2
import numpy as np
import pytest

from src.detectors.copy_move_detector import (
    CopyMoveDetector,
    _bbox_area_frac,
    _chance_cell_matches,
    _logistic,
)
from src.detectors.ai_generation_detector import detect_ai_generation
from src.utils.synth import apply_copy_move

CLEAN_DIR = "data/clean"


def _clean_figures(limit: int) -> list[str]:
    """A small, deterministic sample of the real clean figures."""
    files = sorted(glob.glob(os.path.join(CLEAN_DIR, "*.jpg"))
                   + glob.glob(os.path.join(CLEAN_DIR, "*.png")))
    if not files:
        return []
    # Even stride across the corpus so the sample isn't all from one paper.
    step = max(1, len(files) // limit)
    return files[::step][:limit]


# ======================================================================
# Unit tests for the new confidence-model helpers (fast, no image I/O).
# ======================================================================
def test_logistic_is_bounded_and_monotonic():
    # Bounded in (0, 1) even for extreme inputs (no overflow either way).
    for x in (-1e6, -50, -1, 0, 1, 50, 1e6):
        assert 0.0 <= _logistic(x) <= 1.0
    assert _logistic(0.0) == pytest.approx(0.5)
    # Strictly increasing.
    xs = [-10, -2, 0, 2, 10]
    ys = [_logistic(x) for x in xs]
    assert all(b > a for a, b in zip(ys, ys[1:]))


def test_chance_cell_matches_scales_sensibly():
    # No matches -> no chance mass.
    assert _chance_cell_matches(0, 500, 500, 24.0) == 0.0
    # More matches -> proportionally higher expected count per cell.
    lo = _chance_cell_matches(100, 500, 500, 24.0)
    hi = _chance_cell_matches(1000, 500, 500, 24.0)
    assert hi > lo > 0.0
    assert hi == pytest.approx(10 * lo, rel=1e-6)
    # A bigger image spreads the same matches thinner (smaller chance/cell).
    big = _chance_cell_matches(1000, 1000, 1000, 24.0)
    assert big < hi


def test_bbox_area_frac_matches_hand_computation():
    h, w = 100, 200
    pts = np.array([[10.0, 20.0], [60.0, 70.0]])  # 50 wide x 50 tall
    assert _bbox_area_frac(pts, h, w) == pytest.approx((50 * 50) / (h * w))
    # Degenerate inputs are a compact (zero-area) region, not an error.
    assert _bbox_area_frac(np.array([[1.0, 1.0]]), h, w) == 0.0
    assert _bbox_area_frac(None, h, w) == 0.0


# ======================================================================
# Deterministic bug-mechanism lock: flat regions must not inflate score.
# ======================================================================
def test_flat_background_cannot_inflate_confidence():
    """A duplicated patch sitting on a large flat background.

    Flat pixels are exactly where the local ZNCC divides by ~0 and used to
    explode into the thousands, dragging the mean correlation (and thus the
    old confidence) far above 1. The fix masks the mean by std_ok. Whatever
    the verdict, the confidence must remain a real number in [0, 1].
    """
    rng = np.random.default_rng(3)
    img = np.full((480, 640, 3), 235, np.uint8)  # mostly flat "paper"
    patch = rng.integers(0, 255, (60, 80, 3), dtype=np.uint8)  # textured content
    img[60:120, 80:160] = patch
    img[300:360, 400:480] = patch  # exact duplicate elsewhere
    result = CopyMoveDetector().detect(img)
    assert 0.0 <= result["confidence"] <= 1.0


# ======================================================================
# Real-image regression tests.
# ======================================================================
@pytest.mark.skipif(not _clean_figures(1), reason="data/clean figures not present")
def test_confidence_bounded_on_real_figures():
    """THE core regression: confidence in [0, 1] on real published figures."""
    detector = CopyMoveDetector()
    checked = 0
    for path in _clean_figures(6):
        img = cv2.imread(path)
        if img is None:
            continue
        conf = detector.detect(img)["confidence"]
        assert 0.0 <= conf <= 1.0, f"confidence {conf} out of range on {path}"
        checked += 1
    assert checked >= 1


@pytest.mark.skipif(not _clean_figures(1), reason="data/clean figures not present")
def test_injected_copy_move_on_real_figure_is_detected():
    """Redesign keeps true-positive sensitivity on *real* image content.

    Take a real clean figure, stamp a copied patch into it, and require the
    forged version to (a) score strictly higher than the untouched figure and
    (b) cross the decision threshold. This is what a synthetic-only suite could
    not exercise: a genuine forgery on genuine scientific texture.
    """
    detector = CopyMoveDetector()
    rng = np.random.default_rng(2026)
    tried = 0
    for path in _clean_figures(6):
        img = cv2.imread(path)
        if img is None:
            continue
        base_conf = detector.detect(img)["confidence"]
        forged, _ = apply_copy_move(img, rng, patch_size=(90, 120))
        forged_res = detector.detect(forged)
        tried += 1
        # The injected copy is a large, localized, near-exact duplicate: it must
        # register as more suspicious than the original and clear the threshold.
        if forged_res["forged"] and forged_res["confidence"] > base_conf:
            return
    pytest.fail(f"injected copy-move not detected on any of {tried} real figures")


@pytest.mark.skipif(not _clean_figures(1), reason="data/clean figures not present")
def test_ai_generation_recalibration_low_fpr_on_real_clean_figures():
    """Recalibrated forensic bands must not flag most real clean figures.

    The old synthetic-tuned bands (0.35/0.55) fired on ~52% of real clean
    figures; the real-baseline bands (~mean+2sd / +3sd) should fire on very few.
    We allow a small margin — this is a regression floor, not the headline
    metric (which is measured, with its overfitting caveat, in Stage 7).
    """
    sample = _clean_figures(8)
    fired = 0
    checked = 0
    for path in sample:
        verdict = detect_ai_generation(path)["combined_verdict"]
        checked += 1
        if verdict != "likely_real":
            fired += 1
    assert checked >= 1
    # Comfortably below the old 0.5+ FPR; flag the regression if it creeps back.
    assert fired <= max(1, checked // 4), (
        f"AI-generation fired on {fired}/{checked} real clean figures — "
        "recalibration may have regressed")

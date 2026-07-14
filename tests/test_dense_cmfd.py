"""Unit tests for the dense-field copy-move tier (smooth-region duplication)."""

import cv2
import numpy as np
import pytest

from src.detectors.copy_move_detector import CopyMoveDetector, DetectorConfig
from src.detectors.dense_cmfd import DenseCMFDConfig, detect_dense_copy_move


@pytest.fixture
def smooth_blot(scope="module"):
    """A smooth blot-like image (few SIFT keypoints) + a copy-moved variant."""
    rng = np.random.default_rng(3)
    img = np.full((400, 500), 210, np.float32)
    for _ in range(6):
        cx, cy = rng.integers(60, 440), rng.integers(60, 340)
        ax, ay = rng.integers(30, 55), rng.integers(12, 22)
        cv2.ellipse(img, (int(cx), int(cy)), (int(ax), int(ay)), 0, 0, 360,
                    float(rng.uniform(70, 130)), -1)
    img = cv2.GaussianBlur(img, (0, 0), 3) + rng.normal(0, 3, (400, 500)).astype(np.float32)
    clean = np.clip(img, 0, 255).astype(np.uint8)
    forged = clean.copy()
    # offset (240, 140) — NOT a multiple of the block step, so this exercises
    # the small-stride dense matching (a coarse grid would miss it).
    forged[220:320, 300:420] = clean[80:180, 60:180].copy()
    return clean, forged


def test_dense_detects_smooth_copy_move(smooth_blot):
    _, forged = smooth_blot
    r = detect_dense_copy_move(forged)
    assert r["forged"] is True
    assert r["n_support"] >= DenseCMFDConfig().min_support
    # recovered shift is close to the true (240, 140)
    dx, dy = r["offset"]
    assert abs(abs(dx) - 240) <= 8 and abs(abs(dy) - 140) <= 8


def test_dense_quiet_on_clean(smooth_blot):
    clean, _ = smooth_blot
    r = detect_dense_copy_move(clean)
    assert r["forged"] is False


def test_dense_quiet_on_flat():
    flat = np.full((300, 300), 200, np.uint8)
    r = detect_dense_copy_move(flat)
    assert r["forged"] is False
    assert r["n_support"] == 0


def test_copy_move_escalates_to_dense(smooth_blot):
    """The SIFT detector should escalate and flag the smooth copy-move via dense."""
    _, forged = smooth_blot
    bgr = cv2.cvtColor(forged, cv2.COLOR_GRAY2BGR)
    det = CopyMoveDetector(DetectorConfig(use_dense_tier=True))
    r = det.detect(bgr)
    assert r["forged"] is True
    assert r["dense_tier_used"] is True


def test_dense_tier_can_be_disabled(smooth_blot):
    _, forged = smooth_blot
    bgr = cv2.cvtColor(forged, cv2.COLOR_GRAY2BGR)
    det = CopyMoveDetector(DetectorConfig(use_dense_tier=False))
    r = det.detect(bgr)
    assert r["dense_tier_used"] is False


# ---------------------------------------------------------------------------
# False-positive gates: independent-noise look-alikes and periodic texture.
# These are exactly the "repetitive/self-similar texture" cases that doubled
# copy-move's FPR when the dense tier was added.
# ---------------------------------------------------------------------------
@pytest.fixture
def independent_lookalike():
    """The SAME smooth content at two spots, but with INDEPENDENT noise.

    Its low-frequency DCT matches (so the block matcher fires), but the two
    regions do not share a capture's noise field — an honest look-alike, not
    a pixel clone. The residual gate must suppress it.
    """
    rng = np.random.default_rng(11)
    img = np.full((400, 500), 205, np.float32)
    blob = np.zeros((100, 120), np.float32)
    cv2.ellipse(blob, (60, 50), (45, 30), 0, 0, 360, -90.0, -1)
    blob = cv2.GaussianBlur(blob, (0, 0), 4)
    img[80:180, 60:180] += blob + rng.normal(0, 5, blob.shape).astype(np.float32)
    img[220:320, 300:420] += blob + rng.normal(0, 5, blob.shape).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def test_residual_gate_suppresses_independent_lookalike(independent_lookalike):
    """Content matches, but independent noise -> the residual gate vetoes it."""
    # With the noise gate OFF (and the self-similarity veto relaxed) the smooth
    # look-alike fires purely on matching content...
    ungated = detect_dense_copy_move(
        independent_lookalike,
        DenseCMFDConfig(require_residual_confirm=False, max_secondary_ratio=2.0))
    assert ungated["forged"] is True
    # ...with the gate ON (default) the independent noise field vetoes it.
    gated = detect_dense_copy_move(independent_lookalike)
    assert gated["forged"] is False


def test_selfsimilarity_veto_suppresses_periodic_texture():
    """Periodic stripes give many equal-strength offsets -> not a copy-move."""
    rng = np.random.default_rng(5)
    img = np.full((400, 480), 60, np.float32)
    for x in range(0, 480, 40):                 # vertical stripes, period 40
        img[:, x:x + 20] = 190
    img = cv2.GaussianBlur(img, (0, 0), 2) + rng.normal(0, 4, (400, 480)).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    # Isolate the self-similarity veto (disable the residual gate).
    r = detect_dense_copy_move(img, DenseCMFDConfig(require_residual_confirm=False))
    assert r["forged"] is False


def test_inconclusive_dense_hit_is_lead_only(monkeypatch):
    """An unconfirmed (INCONCLUSIVE residual) dense hit is a LEAD, not a score.

    A heavily-compressed/flat clone still block-matches (low-freq DCT survives)
    but its high-frequency noise residual is gone, so the clone test returns
    INCONCLUSIVE. Such a hit must be surfaced for review yet leave the fraud
    score untouched. We inject the dense result so the branch is exercised
    deterministically (a real INCONCLUSIVE image is compression-dependent).
    """
    import src.detectors.dense_cmfd as dense_mod

    gray = np.full((300, 400), 200, np.uint8)
    mask = np.zeros((300, 400), np.uint8)
    mask[40:120, 250:360] = 255
    fake = {
        "forged": True, "confidence": 0.8, "mask": mask, "n_support": 150,
        "offset": (200, 0), "mean_zncc": 0.9, "residual_verdict": "inconclusive",
    }
    monkeypatch.setattr(dense_mod, "detect_dense_copy_move", lambda *a, **k: fake)

    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)   # flat -> SIFT finds nothing
    det = CopyMoveDetector(DetectorConfig(use_dense_tier=True))
    r = det.detect(bgr)
    assert r["dense_tier_used"] is True
    assert r["forged"] is False                       # lead only: not scored
    assert r["confidence"] < 0.45
    assert any(reg.get("lead_only") for reg in r["regions"])


def test_confirmed_dense_hit_drives_score(monkeypatch):
    """A CLONE-confirmed dense hit DOES flag the figure (the recall we keep)."""
    import src.detectors.dense_cmfd as dense_mod

    gray = np.full((300, 400), 200, np.uint8)
    mask = np.zeros((300, 400), np.uint8)
    mask[40:120, 250:360] = 255
    fake = {
        "forged": True, "confidence": 0.8, "mask": mask, "n_support": 150,
        "offset": (200, 0), "mean_zncc": 0.9, "residual_verdict": "clone",
    }
    monkeypatch.setattr(dense_mod, "detect_dense_copy_move", lambda *a, **k: fake)

    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    det = CopyMoveDetector(DetectorConfig(use_dense_tier=True))
    r = det.detect(bgr)
    assert r["dense_tier_used"] is True
    assert r["forged"] is True
    assert r["confidence"] >= 0.45
    assert not any(reg.get("lead_only") for reg in r["regions"])

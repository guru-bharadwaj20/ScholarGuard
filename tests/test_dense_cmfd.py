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

"""Unit tests for splice / foreign-region detection.

A splice is synthesised with a *different* compression + noise history than
its host (the real-world tell), and the detector must fire on it while staying
quiet on the authentic control and on flat content.
"""

import cv2
import numpy as np
import pytest

from src.forensics.splice_detection import SpliceConfig, detect_splice


def _textured(rng, h=512, w=512, mean=140, sigma=30):
    base = cv2.GaussianBlur(rng.normal(mean, sigma, (h, w)).astype(np.float32),
                            (0, 0), 3)
    return np.clip(base + rng.normal(0, 6, (h, w)), 0, 255).astype(np.uint8)


def _jpeg(gray, q):
    return cv2.imdecode(cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, q])[1],
                        cv2.IMREAD_GRAYSCALE)


@pytest.fixture
def spliced_and_authentic():
    rng = np.random.default_rng(0)
    host = _textured(rng)
    patch = _jpeg(_textured(rng, 160, 160, mean=120, sigma=35), 35)  # foreign history
    spliced = host.copy()
    spliced[170:330, 170:330] = patch
    authentic = _jpeg(host, 90)  # single uniform recompression
    return spliced, authentic


def test_detects_synthetic_splice(spliced_and_authentic):
    spliced, _ = spliced_and_authentic
    r = detect_splice(cv2.cvtColor(spliced, cv2.COLOR_GRAY2BGR))
    assert r["spliced"] is True
    assert r["n_flagged_blocks"] >= SpliceConfig().min_flagged_blocks
    assert r["mask"].shape == spliced.shape


def test_authentic_not_flagged(spliced_and_authentic):
    _, authentic = spliced_and_authentic
    r = detect_splice(cv2.cvtColor(authentic, cv2.COLOR_GRAY2BGR))
    assert r["spliced"] is False


def test_flat_image_is_quiet():
    flat = np.full((256, 256, 3), 200, np.uint8)
    r = detect_splice(flat)
    assert r["spliced"] is False
    assert r["n_flagged_blocks"] == 0


def test_analysis_mask_restricts_search(spliced_and_authentic):
    spliced, _ = spliced_and_authentic
    # Mask out the spliced region -> nothing to find there.
    mask = np.full(spliced.shape, 255, np.uint8)
    mask[150:350, 150:350] = 0
    r = detect_splice(cv2.cvtColor(spliced, cv2.COLOR_GRAY2BGR), analysis_mask=mask)
    assert r["spliced"] is False


def test_result_shape_and_keys():
    rng = np.random.default_rng(1)
    r = detect_splice(cv2.cvtColor(_textured(rng), cv2.COLOR_GRAY2BGR))
    assert set(r) >= {"spliced", "confidence", "n_flagged_blocks",
                      "flagged_fraction", "mask", "cues"}
    assert 0.0 <= r["confidence"] <= 1.0

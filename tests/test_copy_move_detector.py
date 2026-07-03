"""Unit tests for the Stage 2 copy-move detector.

The tests generate deterministic synthetic forgeries on the fly (seeded
RNG) so they are self-contained and do not depend on Stage 1 data being
present in data/synthetic/.
"""

import numpy as np
import pytest

from src.detectors.copy_move_detector import CopyMoveDetector, detect_copy_move
from src.evaluation.metrics import compute_iou, compute_pixel_metrics
from src.utils.image_io import save_image
from src.utils.synth import apply_copy_move, make_base_figure


@pytest.fixture(scope="module")
def detector():
    return CopyMoveDetector()


@pytest.fixture(scope="module")
def forged_sample():
    """A deterministic forged figure with its ground-truth mask."""
    rng = np.random.default_rng(7)
    base = make_base_figure(rng)
    forged, gt_mask = apply_copy_move(base, rng, patch_size=(80, 100))
    return forged, gt_mask


@pytest.fixture(scope="module")
def clean_sample():
    """A deterministic clean (unforged) figure."""
    return make_base_figure(np.random.default_rng(11))


# ---------------------------------------------------------------- test 1
def test_forged_image_is_flagged(detector, forged_sample):
    forged, _ = forged_sample
    result = detector.detect(forged)
    assert result["forged"] is True
    assert result["confidence"] >= 0.45
    assert len(result["regions"]) >= 1
    # Every region must report both bounding boxes and a 2x3 transform.
    for region in result["regions"]:
        assert len(region["source_bbox"]) == 4
        assert len(region["dup_bbox"]) == 4
        assert np.array(region["transform"]).shape == (2, 3)


# ---------------------------------------------------------------- test 2
def test_clean_image_is_not_flagged(detector, clean_sample):
    result = detector.detect(clean_sample)
    # A clean image must either not be flagged or sit below the decision
    # threshold — both indicate "no forgery found".
    assert result["forged"] is False
    assert result["confidence"] < 0.45
    assert result["mask"].shape == clean_sample.shape[:2]


# ---------------------------------------------------------------- test 3
def test_predicted_mask_iou_against_ground_truth(detector, forged_sample):
    forged, gt_mask = forged_sample
    result = detector.detect(forged)
    iou = compute_iou(result["mask"], gt_mask)
    assert iou > 0.3, f"mask IoU too low: {iou:.3f}"


# ------------------------------------------------------------ extra tests
def test_detect_copy_move_file_api(tmp_path, forged_sample):
    """The public path-based API returns the documented dict structure."""
    forged, _ = forged_sample
    path = str(tmp_path / "forged.png")
    save_image(forged, path)

    result = detect_copy_move(path)
    assert set(result) >= {"forged", "confidence", "mask", "regions", "visualization"}
    assert isinstance(result["forged"], bool)
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["mask"].shape == forged.shape[:2]
    assert result["mask"].dtype == np.uint8
    assert result["visualization"].shape == forged.shape


def test_metrics_math():
    """Sanity-check the pixel metrics on hand-built masks."""
    gt = np.zeros((10, 10), np.uint8)
    gt[0:4, 0:10] = 255          # 40 positive pixels
    pred = np.zeros((10, 10), np.uint8)
    pred[2:6, 0:10] = 255        # 40 predicted, 20 overlap

    metrics = compute_pixel_metrics(pred, gt)
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.5)
    assert metrics["f1"] == pytest.approx(0.5)
    assert metrics["iou"] == pytest.approx(20 / 60)

    # Both empty => perfect agreement.
    empty = np.zeros((10, 10), np.uint8)
    assert compute_iou(empty, empty) == 1.0

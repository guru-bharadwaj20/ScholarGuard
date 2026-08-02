"""Unit tests for the accuracy-improvement modules added on top of the
original pipeline: panel segmentation / content gating, the noise-residual
clone test, JPEG-blockiness estimation, likelihood-ratio evidence fusion,
and the new threshold-free / LOOCV evaluation metrics.
"""

import os

import numpy as np
import pytest

from src.forensics.jpeg_quality import (
    HIGH_COMPRESSION,
    LOW_COMPRESSION,
    compression_stratum,
    estimate_blockiness,
)
from src.forensics.residual_similarity import (
    CLONE,
    INCONCLUSIVE,
    INDEPENDENT,
    clone_factor,
    residual_clone_test,
)
from src.pipeline.evidence_fusion import (
    DEFAULT_CALIBRATION,
    FusionConfig,
    detector_llr,
    fuse_figure,
    fuse_paper,
)
from src.preprocessing.panel_segmentation import (
    BLANK,
    CONTINUOUS_TONE,
    GRAPHICS,
    build_analysis_mask,
    classify_region,
    content_entropy,
    segment_panels,
    text_mask,
)


# --------------------------------------------------------------- panel seg
def _noisy_photo(rng, h=200, w=200):
    """A continuous-tone patch: broadband texture, many gray levels."""
    base = rng.normal(128, 40, (h, w))
    base = np.clip(base, 0, 255).astype(np.uint8)
    return base


def _line_plot(h=200, w=200):
    """A vector-graphics patch: white background + a few thin dark strokes."""
    img = np.full((h, w), 255, np.uint8)
    img[:, 40] = 0            # y axis
    img[h - 30, :] = 0        # x axis
    for x in range(40, w, 5):  # a diagonal data line
        y = h - 30 - (x - 40)
        if 0 <= y < h:
            img[y, x] = 0
    return img


def test_classify_continuous_tone_vs_graphics():
    rng = np.random.default_rng(0)
    kind_photo, _ = classify_region(_noisy_photo(rng))
    kind_plot, _ = classify_region(_line_plot())
    assert kind_photo == CONTINUOUS_TONE
    assert kind_plot in (GRAPHICS,)  # never continuous_tone


def test_classify_blank_region():
    flat = np.full((100, 100), 200, np.uint8)
    kind, _ = classify_region(flat)
    assert kind == BLANK


def test_segment_panels_splits_on_gutter():
    # Two noisy panels separated by a wide white gutter column.
    rng = np.random.default_rng(1)
    left = _noisy_photo(rng, 200, 90)
    right = _noisy_photo(rng, 200, 90)
    gutter = np.full((200, 40), 255, np.uint8)
    fig = np.hstack([left, gutter, right])
    panels = segment_panels(fig)
    assert len(panels) >= 2


def test_analysis_mask_keeps_photo_drops_plot():
    rng = np.random.default_rng(2)
    photo = _noisy_photo(rng, 200, 200)
    mask_photo, _ = build_analysis_mask(photo)
    mask_plot, _ = build_analysis_mask(_line_plot())
    assert mask_photo.mean() > 200          # mostly analyzed
    assert mask_plot.mean() < mask_photo.mean()  # graphics gated out


def test_text_mask_ignores_solid_band():
    """A solid dark band (blot) must NOT be masked as text."""
    img = np.full((200, 200), 235, np.uint8)
    import cv2
    cv2.ellipse(img, (100, 100), (60, 14), 0, 0, 360, 40, -1)
    tm = text_mask(img)
    # Very little of the band's area should be flagged as text.
    assert tm.mean() < 5


def test_content_entropy_ordering():
    rng = np.random.default_rng(3)
    photo = _noisy_photo(rng)
    logo = np.full((100, 100), 255, np.uint8)
    logo[40:60, 40:60] = 0
    assert content_entropy(photo) > content_entropy(logo)


# --------------------------------------------------------- residual clone
def test_residual_clone_detects_identical_noise():
    """Two regions sharing one noise field read as CLONE; independent as INDEPENDENT."""
    import cv2
    rng = np.random.default_rng(4)
    # SMOOTH content (low-freq) so it does not leak into the high-freq
    # residual; the residual is then dominated by the sensor noise, which is
    # exactly what the clone test keys on.
    content = cv2.GaussianBlur(rng.normal(120, 40, (120, 120)).astype(np.float32),
                               (0, 0), 6.0)
    noise = rng.normal(0, 4, (120, 120)).astype(np.float32)
    ref = np.clip(content + noise, 0, 255)
    clone = ref.copy()                                   # carries the SAME noise
    independent = np.clip(content + rng.normal(0, 4, (120, 120)), 0, 255)
    mask = np.ones((120, 120), np.uint8) * 255

    assert residual_clone_test(ref, clone, mask)["verdict"] == CLONE
    assert residual_clone_test(ref, independent, mask)["verdict"] in (
        INDEPENDENT, INCONCLUSIVE)


def test_residual_flat_region_is_inconclusive():
    flat = np.full((120, 120), 128, np.float32)
    mask = np.ones((120, 120), np.uint8) * 255
    res = residual_clone_test(flat, flat.copy(), mask)
    assert res["verdict"] == INCONCLUSIVE
    assert res["conclusive"] is False


def test_clone_factor_ordering():
    assert clone_factor({"verdict": CLONE}) == 1.0
    assert clone_factor({"verdict": INDEPENDENT}) < clone_factor({"verdict": INCONCLUSIVE})
    assert 0.0 < clone_factor({"verdict": INDEPENDENT}) <= 1.0


# --------------------------------------------------------- jpeg blockiness
def test_blockiness_higher_for_jpeg():
    rng = np.random.default_rng(5)
    img = rng.normal(128, 30, (256, 256)).astype(np.uint8)
    import cv2
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 12])
    jpeg = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
    assert estimate_blockiness(jpeg) > estimate_blockiness(img)


def test_compression_stratum_labels():
    rng = np.random.default_rng(6)
    img = rng.normal(128, 30, (256, 256)).astype(np.uint8)
    stratum, _ = compression_stratum(img)
    assert stratum in (LOW_COMPRESSION, HIGH_COMPRESSION)


# ------------------------------------------------------------ fusion (LLR)
def test_uninformative_detector_contributes_zero_llr():
    """A detector with equal fire rates on fraud/clean adds ~0 log-LR."""
    cfg = FusionConfig(calibration={"copy_move":
                                    {"p_fire_fraud": 0.4, "p_fire_clean": 0.4}})
    assert detector_llr("copy_move", True, cfg) == pytest.approx(0.0, abs=1e-9)
    assert detector_llr("copy_move", False, cfg) == pytest.approx(0.0, abs=1e-9)


def test_informative_detector_moves_odds():
    cfg = FusionConfig()  # defaults: all detectors fire more on fraud
    fired = detector_llr("ai_generation", True, cfg)
    not_fired = detector_llr("ai_generation", False, cfg)
    assert fired > 0 > not_fired


def test_fuse_figure_probability_rises_with_evidence():
    cfg = FusionConfig(prior=0.5)
    clean = {"copy_move": {"status": "ok", "forged": False},
             "cross_figure": {"status": "ok", "n_exact": 0, "n_region_reuse": 0},
             "ai_generation": {"status": "ok", "verdict": "likely_real"},
             "claim_consistency": {"status": "ok", "consistent": True}}
    fraud = {"copy_move": {"status": "ok", "forged": True},
             "cross_figure": {"status": "ok", "n_exact": 1, "n_region_reuse": 0},
             "ai_generation": {"status": "ok", "verdict": "likely_ai_generated"},
             "claim_consistency": {"status": "ok", "consistent": False}}
    p_clean = fuse_figure(clean, cfg)["fraud_probability"]
    p_fraud = fuse_figure(fraud, cfg)["fraud_probability"]
    assert p_fraud > 0.5 > p_clean


def test_fuse_paper_noisy_or():
    # One strong figure dominates; all-weak stays low.
    assert fuse_paper([0.9, 0.1, 0.1]) > 0.9
    assert fuse_paper([0.1, 0.1, 0.1]) < 0.3
    assert fuse_paper([]) == 0.0


def test_default_calibration_all_detectors_informative():
    for name, c in DEFAULT_CALIBRATION.items():
        assert c["p_fire_fraud"] > c["p_fire_clean"], name


# --------------------------------------------------------- eval: AUC/LOOCV
def test_roc_auc_and_ap_perfect_separation():
    from src.evaluation.metrics import average_precision, roc_auc
    y = [True, True, False, False]
    scores = [0.9, 0.8, 0.2, 0.1]
    assert roc_auc(y, scores) == 1.0
    assert average_precision(y, scores) == 1.0


def test_roc_auc_random_is_half():
    from src.evaluation.metrics import roc_auc
    y = [True, False, True, False]
    scores = [0.5, 0.5, 0.5, 0.5]  # all ties -> 0.5
    assert roc_auc(y, scores) == 0.5


def test_roc_auc_undefined_single_class():
    from src.evaluation.metrics import roc_auc
    assert roc_auc([True, True], [0.1, 0.2]) is None


def test_average_precision_ignores_row_order_under_ties():
    """Ties must not be broken by the order rows happen to arrive in.

    benchmark_report.json stores fraud papers first, so a stable sort keyed on
    score alone used to rank every tied fraud paper above every tied clean one.
    A coarse statistic then reported AP 0.865 where honest tie-breaking gives
    ~0.61 — an inflation produced entirely by row order.
    """
    from src.evaluation.metrics import average_precision
    y = [True, True, False, False, True, False]
    scores = [1.0, 1.0, 1.0, 0.0, 0.0, 0.0]
    baseline = average_precision(y, scores)
    order = [5, 2, 0, 4, 1, 3]
    shuffled = average_precision([y[i] for i in order], [scores[i] for i in order])
    assert baseline == shuffled


def test_average_precision_all_tied_equals_base_rate():
    """With one indistinguishable block, precision is just the base rate."""
    from src.evaluation.metrics import average_precision
    y = [True, False, False, True]
    assert average_precision(y, [0.5] * 4) == 0.5


def test_count_matched_auc_neutralises_the_stratifying_variable():
    """The stratifying variable itself must score exactly 0.5 under this control.

    That is the whole point: figure count reaches ROC-AUC 0.681 on set 1, almost
    the pipeline's 0.685, so a control that does not zero it out is not a control.
    """
    from src.evaluation.metrics import count_matched_auc
    y = [True, True, False, False, True, False]
    counts = [3, 5, 3, 5, 3, 5]
    res = count_matched_auc(y, [float(c) for c in counts], counts)
    assert res["auc"] == 0.5
    assert res["n_pairs"] == 4      # 2 fraud@3 x 1 clean@3, 1 fraud@5 x 1 clean@5


def test_count_matched_auc_detects_signal_within_strata():
    from src.evaluation.metrics import count_matched_auc
    y = [True, False, True, False]
    counts = [4, 4, 9, 9]
    scores = [1.0, 0.0, 1.0, 0.0]        # fraud always wins inside its stratum
    assert count_matched_auc(y, scores, counts)["auc"] == 1.0


def test_count_matched_auc_ignores_uncomparable_papers():
    from src.evaluation.metrics import count_matched_auc
    y = [True, False, True]
    counts = [2, 2, 77]                  # the 77-figure fraud paper has no match
    res = count_matched_auc(y, [1.0, 0.0, 1.0], counts)
    assert res["n_pairs"] == 1 and res["n_strata"] == 1


def test_count_matched_auc_undefined_without_pairs():
    from src.evaluation.metrics import count_matched_auc
    res = count_matched_auc([True, False], [1.0, 0.0], [1, 2])
    assert res["auc"] is None and res["n_pairs"] == 0


def test_ranking_metrics_carries_the_control_when_strata_given():
    from src.evaluation.metrics import ranking_metrics
    y = [True, False, True, False]
    out = ranking_metrics(y, [0.9, 0.1, 0.8, 0.2], strata=[3, 3, 4, 4])
    assert out["count_matched"]["auc"] == 1.0
    assert "count_matched" not in ranking_metrics(y, [0.9, 0.1, 0.8, 0.2])


def test_average_precision_matches_sklearn_under_heavy_ties():
    import random

    from sklearn.metrics import average_precision_score

    from src.evaluation.metrics import average_precision
    rng = random.Random(7)
    for _ in range(60):
        n = rng.randint(6, 40)
        y = [rng.random() < 0.4 for _ in range(n)]
        if not any(y) or all(y):
            continue
        scores = [rng.choice([0, 1, 2, 3, 0.5]) for _ in range(n)]
        assert average_precision(y, scores) == pytest.approx(
            float(average_precision_score(y, scores)), abs=1e-4)


def test_loocv_threshold_accuracy_runs():
    from src.evaluation.metrics import loocv_threshold_accuracy
    # Well-separated classes with a comfortable margin -> LOOCV recovers it.
    y = [True] * 6 + [False] * 6
    scores = [0.90, 0.88, 0.95, 0.92, 0.86, 0.91,
              0.10, 0.12, 0.08, 0.15, 0.11, 0.09]
    out = loocv_threshold_accuracy(y, scores)
    assert out["loocv_accuracy"] == pytest.approx(1.0)
    assert 0.15 < out["modal_threshold"] < 0.86


def test_loocv_penalizes_overlapping_classes():
    """LOOCV is honest: when the classes overlap it cannot reach 1.0."""
    from src.evaluation.metrics import loocv_threshold_accuracy
    y = [True] * 6 + [False] * 6
    # Deliberately overlapping: a fraud at 0.40 sits among the clean scores.
    scores = [0.8, 0.7, 0.9, 0.75, 0.85, 0.40,
              0.2, 0.3, 0.1, 0.25, 0.15, 0.45]
    out = loocv_threshold_accuracy(y, scores)
    assert out["loocv_accuracy"] < 1.0


def test_estimate_fire_calibration_smoothed():
    from src.evaluation.metrics import estimate_fire_calibration
    # Fires on every fraud, never on clean -> smoothed, never 1.0/0.0.
    fired = [True, True, True, False, False, False]
    labels = [True, True, True, False, False, False]
    cal = estimate_fire_calibration(fired, labels)
    assert 0.0 < cal["p_fire_clean"] < cal["p_fire_fraud"] < 1.0


# ---------------------------------------------------------------------------
# Non-ASCII paths. cv2.imread hands the filename to the C++ layer in the system
# locale encoding, so on Windows it silently returns None for any path outside
# the active code page -- and this project's inputs are user-uploaded PDFs and
# PMC filenames, on a Windows-primary environment.
# ---------------------------------------------------------------------------
def test_image_io_round_trips_a_non_ascii_path(tmp_path):
    import numpy as np

    from src.utils.image_io import load_image, load_mask, save_image, save_mask

    folder = tmp_path / "Müller_étude_日本語"
    folder.mkdir()
    path = str(folder / "figuré_ünï.png")

    original = np.dstack([
        np.full((30, 40), 10, np.uint8),
        np.full((30, 40), 120, np.uint8),
        np.full((30, 40), 250, np.uint8),
    ])
    save_image(original, path)
    assert os.path.isfile(path)

    loaded = load_image(path)
    assert loaded.shape == original.shape
    np.testing.assert_array_equal(loaded, original)

    gray = load_image(path, grayscale=True)
    assert gray.ndim == 2

    mask_path = str(folder / "figuré_ünï_mask.png")
    mask = np.zeros((30, 40), np.uint8)
    mask[5:15, 5:15] = 255
    save_mask(mask, mask_path)
    np.testing.assert_array_equal(load_mask(mask_path), mask)


def test_load_image_still_raises_for_a_missing_file(tmp_path):
    from src.utils.image_io import load_image

    with pytest.raises(FileNotFoundError):
        load_image(str(tmp_path / "nope_ünï.png"))


def test_load_image_raises_for_a_non_image(tmp_path):
    from src.utils.image_io import load_image

    junk = tmp_path / "nöt_an_image.png"
    junk.write_bytes(b"definitely not a PNG")
    with pytest.raises(FileNotFoundError):
        load_image(str(junk))

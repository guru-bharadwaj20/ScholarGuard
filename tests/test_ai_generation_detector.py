"""Unit tests for the Stage 4 AI-generation detector.

Real vs. AI-generated samples are synthesized on the fly (seeded RNG):
``make_base_figure`` gives a real-sensor-noise image, and
``apply_generative_artifacts`` bakes in the diffusion/GAN forensic
signatures the detector keys on. No trained classifier weights are
required — the tests exercise the fully-local forensic path and the
graceful-fallback / combination logic.
"""

import numpy as np
import pytest

from src.detectors.ai_generation_detector import (
    LIKELY_AI,
    LIKELY_REAL,
    SUSPICIOUS,
    detect_ai_generation,
)
from src.forensics.frequency_analysis import analyze_frequency_spectrum
from src.forensics.noise_residual import analyze_noise_residual
from src.utils.image_io import save_image
from src.utils.synth import apply_generative_artifacts, make_base_figure


@pytest.fixture(scope="module")
def sample_pair(tmp_path_factory):
    """A (real_path, ai_path) pair sharing the same underlying content."""
    tmp = tmp_path_factory.mktemp("stage4")
    rng = np.random.default_rng(7)
    real = make_base_figure(rng, size=(480, 640))
    ai = apply_generative_artifacts(real, rng)
    real_path = str(tmp / "real.png")
    ai_path = str(tmp / "ai.png")
    save_image(real, real_path)
    save_image(ai, ai_path)
    return real_path, ai_path


# ---------------------------------------------------------------- test 1
def test_frequency_analysis_separates_pair(sample_pair):
    real_path, ai_path = sample_pair
    real = analyze_frequency_spectrum(real_path)
    ai = analyze_frequency_spectrum(ai_path)
    assert ai["anomaly_score"] > real["anomaly_score"]
    # The AI sample should show the periodic-grid tell more strongly.
    assert ai["periodicity"] >= real["periodicity"]


# ---------------------------------------------------------------- test 2
def test_noise_residual_separates_pair(sample_pair):
    real_path, ai_path = sample_pair
    real = analyze_noise_residual(real_path)
    ai = analyze_noise_residual(ai_path)
    assert ai["anomaly_score"] > real["anomaly_score"]
    # Over-smoothed synthetic residual is more spatially correlated.
    assert ai["autocorrelation"] > real["autocorrelation"]


# ---------------------------------------------------------------- test 3
def test_end_to_end_without_classifier_weights(sample_pair):
    """Runs fully locally (no weights) and still returns sane verdicts."""
    real_path, ai_path = sample_pair
    real = detect_ai_generation(real_path, weights_path="does/not/exist.pt")
    ai = detect_ai_generation(ai_path, weights_path="does/not/exist.pt")

    # Graceful fallback: classifier score is absent, forensics still decide.
    assert real["classifier_score"] is None
    assert ai["classifier_score"] is None
    assert "no classifier weights" in real["explanation"]

    assert real["combined_verdict"] == LIKELY_REAL
    assert ai["combined_verdict"] in (SUSPICIOUS, LIKELY_AI)
    # Full structured contract.
    for res in (real, ai):
        assert set(res) >= {"frequency_anomaly_score", "noise_residual_anomaly_score",
                            "classifier_score", "combined_verdict", "explanation"}
        assert 0.0 <= res["frequency_anomaly_score"] <= 1.0
        assert 0.0 <= res["noise_residual_anomaly_score"] <= 1.0


# ---------------------------------------------------------------- test 4
def test_combination_logic_resolves_conflicts(monkeypatch, sample_pair):
    """With weights present, a classifier that strongly disagrees with the
    forensics must resolve to 'suspicious' (documented conflict rule),
    while agreement lets the blended score decide."""
    real_path, _ = sample_pair
    import src.detectors.ai_generation_detector as mod

    # Case A: real-looking forensics (low scores) but classifier screams AI.
    monkeypatch.setattr(mod, "classify_artifact",
                        lambda p, w=None: {"is_ai_generated": True,
                                           "confidence": 0.99,
                                           "p_ai_generated": 0.99,
                                           "val_accuracy": 0.9})
    conflicted = detect_ai_generation(real_path, weights_path="pretend.pt")
    assert conflicted["combined_verdict"] == SUSPICIOUS
    assert "disagree" in conflicted["explanation"]

    # Case B: classifier agrees with (low) forensics -> likely_real.
    monkeypatch.setattr(mod, "classify_artifact",
                        lambda p, w=None: {"is_ai_generated": False,
                                           "confidence": 0.95,
                                           "p_ai_generated": 0.05,
                                           "val_accuracy": 0.9})
    agreed = detect_ai_generation(real_path, weights_path="pretend.pt")
    assert agreed["combined_verdict"] == LIKELY_REAL
    assert agreed["classifier_score"] == 0.05


# ------------------------------------------------------------ extra checks
def test_verdict_thresholds_are_ordered():
    from src.detectors.ai_generation_detector import (
        COMBINED_HIGH, COMBINED_LOW, FORENSIC_HIGH, FORENSIC_LOW,
    )
    assert 0 < FORENSIC_LOW < FORENSIC_HIGH < 1
    assert 0 < COMBINED_LOW < COMBINED_HIGH < 1


def test_classifier_returns_none_without_weights(sample_pair):
    from src.models.artifact_classifier import classify_artifact, weights_available
    real_path, _ = sample_pair
    assert weights_available("no/such/file.pt") is False
    assert classify_artifact(real_path, "no/such/file.pt") is None


def test_forensic_bands_recalibrated_to_real_baseline():
    """Lock the 2026-07-11 real-data recalibration of the forensic bands.

    Real clean PMC figures score forensic mean 0.357, sd 0.107. A score of
    ~0.45 (about 1 sd above the real mean) is well within the real-figure
    range and used to be wrongly called 'suspicious' under the old synthetic
    band (0.35); it must now read 'likely_real'. Scores only fire once they
    are clearly above the real baseline (~mean+2sd and ~mean+3sd).
    """
    from src.detectors.ai_generation_detector import (
        _forensic_verdict, LIKELY_REAL, SUSPICIOUS, LIKELY_AI,
        REAL_CLEAN_FORENSIC_MEAN, REAL_CLEAN_FORENSIC_STD,
        FORENSIC_LOW, FORENSIC_HIGH,
    )
    # A typical real figure (~mean, and ~mean+1sd) is not flagged any more.
    assert _forensic_verdict(REAL_CLEAN_FORENSIC_MEAN) == LIKELY_REAL
    assert _forensic_verdict(0.45) == LIKELY_REAL
    # The bands sit ~2 sd and ~3 sd above the measured real-clean mean.
    two_sd = REAL_CLEAN_FORENSIC_MEAN + 2 * REAL_CLEAN_FORENSIC_STD
    three_sd = REAL_CLEAN_FORENSIC_MEAN + 3 * REAL_CLEAN_FORENSIC_STD
    assert abs(FORENSIC_LOW - two_sd) < 0.03
    assert abs(FORENSIC_HIGH - three_sd) < 0.03
    assert _forensic_verdict(two_sd + 0.005) == SUSPICIOUS
    assert _forensic_verdict(three_sd + 0.02) == LIKELY_AI

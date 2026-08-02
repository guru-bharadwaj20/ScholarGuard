"""The fusion calibration exists twice; the two copies must agree.

src.pipeline.evidence_fusion carries DEFAULT_CALIBRATION and DEFAULT_PRIOR as
conservative fallbacks for an unconfigured install, and config.yaml carries the
same five likelihood-ratio pairs under `evidence_fusion:`. Nothing forced them
to match, so a recalibration applied to one copy would silently leave the other
behind -- and which one wins depends on whether a caller passed settings.
"""

import pytest

from src.config.settings import load_settings
from src.pipeline.evidence_fusion import (
    DEFAULT_CALIBRATION,
    DEFAULT_PRIOR,
    FusionConfig,
    _FUSION_DETECTORS,
)


@pytest.fixture(scope="module")
def shipped() -> dict:
    return load_settings().raw["evidence_fusion"]


def test_prior_matches(shipped):
    assert shipped["prior"] == pytest.approx(DEFAULT_PRIOR)


def test_every_detector_is_calibrated_in_both_places(shipped):
    assert set(shipped["calibration"]) == set(DEFAULT_CALIBRATION)
    assert set(DEFAULT_CALIBRATION) == set(_FUSION_DETECTORS), (
        "a fused detector with no calibration silently contributes zero "
        "evidence")


@pytest.mark.parametrize("detector", sorted(DEFAULT_CALIBRATION))
def test_calibration_values_match(shipped, detector):
    yaml_values = shipped["calibration"][detector]
    code_values = DEFAULT_CALIBRATION[detector]
    for key in ("p_fire_fraud", "p_fire_clean"):
        assert yaml_values[key] == pytest.approx(code_values[key]), (
            f"{detector}.{key} differs between config.yaml and "
            f"evidence_fusion.DEFAULT_CALIBRATION")


def test_loading_the_shipped_config_reproduces_the_code_defaults(shipped):
    """End to end: the built FusionConfig equals the in-code fallback."""
    built = FusionConfig.from_settings_dict(shipped)
    assert built.prior == pytest.approx(DEFAULT_PRIOR)
    for detector, values in DEFAULT_CALIBRATION.items():
        assert built.calibration[detector] == values


def test_probabilities_are_valid():
    """A rate outside (0, 1) would make the log-likelihood ratio meaningless."""
    for detector, values in DEFAULT_CALIBRATION.items():
        for key in ("p_fire_fraud", "p_fire_clean"):
            assert 0.0 < values[key] < 1.0, f"{detector}.{key} out of range"

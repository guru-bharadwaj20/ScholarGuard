"""config.yaml must be able to reach every knob the detectors document.

The builders used to carry hand-maintained whitelists of key names, so roughly
35 documented options were silently inert -- editing them in config.yaml did
nothing, with no error and no warning, against a file whose own header says
"Edit values here, not in the detector source".
"""

import dataclasses

import pytest

from src.config.settings import ConfigError, Settings, load_settings
from src.detectors.copy_move_detector import DetectorConfig
from src.detectors.cross_figure_detector import CrossFigureConfig
from src.forensics.splice_detection import SpliceConfig


def _settings(detector: str, values: dict) -> Settings:
    return Settings(raw={"detectors": {detector: values}})


@pytest.mark.parametrize("detector, builder, cls", [
    ("copy_move", "copy_move_config", DetectorConfig),
    ("cross_figure", "cross_figure_config", CrossFigureConfig),
    ("splice", "splice_config", SpliceConfig),
])
def test_every_scalar_field_is_settable(detector, builder, cls):
    """No dataclass field may be unreachable from config.yaml."""
    default = cls()
    overrides = {}
    for f in dataclasses.fields(cls):
        current = getattr(default, f.name)
        if dataclasses.is_dataclass(current):
            continue                     # nested sections tested separately
        if isinstance(current, bool):
            overrides[f.name] = not current
        elif isinstance(current, int):
            overrides[f.name] = current + 7
        elif isinstance(current, float):
            overrides[f.name] = current + 0.125
        elif isinstance(current, tuple):
            overrides[f.name] = [1, 2, 3]

    built = getattr(_settings(detector, overrides), builder)()
    for name, value in overrides.items():
        got = getattr(built, name)
        expected = tuple(value) if isinstance(value, list) else value
        assert got == expected, f"{cls.__name__}.{name} is not settable"


def test_previously_inert_knobs_now_apply():
    """The specific keys the whitelists dropped, named so they stay covered."""
    cm = _settings("copy_move", {
        "dense_confirmed_only": False,     # documented as "the precision gate"
        "zncc_threshold": 0.9,
        "cluster_eps": 40.0,
        "min_region_area": 999,
        "max_keypoints": 1234,
    }).copy_move_config()
    assert cm.dense_confirmed_only is False
    assert cm.zncc_threshold == 0.9
    assert cm.cluster_eps == 40.0
    assert cm.min_region_area == 999
    assert cm.max_keypoints == 1234

    sp = _settings("splice", {"noise_mad_z": 5.0, "ghost_mad_z": 5.5,
                              "ela_mad_z": 6.0, "block": 16}).splice_config()
    assert (sp.noise_mad_z, sp.ghost_mad_z, sp.ela_mad_z) == (5.0, 5.5, 6.0)
    assert sp.block == 16

    cf = _settings("cross_figure", {"zncc_threshold": 0.8, "corr_norm": 0.5,
                                    "highpass_sigma": 6.0}).cross_figure_config()
    assert (cf.zncc_threshold, cf.corr_norm, cf.highpass_sigma) == (0.8, 0.5, 6.0)


def test_dense_tier_knobs_are_reachable():
    """DenseCMFDConfig was 100% unconfigurable: the call passed no cfg at all."""
    cm = _settings("copy_move", {
        "dense": {"min_support": 200, "zncc_min": 0.75,
                  "require_residual_confirm": False},
    }).copy_move_config()
    assert cm.dense.min_support == 200
    assert cm.dense.zncc_min == 0.75
    assert cm.dense.require_residual_confirm is False
    # Untouched dense fields keep their defaults.
    assert cm.dense.block == 16


def test_cross_figure_nested_stage2_block_applies():
    cf = _settings("cross_figure",
                   {"stage2": {"zncc_window": 15}}).cross_figure_config()
    assert cf.stage2.zncc_window == 15


def test_yaml_list_becomes_a_tuple_field():
    sp = _settings("splice", {"ghost_qualities": [50, 75]}).splice_config()
    assert sp.ghost_qualities == (50, 75)


def test_unknown_option_is_an_error_not_a_silent_no_op():
    """A typo used to be indistinguishable from leaving the default."""
    with pytest.raises(ConfigError, match="unknown DetectorConfig option"):
        _settings("copy_move", {"confidence_threshhold": 0.9}).copy_move_config()


def test_section_metadata_keys_are_not_mistaken_for_typos():
    assert _settings("copy_move", {"enabled": True}).copy_move_config()
    assert _settings("cross_figure", {"enabled": False,
                                      "corpus_dir": "/tmp/x"}).cross_figure_config()
    assert _settings("splice", {"enabled": True}).splice_config()


def test_shipped_config_still_builds_every_detector_config():
    settings = load_settings()
    assert settings.copy_move_config().confidence_threshold == 0.45
    assert settings.cross_figure_config().phash_max_distance == 10
    assert settings.splice_config().min_flagged_blocks == 4

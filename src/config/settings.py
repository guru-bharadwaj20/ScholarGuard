"""Typed configuration loader for the ScholarGuard pipeline.

Loads ``config.yaml`` once, validates required fields, and exposes a typed
:class:`Settings` object. Other modules import this instead of hardcoding
values. Stage 2/3 thresholds are turned into their existing config dataclasses
via :meth:`Settings.copy_move_config` / :meth:`Settings.cross_figure_config`,
so the detector source files are never edited — configuration flows
config.yaml -> Settings -> existing DetectorConfig/CrossFigureConfig -> detector.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

# Category ordering, low -> high, used for comparisons.
RISK_CATEGORIES = ["low", "moderate", "high", "critical"]


class ConfigError(RuntimeError):
    """Raised when config.yaml is missing required fields or malformed."""


@dataclass
class Settings:
    """Typed, validated view over config.yaml."""

    raw: dict[str, Any] = field(default_factory=dict)
    config_path: str = DEFAULT_CONFIG_PATH

    # -- detector toggles ---------------------------------------------------
    def enabled(self, detector: str) -> bool:
        return bool(self._detector(detector).get("enabled", True))

    def _detector(self, name: str) -> dict:
        return self.raw.get("detectors", {}).get(name, {})

    # -- Stage 2 / 3 config-object builders (no detector source edits) ------
    def copy_move_config(self):
        """Build a Stage 2 DetectorConfig from config.yaml threshold values."""
        from src.detectors.copy_move_detector import DetectorConfig

        cfg = self._detector("copy_move")
        return _apply(DetectorConfig(), cfg, [
            "confidence_threshold", "ratio_threshold", "min_inliers",
            "sift_contrast_threshold", "max_dim",
            "surprise_midpoint", "surprise_width",
            "localization_scale", "localization_floor",
            "use_analysis_mask", "residual_independent_factor",
            "residual_inconclusive_factor",
            "use_dense_tier", "dense_escalate_below",
        ])

    def cross_figure_config(self):
        """Build a Stage 3 CrossFigureConfig from config.yaml threshold values."""
        from src.detectors.cross_figure_detector import CrossFigureConfig

        cfg = self._detector("cross_figure")
        return _apply(CrossFigureConfig(), cfg, [
            "phash_max_distance", "embed_review", "embed_high",
            "min_inliers", "min_region_area", "top_k",
            "use_analysis_mask", "min_content_entropy",
            "residual_independent_factor", "residual_inconclusive_factor",
            "residual_veto_independent",
        ])

    # -- Stage 4 / 5 --------------------------------------------------------
    @property
    def ai_weights_path(self) -> str | None:
        return self._detector("ai_generation").get("weights_path")

    def ai_forensic_bands(self, default_low: float,
                          default_high: float) -> tuple[float, float]:
        """Forensic (suspicious, likely-AI) thresholds for the AI detector.

        Falls back to the detector's real-data-recalibrated module defaults
        when config.yaml does not override them.
        """
        cfg = self._detector("ai_generation")
        low = cfg.get("forensic_suspicious_threshold")
        high = cfg.get("forensic_ai_threshold")
        return (float(low) if low is not None else default_low,
                float(high) if high is not None else default_high)

    @property
    def panel_count_tolerance(self) -> float:
        return float(self._detector("claim_consistency").get(
            "panel_count_tolerance", 0.5))

    @property
    def use_vision_observation(self) -> bool:
        """Whether to attach the figure image to the LLM call (multimodal)."""
        return bool(self._detector("claim_consistency").get(
            "use_vision_observation", True))

    @property
    def cross_figure_corpus_dir(self) -> str | None:
        return self._detector("cross_figure").get("corpus_dir")

    def splice_config(self):
        """Build a SpliceConfig from config.yaml threshold values."""
        from src.forensics.splice_detection import SpliceConfig

        cfg = self._detector("splice")
        return _apply(SpliceConfig(), cfg, ["min_flagged_frac", "min_flagged_blocks"])

    def ai_compression_baselines(self) -> dict | None:
        """Compression-conditioned AI-forensic baselines for the AI detector.

        Returns the ``{stratum: {mean, std}}`` map when
        ``condition_on_compression`` is on and baselines are configured;
        ``None`` when it is on but none are configured (the detector then uses
        its own ``DEFAULT_BASELINES``); and an **empty dict** when conditioning
        is explicitly disabled, which is the detector's documented signal to
        fall back to the absolute forensic bands.

        The three return values are distinct on purpose -- ``{}`` and ``None``
        mean opposite things to ``detect_ai_generation``.
        """
        cfg = self._detector("ai_generation")
        if not cfg.get("condition_on_compression", True):
            return {}   # empty dict = conditioning explicitly disabled
        return cfg.get("compression_baselines") or None

    def ai_threshold_conflict(self) -> str | None:
        """Warn when configured absolute AI bands cannot take effect.

        ``forensic_suspicious_threshold`` / ``forensic_ai_threshold`` are only
        consulted when compression conditioning is OFF: with it on, the detector
        derives its bands from the per-stratum baseline (mean + 2sd / mean + 3sd)
        and overwrites whatever was passed in. Editing those two keys while
        ``condition_on_compression`` is true therefore changes nothing, which
        previously happened silently. Returns an explanatory string in that
        case, else None.
        """
        cfg = self._detector("ai_generation")
        if not cfg.get("condition_on_compression", True):
            return None
        configured = [k for k in ("forensic_suspicious_threshold",
                                  "forensic_ai_threshold")
                      if cfg.get(k) is not None]
        if not configured:
            return None
        return (f"ai_generation: {' and '.join(configured)} "
                f"{'are' if len(configured) > 1 else 'is'} IGNORED because "
                f"condition_on_compression is true -- the bands come from "
                f"compression_baselines (mean+2sd / mean+3sd) instead. Set "
                f"condition_on_compression: false to use the absolute bands.")

    # -- LLM ----------------------------------------------------------------
    @property
    def llm_model(self) -> str:
        return self.raw.get("llm", {}).get("model", "claude-opus-4-8")

    @property
    def llm_max_retries(self) -> int:
        return int(self.raw.get("llm", {}).get("max_retries", 3))

    @property
    def llm_timeout_seconds(self) -> float:
        """Per-request wall-clock cap for Claude calls.

        config.yaml has carried this key since the beginning but nothing read
        it, so requests ran with no timeout of ours at all -- a stalled
        connection could hang a whole benchmark.
        """
        from src.llm.client import DEFAULT_TIMEOUT_SECONDS

        return float(self.raw.get("llm", {}).get("timeout_seconds",
                                                 DEFAULT_TIMEOUT_SECONDS))

    # -- optimization -------------------------------------------------------
    @property
    def skip_llm_when_image_risk(self) -> bool:
        return bool(self.raw.get("optimization", {}).get(
            "skip_llm_when_image_risk", False))

    @property
    def skip_llm_at_category(self) -> str:
        return self.raw.get("optimization", {}).get("skip_llm_at_category",
                                                    "critical")

    # -- risk scoring -------------------------------------------------------
    @property
    def risk(self) -> dict:
        return self.raw.get("risk_scoring", {})

    # -- paths / logging ----------------------------------------------------
    @property
    def output_dir(self) -> str:
        return self.raw.get("paths", {}).get("output_dir", "outputs/stage6_results")

    @property
    def log_level(self) -> str:
        return self.raw.get("logging", {}).get("level", "INFO")

    # -- validation ---------------------------------------------------------
    def validate(self) -> None:
        """Fail fast on structural problems (missing sections, bad weights)."""
        for section in ("detectors", "risk_scoring"):
            if section not in self.raw:
                raise ConfigError(f"config.yaml missing required section: '{section}'")
        weights = self.risk.get("weights", {})
        total = sum(weights.get(k, 0) for k in
                    ("copy_move", "cross_figure", "splice", "ai_generation",
                     "claim_consistency"))
        if total <= 0:
            raise ConfigError("risk_scoring.weights must sum to a positive number")
        cats = self.risk.get("categories", {})
        for c in RISK_CATEGORIES:
            if c not in cats:
                raise ConfigError(f"risk_scoring.categories missing '{c}'")


def _apply(config_obj, values: dict, keys: list[str]):
    """Set the listed keys on a dataclass config object from a dict, if present."""
    for key in keys:
        if key in values and values[key] is not None:
            setattr(config_obj, key, values[key])
    return config_obj


def load_settings(config_path: str = DEFAULT_CONFIG_PATH) -> Settings:
    """Load, validate, and return the typed Settings for the pipeline."""
    if not os.path.isfile(config_path):
        raise ConfigError(f"config file not found: {config_path}")
    with open(config_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    settings = Settings(raw=raw, config_path=config_path)
    settings.validate()
    return settings

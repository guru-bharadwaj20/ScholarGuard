"""Likelihood-ratio evidence fusion (the "discount noisy detectors" layer).

Why this exists alongside the weighted-point score
--------------------------------------------------
The 0-100 point score (:mod:`src.pipeline.risk_scorer`) is a transparent,
fixed-weight sum — great for explaining *what* fired, but it has no way to
express "copy-move fires on clean papers 57% of the time, so a copy-move
flag is weak evidence". A detector that is right and a detector that is
barely better than a coin both add their full weight.

This module fuses detectors by **calibrated likelihood ratios** instead.
For each detector we hold, from data, the probability its signal fires on
fraudulent vs. clean figures:

    LR = P(signal | fraud) / P(signal | clean)

A detector whose fire rate is the same on fraud and clean has LR ~ 1 and
contributes ~0 to the log-odds — it is *automatically* discounted, with no
hand-tuned weight. Evidence combines as a naive-Bayes sum of log-LRs
(independence is an approximation, stated plainly), turned into a
posterior fraud probability through a configurable prior. Papers aggregate
their figures with **noisy-OR** — one convincingly fraudulent figure
drives the paper probability up, exactly the "worst figure dominates"
intent, but derived from probabilities rather than a 0.7/0.3 blend.

Calibration numbers live in ``config.yaml`` (``evidence_fusion``) and MUST
be estimated on held-out data (see src.evaluation for the LOOCV fit) — the
whole point is undone if they are guessed. Defaults here are deliberately
conservative (LRs near 1) so an unconfigured install does not over-claim.

Everything is additive: it augments the report with ``fraud_probability``
and per-detector LLR contributions; it does not replace the point score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Conservative default calibration: mild evidence only, so a fresh install
# (before real calibration) cannot produce over-confident posteriors. Each
# entry is P(this detector's signal | class). Replace via config after a
# proper held-out fit.
DEFAULT_CALIBRATION = {
    "copy_move": {"p_fire_fraud": 0.55, "p_fire_clean": 0.30},
    "cross_figure": {"p_fire_fraud": 0.45, "p_fire_clean": 0.20},
    "splice": {"p_fire_fraud": 0.35, "p_fire_clean": 0.08},
    "ai_generation": {"p_fire_fraud": 0.40, "p_fire_clean": 0.10},
    "claim_consistency": {"p_fire_fraud": 0.50, "p_fire_clean": 0.15},
}
# Per-FIGURE prior probability of manipulation. Deliberately low: even in a
# fraudulent paper most figures are genuine, and the paper-level noisy-OR
# compounds across figures, so a high per-figure prior makes every multi-panel
# paper look guilty. Calibrate against data before trusting the posterior.
DEFAULT_PRIOR = 0.12
_EPS = 1e-6
# Detectors fused, in a fixed order. Splice is included as an independent
# image-forensic signal alongside the others.
_FUSION_DETECTORS = ("copy_move", "cross_figure", "splice", "ai_generation",
                     "claim_consistency")


@dataclass
class FusionConfig:
    """Per-detector calibration + prior for likelihood-ratio fusion."""

    calibration: dict = field(default_factory=lambda: dict(DEFAULT_CALIBRATION))
    prior: float = DEFAULT_PRIOR

    @classmethod
    def from_settings_dict(cls, raw: dict | None) -> "FusionConfig":
        raw = raw or {}
        calib = dict(DEFAULT_CALIBRATION)
        for name, vals in (raw.get("calibration") or {}).items():
            calib.setdefault(name, {}).update(vals)
        return cls(calibration=calib,
                   prior=float(raw.get("prior", DEFAULT_PRIOR)))


def detector_fired(name: str, result: dict) -> bool | None:
    """Did a detector's signal fire? None when it did not run (no evidence).

    Mirrors the evaluation's fire rules so calibration and inference agree.
    """
    if result.get("status") not in ("ok", None):
        return None
    if name == "copy_move":
        return bool(result.get("forged"))
    if name == "cross_figure":
        return result.get("n_exact", 0) > 0 or result.get("n_region_reuse", 0) > 0
    if name == "splice":
        return bool(result.get("spliced"))
    if name == "ai_generation":
        return result.get("verdict") in ("suspicious", "likely_ai_generated")
    if name == "claim_consistency":
        return result.get("consistent") is False
    return None


def detector_llr(name: str, fired: bool | None, config: FusionConfig) -> float:
    """Log-likelihood ratio contributed by one detector's observed outcome.

    Uses the fire/no-fire outcome: ``log P(obs|fraud) / P(obs|clean)``.
    A detector that did not run contributes 0 (no evidence either way).
    """
    if fired is None:
        return 0.0
    calib = config.calibration.get(name)
    if not calib:
        return 0.0
    pf = min(max(calib.get("p_fire_fraud", 0.5), _EPS), 1 - _EPS)
    pc = min(max(calib.get("p_fire_clean", 0.5), _EPS), 1 - _EPS)
    if fired:
        return math.log(pf / pc)
    return math.log((1.0 - pf) / (1.0 - pc))


def fuse_figure(detectors: dict, config: FusionConfig) -> dict:
    """Posterior fraud probability for one figure from its detector results.

    Returns ``{"fraud_probability", "log_odds", "contributions": [...]}``
    where each contribution records a detector's fired state and its LLR
    (so a reviewer sees which evidence moved the needle, and by how much).
    """
    prior = min(max(config.prior, _EPS), 1 - _EPS)
    log_odds = math.log(prior / (1.0 - prior))
    contributions = []
    for name in _FUSION_DETECTORS:
        result = detectors.get(name, {"status": "skipped"})
        fired = detector_fired(name, result)
        llr = detector_llr(name, fired, config)
        log_odds += llr
        contributions.append({"detector": name, "fired": fired,
                              "log_likelihood_ratio": round(llr, 4)})
    prob = 1.0 / (1.0 + math.exp(-log_odds))
    return {
        "fraud_probability": round(prob, 4),
        "log_odds": round(log_odds, 4),
        "contributions": contributions,
    }


def fuse_paper(figure_probabilities: list[float]) -> float:
    """Noisy-OR of per-figure fraud probabilities -> paper probability.

    ``P(paper fraud) = 1 - prod(1 - p_i)``: one convincingly fraudulent
    figure drives the paper up, but each figure's *uncertainty* is carried
    through (unlike a hard max), so five weak figures still accumulate some
    evidence while never overwhelming one strong one.
    """
    keep = 1.0
    for p in figure_probabilities:
        keep *= (1.0 - min(max(p, 0.0), 1.0 - _EPS))
    return round(1.0 - keep, 4)

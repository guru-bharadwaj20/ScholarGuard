"""Noise-residual clone test: does a matched region carry *identical* noise?

The physics
-----------
Every real capture contains photon shot noise + sensor read noise, drawn
independently per exposure. Two *genuinely different* captures of
similar-looking content (replicate blots, dose-response panels) therefore
have statistically independent high-frequency residuals — their expected
correlation is 0. A **copy-pasted region carries its noise field with
it**: after alignment, the residuals of source and duplicate correlate
strongly. This is the same physical principle as PRNU camera-source
identification (Lukas, Fridrich & Goljan 2006), applied per-region.

This is the discriminator intensity-domain ZNCC fundamentally lacks:
ZNCC says "these regions look alike" — true for both clones and honest
replicates. Residual correlation says "these regions share one exposure's
noise" — true only for clones.

Honest limitations, encoded in the ``conclusive`` flag:

* Heavy JPEG compression / aggressive downsampling destroys the residual.
  When the residual energy inside the region is below a floor, the test
  returns **inconclusive** — never "independent" (absence of evidence).
* Interpolation from rotation/rescaling low-pass-filters the copied
  noise, attenuating (not erasing) the correlation — thresholds are set
  low to tolerate it.
* Flat/saturated regions carry no noise; they are excluded via the same
  std-floor.

Verdicts: ``clone`` / ``independent`` / ``inconclusive``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from src.forensics.noise_residual import extract_noise_residual

CLONE = "clone"
INDEPENDENT = "independent"
INCONCLUSIVE = "inconclusive"


@dataclass
class ResidualTestConfig:
    """Thresholds for the clone test. Deliberately permissive (see module doc)."""

    min_pixels: int = 400           # region too small -> inconclusive
    min_residual_std: float = 0.35  # gray levels; weaker residual -> inconclusive
    clone_corr_min: float = 0.20    # aligned residual corr >= this -> clone
    independent_corr_max: float = 0.08  # below this -> independent captures
    min_z: float = 4.0              # Fisher-z significance required for "clone"
    # The wavelet residual is not white (the denoiser correlates neighbouring
    # pixels), so N pixels are not N independent samples. A conservative
    # effective-sample-size divisor for the Fisher z-test:
    n_eff_divisor: float = 4.0


def residual_clone_test(
    gray_ref: np.ndarray,
    gray_aligned: np.ndarray,
    region_mask: np.ndarray,
    config: ResidualTestConfig | None = None,
) -> dict:
    """Test whether a matched region is a pixel clone or an honest look-alike.

    Args:
        gray_ref: grayscale image containing the *destination* region.
        gray_aligned: the *source* content warped into the destination frame
            (same shape as ``gray_ref``).
        region_mask: non-zero over the matched region (destination frame).

    Returns ``{"verdict", "correlation", "z", "n_pixels", "conclusive",
    "reason"}`` — ``correlation`` is the Pearson correlation of the two
    noise residuals over the region.
    """
    cfg = config or ResidualTestConfig()
    m = np.asarray(region_mask) > 0
    n_pixels = int(m.sum())
    if n_pixels < cfg.min_pixels:
        return _result(INCONCLUSIVE, 0.0, 0.0, n_pixels,
                       f"region too small ({n_pixels} px) for a stable "
                       f"noise-correlation estimate")

    ref = gray_ref.astype(np.float32)
    aligned = gray_aligned.astype(np.float32)

    # Residuals are extracted LOCALLY, on the region's bounding box — never on
    # the whole warped frame. warpAffine leaves large zero borders, and the
    # wavelet denoiser's global noise estimate collapses on them (the warped
    # residual goes to ~0), which would spuriously read "inconclusive" on a
    # genuine clone. Cropping first keeps the noise estimate on real content.
    ys, xs = np.where(m)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    sub_m = m[y0:y1, x0:x1]
    res_a_crop = extract_noise_residual(ref[y0:y1, x0:x1])
    res_b_crop = extract_noise_residual(aligned[y0:y1, x0:x1])

    a = res_a_crop[sub_m].astype(np.float64)
    b = res_b_crop[sub_m].astype(np.float64)
    std_a, std_b = float(a.std()), float(b.std())
    if std_a < cfg.min_residual_std or std_b < cfg.min_residual_std:
        return _result(
            INCONCLUSIVE, 0.0, 0.0, n_pixels,
            f"residual energy too low (std {std_a:.2f}/{std_b:.2f}) — heavy "
            f"compression or flat content; noise test cannot run")

    a -= a.mean()
    b -= b.mean()
    corr = float((a * b).sum() / (math.sqrt((a * a).sum() * (b * b).sum()) + 1e-12))
    corr = max(-1.0, min(1.0, corr))

    # Fisher z-test with a conservative effective sample size (the residual
    # field is spatially correlated by the denoiser, so N px != N samples).
    n_eff = max(4.0, n_pixels / cfg.n_eff_divisor)
    z = math.atanh(max(-0.999999, min(0.999999, corr))) * math.sqrt(n_eff - 3.0)

    if corr >= cfg.clone_corr_min and z >= cfg.min_z:
        return _result(CLONE, corr, z, n_pixels,
                       f"aligned noise residuals correlate (r={corr:.3f}, "
                       f"z={z:.1f}) — the regions share one capture's noise "
                       f"field, the physical signature of duplication")
    if corr < cfg.independent_corr_max:
        return _result(INDEPENDENT, corr, z, n_pixels,
                       f"noise residuals are independent (r={corr:.3f}) — "
                       f"consistent with genuinely distinct captures that "
                       f"merely look similar")
    return _result(INCONCLUSIVE, corr, z, n_pixels,
                   f"residual correlation r={corr:.3f} is in the ambiguous "
                   f"band — neither clone nor independent can be concluded")


def clone_factor(test: dict, independent_factor: float = 0.25,
                 inconclusive_factor: float = 0.85) -> float:
    """Multiplicative confidence factor in (0, 1] from a clone-test result.

    * ``clone``        -> 1.0  (physical evidence corroborates duplication)
    * ``independent``  -> ``independent_factor`` (strong evidence the match
      is a legitimate look-alike; suppress hard)
    * ``inconclusive`` -> ``inconclusive_factor`` (mild damping only — the
      test could not run, which must not erase intensity-domain evidence,
      because most published figures are JPEG-compressed)
    """
    verdict = test.get("verdict")
    if verdict == CLONE:
        return 1.0
    if verdict == INDEPENDENT:
        return float(independent_factor)
    return float(inconclusive_factor)


def _result(verdict: str, corr: float, z: float, n_pixels: int,
            reason: str) -> dict:
    return {
        "verdict": verdict,
        "correlation": round(corr, 4),
        "z": round(z, 2),
        "n_pixels": n_pixels,
        "conclusive": verdict != INCONCLUSIVE,
        "reason": reason,
    }

"""FFT-based spectral analysis for AI-generation detection.

Rationale
---------
Real sensor-captured images (microscopy, blots, gels) have a power
spectrum that falls off roughly as a power law ``P(f) ~ 1/f^alpha`` with
``alpha`` typically in ``[1.5, 3.0]``, and a *broadband* high-frequency
noise floor from the sensor. Generative models deviate in two
characteristic, measurable ways:

1. **Spectral falloff.** Diffusion/VAE decoders over-smooth high
   frequencies (steeper falloff, high-frequency energy suppressed) or,
   conversely, some GANs inject excess high-frequency energy — either way
   the radially-averaged spectrum departs from the natural power law and
   fits it poorly (low R^2).

2. **Periodic peaks.** Transposed-convolution ("deconv") upsampling in
   many GANs leaves a periodic grid, which shows up as bright peaks at
   regular offsets in the 2-D spectrum (the classic checkerboard
   signature). Real sensor noise has no such periodicity.

Everything here is pure NumPy FFT — fast on CPU, no training. Each metric
is turned into a sub-score in ``[0, 1]`` and combined into one anomaly
score (higher == more likely synthetic).
"""

from __future__ import annotations

import os

import cv2
import numpy as np

from src.utils.image_io import load_image

# Natural-image priors (see module docstring). These bound what counts as
# a "normal" radially-averaged spectral slope; the defaults are broad on
# purpose so genuine figures rarely trip them.
NATURAL_SLOPE_RANGE = (1.5, 3.0)
# High-freq-to-mid-band log-power gap: shallower than NATURAL reads natural,
# more suppressed than SUPPRESSED reads fully synthetic (see _high_freq_falloff).
NATURAL_FALLOFF_GAP = -4.5
SUPPRESSED_FALLOFF_GAP = -6.5
WORK_SIZE = 512  # analysis resolution; power-of-two keeps the FFT cheap


def _to_analysis_gray(image: np.ndarray) -> np.ndarray:
    """Center-crop to square, resize to WORK_SIZE, float32 grayscale."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    h, w = gray.shape
    side = min(h, w)
    top, left = (h - side) // 2, (w - side) // 2
    square = gray[top:top + side, left:left + side]
    resized = cv2.resize(square, (WORK_SIZE, WORK_SIZE), interpolation=cv2.INTER_AREA)
    return resized.astype(np.float32)


def _power_spectrum(gray: np.ndarray) -> np.ndarray:
    """2-D power spectrum with a Hann window (kills edge-wrap leakage)."""
    hann = np.outer(np.hanning(gray.shape[0]), np.hanning(gray.shape[1]))
    windowed = (gray - gray.mean()) * hann
    fft = np.fft.fftshift(np.fft.fft2(windowed))
    return np.abs(fft) ** 2


def _radial_profile(power: np.ndarray) -> np.ndarray:
    """Radially-averaged power as a function of integer radius (bin)."""
    h, w = power.shape
    cy, cx = h // 2, w // 2
    y, x = np.indices((h, w))
    radius = np.hypot(x - cx, y - cy).astype(int)
    total = np.bincount(radius.ravel(), weights=power.ravel())
    counts = np.bincount(radius.ravel())
    profile = total / np.maximum(counts, 1)
    return profile[: min(cy, cx)]  # drop corners beyond the inscribed circle


def _fit_power_law(profile: np.ndarray) -> tuple[float, float]:
    """Fit ``log P = -alpha * log f + c`` over mid/high frequencies.

    Returns (alpha, r_squared). The lowest few bins (DC + coarse
    structure) are skipped because real figures have strong, content-
    dependent low-frequency energy that doesn't follow the noise power law.
    """
    n = len(profile)
    lo, hi = max(3, n // 32), n - 1
    freqs = np.arange(lo, hi)
    log_f = np.log(freqs.astype(np.float64))
    log_p = np.log(profile[lo:hi] + 1e-12)

    slope, intercept = np.polyfit(log_f, log_p, 1)
    predicted = slope * log_f + intercept
    ss_res = np.sum((log_p - predicted) ** 2)
    ss_tot = np.sum((log_p - log_p.mean()) ** 2) + 1e-12
    return float(-slope), float(1.0 - ss_res / ss_tot)


def _high_freq_falloff(profile: np.ndarray) -> float:
    """Log-power gap between the high band and the mid band of the spectrum.

    Returns ``log(mean P over top half) - log(mean P over the mid octave)``
    — a negative number whose magnitude grows as high frequencies are
    suppressed. Real sensor images keep a broadband noise floor (gap around
    -3 to -4 on our figures); over-smoothed generated images push it much
    more negative. This is far more discriminative than a raw energy
    fraction, which saturates near zero for any natural image.
    """
    n = len(profile)
    high_band = float(profile[n // 2:].mean())
    mid_band = float(profile[n // 8: n // 4].mean())
    return float(np.log(high_band + 1e-12) - np.log(mid_band + 1e-12))


def _azimuthal_anisotropy(power: np.ndarray, profile: np.ndarray) -> float:
    """Off-axis angular concentration of spectral energy (GAN grid tell).

    The radial mean used elsewhere washes out *direction*: GAN upsampling
    grids put their peaks at specific angles, which the radial average
    hides. We divide the spectrum by its radial background, bin the
    mid/high-frequency residual by angle, and measure how concentrated it
    is in a few bins.

    Crucially, wedges within ±10° of the horizontal/vertical axes are
    EXCLUDED: scientific plots are full of axis-aligned strokes (axes,
    gridlines, lane edges) that legitimately concentrate energy there —
    including them would flag every line plot. Diagonal concentration has
    no such benign explanation.
    """
    h, w = power.shape
    cy, cx = h // 2, w // 2
    y, x = np.indices((h, w))
    radius = np.hypot(x - cx, y - cy)
    theta = np.degrees(np.arctan2(y - cy, x - cx)) % 180.0  # spectrum is symmetric

    n = len(profile)
    band = (radius >= n / 4) & (radius <= n - 1)
    off_axis = (np.minimum(theta % 90.0, 90.0 - theta % 90.0) > 10.0)
    sel = band & off_axis
    if not sel.any():
        return 0.0

    background = profile[np.clip(radius.astype(int), 0, n - 1)]
    residual = power / (background + 1e-12)

    bins = np.clip((theta[sel] / 5.0).astype(int), 0, 35)  # 5° angle bins
    sums = np.bincount(bins, weights=residual[sel], minlength=36)
    counts = np.bincount(bins, minlength=36).astype(np.float64)
    means = sums / np.maximum(counts, 1)
    means = means[counts > 0]
    if len(means) < 4:
        return 0.0
    peak = float(means.max())
    median = float(np.median(means)) + 1e-12
    # log-ratio squashed to [0, 1]; a >10x angular peak reads fully anomalous.
    return float(np.clip(np.log10(peak / median), 0.0, 1.0))


def _periodicity_score(power: np.ndarray, profile: np.ndarray) -> float:
    """Strength of periodic spectral peaks (GAN upsampling grid).

    Divides the 2-D spectrum by its radial-average background so genuine
    falloff is flattened out, then measures how strongly the residual
    spikes — real noise leaves a near-flat residual, a periodic grid
    leaves sharp peaks.
    """
    h, w = power.shape
    cy, cx = h // 2, w // 2
    y, x = np.indices((h, w))
    radius = np.hypot(x - cx, y - cy).astype(int)
    radius = np.clip(radius, 0, len(profile) - 1)

    background = profile[radius]
    residual = power / (background + 1e-12)
    # Ignore the low-frequency core (dominated by content, not artifacts).
    residual[radius < max(3, len(profile) // 16)] = 0.0

    peak = float(np.percentile(residual, 99.99))
    median = float(np.median(residual[residual > 0])) + 1e-12
    # Map the peak-to-background ratio to [0, 1]; ratios >~50 are strongly
    # periodic. log keeps it well-behaved across orders of magnitude.
    return float(np.clip(np.log10(peak / median) / 2.0, 0.0, 1.0))


def analyze_frequency_spectrum(
    image_path: str, heatmap_path: str | None = None
) -> dict:
    """Analyze an image's frequency spectrum for generative artifacts.

    Returns a dict with:
      * ``anomaly_score``   — combined score in [0, 1], higher == synthetic
      * ``spectral_slope``  — fitted power-law exponent alpha
      * ``slope_r2``        — goodness of the power-law fit (0..1)
      * ``high_freq_ratio`` — energy fraction in the upper spectrum half
      * ``periodicity``     — periodic-peak strength (0..1)
      * ``sub_scores``      — the individual [0,1] components

    If ``heatmap_path`` is given, a log-spectrum heatmap PNG is saved there.
    """
    gray = _to_analysis_gray(load_image(image_path))
    power = _power_spectrum(gray)
    profile = _radial_profile(power)

    slope, r2 = _fit_power_law(profile)
    hf_falloff = _high_freq_falloff(profile)
    periodicity = _periodicity_score(power, profile)
    anisotropy = _azimuthal_anisotropy(power, profile)

    # --- turn each raw metric into a [0, 1] "looks synthetic" sub-score ---
    lo, hi = NATURAL_SLOPE_RANGE
    if slope < lo:
        slope_score = np.clip((lo - slope) / lo, 0.0, 1.0)
    elif slope > hi:
        slope_score = np.clip((slope - hi) / hi, 0.0, 1.0)
    else:
        slope_score = 0.0
    fit_score = float(np.clip(1.0 - r2, 0.0, 1.0))          # poor power-law fit
    # High-freq suppression: gap of NATURAL_FALLOFF_GAP (~ -4.5) or shallower
    # is natural (0); by SUPPRESSED_FALLOFF_GAP (~ -6.5) it reads fully
    # synthetic. Calibrated on the Stage 4 sample set (real ~ -3.9, AI ~ -6.4).
    smooth_score = float(np.clip(
        (NATURAL_FALLOFF_GAP - hf_falloff) / (NATURAL_FALLOFF_GAP - SUPPRESSED_FALLOFF_GAP),
        0.0, 1.0,
    ))

    sub_scores = {
        "slope_deviation": float(slope_score),
        "poor_powerlaw_fit": fit_score,
        "high_freq_suppression": smooth_score,
        "periodicity": float(periodicity),
        "azimuthal_anisotropy": float(anisotropy),
    }
    # Weighted blend: periodicity, high-freq suppression and off-axis
    # anisotropy are the most specific tells for the diffusion/GAN
    # signatures we target. NOTE: adding/reweighting sub-scores changes the
    # anomaly scale — the real-data baseline (mean/std per compression
    # stratum in the AI detector) must be re-measured after any change here.
    anomaly = (0.30 * periodicity + 0.28 * smooth_score
               + 0.12 * slope_score + 0.18 * fit_score
               + 0.12 * anisotropy)

    if heatmap_path:
        _save_spectrum_heatmap(power, heatmap_path)

    return {
        "anomaly_score": float(np.clip(anomaly, 0.0, 1.0)),
        "spectral_slope": slope,
        "slope_r2": r2,
        "high_freq_falloff": hf_falloff,
        "periodicity": float(periodicity),
        "azimuthal_anisotropy": float(anisotropy),
        "sub_scores": sub_scores,
    }


def _save_spectrum_heatmap(power: np.ndarray, path: str) -> None:
    """Save a log-power spectrum as a JET heatmap for visual inspection."""
    from src.utils.visualization import make_heatmap
    from src.utils.image_io import save_image

    log_power = np.log1p(power)
    save_image(make_heatmap(log_power), path)

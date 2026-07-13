"""PRNU-style noise-residual analysis for AI-generation detection.

Rationale
---------
A real captured image is ``content + sensor_noise``. The sensor noise
(photon shot noise + PRNU + read noise) is a broadband, high-frequency,
roughly stationary field with characteristic statistics: a non-trivial
standard deviation, near-zero spatial autocorrelation (white-ish), and
heavy-ish tails. Extract it by denoising and subtracting:

    residual = image - denoise(image)

Generative models (GAN/diffusion) reconstruct from a smooth latent and
rarely reproduce a faithful sensor-noise field. Their residuals tend to
be **unnaturally weak** (over-smoothed), **spatially correlated** (the
denoiser removes little because there is little true high-frequency
content), or **too Gaussian/regular**. We quantify:

* residual energy (std) — synthetic often too low,
* spatial autocorrelation at lag 1 — synthetic often too high,
* mid-band spectral flatness of the residual — synthetic often not white,
* kurtosis — deviation from the heavy-tailed sensor-noise prior.

All CPU-friendly (a wavelet or Gaussian denoiser + simple statistics), no
training. Returns an anomaly score in ``[0, 1]`` (higher == synthetic).
"""

from __future__ import annotations

import cv2
import numpy as np
import pywt

from src.utils.image_io import load_image

WORK_SIZE = 512
# Expected sensor-noise residual std for an 8-bit image (very rough prior;
# real figures usually sit above ~1.5 gray levels of residual energy).
MIN_NATURAL_STD = 1.5
# Lag-1 residual autocorrelation: white sensor noise sits near NATURAL;
# an over-smoothed synthetic residual approaches SYNTHETIC. Calibrated on
# the Stage 4 sample set (real ~0.1 after native-res cropping, AI ~0.9).
NATURAL_AUTOCORR = 0.15
SYNTHETIC_AUTOCORR = 0.75


def _to_gray(image: np.ndarray) -> np.ndarray:
    """Center-crop (never resample) to <= WORK_SIZE, float32 grayscale.

    Resampling low-pass-filters and spatially correlates the sensor noise,
    destroying exactly the statistics this module measures — so we crop a
    native-resolution window instead of resizing.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    h, w = gray.shape
    ch, cw = min(h, WORK_SIZE), min(w, WORK_SIZE)
    top, left = (h - ch) // 2, (w - cw) // 2
    return gray[top:top + ch, left:left + cw].astype(np.float32)


def extract_noise_residual(gray: np.ndarray, method: str = "wavelet") -> np.ndarray:
    """Return the high-frequency noise residual of a grayscale image.

    ``wavelet`` uses a soft-thresholded Daubechies decomposition (the
    classic PRNU denoiser); ``gaussian`` subtracts a Gaussian-blurred copy
    (cheaper, coarser). Both return ``image - denoised``.
    """
    if method == "gaussian":
        denoised = cv2.GaussianBlur(gray, (0, 0), 1.5)
        return gray - denoised

    # Wavelet denoise: threshold detail coefficients (VisuShrink-style),
    # reconstruct the smooth image, residual = original - reconstruction.
    # Cap the level so small crops (region-local clone tests) don't request
    # more decomposition levels than their size supports.
    max_level = pywt.dwtn_max_level(gray.shape, "db4")
    level = max(1, min(4, max_level))
    coeffs = pywt.wavedec2(gray, "db4", level=level)
    detail = np.concatenate([c.ravel() for c in coeffs[1][:]])
    sigma = np.median(np.abs(detail)) / 0.6745 + 1e-6  # robust noise estimate
    threshold = sigma * np.sqrt(2 * np.log(gray.size))

    denoised_coeffs = [coeffs[0]]
    for level in coeffs[1:]:
        denoised_coeffs.append(tuple(pywt.threshold(c, threshold, mode="soft")
                                     for c in level))
    denoised = pywt.waverec2(denoised_coeffs, "db4")
    denoised = denoised[: gray.shape[0], : gray.shape[1]]  # waverec may pad
    return gray - denoised


def _lag1_autocorrelation(residual: np.ndarray) -> float:
    """Mean of horizontal + vertical lag-1 autocorrelation of the residual.

    White sensor noise -> ~0; over-smoothed/correlated synthetic noise ->
    higher positive values.
    """
    r = residual - residual.mean()
    denom = float(np.sum(r * r)) + 1e-12
    horiz = float(np.sum(r[:, :-1] * r[:, 1:])) / denom
    vert = float(np.sum(r[:-1, :] * r[1:, :])) / denom
    return (horiz + vert) / 2.0


def _spectral_flatness(residual: np.ndarray) -> float:
    """Spectral flatness (geo-mean / arith-mean of power) of the residual.

    White noise -> near 1.0; structured/correlated residual -> near 0.
    """
    power = np.abs(np.fft.fft2(residual - residual.mean())) ** 2
    power = power.ravel() + 1e-12
    geo = np.exp(np.mean(np.log(power)))
    arith = np.mean(power)
    return float(geo / arith)


def _kurtosis(residual: np.ndarray) -> float:
    """Excess kurtosis of residual values (0 == Gaussian)."""
    r = residual.ravel()
    r = r - r.mean()
    var = float(np.mean(r * r)) + 1e-12
    return float(np.mean(r ** 4) / (var ** 2) - 3.0)


def analyze_noise_residual(image_path: str, method: str = "wavelet") -> dict:
    """Analyze an image's sensor-noise residual for generative artifacts.

    Returns a dict with:
      * ``anomaly_score``    — combined score in [0, 1], higher == synthetic
      * ``residual_std``     — residual energy (gray levels)
      * ``autocorrelation``  — lag-1 spatial autocorrelation (~0 is natural)
      * ``spectral_flatness``— residual whiteness (1 is natural white noise)
      * ``kurtosis``         — excess kurtosis of the residual
      * ``sub_scores``       — the individual [0,1] components
    """
    gray = _to_gray(load_image(image_path))
    residual = extract_noise_residual(gray, method=method)

    std = float(residual.std())
    autocorr = _lag1_autocorrelation(residual)
    flatness = _spectral_flatness(residual)
    kurt = _kurtosis(residual)

    # --- map each metric to a [0, 1] "looks synthetic" sub-score ----------
    # Too little residual energy -> synthetic.
    weak_score = float(np.clip((MIN_NATURAL_STD - std) / MIN_NATURAL_STD, 0.0, 1.0))
    # Positive spatial correlation -> synthetic. White sensor noise sits
    # near NATURAL_AUTOCORR; by SYNTHETIC_AUTOCORR the residual is strongly
    # correlated (over-smoothed). Below the natural floor scores 0.
    corr_score = float(np.clip(
        (autocorr - NATURAL_AUTOCORR) / (SYNTHETIC_AUTOCORR - NATURAL_AUTOCORR),
        0.0, 1.0,
    ))
    # Low spectral flatness -> non-white residual -> synthetic.
    nonwhite_score = float(np.clip((0.5 - flatness) / 0.5, 0.0, 1.0))

    sub_scores = {
        "weak_residual": weak_score,
        "spatial_correlation": corr_score,
        "non_white_spectrum": nonwhite_score,
    }
    # Residual energy and whiteness are the most reliable tells here.
    anomaly = 0.4 * weak_score + 0.35 * corr_score + 0.25 * nonwhite_score

    return {
        "anomaly_score": float(np.clip(anomaly, 0.0, 1.0)),
        "residual_std": std,
        "autocorrelation": autocorr,
        "spectral_flatness": flatness,
        "kurtosis": kurt,
        "sub_scores": sub_scores,
    }

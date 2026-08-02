"""Blind JPEG-compression-strength estimation (blockiness).

Why the AI-generation detector needs this
-----------------------------------------
Publisher JPEG compression destroys sensor noise and suppresses high
frequencies — exactly the signals the AI-generation forensics measure.
The measured consequence: real clean PMC figures scored forensic ~0.36
(vs. ~0.17 for uncompressed captures), which forced a blanket +2σ
threshold hike that also threw away sensitivity on uncompressed images.
Estimating compression strength lets the detector compare each image
against a **baseline of real images at similar compression** instead of
one global baseline — the confound becomes a conditioning variable.

Method: the classic blocking-artifact measure. JPEG operates on an 8x8
grid, so compression leaves systematically larger intensity steps across
grid-aligned boundaries than inside blocks. We compare the mean absolute
step at every 8th column/row against the mean step elsewhere; their
normalized excess is the blockiness. Grid phase is unknown after
cropping, so all 8 phases are tried and the maximum taken. Pure NumPy,
training-free, resolution-independent.
"""

from __future__ import annotations

import numpy as np

# Compression strata for baseline conditioning.
LOW_COMPRESSION = "low_compression"        # blockiness below visibility
HIGH_COMPRESSION = "high_compression"      # clear 8x8 grid artifacts
BLOCKINESS_HIGH = 0.10                     # boundary steps >10% above interior


def estimate_blockiness(gray: np.ndarray) -> float:
    """Normalized 8x8 boundary-step excess. ~0 = no visible JPEG grid.

    Returns ``max over 8 grid phases of (boundary_step - interior_step) /
    interior_step``, computed for columns and rows and averaged. Negative
    values (boundaries smoother than interior) are clamped to 0.
    """
    g = gray.astype(np.float64)
    h, w = g.shape[:2]
    if h < 24 or w < 24:
        return 0.0

    def _axis_blockiness(diffs: np.ndarray) -> float:
        # diffs[k] = mean |I[k+1] - I[k]| along the axis.
        best = 0.0
        overall = float(diffs.mean()) + 1e-9
        for phase in range(8):
            boundary = diffs[phase::8]
            if len(boundary) < 2:
                continue
            interior = float((diffs.sum() - boundary.sum())
                             / max(len(diffs) - len(boundary), 1))
            excess = (float(boundary.mean()) - interior) / max(interior, overall * 0.1)
            best = max(best, excess)
        return best

    col_diffs = np.abs(np.diff(g, axis=1)).mean(axis=0)   # per column boundary
    row_diffs = np.abs(np.diff(g, axis=0)).mean(axis=1)
    return float(max(0.0, (_axis_blockiness(col_diffs)
                           + _axis_blockiness(row_diffs)) / 2.0))


def compression_stratum(gray: np.ndarray) -> tuple[str, float]:
    """Classify an image into a compression stratum for baseline lookup.

    Returns ``(stratum, blockiness)`` where stratum is
    ``low_compression`` or ``high_compression``. The two-way split is
    deliberate: with the small real calibration sets available, finer
    strata would just fit noise.
    """
    blockiness = estimate_blockiness(gray)
    stratum = HIGH_COMPRESSION if blockiness >= BLOCKINESS_HIGH else LOW_COMPRESSION
    return stratum, blockiness

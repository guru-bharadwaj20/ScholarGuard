"""Splice / foreign-region detection — the fraud mode the other detectors miss.

Why this exists
---------------
Copy-move finds a region duplicated *within* one figure; cross-figure finds a
figure reused whole. But the most common real image fraud is **splicing**:
pasting a band, blot, or panel from a *different* source into a figure. The
spliced region is not a duplicate of anything in the image, so copy-move and
cross-figure never see it — yet it carries the tell-tale fingerprints of a
different capture/processing history. This module looks for exactly those,
per-region, and returns a localized suspicion map + a bounded score.

Three complementary, CPU-only, training-free cues (any one can fire; together
they corroborate):

1. **Noise-residual inconsistency.** A single capture has a roughly stationary
   sensor-noise level. Split the image into blocks, measure each block's
   high-frequency residual energy, and flag blocks whose noise level is an
   outlier versus the image's own robust distribution — a foreign paste
   usually has visibly more or less noise than its host. (This is the inverse
   of the copy-move clone test in ``residual_similarity``: there we look for
   *shared* noise between two regions; here for a region whose noise does not
   *belong*.)

2. **JPEG-ghost / double-quantization.** A spliced region that was previously
   JPEG-compressed at a different quality leaves a "ghost": recompressing the
   whole image at a matching quality makes the foreign region's reconstruction
   error dip relative to its surroundings. We sweep quality factors and flag
   blocks whose error is a spatial outlier at some quality.

3. **Error-Level Analysis (ELA).** A single recompression raises error
   uniformly across an authentic image; edited regions, having a different
   compression history, show anomalously high or low local error. Classic,
   fast, and complementary to the above.

Every verdict is a **lead for human review**. Smooth/near-flat regions carry
no usable noise or compression signal and are excluded, so the detector stays
quiet on legitimately uniform panels rather than inventing artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.forensics.noise_residual import extract_noise_residual


@dataclass
class SpliceConfig:
    """Knobs for the three cues + the combined decision."""

    work_size: int = 1024          # cap the long side (speed); native detail kept
    block: int = 32                # analysis block size (px)
    min_block_std: float = 3.0     # blocks flatter than this carry no signal
    # --- noise inconsistency ---
    noise_mad_z: float = 3.5       # robust z (MAD) above which a block's noise is foreign
    # --- JPEG ghost ---
    ghost_qualities: tuple = (60, 70, 80, 90)
    ghost_mad_z: float = 3.5
    # --- ELA ---
    ela_quality: int = 90
    ela_mad_z: float = 3.5
    # --- decision ---
    min_flagged_frac: float = 0.02  # >= this fraction of textured blocks flagged => spliced
    min_flagged_blocks: int = 4     # and at least this many blocks (guards tiny images)


def _to_gray_bounded(image: np.ndarray, work_size: int) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    h, w = gray.shape[:2]
    longest = max(h, w)
    if longest > work_size:
        s = work_size / longest
        gray = cv2.resize(gray, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return gray


def _block_view(a: np.ndarray, block: int) -> tuple[np.ndarray, int, int]:
    """Trim to a whole number of blocks and reshape to (ny, nx, block, block)."""
    h, w = a.shape
    ny, nx = h // block, w // block
    a = a[: ny * block, : nx * block]
    return a.reshape(ny, block, nx, block).swapaxes(1, 2), ny, nx


def _robust_outlier_map(block_stat: np.ndarray, valid: np.ndarray,
                        mad_z: float, high_only: bool = False) -> np.ndarray:
    """Boolean per-block map: statistic is a robust (MAD) outlier among valid blocks.

    Uses median + MAD so a genuine splice (a minority of blocks) does not
    inflate its own threshold, unlike mean+std.
    """
    vals = block_stat[valid]
    if vals.size < 8:
        return np.zeros_like(block_stat, dtype=bool)
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) * 1.4826 + 1e-6
    z = (block_stat - med) / mad
    out = z >= mad_z if high_only else np.abs(z) >= mad_z
    return out & valid


def _noise_inconsistency(gray: np.ndarray, cfg: SpliceConfig):
    """Per-block sensor-noise energy, and blocks whose level is foreign."""
    residual = extract_noise_residual(gray.astype(np.float32))
    blocks, ny, nx = _block_view(residual, cfg.block)
    noise_std = blocks.std(axis=(2, 3))
    gblocks, _, _ = _block_view(gray.astype(np.float32), cfg.block)
    valid = gblocks.std(axis=(2, 3)) > cfg.min_block_std
    flagged = _robust_outlier_map(noise_std, valid, cfg.noise_mad_z)
    return flagged, valid, ny, nx


def _recompress_error(gray: np.ndarray, quality: int) -> np.ndarray:
    ok, enc = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        return np.zeros_like(gray, np.float32)
    dec = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE).astype(np.float32)
    return np.abs(gray.astype(np.float32) - dec)


def _jpeg_ghost(gray: np.ndarray, cfg: SpliceConfig, valid: np.ndarray):
    """Blocks that are a spatial error outlier at ANY swept recompression quality."""
    ny, nx = valid.shape
    any_flag = np.zeros((ny, nx), dtype=bool)
    for q in cfg.ghost_qualities:
        err = _recompress_error(gray, q)
        eb, _, _ = _block_view(err, cfg.block)
        block_err = eb.mean(axis=(2, 3))
        any_flag |= _robust_outlier_map(block_err, valid, cfg.ghost_mad_z)
    return any_flag


def _ela(gray: np.ndarray, cfg: SpliceConfig, valid: np.ndarray):
    err = _recompress_error(gray, cfg.ela_quality)
    eb, _, _ = _block_view(err, cfg.block)
    block_err = eb.mean(axis=(2, 3))
    return _robust_outlier_map(block_err, valid, cfg.ela_mad_z, high_only=True)


def detect_splice(image: np.ndarray, config: SpliceConfig | None = None,
                  analysis_mask: np.ndarray | None = None) -> dict:
    """Detect spliced / foreign regions in a figure.

    ``analysis_mask`` (optional, image-sized, 255 = analyze) restricts the
    search to continuous-tone content, matching the other detectors.

    Returns ``{"spliced": bool, "confidence": float, "n_flagged_blocks": int,
    "flagged_fraction": float, "mask": uint8 image-sized, "cues": {...}}``.
    """
    cfg = config or SpliceConfig()
    gray = _to_gray_bounded(image, cfg.work_size)

    noise_flag, valid, ny, nx = _noise_inconsistency(gray, cfg)
    ghost_flag = _jpeg_ghost(gray, cfg, valid)
    ela_flag = _ela(gray, cfg, valid)

    if analysis_mask is not None:
        m = cv2.resize(analysis_mask, (gray.shape[1], gray.shape[0]),
                       interpolation=cv2.INTER_NEAREST)
        mb, _, _ = _block_view(m, cfg.block)
        gate = mb.mean(axis=(2, 3)) > 127
        valid &= gate
        noise_flag &= gate
        ghost_flag &= gate
        ela_flag &= gate

    # A block counts as spliced only if BOTH independent evidence FAMILIES
    # agree on it: (A) sensor-noise inconsistency and (B) compression-history
    # inconsistency. JPEG-ghost and ELA are the SAME family (both measure
    # recompression error), so they co-fire on ordinary high-texture blocks —
    # counting them as two independent votes was a false-positive source.
    # Requiring a foreign noise level AND a foreign compression fingerprint is
    # the signature of a genuine paste, and stays quiet on authentic texture.
    compression_flag = ghost_flag | ela_flag
    block_flag = noise_flag & compression_flag

    n_valid = int(valid.sum())
    n_flag = int(block_flag.sum())
    frac = (n_flag / n_valid) if n_valid else 0.0
    spliced = bool(n_flag >= cfg.min_flagged_blocks and frac >= cfg.min_flagged_frac)

    # Confidence: how far above the firing floor, squashed to [0, 1].
    confidence = float(np.clip(frac / (2.0 * cfg.min_flagged_frac), 0.0, 1.0)) \
        if spliced else float(np.clip(frac / (2.0 * cfg.min_flagged_frac), 0.0, 0.44))

    # Upsample the block map to an image-sized mask for visualization/overlap.
    # Built at the bounded working resolution, then resized back to the INPUT
    # image's dimensions -- the docstring promises an image-sized mask, and a
    # caller overlaying a work-sized one on the original figure would have got a
    # silently misaligned result for any figure longer than cfg.work_size.
    mask = np.zeros(gray.shape, np.uint8)
    ys, xs = np.where(block_flag)
    for by, bx in zip(ys, xs):
        mask[by * cfg.block:(by + 1) * cfg.block,
             bx * cfg.block:(bx + 1) * cfg.block] = 255
    full_h, full_w = image.shape[:2]
    if mask.shape != (full_h, full_w):
        mask = cv2.resize(mask, (full_w, full_h),
                          interpolation=cv2.INTER_NEAREST)

    return {
        "spliced": spliced,
        "confidence": round(confidence, 4),
        "n_flagged_blocks": n_flag,
        "n_valid_blocks": n_valid,
        "flagged_fraction": round(frac, 4),
        "mask": mask,
        "cues": {
            "noise_inconsistency_blocks": int(noise_flag.sum()),
            "jpeg_ghost_blocks": int(ghost_flag.sum()),
            "ela_blocks": int(ela_flag.sum()),
        },
        "note": ("Spliced/foreign-region leads for human review, not proof. "
                 "Blocks require >=2 independent forensic cues to be flagged."),
    }

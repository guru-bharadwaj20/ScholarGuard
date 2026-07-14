"""Dense-field copy-move detection — the smooth-region tier SIFT can't do.

Why this exists
---------------
The SIFT copy-move detector needs distinctive keypoints. Western blots, gels,
and micrographs are *smooth*: large low-texture regions where SIFT finds few or
no stable keypoints, so a duplicated blot band or a cloned background patch
slips through. This module is the classical complement (Fridrich 2003 /
Popescu-Farid block matching): it examines **every** overlapping block, so it
sees duplications in exactly the low-texture areas SIFT misses.

Method (CPU-only, training-free):

1. Slide overlapping blocks over the (masked) grayscale image.
2. Describe each block by its low-frequency **DCT** coefficients — a compact,
   quantised feature that is near-identical for two copies of the same content
   and stable on smooth blocks (unlike keypoints).
3. Lexicographically sort the feature rows; genuine duplicate blocks become
   adjacent, so only near-neighbours in the sorted order are compared (O(n log
   n), not O(n²)).
4. For every matching block pair record its **shift vector**. A real copy-move
   translates a whole region by one vector, so many pairs share (almost) the
   same shift; a histogram peak in shift space with enough support is the
   detection. Scattered coincidental matches do not accumulate.
5. Grow the supporting blocks into a mask and confirm with ZNCC.

Rotation/scale are the SIFT tier's job; this tier targets the common
translate-and-paste case on smooth content. The two are combined (corroborate
/ take the stronger) in :class:`CopyMoveDetector`.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.forensics.residual_similarity import (
    INDEPENDENT,
    clone_factor,
    residual_clone_test,
)


@dataclass
class DenseCMFDConfig:
    max_dim: int = 600            # dense matching is heavier; cap the long side
    block: int = 16               # analysis block (px)
    step: int = 2                 # stride: small so ANY copy offset is caught
    n_dct: int = 10               # low-freq DCT coeffs kept per block (zigzag)
    quant: float = 4.0            # DCT quantisation step (robust to mild noise)
    sort_window: int = 4          # compare each row to this many sorted neighbours
    feat_max_dist: float = 6.0    # L2 feature distance to call two blocks equal
    min_offset: float = 24.0      # px; matched blocks nearer than this are self-noise
    offset_tol: int = 4           # px bin for shift-vector histogram
    min_support: int = 80         # matched block-pairs sharing one shift to fire
    min_local_std: float = 3.0    # flat blocks (below this) carry no signal
    zncc_min: float = 0.5         # mean ZNCC over grown region to keep it

    # -- noise-residual confirmation (the dense-tier false-positive gate) ----
    # Intensity ZNCC says "these blocks look alike" — true for a real clone AND
    # for legitimately self-similar texture (gel lanes, repeated blot bands),
    # which is exactly what over-fired on clean figures. The residual clone
    # test settles it: a genuine copy carries one capture's noise field
    # (identical residuals), an honest look-alike has independent noise. We
    # VETO an INDEPENDENT verdict (legitimate look-alike) and damp an
    # INCONCLUSIVE one (compressed/flat: test could not run).
    require_residual_confirm: bool = True
    residual_independent_factor: float = 0.25
    residual_inconclusive_factor: float = 0.85

    # -- self-similarity veto (the repetitive-texture false-positive gate) ---
    # A genuine copy-move has ONE dominant translation. Periodic/self-similar
    # texture (gel lanes, tiled sub-panels, repeated blot bands) instead
    # produces SEVERAL competing shift-vector peaks of comparable strength.
    # If a peak that is NOT a spillover neighbour of the winner reaches a
    # comparable support, the content is repetitive, not a localized
    # duplication -> veto. This complements the residual gate, which can only
    # damp (not reject) on the smooth/compressed blocks this tier targets.
    max_secondary_ratio: float = 0.5   # rival/winner support above this -> veto
    secondary_min_frac: float = 0.5    # a rival must itself reach this*min_support


_ZIGZAG_CACHE: dict = {}
_KERNEL_CACHE: dict = {}


def _zigzag_coords(block: int, n: int) -> list[tuple[int, int]]:
    """The first ``n`` (u, v) DCT frequency pairs in zigzag order."""
    key = (block, n)
    if key not in _ZIGZAG_CACHE:
        coords = sorted(((r, c) for r in range(block) for c in range(block)),
                        key=lambda rc: (rc[0] + rc[1],
                                        rc[1] if (rc[0] + rc[1]) % 2 else rc[0]))
        _ZIGZAG_CACHE[key] = coords[:n]
    return _ZIGZAG_CACHE[key]


def _dct_kernels(block: int, n: int) -> list[np.ndarray]:
    """Separable DCT-II basis kernels for the first ``n`` zigzag frequencies.

    Each kernel, cross-correlated with the image (filter2D, anchor at the
    top-left), yields that DCT coefficient for the block starting at every
    pixel — a fully vectorised replacement for a per-block ``cv2.dct`` loop,
    which lets us use a tiny stride (so arbitrary copy offsets are caught).
    """
    key = (block, n)
    if key in _KERNEL_CACHE:
        return _KERNEL_CACHE[key]
    b = block
    idx = np.arange(b)

    def basis(u):
        c = np.sqrt((1.0 if u == 0 else 2.0) / b)
        return c * np.cos((2 * idx + 1) * u * np.pi / (2 * b))

    kernels = [np.outer(basis(u), basis(v)).astype(np.float32)
               for u, v in _zigzag_coords(b, n)]
    _KERNEL_CACHE[key] = kernels
    return kernels


def detect_dense_copy_move(gray: np.ndarray, cfg: DenseCMFDConfig | None = None,
                           analysis_mask: np.ndarray | None = None) -> dict:
    """Detect translate-and-paste duplication on (smooth) content.

    Returns ``{"forged", "confidence", "mask", "n_support", "offset"}`` where
    ``mask`` is image-sized (uint8 0/255) and ``offset`` is the recovered
    (dx, dy) shift of the dominant duplication (or None).
    """
    cfg = cfg or DenseCMFDConfig()
    g = gray if gray.ndim == 2 else cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    h0, w0 = g.shape
    scale = 1.0
    if max(h0, w0) > cfg.max_dim:
        scale = cfg.max_dim / max(h0, w0)
        g = cv2.resize(g, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)
    if analysis_mask is not None and analysis_mask.shape != g.shape:
        analysis_mask = cv2.resize(analysis_mask, (g.shape[1], g.shape[0]),
                                   interpolation=cv2.INTER_NEAREST)

    h, w = g.shape
    b, step = cfg.block, cfg.step
    if h < b * 2 or w < b * 2:
        return _empty(gray.shape)

    gf = g.astype(np.float32)

    # Vectorised block DCT: one filter2D per kept coefficient -> coeff maps.
    anchor = (0, 0)
    coeff_maps = [cv2.filter2D(gf, cv2.CV_32F, k, anchor=anchor,
                               borderType=cv2.BORDER_REFLECT)
                  for k in _dct_kernels(b, cfg.n_dct)]
    feat_map = np.stack(coeff_maps, axis=-1)                     # (h, w, n_dct)

    # Per-block std (vectorised) for the flat-region gate.
    ksz = (b, b)
    mu = cv2.blur(gf, ksz, anchor=anchor, borderType=cv2.BORDER_REFLECT)
    mu2 = cv2.blur(gf * gf, ksz, anchor=anchor, borderType=cv2.BORDER_REFLECT)
    std_map = np.sqrt(np.clip(mu2 - mu * mu, 0, None))

    ys = np.arange(0, h - b + 1, step)
    xs = np.arange(0, w - b + 1, step)
    gy, gx = np.meshgrid(ys, xs, indexing="ij")
    gy, gx = gy.ravel(), gx.ravel()
    keep = std_map[gy, gx] >= cfg.min_local_std
    if analysis_mask is not None:
        keep &= analysis_mask[gy, gx] > 127
    gy, gx = gy[keep], gx[keep]
    if len(gy) < cfg.min_support:
        return _empty(gray.shape)

    feats = np.round(feat_map[gy, gx] / cfg.quant).astype(np.float32)
    positions = np.stack([gx, gy], axis=1).astype(np.int32)

    # Lexicographic sort so identical/near-identical blocks become adjacent.
    order = np.lexsort(feats.T[::-1])
    feats_s, pos_s = feats[order], positions[order]

    # Compare each block to a few sorted neighbours; collect consistent shifts.
    offsets: dict[tuple[int, int], list[int]] = {}
    tol = cfg.offset_tol
    for i in range(len(feats_s)):
        for j in range(i + 1, min(i + 1 + cfg.sort_window, len(feats_s))):
            if np.linalg.norm(feats_s[i] - feats_s[j]) > cfg.feat_max_dist:
                continue
            dx = int(pos_s[j][0] - pos_s[i][0])
            dy = int(pos_s[j][1] - pos_s[i][1])
            if (dx * dx + dy * dy) ** 0.5 < cfg.min_offset:
                continue
            if dx < 0 or (dx == 0 and dy < 0):   # canonical direction
                dx, dy = -dx, -dy
            key = (round(dx / tol) * tol, round(dy / tol) * tol)
            offsets.setdefault(key, []).append(i)

    if not offsets:
        return _empty(gray.shape)
    best_key = max(offsets, key=lambda k: len(offsets[k]))
    support_idx = offsets[best_key]
    n_support = len(support_idx)
    if n_support < cfg.min_support:
        return _empty(gray.shape)

    # Self-similarity veto: compare the winning peak to the strongest rival
    # that is NOT just a spillover neighbour of the winner (a single true
    # offset can smear across a couple of adjacent tol-bins). A comparable
    # non-adjacent rival is the signature of repetitive texture, not a copy.
    bx, by = best_key
    adj2 = (2 * b) ** 2
    rivals = [len(v) for k, v in offsets.items()
              if (k[0] - bx) ** 2 + (k[1] - by) ** 2 > adj2]
    second = max(rivals) if rivals else 0
    if (second >= cfg.secondary_min_frac * cfg.min_support
            and second > cfg.max_secondary_ratio * n_support):
        return _empty(gray.shape)

    # Build a mask from the supporting blocks (both ends of each shift). Track
    # the duplicate (shifted-in) side separately: the residual clone test must
    # correlate the DUPLICATE content against its source, not the whole union.
    mask = np.zeros((h, w), np.uint8)
    dup_mask = np.zeros((h, w), np.uint8)
    dx, dy = best_key
    for i in support_idx:
        x, y = pos_s[i]
        mask[y:y + b, x:x + b] = 255
        x2, y2 = x + dx, y + dy
        if 0 <= x2 <= w - b and 0 <= y2 <= h - b:
            mask[y2:y2 + b, x2:x2 + b] = 255
            dup_mask[y2:y2 + b, x2:x2 + b] = 255

    # ZNCC confirmation: the region shifted by (dx,dy) must actually correlate.
    zncc = _shift_zncc(gf, dx, dy, mask)
    if zncc < cfg.zncc_min:
        return _empty(gray.shape)

    # Noise-residual confirmation — the dense-tier false-positive gate.
    # Shifting the image by (dx,dy) lands the SOURCE content onto the duplicate
    # blocks, so over `dup_mask` the reference is the duplicate and the shifted
    # frame is its source: their noise residuals are correlated iff this is a
    # real pixel copy. An INDEPENDENT verdict means legitimate self-similar
    # texture -> veto; INCONCLUSIVE (smooth/compressed) only damps.
    noise_factor = 1.0
    residual = {"verdict": "not run"}
    if cfg.require_residual_confirm and cv2.countNonZero(dup_mask) > 0:
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        shifted = cv2.warpAffine(gf, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        residual = residual_clone_test(gf, shifted, dup_mask)
        if residual["verdict"] == INDEPENDENT:
            return _empty(gray.shape)   # honest look-alike, not a duplication
        noise_factor = clone_factor(
            residual,
            independent_factor=cfg.residual_independent_factor,
            inconclusive_factor=cfg.residual_inconclusive_factor)

    # Confidence: support above the floor, gated by correlation quality and the
    # noise-residual verdict.
    surprise = min(1.0, (n_support - cfg.min_support) / (3.0 * cfg.min_support) + 0.34)
    confidence = float(np.clip(surprise * max(zncc, 0.0) * noise_factor, 0.0, 1.0))

    if scale != 1.0:  # back to original resolution
        mask = cv2.resize(mask, (gray.shape[1], gray.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    return {
        "forged": bool(confidence >= 0.45),
        "confidence": round(confidence, 4),
        "mask": mask,
        "n_support": n_support,
        "offset": (int(dx / max(scale, 1e-9)), int(dy / max(scale, 1e-9))),
        "mean_zncc": round(float(zncc), 4),
        "residual_verdict": residual.get("verdict"),
    }


def _shift_zncc(gf: np.ndarray, dx: int, dy: int, mask: np.ndarray) -> float:
    """Mean ZNCC between the image and itself shifted by (dx,dy), over the mask."""
    h, w = gf.shape
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    shifted = cv2.warpAffine(gf, M, (w, h), borderMode=cv2.BORDER_REFLECT)
    m = mask > 0
    a, b_ = gf[m], shifted[m]
    if a.size < 16:
        return 0.0
    a = a - a.mean()
    b_ = b_ - b_.mean()
    denom = (np.sqrt((a * a).sum() * (b_ * b_).sum())) + 1e-6
    return float((a * b_).sum() / denom)


def _empty(shape) -> dict:
    return {"forged": False, "confidence": 0.0,
            "mask": np.zeros(shape[:2], np.uint8), "n_support": 0,
            "offset": None, "mean_zncc": 0.0, "residual_verdict": None}

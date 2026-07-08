"""Check whether a figure's written claims match what the figure shows.

Compares the structured claims from :mod:`src.nlp.claim_extractor` against:

  (a) **Visual heuristics** — an *approximate* count of distinct visual
      elements (lanes / bands / blobs) via classical CV. This is deliberately
      coarse: it is a screening signal to flag figures for human review, NOT a
      precise measurement. It is the weakest link in the pipeline (see README)
      and never on its own "proves" a mismatch.

  (b) **Prior detector flags** — if Stage 2/3/4 already flagged the figure as
      copy-move forged, cross-figure reused, or AI-generated, that raises the
      prior that the text and image disagree, and is folded into the score.

``check_consistency`` returns ``{"consistent", "mismatches", "confidence"}``.
"""

from __future__ import annotations

import cv2
import numpy as np

from src.utils.image_io import load_image

# A claimed vs. observed panel count is only flagged when they differ by more
# than this fraction — the heuristic count is noisy, so we require a clear gap.
PANEL_COUNT_TOLERANCE = 0.5   # e.g. claim 12, observe <6 or >18 -> flag
MIN_ELEMENTS_FOR_CHECK = 2    # too few detected -> heuristic unreliable, skip


def count_visual_elements(image_path: str) -> dict:
    """Approximate the number of distinct visual elements in a figure.

    Two coarse, classical-CV estimates (documented as approximate):

    * ``blob_count`` — connected dark components after Otsu threshold +
      morphology (bands, spots, blobs).
    * ``lane_count`` — peaks in the vertical intensity projection (lanes in a
      gel/blot are regularly-spaced dark columns).

    Returns both plus a ``best_estimate`` (the larger of the two, since a lane
    usually contains at least one band). These are screening numbers only.
    """
    image = load_image(image_path, grayscale=True)
    h, w = image.shape

    # --- blob count: dark connected components -----------------------------
    blur = cv2.GaussianBlur(image, (3, 3), 0)
    _, binary = cv2.threshold(blur, 0, 255,
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    min_area = max(20, (h * w) // 2000)  # ignore speckle
    blob_count = int(sum(1 for i in range(1, n_labels)
                         if stats[i, cv2.CC_STAT_AREA] >= min_area))

    # --- lane count: peaks in the column intensity projection --------------
    # Dark lanes -> low mean intensity columns. Invert so lanes are peaks, then
    # smooth heavily so per-pixel sensor noise doesn't create spurious peaks.
    col_profile = (255.0 - image.mean(axis=0)).astype(np.float32)
    sigma = max(2.0, w / 80.0)
    col_profile = cv2.GaussianBlur(col_profile.reshape(1, -1), (0, 0),
                                   sigmaX=sigma).ravel()
    lane_count = _count_peaks(col_profile, min_separation=max(8, w // 30))

    # best_estimate: the two heuristics measure the same thing (distinct dark
    # elements) different ways. When they roughly agree, average; when they
    # diverge, trust the connected-component count (blob_count) — the lane
    # projection is the noisier of the two. Never take a blind max, which would
    # let a spurious lane peak mask a real "fewer elements than claimed" gap.
    if max(blob_count, lane_count) <= 1:
        best = max(blob_count, lane_count)
    elif abs(blob_count - lane_count) <= 0.5 * max(blob_count, lane_count):
        best = int(round((blob_count + lane_count) / 2))
    else:
        best = blob_count

    return {
        "blob_count": blob_count,
        "lane_count": lane_count,
        "best_estimate": int(best),
        "note": "approximate CV heuristic - for screening, not measurement",
    }


def _count_peaks(profile: np.ndarray, min_separation: int) -> int:
    """Count prominent local maxima in a 1-D profile (simple, robust)."""
    if profile.size < 3:
        return 0
    threshold = profile.mean() + 0.5 * profile.std()
    peaks = []
    for i in range(1, len(profile) - 1):
        if (profile[i] > threshold and profile[i] >= profile[i - 1]
                and profile[i] > profile[i + 1]):
            if not peaks or (i - peaks[-1]) >= min_separation:
                peaks.append(i)
    return len(peaks)


def check_consistency(
    claims: dict,
    figure_image_path: str | None,
    prior_detector_flags: dict | None = None,
    visual_elements: dict | None = None,
) -> dict:
    """Compare a figure's claims against its pixels + prior detector flags.

    Args:
        claims: structured claims (see claim_extractor). Missing keys tolerated.
        figure_image_path: path to the figure image (may be None).
        prior_detector_flags: optional
            ``{"copy_move_forged": bool, "cross_figure_reused": bool,
               "ai_generated": bool}`` from Stages 2/3/4.
        visual_elements: optional precomputed count_visual_elements() result
            (so the orchestrator doesn't run the CV twice).

    Returns ``{"consistent": bool, "mismatches": list[str], "confidence": float}``
    where ``confidence`` is how confident we are that a *problem exists*
    (0 = looks consistent, 1 = strong text/image disagreement).
    """
    mismatches: list[str] = []
    signals: list[float] = []
    prior_detector_flags = prior_detector_flags or {}

    # ---- (a) claimed count vs. observed visual element count --------------
    claimed_count = claims.get("claimed_panel_count")
    if claimed_count and figure_image_path:
        if visual_elements is None:
            visual_elements = count_visual_elements(figure_image_path)
        observed = visual_elements["best_estimate"]
        if observed >= MIN_ELEMENTS_FOR_CHECK:
            lo = claimed_count * (1 - PANEL_COUNT_TOLERANCE)
            hi = claimed_count * (1 + PANEL_COUNT_TOLERANCE)
            if not (lo <= observed <= hi):
                kind = claims.get("panel_count_kind") or "elements"
                mismatches.append(
                    f"text states {claimed_count} {kind}, but the figure "
                    f"appears to show ~{observed} distinct elements "
                    f"(approximate count — needs human review)"
                )
                # Larger relative gap -> stronger signal.
                gap = abs(observed - claimed_count) / max(claimed_count, 1)
                signals.append(min(gap, 1.0))

    # ---- claimed n vs. claimed panel count internal coherence -------------
    claimed_n = claims.get("claimed_n")
    if claimed_n and claimed_count and claimed_n < claimed_count:
        mismatches.append(
            f"text reports n={claimed_n} but describes {claimed_count} "
            f"{claims.get('panel_count_kind') or 'conditions'} — more shown "
            f"than the stated sample size"
        )
        signals.append(0.5)

    # ---- (b) prior image-forensics flags as a strong prior ----------------
    flag_reasons = {
        "copy_move_forged": "Stage 2 flagged duplicated regions WITHIN this figure",
        "cross_figure_reused": "Stage 3 flagged this figure as reused from "
                               "another figure",
        "ai_generated": "Stage 4 flagged this figure as likely AI-generated",
    }
    for flag, reason in flag_reasons.items():
        if prior_detector_flags.get(flag):
            mismatches.append(reason + " — a strong prior for text/image mismatch")
            signals.append(0.8)

    # ---- combine ----------------------------------------------------------
    confidence = float(min(1.0, max(signals))) if signals else 0.0
    # If several independent signals fire, nudge confidence up (capped).
    if len(signals) > 1:
        confidence = float(min(1.0, confidence + 0.1 * (len(signals) - 1)))

    return {
        "consistent": len(mismatches) == 0,
        "mismatches": mismatches,
        "confidence": round(confidence, 4),
        "visual_elements": visual_elements,
    }

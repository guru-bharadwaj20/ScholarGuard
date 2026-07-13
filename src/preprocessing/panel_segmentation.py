"""Panel segmentation + content-type gating for scientific figures.

Why this module exists (the core false-positive fix)
-----------------------------------------------------
Scientific figures are collages: continuous-tone imagery (blots, gels,
micrographs) sits next to vector graphics (line plots, bar charts,
diagrams), text labels, and scale bars. The forensic detectors ask "is
this region duplicated?", but duplication is only *suspicious* in
continuous-tone imagery — repeated axis labels, tiled plot markers,
identical scale bars and repeated text are how legitimate figures are
built. Running copy-move/cross-figure matching over the whole composite
is what drove the measured 56.6% copy-move false-alarm rate on real
papers.

This module produces an **analysis mask**: 255 where forensic pixel
analysis is meaningful (continuous-tone panels, minus text and scale
bars), 0 elsewhere. Detectors drop keypoints/regions outside the mask.

Three stages, all classical CV (CPU, training-free):

1. **Recursive X-Y cut** — split the figure at uniform gutter bands
   (rows/columns whose intensity is near-constant across the full span),
   the standard document-layout decomposition. Panels are axis-aligned
   boxes; nested layouts are handled by recursion.
2. **Panel content classification** — each panel is typed as
   ``continuous_tone`` / ``graphics`` / ``text`` / ``blank`` from
   grayscale statistics (see :func:`classify_region`). The rules are
   deliberately biased toward ``continuous_tone`` (a misclassified blot
   would silently disable fraud detection on it, which is worse than a
   few extra graphics pixels staying in the mask).
3. **Text + scale-bar masking** — a morphological-gradient text detector
   (gradient -> Otsu -> horizontal closing -> component shape filter)
   plus a thin-solid-bar detector, subtracted from the mask.

Everything is heuristic and documented as such; the point is not perfect
segmentation but removing the *systematic* legitimate-repetition sources
from the forensic detectors' field of view.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

# Panel content types.
CONTINUOUS_TONE = "continuous_tone"
GRAPHICS = "graphics"
TEXT = "text"
BLANK = "blank"


@dataclass
class PanelSegConfig:
    """Knobs for segmentation, classification and masking."""

    # -- X-Y cut ------------------------------------------------------------
    gutter_std_max: float = 4.0     # a row/col with std below this is "uniform"
    gutter_min_frac: float = 0.012  # gutter band must be >= this fraction of dim
    min_panel_frac: float = 0.05    # panels smaller than this fraction of a dim stop recursion
    max_depth: int = 4              # recursion depth cap

    # -- classification (see classify_region for the rationale) --------------
    # Fraction of pixels OUTSIDE the two dominant intensity bins. Vector
    # graphics are dominated by background + one ink tone (low tone fraction);
    # photographs spread across many levels (high tone fraction).
    graphics_tone_frac_max: float = 0.22
    continuous_tone_frac_min: float = 0.45
    # Fraction of pixels whose local (5x5) std exceeds ~1.5 gray levels —
    # photographs are textured almost everywhere, graphics only at edges.
    textured_frac_min: float = 0.30
    blank_std_max: float = 2.0      # panel std below this is blank

    # -- text detection -------------------------------------------------------
    text_min_height: int = 5        # px; component height bounds for text lines
    text_max_height_frac: float = 0.08  # relative to image height
    text_min_aspect: float = 1.2    # text lines are wider than tall
    text_max_aspect: float = 40.0
    text_dilate_px: int = 2         # safety margin around detected text

    # -- scale-bar detection --------------------------------------------------
    bar_max_thickness: int = 8
    bar_min_length: int = 30
    bar_solid_min: float = 0.85     # fill ratio of the component's bbox


@dataclass
class Panel:
    """One segmented panel: bbox in image coords + content type + stats."""

    bbox: tuple[int, int, int, int]   # (x, y, w, h)
    kind: str                         # continuous_tone | graphics | text | blank
    stats: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# 1. Recursive X-Y cut on uniform gutters
# --------------------------------------------------------------------------
def _uniform_runs(stds: np.ndarray, means: np.ndarray, std_max: float,
                  min_len: int) -> list[tuple[int, int]]:
    """Runs of consecutive uniform lines (std < std_max) at least min_len long.

    Uniformity alone qualifies a gutter — the background may be white,
    black, or gray; what matters is that the band is featureless across
    the whole span.
    """
    uniform = stds < std_max
    runs: list[tuple[int, int]] = []
    start = None
    for i, flag in enumerate(uniform):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if i - start >= min_len:
                runs.append((start, i))
            start = None
    if start is not None and len(uniform) - start >= min_len:
        runs.append((start, len(uniform)))
    _ = means  # reserved for future background-color checks
    return runs


def _split_positions(runs: list[tuple[int, int]], span: int,
                     min_panel: int) -> list[int]:
    """Centers of interior gutter runs that leave both children big enough."""
    cuts = []
    for start, end in runs:
        if start <= 0 or end >= span:      # border margin, not a divider
            continue
        center = (start + end) // 2
        if center >= min_panel and span - center >= min_panel:
            cuts.append(center)
    return cuts


def segment_panels(image: np.ndarray,
                   config: PanelSegConfig | None = None) -> list[Panel]:
    """Segment a figure into content-typed panels via recursive X-Y cuts.

    Returns at least one Panel (the whole image, when no gutter is found).
    """
    cfg = config or PanelSegConfig()
    gray = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if image.ndim == 3 else image).astype(np.float32)
    h, w = gray.shape
    panels: list[Panel] = []

    def recurse(x0: int, y0: int, x1: int, y1: int, depth: int) -> None:
        sub = gray[y0:y1, x0:x1]
        sh, sw = sub.shape
        if sh == 0 or sw == 0:
            return
        if depth < cfg.max_depth and min(sh, sw) > 2:
            row_stds, row_means = sub.std(axis=1), sub.mean(axis=1)
            col_stds, col_means = sub.std(axis=0), sub.mean(axis=0)
            h_runs = _uniform_runs(row_stds, row_means, cfg.gutter_std_max,
                                   max(2, int(cfg.gutter_min_frac * sh)))
            v_runs = _uniform_runs(col_stds, col_means, cfg.gutter_std_max,
                                   max(2, int(cfg.gutter_min_frac * sw)))
            h_cuts = _split_positions(h_runs, sh, max(8, int(cfg.min_panel_frac * sh)))
            v_cuts = _split_positions(v_runs, sw, max(8, int(cfg.min_panel_frac * sw)))
            # Cut along the direction with more/wider gutters first.
            if h_cuts or v_cuts:
                if len(h_cuts) >= len(v_cuts):
                    edges = [0, *h_cuts, sh]
                    for a, b in zip(edges[:-1], edges[1:]):
                        recurse(x0, y0 + a, x1, y0 + b, depth + 1)
                else:
                    edges = [0, *v_cuts, sw]
                    for a, b in zip(edges[:-1], edges[1:]):
                        recurse(x0 + a, y0, x0 + b, y1, depth + 1)
                return
        kind, stats = classify_region(sub, cfg)
        panels.append(Panel(bbox=(x0, y0, x1 - x0, y1 - y0), kind=kind,
                            stats=stats))

    recurse(0, 0, w, h, 0)
    return panels


# --------------------------------------------------------------------------
# 2. Panel content classification
# --------------------------------------------------------------------------
def classify_region(gray: np.ndarray,
                    config: PanelSegConfig | None = None) -> tuple[str, dict]:
    """Type a grayscale region as continuous-tone / graphics / text / blank.

    Statistics used (all cheap, all interpretable):

    * ``tone_frac``    — fraction of pixels outside the two dominant intensity
      bins. Vector graphics are background + ink (near 0); photographs and
      blots spread energy across many levels (high).
    * ``textured_frac``— fraction of pixels with local 5x5 std > 1.5 gray
      levels. Sensor-captured content is textured *everywhere* (noise,
      gradients); graphics are flat except at strokes.
    * ``n_levels``     — number of intensity bins holding >0.05% of pixels.

    The decision is biased toward ``continuous_tone``: gating a blot out of
    the forensic mask silently disables fraud detection there, which is a
    worse failure than leaving some graphics pixels in.
    """
    cfg = config or PanelSegConfig()
    g = gray.astype(np.float32)
    n = g.size
    if n == 0:
        return BLANK, {}
    if float(g.std()) < cfg.blank_std_max:
        return BLANK, {"std": float(g.std())}

    hist = np.bincount(np.clip(g, 0, 255).astype(np.uint8).ravel(),
                       minlength=256).astype(np.float64)
    top2 = float(np.sort(hist)[-2:].sum() / n)
    tone_frac = 1.0 - top2
    n_levels = int((hist > 0.0005 * n).sum())

    mu = cv2.blur(g, (5, 5))
    var = np.clip(cv2.blur(g * g, (5, 5)) - mu * mu, 0, None)
    textured_frac = float((np.sqrt(var) > 1.5).mean())

    stats = {"tone_frac": round(tone_frac, 4), "n_levels": n_levels,
             "textured_frac": round(textured_frac, 4)}

    if tone_frac >= cfg.continuous_tone_frac_min:
        return CONTINUOUS_TONE, stats
    if tone_frac <= cfg.graphics_tone_frac_max and n_levels < 60:
        # Flat two-tone region: line art or text. Distinguish by whether the
        # ink is organized into small text-line-shaped components.
        kind = TEXT if _looks_like_text(g, cfg) else GRAPHICS
        return kind, stats
    # Ambiguous middle ground: JPEG-compressed graphics gain levels, small
    # or noisy photos lose them. Texture coverage is the tiebreaker, biased
    # toward continuous_tone (see docstring).
    if textured_frac >= cfg.textured_frac_min:
        return CONTINUOUS_TONE, stats
    return GRAPHICS, stats


def _looks_like_text(gray: np.ndarray, cfg: PanelSegConfig) -> bool:
    """True when a two-tone region's ink forms mostly text-line components."""
    mask = text_mask(gray, cfg, dilate=False)
    ink = _ink_mask(gray)
    ink_px = int(cv2.countNonZero(ink))
    if ink_px == 0:
        return False
    covered = int(cv2.countNonZero(cv2.bitwise_and(mask, ink)))
    return covered / ink_px > 0.5


# --------------------------------------------------------------------------
# 3. Text + scale-bar masking
# --------------------------------------------------------------------------
def _ink_mask(gray: np.ndarray) -> np.ndarray:
    """Foreground 'ink' (dark-on-light or light-on-dark) via Otsu."""
    g8 = np.clip(gray, 0, 255).astype(np.uint8)
    _, bw = cv2.threshold(g8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Ink is whichever side is the minority.
    if cv2.countNonZero(bw) > bw.size // 2:
        bw = cv2.bitwise_not(bw)
    return bw


def text_mask(gray: np.ndarray, config: PanelSegConfig | None = None,
              dilate: bool = True) -> np.ndarray:
    """Binary mask (255) over likely text regions.

    Classic morphological text detection: intensity gradient -> Otsu ->
    horizontal closing (merges characters into line blobs) -> keep
    components with text-line geometry (bounded height, wide aspect,
    reasonably dense). Handles horizontal labels/captions/axis text; a
    rotated y-axis label may be missed — acceptable, since text masking is
    a false-positive reducer, not a guarantee.
    """
    cfg = config or PanelSegConfig()
    g8 = np.clip(gray, 0, 255).astype(np.uint8)
    h, w = g8.shape
    if h < 8 or w < 8:
        return np.zeros_like(g8)

    grad = cv2.morphologyEx(g8, cv2.MORPH_GRADIENT,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Pre-closing character components: a real text line is made of MANY small
    # letter-sized blobs sitting side by side; a solid blot band or a filled
    # marker is one big blob. Counting characters per line is what separates
    # text from figure content (a band's shape alone can pass the geometry
    # filter, which over-masked real blots before this check was added).
    n_char, char_labels, char_stats, _ = cv2.connectedComponentsWithStats(bw, 8)

    # Merge adjacent characters into word/line blobs.
    join = cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, w // 60), 1))
    joined = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, join)

    max_height = max(cfg.text_min_height + 1, int(cfg.text_max_height_frac * h))
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    out = np.zeros_like(g8)
    for i in range(1, n_labels):
        x, y, bw_, bh, area = stats[i]
        if not (cfg.text_min_height <= bh <= max_height):
            continue
        aspect = bw_ / max(bh, 1)
        if not (cfg.text_min_aspect <= aspect <= cfg.text_max_aspect):
            continue
        if area < 0.18 * bw_ * bh:   # too sparse to be a text line
            continue
        # Require several small character-sized components inside this line
        # box — the signature of text, absent in solid bands/markers.
        comp = char_labels[y:y + bh, x:x + bw_]
        ids = [c for c in np.unique(comp) if c != 0]
        small = sum(1 for c in ids
                    if char_stats[c, cv2.CC_STAT_HEIGHT] <= 1.3 * bh
                    and char_stats[c, cv2.CC_STAT_WIDTH] <= 1.5 * bh)
        if small < 3:
            continue
        out[labels == i] = 255
    if dilate and cfg.text_dilate_px > 0:
        k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (2 * cfg.text_dilate_px + 1, 2 * cfg.text_dilate_px + 1))
        out = cv2.dilate(out, k)
    return out


def scale_bar_mask(gray: np.ndarray,
                   config: PanelSegConfig | None = None) -> np.ndarray:
    """Binary mask over thin, solid, elongated bars (scale bars, rules)."""
    cfg = config or PanelSegConfig()
    ink = _ink_mask(gray)
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    out = np.zeros_like(ink)
    for i in range(1, n_labels):
        x, y, w_, h_, area = stats[i]
        thin_horiz = h_ <= cfg.bar_max_thickness and w_ >= cfg.bar_min_length
        thin_vert = w_ <= cfg.bar_max_thickness and h_ >= cfg.bar_min_length
        if not (thin_horiz or thin_vert):
            continue
        if area < cfg.bar_solid_min * w_ * h_:  # not solid — a line of dots/text
            continue
        out[labels == i] = 255
    return cv2.dilate(out, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))


# --------------------------------------------------------------------------
# The one call detectors use
# --------------------------------------------------------------------------
def build_analysis_mask(
    image: np.ndarray, config: PanelSegConfig | None = None,
) -> tuple[np.ndarray, list[Panel]]:
    """255 where forensic pixel analysis is meaningful, 0 elsewhere.

    continuous-tone panels, minus detected text and scale bars. Also
    returns the panel list so callers can report *why* an area was gated.
    """
    cfg = config or PanelSegConfig()
    gray = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if image.ndim == 3 else image)
    panels = segment_panels(gray, cfg)
    mask = np.zeros(gray.shape[:2], np.uint8)
    for panel in panels:
        if panel.kind != CONTINUOUS_TONE:
            continue
        x, y, w, h = panel.bbox
        sub = gray[y:y + h, x:x + w]
        region = np.full((h, w), 255, np.uint8)
        region[text_mask(sub, cfg) > 0] = 0
        region[scale_bar_mask(sub, cfg) > 0] = 0
        mask[y:y + h, x:x + w] = region
    return mask, panels


def content_entropy(gray: np.ndarray) -> float:
    """Shannon entropy (bits) of the intensity histogram.

    Publisher furniture (logos, license badges, solid rules) is
    low-entropy; real figure content is not. Used as a cheap junk filter.
    """
    hist = np.bincount(np.clip(gray, 0, 255).astype(np.uint8).ravel(),
                       minlength=256).astype(np.float64)
    p = hist / max(hist.sum(), 1.0)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())

"""Visualization helpers: overlays, heatmaps and side-by-side comparisons.

All functions take/return BGR uint8 images (OpenCV convention) so results
can be written straight to disk with ``cv2.imwrite`` / ``save_image``.
"""

from __future__ import annotations

import cv2
import numpy as np

from src.utils.image_io import save_image

# BGR colors
COLOR_SOURCE = (0, 200, 0)      # green  — suspected source region
COLOR_DUPLICATE = (0, 0, 220)   # red    — suspected duplicated region
COLOR_MASK = (0, 140, 255)      # orange — generic mask overlay
COLOR_LINK = (0, 220, 220)      # yellow — source->duplicate link line


def overlay_mask(
    image: np.ndarray,
    mask: np.ndarray,
    color: tuple[int, int, int] = COLOR_MASK,
    alpha: float = 0.45,
) -> np.ndarray:
    """Blend a colored translucent overlay onto the image where mask > 0."""
    out = image.copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    if mask is None or not mask.any():
        return out
    color_layer = np.zeros_like(out)
    color_layer[:] = color
    region = mask > 0
    out[region] = cv2.addWeighted(out, 1 - alpha, color_layer, alpha, 0)[region]
    return out


def draw_detection(
    image: np.ndarray, mask: np.ndarray, regions: list[dict]
) -> np.ndarray:
    """Render the detector's full output on top of the original image.

    Draws the translucent mask, a green box on each source region, a red
    box on each duplicated region, and a line linking the two centers.
    """
    out = overlay_mask(image, mask)
    for region in regions:
        sx, sy, sw, sh = region["source_bbox"]
        dx, dy, dw, dh = region["dup_bbox"]
        cv2.rectangle(out, (sx, sy), (sx + sw, sy + sh), COLOR_SOURCE, 2)
        cv2.rectangle(out, (dx, dy), (dx + dw, dy + dh), COLOR_DUPLICATE, 2)
        src_center = (sx + sw // 2, sy + sh // 2)
        dup_center = (dx + dw // 2, dy + dh // 2)
        cv2.line(out, src_center, dup_center, COLOR_LINK, 1, cv2.LINE_AA)
        cv2.putText(out, "src", (sx, max(12, sy - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_SOURCE, 1, cv2.LINE_AA)
        cv2.putText(out, "dup", (dx, max(12, dy - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_DUPLICATE, 1, cv2.LINE_AA)
    return out


def make_heatmap(score_map: np.ndarray) -> np.ndarray:
    """Turn a float score map (any range) into a JET-colored BGR heatmap."""
    normalized = cv2.normalize(
        score_map.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX
    ).astype(np.uint8)
    return cv2.applyColorMap(normalized, cv2.COLORMAP_JET)


def _labeled_panel(image: np.ndarray, label: str, height: int) -> np.ndarray:
    """Resize a panel to a common height and stamp a label on it."""
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    scale = height / image.shape[0]
    panel = cv2.resize(image, (max(1, int(image.shape[1] * scale)), height))
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 24), (30, 30, 30), -1)
    cv2.putText(panel, label, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    return panel


def side_by_side(
    original: np.ndarray,
    predicted_mask: np.ndarray,
    ground_truth_mask: np.ndarray | None = None,
    height: int = 360,
) -> np.ndarray:
    """Build 'original | predicted mask | ground truth' comparison strip.

    The ground-truth panel is omitted when no ground truth is available.
    """
    panels = [
        _labeled_panel(original, "original", height),
        _labeled_panel(overlay_mask(original, predicted_mask, COLOR_DUPLICATE),
                       "predicted", height),
    ]
    if ground_truth_mask is not None:
        panels.append(
            _labeled_panel(overlay_mask(original, ground_truth_mask, COLOR_SOURCE),
                           "ground truth", height)
        )
    divider = np.full((height, 3, 3), 255, np.uint8)
    strip = panels[0]
    for panel in panels[1:]:
        strip = np.hstack([strip, divider, panel])
    return strip


def draw_cross_figure_match(
    query_image: np.ndarray,
    matched_image: np.ndarray,
    mask_query: np.ndarray | None = None,
    mask_matched: np.ndarray | None = None,
    bbox_query: tuple | None = None,
    bbox_matched: tuple | None = None,
    height: int = 360,
) -> np.ndarray:
    """Two figures side by side with the reused region highlighted in both.

    Used by the Stage 3 cross-figure detector: the query figure on the
    left, the corpus match on the right, suspected reused regions overlaid
    in red with bounding boxes, and a link line joining the two regions.
    """
    def _prep(image, mask, bbox):
        panel = overlay_mask(image, mask, COLOR_DUPLICATE) if mask is not None \
            else (image.copy() if image.ndim == 3
                  else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))
        center = None
        if bbox is not None:
            x, y, w, h = bbox
            cv2.rectangle(panel, (x, y), (x + w, y + h), COLOR_DUPLICATE, 2)
            center = (x + w // 2, y + h // 2)
        return panel, center

    left, center_l = _prep(query_image, mask_query, bbox_query)
    right, center_r = _prep(matched_image, mask_matched, bbox_matched)
    scale_l = height / left.shape[0]
    scale_r = height / right.shape[0]
    left = _labeled_panel(left, "query", height)
    right = _labeled_panel(right, "match", height)
    divider = np.full((height, 4, 3), 255, np.uint8)
    canvas = np.hstack([left, divider, right])

    if center_l and center_r:
        p1 = (int(center_l[0] * scale_l), int(center_l[1] * scale_l))
        p2 = (left.shape[1] + 4 + int(center_r[0] * scale_r),
              int(center_r[1] * scale_r))
        cv2.line(canvas, p1, p2, COLOR_LINK, 2, cv2.LINE_AA)
    return canvas


def save_side_by_side(
    path: str,
    original: np.ndarray,
    predicted_mask: np.ndarray,
    ground_truth_mask: np.ndarray | None = None,
) -> None:
    """Convenience wrapper: build the comparison strip and write it to disk."""
    save_image(side_by_side(original, predicted_mask, ground_truth_mask), path)

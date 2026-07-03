"""Copy-move forgery detector (Stage 2 core).

Detects regions duplicated *within* a single image using classical CV:

    1. SIFT keypoints/descriptors (ORB fallback) extracted from the image.
    2. Self-matching of descriptors with a ratio test (generalized Lowe test,
       skipping trivial self-matches and spatially-near neighbours).
    3. DBSCAN clustering of matched pairs in (x1, y1, x2, y2) space so that
       only *dense, spatially coherent* groups of matches survive — a real
       copy-move shows many keypoints mapping consistently from one region
       to another, whereas noise matches are scattered.
    4. Per-cluster geometric verification with a RANSAC-estimated partial
       affine transform (rotation + uniform scale + translation).
    5. Region growing: the source region is warped onto the destination by
       the verified transform and a local zero-mean normalized cross
       correlation (ZNCC) map is thresholded to grow the sparse keypoint
       seeds into full pixel masks for both the source and the duplicate.
    6. A confidence score in [0, 1] combining inlier count, RANSAC inlier
       ratio, grown-region area and correlation strength.

Designed to run fast on CPU-only machines (no deep learning). All heavy
per-pixel work is done with vectorized OpenCV/NumPy operations.

CLI usage:
    python -m src.detectors.copy_move_detector \
        --image path/to/figure.png --output outputs/stage2_results/
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field

import cv2
import numpy as np
from sklearn.cluster import DBSCAN

from src.utils.image_io import load_image, save_image, save_mask
from src.utils.visualization import draw_detection


# --------------------------------------------------------------------------
# Tunable parameters, grouped so later stages can tweak them in one place.
# --------------------------------------------------------------------------
@dataclass
class DetectorConfig:
    """All knobs of the copy-move detector."""

    # -- feature extraction -------------------------------------------------
    max_dim: int = 1600           # downscale larger images to this max side (CPU speed)
    max_keypoints: int = 6000     # cap keypoints so matching stays O(fast) on CPU
    # Scientific figures (blots, micrographs, plots) are much smoother than
    # natural photos, so SIFT's default contrast threshold (0.04) finds far
    # too few keypoints. A low threshold harvests weak-texture features; the
    # ratio test + RANSAC downstream remove the extra noise this lets in.
    sift_contrast_threshold: float = 0.008
    sift_edge_threshold: float = 16.0

    # -- self-matching ------------------------------------------------------
    knn_k: int = 8                # neighbours fetched per descriptor for self-matching
    ratio_threshold: float = 0.78 # Lowe ratio: best/next-best distance
    min_pair_distance: float = 24.0  # px; matches closer than this are "same spot" noise

    # -- clustering (DBSCAN over match offset vectors (dx, dy)) -------------
    # All matches of one rigid copy-move share (nearly) the same offset no
    # matter how far apart the keypoints are, so even a copy with only 3-4
    # repeatable keypoints forms a tight offset cluster, while noise
    # matches scatter. Small rotations/scales spread the offsets smoothly,
    # which DBSCAN chains through; large rotations are a known limitation.
    cluster_eps: float = 24.0     # px radius in offset space
    cluster_min_samples: int = 3  # minimum matches to seed a cluster

    # -- geometric verification (RANSAC affine) -----------------------------
    # min_inliers is deliberately low: smooth figures often yield only a
    # handful of repeatable keypoints per copied patch, and the dense ZNCC
    # region-growing stage (which a spurious cluster cannot pass) is the
    # real false-positive gate.
    ransac_reproj_thresh: float = 4.0
    min_inliers: int = 3          # clusters with fewer verified inliers are rejected
    min_scale: float = 0.33       # sanity bounds on the recovered uniform scale
    max_scale: float = 3.0

    # -- region growing -----------------------------------------------------
    zncc_window: int = 9          # window (px) for local correlation
    zncc_threshold: float = 0.72  # correlation needed to accept a pixel as duplicated
    min_local_std: float = 2.0    # pixels flatter than this can't vote (ZNCC unstable)
    seed_radius: int = 14         # px stamped around each inlier keypoint
    min_region_area: int = 250    # px^2; smaller grown regions are discarded

    # -- decision -----------------------------------------------------------
    confidence_threshold: float = 0.45  # >= this => forged


@dataclass
class _VerifiedCluster:
    """Internal: one geometrically verified copy-move candidate."""

    src_pts: np.ndarray           # (N, 2) inlier source keypoint coords
    dst_pts: np.ndarray           # (N, 2) inlier destination keypoint coords
    transform: np.ndarray         # 2x3 partial affine mapping src -> dst
    inlier_ratio: float
    kp_sizes: np.ndarray = field(default_factory=lambda: np.array([]))


class CopyMoveDetector:
    """Reusable detector object. Later stages can subclass or re-configure."""

    def __init__(self, config: DetectorConfig | None = None):
        self.config = config or DetectorConfig()
        self._feature, self._norm = self._build_feature_extractor(self.config)

    # ------------------------------------------------------------------ API
    def detect(self, image: np.ndarray) -> dict:
        """Run the full pipeline on a BGR or grayscale image array.

        Returns the result dict described in :func:`detect_copy_move`.
        """
        cfg = self.config
        bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        orig_h, orig_w = bgr.shape[:2]

        # Work at a bounded resolution for speed; remember the scale so the
        # final mask can be resized back to the original image dimensions.
        work, scale = self._maybe_downscale(bgr)
        gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)

        keypoints, descriptors = self._extract_features(gray)
        matches = self._self_match(keypoints, descriptors, gray.shape)
        clusters = self._cluster_and_verify(matches, keypoints)

        mask, labeled_mask, regions, grow_stats = self._grow_regions(gray, clusters)
        confidence = self._score(clusters, mask, gray, grow_stats)
        forged = bool(confidence >= cfg.confidence_threshold and len(regions) > 0)

        # Rescale outputs back to the original resolution if we downscaled.
        if scale != 1.0:
            mask = cv2.resize(mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
            labeled_mask = cv2.resize(
                labeled_mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST
            )
            regions = [self._rescale_region(r, 1.0 / scale) for r in regions]

        visualization = draw_detection(bgr, mask, regions)

        return {
            "forged": forged,
            "confidence": float(round(confidence, 4)),
            "mask": mask,
            "labeled_mask": labeled_mask,  # extra: 1 = source, 2 = duplicate
            "regions": regions,
            "visualization": visualization,
        }

    # ------------------------------------------------------- feature stage
    @staticmethod
    def _build_feature_extractor(cfg: DetectorConfig):
        """SIFT is preferred (patent expired, in mainline OpenCV >= 4.4).

        Falls back to ORB if SIFT is unavailable in the installed build.
        Returns (extractor, norm_type_for_matching).
        """
        try:
            sift = cv2.SIFT_create(
                contrastThreshold=cfg.sift_contrast_threshold,
                edgeThreshold=cfg.sift_edge_threshold,
            )
            return sift, cv2.NORM_L2
        except AttributeError:
            return cv2.ORB_create(nfeatures=8000, fastThreshold=5), cv2.NORM_HAMMING

    def _maybe_downscale(self, bgr: np.ndarray) -> tuple[np.ndarray, float]:
        """Downscale so max(side) <= cfg.max_dim. Returns (image, scale)."""
        h, w = bgr.shape[:2]
        longest = max(h, w)
        if longest <= self.config.max_dim:
            return bgr, 1.0
        scale = self.config.max_dim / longest
        resized = cv2.resize(bgr, (int(w * scale), int(h * scale)),
                             interpolation=cv2.INTER_AREA)
        return resized, scale

    def _extract_features(self, gray: np.ndarray):
        keypoints, descriptors = self._feature.detectAndCompute(gray, None)
        if descriptors is None:
            return [], None
        # Keep only the strongest keypoints — matching is O(N^2)-ish.
        if len(keypoints) > self.config.max_keypoints:
            order = np.argsort([-kp.response for kp in keypoints])
            order = order[: self.config.max_keypoints]
            keypoints = [keypoints[i] for i in order]
            descriptors = descriptors[order]
        return keypoints, descriptors

    def extract_keypoints(self, gray: np.ndarray):
        """Public alias of the feature stage for reuse by other detectors
        (Stage 3 cross-figure matching runs the same SIFT configuration)."""
        return self._extract_features(gray)

    # ------------------------------------------------------ matching stage
    def _self_match(self, keypoints, descriptors, shape) -> list[tuple[int, int]]:
        """Match the image's descriptors against themselves.

        Trivial self-matches (same index / ~zero distance) and matches whose
        endpoints are spatially too close (textured neighbourhoods matching
        their own neighbours) are discarded, then a generalized Lowe ratio
        test keeps only distinctive matches.
        """
        cfg = self.config
        if descriptors is None or len(keypoints) < 2 * cfg.cluster_min_samples:
            return []

        matcher = cv2.BFMatcher(self._norm)
        knn = matcher.knnMatch(descriptors, descriptors, k=min(cfg.knn_k, len(keypoints)))

        pts = np.array([kp.pt for kp in keypoints], dtype=np.float32)
        pairs: set[tuple[int, int]] = set()

        for neighbours in knn:
            # Drop the trivial self-match and keypoints sitting on (almost)
            # the same pixel — SIFT emits multiple orientations per location.
            candidates = []
            for m in neighbours:
                if m.trainIdx == m.queryIdx:
                    continue
                if np.linalg.norm(pts[m.queryIdx] - pts[m.trainIdx]) < cfg.min_pair_distance:
                    continue
                candidates.append(m)
            if len(candidates) < 2:
                continue
            # Lowe ratio test between the best and second-best *valid* match.
            best, second = candidates[0], candidates[1]
            if second.distance <= 1e-9:  # duplicate descriptors; ambiguous
                continue
            if best.distance / second.distance < cfg.ratio_threshold:
                i, j = best.queryIdx, best.trainIdx
                pairs.add((min(i, j), max(i, j)))  # dedupe (i,j)/(j,i)

        return sorted(pairs)

    # ---------------------------------------------- clustering/verification
    def _cluster_and_verify(self, matches, keypoints) -> list[_VerifiedCluster]:
        """DBSCAN the matches in offset space, then RANSAC-verify clusters."""
        cfg = self.config
        if len(matches) < cfg.cluster_min_samples:
            return []

        pts = np.array([kp.pt for kp in keypoints], dtype=np.float32)
        sizes = np.array([kp.size for kp in keypoints], dtype=np.float32)

        # Orient every pair the same way (left-most endpoint first) so that
        # source->dup and dup->source matches land in the same cluster.
        quads = []
        for i, j in matches:
            a, b = pts[i], pts[j]
            if (a[0], a[1]) > (b[0], b[1]):
                a, b = b, a
                i, j = j, i
            quads.append((a[0], a[1], b[0], b[1], i, j))
        quads = np.array(quads, dtype=np.float32)

        # Cluster on the displacement vector of each match: a genuine rigid
        # copy-move gives many matches with (almost) identical offsets.
        offsets = quads[:, 2:4] - quads[:, 0:2]
        labels = DBSCAN(eps=cfg.cluster_eps, min_samples=cfg.cluster_min_samples).fit_predict(
            offsets
        )

        verified: list[_VerifiedCluster] = []
        for label in set(labels) - {-1}:
            members = quads[labels == label]
            # OpenCV needs contiguous Nx2 point arrays, not strided views.
            src = np.ascontiguousarray(members[:, 0:2])
            dst = np.ascontiguousarray(members[:, 2:4])
            if len(src) < max(cfg.cluster_min_samples, 3):
                continue

            transform, inlier_flags = cv2.estimateAffinePartial2D(
                src, dst, method=cv2.RANSAC,
                ransacReprojThreshold=cfg.ransac_reproj_thresh,
            )
            if transform is None or inlier_flags is None:
                continue

            inlier_flags = inlier_flags.ravel().astype(bool)
            n_inliers = int(inlier_flags.sum())
            if n_inliers < cfg.min_inliers:
                continue

            # Sanity checks on the recovered rigid transform: plausible
            # uniform scale, and a real displacement (identity-like
            # transforms are self-matching noise, not a copy-move).
            scale = float(np.hypot(transform[0, 0], transform[0, 1]))
            if not (cfg.min_scale <= scale <= cfg.max_scale):
                continue
            displacement = np.linalg.norm(
                dst[inlier_flags] - src[inlier_flags], axis=1
            ).mean()
            if displacement < cfg.min_pair_distance:
                continue

            kp_idx = members[inlier_flags][:, 4:6].astype(int).ravel()
            verified.append(
                _VerifiedCluster(
                    src_pts=src[inlier_flags],
                    dst_pts=dst[inlier_flags],
                    transform=transform,
                    inlier_ratio=n_inliers / len(src),
                    kp_sizes=sizes[kp_idx],
                )
            )
        return verified

    # ------------------------------------------------- region growing stage
    def _grow_regions(self, gray: np.ndarray, clusters: list[_VerifiedCluster]):
        """Grow sparse verified keypoints into full source/duplicate masks.

        For each verified cluster the whole image is warped by the cluster's
        affine transform so that the source region lands on the duplicate.
        Wherever the warped image locally correlates with the original
        (local ZNCC above threshold) the pixels are duplication candidates;
        connected candidate components that contain a verified keypoint act
        as the grown duplicate region (seeded region growing). The source
        mask is obtained by warping the duplicate mask back through the
        inverse transform.
        """
        cfg = self.config
        h, w = gray.shape
        mask = np.zeros((h, w), np.uint8)
        labeled = np.zeros((h, w), np.uint8)   # 1 = source, 2 = duplicate
        regions: list[dict] = []
        corr_means: list[float] = []

        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        for cluster in clusters:
            # --- seeds: verified inlier keypoints on the destination side --
            seeds = np.zeros((h, w), np.uint8)
            for (x, y), ks in zip(cluster.dst_pts, np.resize(cluster.kp_sizes, len(cluster.dst_pts))):
                radius = int(max(cfg.seed_radius, ks))
                cv2.circle(seeds, (int(round(x)), int(round(y))), radius, 255, -1)

            # --- dense verification: warp source content onto destination --
            warped = cv2.warpAffine(gray, cluster.transform, (w, h),
                                    flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            corr, std_ok = _local_zncc(gray, warped, cfg.zncc_window, cfg.min_local_std)
            dup = ((corr > cfg.zncc_threshold) & std_ok).astype(np.uint8) * 255

            # Fill small gaps, drop speckle, then grow from the seeds: only
            # connected components containing a verified keypoint survive,
            # so coincidental high-correlation areas elsewhere are ignored.
            dup = cv2.morphologyEx(dup, cv2.MORPH_CLOSE, close_kernel)
            dup = cv2.morphologyEx(dup, cv2.MORPH_OPEN, open_kernel)
            dup = _keep_seeded_components(dup, seeds, cfg.min_region_area)
            if cv2.countNonZero(dup) == 0:
                continue

            # --- source mask: map the duplicate back through inverse(A) ----
            inv = cv2.invertAffineTransform(cluster.transform)
            src = cv2.warpAffine(dup, inv, (w, h), flags=cv2.INTER_NEAREST)

            mask = cv2.bitwise_or(mask, cv2.bitwise_or(dup, src))
            labeled[src > 0] = 1
            labeled[dup > 0] = 2
            corr_means.append(float(corr[dup > 0].mean()))

            regions.append({
                "source_bbox": cv2.boundingRect(src),      # (x, y, w, h)
                "dup_bbox": cv2.boundingRect(dup),
                "transform": cluster.transform.tolist(),
                "n_inliers": int(len(cluster.src_pts)),
                "inlier_ratio": float(round(cluster.inlier_ratio, 4)),
            })

        stats = {"mean_corr": float(np.mean(corr_means)) if corr_means else 0.0}
        return mask, labeled, regions, stats

    # ----------------------------------------------------------- scoring
    def _score(self, clusters, mask, gray, grow_stats) -> float:
        """Combine match evidence into a single confidence in [0, 1].

        Components:
          * inlier support   — saturates at ~40 verified inlier matches
          * inlier ratio     — geometric consistency of the best transform
          * region area      — grown mask area relative to the image
          * correlation      — mean ZNCC over the grown duplicate region
        """
        if not clusters or cv2.countNonZero(mask) == 0:
            return 0.0
        total_inliers = sum(len(c.src_pts) for c in clusters)
        inlier_score = min(total_inliers / 40.0, 1.0)
        ratio_score = max(c.inlier_ratio for c in clusters)
        area_frac = cv2.countNonZero(mask) / mask.size
        area_score = min(area_frac / 0.005, 1.0)   # saturates at 0.5% of image
        corr_score = max(grow_stats["mean_corr"], 0.0)
        return float(
            0.35 * inlier_score + 0.20 * ratio_score
            + 0.15 * area_score + 0.30 * corr_score
        )

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _rescale_region(region: dict, factor: float) -> dict:
        """Scale a region dict's bboxes/transform back to original coords."""
        sx, sy, sw, sh = region["source_bbox"]
        dx, dy, dw, dh = region["dup_bbox"]
        transform = np.array(region["transform"], dtype=np.float64)
        transform[:, 2] *= factor  # translation scales; rotation/scale part doesn't
        return {
            **region,
            "source_bbox": tuple(int(round(v * factor)) for v in (sx, sy, sw, sh)),
            "dup_bbox": tuple(int(round(v * factor)) for v in (dx, dy, dw, dh)),
            "transform": transform.tolist(),
        }


def _local_zncc(a: np.ndarray, b: np.ndarray, window: int, min_std: float):
    """Vectorized local zero-mean normalized cross-correlation.

    Returns (corr_map, std_ok) where std_ok is False on near-flat pixels —
    ZNCC is meaningless there (this is the classic textureless failure
    mode of correlation-based verification).
    """
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    win = (window, window)
    mu_a, mu_b = cv2.blur(a, win), cv2.blur(b, win)
    var_a = np.clip(cv2.blur(a * a, win) - mu_a * mu_a, 0, None)
    var_b = np.clip(cv2.blur(b * b, win) - mu_b * mu_b, 0, None)
    cov = cv2.blur(a * b, win) - mu_a * mu_b
    std_a, std_b = np.sqrt(var_a), np.sqrt(var_b)
    corr = cov / (std_a * std_b + 1e-6)
    std_ok = (std_a > min_std) & (std_b > min_std)
    return corr, std_ok


def local_zncc(a: np.ndarray, b: np.ndarray, window: int, min_std: float):
    """Public alias of :func:`_local_zncc` for reuse by other detectors."""
    return _local_zncc(a, b, window, min_std)


def _keep_seeded_components(mask: np.ndarray, seeds: np.ndarray, min_area: int) -> np.ndarray:
    """Remove connected components not touching any seed or below min_area."""
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = np.zeros_like(mask)
    for label in range(1, n_labels):
        if stats[label, cv2.CC_STAT_AREA] < min_area:
            continue
        component = labels == label
        if seeds[component].any():
            out[component] = 255
    return out


def keep_seeded_components(mask: np.ndarray, seeds: np.ndarray, min_area: int) -> np.ndarray:
    """Public alias of :func:`_keep_seeded_components` for reuse by other detectors."""
    return _keep_seeded_components(mask, seeds, min_area)


# --------------------------------------------------------------------------
# Public functional API (stable signature for later stages)
# --------------------------------------------------------------------------
_default_detector: CopyMoveDetector | None = None


def detect_copy_move(image_path: str) -> dict:
    """Detect copy-move forgery in a single image file.

    Returns:
    {
        "forged": bool,
        "confidence": float,           # 0..1
        "mask": np.ndarray,            # uint8 binary mask (0/255), image-sized
        "regions": list[dict],         # {source_bbox, dup_bbox, transform, ...}
        "visualization": np.ndarray    # BGR image with regions highlighted
    }
    """
    global _default_detector
    if _default_detector is None:
        _default_detector = CopyMoveDetector()
    image = load_image(image_path)
    return _default_detector.detect(image)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ScholarGuard copy-move detector")
    parser.add_argument("--image", required=True, help="path to the input figure image")
    parser.add_argument("--output", default="outputs/stage2_results",
                        help="directory to write mask + visualization")
    args = parser.parse_args(argv)

    result = detect_copy_move(args.image)
    os.makedirs(args.output, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.image))[0]

    mask_path = os.path.join(args.output, f"{stem}_pred_mask.png")
    viz_path = os.path.join(args.output, f"{stem}_detection.png")
    save_mask(result["mask"], mask_path)
    save_image(result["visualization"], viz_path)

    summary = {
        "image": args.image,
        "forged": result["forged"],
        "confidence": result["confidence"],
        "n_regions": len(result["regions"]),
        "regions": [
            {k: v for k, v in r.items() if k != "transform"} for r in result["regions"]
        ],
        "mask_saved_to": mask_path,
        "visualization_saved_to": viz_path,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

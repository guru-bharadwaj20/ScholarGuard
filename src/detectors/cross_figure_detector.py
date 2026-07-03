"""Cross-figure duplicate/reuse detector (Stage 3 core).

Finds figure images that duplicate — wholly or partially — other figures
in a corpus (same paper or different papers). Three escalating checks:

    1. **pHash lookup** — instant; catches exact and near-exact whole-image
       duplicates (re-saves, resizes, mild recompression). High confidence.
    2. **Deep-embedding ANN search** — MobileNetV3 features via the Stage 3
       index; catches duplicates that survived rotation, crop or color
       adjustment. Medium/low confidence, needs review.
    3. **Cross-image keypoint verification** — for every candidate from
       (1)/(2), the Stage 2 SIFT machinery is run *between* the two images
       (query descriptors matched against candidate descriptors instead of
       self-matching) with RANSAC + dense ZNCC region growing, to localize
       exactly which sub-region was reused.

IMPORTANT: a flag from this detector is a *lead for human review*, not an
accusation — legitimately similar figures (same lab, same protocol, same
equipment) can score high on visual similarity.

CLI usage:
    # one-time (cached) corpus indexing + query
    python -m src.detectors.cross_figure_detector \
        --image path/to/figure.png --corpus data/figure_corpus \
        --output outputs/stage3_results/
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field

import cv2
import numpy as np

from src.detectors.copy_move_detector import (
    CopyMoveDetector,
    DetectorConfig,
    keep_seeded_components,
    local_zncc,
)
from src.indexing.feature_extractor import FeatureExtractor
from src.indexing.similarity_index import SimilarityIndex
from src.utils.image_io import load_image, save_image
from src.utils.visualization import draw_cross_figure_match


@dataclass
class CrossFigureConfig:
    """Thresholds for the three detection tiers.

    Defaults were calibrated on the synthetic figure corpus (31 figures,
    7 known reuse cases — see README / outputs/stage3_results):

    * ``phash_max_distance=10`` (of 64 bits): re-saved/recompressed/
      brightness-shifted whole-figure duplicates measured Hamming 0-2,
      while the closest *unrelated* figure pair sat at 18. 10 keeps a wide
      margin on both sides. (A rotated+cropped duplicate measured 16 —
      inside unrelated territory, so it is deliberately left to the
      embedding tier rather than stretching this threshold.)
    * ``embed_review=0.85`` is a permissive floor, NOT a decision
      boundary: on a visually homogeneous corpus (all blot-like figures)
      unrelated pairs reach 0.98 cosine while true panel reuses can score
      0.89, so absolute similarity CANNOT separate them. The embedding
      tier is therefore a *candidate generator* (top-k by whole-image
      score ∪ top-k by tile-max score, which together retrieved 7/7 known
      cases at k=10); decisive evidence comes from keypoint verification.
    * ``embed_high=0.985`` labels a hit "medium" instead of "low" — only
      near-identical embeddings clear it (measured: real duplicates 0.99+,
      worst unrelated pair 0.980). Everything below is "low" until the
      keypoint tier confirms it.
    """

    phash_max_distance: int = 10
    embed_high: float = 0.985     # cosine sim >= this: "medium" confidence
    embed_review: float = 0.85    # candidate floor; below this: discard
    top_k: int = 10               # per-ranking ANN candidates per query

    # -- cross-image keypoint verification ---------------------------------
    ratio_threshold: float = 0.75  # Lowe ratio for A->B matches
    min_inliers: int = 6           # RANSAC inliers needed to claim region reuse
    min_scale: float = 0.25        # sanity bounds on recovered uniform scale
    max_scale: float = 4.0
    min_region_area: int = 400     # px^2 of grown region in the candidate image
    # ZNCC here runs on HIGH-PASSED images (see CrossImageRegionMatcher):
    # unlike the within-image Stage 2 case, two *different* figures share
    # smooth background shading that correlates near 1.0 locally (any two
    # gradients look alike through a 9 px window), which produced verified
    # false positives on raw intensities. High-passing kills ramp
    # correlation; copied fine detail still correlates, though interpolation
    # from rotation/rescaling attenuates it — hence the lower threshold.
    highpass_sigma: float = 3.0
    zncc_threshold: float = 0.55

    # Stage 2 feature/ZNCC settings are reused as-is.
    stage2: DetectorConfig = field(default_factory=DetectorConfig)


class CrossImageRegionMatcher:
    """Stage 2's matching pipeline adapted to a *pair* of images.

    Reuses the CopyMoveDetector feature stage (same SIFT configuration) and
    the ZNCC region-growing helpers; only the matching step differs —
    descriptors of image A are matched against image B's (plain 2-NN Lowe
    ratio test; no self-match exclusion needed), then one global RANSAC
    partial-affine transform is estimated over all candidate matches.
    """

    def __init__(self, config: CrossFigureConfig | None = None):
        self.config = config or CrossFigureConfig()
        self._stage2 = CopyMoveDetector(self.config.stage2)

    def match(self, image_a: np.ndarray, image_b: np.ndarray) -> dict:
        """Check whether a region of ``image_a`` re-appears in ``image_b``.

        Returns {"reused": bool, "n_inliers", "transform", "bbox_a",
        "bbox_b", "mask_a", "mask_b", "mean_corr", "confidence"}.
        """
        cfg = self.config
        gray_a = cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY) if image_a.ndim == 3 else image_a
        gray_b = cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY) if image_b.ndim == 3 else image_b

        kps_a, des_a = self._stage2.extract_keypoints(gray_a)
        kps_b, des_b = self._stage2.extract_keypoints(gray_b)
        no_match = {"reused": False, "n_inliers": 0, "confidence": 0.0}
        if des_a is None or des_b is None or len(kps_a) < 2 or len(kps_b) < 2:
            return no_match

        # Plain cross-image 2-NN matching with Lowe ratio test.
        matcher = cv2.BFMatcher(self._stage2._norm)
        knn = matcher.knnMatch(des_a, des_b, k=2)
        pts_a, pts_b = [], []
        for pair in knn:
            if len(pair) < 2:
                continue
            best, second = pair
            if second.distance > 1e-9 and best.distance / second.distance < cfg.ratio_threshold:
                pts_a.append(kps_a[best.queryIdx].pt)
                pts_b.append(kps_b[best.trainIdx].pt)
        if len(pts_a) < cfg.min_inliers:
            return no_match

        src = np.ascontiguousarray(pts_a, np.float32)
        dst = np.ascontiguousarray(pts_b, np.float32)
        transform, inlier_flags = cv2.estimateAffinePartial2D(
            src, dst, method=cv2.RANSAC,
            ransacReprojThreshold=cfg.stage2.ransac_reproj_thresh,
        )
        if transform is None or inlier_flags is None:
            return no_match
        inlier_flags = inlier_flags.ravel().astype(bool)
        n_inliers = int(inlier_flags.sum())
        scale = float(np.hypot(transform[0, 0], transform[0, 1]))
        if n_inliers < cfg.min_inliers or not (cfg.min_scale <= scale <= cfg.max_scale):
            return no_match

        # Dense verification + region growing in B's frame: warp A onto B by
        # the recovered transform, correlate locally, grow from inlier seeds.
        # Correlation runs on high-passed images (see CrossFigureConfig).
        h_b, w_b = gray_b.shape
        warped = cv2.warpAffine(gray_a, transform, (w_b, h_b),
                                flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)

        def _highpass(img: np.ndarray) -> np.ndarray:
            as_float = img.astype(np.float32)
            return as_float - cv2.GaussianBlur(as_float, (0, 0), cfg.highpass_sigma)

        corr, std_ok = local_zncc(_highpass(gray_b), _highpass(warped),
                                  cfg.stage2.zncc_window,
                                  cfg.stage2.min_local_std)
        dup = ((corr > cfg.zncc_threshold) & std_ok).astype(np.uint8) * 255
        dup = cv2.morphologyEx(dup, cv2.MORPH_CLOSE,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
        dup = cv2.morphologyEx(dup, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        seeds = np.zeros((h_b, w_b), np.uint8)
        for x, y in dst[inlier_flags]:
            cv2.circle(seeds, (int(round(x)), int(round(y))),
                       cfg.stage2.seed_radius, 255, -1)
        mask_b = keep_seeded_components(dup, seeds, cfg.min_region_area)
        if cv2.countNonZero(mask_b) == 0:
            return no_match

        # Map the verified region back into A's frame.
        h_a, w_a = gray_a.shape
        inv = cv2.invertAffineTransform(transform)
        mask_a = cv2.warpAffine(mask_b, inv, (w_a, h_a), flags=cv2.INTER_NEAREST)

        mean_corr = float(corr[mask_b > 0].mean())
        confidence = float(
            0.45 * min(n_inliers / 30.0, 1.0)
            + 0.40 * max(mean_corr, 0.0)
            + 0.15 * min(cv2.countNonZero(mask_b) / (0.01 * mask_b.size), 1.0)
        )
        return {
            "reused": True,
            "n_inliers": n_inliers,
            "transform": transform.tolist(),
            "bbox_a": cv2.boundingRect(mask_a),   # (x, y, w, h) in query image
            "bbox_b": cv2.boundingRect(mask_b),   # (x, y, w, h) in matched image
            "mask_a": mask_a,
            "mask_b": mask_b,
            "mean_corr": round(mean_corr, 4),
            "confidence": round(confidence, 4),
        }


class CrossFigureDetector:
    """Corpus-level duplicate search. Holds the index + extractor once."""

    def __init__(
        self,
        corpus_dir: str,
        config: CrossFigureConfig | None = None,
        extractor: FeatureExtractor | None = None,
        index: SimilarityIndex | None = None,
        show_progress: bool = True,
    ):
        self.config = config or CrossFigureConfig()
        self.corpus_dir = corpus_dir
        self.extractor = extractor or FeatureExtractor()
        self.index = index or SimilarityIndex.build_or_load(
            corpus_dir, extractor=self.extractor, show_progress=show_progress
        )
        self._region_matcher = CrossImageRegionMatcher(self.config)

    def detect(self, query_image_path: str, verify_regions: bool = True) -> dict:
        """Run the three-tier duplicate search for one query image."""
        cfg = self.config
        query_abs = os.path.abspath(query_image_path)
        query_image = load_image(query_image_path)

        # ---- tier 1: pHash (near-exact whole-image duplicates) -----------
        query_hash = str(self.extractor.phash(query_image_path))
        hash_matches = []
        for hit in self.index.query_phash(query_hash, cfg.phash_max_distance):
            if hit["path"] == query_abs:
                continue  # the query itself, if it is part of the corpus
            hash_matches.append({
                "matched_image_path": hit["path"],
                "similarity_score": 1.0 - hit["hamming_distance"] / 64.0,
                "hamming_distance": hit["hamming_distance"],
                "confidence_level": "high",
                "method": "phash",
            })

        # ---- tier 2: embedding ANN search (tiled query views) -------------
        query_views = self.extractor.embed_tiles(query_image)
        already = {m["matched_image_path"] for m in hash_matches}
        embed_matches = []
        for hit in self.index.query_embedding(query_views, cfg.top_k):
            if hit["path"] == query_abs or hit["path"] in already:
                continue
            if hit["similarity"] < cfg.embed_review:
                continue
            embed_matches.append({
                "matched_image_path": hit["path"],
                "similarity_score": round(hit["similarity"], 4),
                "confidence_level": ("medium" if hit["similarity"] >= cfg.embed_high
                                     else "low"),
                "method": "embedding",
            })

        # ---- tier 3: keypoint verification of every candidate -------------
        region_matches = []
        if verify_regions:
            for candidate in hash_matches + embed_matches:
                other = load_image(candidate["matched_image_path"])
                verdict = self._region_matcher.match(query_image, other)
                if verdict["reused"]:
                    region_matches.append({
                        "matched_image_path": candidate["matched_image_path"],
                        "similarity_score": verdict["confidence"],
                        "confidence_level": "high",
                        "method": "keypoint_region",
                        "n_inliers": verdict["n_inliers"],
                        "query_bbox": verdict["bbox_a"],
                        "matched_bbox": verdict["bbox_b"],
                        "transform": verdict["transform"],
                        "mask_query": verdict["mask_a"],
                        "mask_matched": verdict["mask_b"],
                        "mean_corr": verdict["mean_corr"],
                    })

        return {
            "query": query_abs,
            "exact_or_near_duplicate_matches": hash_matches,
            "visual_similarity_matches": embed_matches,
            "suspected_region_reuse": region_matches,
        }


def detect_cross_figure_duplicates(query_image_path: str, corpus_dir: str) -> dict:
    """One-shot functional API (builds/loads the corpus index on demand).

    For many queries against the same corpus, construct a
    :class:`CrossFigureDetector` once and call ``.detect()`` repeatedly.
    """
    return CrossFigureDetector(corpus_dir).detect(query_image_path)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ScholarGuard cross-figure detector")
    parser.add_argument("--image", required=True, help="query figure image")
    parser.add_argument("--corpus", required=True, help="folder of corpus figures")
    parser.add_argument("--output", default="outputs/stage3_results",
                        help="directory for visualizations + JSON report")
    parser.add_argument("--rebuild-index", action="store_true",
                        help="force re-embedding of the corpus")
    args = parser.parse_args(argv)

    index = SimilarityIndex.build_or_load(args.corpus,
                                          force_rebuild=args.rebuild_index)
    detector = CrossFigureDetector(args.corpus, index=index)
    result = detector.detect(args.image)

    os.makedirs(args.output, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.image))[0]

    # Save a side-by-side visualization for every verified region reuse.
    query_image = load_image(args.image)
    for i, match in enumerate(result["suspected_region_reuse"]):
        other = load_image(match["matched_image_path"])
        canvas = draw_cross_figure_match(
            query_image, other, match["mask_query"], match["mask_matched"],
            match["query_bbox"], match["matched_bbox"],
        )
        save_image(canvas, os.path.join(args.output, f"{stem}_reuse_{i}.png"))

    # JSON report (numpy masks are dropped; bboxes/scores kept).
    def _clean(match: dict) -> dict:
        return {k: v for k, v in match.items()
                if not isinstance(v, np.ndarray)}

    report = {
        "query": result["query"],
        "exact_or_near_duplicate_matches": result["exact_or_near_duplicate_matches"],
        "visual_similarity_matches": result["visual_similarity_matches"],
        "suspected_region_reuse": [_clean(m) for m in result["suspected_region_reuse"]],
        "note": ("Matches are leads for human review, not proof of misconduct: "
                 "legitimately similar figures can score high."),
    }
    report_path = os.path.join(args.output, f"{stem}_cross_figure_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))
    print(f"\nreport saved to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

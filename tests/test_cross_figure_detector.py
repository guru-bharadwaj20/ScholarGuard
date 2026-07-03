"""Unit tests for the Stage 3 cross-figure duplicate detector.

A small synthetic corpus (~20 figures, seeded RNG) is generated once per
session; the detector/index are also built once — CNN inference on an
i3-class CPU makes per-test rebuilding too slow.
"""

import os
import shutil

import cv2
import numpy as np
import pytest

from src.detectors.cross_figure_detector import CrossFigureDetector
from src.indexing.feature_extractor import FeatureExtractor
from src.indexing.similarity_index import SimilarityIndex
from src.utils.image_io import load_image, save_image
from src.utils.synth import generate_figure_corpus, make_base_figure


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    """~20-figure corpus: 15 originals + 2 whole duplicates + 2 panel reuses."""
    corpus_dir = str(tmp_path_factory.mktemp("figure_corpus"))
    ground_truth = generate_figure_corpus(
        corpus_dir, n_papers=5, figures_per_paper=3,
        n_whole_duplicates=2, n_panel_reuses=2, seed=99,
    )
    return corpus_dir, ground_truth


@pytest.fixture(scope="module")
def detector(corpus):
    corpus_dir, _ = corpus
    return CrossFigureDetector(corpus_dir, show_progress=False)


@pytest.fixture(scope="module")
def query_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("queries"))


# ---------------------------------------------------------------- test 1
def test_exact_duplicate_flagged_by_phash(corpus, detector, query_dir):
    """A byte-identical copy of a corpus image is a high-confidence pHash hit."""
    corpus_dir, ground_truth = corpus
    target = ground_truth["clean"][0]
    query_path = os.path.join(query_dir, "exact_copy.png")
    shutil.copyfile(os.path.join(corpus_dir, target), query_path)

    result = detector.detect(query_path)
    hash_hits = {os.path.basename(m["matched_image_path"]): m
                 for m in result["exact_or_near_duplicate_matches"]}
    assert target in hash_hits
    assert hash_hits[target]["confidence_level"] == "high"
    assert hash_hits[target]["hamming_distance"] == 0
    assert hash_hits[target]["method"] == "phash"


# ---------------------------------------------------------------- test 2
def test_rotated_cropped_duplicate_flagged_by_embedding(corpus, detector, query_dir):
    """A rotated + cropped + brightness-shifted copy defeats pHash but is
    still retrieved by the embedding tier (and verified by keypoints)."""
    corpus_dir, ground_truth = corpus
    target = ground_truth["clean"][3]
    image = load_image(os.path.join(corpus_dir, target))

    h, w = image.shape[:2]
    rotation = cv2.getRotationMatrix2D((w / 2, h / 2), 7.0, 1.0)
    edited = cv2.warpAffine(image, rotation, (w, h), borderMode=cv2.BORDER_REPLICATE)
    margin_y, margin_x = int(h * 0.1), int(w * 0.1)
    edited = edited[margin_y:h - margin_y, margin_x:w - margin_x]
    edited = np.clip(edited.astype(np.float32) * 1.08 - 6, 0, 255).astype(np.uint8)
    query_path = os.path.join(query_dir, "rotated_crop.png")
    save_image(edited, query_path)

    result = detector.detect(query_path)
    embed_hits = {os.path.basename(m["matched_image_path"])
                  for m in result["visual_similarity_matches"]}
    region_hits = {os.path.basename(m["matched_image_path"])
                   for m in result["suspected_region_reuse"]}
    assert target in embed_hits, "embedding tier should retrieve the source"
    assert target in region_hits, "keypoint tier should verify the reuse"


# ---------------------------------------------------------------- test 3
def test_unrelated_image_not_flagged(corpus, detector, query_dir):
    """A brand-new figure must produce no high-confidence match."""
    unrelated = make_base_figure(np.random.default_rng(2024))
    query_path = os.path.join(query_dir, "unrelated.png")
    save_image(unrelated, query_path)

    result = detector.detect(query_path)
    assert result["exact_or_near_duplicate_matches"] == []
    assert result["suspected_region_reuse"] == []
    # Embedding hits, if any, are low-confidence leads only.
    assert all(m["confidence_level"] == "low"
               for m in result["visual_similarity_matches"])


# ---------------------------------------------------------------- test 4
def test_index_topk_ranking(corpus, detector):
    """Querying the index with a corpus member ranks itself first with
    ~1.0 similarity, scores sorted descending, k respected."""
    corpus_dir, ground_truth = corpus
    index: SimilarityIndex = detector.index
    extractor: FeatureExtractor = detector.extractor
    assert len(index) >= 19

    target = ground_truth["clean"][5]
    target_path = os.path.abspath(os.path.join(corpus_dir, target))
    tiles = extractor.embed_tiles(load_image(target_path))

    k = 5
    hits = index.query_embedding(tiles, k=k)
    assert 1 <= len(hits) <= 2 * k          # union of two top-k rankings
    assert hits[0]["path"] == target_path   # itself is the best match
    assert hits[0]["similarity"] == pytest.approx(1.0, abs=1e-3)
    scores = [h["similarity"] for h in hits]
    assert scores == sorted(scores, reverse=True)

    # pHash lookup: the image finds itself at Hamming distance 0.
    hash_hits = index.query_phash(str(extractor.phash(target_path)), max_distance=0)
    assert any(h["path"] == target_path for h in hash_hits)


# ------------------------------------------------------------ extra checks
def test_result_dict_structure(corpus, detector, query_dir):
    """The public API returns the documented three-list structure."""
    corpus_dir, ground_truth = corpus
    result = detector.detect(
        os.path.join(corpus_dir, ground_truth["pairs"][0]["query"])
    )
    assert set(result) >= {"exact_or_near_duplicate_matches",
                           "visual_similarity_matches",
                           "suspected_region_reuse"}
    for group in ("exact_or_near_duplicate_matches",
                  "visual_similarity_matches",
                  "suspected_region_reuse"):
        for match in result[group]:
            assert "matched_image_path" in match
            assert "similarity_score" in match
            assert match["confidence_level"] in {"high", "medium", "low"}


def test_panel_reuse_localized(corpus, detector):
    """A reused sub-panel is verified with masks/bboxes in both figures."""
    corpus_dir, ground_truth = corpus
    panel_pairs = [p for p in ground_truth["pairs"] if p["type"] == "panel"]
    assert panel_pairs
    found = 0
    for pair in panel_pairs:
        result = detector.detect(os.path.join(corpus_dir, pair["query"]))
        for match in result["suspected_region_reuse"]:
            if os.path.basename(match["matched_image_path"]) == pair["source"]:
                found += 1
                assert match["n_inliers"] >= 10
                assert cv2.countNonZero(match["mask_matched"]) >= 2000
                assert len(match["query_bbox"]) == 4
                assert len(match["matched_bbox"]) == 4
    assert found >= 1, "at least one panel reuse must be verified end-to-end"

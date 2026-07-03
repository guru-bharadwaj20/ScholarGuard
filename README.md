# ScholarGuard — AI-Powered Scientific Figure Fraud Detector

Detects image manipulation (duplicated/spliced regions, cross-figure reuse, AI-generated artifacts) in scientific paper figures and cross-checks captions against reported data using CV forensics and NLP, flagging integrity risks for reviewers and journals.

## Stage 2 — Copy-Move Forgery Detector

Classical-CV detector that finds regions duplicated *within* a single figure
(the most common form of blot/microscopy image fraud). CPU-only, no deep
learning — runs in well under a second per image on a low-spec laptop.

### Pipeline

1. **SIFT keypoints** (ORB fallback) with a lowered contrast threshold —
   scientific figures are much smoother than natural photos.
2. **Self-matching** with a brute-force matcher + Lowe ratio test, skipping
   trivial self-matches and spatially-near neighbours.
3. **Offset-space DBSCAN**: matches of a genuine rigid copy-move share
   (nearly) the same displacement vector, so they form a tight cluster in
   `(dx, dy)` space even when only 3–4 keypoints are repeatable.
4. **RANSAC partial-affine verification** per cluster (rotation + uniform
   scale + translation), with scale/displacement sanity checks.
5. **ZNCC region growing**: the image is warped by the verified transform
   and thresholded local normalized cross-correlation grows the sparse
   keypoint seeds into full source/duplicate masks. This dense check is
   also the main false-positive gate.
6. **Confidence score** in `[0, 1]` from inlier count, RANSAC inlier ratio,
   grown-region area and correlation strength. `confidence >= 0.45` ⇒ forged.

### Project structure

```
├── data/
│   ├── synthetic/          # forged images + *_mask.png ground truths (Stage 1)
│   ├── real_test_cases/    # real documented fraud cases (held-out test set)
│   └── clean/              # unforged images (false-positive measurement)
├── src/
│   ├── detectors/copy_move_detector.py   # the Stage 2 detector
│   ├── utils/image_io.py                 # image/mask loading & saving
│   ├── utils/visualization.py            # overlays, side-by-side comparisons
│   ├── utils/synth.py                    # synthetic forgery generator
│   └── evaluation/metrics.py             # IoU / precision / recall / F1 + benchmark CLI
├── tests/test_copy_move_detector.py
├── notebooks/stage2_exploration.ipynb    # visual debugging playground
└── outputs/stage2_results/               # masks, visualizations, per-image CSV
```

### Setup

```bash
pip install -r requirements.txt
```

### Run the detector on a single image

```bash
python -m src.detectors.copy_move_detector --image path/to/image.jpg --output outputs/stage2_results/
```

Prints a JSON summary and writes `<name>_pred_mask.png` (binary mask) and
`<name>_detection.png` (overlay: green box = suspected source, red box =
suspected duplicate) to the output directory.

From Python:

```python
from src.detectors.copy_move_detector import detect_copy_move

result = detect_copy_move("figure.png")
# result: {"forged": bool, "confidence": float, "mask": ndarray,
#          "regions": [{"source_bbox", "dup_bbox", "transform", ...}],
#          "visualization": ndarray}
```

### Generate a synthetic benchmark dataset

If Stage 1 output is not yet in `data/synthetic/`, generate stand-in
forgeries (blot/microscopy-style figures with copy-moved patches, saved as
`<stem>.png` + `<stem>_mask.png`):

```bash
python -m src.utils.synth --output data/synthetic --clean-dir data/clean --n-forged 12 --n-clean 6
```

### Evaluate on the whole dataset

```bash
python -m src.evaluation.metrics --data data/synthetic --clean data/clean --output outputs/stage2_results
```

Writes `outputs/stage2_results/per_image_results.csv` (per-image IoU,
precision, recall, F1, confidence, runtime) plus side-by-side comparison
images, and prints summary statistics.

### Run the tests

```bash
python -m pytest tests/ -v
```

### Current results (synthetic benchmark, 12 forged + 6 clean)

| metric | value |
|---|---|
| detection accuracy (image-level) | 0.89 |
| forged recall | 0.83 (10/12) |
| clean false-positive rate | 0.00 (0/6) |
| mean pixel IoU (forged) | 0.68 |
| mean pixel F1 (forged) | 0.74 |
| mean runtime / image (i3-class CPU) | ~0.5 s |

### Known limitations (keypoint-based methods)

- **Smooth/textureless duplications** — copies of blank blot background or
  uniform regions produce almost no keypoints and pass through undetected.
  ZNCC also refuses to vote on near-flat pixels (`min_local_std`), so such
  regions can neither be found nor grown. This is the classic failure mode
  of keypoint copy-move detection and will need a dense/block-based or
  learned method later.
- **Rotated/rescaled copies of weakly-textured content** — interpolation
  during rotation decorrelates fine texture, so keypoint repeatability
  drops; small rotations (≤ ~10°) of textured content are handled, large
  rotations/flips of smooth content often are not (offset-space clustering
  also assumes offsets vary smoothly across the patch).
- **Legitimately repeated structure** — figures with genuinely identical
  elements (repeated markers, ladders/rulers, tiled panels) can trigger
  detections that are "correct" pixel-wise but not fraud; downstream stages
  need semantic filtering.
- **Splices from *other* images** are invisible to self-matching by
  construction — that's a Stage 3+ problem (cross-figure matching /
  noise-inconsistency analysis).

## Stage 3 — Cross-Figure Duplicate Detection (current)

Finds figures that duplicate — wholly or partially — *other* figures in a
corpus (same paper or different papers): the "same blot presented as a
different experiment" fraud pattern. Three escalating tiers:

1. **pHash lookup** (`imagehash`) — instant; catches exact/near-exact
   whole-figure duplicates (re-saves, resizes, mild recompression).
2. **Deep-embedding ANN search** — MobileNetV3-small (ImageNet-pretrained,
   inference only, CPU) features indexed in FAISS. Each figure is embedded
   as 5 views (whole + 2×2 quadrant tiles) so a reused *sub-panel* can
   dominate a tile even when the whole-image similarity is unremarkable.
   Candidates are the union of top-k by whole-image score and top-k by
   tile-max score. This tier **generates leads, it does not decide**.
3. **Cross-image keypoint verification** — the Stage 2 SIFT machinery run
   *between* the two images (query descriptors matched against candidate
   descriptors), RANSAC affine + high-passed ZNCC region growing. This
   localizes exactly which region was reused and is the decisive,
   high-confidence evidence tier.

### Build the corpus index and run a query

```bash
# (optional) simulate a multi-paper corpus with known reuse cases
python -m src.utils.synth --corpus --corpus-dir data/figure_corpus

# query one figure against the corpus (index is built once and cached in
# data/figure_corpus/.scholarguard_index, ~0.5 s/figure to build on CPU)
python -m src.detectors.cross_figure_detector \
    --image path/to/figure.png --corpus data/figure_corpus \
    --output outputs/stage3_results/
```

Prints/saves a JSON report with the three match lists
(`exact_or_near_duplicate_matches`, `visual_similarity_matches`,
`suspected_region_reuse`) and writes a query|match side-by-side PNG for
every verified region reuse. Add `--rebuild-index` after changing corpus
images. From Python:

```python
from src.detectors.cross_figure_detector import CrossFigureDetector

detector = CrossFigureDetector("data/figure_corpus")  # index built once
result = detector.detect("path/to/figure.png")
```

### Evaluate against a labelled corpus

```bash
python -m src.evaluation.metrics --cross-figure data/figure_corpus --output outputs/stage3_results
```

### Stage 3 results (synthetic corpus: 24 clean figures, 7 known reuses)

| metric | value |
|---|---|
| retrieval recall (source found, any tier) | 1.00 (7/7) |
| … caught by pHash | 2/7 (the re-saved/brightness whole-figure dups) |
| … via embedding candidates | 5/7 (rotated/cropped dup + all 4 panel reuses) |
| region reuse verified by keypoints | 1.00 (7/7) |
| clean false-flag rate (pHash/verified tiers) | 0.00 (0/24) |
| mean query time (i3-class CPU, incl. verification) | ~5 s |

Calibration notes (measured on this corpus, see `CrossFigureConfig`):
pHash Hamming ≤ 10 (duplicates 0–2, closest unrelated pair 18); embedding
cosine floor 0.85 — on a homogeneous corpus unrelated figures reach 0.98,
so absolute similarity **cannot** separate reuse from coincidence and the
embedding tier is candidate-generation only; keypoint gates `min_inliers=10`
and `min_region_area=2000 px²` (genuine reuses measured 44–313 inliers /
≥34k px², accidental matches ≤9 inliers / ≤1.4k px²).

### Stage 3 limitations

- **Flags are leads, not proof** — legitimately similar figures (same lab,
  protocol, equipment) score high on visual similarity; every hit needs
  human review before any action.
- **Embedding thresholds are corpus-dependent** — on visually homogeneous
  corpora only *rank* is informative. A reused panel that neither ranks in
  the top-k of either scoring nor matches by pHash is missed.
- **Same keypoint caveats as Stage 2** for the verification tier
  (textureless panels, heavy re-editing).

### Roadmap

- **Stage 1** — data collection (synthetic forgeries + real fraud cases) ✅
- **Stage 2** — within-figure copy-move detector ✅
- **Stage 3** — cross-figure duplicate/reuse detection ✅
- **Stage 4+** — splice detection via noise/compression inconsistencies,
  dense fallback for textureless regions, panel segmentation (multi-panel
  figures currently indexed whole), caption/data cross-checking,
  reviewer-facing report generation.

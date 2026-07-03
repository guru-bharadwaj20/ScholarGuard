# ScholarGuard — AI-Powered Scientific Figure Fraud Detector

Detects image manipulation (duplicated/spliced regions, cross-figure reuse, AI-generated artifacts) in scientific paper figures and cross-checks captions against reported data using CV forensics and NLP, flagging integrity risks for reviewers and journals.

## Stage 2 — Copy-Move Forgery Detector (current)

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

### Roadmap

- **Stage 1** — data collection (synthetic forgeries + real fraud cases) ✅
- **Stage 2** — copy-move detector (this stage) ✅
- **Stage 3+** — cross-figure duplication search, splice detection via noise
  /compression inconsistencies, dense fallback for textureless regions,
  caption/data cross-checking, reviewer-facing report generation.

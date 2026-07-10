# ScholarGuard — AI-Powered Scientific Figure Fraud Detector

Detects image manipulation (duplicated/spliced regions, cross-figure reuse, AI-generated artifacts) in scientific paper figures and cross-checks captions against reported data using CV forensics and NLP, flagging integrity risks for reviewers and journals.

## Quick start — analyze a paper in one command

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...        # optional: enables text/claim checking
python run_scholarguard.py --pdf path/to/paper.pdf
```

This runs the **unified Stage 6 pipeline** — every detector (copy-move,
cross-figure reuse, AI-generation, claim consistency) over every figure — and
writes one integrity report (JSON + Markdown) with a paper-level risk score.
No API key? It still runs, on image forensics only, and says what it skipped.
Everything is configured in [src/config/config.yaml](src/config/config.yaml)
(see the [Stage 6 section](#stage-6--unified-pipeline-current)). The stage
sections below document each detector individually.

## Building a real figure corpus (PubMed Central Open Access)

Populate `data/clean/` (and `data/figure_corpus/`) with **real** scientific
figures from PubMed Central's Open Access subset, instead of synthetic
stand-ins. [scripts/fetch_corpus.py](scripts/fetch_corpus.py) searches PMC,
downloads each paper's OA package, extracts + dimension-filters the figure
images, skips retracted papers, respects NCBI's rate limits, and records
everything in a resumable manifest.

### Setup (required by NCBI usage policy)

```bash
export NCBI_CONTACT_EMAIL=you@institution.edu   # REQUIRED — a real contact email
export NCBI_API_KEY=your_ncbi_key               # OPTIONAL — raises 3/s -> 10/s
```

`NCBI_CONTACT_EMAIL` is read from the environment (never hardcoded); the script
errors clearly if it is unset. With `NCBI_API_KEY` present the rate limiter
auto-switches from 3 to 10 requests/second.

### Run

```bash
python scripts/fetch_corpus.py --search-terms "western blot" "immunoblot" \
    --target-count 300 --output-dir data/clean
python scripts/fetch_corpus.py --search-terms "microscopy panel" \
    --target-count 150 --output-dir data/figure_corpus
```

Options: `--min-image-dim` (default 200 px shorter side — drops icons/logos),
`--max-package-mb` (default 50 — skips huge supplementary files),
`--retmax-per-term`, `--manifest`, `--raw-dir`.

- **Resumable:** every processed PMCID is recorded in `data/manifest.json`, so
  re-running never re-downloads or re-processes a paper. *Terminal* outcomes
  (extracted, no images, retracted, not open-access, over the size cap) are
  never retried; a *transient* download failure is retried on the next run, so
  one network blip can't permanently exclude a paper. Pass `--no-retry-failed`
  to treat every recorded PMCID as done.
- **Attribution:** each manifest entry records the paper's license (e.g.
  `CC BY`, `CC BY-NC`, `CC BY-NC-ND`), DOI, title, and saved image paths —
  check the license before any use beyond personal research.
- **Robust:** one paper failing (no OA package, download error, no qualifying
  images, size cap) is logged and skipped; the run continues. A final summary
  groups skips by reason.
- **Clean only:** retracted papers (`retracted="yes"`) are skipped — this
  script builds the legitimate corpus; retracted-case sourcing is separate.

> **Note on NCBI's April 2026 restructure.** `oa.fcgi` still returns pre-2026
> `ftp://.../pub/pmc/oa_package/...` hrefs, but those paths now **404** — the
> legacy article-dataset files were moved under `/pub/pmc/deprecated/` (NCBI
> says they'll be removed in **August 2026**). The downloader therefore tries
> the canonical HTTPS path first and falls back to the `deprecated/` tree,
> caching the result so it probes the dead path only once per run. When NCBI
> publishes a replacement distribution channel (their AWS Open Data mirror is
> the stated direction), update `candidate_urls()` in
> [pmc_oa_fetch.py](src/data_acquisition/pmc_oa_fetch.py) — nothing else needs
> to change.

## Building the REAL evaluation set (Retraction Watch × PMC OA)

[scripts/fetch_evaluation_set.py](scripts/fetch_evaluation_set.py) cross-references
the [Retraction Watch database](https://gitlab.com/crossref/retraction-watch-data)
against PMC Open Access to assemble a **real** evaluation set: formally-retracted
papers whose stated retraction reason concerns image integrity, plus clean control
papers (including dose-response series — the false-positive trap Stage 7 found).
It writes a `labels.json` that Stage 7's `ground_truth_loader` consumes unchanged.

It saves **full PDFs** (not just figure images) because Stage 5's `pdf_parser`
needs whole documents with captions and results text intact. It reuses
`pmc_oa_fetch`, `pmc_search`, `rate_limiter` and `manifest` as-is.

```bash
export NCBI_CONTACT_EMAIL=you@institution.edu       # required
python scripts/fetch_evaluation_set.py --fraud-target 40 --clean-target 25 \
    --dose-response-count 10 --output-dir data/evaluation_set
```

The Retraction Watch repo (~63 MB) is shallow-cloned automatically via the `git`
CLI. Progress is tracked in `data/evaluation_manifest.json` (separate from
`data/manifest.json`); **targets are absolute**, so a resumed run tops the set up
rather than fetching a fresh quota. Runs are fully resumable — safe to interrupt.

### `labels.json` schema

```json
{
  "dataset_name": "...", "note": "...", "n_fraud": 15, "n_clean": 10,
  "papers": [{
    "paper_id": "PMC10551568",
    "pdf_path": "data/evaluation_set/fraud_cases/PMC10551568.pdf",
    "is_fraudulent": true,
    "label_confidence": "confirmed",
    "figures": [{"figure_num": null, "fraud_type": "copy_move",
                 "label_confidence": "confirmed", "note": "..."}],
    "doi": "10.1016/j.heliyon.2023.e20459",
    "retraction_reason": "…;Duplication of/in Image;…"
  }]
}
```

- `is_fraudulent` — paper-level ground truth.
- `label_confidence` — `confirmed` for every Retraction Watch case (these are
  *formal retractions*; Expressions of Concern and Corrections are excluded).
- `fraud_type` — a **coarse** mapping of the retraction reason onto the detector
  taxonomy. All three image reasons (`Duplication of/in Image`,
  `Manipulation of Images`, `Falsification/Fabrication of Image`) map to
  `copy_move`; we deliberately never map fabrication to `ai_generated`, which
  would assert a generative origin the data does not support. The verbatim
  reason is preserved in `retraction_reason`.
- `doi`, `title`, `subset` — provenance; the loader ignores unknown keys.

### ⚠ Figure-level locations are NOT annotated

**`figure_num` is `null` for every fraud case.** Retraction Watch states *why a
paper was retracted*, never *which figure* was manipulated — so the script never
guesses a figure number. Consequences:

- **Paper-level metrics are valid** (does the pipeline flag the retracted paper?).
- **Figure-level, per-detector metrics are NOT** — without knowing which figure
  is fraudulent, every detection on a fraud paper's other figures would be
  miscounted. Manual figure-level annotation is required before trusting
  per-detector precision/recall on this set.

### Clean-control safety

Every clean candidate's DOI is resolved (via NCBI's ID Converter) and checked
against the **entire** Retraction Watch DOI set — all ~108k retracted DOIs, not
just the image-related subset — *before* anything is downloaded. As a second
gate, any paper whose OA record reports `retracted="yes"` is discarded too.

### Real vs. synthetic data: the overwrite guard

Every `labels.json` entry carries a `source` field (`"real"` | `"synthetic"`).
`src/evaluation/make_eval_set.py` (the synthetic generator) **refuses to run**
if `labels.json` already contains any `source: "real"` entry — real data costs
thousands of rate-limited NCBI requests to rebuild, and retracted papers have
only ~0.7% OA PDF availability. The check runs *before* any PDF is generated,
so a blocked run writes nothing at all:

```console
$ python -m src.evaluation.make_eval_set
ERROR: refusing to overwrite 'data/evaluation_set/labels.json': it contains 25
REAL evaluation entries downloaded from PMC. ... re-run with --force.
$ echo $?
2
```

Pass `--force` to deliberately replace real data with synthetic. Both the
guard and the `--force` escape hatch are covered by tests.

### Known constraint: PMC OA rarely exposes PDFs for retracted papers

Measured on the live data (2026-07): of ~2,300 image-fraud papers resolved to a
PMCID, **only ~0.7% offered a downloadable OA PDF** — retracted articles are
largely withdrawn from OA distribution. (Clean, recent papers hit ~20%.) The
`.tar.gz` packages do *not* contain the article PDF either, only figures, XML and
supplementary files. Building a large real fraud set therefore requires sweeping
the full Retraction Watch image subset; the script's resumability is what makes
that practical.

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

## Stage 4 — AI-Generation Detection

Flags whether a figure (or region) was likely produced by a generative
model (GAN/diffusion) rather than captured by a real instrument — the
"fabricate data wholesale with AI" fraud pattern. Three signals, combined
by a documented rule:

1. **Frequency anomaly** ([frequency_analysis.py](src/forensics/frequency_analysis.py))
   — CPU, training-free. Radial power-spectrum falloff, power-law fit
   quality, high-frequency suppression, and periodic upsampling ("deconv"
   grid) peaks.
2. **Noise-residual anomaly** ([noise_residual.py](src/forensics/noise_residual.py))
   — CPU, training-free. PRNU-style wavelet residual: energy, lag-1 spatial
   autocorrelation, and spectral whiteness of the sensor-noise field.
3. **Learned classifier** ([artifact_classifier.py](src/models/artifact_classifier.py))
   — *optional*. MobileNetV3-small fine-tuned on **GPU (Colab)**; inference
   runs (slowly) on CPU. Absent until you train and drop in weights.

**The first two run fully locally with no GPU and no training.** The
detector works on those alone and gracefully adds the classifier when
`src/models/weights/artifact_classifier.pt` is present.

### Run local-only detection (no GPU needed)

```bash
# (optional) generate a real-vs-AI sample set for testing
python -m src.utils.synth --ai --n-each 120

python -m src.detectors.ai_generation_detector \
    --image path/to/figure.png --output outputs/stage4_results/
```

Writes a JSON report (`frequency_anomaly_score`, `noise_residual_anomaly_score`,
`classifier_score` — `null` without weights, `combined_verdict`,
`explanation`) and a spectrum heatmap PNG. From Python:

```python
from src.detectors.ai_generation_detector import detect_ai_generation
result = detect_ai_generation("figure.png")               # forensics only
result = detect_ai_generation("figure.png", weights_path="src/models/weights/artifact_classifier.pt")
```

### Train the classifier on Colab and plug weights back in

1. Open [colab/train_artifact_classifier.ipynb](colab/train_artifact_classifier.ipynb)
   in Colab, set the runtime to **GPU (T4)**.
2. Upload your `real_captured_samples/` and `ai_generated_samples/` (Drive
   mount or zip upload). Use **genuine** captures + **real** generator
   output for a model that generalizes — the synthetic stand-ins are only
   for wiring/validation.
3. Run all cells (~3–6 min on a free T4). It exports
   `artifact_classifier.pt` (checkpoint schema matches `classify_artifact`).
4. Place it at `src/models/weights/artifact_classifier.pt`. The local
   detector picks it up automatically and blends it in.

### Signal combination (documented — it's a judgment call)

`forensic = 0.5·freq + 0.5·noise` (independent artifacts → unweighted mean).
- **No weights:** threshold `forensic` → `<0.35` `likely_real`, `0.35–0.55`
  `suspicious`, `≥0.55` `likely_ai_generated`.
- **With weights:** `combined = 0.6·p_ai + 0.4·forensic`, thresholded at
  0.4/0.6. If classifier and forensics disagree strongly (`|p_ai−forensic| ≥
  0.5`) the verdict is pinned to `suspicious` and the conflict is surfaced —
  neither signal silently overrides the other.

### Evaluate on labelled folders

```bash
python -m src.evaluation.metrics --ai-generation --output outputs/stage4_results
```

### Stage 4 results — forensics only, no classifier (120 real + 120 AI)

| metric | value |
|---|---|
| AI recall, strict (`likely_ai_generated`) | 0.70 |
| AI recall, lenient (`suspicious` or stronger) | 1.00 |
| real images falsely flagged AI (strict) | 0.00 |
| real images called `suspicious` | 0.00 |
| strict accuracy | 0.85 |
| mean freq score (real / AI) | 0.22 / 0.61 |
| mean noise score (real / AI) | 0.12 / 0.56 |
| mean runtime / image (CPU) | ~0.3 s |

**Honest read:** frequency + noise cleanly separate *these* signatures
(0 real false positives, every AI image at least `suspicious`), but only
70% of AI images clear the confident `likely_ai_generated` bar — the other
30% land in `suspicious`. That gap **is the point of the classifier**: it
learns generator fingerprints the hand-crafted forensics can't name, and
turns "suspicious" into a confident call. These numbers are on **synthetic
stand-in** generative artifacts; real diffusion/GAN output will shift the
distributions and the thresholds must be re-calibrated (and the classifier
retrained) on genuine data.

### Stage 4 limitations

- **Verdicts are leads, not proof** — never an automated accusation.
- **Forensic thresholds are signature-specific** — heavy JPEG recompression,
  downscaling, or print-scan cycles alter the spectrum/noise of *real*
  images too and can raise their scores; a generator that deliberately
  re-injects sensor-like noise can lower its own. Re-calibrate per corpus.
- **Synthetic training data ≠ real generators** — the shipped samples mimic
  the *forensic signatures* (over-smoothing, deconv grid) but are not real
  diffusion output; treat local numbers as a wiring check.

### What Stage 5 (NLP claim-consistency) consumes from Stage 4

Stage 5 cross-checks figure captions/claims against detected integrity
issues. From this stage it takes, per figure: `combined_verdict`, the two
forensic scores + `classifier_score`, and the `explanation` string — so a
claim like "representative micrograph" over a `likely_ai_generated` panel
becomes a high-priority, human-readable flag in the reviewer report.

## Stage 5 — Claim-Consistency Checking (current)

An NLP layer that reads a paper's **PDF** (text + figures) and checks whether
the written claims about each figure match what the figure shows and what the
image-forensic detectors found. Targets textual inconsistency — a common
accompanying signal in real fraud (e.g. "n = 12 independent replicates" over a
figure showing 4 lanes).

### Pipeline

1. **PDF parsing** ([pdf_parser.py](src/nlp/pdf_parser.py)) — PyMuPDF extracts
   text split by section (Abstract/Methods/Results/…), figure captions
   (`Figure N` / `Fig. N` regex), the surrounding results context for each
   figure, and the **embedded figure images** to disk.
2. **Claim extraction** ([claim_extractor.py](src/nlp/claim_extractor.py)) —
   the Claude API ([llm/client.py](src/llm/client.py)) extracts structured
   claims (sample size, panel/lane count, p-values, fold-changes, error bars).
   The call uses **structured outputs** (`output_config.format` + a JSON
   Schema), so the response is *guaranteed* to parse and match the schema —
   no fragile "please output JSON" prompting. Prompts live in
   [llm/prompts.py](src/llm/prompts.py).
3. **Consistency checking** ([consistency_checker.py](src/nlp/consistency_checker.py))
   — compares claims against (a) an **approximate** visual element count
   (classical CV: connected components + column-projection lane peaks) and
   (b) the Stage 2/3/4 detector flags as a strong prior.
4. **Orchestration** ([claim_consistency_detector.py](src/detectors/claim_consistency_detector.py))
   — runs the existing Stage 2/3/4 detectors (unchanged, via their public
   entry points) on every extracted figure, folds in the textual signals, and
   emits one per-figure risk report (low/medium/high) plus a paper-level
   summary.

### Setup — API key (never hardcoded)

The claim extractor calls the Claude API. Set your key in the environment:

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # bash / zsh
$env:ANTHROPIC_API_KEY = 'sk-ant-...'      # PowerShell
```

or put `ANTHROPIC_API_KEY=sk-ant-...` in a local `.env` file (loaded
automatically via python-dotenv). Without a key, the pipeline still runs — it
degrades gracefully to image-forensics-only and reports the missing key.

### Run on a paper end-to-end

```bash
# (optional) generate a synthetic test paper with an embedded claim/image mismatch
python -m src.utils.sample_paper --output data/sample_papers/synthetic_paper_01.pdf

python -m src.detectors.claim_consistency_detector \
    --pdf data/sample_papers/synthetic_paper_01.pdf --output outputs/stage5_results/
```

Drop real open-access PDFs into `data/sample_papers/` to analyze genuine
papers. `--no-image-detectors` runs text-only; `--weights` supplies the
optional Stage 4 classifier. From Python:

```python
from src.detectors.claim_consistency_detector import analyze_paper
report = analyze_paper("paper.pdf")   # {"figures": [...], "paper_summary": {...}}
```

### Run the tests

```bash
python -m pytest tests/test_claim_consistency_detector.py -v
```

Automated tests **mock the LLM** (no credits spent). The one real-API test is
gated behind `SCHOLARGUARD_LIVE_LLM=1`.

### Stage 5 limitations (read before trusting output)

- **The lane/panel visual count is the weakest link.** It is a coarse
  classical-CV heuristic (blob components + column peaks), not a measurement.
  It catches gross discrepancies (12 claimed vs ~4 shown) but will miss subtle
  ones and misfire on dense/overlapping panels, multi-panel composites, or
  unusual layouts. Treat every count-based flag as *"route to a human"*, not
  *"proven wrong"* — full automation of panel counting is not reliable yet.
- **Every flag is a lead, not an accusation.** Claim extraction, forensics,
  and the visual count are all fallible; a `high` risk figure means "a reviewer
  should look," never "misconduct."
- **PDF/caption parsing is heuristic.** Journal layouts vary; caption↔image
  association assumes roughly one image per figure in reading order.
- **Within-paper cross-figure reuse is false-positive-prone** on figures that
  legitimately share style (same equipment/background) — the self-match
  exclusion handles a figure matching its own copy, but stylistic similarity
  can still surface as a low-confidence lead.

### What Stage 6 (full pipeline integration) needs from all detectors

Stage 6 unifies everything into one reviewer report. Stage 5 already returns
the merge-ready shape — per figure: the extracted `claims`, the
`image_forensics.flags` + `detail` (Stage 2 copy-move, Stage 3 reuse, Stage 4
AI-generation), the `consistency` mismatches with a `text_image_confidence`,
and a banded `risk_level` with human-readable `risk_reasons`; plus a
paper-level `paper_summary` (overall risk, counts, flagged figures). Stage 6
needs each detector to keep emitting these structured, per-figure verdicts
with confidences and short explanations so it can rank figures, deduplicate
overlapping signals (e.g. a copy-move flag that also drives a text mismatch),
and produce a single prioritized, explainable integrity report for editors.

### Stage 5 results (synthetic test paper)

On the generated sample paper (2 figures; Figure 1 caption claims 12 lanes,
image shows 4), with the LLM claim extractor supplying the caption's claims:

| signal | outcome |
|---|---|
| PDF parsing | 4 sections + 2 figures (caption + embedded image) extracted |
| Claim extraction (structured JSON) | schema-valid every call (guaranteed by `output_config.format`) |
| Visual count (Fig 1) | ~4 elements (blob 4 / lane 4) vs claimed 12 → **mismatch flagged** |
| Image forensics | 0 false positives after self-match exclusion (copy-move / reuse / AI all clean) |
| Figure 1 risk | **medium/high** (text/image count mismatch) |

## Stage 6 — Unified Pipeline (current)

The single, production-quality entry point that ties Stages 2–5 into **one
robust, config-driven pipeline**: one PDF in, one comprehensive integrity
report out. This stage adds no new detection logic — it orchestrates, wraps
each detector in isolated error handling, centralizes all configuration, and
produces a unified risk score.

### The one command

```bash
python run_scholarguard.py --pdf paper.pdf \
    [--config src/config/config.yaml] [--output-dir outputs/stage6_results]
```

Prints a per-figure + paper-level risk summary to the console and writes a
full report (`<paper>_report.json` + `<paper>_report.md`) to the output
directory. From Python:

```python
from src.pipeline import run_pipeline
report = run_pipeline("paper.pdf")   # never raises on a bad/empty PDF
```

### Architecture

- **[orchestrator.py](src/pipeline/orchestrator.py)** — `run_pipeline(pdf)`:
  validate → parse (Stage 5 pdf_parser) → per figure run enabled detectors
  (Stages 2/3/4) each in its own `try/except` → claim consistency (Stage 5) →
  risk score → report. Uses the `logging` module throughout (INFO progress,
  WARNING/ERROR for degraded steps). Builds the Stage 3 corpus/embeddings
  **once** and reuses them.
- **[risk_scorer.py](src/pipeline/risk_scorer.py)** — combines all signals into
  a per-figure score (0–100) with a full contribution **breakdown**, and a
  per-paper score where the **worst figure dominates** (not a plain mean).
- **[report_builder.py](src/pipeline/report_builder.py)** — structured JSON
  (the machine-readable source of truth) + human-readable Markdown.
- **[config/settings.py](src/config/settings.py)** — loads and validates
  [config.yaml](src/config/config.yaml) into a typed `Settings` object.

### Configuration (`src/config/config.yaml`) — single source of truth

| Section | What it controls |
|---|---|
| `detectors.<name>.enabled` | Turn each of the 4 detectors on/off |
| `detectors.copy_move.*` | Stage 2 thresholds (`confidence_threshold`, `ratio_threshold`, `min_inliers`, `sift_contrast_threshold`, `max_dim`) |
| `detectors.cross_figure.*` | Stage 3 thresholds (`phash_max_distance`, `embed_review`, `min_inliers`, `min_region_area`, `top_k`) + optional external `corpus_dir` (null ⇒ use the paper's own figures) |
| `detectors.ai_generation.weights_path` | Stage 4 classifier weights (missing file ⇒ forensics-only, reported) |
| `detectors.claim_consistency.panel_count_tolerance` | Stage 5 count-mismatch slack |
| `llm.model` / `max_retries` / `timeout_seconds` | Claude API settings (**API key from `ANTHROPIC_API_KEY` env / `.env`, never in config**) |
| `optimization.skip_llm_when_image_risk` + `skip_llm_at_category` | Documented cost-saver: skip the paid LLM call for a figure already at/above the given image-forensic risk category (reported per figure, never silent) |
| `risk_scoring.weights` | Max points each detector adds (sum = 100) |
| `risk_scoring.*_severity`, `paper_aggregation`, `categories` | Signal severities, worst-figure weighting, and score→category cutoffs |
| `paths.output_dir`, `logging.level` | Where reports go; log verbosity |

**How config reaches the detectors without touching their code:** Stage 2/3
thresholds are injected via their existing `DetectorConfig` / `CrossFigureConfig`
dataclasses (config.yaml → `Settings` → dataclass → detector). Stage 5's one
loose constant (`panel_count_tolerance`) is now an optional parameter with a
back-compatible default. Stage 4's internal forensic bands stay at their
Stage-4-calibrated values (the pipeline consumes its verdict). No core
detection algorithm was modified.

### Graceful degradation (never crash, never silently skip)

| Failure | Behavior |
|---|---|
| Missing Stage 4 classifier weights | AI detection runs **forensics-only**; a warning is added to the report |
| Missing `ANTHROPIC_API_KEY` | Claim consistency **skipped** for all figures; a warning is added |
| One detector throws on a figure | That detector is marked `status: error`; the **other detectors still run** |
| Corrupted / unreadable PDF | `status: "failed"` with a clear message (no stack trace); a report is still written |
| PDF with 0 extractable figures | `status: "completed_no_figures"` with a note; overall risk = low |

Every skipped/degraded/errored step is recorded in `pipeline_warnings` and in
the per-figure `risk.breakdown` — nothing is silently omitted.

### Run the tests

```bash
python -m pytest tests/test_orchestrator.py tests/test_risk_scorer.py \
    tests/test_pipeline_failure_modes.py -v
```

The LLM is mocked (no credits spent). Failure-mode tests cover all five
degradation scenarios above.

## Stage 7 — Formal Evaluation (current)

Measures how the **whole pipeline** performs against labeled papers: does it
catch documented fraud without falsely flagging clean papers? This produces the
project's real metrics (precision, recall, FPR) and a categorized error
analysis. **Measurement only — no detector logic was changed.**

> **Honest data note:** Stage 1's *genuine* held-out fraud cases were never
> present in this repo. Rather than fabricate "real fraud" numbers, Stage 7
> ships a **clearly-labeled synthetic stand-in evaluation set**
> ([make_eval_set.py](src/evaluation/make_eval_set.py)) that exercises the full
> pipeline and includes realistic **false-positive traps** (dose-response
> series of legitimately-similar figures). The metrics below are *real pipeline
> metrics on synthetic data*. To evaluate on real fraud, drop genuine PDFs into
> `data/evaluation_set/{fraud_cases,clean_control_papers}/` and label them in
> `labels.json` — no code changes needed.

### Run the full benchmark

```bash
# (optional) regenerate the synthetic stand-in evaluation set
python -m src.evaluation.make_eval_set

# run the pipeline over every labeled paper, then compute all metrics
python -m src.evaluation.benchmark_runner --eval-config src/config/eval_config.yaml
```

Outputs to `outputs/stage7_results/`: `benchmark_report.json` (raw per-paper
results, saved after **each** paper so a crash loses nothing — re-run to
`--resume`), `metrics_summary.md` (report-ready), `threshold_sweep_results.csv`,
and annotated worst-case images under `error_analysis/`. Use `--analyze-only`
to recompute metrics from an existing benchmark without re-running the pipeline.

### `labels.json` structure

```json
{
  "dataset_name": "...",
  "note": "provenance / caveats",
  "papers": [
    {
      "paper_id": "fraud_copymove_01",
      "pdf_path": "data/evaluation_set/fraud_cases/fraud_copymove_01.pdf",
      "is_fraudulent": true,
      "label_confidence": "confirmed",         // confirmed | disputed
      "figures": [
        {"figure_num": 1, "fraud_type": "copy_move", "label_confidence": "confirmed"},
        {"figure_num": 2, "fraud_type": "none"}
      ]
    }
  ]
}
```

`fraud_type` ∈ `copy_move | cross_figure | ai_generated | claim_mismatch | none`.
Missing PDFs are **warned** about (not fatal); disputed labels are carried
through so weak evidence isn't over-counted.

### Interpreting `metrics_summary.md`

- **Per-detector table** — each detector's precision/recall/FPR at the
  *figure* level, scored only on figures where it actually ran (skipped
  detectors are counted separately, never as silent misses).
- **Combined pipeline** — paper-level fraud classification at the decision
  threshold, with a confusion matrix.
- **Threshold sweep** — the precision/recall tradeoff across paper-score
  cutoffs (reuses stored scores; no re-running), plus a recommended operating
  point that **prioritizes few false positives** (a false accusation is costlier
  than a missed case at screening).
- **Error analysis** — every FP/FN bucketed by *why*, with annotated images.

### Stage 7 results (synthetic stand-in set: 8 fraud + 6 clean papers)

| Detector (figure-level) | Recall | Precision | FPR |
|---|---:|---:|---:|
| copy-move | **1.00** | 0.40 | 0.10 |
| cross-figure | 0.50 | **0.09** | **0.35** |
| AI-generation (forensics-only) | 1.00 | 0.67 | 0.04 |
| claim-consistency | *not evaluated (no API key in this run)* | | |

Combined paper-level: precision 0.57, recall 0.50. **No score threshold
achieved zero false positives** — the honest headline finding.

### Honest summary — strengths, weaknesses, and framing

- **Catches reliably:** in-figure **copy-move** (100% recall here) and
  **AI-generated** figures (both flagged, as `suspicious`, even without
  classifier weights).
- **Catches poorly / the main weakness:** **cross-figure reuse** has low
  precision (0.09) because it **cannot distinguish legitimate similarity from
  fraudulent reuse** — it flagged the dose-response series (9 of 14 false
  positives). This is the #1 real-world false-positive risk and the clearest
  target for future work (it needs semantic/context filtering, not threshold
  tuning).
- **Not measured here:** **claim-consistency** (text/claim mismatch) requires an
  `ANTHROPIC_API_KEY`; this offline run skipped it and says so — the two
  claim-mismatch fraud papers are reported as *not evaluated*, not as misses.
- **Two documented findings (not patched, per stage rules):** (1) the AI
  detector lands genuine AI figures at `suspicious` rather than the confident
  tier without classifier weights — expected from Stage 4, but it means
  forensics-only AI detection is a soft signal; (2) copy-move can false-trigger
  on self-similar texture (FPR 0.10).

**ScholarGuard is a screening/triage tool for human reviewers, NOT an
autonomous accusation system.** Every flag is a lead for a person to verify.
The false-positive analysis matters as much as detection rate: on this set the
pipeline would hand a reviewer several clean-but-flagged figures, so the UI
(Stage 8) must present flags as *prompts to look*, with the evidence and its
uncertainty, never as verdicts.

### Roadmap

- **Stage 1** — data collection (synthetic forgeries + real fraud cases) ✅
- **Stage 2** — within-figure copy-move detector ✅
- **Stage 3** — cross-figure duplicate/reuse detection ✅
- **Stage 4** — AI-generation detection (frequency + noise + optional CNN) ✅
- **Stage 5** — NLP caption/claim-consistency checking (PDF + Claude API) ✅
- **Stage 6** — unified, config-driven pipeline with one report + risk score ✅
- **Stage 7** — formal evaluation, metrics, and error analysis ✅
- **Stage 8+** — reviewer-facing UI (flags as evidence-backed prompts, not
  verdicts); cross-figure specificity (the top weakness); splice detection;
  panel segmentation; evaluation on real held-out fraud cases.

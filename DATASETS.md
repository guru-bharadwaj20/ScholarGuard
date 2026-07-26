# Building the datasets

Every number in [EVALUATION.md](EVALUATION.md) comes from real PubMed Central
papers fetched by the scripts below. **No dataset is committed** (see
`.gitignore`) — they are re-fetchable from here, which is also what keeps the
repository clonable.

All scripts respect NCBI rate limits, resume from a manifest, and record
licensing.

```bash
export NCBI_CONTACT_EMAIL=you@institution.edu   # required by NCBI policy
export NCBI_API_KEY=...                         # optional: 3 -> 10 requests/sec
```

← [Back to the README](README.md)

---

## 1. Calibration set (25 papers)

Used to fit thresholds and fusion weights. Never used to report a result.

```bash
python scripts/fetch_corpus.py --target-count 50
python scripts/fetch_evaluation_set.py --fraud-target 15 --clean-target 10
```

## 2. A held-out set

Retracted image-fraud papers are almost never available as a main PDF in PMC —
only as **OA packages** (JATS XML + native figure images). Clean controls are
fetched the same way, so no detector can separate the classes on a
PDF-vs-native format artifact.

```bash
# Clean controls: a screened PMCID list, with no PDFs fetched that the package
# benchmark would never open (~1 GB saved for 58 papers).
python scripts/build_heldout_clean_list.py --clean-target 50 \
    --output data/heldout4_set/labels.json \
    --exclude data/heldout_packages/labels.json \
             data/heldout_packages_v2/labels.json \
             data/heldout3_packages/labels.json \
             data/evaluation_set/labels.json

# Fraud + clean as packages. --exclude guarantees disjointness by DOI/PMCID.
python scripts/fetch_heldout_packages.py --fraud-target 30 \
    --output-dir data/heldout4_packages \
    --clean-from data/heldout4_set/labels.json \
    --exclude data/heldout_packages/labels.json \
             data/heldout_packages_v2/labels.json \
             data/heldout3_packages/labels.json \
             data/evaluation_set/labels.json
```

Every clean candidate is screened against the **full Retraction Watch DOI list**
and dropped if its DOI cannot be resolved — a control that could not be checked
is worse than one fewer control.

## 3. Figure-level labels

Retraction Watch says a paper was retracted for "Duplication of/in Image", never
*which figure*. Without this step **recall is not measurable at all**. The
annotator follows PubMed's `RetractionIn` pointer to the retraction *notice* — a
separate article that often does name figures — and records them.

```bash
# --dry-run first: it prints the notice sentence behind every figure number.
python scripts/annotate_fraud_figures.py \
    --labels data/heldout4_packages/labels.json --dry-run
python scripts/annotate_fraud_figures.py \
    --labels data/heldout4_packages/labels.json
```

Coverage is partial by design: a bare "Retracted: \<title\>" notice names no
figure, and those papers stay paper-level only rather than being silently
treated as all-clean. Across the three existing sets it found a notice for 89 of
90 fraud papers and figure numbers in 74 of them, marking **197 figures**.

Two caveats that make the resulting numbers *conservative*, both recorded per
annotation in `figure_annotations_audit.json`:

- A notice names the figures it discusses; others in the same paper may be
  manipulated but unmentioned. Detections on unnamed fraud-paper figures count
  as false positives, so precision reads pessimistic.
- Extraction is regex over natural language. Every annotation stores its notice
  PMID and the surrounding sentence so it can be checked by hand.

## 4. Evaluate

```bash
# Papers are independent, so run them in parallel. Results are identical
# to --workers 1; 73 papers take ~3 min on 8 workers.
python -m src.evaluation.benchmark_runner \
    --eval-config src/config/eval_config_heldout3.yaml --workers 8

# Re-analyse without re-running detectors (picks up new figure annotations).
python -m src.evaluation.benchmark_runner \
    --eval-config src/config/eval_config_heldout3.yaml --analyze-only
```

Writes `benchmark_report.json`, `metrics_summary.md`, a threshold sweep and
annotated error examples. The summary reports ROC-AUC, average precision, the
**figure-count-matched AUC**, and both reference rankings.

> **Budget for fresh sets.** Sets 1–3 have all informed decisions by now, so
> none of them is a clean test any more. An unseen set is the scarce resource —
> not compute. Fetch the next one *before* the change you intend to measure.

---

## Training the AI-generation classifier (optional — not recommended)

> ⚠️ **Current recommendation: don't enable it.** On held-out set 1 the trained
> classifier looked like a clear win (ROC-AUC 0.685 → 0.733). On set 2 it was
> the worst of three configurations, with nearly triple the AI false-alarm rate
> of the shipped forensics — see
> [Stage 2g](EVALUATION.md#stage-2g--a-second-held-out-set-overturns-stage-2e-and-recall-becomes-measurable).
> The tooling is sound and the experiment is worth repeating with better
> training data; the resulting model is not worth shipping.

This is the only GPU step in the project. Inference is CPU either way.

**The training data matters more than the training.** `data/ai_generated_samples/`
holds *synthetic stand-ins* — a real sample bilateral-denoised with a
checkerboard added — and [src/utils/synth.py](src/utils/synth.py) says so
itself. A classifier trained on those learns `cv2.bilateralFilter`.

```bash
# 1. Real class: native PMC package figures
python scripts/fetch_corpus.py --target-count 400 --output-dir data/clean \
    --search-terms "western blot" "fluorescence microscopy" "immunohistochemistry"

# 2. AI class: genuine Stable-Diffusion XL output, with resolution and JPEG
#    confounds matched to the real class so the model cannot separate them on
#    compression alone (~25 min for 400 images on a 24 GB card)
python scripts/generate_ai_figures.py --n 400 --batch-size 2 --render-size 768

# 3. Train (~1 min). Real-class figures whose PMCID appears in an evaluation
#    labels.json are dropped automatically -- without that, 185 of 486 figures
#    would have been papers under test.
python scripts/train_artifact_classifier.py --epochs 8
```

Writes `src/models/weights/artifact_classifier.pt` plus a `training_report.json`
recording the split, exclusions and per-class metrics; the detector picks it up
automatically. [colab/train_artifact_classifier.ipynb](colab/train_artifact_classifier.ipynb)
does the same on a free T4.

A 0.99 validation accuracy does not mean 0.99 in the wild — it measured as a
regression on unseen papers. The checkpoint format stays in lock-step with the
inference loader (the trainer calls `src/models/artifact_classifier.py`'s own
`build_model`, and a round-trip test guarantees a checkpoint loads and blends
into the verdict). Without a checkpoint the detector degrades to frequency +
noise forensics and the report says so.

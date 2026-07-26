# ScholarGuard

**Figure-integrity screening for scientific papers — with every limitation measured and disclosed.**

[![tests](https://github.com/guru-bharadwaj20/Scientific-Figure-Integrity-Analyzer/actions/workflows/tests.yml/badge.svg)](https://github.com/guru-bharadwaj20/Scientific-Figure-Integrity-Analyzer/actions/workflows/tests.yml)

ScholarGuard screens a paper's figures for duplication, cross-figure reuse, splicing and AI-generation artifacts, then checks the text's claims against the figures. It is a research prototype: it does not accuse, it surfaces leads for a human reviewer — and it tells you exactly how much to trust each signal.

The evaluation is the point of the project. Detectors are easy to write and easy to fool yourself about; most of the work here went into measuring how often each one is wrong, on real retracted papers, and into **withdrawing the improvements that did not replicate**.

![ScholarGuard landing page](images/hero.png)

<p align="center">
  <img src="images/analyze.png" width="49%" alt="Upload and analyze a paper" />
  <img src="images/methodology.png" width="49%" alt="Per-detector reliability" />
</p>

---

## Where it stands

Measured on **three independent held-out sets** of real PubMed Central papers — 30 formally-retracted image-fraud papers each, against 50, 46 and 43 clean controls, with no overlap between sets or with anything used for tuning.

![ROC and precision-recall on the held-out sets](images/roc_pr.png)

| | Set 1 (30/50) | Set 2 (30/46) | Set 3 (30/43) |
|---|---|---|---|
| ROC-AUC (0.5 = chance) | 0.685 | 0.664 | 0.668 |
| **…with figure count controlled** | **0.571** | **0.632** | **0.625** |
| *Figure count alone, no image analysis* | *0.681* | *0.690* | *0.658* |
| Average precision | 0.613 | 0.567 | 0.602 |
| Recall at the screening cutoff | 0.70 | 0.77 | 0.60 |
| Precision at the screening cutoff | 0.60 | 0.52 | 0.53 |

It finds roughly **6–8 in 10 known-fraud papers** while flagging **28–47% of clean ones**. That is a triage aid for a human reviewer, not a verdict machine, and the README says so because the numbers do.

**Read the second and third rows together.** Retracted papers simply have more figures (median 7.5 vs 5.0), and counting them predicts retraction about as well as the whole pipeline does — better, on set 2. Comparing only papers with an *identical* figure count, the ranking pooled across all three sets is **0.610 (95% CI 0.482–0.725, 439 matched pairs)**: probably real signal, roughly a fifth as strong as the raw number suggests, and still not separable from chance at 95%. Every evaluation run prints this control.

**Per-detector, the honest picture** — and the half of it that only became measurable once retraction notices were parsed for figure-level labels:

![Per-detector recall and false-alarm rate](images/detector_recall_fpr.png)

Copy-move has the clearest sensitivity, replicated three times: it catches about **half** the figures a retraction notice actually names (0.57 / 0.44 / 0.59). Cross-figure lands at 0.33 / 0.00 / 0.31. Splice fires on ~2% of the figures it should, on all three sets. AI-generation's recall cannot be measured at all, because no retraction notice in any set describes a figure as generated.

But read the error bars, not the bars: **across all three sets, every detector's recall interval overlaps its own false-alarm interval.** Copy-move comes closest to separating (0.57 [0.43–0.69] against 0.39 [0.35–0.43] on set 1) and does not manage it. At the figure level this tool surfaces leads; it does not yet demonstrate that it surfaces the right ones more often than the wrong ones.

**And one detector has never been evaluated at all.** Claim-consistency needs an `ANTHROPIC_API_KEY`, and every benchmark run above was made without one, so it was skipped on all 1,475 figures of the three held-out sets and contributes nothing to any number on this page — while still holding 10 of the 100 risk-score points. It is implemented and unit-tested against a mocked LLM; it has never been scored against real papers. Closing that gap needs a key and a re-run, and it is the largest unmeasured surface in the project.

**Four findings worth more than the metrics:**

- **The headline metric was measuring the wrong thing.** Paper-level ROC-AUC could not distinguish this pipeline from `len(paper.figures)`. Found by benchmarking against the dumbest possible predictor — now a permanent line in every report.
- **An "improvement" that did not replicate.** A trained AI-generation classifier lifted set 1's ROC-AUC 0.685 → 0.733. On set 2 it was the *worst* of three configurations, with triple the false-alarm rate. It is disabled by default and the whole arc is documented rather than deleted.
- **A threshold, not a model.** Most of that apparent gain was reproducible by a two-line threshold change with no classifier at all.
- **One held-out set is not enough.** The same detector's false-alarm rate moved 1.4% → 5.4% between sets with no code change.

Two further changes were built, measured, and **declined**: an explicit conformal + Benjamini–Yekutieli count correction (it ranks *worse* than the confound it removes), and switching the headline to the noisy-OR posterior (a +0.073 win on set 1 that did not replicate). Both are documented with their numbers.

**→ [Full evaluation: stage by stage, including what was withdrawn](EVALUATION.md)**

---

## Quickstart

```bash
pip install -r requirements.txt          # Python >= 3.10
export ANTHROPIC_API_KEY=sk-ant-...      # optional — enables claim-consistency
python run_scholarguard.py --pdf path/to/paper.pdf
```

Writes one integrity report (JSON + Markdown) with a paper-level risk score. No API key? It still runs on image forensics and says what it skipped. All behaviour is configured in [src/config/config.yaml](src/config/config.yaml).

```bash
pytest -q            # 200 passed, 1 skipped
docker build -t scholarguard .        # CPU-only image, datasets mounted not baked
```

### Run the web app

Two local servers — a thin FastAPI bridge that calls the unmodified pipeline, and the Next.js frontend.

```bash
# 1. API bridge on :8000
pip install -r server/requirements.txt
uvicorn server.main:app --port 8000

# 2. Web app on :3000
cd web && npm install && npm run dev
```

Open http://localhost:3000. Upload a PDF or run a bundled real example; progress streams live over Server-Sent Events.

---

## How it works

Every figure is first **segmented into panels and content-typed**, then four detectors run over the parts where their signal is meaningful; a config-driven risk scorer combines them into a 0–100 paper score, and a calibrated likelihood-ratio layer produces a complementary fraud probability.

| Detector | Signal | Technique |
|---|---|---|
| Copy-move | Regions duplicated within one figure | content-gated SIFT + g2NN matching + RANSAC + ZNCC region growing + **noise-residual clone test**, with a **dense-field (block-DCT) escalation tier** for smooth blots SIFT misses |
| Cross-figure | One figure reusing another | pHash + CNN embeddings + FAISS + geometric verification + **noise-residual clone test**, with publisher-furniture filtering |
| **Splice** | A region pasted from another source | **noise-inconsistency + JPEG-ghost/ELA**, flagged only where both a foreign noise level AND a foreign compression fingerprint agree |
| AI-generation | GAN/diffusion artifacts | FFT spectral falloff + azimuthal anisotropy + PRNU wavelet noise residual, **conditioned on JPEG compression** (optional CNN) |
| Claim-consistency | Text claims vs. figure content | PDF parsing + Claude API structured extraction + **multimodal figure observation** |

The paper decision **leads with corroboration**: a figure that two or more independent detectors flag is real evidence and lifts the paper to at least "high", whereas a paper full of lone single-detector fires (which merely compound across many figures) is not — this is what lifted held-out average precision from ~0.45 to ~0.70.

### The two ideas doing the heavy lifting

**Content gating (panel segmentation).** Scientific figures are collages. Repeated axis labels, tiled plot markers, and identical scale bars are *geometrically identical to forgery*, and running the matchers over the whole composite is what produced most of the false alarms. Before any detector runs, [src/preprocessing/panel_segmentation.py](src/preprocessing/panel_segmentation.py) splits the figure into panels (recursive X-Y cut), types each as continuous-tone / graphics / text / blank, and builds an **analysis mask** = continuous-tone panels minus detected text and scale bars. Copy-move and cross-figure only see the masked regions, so legitimate repetition no longer reaches them.

**Noise-residual clone test.** Intensity correlation (ZNCC) answers "do these regions *look* alike?" — which is true for both a copy-paste and two honest replicate blots. It cannot separate them. [src/forensics/residual_similarity.py](src/forensics/residual_similarity.py) asks the physically decisive question instead: after alignment, do the two regions share **one exposure's sensor-noise field**? Photon/read noise is independent per capture, so a genuine look-alike scores ~0 residual correlation while a true clone carries its noise with it and correlates strongly (the per-region analogue of PRNU camera forensics). The verdict (`clone` / `independent` / `inconclusive`) multiplies detector confidence: independent noise suppresses a flag, a clone corroborates it, and — honestly — heavy JPEG compression that destroys the residual returns *inconclusive* rather than a false "independent".

Everything runs CPU-only. The optional AI classifier is the single exception: it trains on a GPU — either [colab/](colab/) on a free T4 or [scripts/train_artifact_classifier.py](scripts/train_artifact_classifier.py) on a local CUDA card — and its inference is CPU. The Claude API key is read from the environment and never hardcoded — without it, claim-consistency (both the text extraction and the multimodal figure observation) is skipped and reported as such.

### Evidence fusion

The 0–100 point score is a transparent fixed-weight sum — good for *explaining* what fired, but it cannot down-weight a detector that fires almost as often on clean papers as on fraud. [src/pipeline/evidence_fusion.py](src/pipeline/evidence_fusion.py) adds a complementary layer that combines detectors by **calibrated likelihood ratios** (`P(signal|fraud) / P(signal|clean)`): a detector whose fire rate barely differs between classes has LR ≈ 1 and contributes ~0 evidence *automatically*, with no hand-tuned weight. Per-figure evidence is a naive-Bayes sum of log-LRs turned into a fraud probability; papers aggregate by noisy-OR. **The calibration numbers must be fit on held-out data** (`src.evaluation.metrics.estimate_fire_calibration` + leave-one-out CV) — the shipped defaults are deliberately weak so an uncalibrated install cannot over-claim, and the probability is only trustworthy once calibrated.

---

## Project structure

```
src/              CV + NLP pipeline
  ├─ preprocessing/   panel segmentation + content typing + text/scale-bar masking
  ├─ detectors/       copy-move, cross-figure, ai-generation, claim-consistency
  ├─ forensics/       frequency, noise-residual, residual clone test, JPEG blockiness
  ├─ pipeline/        orchestrator, risk scorer, evidence fusion (LLR), report builder
  ├─ evaluation/      benchmark runner, metrics (Wilson CIs, ROC/PR-AUC, LOOCV), error analysis
  ├─ nlp/             PDF parser, PMC-package (JATS+images) ingestion, claim/vision extraction
  └─ config/          config.yaml — single source of truth
server/           FastAPI bridge (thin transport; zero pipeline logic)
web/              Next.js 14 + Tailwind + Framer Motion + react-three-fiber
scripts/          data acquisition (PMC Open Access, Retraction Watch)
tests/            pytest suite
run_scholarguard.py   CLI entry point
```

## Building real datasets (optional)

```bash
export NCBI_CONTACT_EMAIL=you@institution.edu   # required by NCBI policy
python scripts/fetch_corpus.py --target-count 50
python scripts/fetch_evaluation_set.py --fraud-target 15 --clean-target 10

# A held-out TEST set as PMC packages (JATS XML + native figure images),
# disjoint from the calibration set above. Retracted fraud papers are almost
# never available as a PDF — only as packages — so this is how the Stage 2
# held-out numbers were produced. Both classes use the same package format.
# The clean class is a PMCID list, selected by the same terms and Retraction
# Watch screen as the calibration controls but without fetching PDFs the
# package benchmark never opens (~1 GB saved for 58 papers).
python scripts/build_heldout_clean_list.py --clean-target 58
python scripts/fetch_heldout_packages.py --fraud-target 30

# Figure-level labels: read each paper's RETRACTION NOTICE (via PubMed's
# RetractionIn link) and record which figures it names. Without this, recall is
# not measurable at all -- Retraction Watch gives only paper-level reasons.
# --dry-run first: it prints the notice sentence behind every figure number.
python scripts/annotate_fraud_figures.py \
    --labels data/heldout_packages/labels.json --dry-run
python scripts/annotate_fraud_figures.py --labels data/heldout_packages/labels.json

# Papers are independent, so evaluate them in parallel (~11 min -> ~3 min for
# 80 papers on 16 cores; results are bit-identical to --workers 1).
python -m src.evaluation.benchmark_runner \
    --eval-config src/config/eval_config_heldout.yaml --workers 16
```

**Build a second set and validate on both.** Stage 2g showed a single held-out set can reverse an 0.05 AUC verdict. Re-run the three commands above with `--exclude` extended to the first set's `labels.json` and a different `--output-dir`, then evaluate on both before accepting any change.

All scripts respect NCBI rate limits, skip already-fetched items via a resumable manifest, and record licensing. Datasets are never committed (see `.gitignore`) — they are re-fetchable from these scripts.

### Train the AI-generation classifier (optional — and currently not recommended)

> ⚠️ **Current recommendation: don't.** On the first held-out set the trained classifier looked like a clear win (ROC-AUC 0.685 → 0.733). On a **second** held-out set it was the worst of three configurations, with nearly triple the AI false-alarm rate of the shipped forensics — see [Stage 2g in the evaluation](EVALUATION.md#stage-2g--a-second-held-out-set-overturns-stage-2e-and-recall-becomes-measurable). The instructions below are kept because the tooling is sound and the experiment is worth repeating with better training data; the resulting model is not currently worth enabling.

The AI detector ships forensics-only, and training its learned model is the one GPU step in the project. A 0.99 validation accuracy does not mean 0.99 in the wild — it measured as a regression on unseen papers.

**The training data matters more than the training.** `data/ai_generated_samples/` holds *synthetic stand-ins* — a real sample bilateral-denoised with a checkerboard added — and [src/utils/synth.py](src/utils/synth.py) says so itself. A classifier trained on those learns `cv2.bilateralFilter`. Generate real diffusion output instead:

```bash
# 1. A real class: native PMC package figures (400 more on top of what you have)
export NCBI_CONTACT_EMAIL=you@institution.edu
python scripts/fetch_corpus.py --search-terms "western blot" "fluorescence microscopy" \
    "immunohistochemistry" --target-count 400 --output-dir data/clean

# 2. An AI class: genuine Stable-Diffusion output, with the resolution and JPEG
#    confounds matched to the real class so the model cannot separate them on
#    compression alone (~25 min for 400 images on a 24 GB card)
python scripts/generate_ai_figures.py --n 400 --batch-size 2 --render-size 768

# 3. Train (~1 min on a modern GPU). Figures whose PMCID appears in an
#    evaluation labels.json are dropped from the real class automatically --
#    without that, ~185 of 486 figures here would have been papers under test.
python scripts/train_artifact_classifier.py --epochs 8
```

That writes `src/models/weights/artifact_classifier.pt` (plus a `training_report.json` recording the split, exclusions and per-class metrics) and the detector picks it up automatically. [colab/train_artifact_classifier.ipynb](colab/train_artifact_classifier.ipynb) does the same on a free T4 if you have no local GPU.

The checkpoint format and architecture are kept in lock-step with the inference loader (`src/models/artifact_classifier.py`) — the local trainer calls that module's own `build_model`, and a round-trip test guarantees a trained checkpoint loads and blends into the AI verdict with zero glue work. Without a checkpoint the detector degrades to the frequency + noise forensics and the report says so.

---

*Flags are leads for human review, not proof of misconduct. ScholarGuard analyzes figures locally; the Claude API is used only for optional text/claim extraction.*

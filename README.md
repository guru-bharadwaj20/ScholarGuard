# ScholarGuard

**Figure-integrity screening for scientific papers — with every limitation measured and disclosed.**

ScholarGuard screens a paper's figures for duplication, cross-figure reuse, and AI-generation artifacts, then checks the text's claims against the figures. It is a research prototype: it does not accuse, it surfaces leads for a human reviewer — and it tells you exactly how much to trust each signal.

![ScholarGuard landing page](images/hero.png)

<p align="center">
  <img src="images/analyze.png" width="49%" alt="Upload and analyze a paper" />
  <img src="images/methodology.png" width="49%" alt="Per-detector reliability" />
</p>

---

## How honest is it?

ScholarGuard was evaluated on **25 real PubMed Central papers** — 15 formally retracted for image integrity (Retraction Watch) and 10 never-retracted controls. The results are deliberately unflattering where the tool is weak:

| Detector | Real false-alarm rate | Verdict |
|---|---|---|
| **AI-generation** | **2.4%** (95% CI 0.7–8.4) | Comparatively reliable |
| **Cross-figure reuse** | 27.7% (19–38) | Frequently over-triggers |
| **Copy-move** | 56.6% (46–67) | Frequently over-triggers |
| **Claim-consistency** | — | Unvalidated on real papers (needs API key) |

At the paper level, **recall is 80%** (12/15 real fraud caught), but the **best accuracy at any single threshold is 60% — the base rate**. The score distributions of fraud and clean papers still overlap: copy-move and cross-figure fire on legitimate repeated structure (replicate panels, scale bars, dose-response series) that is geometrically identical to manipulation.

> **Overfitting caveat:** detector thresholds were recalibrated on these same 25 papers — the only real data available — so the numbers above are optimistic in-sample estimates, **not** unbiased measurement on unseen data. A fresh, never-seen paper set is needed before trusting them further.

> **These numbers predate the current detector architecture.** The table above measured the previous whole-figure detectors. The pipeline has since been rebuilt around panel-level content gating and a noise-residual clone test (see "How it works") that target the exact false-positive source those numbers exposed — legitimate repeated structure scoring identically to manipulation. The improvements are architectural and unit-tested, but the headline recall/false-alarm rates have **not** yet been re-measured on the benchmark, and are not claimed here. Re-running `src/evaluation` on a fresh, figure-annotated set is the required next step, and the evaluation now reports threshold-free **ROC-AUC / average precision** and **leave-one-out** accuracy rather than the in-sample best-threshold accuracy that made the old numbers look better than the tool was.

**ScholarGuard is a screening prototype for human reviewers, not an autonomous accusation system. Every flag is a lead to be checked by a person.**

---

## How it works

Every figure is first **segmented into panels and content-typed**, then four detectors run over the parts where their signal is meaningful; a config-driven risk scorer combines them into a 0–100 paper score, and a calibrated likelihood-ratio layer produces a complementary fraud probability.

| Detector | Signal | Technique |
|---|---|---|
| Copy-move | Regions duplicated within one figure | content-gated SIFT + g2NN matching + offset-space clustering + RANSAC + ZNCC region growing + **noise-residual clone test** |
| Cross-figure | One figure reusing another | pHash + CNN embeddings + FAISS + geometric verification + **noise-residual clone test**, with publisher-furniture filtering |
| AI-generation | GAN/diffusion artifacts | FFT spectral falloff + azimuthal anisotropy + PRNU wavelet noise residual, **conditioned on JPEG compression** (optional CNN) |
| Claim-consistency | Text claims vs. figure content | PDF parsing + Claude API structured extraction + **multimodal figure observation** |

### The two ideas doing the heavy lifting

**Content gating (panel segmentation).** Scientific figures are collages. Repeated axis labels, tiled plot markers, and identical scale bars are *geometrically identical to forgery*, and running the matchers over the whole composite is what produced most of the false alarms. Before any detector runs, [src/preprocessing/panel_segmentation.py](src/preprocessing/panel_segmentation.py) splits the figure into panels (recursive X-Y cut), types each as continuous-tone / graphics / text / blank, and builds an **analysis mask** = continuous-tone panels minus detected text and scale bars. Copy-move and cross-figure only see the masked regions, so legitimate repetition no longer reaches them.

**Noise-residual clone test.** Intensity correlation (ZNCC) answers "do these regions *look* alike?" — which is true for both a copy-paste and two honest replicate blots. It cannot separate them. [src/forensics/residual_similarity.py](src/forensics/residual_similarity.py) asks the physically decisive question instead: after alignment, do the two regions share **one exposure's sensor-noise field**? Photon/read noise is independent per capture, so a genuine look-alike scores ~0 residual correlation while a true clone carries its noise with it and correlates strongly (the per-region analogue of PRNU camera forensics). The verdict (`clone` / `independent` / `inconclusive`) multiplies detector confidence: independent noise suppresses a flag, a clone corroborates it, and — honestly — heavy JPEG compression that destroys the residual returns *inconclusive* rather than a false "independent".

Everything runs CPU-only. The optional AI classifier trains on GPU in [colab/](colab/); inference is CPU. The Claude API key is read from the environment and never hardcoded — without it, claim-consistency (both the text extraction and the multimodal figure observation) is skipped and reported as such.

### Evidence fusion

The 0–100 point score is a transparent fixed-weight sum — good for *explaining* what fired, but it cannot down-weight a detector that fires almost as often on clean papers as on fraud. [src/pipeline/evidence_fusion.py](src/pipeline/evidence_fusion.py) adds a complementary layer that combines detectors by **calibrated likelihood ratios** (`P(signal|fraud) / P(signal|clean)`): a detector whose fire rate barely differs between classes has LR ≈ 1 and contributes ~0 evidence *automatically*, with no hand-tuned weight. Per-figure evidence is a naive-Bayes sum of log-LRs turned into a fraud probability; papers aggregate by noisy-OR. **The calibration numbers must be fit on held-out data** (`src.evaluation.metrics.estimate_fire_calibration` + leave-one-out CV) — the shipped defaults are deliberately weak so an uncalibrated install cannot over-claim, and the probability is only trustworthy once calibrated.

---

## Quickstart

### Analyze a paper from the command line

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...        # optional — enables claim-consistency
python run_scholarguard.py --pdf path/to/paper.pdf
```

Writes one integrity report (JSON + Markdown) with a paper-level risk score. No API key? It still runs on image forensics and says what it skipped. All behaviour is configured in [src/config/config.yaml](src/config/config.yaml).

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

## Project structure

```
src/              CV + NLP pipeline
  ├─ preprocessing/   panel segmentation + content typing + text/scale-bar masking
  ├─ detectors/       copy-move, cross-figure, ai-generation, claim-consistency
  ├─ forensics/       frequency, noise-residual, residual clone test, JPEG blockiness
  ├─ pipeline/        orchestrator, risk scorer, evidence fusion (LLR), report builder
  ├─ evaluation/      benchmark runner, metrics (Wilson CIs, ROC/PR-AUC, LOOCV), error analysis
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
```

Both respect NCBI rate limits, skip already-fetched items via a resumable manifest, and record licensing.

## Tests

```bash
pytest -q      # 119 passed, 1 skipped
```

---

*Flags are leads for human review, not proof of misconduct. ScholarGuard analyzes figures locally; the Claude API is used only for optional text/claim extraction.*

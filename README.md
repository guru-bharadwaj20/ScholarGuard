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

**ScholarGuard is a screening prototype for human reviewers, not an autonomous accusation system. Every flag is a lead to be checked by a person.**

---

## How it works

Four detectors run over every figure; a config-driven risk scorer combines them into a 0–100 paper score.

| Detector | Signal | Technique |
|---|---|---|
| Copy-move | Regions duplicated within one figure | SIFT + offset-space clustering + RANSAC + ZNCC region growing |
| Cross-figure | One figure reusing another | pHash + CNN embeddings + FAISS + geometric verification |
| AI-generation | GAN/diffusion artifacts | FFT spectral falloff + PRNU wavelet noise residual (optional CNN) |
| Claim-consistency | Text claims vs. figure content | PDF parsing + Claude API structured extraction |

Everything runs CPU-only. The optional AI classifier trains on GPU in [colab/](colab/); inference is CPU. The Claude API key is read from the environment and never hardcoded — without it, claim-consistency is skipped and reported as such.

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
  ├─ detectors/       copy-move, cross-figure, ai-generation, claim-consistency
  ├─ forensics/       frequency + noise-residual analysis
  ├─ pipeline/        orchestrator, risk scorer, report builder
  ├─ evaluation/      benchmark runner, metrics (Wilson CIs), error analysis
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
pytest -q      # 97 passed, 1 skipped
```

---

*Flags are leads for human review, not proof of misconduct. ScholarGuard analyzes figures locally; the Claude API is used only for optional text/claim extraction.*

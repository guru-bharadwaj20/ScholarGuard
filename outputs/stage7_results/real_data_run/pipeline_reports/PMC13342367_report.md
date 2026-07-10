# ScholarGuard Integrity Report — PMC13342367.pdf

- **Generated:** 2026-07-10T08:36:34
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 43.51/100, 5 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 39.18/100)
> Design framework linking scaffold, cells and bioactive regulators to mechanics, endothelialization and host remodeling in tissue-engineered blood vessels. Created by the authors. 2 Journal of Tissue E…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 29.18/35.0 | duplicated regions within figure (conf 0.8338) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 34.67/100)
> Purine-metabolizing antithrombotic concept for CD39/CD73-based vascular interfaces. Created by the authors based on published mechanistic concepts.80,81 6 Journal of Tissue Engineering 17

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.67/35.0 | duplicated regions within figure (conf 0.9907) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 43.62/100)
> Original schematic of the Ancr/E7-EXO strategy for targeting Gli1-positive progenitor cells and suppressing vascular graft calcification. Created by the authors. Chen et al. 7

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.62/35.0 | duplicated regions within figure (conf 0.9605) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 43.38/100)
> Representative auxiliary bioactive systems for antithrombosis, endothelialization, calcification control and immune regulation in tissue-engineered blood vessels. The figure summarizes stage-specific …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.38/35.0 | duplicated regions within figure (conf 0.9538) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 44.55/100)
> Simplified microRNA-regulated angiogenic network relevant to tissue-engineered blood vessel integration. The scheme is intended as a mechanistic overlay for scaffold and cell design, not as an exhaust…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.55/35.0 | duplicated regions within figure (conf 0.9872) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
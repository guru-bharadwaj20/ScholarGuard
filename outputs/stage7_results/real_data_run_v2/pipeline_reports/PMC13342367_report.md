# ScholarGuard Integrity Report — PMC13342367.pdf

- **Generated:** 2026-07-11T23:56:19
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 30.81/100, 5 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 31.82/100)
> Design framework linking scaffold, cells and bioactive regulators to mechanics, endothelialization and host remodeling in tissue-engineered blood vessels. Created by the authors. 2 Journal of Tissue E…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.82/35.0 | duplicated regions within figure (conf 0.9091) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk LOW (score 17.98/100)
> Purine-metabolizing antithrombotic concept for CD39/CD73-based vascular interfaces. Created by the authors based on published mechanistic concepts.80,81 6 Journal of Tissue Engineering 17

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 17.98/35.0 | duplicated regions within figure (conf 0.5137) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 33.04/100)
> Original schematic of the Ancr/E7-EXO strategy for targeting Gli1-positive progenitor cells and suppressing vascular graft calcification. Created by the authors. Chen et al. 7

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.04/35.0 | duplicated regions within figure (conf 0.9439) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk LOW (score 22.61/100)
> Representative auxiliary bioactive systems for antithrombosis, endothelialization, calcification control and immune regulation in tissue-engineered blood vessels. The figure summarizes stage-specific …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.61/35.0 | duplicated regions within figure (conf 0.6461) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk LOW (score 22.53/100)
> Simplified microRNA-regulated angiogenic network relevant to tissue-engineered blood vessel integration. The scheme is intended as a mechanistic overlay for scaffold and cell design, not as an exhaust…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.53/35.0 | duplicated regions within figure (conf 0.6436) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
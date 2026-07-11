# ScholarGuard Integrity Report — PMC8220243.pdf

- **Generated:** 2026-07-12T00:24:16
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 46.96/100, 8 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> (A) Effects of activation temperature and impregnation ratio on carbon yield at con- stant activation time (90 min) and activating agent concentration (60 %) (B) Effects of activa- tion time and activ…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk HIGH (score 55.68/100)
> Predicted and actual values plot for (A): Carbon yield, (B): Speciﬁc surface area. R.T. Iwar et al. Heliyon 7 (2021) e07301 7

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.68/35.0 | duplicated regions within figure (conf 0.8193) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk LOW (score 0.0/100)
> (A); Optimization of RPSAC Yield in terms of impregnation ratio and concentration at constant temperature (523.68 C) and activation time (103.83 min) (B); Optimization of Speciﬁc surface area of RPSA…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk HIGH (score 53.11/100)
> SEM image of RPSAC with elemental composition. R.T. Iwar et al. Heliyon 7 (2021) e07301 9

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 26.11/35.0 | duplicated regions within figure (conf 0.746) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk LOW (score 24.92/100)
> EDX spectrum of RPSAC

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.92/35.0 | duplicated regions within figure (conf 0.7119) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk MODERATE (score 25.65/100)
> Crystallographic composition of RPSAC. R.T. Iwar et al. Heliyon 7 (2021) e07301 10

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.65/35.0 | duplicated regions within figure (conf 0.7329) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 25.12/100)
> (A): FTIR spectrum and (B): XRD Proﬁle of RPSAC. R.T. Iwar et al. Heliyon 7 (2021) e07301 11

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.12/35.0 | duplicated regions within figure (conf 0.7178) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 11) — risk MODERATE (score 28.46/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.46/35.0 | duplicated regions within figure (conf 0.8132) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
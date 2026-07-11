# ScholarGuard Integrity Report — PMC8220243.pdf

- **Generated:** 2026-07-10T09:03:25
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 55.18/100, 8 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 10.0/100)
> (A) Effects of activation temperature and impregnation ratio on carbon yield at con- stant activation time (90 min) and activating agent concentration (60 %) (B) Effects of activa- tion time and activ…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk HIGH (score 61.77/100)
> Predicted and actual values plot for (A): Carbon yield, (B): Speciﬁc surface area. R.T. Iwar et al. Heliyon 7 (2021) e07301 7

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.77/35.0 | duplicated regions within figure (conf 0.9933) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk LOW (score 10.0/100)
> (A); Optimization of RPSAC Yield in terms of impregnation ratio and concentration at constant temperature (523.68 C) and activation time (103.83 min) (B); Optimization of Speciﬁc surface area of RPSA…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk HIGH (score 60.37/100)
> SEM image of RPSAC with elemental composition. R.T. Iwar et al. Heliyon 7 (2021) e07301 9

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.37/35.0 | duplicated regions within figure (conf 0.9533) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 45.0/100)
> EDX spectrum of RPSAC

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.3357) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk MODERATE (score 43.73/100)
> Crystallographic composition of RPSAC. R.T. Iwar et al. Heliyon 7 (2021) e07301 10

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.73/35.0 | duplicated regions within figure (conf 0.9638) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 43.66/100)
> (A): FTIR spectrum and (B): XRD Proﬁle of RPSAC. R.T. Iwar et al. Heliyon 7 (2021) e07301 11

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.66/35.0 | duplicated regions within figure (conf 0.9616) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 11) — risk MODERATE (score 43.81/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.81/35.0 | duplicated regions within figure (conf 0.9661) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
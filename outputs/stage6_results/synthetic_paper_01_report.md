# ScholarGuard Integrity Report — synthetic_paper_01.pdf

- **Generated:** 2026-07-08T23:14:05
- **Status:** completed
- **Overall paper risk:** **LOW** (score 11.06/100, 2 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 10.0/100)
> Western blot of Protein X across 12 treatment conditions (n = 12 lanes). Band intensity increases with stress severity. Error bars represent mean +/- SEM.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | ok | 10.0/15.0 | text states 12 lanes, but the figure appears to show ~4 distinct elements (approximate count — needs human review) |

## Figure 2 — risk LOW (score 11.25/100)
> Representative microscopy fields showing sub-cellular localization of Protein X (n = 6 replicates, 3 conditions shown).

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | ok | 11.25/15.0 | text states 12 lanes, but the figure appears to show ~3 distinct elements (approximate count — needs human review) |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
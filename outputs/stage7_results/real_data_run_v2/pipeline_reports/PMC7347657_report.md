# ScholarGuard Integrity Report — PMC7347657.pdf

- **Generated:** 2026-07-12T00:13:22
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 48.69/100, 8 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Single steps chronoamperograms for the electrodeposition of Cys/Au NP on the citrate-AgNPs-GQDs nano ink paper-based electrode surface; photo- graphic paper (A) and ivory sheet (B). E ¼ 0.0V vs. and t…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk LOW (score 0.0/100)
> DPVs of citrate- AgNPs-GQDs nano ink, citrate- AgNPs-GQDs nano ink/AuNP-CysA, cit- rate- AgNPs-GQDs nano ink/AuNPs-CysA/Ab, citrate- AgNPs-GQDs nano ink/AuNPs-CysA/ Ab1/BSA, citrate- AgNPs-GQDs nano i…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 26.31/100)
> DPVs of citrate- AgNPs-GQDs nano ink/Au NPs- CysA/Ab1/BSA/PSA/Ab2 for study of various concentrations of PSA Ag (60–0.07 μg/L) in supporting electrolyte is 0.01M ferricyanide on the surface of ivory s…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 26.31/35.0 | duplicated regions within figure (conf 0.7517) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 27.59/100)
> DPVs of citrate- AgNPs-GQDs nano ink/Cys-Au NPs/Ab1/BSA/PSA/Ab2 for analysis of different concentrations of PSA Ag in human plasma specimens on the surface of ivory sheets (A)and photographic papers(B…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 27.59/35.0 | duplicated regions within figure (conf 0.7882) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 48.81/100)
> shows that, the current signals of the prepared immunode- vice were compared with the current signal achieved in 5-fold excess of different interfering species solution. The peak current produced by i…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 21.81/35.0 | duplicated regions within figure (conf 0.6232) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk HIGH (score 57.83/100)
> Cyclic voltammograms and histograms of engineered immunosensor stability on the surface of ivory sheet(A) and photographic paper(B) study in potential range of -1 to þ1 and scan rate of 100 mV/s in 0.…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 30.83/35.0 | duplicated regions within figure (conf 0.8808) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 7) — risk LOW (score 24.74/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.74/35.0 | duplicated regions within figure (conf 0.7068) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 8) — risk MODERATE (score 33.57/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.57/35.0 | duplicated regions within figure (conf 0.9591) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
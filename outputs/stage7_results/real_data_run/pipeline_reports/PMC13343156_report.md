# ScholarGuard Integrity Report — PMC13343156.pdf

- **Generated:** 2026-07-10T08:39:54
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 66.77/100, 7 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 34.5/100)
> Slit lamp imaging did not reveal changes post vehicle or FLAG/PAX6 injection in WT or Sey/+ eyes Imaging of the injected eye of the same mouse at 2–2.5 and 5 months PI after vehicle or FLAG/PAX6 injec…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.5/35.0 | duplicated regions within figure (conf 0.7) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk HIGH (score 72.0/100)
> Histological imaging showed virus-delivered PAX6 protein in the cornea of Sey/+ eyes and increased corneal thickness (A–D) Immunofluorescence staining was performed on paraffin-embedded sections 5 mon…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.5391) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk HIGH (score 72.0/100)
> Histological imaging showed virus “escaped” and delivered PAX6 protein to the retina of Sey/+ eyes (A–D) Immunofluorescence staining was performed on paraffin-embedded sections 5 months PI after vehic…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.364) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk HIGH (score 55.46/100)
> Significant increase in corneal epithelial thickness after FLAG/ PAX6 injection in Sey/+ eyes (A–D) Quantification of (A) epithelial thickness, (B) epithelial cell count, (C) stromal- endothelial thic…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.46/35.0 | duplicated regions within figure (conf 0.8131) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk HIGH (score 61.92/100)
> Correlations show that uninjected contralateral eyes were not impacted by injection in partner eye (A and B) Correlation analysis shows that the uninjected contralateral eyes were not impacted by inje…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.92/35.0 | duplicated regions within figure (conf 0.7121) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk HIGH (score 51.5/100)
> FLAG/PAX6-injected Sey/+ corneas had the most FLAG-PAX6 transcripts, but the difference was not significant (A–C) Transcript levels of virally delivered FLAG-tagged PAX6 (FLAG-PAX6 assay) or endogenou…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.5/35.0 | duplicated regions within figure (conf 0.7) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 34.5/100)
> Overall significant pattern of the correction of gene transcription back to WT levels (A–D) Endogenous transcript levels in corneas after vehicle or FLAG/PAX6 injection in WT or Sey/+ eyes were quanti…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.5/35.0 | duplicated regions within figure (conf 0.7) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
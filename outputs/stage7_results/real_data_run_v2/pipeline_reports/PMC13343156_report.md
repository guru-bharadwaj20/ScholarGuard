# ScholarGuard Integrity Report — PMC13343156.pdf

- **Generated:** 2026-07-11T23:59:11
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 55.02/100, 7 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 28.54/100)
> Slit lamp imaging did not reveal changes post vehicle or FLAG/PAX6 injection in WT or Sey/+ eyes Imaging of the injected eye of the same mouse at 2–2.5 and 5 months PI after vehicle or FLAG/PAX6 injec…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.54/35.0 | duplicated regions within figure (conf 0.8155) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk HIGH (score 59.64/100)
> Histological imaging showed virus-delivered PAX6 protein in the cornea of Sey/+ eyes and increased corneal thickness (A–D) Immunofluorescence staining was performed on paraffin-embedded sections 5 mon…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.64/35.0 | duplicated regions within figure (conf 0.9326) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk HIGH (score 59.42/100)
> Histological imaging showed virus “escaped” and delivered PAX6 protein to the retina of Sey/+ eyes (A–D) Immunofluorescence staining was performed on paraffin-embedded sections 5 months PI after vehic…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.42/35.0 | duplicated regions within figure (conf 0.9263) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk HIGH (score 59.7/100)
> Significant increase in corneal epithelial thickness after FLAG/ PAX6 injection in Sey/+ eyes (A–D) Quantification of (A) epithelial thickness, (B) epithelial cell count, (C) stromal- endothelial thic…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.7/35.0 | duplicated regions within figure (conf 0.9343) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 27.0/100)
> Correlations show that uninjected contralateral eyes were not impacted by injection in partner eye (A and B) Correlation analysis shows that the uninjected contralateral eyes were not impacted by inje…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk HIGH (score 52.11/100)
> FLAG/PAX6-injected Sey/+ corneas had the most FLAG-PAX6 transcripts, but the difference was not significant (A–C) Transcript levels of virally delivered FLAG-tagged PAX6 (FLAG-PAX6 assay) or endogenou…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.11/35.0 | duplicated regions within figure (conf 0.7175) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk LOW (score 22.29/100)
> Overall significant pattern of the correction of gene transcription back to WT levels (A–D) Endogenous transcript levels in corneas after vehicle or FLAG/PAX6 injection in WT or Sey/+ eyes were quanti…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.29/35.0 | duplicated regions within figure (conf 0.6368) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
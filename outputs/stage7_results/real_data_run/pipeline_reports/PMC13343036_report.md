# ScholarGuard Integrity Report — PMC13343036.pdf

- **Generated:** 2026-07-11T22:22:08
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 43.34/100, 3 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 35.0/100)
> Impaired epithelial maturation and DNA damage in HSCR intestinal epithelium. (A) UMAP representation of epithelial cell subtypes, identifying colonocytes, goblet, tuft, stem, and TA cells, enteroendoc…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.0372) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 44.42/100)
> Suppressed energy programs and focal DNA damage in HSCR colonic epithelium. (A) GO analysis of the distal colon in HSCR, highlighting terms associated with ATP synthesis, electron transport chain acti…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.42/35.0 | duplicated regions within figure (conf 0.9833) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 43.03/100)
> Increased PARP activation in HSCR crypt epithelium. (A) Immunofluorescence staining for PARP1 (red) with DAPI (blue) in crypt regions of control and HSCR distal colon sections. (B) Quantification of P…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.03/35.0 | duplicated regions within figure (conf 0.9437) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
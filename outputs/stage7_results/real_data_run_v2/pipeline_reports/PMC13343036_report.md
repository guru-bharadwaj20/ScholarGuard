# ScholarGuard Integrity Report — PMC13343036.pdf

- **Generated:** 2026-07-12T00:45:46
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 32.33/100, 3 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 20.06/100)
> Impaired epithelial maturation and DNA damage in HSCR intestinal epithelium. (A) UMAP representation of epithelial cell subtypes, identifying colonocytes, goblet, tuft, stem, and TA cells, enteroendoc…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 20.06/35.0 | duplicated regions within figure (conf 0.5732) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 31.87/100)
> Suppressed energy programs and focal DNA damage in HSCR colonic epithelium. (A) GO analysis of the distal colon in HSCR, highlighting terms associated with ATP synthesis, electron transport chain acti…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.87/35.0 | duplicated regions within figure (conf 0.9107) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 33.92/100)
> Increased PARP activation in HSCR crypt epithelium. (A) Immunofluorescence staining for PARP1 (red) with DAPI (blue) in crypt regions of control and HSCR distal colon sections. (B) Quantification of P…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.92/35.0 | duplicated regions within figure (conf 0.9692) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
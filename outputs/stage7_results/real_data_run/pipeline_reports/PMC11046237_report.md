# ScholarGuard Integrity Report — PMC11046237.pdf

- **Generated:** 2026-07-10T09:06:50
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 37.46/100, 8 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 29.88/100)
> Tested Samples of composite.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 19.88/35.0 | duplicated regions within figure (conf 0.5679) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 34.98/100)
> shows the tensile and flexural strength of madar fiber-reinforced porcelain filler particulates embedded within an epoxy matrix composite, as denoted by various samples (C1 to C5). The primary mechani…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.98/35.0 | duplicated regions within figure (conf 0.7138) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 43.52/100)
> shows the Stress vs Strain graph of madar fiber composite during tensile test. Tensile strength demonstrates a material’s resistance to breaking under tension. An upward trend is evident across the sa…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.52/35.0 | duplicated regions within figure (conf 0.9578) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 34.5/100)
> shows the Izod impact strength measures the energy a material absorbs during sudden load, indicating its toughness. While the values are relatively low, there is a discernible increase as one moves fr…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.5/35.0 | duplicated regions within figure (conf 0.7) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 43.53/100)
> shows the SEM analysis of the madar fiber composite, which has provided a microscopic view of the fracture surface of the madar fiber reinforced porcelain nanoparticles blended epoxy matrix composite …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.53/35.0 | duplicated regions within figure (conf 0.9581) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk LOW (score 0.0/100)
> XRD analysis of madar fiber composite sample C5.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk LOW (score 0.0/100)
> FTIR analysis of madar fiber composite sample C5.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 8 — risk LOW (score 0.0/100)
> Antibacterial zone formation of madar fiber composite. T. Raja et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
# ScholarGuard Integrity Report — PMC10979162.pdf

- **Generated:** 2026-07-12T00:33:43
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 29.09/100, 8 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Schematic diagram of low temperature soldering. J. Xiao et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 31.49/100)
> SEM images of copper micron layer morphology:(a) SEM morphology (b) Interface SEM. J. Xiao et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.49/35.0 | duplicated regions within figure (conf 0.8996) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 31.88/100)
> SEM images of morphology for Ag film modified copper micron layer:(a) SEM morphology (b) Cone tip morphology. J. Xiao et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 21.88/35.0 | duplicated regions within figure (conf 0.6252) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk LOW (score 18.72/100)
> SEM images of soldering interface morphology under different conditions:(a) Soldering interface morphology at 200 ◦C, 20 MPa (b) Sol­ dering interface morphology at 210 ◦C, 20 MPa (c) scanline results…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 18.72/35.0 | duplicated regions within figure (conf 0.5348) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 31.12/100)
> Solder interconnect interface TEM analysis results:(a) Low magnification TEM image (b) High magnification TEM image (c) High magni­ fication image of region A (d) Ag elemental surface scan image (e) C…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.12/35.0 | duplicated regions within figure (conf 0.8891) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk LOW (score 15.83/100)
> Relationship between average shear strength of soldered interfaces and hot-pressing conditions.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 15.83/35.0 | duplicated regions within figure (conf 0.4524) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 27.0/100)
> Relationship between average shear strength of soldered interfaces and heat treatment time. J. Xiao et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 8) — risk LOW (score 24.64/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.64/35.0 | duplicated regions within figure (conf 0.704) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
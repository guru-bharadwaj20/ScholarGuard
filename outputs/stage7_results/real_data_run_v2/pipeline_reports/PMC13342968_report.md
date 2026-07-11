# ScholarGuard Integrity Report — PMC13342968.pdf

- **Generated:** 2026-07-11T23:55:31
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 43.01/100, 13 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Menaquinone-7 (MK-7) increases bone mass in aged mice. (A) Schematic diagram illustrating experimental design. (B, C) Micro-computed tomography (micro-CT) reconstructed representative images (B) and q…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk LOW (score 0.0/100)
> Menaquinone-7 (MK-7) rescues cellular senescence and promotes osteogenic differentiation in old primary bone marrow mesenchymal stem cells (BMSCs). (A) Repre- sentative images and quantitative analysi…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk LOW (score 10.0/100)
> Menaquinone-7 (MK-7) restores mitochondrial integrity and function in old primary bone marrow mesenchymal stem cells (BMSCs). (A) Representative images of MitoTracker Green staining for mitochondria a…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk LOW (score 0.0/100)
> Cellular communication network factor 2 (Ccn2) knockdown inhibits osteogenic differentiation and aggravates cellular senescence in old primary bone marrow mesenchymal stem cells (BMSCs). (A) The Venn …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 27.0/100)
> The multidirectional beneficial effect of menaquinone-7 (MK-7) on mitochondria is retarded by cellular communication network factor 2 (Ccn2) knockdown in old primary bone marrow mesenchymal stem cells…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk MODERATE (score 25.63/100)
> Cellular communication network factor 2 (Ccn2) overexpression enhanced menaquinone-7 (MK-7)'s advantageous effect in old primary bone marrow mesenchymal stem cells (BMSCs). (A) Representative images a…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.63/35.0 | duplicated regions within figure (conf 0.7323) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 27.0/100)
> The therapeutic effect of menaquinone-7 (MK-7) on senile osteoporosis relies on cellular communication network factor 2 (Ccn2). (A, B) Micro-computed tomography (micro-CT) reconstructed representative…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 8 — risk LOW (score 24.5/100)
> Pregnane X receptor (PXR) is the nuclear receptor of menaquinone-7 (MK-7) in primary bone marrow mesenchymal stem cells (BMSCs). (A) Western blot for PXR after the total lysate of primary BMSCs was di…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.5/35.0 | duplicated regions within figure (conf 0.7) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 9 — risk HIGH (score 52.52/100)
> Pregnane X receptor (PXR) is essential for the menaquinone-7 (MK-7)-induced activation of the extracellular signal-regulated kinases 1/2 (ERK1/2)/cyclic AMP-responsive element-binding protein (CREB) p…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.52/35.0 | duplicated regions within figure (conf 0.7292) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 10 — risk LOW (score 0.0/100)
> Schematic diagram demonstrating menaquinone-7 (MK-7) restores mitochondrial function and determines the fate of bone marrow mesenchymal stem cells (BMSCs) via mitophagy pathways. Upon the binding of M…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 18) — risk MODERATE (score 31.45/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.45/35.0 | duplicated regions within figure (conf 0.8985) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 19) — risk MODERATE (score 47.08/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 20.08/35.0 | duplicated regions within figure (conf 0.5736) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 20) — risk MODERATE (score 25.56/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.56/35.0 | duplicated regions within figure (conf 0.7303) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
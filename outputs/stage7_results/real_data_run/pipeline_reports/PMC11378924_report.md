# ScholarGuard Integrity Report — PMC11378924.pdf

- **Generated:** 2026-07-10T08:52:37
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 73.28/100, 20 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 29.88/100)
> Schematic illustration of methodology. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 19.88/35.0 | duplicated regions within figure (conf 0.5679) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 43.83/100)
> SEM images of ball milled powder at (a)5hrs (b)10 h and (c)15hrs, (d) 20hrs, (e) magnified image of powder morphology of 20hrs ball milled AlBeSiTiV HEA powder and (f)EDS spectra of AlBeSiTiV HEA powd…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.83/35.0 | duplicated regions within figure (conf 0.9667) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk HIGH (score 71.15/100)
> EDS mapping of 20 h ball milled AlBeSiTiV HEA powder representing HEA elements with corresponding XRD. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.15/35.0 | duplicated regions within figure (conf 0.9757) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk HIGH (score 69.26/100)
> XRD pattern of powder after (a)5hrs (b)10 h and (c)15hrs and (d) 20hrs ball milling.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.26/35.0 | duplicated regions within figure (conf 0.9218) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 34.04/100)
> SEM image of (a) AlBeSiTiV coated surface (b) EDS spectra of coating (c) cross-sectional view of substrate and coating (d) porosity analysis image and (e) XRD pattern of the coated surface. A. Singh e…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.04/35.0 | duplicated regions within figure (conf 0.9727) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk MODERATE (score 44.7/100)
> depicts the elemental mapping analysis of the AlBeSiTiV HEA coating. In spite of the contribution of major elements including Al, Be, Si, V, and Ti, a small amount of O is present due to the formation…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.7/35.0 | duplicated regions within figure (conf 0.9915) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk HIGH (score 71.78/100)
> EDS Line mapping of the (a)substrate, (b)Substrate, and coating, (c) Coating.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.78/35.0 | duplicated regions within figure (conf 0.9937) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 8 — risk MODERATE (score 45.0/100)
> EBSD results of AlBeSiTiV LWHEA coating: (a,b) inverse pole figure (IPF) map of the coated surface, (c) phase image of coating (d) graphical representation of grain size distribution along with coatin…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.0628) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 9 — risk MODERATE (score 34.5/100)
> (a)KAM mapping, (b)Schmid factor diagram, (c,d) pole figure and inverse pole figures of AlBeSiTiV coating.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.5/35.0 | duplicated regions within figure (conf 0.7) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 10 — risk MODERATE (score 38.14/100)
> illustrates the microhardness measured from the interface of the AlBeSiTiV HEA coating/substrate. The mean micro­ hardness of the substrate 316 SS was 172.8 ± 10 HV in the range of (−50 μm to −150 μm)…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.14/35.0 | duplicated regions within figure (conf 0.804) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 11 — risk MODERATE (score 45.0/100)
> (a) Main effect plot of means, (b) main effects plot of S/N ratio. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.1962) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 12 — risk MODERATE (score 44.22/100)
> The linear normal probability plot indicates that the residual errors of the model are normally distributed, and the model’s coefficients are significant. The normal probability values were found to b…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.22/35.0 | duplicated regions within figure (conf 0.9776) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 13 — risk MODERATE (score 45.0/100)
> depicts the SEM images of the worn surface at 15N and 35N, keeping velocity 2 m/s and distance 1000 m constant. It was observed that when a low load of 15N was applied, the worn surface displayed shal…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 0.9999) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 14 — risk HIGH (score 62.31/100)
> (a) SEM image of wear debris, (b) corresponding EDS at 35 N, (c, d) schematic representation of wear mechanism. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.31/35.0 | duplicated regions within figure (conf 0.7231) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 15 — risk HIGH (score 71.18/100)
> Worn surface micrographs of coated samples at (a)1 m/s, (b)2 m/s, (c) 3 m/s.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.18/35.0 | duplicated regions within figure (conf 0.9766) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 16 — risk HIGH (score 72.0/100)
> (a) SEM image of wear debris and (b) corresponding EDS at 3 m/s. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.4933) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 17 — risk CRITICAL (score 80.78/100)
> Worn surface micrographs of coated samples at (a)500m, (b)1000m, (c) 1500m, (d) Raman spectra of oxide layer developed. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.78/35.0 | duplicated regions within figure (conf 0.9651) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 20.0/20.0 | AI-generation verdict: likely_ai_generated (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 18 — risk HIGH (score 71.93/100)
> (a) SEM image of wear debris, (b) corresponding EDS at 1500m, (c) schematic representation of MML formation. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.93/35.0 | duplicated regions within figure (conf 0.998) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 19 — risk HIGH (score 70.55/100)
> Elemental mapping of wear debris at 1500m. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.55/35.0 | duplicated regions within figure (conf 0.9585) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 19) — risk HIGH (score 70.58/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.58/35.0 | duplicated regions within figure (conf 0.9595) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
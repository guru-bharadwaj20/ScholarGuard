# ScholarGuard Integrity Report — PMC11378924.pdf

- **Generated:** 2026-07-12T00:09:59
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 52.77/100, 20 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Schematic illustration of methodology. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 29.27/100)
> SEM images of ball milled powder at (a)5hrs (b)10 h and (c)15hrs, (d) 20hrs, (e) magnified image of powder morphology of 20hrs ball milled AlBeSiTiV HEA powder and (f)EDS spectra of AlBeSiTiV HEA powd…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 29.27/35.0 | duplicated regions within figure (conf 0.8364) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 47.69/100)
> EDS mapping of 20 h ball milled AlBeSiTiV HEA powder representing HEA elements with corresponding XRD. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 20.69/35.0 | duplicated regions within figure (conf 0.5911) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 49.58/100)
> XRD pattern of powder after (a)5hrs (b)10 h and (c)15hrs and (d) 20hrs ball milling.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.58/35.0 | duplicated regions within figure (conf 0.6452) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk LOW (score 18.64/100)
> SEM image of (a) AlBeSiTiV coated surface (b) EDS spectra of coating (c) cross-sectional view of substrate and coating (d) porosity analysis image and (e) XRD pattern of the coated surface. A. Singh e…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 18.64/35.0 | duplicated regions within figure (conf 0.5327) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk LOW (score 24.28/100)
> depicts the elemental mapping analysis of the AlBeSiTiV HEA coating. In spite of the contribution of major elements including Al, Be, Si, V, and Ti, a small amount of O is present due to the formation…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.28/35.0 | duplicated regions within figure (conf 0.6938) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 42.9/100)
> EDS Line mapping of the (a)substrate, (b)Substrate, and coating, (c) Coating.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 15.9/35.0 | duplicated regions within figure (conf 0.4542) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 8 — risk MODERATE (score 31.05/100)
> EBSD results of AlBeSiTiV LWHEA coating: (a,b) inverse pole figure (IPF) map of the coated surface, (c) phase image of coating (d) graphical representation of grain size distribution along with coatin…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.05/35.0 | duplicated regions within figure (conf 0.8872) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 9 — risk LOW (score 24.87/100)
> (a)KAM mapping, (b)Schmid factor diagram, (c,d) pole figure and inverse pole figures of AlBeSiTiV coating.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.87/35.0 | duplicated regions within figure (conf 0.7107) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 10 — risk MODERATE (score 28.52/100)
> illustrates the microhardness measured from the interface of the AlBeSiTiV HEA coating/substrate. The mean micro­ hardness of the substrate 316 SS was 172.8 ± 10 HV in the range of (−50 μm to −150 μm)…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.52/35.0 | duplicated regions within figure (conf 0.815) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 11 — risk MODERATE (score 28.55/100)
> (a) Main effect plot of means, (b) main effects plot of S/N ratio. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.55/35.0 | duplicated regions within figure (conf 0.8156) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 12 — risk MODERATE (score 27.91/100)
> The linear normal probability plot indicates that the residual errors of the model are normally distributed, and the model’s coefficients are significant. The normal probability values were found to b…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 27.91/35.0 | duplicated regions within figure (conf 0.7974) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 13 — risk MODERATE (score 26.1/100)
> depicts the SEM images of the worn surface at 15N and 35N, keeping velocity 2 m/s and distance 1000 m constant. It was observed that when a low load of 15N was applied, the worn surface displayed shal…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 26.1/35.0 | duplicated regions within figure (conf 0.7457) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 14 — risk HIGH (score 55.99/100)
> (a) SEM image of wear debris, (b) corresponding EDS at 35 N, (c, d) schematic representation of wear mechanism. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.99/35.0 | duplicated regions within figure (conf 0.8282) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 15 — risk MODERATE (score 27.0/100)
> Worn surface micrographs of coated samples at (a)1 m/s, (b)2 m/s, (c) 3 m/s.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 16 — risk HIGH (score 55.19/100)
> (a) SEM image of wear debris and (b) corresponding EDS at 3 m/s. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.19/35.0 | duplicated regions within figure (conf 0.8054) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 17 — risk HIGH (score 59.98/100)
> Worn surface micrographs of coated samples at (a)500m, (b)1000m, (c) 1500m, (d) Raman spectra of oxide layer developed. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.98/35.0 | duplicated regions within figure (conf 0.6567) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 18 — risk HIGH (score 54.77/100)
> (a) SEM image of wear debris, (b) corresponding EDS at 1500m, (c) schematic representation of MML formation. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 27.77/35.0 | duplicated regions within figure (conf 0.7935) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 19 — risk HIGH (score 59.66/100)
> Elemental mapping of wear debris at 1500m. A. Singh et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.66/35.0 | duplicated regions within figure (conf 0.933) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 19) — risk MODERATE (score 27.0/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
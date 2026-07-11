# ScholarGuard Integrity Report — PMC11327604.pdf

- **Generated:** 2026-07-12T00:22:30
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 53.35/100, 12 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> 3D and 2D interactions of antioxidant and apoptosis-related targets with predicted compounds GA (370) and EA (5281855). RGZ (77999) and RSV (445154) were used as control drugs. (A) BAX (3PL7) interact…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 33.19/100)
> Effects of PG-F on the cell viability assessed using an MTT assay. (A) Survival rate of SH-SY5Y cells at various H2O2 concentrations. (B) Survival rate of SH-SY5Y cells in response to various PG-F con…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.19/35.0 | duplicated regions within figure (conf 0.9482) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk HIGH (score 56.66/100)
> Treatment with PG-F effectively attenuated the H2O2-induced damage in SH-SY5Y cells. (A) Representative images of cell apoptosis assessed through Hoechst 33342 staining. (a) Control, (b) 200 μM H2O2, …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 29.66/35.0 | duplicated regions within figure (conf 0.8473) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 33.14/100)
> PG-F stabilizes MMP as stained by Rho-123. (a) Cells without treatment, (b) H2O2 (200 μM) significantly decreased the mitochondria membrane potential, (c) cells treated with (10 μg mL−1 PG-F + 200 μM …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.14/35.0 | duplicated regions within figure (conf 0.9469) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk HIGH (score 58.78/100)
> Effect of PG-F on the formation of intracellular ROS was evaluated by treating SH-SY5Y cells with H2O2. (A) ROS generation in SH-SY5Y cells triggered by H2O2 was investigated using DCFH-DA staining. (…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.78/35.0 | duplicated regions within figure (conf 0.9081) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk HIGH (score 59.23/100)
> Enzymatic experiment was used to assess the impact of PG-F on the (a) SOD, (b) CAT, and (c) GPx activities. The data are expressed as the mean ± SD from three separate experiments. ###p < 0.001, indic…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.23/35.0 | duplicated regions within figure (conf 0.921) |
| cross_figure | ok | 27.0/30.0 | 3 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 37.0/100)
> Corresponding gene expression levels of the antioxidant markers (a) SOD, (b) Cat, (c) GPx, (d) Nrf2, (e) HO-1, and (f) Keap1 under H2O2- stressed cells (SH-SY5Y). Before H2O2 exposure, the cells were …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 4 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 8 — risk MODERATE (score 44.07/100)
> Corresponding expression levels of apoptotic markers (a) Bax, (b) Bcl-2, (c) Bax/bcl2 (d) Caspase-3, (e) Caspase-7, and (f) Caspase-9 were investigated in H2O2-stressed SH-SY5Y cells. Before H2O2 expo…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 17.07/35.0 | duplicated regions within figure (conf 0.4876) |
| cross_figure | ok | 27.0/30.0 | 4 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 9 — risk MODERATE (score 46.1/100)
> Relative gene expression levels of the MAPK signaling components (a) P38, (b) JNK, and (c) ERK were investigated in H2O2-stressed SH- SY5Y cells. Before H2O2 exposure, the cells were pretreated with P…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 19.1/35.0 | duplicated regions within figure (conf 0.5456) |
| cross_figure | ok | 27.0/30.0 | 4 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 10 — risk MODERATE (score 27.0/100)
> Modulatory effects of PG-F pretreatment on protein translation in H2O2-induced SH-SY5Y cells. (a) western blot images for (b) cleaved caspase-3, (c) cleaved caspase-9, (d) p-p38, and (e) Nrf2 regulati…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 5 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 11 — risk HIGH (score 56.08/100)
> presents the drug–drug interaction data, which underwent analysis through CompuSyn software. Using a constant ratio combination facilitated the computerized simulation of the dose-effect curves (Fig. …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 29.08/35.0 | duplicated regions within figure (conf 0.831) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 14) — risk LOW (score 24.31/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.31/35.0 | duplicated regions within figure (conf 0.6947) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
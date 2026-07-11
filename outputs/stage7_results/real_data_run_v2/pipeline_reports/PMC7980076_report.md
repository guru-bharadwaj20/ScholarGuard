# ScholarGuard Integrity Report — PMC7980076.pdf

- **Generated:** 2026-07-12T00:44:10
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 57.2/100, 18 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Representative images of H&E stained rat gastric tissue sections of the different groups (n ¼ 6) : (CON)–Control rats, (ADR 0.3) - only adrenaline treated rats at 0.3 mg/kg bw, (OA2.5,OA5,OA10,OA20) –…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 33.07/100)
> Acid Sirius staining of rat gastric tissue. Panel A represents the light photomicrographs of gastric tissue sections of various groups (n ¼ 6): (CON) – Control rats, (ADR 0.3) - only adrenaline treate…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.07/35.0 | duplicated regions within figure (conf 0.945) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 31.8/100)
> Representative scanning electron microscope images of rat gastric tissue indicating a dose-dependent protection by oleic acid of the following groups (n ¼ 6): (CON) – Control rats, (ADR 0.3) - only ad…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.8/35.0 | duplicated regions within figure (conf 0.9087) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 26.83/100)
> represents the changes in biomarkers of oxidative stress following adrenaline bitartrate treatment and the protection rendered by pre-treatment of rats with oleic acid at increasing doses, the maximum…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 26.83/35.0 | duplicated regions within figure (conf 0.7665) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 27.93/100)
> Dose-dependent protection by oleic acid against adrenaline–induced alterations in biomarkers of oxidative stress in rat gastric tissue such as (A) Level of reduced glutathione content,(B) Level of oxi…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 27.93/35.0 | duplicated regions within figure (conf 0.7981) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk HIGH (score 60.3/100)
> Dose-dependent protection by oleic acid against adrenaline–induced alterations in the activities of antioxidant enzymes of the rat gastric tissue such as (A) Cu-ZnSOD, (B) MnSOD, (C) Catalase as obser…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.3/35.0 | duplicated regions within figure (conf 0.9514) |
| cross_figure | ok | 27.0/30.0 | 7 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk HIGH (score 57.11/100)
> shows that treatment of rats with adrenaline bitartrate at a dose of 0.3 mg/kg bw. (ADR 0.3) s.c., every day for a period of 17 days

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 30.11/35.0 | duplicated regions within figure (conf 0.8604) |
| cross_figure | ok | 27.0/30.0 | 4 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 8 — risk HIGH (score 58.82/100)
> Protein concentration-dependent changes in the activities of mitochondrial marker enzymes of rat gastric tissue namely (A) Succinate dehydrogenase enzyme (SDH) and (B) Gastric peroxidase (GPO) of cont…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.82/35.0 | duplicated regions within figure (conf 0.9091) |
| cross_figure | ok | 27.0/30.0 | 6 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 9 — risk HIGH (score 62.11/100)
> demonstrates that treatment of rats with adrenaline bitar- trate (ADR 0.3) at the above mentioned dose and time period signiﬁ- cantly (*p < 0.001 vs. control group) decreased both cytochrome-c- oxidas…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.11/35.0 | duplicated regions within figure (conf 0.7173) |
| cross_figure | ok | 27.0/30.0 | 7 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 10 — risk HIGH (score 50.71/100)
> Dose-dependent protection by oleic acid against adrenaline–induced alterations in the activities of enzymes related to energy metabolism of rat gastric tissue namely (A) Pyruvate dehydrogenase, (B) Is…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 23.71/35.0 | duplicated regions within figure (conf 0.6775) |
| cross_figure | ok | 27.0/30.0 | 5 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 11 — risk HIGH (score 59.6/100)
> The Lineweaver Burk double reciprocal plots of the activities of enzymes related to energy metabolism of rat gastric tissue: (A) Pyruvate dehydrogenase, (B) Isocitrate dehydrogenase, (C) Alpha-ketoglu…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.6/35.0 | duplicated regions within figure (conf 0.6458) |
| cross_figure | ok | 27.0/30.0 | 5 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 12 — risk HIGH (score 57.38/100)
> The Eadie-Hofstee plots of the activities of enzymes related to energy metabolism of rat gastric tissue: (A) Pyruvate dehydrogenase, (B) Isocitrate de- hydrogenase, (C) Alpha-ketoglutarate dehydrogena…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 30.38/35.0 | duplicated regions within figure (conf 0.8679) |
| cross_figure | ok | 27.0/30.0 | 5 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 13 — risk HIGH (score 55.95/100)
> depicts the images obtained through SEM of gastric mito- chondria at 20000X magniﬁcation. The mitochondria obtained from adrenaline bitartrate (0.3 mg/kg bw. s.c.) treated rat stomach tissues were fou…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.95/35.0 | duplicated regions within figure (conf 0.827) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 14 — risk HIGH (score 55.48/100)
> Effect of ascorbic acid, melatonin and oleic acid on adrenaline mediated changes in (A) lipid peroxidation and (B) reduced glutathione content in isolated rat gastric tissue mitochondria, C¼Control, O…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.48/35.0 | duplicated regions within figure (conf 0.8137) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 15 — risk MODERATE (score 37.52/100)
> Changes in different parameters upon oleic acid treatment against adrenaline–induced alterations in (A) Body weight of rats of different groups, (B) Serum SGPT activity and (D) Serum Lactate dehydroge…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 27.52/35.0 | duplicated regions within figure (conf 0.7862) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 16 — risk HIGH (score 60.15/100)
> Representative images of H&E stained rat liver tissue sections of the different groups (n ¼ 6) : (CON) – Control rats, (ADR 0.3) - only adrenaline treated rats at 0.3 mg/kg bw, (OA2.5, OA5,OA10, OA20)…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 23.15/35.0 | duplicated regions within figure (conf 0.6613) |
| cross_figure | ok | 27.0/30.0 | 3 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 15) — risk HIGH (score 59.91/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.91/35.0 | duplicated regions within figure (conf 0.9403) |
| cross_figure | ok | 27.0/30.0 | 4 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 16) — risk MODERATE (score 28.42/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.42/35.0 | duplicated regions within figure (conf 0.812) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
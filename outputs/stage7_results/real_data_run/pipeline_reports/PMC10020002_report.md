# ScholarGuard Integrity Report — PMC10020002.pdf

- **Generated:** 2026-07-10T09:09:49
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 42.75/100, 8 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 29.88/100)
> Significant gene functions and signaling pathways enriched for differentially expressed genes. (A) Significant gene functions of DP/ HC differential gene enrichment; (B) Significant gene functions of …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 19.88/35.0 | duplicated regions within figure (conf 0.5679) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk LOW (score 20.0/100)
> Verification of the expression levels of eight differentially expressed miRNAs in three groups of serum samples by PCR. (A) Quantitative real-time PCR was used to detect the expression levels of sever…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 20.0/20.0 | AI-generation verdict: likely_ai_generated (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 45.0/100)
> Effects of miR-1281 on the expression levels of wild-type and mutant ADCY1/DVL1-transfected cells. (A–B) ADCY1 and DVL1 mutation sites. (C–D) The miR-1281 overexpression plasmid was cotransfected with…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.1268) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 45.0/100)
> Expression levels of miR-1281, ADCY1 and DVL1 in corticosterone-injured SH-SY5Y cells and after KXS treatment. Compared with the control group, #P < 0.05, ##P < 0.01, ###P < 0.001, ####P < 0.0001 comp…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.1302) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 35.0/100)
> Effects of KXS on the viability and apoptosis of miR-1281-overexpressing SH-SY5Y cells and the relative expression levels of miR- 1281 and target genes. (A) A-1 is a virus-infected cell; A-2 is a DAPI…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 2.3079) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk MODERATE (score 45.0/100)
> Effects of KXS on the cAMP/PKA/ERK/CREB and Wnt/β-catenin signaling pathways in cells after miR-1281 overexpression. Western blot was used to detect the effects of miR-1281 overexpression on cAMP/PKA/…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.2616) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 11) — risk MODERATE (score 45.0/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.0027) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 12) — risk MODERATE (score 35.0/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 4.71) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
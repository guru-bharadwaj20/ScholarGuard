# ScholarGuard Integrity Report — PMC11128842.pdf

- **Generated:** 2026-07-12T00:27:20
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 47.07/100, 6 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Detection of expression of IFITM1, β-catenin, P-gp, CyclinD1 and c-Myc in clinical specimens from SCLC patients A) RT-qPCR was used to detect the relative contents of IFITM1 mRNA in 24 tumor tissues o…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 25.87/100)
> Silencing of IFITM1 gene in cisplatin resistant SCLC cells and overexpression of IFITM1 in their parent cells by using lentivirus A) IC50 value analysis of cisplatin-resistant SCLC cells (NCI–H466 and…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.87/35.0 | duplicated regions within figure (conf 0.7391) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk HIGH (score 55.95/100)
> Evaluation of the effect of IFITM1 gene intervention on the chemotherapy sensitivity of cisplatin-resistant SCLC cells to cisplatin Prolif­ eration of cells was determined using CCK-8 assay. The x-coo…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.95/35.0 | duplicated regions within figure (conf 0.827) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk LOW (score 21.93/100)
> Evaluation of the effect of IFITM1 silencing on invasion and expression of relating proteins under treatment of cisplatin A) An in vitro cell invasion assay by using trans-well method. DAPI was used t…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 21.93/35.0 | duplicated regions within figure (conf 0.6266) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 32.36/100)
> Validation the effect of IFITM1 silencing on acquired resistance of SCLC to cisplatin in vivo A) Subcutaneous tumor growth curves were performed according to the xenograft tumor volumes of 4 groups. T…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.36/35.0 | duplicated regions within figure (conf 0.9245) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 9) — risk LOW (score 21.92/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 21.92/35.0 | duplicated regions within figure (conf 0.6262) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
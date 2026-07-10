# ScholarGuard Integrity Report — PMC11388766.pdf

- **Generated:** 2026-07-10T08:04:56
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 43.62/100, 8 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 29.88/100)
> Construction of extrahepatic cholangiocarcinoma organoids and TAMs co-culture system. (A) Study design used to create co-culture system from eCCA patients. (B) Morphology of eCCA organoids with TAMs i…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 19.88/35.0 | duplicated regions within figure (conf 0.5679) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 44.02/100)
> Histopathological characterization comparing eCCA organoids from mono-culture and co-culture models and corresponding specimens. (A–B) Representative H&E staining of eCCA specimens and organoids (spec…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 34.02/35.0 | duplicated regions within figure (conf 0.9719) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 42.33/100)
> General genetic alterations in two original specimens and organoids. (A) Number of SNP in different regions of the genome (left) and number of different types of SNP in the coding region (right) from …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.33/35.0 | duplicated regions within figure (conf 0.9237) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 41.34/100)
> Detailed genetic profiles of six original specimens and organoids. (A) Representative driver genes of the specimens and organoids are presented. The horizontal coordinate is the sample (P: specimens; …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.34/35.0 | duplicated regions within figure (conf 0.8954) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 45.0/100)
> Organoids response to gemcitabine and cisplatin. (A) Representative images showing patient 2 organoids from the two models response to gemcitabine (magnification, 100×). (B) Dose-response curves of or…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.178) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk MODERATE (score 41.2/100)
> Organoids response to 5-fluorouracil and paclitaxel. (A) Representative images showing patient 6 organoids from the two models response to 5-fluorouracil(magnification, 100×). (B–D) Dose-response curv…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.2/35.0 | duplicated regions within figure (conf 0.8913) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 45.0/100)
> TAMs promotes the growth of eCCA organoids in vitro and in vivo. (A) Representative images of eCCA organoids in mono-culture and co- culture(magnification, 40×). (B) Diameters of eCCA organoids cultur…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.0487) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 10) — risk MODERATE (score 34.5/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.5/35.0 | duplicated regions within figure (conf 0.7) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
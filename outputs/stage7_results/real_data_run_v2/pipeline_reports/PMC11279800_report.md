# ScholarGuard Integrity Report — PMC11279800.pdf

- **Generated:** 2026-07-12T00:16:46
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 43.41/100, 6 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Expression and purification study of AtMYB12. (a) Diagrammatic representation of domain architecture of AtMYB12 and its N-terminal deletion forms. (b) SWISS-PROT structure prediction study of full-len…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 33.39/100)
> Tryptophan fluorescence spectra and urea-induced denaturation profiles of AtMYB12, AtMYB12Δ1, and AtMYB12Δ2 under control and UV- B treatment. (a–c) Purified recombinant AtMYB12, AtMYB12Δ1, and AtMYB1…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.39/35.0 | duplicated regions within figure (conf 0.954) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 32.67/100)
> Determination of surface hydrophobicity and reverse titration of AtMYB12 and N-terminal deletion forms. (a–c) Bis-ANS binding titration of AtMYB12, AtMYB12Δ1, and AtMYB12Δ2 under (a) control and (b–c)…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 32.67/35.0 | duplicated regions within figure (conf 0.9335) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 49.55/100)
> Study of secondary structure and aggregation pattern of AtMYB12, AtMYB12Δ1, and AtMYB12Δ2. (a–c) Far UV-CD spectra of AtMYB12, AtMYB12Δ1, and AtMYB12Δ2 under (a) control and (b–c) UV-B irradiation for…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.55/35.0 | duplicated regions within figure (conf 0.6443) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 25.65/100)
> Schematic model illustrating the important function of two N-terminal MYB domains of MYB12 transcription factor in the maintenance of protein structural conformation and stability. Elimination of the …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.65/35.0 | duplicated regions within figure (conf 0.7329) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 10) — risk MODERATE (score 33.28/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.28/35.0 | duplicated regions within figure (conf 0.951) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
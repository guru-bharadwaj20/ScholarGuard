# ScholarGuard Integrity Report — PMC10692775.pdf

- **Generated:** 2026-07-11T22:20:42
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 41.82/100, 6 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 29.88/100)
> a. XRD pattern of a) undoped NiCr2O4 (0.00 %) and (b–e), c), La-doped (0.01, 0.02, 0.03 and 0.04 %) NiCr2O4, Fig. 1 b. XRD pattern of (2Ɵ value 20–50) undoped and doped NiCr2O4 and (Fig. 1 c) XRD patt…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 19.88/35.0 | duplicated regions within figure (conf 0.5679) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 43.37/100)
> FT-IR Spectra of a) undoped NiCr2O4 (0.00 %) and (b–e), La-doped (0.01, 0.02, 0.03 and 0.04 %) NiCr2O4. C. Ragupathi et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.37/35.0 | duplicated regions within figure (conf 0.9533) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 45.0/100)
> HR-TEM images of a) undoped NiCr2O4 (0.00 %) and (b–e) La-doped (0.01, 0.02, 0.03 and 0.04 %) NiCr2O4. Scheme 2. TEM image that the NiCr2O4 and La–NiCr2O4 difference of the radius. C. Ragupathi et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 4.6101) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 45.0/100)
> UV–Visible absorption spectrum of a) undoped NiCr2O4 (0.00 %) and (b–e) La-doped (0.01, 0.02, 0.03 and 0.04 %) NiCr2O4.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.0293) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 43.17/100)
> PL spectra spectrum of a) undoped NiCr2O4 (0.00 %) and (b–e) La-doped (0.01, 0.02, 0.03 and 0.04 %) NiCr2O4. C. Ragupathi et al.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.17/35.0 | duplicated regions within figure (conf 0.9476) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk LOW (score 0.0/100)
> The PL intensity decreases with the increase of the dopant La. The decrease in the intensity of the PL spectrum might be because of the decrease in particle size affirmed by XRD and TEM investigations…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
# ScholarGuard Integrity Report — PMC13342975.pdf

- **Generated:** 2026-07-11T23:44:02
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 51.1/100, 7 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Workflow of experimental procedures. M. Akhbari et al. IBRO Neuroscience Reports 21 (2026) 199–206 200

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk LOW (score 0.0/100)
> The effect of S. boulardii administration (gavage, four weeks, 1010 CFU/rat/day) on spatial learning and memory in LPS-induced (250 µg/kg/day, i.p., for 9 days), rats. a) Escape latency to locate the …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk LOW (score 10.0/100)
> The effect of S. boulardii (gavage, four weeks, 1010 CFU/rat/day) on downstream effectors within the TLR4 neuroinflammatory signaling pathway and hippocampal inflammatory cytokines in LPS-stimulated (…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 26.17/100)
> The effect of S. boulardii (gavage, four weeks, 1010 CFU/rat/day) pretreatment on LPS-induced (250 µg/kg/day, i.p., for 9 days) neuronal loss in the hip­ pocampus. a) Representative images of Nissl-st…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 26.17/35.0 | duplicated regions within figure (conf 0.7476) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 4) — risk HIGH (score 60.37/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.37/35.0 | duplicated regions within figure (conf 0.9534) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 5) — risk HIGH (score 51.45/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.45/35.0 | duplicated regions within figure (conf 0.6986) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 6) — risk HIGH (score 58.37/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.37/35.0 | duplicated regions within figure (conf 0.8962) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
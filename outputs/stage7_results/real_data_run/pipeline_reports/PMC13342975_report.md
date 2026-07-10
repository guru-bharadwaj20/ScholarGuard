# ScholarGuard Integrity Report — PMC13342975.pdf

- **Generated:** 2026-07-10T08:23:29
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 65.07/100, 7 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 36.96/100)
> Workflow of experimental procedures. M. Akhbari et al. IBRO Neuroscience Reports 21 (2026) 199–206 200

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 26.96/35.0 | duplicated regions within figure (conf 0.7703) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 39.06/100)
> The effect of S. boulardii administration (gavage, four weeks, 1010 CFU/rat/day) on spatial learning and memory in LPS-induced (250 µg/kg/day, i.p., for 9 days), rats. a) Escape latency to locate the …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 29.06/35.0 | duplicated regions within figure (conf 0.8302) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk LOW (score 20.0/100)
> The effect of S. boulardii (gavage, four weeks, 1010 CFU/rat/day) on downstream effectors within the TLR4 neuroinflammatory signaling pathway and hippocampal inflammatory cytokines in LPS-stimulated (…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 20.0/20.0 | AI-generation verdict: likely_ai_generated (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 35.0/100)
> The effect of S. boulardii (gavage, four weeks, 1010 CFU/rat/day) pretreatment on LPS-induced (250 µg/kg/day, i.p., for 9 days) neuronal loss in the hip­ pocampus. a) Representative images of Nissl-st…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.0244) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 4) — risk HIGH (score 72.0/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.1069) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 5) — risk HIGH (score 72.0/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.5525) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 6) — risk HIGH (score 67.23/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 30.23/35.0 | duplicated regions within figure (conf 0.8638) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
# ScholarGuard Integrity Report — PMC13344374.pdf

- **Generated:** 2026-07-11T23:41:47
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 49.98/100, 7 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## (uncaptioned figure, page 1) — risk LOW (score 0.0/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 15) — risk HIGH (score 55.65/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.65/35.0 | duplicated regions within figure (conf 0.8187) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 17) — risk MODERATE (score 48.46/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 21.46/35.0 | duplicated regions within figure (conf 0.6131) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 19) — risk MODERATE (score 33.6/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.6/35.0 | duplicated regions within figure (conf 0.96) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 21) — risk HIGH (score 56.59/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 29.59/35.0 | duplicated regions within figure (conf 0.8454) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 23) — risk LOW (score 15.98/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 15.98/35.0 | duplicated regions within figure (conf 0.4567) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 24) — risk MODERATE (score 31.51/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.51/35.0 | duplicated regions within figure (conf 0.9004) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
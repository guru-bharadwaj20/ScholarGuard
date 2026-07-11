# ScholarGuard Integrity Report — PMC9069901.pdf

- **Generated:** 2026-07-12T00:02:58
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 54.85/100, 7 figure(s))

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

## (uncaptioned figure, page 3) — risk HIGH (score 58.12/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.12/35.0 | duplicated regions within figure (conf 0.8891) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 4) — risk HIGH (score 54.78/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 27.78/35.0 | duplicated regions within figure (conf 0.7937) |
| cross_figure | ok | 27.0/30.0 | 3 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 4) — risk HIGH (score 56.52/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 29.52/35.0 | duplicated regions within figure (conf 0.8434) |
| cross_figure | ok | 27.0/30.0 | 3 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 5) — risk HIGH (score 58.65/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 31.65/35.0 | duplicated regions within figure (conf 0.9042) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 6) — risk MODERATE (score 49.62/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.62/35.0 | duplicated regions within figure (conf 0.6464) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 7) — risk MODERATE (score 44.1/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 17.1/35.0 | duplicated regions within figure (conf 0.4885) |
| cross_figure | ok | 27.0/30.0 | 4 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
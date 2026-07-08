# ScholarGuard Integrity Report — clean_doseresponse_02.pdf

- **Generated:** 2026-07-08T23:36:31
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 48.24/100, 3 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk HIGH (score 52.8/100)
> Dose-response at 1 uM (n = 4).

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 22.8/35.0 | duplicated regions within figure (conf 0.6513) |
| cross_figure | ok | 30.0/30.0 | 2 near-exact duplicate figure(s) |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 30.0/100)
> Dose-response at 10 uM (n = 4).

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 30.0/30.0 | 2 near-exact duplicate figure(s) |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 30.0/100)
> Dose-response at 100 uM (n = 4).

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 30.0/30.0 | 2 near-exact duplicate figure(s) |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
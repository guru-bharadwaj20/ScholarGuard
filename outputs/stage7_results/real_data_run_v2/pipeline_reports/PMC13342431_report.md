# ScholarGuard Integrity Report — PMC13342431.pdf

- **Generated:** 2026-07-12T00:49:54
- **Status:** completed
- **Overall paper risk:** **MODERATE** (score 45.27/100, 7 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk MODERATE (score 25.04/100)
> Overview of study selection process.

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.04/35.0 | duplicated regions within figure (conf 0.7155) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 29.61/100)
> Risk-of-bias. (a) Traffic light plots for quality assessment of RCTs. (b) Summary plot for quality assessment of RCTs. (c) Traffic light plots for quality assessment of cohort studies. (d) Summary plo…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 29.61/35.0 | duplicated regions within figure (conf 0.8459) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk LOW (score 24.64/100)
> Forest plot of Helicobacter pylori eradication rate (pairwise meta-analysis). (a) Forest plot of the ITT analysis of H. pylori eradication rate (pairwise meta-analysis). (b) Forest plot of the PP anal…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 24.64/35.0 | duplicated regions within figure (conf 0.7039) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk HIGH (score 55.22/100)
> Sensitivity analysis plot of Helicobacter pylori (H. pylori) eradication rate (pairwise meta-analysis). (a) Sensitivity analysis plot of the ITT analysis of H. pylori eradication rate (pairwise meta-a…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 28.22/35.0 | duplicated regions within figure (conf 0.8063) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk LOW (score 19.75/100)
> Forest plot and sensitivity analysis plot of Helicobacter pylori (H. pylori) eradication rate (meta-analysis of proportions). (a) Forest plot of the ITT analysis of H. pylori eradication rate (meta-an…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 19.75/35.0 | duplicated regions within figure (conf 0.5642) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk LOW (score 0.0/100)
> Funnel plot of Helicobacter pylori (H. pylori) eradication rate. (a) Funnel plot for the ITT analysis of H. pylori eradication rate (pairwise meta-analysis). (b) Funnel plot for the PP analysis of H. …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk LOW (score 0.0/100)
> Heterogeneity between studies was low (I2 = 25%, and p = 0.17). A meta-analysis of proportions from 15 studies showed that the pooled adverse reaction rate for minocycline-containing regimens was 0.29…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
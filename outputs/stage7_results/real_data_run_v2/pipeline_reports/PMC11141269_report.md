# ScholarGuard Integrity Report — PMC11141269.pdf

- **Generated:** 2026-07-12T00:28:18
- **Status:** completed
- **Overall paper risk:** **LOW** (score 19.64/100, 11 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Transcritical bifurcation diagram and MLE for model (1.2) with 𝜍1 = 1.1, 𝜚1 = 0.9, 𝛾1 ∈[0.4, 0.9], Υ1 = 0.08 and initial conditions (𝑥0, 𝑦0) = (0.1111, 0.0001): (a), (c) bifurcation diagram for 𝑥𝑛, (b…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk MODERATE (score 27.0/100)
> NS-bifurcation diagram and MLE for model (1.2) with 𝜍1 = 1.8, 𝜚1 = 0.5, Υ1 = 0.4, 𝛾1 ∈[0.40, 0.99] and initial conditions (𝑥0, 𝑦0)=(0.6333, 0.5323): (a), (c) bifurcation diagram for 𝑥𝑛, (b), (d) bifur…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk LOW (score 0.0/100)
> Neimrk-sacker bifurcation diagram for model (1.2) with 𝜍1 = 1.8, 𝜚1 = 0.5, Υ1 = 0.4, 𝛾1 ∈[0.66, 0.685] and initial conditions (𝑥0, 𝑦0)=(0.6333, 0.5323): (a) bifurcation diagram for 𝑥𝑛, (b) bifurcation…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk LOW (score 0.0/100)
> Neimrk-sacker bifurcation diagram for model (1.2) with 𝜍1 = 1.8, 𝜚1 = 0.5, Υ1 = 0.4, 𝛾1 ∈[1.0, 1.7] and initial conditions (𝑥0, 𝑦0)=(0.6333, 0.5323): (a) bifurcation diagram for 𝑥𝑛, (b) bifurcation di…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk LOW (score 0.0/100)
> Phase portraits of model (1.2) for 𝜍1 = 1.5, 𝜚1 = 0.9, Υ1 = 0.5, (𝑥0, 𝑦0)=(0.6333, 0.5323) with diﬀerent values of 𝛾1: (a) 𝛾1 = 0.38, (b) 𝛾1 = 0.33, (c) 𝛾1 = 0.41, (d) 𝛾1 = 0.44, (e) 𝛾1 = 0.48, (f) 𝛾1…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk LOW (score 0.0/100)
> Phase portraits of model (1.2) for 𝜍1 = 1.4, 𝜚1 = 0.8, Υ1 = 0.5, (𝑥0, 𝑦0)=(0.1111, 0.0311) with diﬀerent values of 𝛾1: (a) 𝛾1 = 0.51, (b) 𝛾1 = 0.52, (c) 𝛾1 = 0.61, (d) 𝛾1 = 0.62, (e) 𝛾1 = 0.65, (f) 𝛾1…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk LOW (score 0.0/100)
> Behavior of solution of system (1.2) for 𝜍1 = 1.5, 𝜚1 = 0.6, Υ1 = 0.6, (𝑥0, 𝑦0)=(0.3111, 0.6111) with diﬀerent values of 𝛾1: (a) 𝛾1 = 0.2, (b) 𝛾1 = 0.2, (c) 𝛾1 = 0.22, (d) 𝛾1 = 0.22, (e) 𝛾1 = 0.28, (f…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 8 — risk LOW (score 0.0/100)
> Behavior of solution of system (1.2) for 𝜍1 = 1.5, 𝜚1 = 0.6, Υ1 = 0.6, (𝑥0, 𝑦0)=(0.3111, 0.6111) with diﬀerent values of 𝛾1: (a) 𝛾1 = 0.30, (b) 𝛾1 = 0.30, (c) 𝛾1 = 0.45, (d) 𝛾1 = 0.45, (e) 𝛾1 = 0.50, …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 9 — risk LOW (score 0.0/100)
> Behavior of solution of system (1.2) for 𝜍1 = 1.5, 𝜚1 = 0.6, Υ1 = 0.6, (𝑥0, 𝑦0)=(0.3111, 0.6111) with diﬀerent values of 𝛾1: (a) 𝛾1 = 0.52, (b) 𝛾1 = 0.52, (c) 𝛾1 = 0.55, (d) 𝛾1 = 0.55, (e) 𝛾1 = 0.58, …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 10 — risk LOW (score 0.0/100)
> Behavior of solution of system (1.2) for 𝜍1 = 2.1, 𝜚1 = 2.8, Υ1 = 0.6, (𝑥0, 𝑦0)=(0.3111, 0.6111) with diﬀerent values of 𝛾1: (a) 𝛾1 = 0.66, (b) 𝛾1 = 0.66, (c) 𝛾1 = 0.75, (d) 𝛾1 = 0.75, (e) 𝛾1 = 1.0, (…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 11 — risk LOW (score 0.0/100)
> Bounded stability region for system (1.2). Furthermore, the inclusion of the maximum Lyapunov exponent technique serves as a valuable tool for evaluating chaos within the systems depicted in Fig. 1 an…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | skipped | 0.0/35.0 | copy-move skipped |
| cross_figure | skipped | 0.0/30.0 | cross-figure skipped |
| ai_generation | skipped | 0.0/20.0 | ai-generation skipped |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
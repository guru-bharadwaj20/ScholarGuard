# ScholarGuard Integrity Report — PMC13343157.pdf

- **Generated:** 2026-07-10T08:15:24
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 58.36/100, 7 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk HIGH (score 62.0/100)
> WWOX restoration driven by the synapsin promoter achieves high expression efficiency (A, D, G, and J) Kaplan-Meier survival analyses of Wwox-null mice treated with AAV9-EF1a-hWWOX-WPRE (4 × 1010 vg, n…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.7701) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk HIGH (score 62.0/100)
> Consequences of WPRE removal on WWOX expression and therapeutic efficacy (A) Schematic representation of AAV9 vectors expressing WWOX under the human synapsin (hSynI) promoter, with or without the WPR…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.1667) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 45.0/100)
> WWOX gene therapy enhances survival in a dose-dependent manner (A) Schematic representation of the AAV9-hSynI-hWWOX vectors used for neonatal intracerebroventricular (ICV) injections. Two viral doses …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.0066) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk MODERATE (score 45.0/100)
> High-dose neuronal WWOX expression restores neurobehavioral performance (A) Schematic representation of the experimental design. KO mice were injected at postnatal day 0–1 (P0‑P1) with AAV9-hSynI-hWWO…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.9872) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 45.0/100)
> AAV9-hSynI-hWWOX increases WWOX DNA, mRNA, and protein expression in Wwox-null mice in a dose-dependent manner (A–D) Vector genome copies (GC) in cortex, hippocampus, midbrain, and cerebellum at postn…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.2117) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 6 — risk MODERATE (score 45.0/100)
> Neuronal WWOX restoration rescues hypomyelination in Wwox-null mice in a dose-dependent manner (A) Representative coronal brain sections stained for myelin basic protein (MBP) showing reduced myelinat…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 4.6614) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 7 — risk MODERATE (score 45.0/100)
> Wwox KO littermates exhibit elevated spike activity compared with WT pups, and AAV-mediated WWOX restoration rescues SWDs in Wwox KO pups (A) A single representative ECoG trace together with a magnifi…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.0809) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
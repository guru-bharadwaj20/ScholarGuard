# ScholarGuard Integrity Report — PMC13344357.pdf

- **Generated:** 2026-07-11T22:28:08
- **Status:** completed
- **Overall paper risk:** **HIGH** (score 65.04/100, 6 figure(s))

## ⚠ Pipeline notes (degraded / skipped steps)
- claim-consistency will be SKIPPED for all figures: ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.
  export ANTHROPIC_API_KEY=sk-ant-...      (bash)
  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)
or place it in a .env file (python-dotenv is loaded automatically). (set ANTHROPIC_API_KEY to enable text/claim checking)
- AI-generation running in FORENSICS-ONLY mode: classifier weights not found at 'src/models/weights/artifact_classifier.pt' (train via the Stage 4 Colab notebook to enable the learned signal)

## Figure 1 — risk LOW (score 0.0/100)
> Automated planar patch clamp recordings of the mexiletine block of Nav1.5 currents in transiently transfected HEK293 cells. A) Patchliner schematic. B) Representative INa trace. C) The protocol used t…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 0.0/35.0 | no in-figure duplication |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 0.0/20.0 | AI-generation verdict: likely_real (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 2 — risk HIGH (score 72.0/100)
> NaV1.5 localization within iPSC-derived cardiomyocyte nanodomains. NaV1.5 (purple) colocalizes with α-actinin at the z-discs (A-C, blue) and with N-cadherin at the intercalated discs (D-F, yellow) in …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 35.0/35.0 | duplicated regions within figure (conf 1.153) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 3 — risk MODERATE (score 43.6/100)
> Mexiletine block of Nav1.5 currents in iPSC-CMs lines with WTc or MVET-55 background. Top panel: the S1103Y homozygous line was CRISPR-engineered from the WTc line. A) Representative INa traces before…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.6/35.0 | duplicated regions within figure (conf 0.96) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 4 — risk HIGH (score 70.94/100)
> Action potential duration (APD) and late sodium current measurements in MVET-55 background iPSC-CM lines. A) Representative APD90 traces measured at 1Hz in control and mexiletine-treated cells. 20 μM …

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.94/35.0 | duplicated regions within figure (conf 0.9698) |
| cross_figure | ok | 27.0/30.0 | 2 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## Figure 5 — risk MODERATE (score 35.99/100)
> Nav1.5 kinetics in control and mexiletine-treated iPSC-CMs. A) Acute mexiletine (20 μM) application does not significantly reduce peak INa in the S1103Y−/−, S1103Y+/− or S1103Y+/+ lines (p = 0.99, 0.5…

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 25.99/35.0 | duplicated regions within figure (conf 0.7425) |
| cross_figure | ok | 0.0/30.0 | only low-confidence visual-similarity leads |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

## (uncaptioned figure, page 25) — risk HIGH (score 70.36/100)

| Detector | Status | Points | Finding |
|---|---|---:|---|
| copy_move | ok | 33.36/35.0 | duplicated regions within figure (conf 0.9531) |
| cross_figure | ok | 27.0/30.0 | 1 reused region(s) from another figure |
| ai_generation | ok | 10.0/20.0 | AI-generation verdict: suspicious (forensics-only, no classifier) |
| claim_consistency | skipped | 0.0/15.0 | claim-consistency skipped |

---
_All findings are leads for human review, not proof of misconduct. The visual lane/panel count is an approximate screening heuristic._
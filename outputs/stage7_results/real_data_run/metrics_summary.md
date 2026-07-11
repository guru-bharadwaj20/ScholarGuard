# ScholarGuard — Stage 7 Real-Data Evaluation (N=15 fraud, N=10 clean)

- **Dataset:** `scholarguard_real_eval_v1`
- **Papers evaluated:** 25 (of 25; 0 missing PDFs)
- **Provenance:** REAL evaluation set. Fraud cases are formal retractions from the Retraction Watch database (Crossref) whose stated reason concerns image integrity; PDFs fetched from the PMC Open Access subset. Clean controls are PMC OA papers cross-checked against the FULL Retraction Watch DOI list (all retractions, not just image-related). IMPORTANT: labels are PAPER-LEVEL only — figure_num is null for every fraud case because Retraction Watch does not identify which figure was manipulated. Per-detector, figure-level metrics therefore require manual figure annotation first; paper-level metrics are valid as-is.

> **This is a screening/triage tool for human reviewers, NOT an autonomous accusation system.** Every flag is a lead to be checked by a person.
>
> **Small-sample warning.** With N=15 fraud / N=10 clean, point estimates are unstable. Every rate below carries a 95% Wilson confidence interval; read the interval, not the point.

## What this run does and does not measure
- **copy_move: recall NOT MEASURABLE** — there are no ground-truth positive figures for it in this set. Only its false-positive rate on clean figures is measured (83 figures).
- **cross_figure: recall NOT MEASURABLE** — there are no ground-truth positive figures for it in this set. Only its false-positive rate on clean figures is measured (83 figures).
- **ai_generation: recall NOT MEASURABLE** — there are no ground-truth positive figures for it in this set. Only its false-positive rate on clean figures is measured (83 figures).
- **claim_consistency: NOT EVALUATED** — the detector did not run on any figure (233 figures skipped). Reported as neither passing nor failing.

## Combined pipeline (paper-level fraud classification)
Decision rule: a paper is flagged if its overall risk score >= **25.0**. All rates carry 95% Wilson confidence intervals — at this sample size the point estimate alone is misleading.

- **Precision:** 0.600 (95% CI 0.41-0.77, n=25)
- **Recall:** 1.000 (95% CI 0.80-1.00, n=15)
- **False-positive rate:** 1.000 (95% CI 0.72-1.00, n=10)
- **False-negative rate:** 0.000 (95% CI 0.00-0.20, n=15)
- **Accuracy:** 0.600 (95% CI 0.41-0.77, n=25)
- **F1:** 0.750  _(harmonic mean of two proportions — not a binomial proportion, so no Wilson interval)_

```
                 pred fraud    pred clean   
  true fraud          15            0      
  true clean          10            0      
```

## Per-detector breakdown (figure-level, scoreable figures only)

> **138 figures excluded per detector.** They belong to confirmed-fraud papers with no figure-level annotation, so their true label is UNKNOWN. Counting them as negatives would turn correct detections into false positives; counting them as positives would assume which figure was manipulated. They are excluded and reported separately.

| Detector | Scoreable | Unlabeled | Not eval'd | Precision | Recall | FPR |
|---|---:|---:|---:|---|---|---|
| copy_move | 83 | 138 | 12 | _not measurable_ | _not measurable_ | 0.723 (95% CI 0.62-0.81, n=83) |
| cross_figure | 83 | 138 | 12 | _not measurable_ | _not measurable_ | 0.277 (95% CI 0.19-0.38, n=83) |
| ai_generation | 83 | 138 | 12 | _not measurable_ | _not measurable_ | 0.518 (95% CI 0.41-0.62, n=83) |
| claim_consistency | 0 | 0 | 233 | _not evaluated_ | _not evaluated_ | _not evaluated_ |

_FPR = of the CLEAN figures it was scored on, the fraction it wrongly flagged. Precision/recall are `not measurable` where the set contains no ground-truth positive figures for that detector. `n` in each interval is that metric's own denominator._

**Detections on unlabeled fraud-paper figures** (each is a lead for manual review, scoreable as neither hit nor miss): `copy_move`: 133, `cross_figure`: 54, `ai_generation`: 127

## Side-by-side: synthetic vs. real

Baseline: `scholarguard_synthetic_eval_v1` (N=8 fraud, N=6 clean). This run: N=15 fraud, N=10 clean.

All values carry 95% Wilson CIs. **Read the intervals** — at this sample size small-count point estimates on either side can look firmer than they are (some rest on as few as 2 positive figures).

### Per-detector, figure-level

| Detector | Metric | Synthetic | Real |
|---|---|---|---|
| `copy_move` | precision | 0.400 (95% CI 0.12-0.77, n=5) | _not measurable_ |
| `copy_move` | recall | 1.000 (95% CI 0.34-1.00, n=2) | _not measurable_ |
| `copy_move` | FPR | 0.103 (95% CI 0.04-0.26, n=29) | 0.723 (95% CI 0.62-0.81, n=83) |
| `cross_figure` | precision | 0.091 (95% CI 0.02-0.38, n=11) | _not measurable_ |
| `cross_figure` | recall | 0.500 (95% CI 0.09-0.91, n=2) | _not measurable_ |
| `cross_figure` | FPR | 0.345 (95% CI 0.20-0.53, n=29) | 0.277 (95% CI 0.19-0.38, n=83) |
| `ai_generation` | precision | 0.667 (95% CI 0.21-0.94, n=3) | _not measurable_ |
| `ai_generation` | recall | 1.000 (95% CI 0.34-1.00, n=2) | _not measurable_ |
| `ai_generation` | FPR | 0.035 (95% CI 0.01-0.17, n=29) | 0.518 (95% CI 0.41-0.62, n=83) |
| `claim_consistency` | precision | _not evaluated_ | _not evaluated_ |
| `claim_consistency` | recall | _not evaluated_ | _not evaluated_ |
| `claim_consistency` | FPR | _not evaluated_ | _not evaluated_ |

### Combined pipeline, paper-level

| Metric | Synthetic | Real |
|---|---|---|
| precision | 0.571 (95% CI 0.25-0.84, n=7) | 0.600 (95% CI 0.41-0.77, n=25) |
| recall | 0.500 (95% CI 0.22-0.78, n=8) | 1.000 (95% CI 0.80-1.00, n=15) |
| FPR | 0.500 (95% CI 0.19-0.81, n=6) | 1.000 (95% CI 0.72-1.00, n=10) |
| accuracy | 0.500 (95% CI 0.27-0.73, n=14) | 0.600 (95% CI 0.41-0.77, n=25) |
| F1 _(no CI)_ | 0.533 | 0.750 |

## Threshold sweep & recommended operating point
Full curve in `threshold_sweep_results.csv`. Selected rows:

| Score >= | Precision | Recall | F1 | FPR |
|---:|---:|---:|---:|---:|
| 0 | 0.600 | 1.000 | 0.750 | 1.000 |
| 5 | 0.600 | 1.000 | 0.750 | 1.000 |
| 10 | 0.600 | 1.000 | 0.750 | 1.000 |
| 20 | 0.600 | 1.000 | 0.750 | 1.000 |
| 25 | 0.600 | 1.000 | 0.750 | 1.000 |
| 30 | 0.600 | 1.000 | 0.750 | 1.000 |
| 40 | 0.583 | 0.933 | 0.718 | 1.000 |
| 50 | 0.611 | 0.733 | 0.667 | 0.700 |
| 60 | 0.538 | 0.467 | 0.500 | 0.600 |
| 70 | 1.000 | 0.267 | 0.421 | 0.000 |
| 80 | n/a | 0.000 | n/a | 0.000 |
| 90 | n/a | 0.000 | n/a | 0.000 |
| 100 | n/a | 0.000 | n/a | 0.000 |

**Recommended threshold: 67.5** (basis: zero-false-positive).
> lowest paper-score cutoff that produces NO false positives on the control set, maximizing recall within that constraint — chosen because a false accusation is costlier than a missed case at screening.

## Error analysis
- False positives: **126**  |  False negatives: **0**  |  Not evaluated (detector unavailable on a true-positive figure): **0**  |  Unlabeled hits (fraud paper, unknown figure): **314**

Annotated worst-case images are in `error_analysis/` (figure crops and detector output only — no paper text is reproduced).

### False positives (why the pipeline flagged a clean figure)
- (60x) copy-move false-triggered on repetitive/self-similar texture within a legitimate figure
- (43x) AI-detector false-triggered on a real (non-generated) image
- (12x) cross-figure flagged a legitimate DOSE-RESPONSE SERIES (figures similar by design, not reuse)
- (11x) cross-figure flagged legitimately similar figures as reuse

### Unlabeled hits (detections on confirmed-fraud papers, figure unknown)
- (314x) fired on a figure of a CONFIRMED-FRAUD paper whose manipulated figure is not annotated - cannot be scored as a hit or a false alarm; needs manual figure-level review

---
_Generated by src/evaluation/error_analysis.py. Flags are leads for human review, not proof of misconduct._
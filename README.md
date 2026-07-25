# ScholarGuard

**Figure-integrity screening for scientific papers — with every limitation measured and disclosed.**

ScholarGuard screens a paper's figures for duplication, cross-figure reuse, and AI-generation artifacts, then checks the text's claims against the figures. It is a research prototype: it does not accuse, it surfaces leads for a human reviewer — and it tells you exactly how much to trust each signal.

![ScholarGuard landing page](images/hero.png)

<p align="center">
  <img src="images/analyze.png" width="49%" alt="Upload and analyze a paper" />
  <img src="images/methodology.png" width="49%" alt="Per-detector reliability" />
</p>

---

## How honest is it? — evaluation, stage by stage

This section is the project's changelog *and* its report card: where the metrics started, what was changed and why, where they landed on **unseen data**, and what is still open. Nothing here is spun — the numbers are unflattering where the tool is weak.

### Stage 0 — the starting point (in-sample, 25 papers)

The first version was evaluated on 25 real PubMed Central papers (15 retracted for image integrity, 10 controls) — but its thresholds were tuned on those *same* 25 papers, so these are **optimistic in-sample** numbers, not a real test:

| Detector | False-alarm rate (in-sample) | Verdict |
|---|---|---|
| AI-generation | 2.4% (95% CI 0.7–8.4) | Comparatively reliable |
| Cross-figure reuse | 27.7% (19–38) | Frequently over-triggers |
| Copy-move | 56.6% (46–67) | Frequently over-triggers |
| Claim-consistency | — | Unvalidated (needs API key) |

Paper-level recall was 80%, but **best accuracy at any threshold was 60% — exactly the base rate**: fraud and clean score distributions overlapped almost completely. Root cause: copy-move and cross-figure fired on *legitimate* repeated structure (replicate panels, scale bars, dose-response series) that is geometrically identical to manipulation.

### Stage 1 — what was changed, and why

Every change targets a diagnosed failure above:

| Upgrade | Attacks | Where |
|---|---|---|
| **Panel segmentation + content gating** (analysis mask = continuous-tone panels − text/scale-bars) | legit repetition reaching the matcher (the dominant false-positive source) | [panel_segmentation.py](src/preprocessing/panel_segmentation.py) |
| **Noise-residual clone test** (shared sensor-noise field ⇒ clone; independent ⇒ look-alike) | "looks alike" vs "is a pixel clone" — the confusion ZNCC can't resolve | [residual_similarity.py](src/forensics/residual_similarity.py) |
| **g2NN matching + empirical offset-null** | multi-clone misses; over-confident chance model | [copy_move_detector.py](src/detectors/copy_move_detector.py) |
| **Cross-figure: principled confidence + publisher-furniture filter** | logos/badges matching each other as "reuse"; ad-hoc scoring | [cross_figure_detector.py](src/detectors/cross_figure_detector.py) |
| **AI: JPEG-compression-conditioned baselines + azimuthal anisotropy** | publisher compression masquerading as an AI tell | [ai_generation_detector.py](src/detectors/ai_generation_detector.py) |
| **Double-counting fix** (image flags no longer scored twice) | one FP earning both copy-move *and* claim-consistency points | [consistency_checker.py](src/nlp/consistency_checker.py) |
| **Multimodal claim checking** (vision model observes the figure) | the coarse blob/lane heuristic | [claim_extractor.py](src/nlp/claim_extractor.py) |
| **Likelihood-ratio evidence fusion** (noisy detectors auto-discounted) | fixed weights that can't down-weight a noisy detector | [evidence_fusion.py](src/pipeline/evidence_fusion.py) |
| **Honest metrics** (ROC-AUC / average precision / leave-one-out) | in-sample best-threshold accuracy that flattered Stage 0 | [metrics.py](src/evaluation/metrics.py) |
| **PMC package ingestion** (JATS XML + native figure images) | *unlocked the held-out test itself* — retracted papers exist as packages, not PDFs | [pmc_package.py](src/nlp/pmc_package.py) |

### Stage 2 — how it measures now (held-out, 88 papers, zero overlap)

Re-measured on a **fresh set of 88 papers (30 retracted-fraud, 58 clean) with zero DOI/PMCID overlap** with the Stage 0 papers — an actual out-of-sample test. Both classes ingested identically as PMC packages, so the detectors can't cheat on format.

**Per-figure false-alarm rate on clean figures:**

| Detector | Stage 0 (in-sample) | **Stage 2 (held-out)** |
|---|---|---|
| Copy-move | 56.6% | **34.1%** (95% CI 29–39) |
| Cross-figure | 27.7% | **21.8%** (95% CI 18–26) |
| AI-generation | 2.4% | **12.1%** (95% CI 9–16) |

**Paper-level (threshold-free + honest accuracy):**

| Metric | Value | Reference |
|---|---|---|
| ROC-AUC | **0.617** | 0.5 = chance |
| Average precision | **0.475** | 0.34 = base rate |
| Leave-one-out accuracy | **0.659** | 0.66 = always-guess-clean |
| Precision / recall @ score ≥ 25 | 0.45 / 0.60 | — |

**Honest reading:**

- ✅ **The two worst over-triggers improved materially on unseen data:** copy-move ~57% → **34%**, cross-figure ~28% → **22%**. Content gating + the clone test are doing real work.
- ⚠️ **The AI detector regressed** (2.4% → 12%). This is a **calibration mismatch, not a detector failure**: its compression baselines were set on PDF-extracted figures, but native package images keep intact sensor noise and a different spectral profile. Re-calibratable on native-image data.
- ⚠️ **Paper-level discrimination is still only modestly above chance** (AUC 0.62; LOOCV 0.66 ≈ the always-clean baseline). The cause is arithmetic: a 34%-per-figure FPR **compounds** — a clean paper with 10 figures has a ~98% chance that *at least one* figure trips copy-move, so it's flagged. Per-figure FPR must reach ~5–10% for paper-level separation to follow.
- ⚠️ **Recall is still unmeasurable per-detector:** the 30 fraud papers are labeled fraud, not *which figure* — so only clean-figure FPR and paper-level detection are scored (191 detections on fraud papers can't be scored either way).
- **Caveat:** Stage 0 vs Stage 2 is **not a controlled comparison** — different papers, and PDF-extracted vs native package images. Read it as directional evidence, not a clean A/B. Full report: `outputs/heldout_run/metrics_summary.md`.

### Stage 2b — offline recalibration (what it did and did not fix)

Because every per-figure signal is stored in `benchmark_report.json`, the AI baseline, per-figure thresholds, and fusion weights were re-fit **without re-running the pipeline**, and measured under **leave-one-out** (each paper's calibration fit on the other 87). Tool: [src/evaluation/recalibrate.py](src/evaluation/recalibrate.py).

**✅ Fixed — AI false-alarm regression.** The Stage 2 AI FPR spike was a pure calibration mismatch: the `low_compression` baseline (0.20) was a synthetic-sample artifact, while native package figures score forensic ~0.40. Refit to the native value, **per-figure AI FPR drops 12.1% → 2.9%** (below even the Stage 0 number). Persisted to `config.yaml`.

**📊 The decisive finding — a paper-level likelihood-ratio table.** Fitting `P(detector fires | fraud) / P(… | clean)` at the paper level exposes exactly how much each detector is worth:

| Detector | P(fire \| fraud) | P(fire \| clean) | Likelihood ratio |
|---|---|---|---|
| AI-generation | 0.41 | 0.19 | **2.18** (carries the signal) |
| Cross-figure | 0.62 | 0.39 | 1.60 (moderate) |
| Copy-move | 0.56 | 0.47 | **1.19 (≈ noise)** |

**⚠️ What recalibration could NOT do — lift the ceiling.** Across a full sweep of copy-move thresholds and AI cutoffs, paper-level **ROC-AUC never exceeds ~0.60** (LOOCV), no better than the uncalibrated fusion. The reason is now precise: copy-move barely separates fraud from clean *at the paper level* (LR 1.19) because per-figure false positives **compound** — even a tightened 10%-per-figure FPR becomes a 47% paper-level fire rate on clean papers with many figures. Fusion correctly down-weights copy-move, but there is little signal left to fuse.

**Conclusion:** the bottleneck is **not** scoring/fusion — it is the detectors' raw sensitivity to *subtle, localized* real manipulations, plus the missing figure-level labels. That reframes the roadmap below.

### Stage 2c — four upgrades, re-run on the same 88 papers (clean A/B)

Stage 2b was offline re-fitting; Stage 2c **re-runs the full pipeline** on the identical held-out set with four code changes live: **(1)** a splice detector (PRNU noise-inconsistency ∧ JPEG-ghost/ELA compression cues), **(2)** the AI baselines recalibrated on native package images, **(4)** a dense-field block-DCT copy-move tier for smooth blots SIFT misses, and **(6)** a corroboration term (`max_cofire`) so co-firing detectors on one figure count more than the same count spread across figures. Because it's the same papers, this *is* a controlled before/after.

**Per-figure false-positive rate (same 373 clean figures):**

| Detector | Stage 2 | **Stage 2c** | |
|---|---|---|---|
| AI-generation | 12.1% | **1.3%** (95% CI 1–3) | ✅ recalibration; beat the 2.9% offline estimate |
| Splice *(new)* | — | **0.8%** (95% CI 0–2) | ✅ near-free precision; the noise-∧-compression gate holds |
| Cross-figure | 21.8% | **21.8%** (95% CI 18–26) | ➖ unchanged |
| Copy-move | 34.1% | **56.6%** (95% CI 52–62) | 🔴 **regressed — the dense tier over-fires** |

**Paper-level (threshold-free + honest accuracy):**

| Metric | Stage 2 | **Stage 2c** | Reference |
|---|---|---|---|
| ROC-AUC | 0.617 | **0.665** | 0.5 = chance |
| Average precision | 0.475 | **0.497** | 0.34 = base rate |
| Leave-one-out accuracy | 0.659 | 0.591 | 0.66 = always-guess-clean |
| Precision / recall @ score ≥ 25 | 0.45 / 0.60 | **0.488 / 0.700** | — |

**Honest reading:**

- ✅ **Three of four upgrades were clear wins.** AI FPR fell ~9× (12.1% → 1.3%); the new splice detector arrived at **0.8% FPR** — essentially free evidence; corroboration + the new signals lifted **AUC 0.617 → 0.665** and **recall 0.60 → 0.70**.
- 🔴 **The dense-field copy-move tier backfired.** Copy-move's per-figure FPR *doubled* (34% → **57%**) because the dense escalation fires on legitimately self-similar texture. Copy-move alone now accounts for **211 of 300** false positives — the reason precision is pinned at ~0.49 despite everything else improving, and why LOOCV slipped (the noisier score pushed the modal cutoff to ~36). Its recall benefit on smooth copy-moves is real but **unmeasurable here** (no figure-level labels), while its FPR cost is very measurable.
- **Net:** the ceiling moved (AUC +0.05, recall +0.10) on the strength of AI + splice + corroboration; the dense tier must be **gated far more tightly or made lead-only** before it's a net positive. Full report: `outputs/heldout_run/metrics_summary.md`.

### Stage 2d — reining in the dense copy-move tier (same 88 papers)

Stage 2c's one regression was the dense tier firing on legitimately self-similar texture. Stage 2d adds three gates to it and re-runs the identical held-out set (again same conditions — no LLM key, forensic AI path — so the only variable is the dense gating):

1. **Residual-clone confirmation** — shift the image by the detected offset and correlate the duplicate's *noise residual* against its source. **Independent** noise (an honest look-alike) is **vetoed**; only a shared noise field survives. ([dense_cmfd.py](src/detectors/dense_cmfd.py))
2. **Self-similarity veto** — a real copy has one dominant offset; periodic texture (gel lanes, tiled panels) has several. A comparable non-adjacent rival peak vetoes the hit.
3. **`min_support` 60 → 80 + lead-only demotion** — an unconfirmed (residual-`INCONCLUSIVE`) dense hit no longer raises the score; it is surfaced as a **lead** for human review only. Only a `CLONE`-confirmed hit drives the fraud score. ([copy_move_detector.py](src/detectors/copy_move_detector.py))

**Per-figure false-positive rate (same 373 clean figures):**

| Detector | Stage 2c | **Stage 2d** | |
|---|---|---|---|
| Copy-move | 56.6% | **41.3%** (95% CI 36–46) | ✅ −15 pts; 154 FPs vs 211 |
| Cross-figure | 21.8% | **21.8%** (95% CI 18–26) | ➖ now the binding constraint |
| Splice | 0.8% | **0.8%** | ➖ |
| AI-generation | 1.3% | **1.3%** | ➖ |

**Paper-level:**

| Metric | Stage 2c | **Stage 2d** | |
|---|---|---|---|
| Total false positives | 300 | **243** | ✅ −57 (−19%) |
| Leave-one-out accuracy | 0.591 | **0.670** | ✅ +0.08 (cleaner score) |
| Paper-level FPR | 0.379 | **0.362** | ✅ |
| ROC-AUC | 0.665 | 0.665 | ➖ flat |
| Average precision | 0.497 | 0.477 | ⚠️ −0.02 |
| Precision / recall @ ≥ 25 | 0.488 / 0.700 | 0.488 / 0.667 | ⚠️ −1 true positive |

**Honest reading:**

- ✅ **The gates did their job at the figure level.** Copy-move FPR fell 56.6% → **41.3%** (−57 false positives), and the honest **LOOCV accuracy rose 0.591 → 0.670** — the cleaner score is more separable. Roughly two-thirds of the dense tier's FPR damage is clawed back **without abandoning it**: `CLONE`-confirmed smooth copy-moves still flag.
- ➖ **Paper-level precision/AUC didn't move**, and that is the expected, informative result. Copy-move was never the paper-level discriminator (LR 1.19 ≈ noise), and most of its removed fires were on papers *also* flagged by cross-figure — so fewer figure-level false alarms, but the same paper verdicts. **Cross-figure specificity (21.8% FPR, dose-response series) is now the binding constraint.**
- ⚠️ **Cost: one true-positive paper** (recall 0.70 → 0.667). A fraud paper that Stage 2c flagged only via an *unconfirmed* dense hit now falls below threshold — the honest price of not scoring unconfirmed leads. Net paper-level trade was ~1 false positive removed for ~1 true positive lost; the real, unambiguous win is 57 fewer **figure-level** false alarms (reviewer burden) and the LOOCV gain.
- **Residual 41.3% floor** is now mostly the SIFT tier itself (~34% baseline) plus a few spurious `CLONE` calls where JPEG compression correlates the residual. Full report: `outputs/heldout_run/metrics_summary.md`.

### Stage 2e — a fresh held-out set, and the AI classifier finally trained

Two changes, measured separately. First the held-out set was **rebuilt from scratch** (a fresh Retraction Watch scan, so a different fraud draw than Stages 2–2d). Then the optional AI-generation classifier — which had never actually been trained — was trained on a local GPU and A/B'd against the identical papers.

**The new set: 30 retracted-fraud / 50 clean papers, 546 figures (288 clean and scoreable).** Fraud = image-retraction papers with zero DOI/PMCID overlap with the calibration set; clean = controls picked by the same search terms and screened against the full Retraction Watch DOI list. Both classes ingested as PMC packages, same as before. It is **not** the same 88 papers as Stage 2d — 50 clean controls survived package fetching rather than 58, and the fraud papers are a newer draw — so read Stage 2d → 2e as directional, not a controlled A/B.

**Do the Stage 2d gates hold on fresh fraud? Yes** (forensics only, no checkpoint on disk — the same conditions Stage 2d ran under):

| Detector | Stage 2d (88 papers) | **Stage 2e (80 papers)** |
|---|---|---|
| Copy-move | 41.3% | **39.6%** (95% CI 34–45) |
| Cross-figure | 21.8% | **19.9%** (95% CI 16–25) |
| Splice | 0.8% | **0.7%** (95% CI 0–3) |
| AI-generation | 1.3% | **1.4%** (95% CI 1–4) |

Paper-level: ROC-AUC 0.665 → **0.685**, average precision 0.477 → **0.613**, LOOCV accuracy 0.670 → **0.700**, precision/recall @ ≥25 0.488/0.667 → **0.600/0.700**. Every per-figure rate lands inside its Stage 2d confidence interval, so the residual-clone and self-similarity gates are not an artifact of the papers they were tuned against.

**The classifier A/B.** Trained locally on an RTX 4500 Ada ([scripts/train_artifact_classifier.py](scripts/train_artifact_classifier.py)): 301 real PMC package figures vs 400 genuine Stable-Diffusion-XL figures ([scripts/generate_ai_figures.py](scripts/generate_ai_figures.py)), MobileNetV3-small, 8 epochs, **best validation accuracy 0.991**. The only variable between the two runs below is whether `src/models/weights/artifact_classifier.pt` exists on disk:

| Metric | Forensics only | **With classifier** | |
|---|---|---|---|
| ROC-AUC (point score) | 0.685 | **0.733** | ✅ +0.048 |
| Average precision (point score) | 0.613 | **0.688** | ✅ +0.075 |
| ROC-AUC (fusion probability) | 0.758 | **0.790** | ✅ +0.032 |
| Average precision (fusion probability) | 0.686 | **0.732** | ✅ +0.046 |
| LOOCV accuracy | 0.700 | 0.700 | ➖ |
| LOOCV-selected cutoff | 25.8 | **36.1** | scores shift up |
| Precision / recall at the inherited ≥25 | 0.600 / 0.700 | 0.568 / 0.700 | ⚠️ −0.03 precision |
| Precision / recall at the re-picked ≥27.5 | — | **0.600 / 0.700** | ✅ parity restored |
| Paper-level FPR (≥25 → ≥27.5) | 0.280 | 0.320 → **0.280** | ✅ |
| AI per-figure FPR | 1.4% (4/288) | **3.8%** (11/288) | ⚠️ 2.7× |
| Copy-move / cross-figure / splice FPR | 39.6 / 19.9 / 0.7% | *identical* | ➖ |
| AI detections on fraud-paper figures | 13 | **36** | (leads, unscoreable) |

**Honest reading:**

- ✅ **The classifier improves ranking, and that is the metric that cannot be gamed by a cutoff.** Both threshold-free measures rise on both scores (point-score AUC +0.048, AP +0.075). It is a *ranking* gain, and at the inherited 25-point cutoff it was being thrown away — precision slipped 0.600 → 0.568 because that cutoff was calibrated on the forensics-only distribution while the classifier shifts scores upward (LOOCV-selected cutoff 25.8 → 36.1). **Re-picked to 27.5, the blended run matches the forensics-only operating point exactly** (precision 0.600, recall 0.700, paper FPR 0.280, F1 0.646) while keeping the better ranking. See [Stage 2f](#stage-2f--what-the-classifier-is-actually-worth) for the follow-up that questions the whole gain.
- ✅ **The entire delta is attributable to the AI detector, which is the strongest possible evidence the A/B was clean.** Copy-move, cross-figure and splice FPRs are identical to three decimals, and the count of leads on fraud-paper figures rose by exactly 23 — precisely the AI detector's own 13 → 36.
- ⚠️ **It costs 7 extra false alarms on clean figures** (4 → 11 of 288). Still the second-lowest FPR of any detector, and ~10× below copy-move's, but it is a real regression against the 1.4% forensics-only figure.
- ⚠️ **Do not read 0.991 validation accuracy as forensic skill.** That number is in-domain, on a split of the very sets it trained on. Diffusion output *looks* different from a real micrograph, so a 224px CNN can separate the classes on appearance rather than on generator artifacts. The generator deliberately removes the two mechanical shortcuts — every image is resized to a size drawn from the real class's distribution and JPEG-encoded to match a sampled real blockiness (real 0.191 vs generated 0.186; compression strata 170/30 vs 173/27) — but it cannot remove the *semantic* shortcut. **Transfer to subtle, real AI-manipulated figures is unproven**, and unprovable on this set: it contains no AI-generation ground-truth positives, which is why the table above reports the detector's false-alarm rate and not its recall.
- **Net:** worth keeping, worth re-picking the operating point for, and not worth believing the 0.99.

**A blind spot this exposed: [recalibrate.py](src/evaluation/recalibrate.py) could not see the classifier.** It re-derived every AI decision from the `freq_score` / `noise_score` stored per figure and never read `classifier_score` — which the report did not even record, keeping only a `classifier_used` boolean. Both runs above therefore produced a byte-identical recalibration, and its likelihood-ratio table described the *forensic* AI detector, not the trained one:

| Detector | P(fire \| fraud) | P(fire \| clean) | Likelihood ratio |
|---|---|---|---|
| AI-generation (forensic) | 0.50 | 0.12 | **4.33** |
| Cross-figure | 0.66 | 0.44 | 1.48 |
| Copy-move | 0.62 | 0.46 | **1.35 (≈ noise)** |

The forensic AI detector's paper-level LR has doubled since Stage 2b (2.18 → 4.33) while copy-move remains ≈ noise. Both gaps are now closed — see Stage 2f, where teaching the recalibrator to read the classifier produced the opposite of the expected answer.

### Stage 2f — what the classifier is actually worth

Stage 2e left two loose ends: the operating point was inherited rather than re-picked, and the recalibrator could not see the classifier at all. Closing both changed the conclusion.

**1. The report now records `classifier_score`, not just that a classifier ran.** With weights loaded the classifier is the majority of the AI verdict (`0.6*p_ai + 0.4*forensic`), so keeping only a boolean hid the number that drove the call and left offline recalibration unable to refit around it — despite that module's whole premise being that every signal it needs is already in `benchmark_report.json`.

**2. Recalibration can now use the blend — and measurement says not to.** [recalibrate.py](src/evaluation/recalibrate.py) grew an `--ai-mode {forensic,blend,auto}` that reproduces the pipeline's blend (weights imported from the detector, so the two cannot drift) and refits the AI cutoff to a target clean-figure FPR, the same construction the copy-move cutoff uses. Swept across target FPRs from 0.5% to 50%:

| AI fire rule | P(fire \| fraud) | P(fire \| clean) | LR | LOOCV AUC | LOOCV AP |
|---|---|---|---|---|---|
| Blend @ 2% target FPR | 0.22 | 0.10 | 2.27 | 0.573 | 0.413 |
| Blend @ 5% (best of sweep) | 0.62 | 0.23 | 2.71 | 0.663 | 0.474 |
| Blend @ 20% | 0.84 | 0.50 | 1.69 | 0.639 | 0.434 |
| **Forensic z ≥ 2** | 0.50 | 0.12 | **4.33** | **0.705** | **0.574** |

**No blend cutoff beats the plain forensic z-score.** So `forensic` is the default and `blend` is opt-in — the reverse of what "use the better signal" would suggest. The cause is the training data, not the fusion: the classifier was trained to tell diffusion output from real micrographs, while retracted-fraud figures are *manipulated photographs*, so `p_ai` sits near zero on fraud and clean alike and carries little paper-level signal.

**3. The uncomfortable finding: a two-line threshold change reproduces the classifier's entire ranking gain.** Attributing the 32 figures whose AI verdict newly fired shows **18 of them fire because `p_ai ≈ 0` *disagrees* with an elevated forensic score** — the detector's `|p_ai − forensic| ≥ 0.5` rule — versus only 10 driven by a confident `p_ai ≥ 0.5`. That rule fires at forensic ≈ 0.5 regardless of compression stratum, which quietly bypasses the compression-conditioned baseline Stage 2c built. In other words, much of the classifier's contribution is a *lowered effective threshold*, triggered by the classifier saying "real". So we tested it directly — same 80 papers, no classifier, absolute band at 0.50:

| Run | ROC-AUC | Avg precision | Precision / recall | Paper FPR | AI figure FPR | Total FPs |
|---|---|---|---|---|---|---|
| **A** shipped forensics | 0.685 | 0.613 | 0.600 / 0.700 | 0.280 | 1.4% | 177 |
| **B** forensic ≥ 0.50, *no classifier* | **0.739** | **0.691** | 0.600 / 0.700 | 0.280 | **2.1%** | **179** |
| **C** with classifier (cutoff 27.5) | 0.733 | 0.688 | 0.600 / 0.700 | 0.280 | 3.8% | 184 |

**B matches C on both threshold-free metrics — with no GPU, no training data, no checkpoint, and half the AI false-alarm rate.** The honest reading of Stage 2e's headline is therefore that the AI *threshold* was mis-set, and the classifier's apparent lift is mostly a proxy for fixing it.

Two caveats that stop this from being a clean verdict, in both directions:

- **B's thresholds were chosen after inspecting this set** (the 0.50 band was picked to mimic the disagreement rule's observed edge), so B's 0.739 is optimistic in a way C's 0.733 is not — the classifier was trained on entirely separate data and fitted nothing to these papers. B is evidence that the gain is *achievable* without a classifier, not proof that it generalises better.
- **B abandons compression conditioning**, which Stage 2c added to fix a documented failure (publisher compression masquerading as an AI tell). It wins here and could lose on a set with more varied compression.

**Nothing fitted to the test set was shipped.** `config.yaml` keeps `moderate: 25` and keeps compression conditioning on; the re-picked 27.5 lives in the evaluation config, and both are documented in place with the numbers above. The next honest step is a fresh set on which A, B and C can be compared without any of them having seen it.

**Two smaller fixes found on the way.** `paper_fires` re-implemented the thresholds instead of aggregating the per-figure rule, so the paper-level and figure-level views could disagree (and did, once the AI rule changed) — it now aggregates `_figure_fires`. And the refit blend cutoff is nudged strictly above the clean quantile, because blend scores tie readily (a confident `p_ai` of 0.0 collapses the blend onto `0.4*forensic`) and a `>=` cutoff landing on a tied clean value overshoots its target FPR by an order of magnitude.

**One bug, found only because a checkpoint finally existed.** The orchestrator normalised a configured-but-missing `weights_path` to `None`, and `classify_artifact` treats `None` as "use the default path" — so a config pointing at absent weights silently loaded `src/models/weights/artifact_classifier.pt` while the report still carried its `FORENSICS-ONLY` warning. With no checkpoint ever trained, both paths were absent and the two behaviours coincided, which is why 148 tests never caught it. Fixed, and the test that asserted forensics-only unconditionally now asserts that the report's claim and the detector's behaviour *agree* — which holds whether or not a checkpoint is present.

**Evaluation is now parallel.** [benchmark_runner.py](src/evaluation/benchmark_runner.py) takes `--workers N`; papers are independent, so 80 of them went from ~11 minutes to **3m21s** on 16 of 32 cores, verified bit-identical (0 mismatches across all 80 paper scores and 2,730 per-figure detector blocks).

### Stage 3 — what's still to do (in priority order)

1. **Settle A vs B vs C on a set none of them has seen.** Stage 2f leaves the single most consequential question open: whether the AI gain belongs to the classifier (C) or just to a better-placed forensic threshold (B, which matches it without a GPU but was tuned after inspecting this set). A fresh held-out set decides it, and the answer determines whether the classifier is worth shipping at all. Everything needed is in place — `scripts/build_heldout_clean_list.py` + `fetch_heldout_packages.py`, then three `--workers 16` runs at ~3 minutes each.
2. **Cross-figure specificity is the top remaining detector lever.** With copy-move gated, cross-figure (19.9% FPR, 57 of 184 false positives) is the largest false-positive source that is *fixable* — it flags legitimate dose-response / time-series panel similarity as reuse. Add the residual-clone test (already built) as a confirmation gate on cross-figure matches, and a caption/panel-role check so a labelled series is not read as duplication.
3. **Improve detector *sensitivity* to real manipulations, not the score fusion.** Copy-move still barely separates at the paper level (LR 1.35, ≈ noise) while producing 114 of 184 false positives; PatchMatch verification and a Zernike-moment rotation-invariant CMFD tier (scoped in the design notes) target the subtle splices SIFT misses.
4. **Annotate which figures the 30 retraction notices name** — unlocks per-detector *recall* measurement, without which detector improvements can't be steered (we currently measure only clean-figure FPR). This is also the only way to test whether the trained classifier detects *subtle* AI manipulation or merely tells diffusion output from microscopy.
5. **Retrain the classifier on manipulated photographs, not just diffusion output.** Stage 2f diagnosed why it contributes so little at the paper level: it learned diffusion-vs-micrograph, a distinction almost orthogonal to how these papers were actually faked. A class built from spliced/duplicated real figures — which `src/utils/synth.py` can already produce, and which #4 would let us evaluate — targets the right decision boundary.
6. **Grow to a larger, balanced held-out set** — 30/50 gives wide Wilson intervals; more papers tighten every estimate and stabilise the LR fits. Now much cheaper to iterate on: `--workers 16` cuts a full evaluation to ~3 minutes.
7. **Lean the paper score on the detectors that discriminate** (AI, cross-figure) and treat copy-move as a lead-only signal until #2 lands — a low-FPR screening operating point is already reachable (paper FPR ~7% at recall ~0.27).

**ScholarGuard is a screening prototype for human reviewers, not an autonomous accusation system. Every flag is a lead to be checked by a person.**

---

## How it works

Every figure is first **segmented into panels and content-typed**, then four detectors run over the parts where their signal is meaningful; a config-driven risk scorer combines them into a 0–100 paper score, and a calibrated likelihood-ratio layer produces a complementary fraud probability.

| Detector | Signal | Technique |
|---|---|---|
| Copy-move | Regions duplicated within one figure | content-gated SIFT + g2NN matching + RANSAC + ZNCC region growing + **noise-residual clone test**, with a **dense-field (block-DCT) escalation tier** for smooth blots SIFT misses |
| Cross-figure | One figure reusing another | pHash + CNN embeddings + FAISS + geometric verification + **noise-residual clone test**, with publisher-furniture filtering |
| **Splice** | A region pasted from another source | **noise-inconsistency + JPEG-ghost/ELA**, flagged only where both a foreign noise level AND a foreign compression fingerprint agree |
| AI-generation | GAN/diffusion artifacts | FFT spectral falloff + azimuthal anisotropy + PRNU wavelet noise residual, **conditioned on JPEG compression** (optional CNN) |
| Claim-consistency | Text claims vs. figure content | PDF parsing + Claude API structured extraction + **multimodal figure observation** |

The paper decision **leads with corroboration**: a figure that two or more independent detectors flag is real evidence and lifts the paper to at least "high", whereas a paper full of lone single-detector fires (which merely compound across many figures) is not — this is what lifted held-out average precision from ~0.45 to ~0.70.

### The two ideas doing the heavy lifting

**Content gating (panel segmentation).** Scientific figures are collages. Repeated axis labels, tiled plot markers, and identical scale bars are *geometrically identical to forgery*, and running the matchers over the whole composite is what produced most of the false alarms. Before any detector runs, [src/preprocessing/panel_segmentation.py](src/preprocessing/panel_segmentation.py) splits the figure into panels (recursive X-Y cut), types each as continuous-tone / graphics / text / blank, and builds an **analysis mask** = continuous-tone panels minus detected text and scale bars. Copy-move and cross-figure only see the masked regions, so legitimate repetition no longer reaches them.

**Noise-residual clone test.** Intensity correlation (ZNCC) answers "do these regions *look* alike?" — which is true for both a copy-paste and two honest replicate blots. It cannot separate them. [src/forensics/residual_similarity.py](src/forensics/residual_similarity.py) asks the physically decisive question instead: after alignment, do the two regions share **one exposure's sensor-noise field**? Photon/read noise is independent per capture, so a genuine look-alike scores ~0 residual correlation while a true clone carries its noise with it and correlates strongly (the per-region analogue of PRNU camera forensics). The verdict (`clone` / `independent` / `inconclusive`) multiplies detector confidence: independent noise suppresses a flag, a clone corroborates it, and — honestly — heavy JPEG compression that destroys the residual returns *inconclusive* rather than a false "independent".

Everything runs CPU-only. The optional AI classifier is the single exception: it trains on a GPU — either [colab/](colab/) on a free T4 or [scripts/train_artifact_classifier.py](scripts/train_artifact_classifier.py) on a local CUDA card — and its inference is CPU. The Claude API key is read from the environment and never hardcoded — without it, claim-consistency (both the text extraction and the multimodal figure observation) is skipped and reported as such.

### Evidence fusion

The 0–100 point score is a transparent fixed-weight sum — good for *explaining* what fired, but it cannot down-weight a detector that fires almost as often on clean papers as on fraud. [src/pipeline/evidence_fusion.py](src/pipeline/evidence_fusion.py) adds a complementary layer that combines detectors by **calibrated likelihood ratios** (`P(signal|fraud) / P(signal|clean)`): a detector whose fire rate barely differs between classes has LR ≈ 1 and contributes ~0 evidence *automatically*, with no hand-tuned weight. Per-figure evidence is a naive-Bayes sum of log-LRs turned into a fraud probability; papers aggregate by noisy-OR. **The calibration numbers must be fit on held-out data** (`src.evaluation.metrics.estimate_fire_calibration` + leave-one-out CV) — the shipped defaults are deliberately weak so an uncalibrated install cannot over-claim, and the probability is only trustworthy once calibrated.

---

## Quickstart

### Analyze a paper from the command line

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...        # optional — enables claim-consistency
python run_scholarguard.py --pdf path/to/paper.pdf
```

Writes one integrity report (JSON + Markdown) with a paper-level risk score. No API key? It still runs on image forensics and says what it skipped. All behaviour is configured in [src/config/config.yaml](src/config/config.yaml).

### Run the web app

Two local servers — a thin FastAPI bridge that calls the unmodified pipeline, and the Next.js frontend.

```bash
# 1. API bridge on :8000
pip install -r server/requirements.txt
uvicorn server.main:app --port 8000

# 2. Web app on :3000
cd web && npm install && npm run dev
```

Open http://localhost:3000. Upload a PDF or run a bundled real example; progress streams live over Server-Sent Events.

---

## Project structure

```
src/              CV + NLP pipeline
  ├─ preprocessing/   panel segmentation + content typing + text/scale-bar masking
  ├─ detectors/       copy-move, cross-figure, ai-generation, claim-consistency
  ├─ forensics/       frequency, noise-residual, residual clone test, JPEG blockiness
  ├─ pipeline/        orchestrator, risk scorer, evidence fusion (LLR), report builder
  ├─ evaluation/      benchmark runner, metrics (Wilson CIs, ROC/PR-AUC, LOOCV), error analysis
  ├─ nlp/             PDF parser, PMC-package (JATS+images) ingestion, claim/vision extraction
  └─ config/          config.yaml — single source of truth
server/           FastAPI bridge (thin transport; zero pipeline logic)
web/              Next.js 14 + Tailwind + Framer Motion + react-three-fiber
scripts/          data acquisition (PMC Open Access, Retraction Watch)
tests/            pytest suite
run_scholarguard.py   CLI entry point
```

## Building real datasets (optional)

```bash
export NCBI_CONTACT_EMAIL=you@institution.edu   # required by NCBI policy
python scripts/fetch_corpus.py --target-count 50
python scripts/fetch_evaluation_set.py --fraud-target 15 --clean-target 10

# A held-out TEST set as PMC packages (JATS XML + native figure images),
# disjoint from the calibration set above. Retracted fraud papers are almost
# never available as a PDF — only as packages — so this is how the Stage 2
# held-out numbers were produced. Both classes use the same package format.
# The clean class is a PMCID list, selected by the same terms and Retraction
# Watch screen as the calibration controls but without fetching PDFs the
# package benchmark never opens (~1 GB saved for 58 papers).
python scripts/build_heldout_clean_list.py --clean-target 58
python scripts/fetch_heldout_packages.py --fraud-target 30

# Papers are independent, so evaluate them in parallel (~11 min -> ~3 min for
# 80 papers on 16 cores; results are bit-identical to --workers 1).
python -m src.evaluation.benchmark_runner \
    --eval-config src/config/eval_config_heldout.yaml --workers 16
```

All scripts respect NCBI rate limits, skip already-fetched items via a resumable manifest, and record licensing. Datasets are never committed (see `.gitignore`) — they are re-fetchable from these scripts.

### Train the AI-generation classifier (optional; measured +0.048 ROC-AUC)

The AI detector ships forensics-only. Training its learned model is the one GPU step in the project, and it measures as **ROC-AUC 0.685 → 0.733, average precision 0.613 → 0.688, for 7 extra false alarms on 288 clean figures** — but read [Stage 2f](#stage-2f--what-the-classifier-is-actually-worth) before trusting it. On that same set a plain threshold change with no classifier at all matched the gain, and offline recalibration found the blended score *less* informative at the paper level than the forensic z-score. A 0.99 validation accuracy does not mean 0.99 in the wild. **Treat this as an experiment worth reproducing, not a settled upgrade.**

**The training data matters more than the training.** `data/ai_generated_samples/` holds *synthetic stand-ins* — a real sample bilateral-denoised with a checkerboard added — and [src/utils/synth.py](src/utils/synth.py) says so itself. A classifier trained on those learns `cv2.bilateralFilter`. Generate real diffusion output instead:

```bash
# 1. A real class: native PMC package figures (400 more on top of what you have)
export NCBI_CONTACT_EMAIL=you@institution.edu
python scripts/fetch_corpus.py --search-terms "western blot" "fluorescence microscopy" \
    "immunohistochemistry" --target-count 400 --output-dir data/clean

# 2. An AI class: genuine Stable-Diffusion output, with the resolution and JPEG
#    confounds matched to the real class so the model cannot separate them on
#    compression alone (~25 min for 400 images on a 24 GB card)
python scripts/generate_ai_figures.py --n 400 --batch-size 2 --render-size 768

# 3. Train (~1 min on a modern GPU). Figures whose PMCID appears in an
#    evaluation labels.json are dropped from the real class automatically --
#    without that, ~185 of 486 figures here would have been papers under test.
python scripts/train_artifact_classifier.py --epochs 8
```

That writes `src/models/weights/artifact_classifier.pt` (plus a `training_report.json` recording the split, exclusions and per-class metrics) and the detector picks it up automatically. [colab/train_artifact_classifier.ipynb](colab/train_artifact_classifier.ipynb) does the same on a free T4 if you have no local GPU.

The checkpoint format and architecture are kept in lock-step with the inference loader (`src/models/artifact_classifier.py`) — the local trainer calls that module's own `build_model`, and a round-trip test guarantees a trained checkpoint loads and blends into the AI verdict with zero glue work. Without a checkpoint the detector degrades to the frequency + noise forensics and the report says so.

## Tests

```bash
pytest -q      # 148 passed, 1 skipped
```

---

*Flags are leads for human review, not proof of misconduct. ScholarGuard analyzes figures locally; the Claude API is used only for optional text/claim extraction.*

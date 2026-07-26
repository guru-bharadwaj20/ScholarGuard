# Evaluation — how honest is it?

This is the project's report card *and* its changelog: where the metrics
started, what was changed and why, where they landed on **unseen data**, and
what is still open. Nothing here is spun. The numbers are unflattering where the
tool is weak, and where a later stage disproved an earlier one **both are left
standing** so the correction is visible — Stage 2e reports a gain that Stage 2g
then withdraws.

Every figure-level rate carries a 95% Wilson interval; every paper-level claim
is either threshold-free (ROC-AUC, average precision) or leave-one-out. Read the
intervals, not the point estimates: with 30 fraud papers per set they are wide
enough to swallow most single changes, which is the lesson of Stage 2g.

← [Back to the README](README.md)

---

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

### Stage 2g — a second held-out set overturns Stage 2e, and recall becomes measurable

Stage 2f ended with one question: is the AI gain the classifier's, or just a better-placed threshold? Answering it needed a set that none of the three configurations had ever seen. **The answer invalidates Stage 2e's headline.**

**A second held-out set: 30 fraud / 46 clean papers**, disjoint from both the calibration set *and* the Stage 2e set, fetched the same way. The three configurations, unchanged, re-run on it:

| Run | ROC-AUC | Avg precision | Precision / recall | Paper FPR | AI figure FPR |
|---|---|---|---|---|---|
| **A** shipped forensics | **0.664** | **0.567** | 0.523 / 0.767 | **0.457** | **5.4%** |
| **B** forensic ≥ 0.50, no classifier | 0.650 | 0.511 | 0.511 / 0.767 | 0.478 | 10.7% |
| **C** with classifier | 0.633 | 0.490 | 0.488 / 0.700 | 0.478 | 15.7% |

**The ordering reverses completely.** On Stage 2e's set the ranking was C ≈ B > A; on data none of them was tuned against it is **A > B > C**. The shipped forensics-only configuration wins outright, and the trained classifier is the *worst* of the three — its AI false-alarm rate nearly triples the baseline's (5.4% → 15.7%).

So Stage 2e's "+0.048 ROC-AUC from the classifier" **did not survive contact with a second sample**. Stage 2f had already shown a two-line threshold change reproduced it; Stage 2g shows neither reproduces on fresh data. The lasting result is the method, not the model: *one held-out set is not enough to accept a change in this project*, because a 30/50 split leaves confidence intervals wide enough to swallow an 0.05 AUC difference whole. Note also that the shipped AI detector's own false-alarm rate moved 1.4% → 5.4% between the two sets with no code change at all — a useful calibration of how much any single number here should be trusted.

**Nothing was shipped on the strength of Stage 2e**, which is why this costs nothing to correct: `config.yaml` still holds the forensics-only defaults, compression conditioning is still on, and the classifier remains opt-in. If you trained one following the instructions above, the honest advice is now: **don't enable it.**

### Per-detector recall — measured for the first time

Every previous stage reported recall as *not measurable*: Retraction Watch says a paper was retracted for "Duplication of/in Image", never which figure. [scripts/annotate_fraud_figures.py](scripts/annotate_fraud_figures.py) closes that gap by reading the retraction *notice* — a separate article that often does name figures — via PubMed's `RetractionIn` pointer. It found a notice for **60 of 60 fraud papers** across both sets and extracted figure numbers from 50 of them (the other 10 are bare "Retracted: <title>" with no detail), marking **130 figures** as manipulated.

With those labels, the shipped configuration finally has two-sided numbers, and they replicate across two independent sets:

| Detector | Recall (set 1) | Recall (set 2) | Precision (set 1) | Precision (set 2) |
|---|---|---|---|---|
| Copy-move | **0.576** (95% CI 0.46–0.69) | **0.476** (0.36–0.60) | 0.184 (0.14–0.24) | 0.146 (0.10–0.20) |
| Splice | **0.030** (0.01–0.10) | **0.048** (0.02–0.13) | 0.400 (0.12–0.77) | 0.273 (0.10–0.57) |
| Cross-figure | *no positives of its type* | — | — | — |
| AI-generation | *no positives of its type* | — | — | — |

**What this changes:**

- ✅ **Copy-move genuinely works, and now we know how well.** It finds roughly **half** the figures a retraction notice names (0.48–0.58 across two sets) — a real, replicated sensitivity that three prior stages could only guess at. Its precision is low (~0.15–0.18), so it stays a lead generator, but "noisy and useless" and "noisy but catching half of them" are very different tools, and until now we could not tell them apart.
- 🔴 **Splice is barely detecting anything.** Recall **0.03–0.05**. Stage 2c introduced it at 0.8% FPR and called it "essentially free evidence" — with only one side of the ledger visible. The other side is that it fires on ~1 in 25 of the figures it should. Its precision is the best of any detector, so it is not harmful; it is close to inert.
- ⚠️ **Cross-figure and AI recall are still unmeasurable**, for a structural reason: each annotated figure inherits a single `fraud_type` from its paper's retraction reason, and no paper's reason mapped to those two modes. Per-figure manipulation *types*, not just locations, are the next annotation step.
- ⚠️ **These labels are a lower bound.** A notice names the figures it discusses; other figures in the same paper may be manipulated but unmentioned. Detections on unnamed fraud-paper figures are therefore counted as false positives, which makes the precision numbers pessimistic and the fraud-paper false-alarm rate optimistic. Extraction is also automated regex over natural language — every annotation records its notice PMID and the surrounding sentence in `figure_annotations_audit.json` so it can be checked.

### Cross-figure residual gate — implemented, and it does nothing

The roadmap's top detector lever was to promote the residual-clone test from a damping factor to a hard veto on cross-figure matches, as the dense copy-move tier already does. It is implemented ([`residual_veto_independent`](src/config/config.yaml)) — and it **changes nothing at all**: gated and ungated runs produce byte-identical cross-figure output for all **546 figures across 80 papers**.

The reason is worth recording, because it redirects the work. Instrumenting the residual test through the orchestrator gives **30 of 30 verdicts as `CLONE`** (median correlation 1.000) and never `INDEPENDENT` — the veto condition simply never occurs. Cross-figure's false alarms are not honest look-alikes that a noise test can reject; they *pass* the noise test. Two contributors were identified: 4 of 50 clean packages ship byte-identical duplicate image files under different names, and publisher JPEG compression correlates residuals — the same effect this README already notes behind copy-move's spurious `CLONE` calls. The gate is kept (six lines, config-flagged, zero measured cost, plausibly useful on native uncompressed figures) but it is **not** the fix for cross-figure specificity.

### Stage 3 — what's still to do (in priority order)

1. **Annotate manipulation *type*, not just location.** Copy-move and splice now have recall; cross-figure and AI still do not, purely because each annotated figure inherits one `fraud_type` from its paper's retraction reason and no reason mapped to those modes. The notices already describe the manipulation ("duplicated from", "spliced", "overlapping with Figure X in another paper") — classifying that phrase per figure would complete the picture for every detector. This is the highest-value next step: it is the only thing that makes cross-figure and AI improvements steerable at all.
2. **Fix cross-figure specificity — but not with the residual test.** It remains the largest fixable false-positive source (27–29% per-figure), and Stage 2g rules out the approach the roadmap previously assumed: the matches pass the noise test rather than failing it. What is left is semantic — a caption/panel-role check so a labelled dose-response or time series is not read as duplication — plus a same-package duplicate-file guard, since 4 of 50 clean packages ship the same image under two names.
3. **Make splice work, or retire it.** Recall 0.03–0.05 across two sets means it is close to inert. Its 0.8% FPR bought nothing, because it almost never fires on the figures that matter. Either loosen it now that recall is measurable and the trade-off is visible, or drop it and reclaim its 20 risk-score points.
4. **Improve copy-move precision.** It is the one detector with proven sensitivity (recall ~0.5) and it produces the bulk of the false alarms (precision ~0.15). PatchMatch verification and a Zernike-moment rotation-invariant CMFD tier target the subtle cases SIFT misses; with recall now measurable, both sides of any change are finally visible.
5. **Adopt two-set validation as the standard.** Stage 2g showed a single 30/50 held-out set can reverse an 0.05 AUC verdict, and that the same detector's FPR moved 1.4% → 5.4% between sets with no code change. No change should be accepted on one set again. At `--workers 16` a full evaluation is ~3 minutes, so this costs almost nothing.
6. **Retrain the classifier on manipulated photographs, or drop it.** Stage 2f diagnosed why it adds so little and Stage 2g showed it actively hurts on fresh data: it learned diffusion-vs-micrograph, a distinction nearly orthogonal to how these papers were faked. A class built from spliced/duplicated *real* figures targets the right boundary; until then, leave it disabled.

**ScholarGuard is a screening prototype for human reviewers, not an autonomous accusation system. Every flag is a lead to be checked by a person.**

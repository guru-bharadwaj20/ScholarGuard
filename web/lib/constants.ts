/**
 * THE single source of truth for every measured number shown anywhere in this
 * app. Components must import from here — never hardcode a percentage — so the
 * numbers can never drift out of sync between views.
 *
 * Provenance: three INDEPENDENT held-out sets of real PubMed Central papers,
 * 30 formally-retracted image-fraud papers each, against 50 / 46 / 43 clean
 * controls. No overlap between sets, or with anything used for tuning.
 * Set 3 was downloaded fresh, screened, and run exactly once.
 *
 * Per-figure recall comes from scripts/annotate_fraud_figures.py, which reads
 * the retraction NOTICE (a separate article that often names figures) and
 * marked 197 figures across 90 papers as manipulated.
 *
 * Full write-up: EVALUATION.md. Reports live under outputs/heldout_run.../ as
 * metrics_summary.md.
 *
 * ⚠ These labels are a LOWER BOUND: a notice names the figures it discusses,
 * and other figures in the same paper may be manipulated but unmentioned.
 * Detections on unnamed fraud-paper figures are therefore counted as false
 * positives, which makes precision pessimistic and false-alarm rates optimistic.
 */

export type DetectorId =
  | "copy_move"
  | "cross_figure"
  | "splice"
  | "ai_generation"
  | "claim_consistency";

export type ReliabilityTier = "reliable" | "caution" | "unvalidated" | "inert";

export interface DetectorReliability {
  id: DetectorId;
  name: string;
  shortName: string;
  tier: ReliabilityTier;
  /** False-alarm rate on clean figures, per held-out set (%). */
  fprPercentBySet: number[];
  /** Representative FPR for single-number displays (the median set). */
  fprPercent: number | null;
  fprCi: string | null;
  /** Fraction of notice-named manipulated figures caught, per set. */
  recallBySet: number[] | null;
  recallNote: string;
  badgeLabel: string;
  plainExplanation: string;
}

const median = (xs: number[]): number =>
  [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

export const DETECTORS: Record<DetectorId, DetectorReliability> = {
  copy_move: {
    id: "copy_move",
    name: "Copy-move detector",
    shortName: "Copy-move",
    tier: "caution",
    fprPercentBySet: [39, 43, 49],
    fprPercent: 43,
    fprCi: "39–49% across three held-out sets",
    recallBySet: [0.57, 0.44, 0.59],
    recallNote: "catches about half the figures a retraction notice names",
    badgeLabel: "Catches ~half — but flags ~43% of clean figures",
    plainExplanation:
      "Looks for regions duplicated inside one figure. It is the most " +
      "sensitive detector here, replicated three times: it finds roughly " +
      "half the figures a retraction notice actually names. It also fires " +
      "on about 43% of clean figures, because legitimate science is full of " +
      "honest repetition — replicate panels, scale bars, repeated markers — " +
      "that is geometrically identical to a copy-paste. Its recall interval " +
      "still overlaps its own false-alarm interval, so treat it as a lead " +
      "generator, not a finding.",
  },
  cross_figure: {
    id: "cross_figure",
    name: "Cross-figure reuse detector",
    shortName: "Cross-figure",
    tier: "caution",
    fprPercentBySet: [27, 29, 26],
    fprPercent: 27,
    fprCi: "26–29% across three held-out sets",
    recallBySet: [0.33, 0.0, 0.31],
    recallNote: "0.33 / 0.00 / 0.31 — did not replicate on set 2",
    badgeLabel: "Unstable recall — flags ~27% of clean figures",
    plainExplanation:
      "Looks for one figure reusing content from another figure in the same " +
      "paper. It cannot distinguish fraudulent reuse from legitimately " +
      "similar figures — dose-response series and repeated experimental " +
      "layouts trip it on roughly a quarter of clean figures. Its recall " +
      "did not replicate: 0.33 and 0.31 on two sets, but 0.00 on the third.",
  },
  splice: {
    id: "splice",
    name: "Splice / foreign-region detector",
    shortName: "Splice",
    tier: "inert",
    fprPercentBySet: [1, 2, 1],
    fprPercent: 1,
    fprCi: "95% CI 0–3%",
    recallBySet: [0.02, 0.02, 0.02],
    recallNote: "0.02 on all three sets — fires on ~1 figure in 50",
    badgeLabel: "Almost never fires — recall 0.02",
    plainExplanation:
      "Looks for a region pasted in from a different source, by requiring " +
      "BOTH a foreign sensor-noise level AND a foreign compression " +
      "fingerprint on the same block. When it does fire it is the most " +
      "precise signal in the tool, and its false-alarm rate is the lowest " +
      "at about 1%. But it fires on only 1 in 50 of the figures it should, " +
      "identically on all three sets — so a silent splice detector is " +
      "close to no evidence either way, not reassurance.",
  },
  ai_generation: {
    id: "ai_generation",
    name: "AI-generation forensics",
    shortName: "AI generation",
    tier: "unvalidated",
    fprPercentBySet: [3, 4, 3],
    fprPercent: 3,
    fprCi: "3–4% across three held-out sets",
    recallBySet: null,
    recallNote: "not measurable — no notice describes a figure as generated",
    badgeLabel: "Low false-alarm rate, but recall never measured",
    plainExplanation:
      "Checks whether a figure's frequency spectrum and sensor-noise " +
      "statistics look like a real captured image or a generated one. It " +
      "rarely fires on clean papers (about 3%), but its ability to CATCH " +
      "generated figures has never been measured: no retraction notice in " +
      "any of the three sets describes a figure as AI-generated. A quiet " +
      "result here means nothing was found, not that nothing is there. The " +
      "optional trained classifier is disabled by default — it made results " +
      "worse on fresh data.",
  },
  claim_consistency: {
    id: "claim_consistency",
    name: "Claim-consistency checker",
    shortName: "Claim consistency",
    tier: "unvalidated",
    fprPercentBySet: [],
    fprPercent: null,
    fprCi: null,
    recallBySet: null,
    recallNote: "never evaluated against real papers",
    badgeLabel: "Unvalidated on real papers",
    plainExplanation:
      "Compares what the paper's text claims against what its figures show, " +
      "using an LLM. It was never evaluated against real papers (no API key " +
      "was available during testing) — treat it as unvalidated, not as " +
      "passing. Without an ANTHROPIC_API_KEY it is skipped entirely.",
  },
};

export const DETECTOR_ORDER: DetectorId[] = [
  "copy_move",
  "cross_figure",
  "splice",
  "ai_generation",
  "claim_consistency",
];

/** Max risk-score points each detector can contribute (config.yaml weights). */
export const DETECTOR_WEIGHTS: Record<DetectorId, number> = {
  copy_move: 25,
  cross_figure: 25,
  splice: 20,
  ai_generation: 20,
  claim_consistency: 10,
};

/** Combined pipeline, per held-out set. */
export const COMBINED = {
  sets: [
    { id: 1, nFraud: 30, nClean: 50, rocAuc: 0.685, countMatchedAuc: 0.571, figureCountOnlyAuc: 0.681, averagePrecision: 0.613, precision: 0.6, recall: 0.7 },
    { id: 2, nFraud: 30, nClean: 46, rocAuc: 0.664, countMatchedAuc: 0.632, figureCountOnlyAuc: 0.69, averagePrecision: 0.567, precision: 0.52, recall: 0.77 },
    { id: 3, nFraud: 30, nClean: 43, rocAuc: 0.668, countMatchedAuc: 0.625, figureCountOnlyAuc: 0.658, averagePrecision: 0.602, precision: 0.53, recall: 0.6 },
  ],
  /** Pooled, controlling for figure count. The number that should be believed. */
  pooledCountMatchedAuc: 0.61,
  pooledCountMatchedCi: "95% CI 0.482–0.725, 439 matched pairs",
  recallRangeText: "6–8 in 10 known-fraud papers",
  cleanFlaggedRangeText: "28–47% of clean ones",
} as const;

/** Every paper across all three held-out sets. */
export const TOTAL_PAPERS = COMBINED.sets.reduce(
  (n, s) => n + s.nFraud + s.nClean,
  0,
);

/** The permanent, non-dismissible limitation line under every risk gauge. */
export const ACCURACY_CEILING_NOTE =
  "Across three independent held-out sets this tool finds 6–8 in 10 known-" +
  "fraud papers while flagging 28–47% of clean ones. Controlling for how many " +
  "figures a paper has — retracted papers simply have more — its ranking " +
  "ability is 0.61 (95% CI 0.48–0.73), where 0.5 is chance. Treat every flag " +
  "as a prompt to look, not a finding.";

export const IN_SAMPLE_CAVEAT =
  "Figure-level labels come from retraction notices, which name only the " +
  "figures they discuss. Other figures in the same paper may be manipulated " +
  "but unmentioned, so these false-alarm rates are optimistic and the " +
  "precision figures pessimistic.";

export const SCREENING_DISCLAIMER =
  "ScholarGuard is a screening prototype for human reviewers, not an " +
  "autonomous accusation system. Every flag is a lead to be checked by a " +
  "person.";

export const RUNTIME_NOTE =
  "Real papers took anywhere from ~20 seconds to ~12 minutes in testing — " +
  "complex papers can take several minutes.";

/** Risk-zone thresholds mirror config.yaml risk_scoring.categories. */
export const RISK_ZONES = [
  { id: "low", label: "Low", from: 0, to: 25, colorClass: "bg-slate-500/50", textClass: "text-slate-300" },
  { id: "moderate", label: "Moderate", from: 25, to: 50, colorClass: "bg-caution/60", textClass: "text-caution" },
  { id: "high", label: "High", from: 50, to: 75, colorClass: "bg-elevated/60", textClass: "text-elevated" },
  { id: "critical", label: "Critical", from: 75, to: 100, colorClass: "bg-severe/60", textClass: "text-severe" },
] as const;

/** Numbers used by the methodology timeline (all measured, all real). */
export const JOURNEY = {
  // The FIRST real-data evaluation (2026-07), 15 retracted + 10 clean. These
  // are history, not the current headline -- the timeline narrates the arc, so
  // it must not reach into COMBINED, which now holds the three held-out sets.
  firstRealSetFraud: 15,
  firstRealSetClean: 10,
  firstRealSetAccuracyCeilingPercent: 60,
  firstRealSetRecallPercent: 80,
  firstRealSetRecallDetail: "12 of 15 real fraud papers caught",
  syntheticCopyMoveFprPercent: 10.3,
  syntheticAiFprPercent: 3.5,
  realCopyMoveFprBeforePercent: 72.3,
  realAiFprBeforePercent: 51.8,
  confidenceBlowup: 13.41, // documented contract was [0, 1]
  znccGarbageValue: 3906, // ZNCC must lie in [-1, 1]
  fraudMedianBefore: 56.3,
  cleanMedianBefore: 62.2,
  fraudMedianAfter: 47.0,
  cleanMedianAfter: 47.6,
  falsePositivesBefore: 126,
  falsePositivesAfter: 72,
  copyMoveFprAfterPercent: median(DETECTORS.copy_move.fprPercentBySet),
  aiFprAfterPercent: median(DETECTORS.ai_generation.fprPercentBySet),
} as const;

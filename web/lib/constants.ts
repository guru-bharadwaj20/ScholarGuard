/**
 * THE single source of truth for every measured reliability number shown
 * anywhere in this app. Components must import from here — never hardcode a
 * percentage — so the numbers can never drift out of sync between views.
 *
 * Provenance: Stage 7 real-data evaluation, 2026-07-11/12.
 *   - 25 real PMC Open Access papers: 15 formally retracted for image fraud
 *     (Retraction Watch), 10 never-retracted clean controls.
 *   - Full reports: outputs/stage7_results/real_data_run_v2/metrics_summary.md
 *
 * ⚠ OVERFITTING CAVEAT (must be shown, not hidden): detector thresholds were
 * recalibrated ON these same 25 papers — the only real data available. All
 * "after" numbers are optimistic in-sample estimates, NOT unbiased
 * measurements on unseen data.
 */

export type DetectorId =
  | "copy_move"
  | "cross_figure"
  | "ai_generation"
  | "claim_consistency";

export type ReliabilityTier = "reliable" | "caution" | "unvalidated";

export interface DetectorReliability {
  id: DetectorId;
  name: string;
  shortName: string;
  tier: ReliabilityTier;
  /** Measured real-world false-positive rate on 83 clean figures (v2 run). */
  fprPercent: number | null;
  fprCi: string | null;
  badgeLabel: string;
  plainExplanation: string;
}

export const DETECTORS: Record<DetectorId, DetectorReliability> = {
  ai_generation: {
    id: "ai_generation",
    name: "AI-generation forensics",
    shortName: "AI generation",
    tier: "reliable",
    fprPercent: 2.4,
    fprCi: "95% CI 0.7–8.4%",
    badgeLabel: "Comparatively reliable — 2.4% false-alarm rate",
    plainExplanation:
      "Checks whether a figure's frequency spectrum and sensor-noise " +
      "statistics look like a real captured image or a generated one. After " +
      "recalibration against real published figures it rarely fires on clean " +
      "papers (2.4% of clean figures) — but its ability to CATCH real " +
      "AI-generated figures has not been measured on real fraud cases.",
  },
  copy_move: {
    id: "copy_move",
    name: "Copy-move detector",
    shortName: "Copy-move",
    tier: "caution",
    fprPercent: 56.6,
    fprCi: "95% CI 46–67%",
    badgeLabel: "Frequently over-triggers — 56.6% false-alarm rate",
    plainExplanation:
      "Looks for regions duplicated inside one figure. It over-triggers on " +
      "more than half of clean real figures because legitimate science is " +
      "full of honest repetition — replicate panels, scale bars, repeated " +
      "markers — that is geometrically identical to a copy-paste. This is an " +
      "information limitation, not a tuning problem.",
  },
  cross_figure: {
    id: "cross_figure",
    name: "Cross-figure reuse detector",
    shortName: "Cross-figure",
    tier: "caution",
    fprPercent: 27.7,
    fprCi: "95% CI 19–38%",
    badgeLabel: "Frequently over-triggers — 27.7% false-alarm rate",
    plainExplanation:
      "Looks for one figure reusing content from another figure in the same " +
      "paper. It cannot distinguish fraudulent reuse from legitimately " +
      "similar figures — dose-response series and repeated experimental " +
      "layouts trip it about a quarter of the time on clean papers.",
  },
  claim_consistency: {
    id: "claim_consistency",
    name: "Claim-consistency checker",
    shortName: "Claim consistency",
    tier: "unvalidated",
    fprPercent: null,
    fprCi: null,
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
  "ai_generation",
  "claim_consistency",
];

/** Combined pipeline results on the real 25-paper evaluation (v2, post-fix). */
export const COMBINED = {
  nFraud: 15,
  nClean: 10,
  /** Best paper-level accuracy achievable at ANY single score threshold. */
  bestAccuracyPercent: 60,
  /** …which equals this eval set's base rate — i.e. no real separation. */
  baseRatePercent: 60,
  recallPercent: 80,
  recallDetail: "12 of 15 real fraud papers caught",
  falsePositiveRatePercent: 90,
  precisionPercent: 57.1,
} as const;

/** The permanent, non-dismissible limitation line under every risk gauge. */
export const ACCURACY_CEILING_NOTE =
  "This tool's real-world testing showed a 60% accuracy ceiling at telling " +
  "real fraud from clean papers — treat every flag as a prompt to look, not " +
  "a finding.";

export const IN_SAMPLE_CAVEAT =
  "All reliability numbers come from recalibrating on the same 25 real " +
  "papers used to measure them — optimistic, in-sample estimates, not " +
  "unbiased measurement on unseen data.";

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
  copyMoveFprAfterPercent: 56.6,
  aiFprAfterPercent: 2.4,
} as const;

"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  Bug,
  FlaskConical,
  Microscope,
  Scale,
  SearchCheck,
  Wrench,
} from "lucide-react";
import { COMBINED, IN_SAMPLE_CAVEAT, JOURNEY } from "@/lib/constants";
import { GlassCard } from "@/components/ui/card";

/**
 * The actual Stage 1–7 research story, told with the real measured numbers.
 * Every figure here traces back to lib/constants.ts and the Stage 7 reports.
 */

interface Step {
  icon: React.ReactNode;
  phase: string;
  title: string;
  body: React.ReactNode;
  metrics?: { label: string; value: string; tone?: "good" | "bad" | "neutral" }[];
}

const STEPS: Step[] = [
  {
    icon: <FlaskConical size={18} />,
    phase: "Stages 1–6",
    title: "Build, on synthetic ground truth",
    body: (
      <>
        Four detectors — copy-move, cross-figure reuse, AI-generation
        forensics, claim-consistency — unified into one config-driven
        pipeline. Development and first evaluation used synthetic forgeries,
        because real annotated fraud data is scarce.
      </>
    ),
    metrics: [
      { label: "copy-move false alarms (synthetic)", value: `${JOURNEY.syntheticCopyMoveFprPercent}%`, tone: "good" },
      { label: "AI-detector false alarms (synthetic)", value: `${JOURNEY.syntheticAiFprPercent}%`, tone: "good" },
    ],
  },
  {
    icon: <Microscope size={18} />,
    phase: "Stage 7 · real data",
    title: "Real papers broke it — and told the truth",
    body: (
      <>
        We downloaded {COMBINED.nFraud} formally retracted image-fraud papers
        (Retraction Watch × PMC Open Access) and {COMBINED.nClean} clean
        controls, then re-ran the whole benchmark. The result was inverted:
        clean papers scored <em>higher</em> than fraud papers (median{" "}
        {JOURNEY.cleanMedianBefore} vs {JOURNEY.fraudMedianBefore}). At the
        default threshold the pipeline flagged all 25 papers.
      </>
    ),
    metrics: [
      { label: "copy-move false alarms (real)", value: `${JOURNEY.realCopyMoveFprBeforePercent}%`, tone: "bad" },
      { label: "AI-detector false alarms (real)", value: `${JOURNEY.realAiFprBeforePercent}%`, tone: "bad" },
      { label: "fraud vs clean median score", value: `${JOURNEY.fraudMedianBefore} vs ${JOURNEY.cleanMedianBefore}`, tone: "bad" },
    ],
  },
  {
    icon: <Bug size={18} />,
    phase: "Root cause",
    title: "A confidence score that could reach 13.4 — on a 0-to-1 scale",
    body: (
      <>
        Instrumenting the worst figure caught it red-handed: on flat image
        regions the local correlation (ZNCC) divides by nearly zero, producing
        garbage values of ±{JOURNEY.znccGarbageValue.toLocaleString()} where
        mathematics says the range is [−1, 1]. A morphological fill pulled
        those pixels back into the scored region, and the unclamped mean drove
        &ldquo;confidence&rdquo; to {JOURNEY.confidenceBlowup}. Beneath the
        bug sat a design flaw: the score rewarded the raw <em>quantity</em> of
        self-similarity — which honest science (replicate panels, scale bars)
        has in abundance.
      </>
    ),
  },
  {
    icon: <Wrench size={18} />,
    phase: "The fix",
    title: "Score surprise, not similarity",
    body: (
      <>
        The confidence was redesigned as an observed-vs-expected statistic:
        how many standard deviations does the match count exceed what pure
        chance would produce (Poisson baseline → z-score → logistic), damped
        by how localized and well-correlated the region is. Bounded, monotonic,
        explainable. The AI detector&apos;s thresholds were recalibrated the
        same way — flag only what sits far above the measured real-figure
        baseline.
      </>
    ),
    metrics: [
      { label: "copy-move false alarms", value: `${JOURNEY.realCopyMoveFprBeforePercent}% → ${JOURNEY.copyMoveFprAfterPercent}%`, tone: "neutral" },
      { label: "AI-detector false alarms", value: `${JOURNEY.realAiFprBeforePercent}% → ${JOURNEY.aiFprAfterPercent}%`, tone: "good" },
      { label: "combined false positives", value: `${JOURNEY.falsePositivesBefore} → ${JOURNEY.falsePositivesAfter}`, tone: "good" },
    ],
  },
  {
    icon: <Scale size={18} />,
    phase: "The honest result",
    title: `A ${COMBINED.bestAccuracyPercent}% ceiling — stated, not hidden`,
    body: (
      <>
        After the fixes, the score inversion is gone (fraud median{" "}
        {JOURNEY.fraudMedianAfter} vs clean {JOURNEY.cleanMedianAfter}), and
        recall is {COMBINED.recallPercent}% ({COMBINED.recallDetail}). But the
        distributions still overlap: the best paper-level accuracy achievable
        at any single threshold is {COMBINED.bestAccuracyPercent}% — exactly
        this evaluation set&apos;s base rate. Copy-move&apos;s remaining false
        alarms are an information limitation: legitimate scientific repetition
        is geometrically identical to a copy-paste. No threshold fixes that.
      </>
    ),
    metrics: [
      { label: "recall on real fraud", value: `${COMBINED.recallPercent}%`, tone: "good" },
      { label: "best single-threshold accuracy", value: `${COMBINED.bestAccuracyPercent}% (= base rate)`, tone: "bad" },
    ],
  },
  {
    icon: <SearchCheck size={18} />,
    phase: "Methodological caveat",
    title: "These numbers are in-sample — deliberately disclosed",
    body: <>{IN_SAMPLE_CAVEAT} A fresh, never-seen real paper set is required
      before any of the post-fix numbers can be treated as unbiased.</>,
  },
];

const TONE_CLASS = {
  good: "text-reliable",
  bad: "text-caution",
  neutral: "text-slate-200",
} as const;

export function JourneyTimeline() {
  const reduce = useReducedMotion();
  return (
    <div className="relative ml-3 border-l border-ink-line pl-8">
      {STEPS.map((step, i) => (
        <motion.div
          key={i}
          initial={reduce ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.45 }}
          className="relative pb-12 last:pb-0"
        >
          {/* Node */}
          <span className="absolute -left-[45px] flex h-8 w-8 items-center justify-center rounded-full border border-ink-line bg-ink text-accent shadow-glass">
            {step.icon}
          </span>

          <p className="type-mono-label mb-1.5">{step.phase}</p>
          <h3 className="type-card-title mb-3 text-slate-100">{step.title}</h3>
          <GlassCard className="!p-5">
            <p className="type-body text-sm">{step.body}</p>
            {step.metrics && (
              <dl className="mt-4 grid gap-3 border-t border-ink-line pt-4 sm:grid-cols-3">
                {step.metrics.map((m) => (
                  <div key={m.label}>
                    <dt className="type-mono-label text-[10px]">{m.label}</dt>
                    <dd
                      className={`font-mono text-base ${TONE_CLASS[m.tone ?? "neutral"]}`}
                    >
                      {m.value}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </GlassCard>
        </motion.div>
      ))}
    </div>
  );
}

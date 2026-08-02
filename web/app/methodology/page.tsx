import type { Metadata } from "next";
import { JourneyTimeline } from "@/components/methodology/JourneyTimeline";
import { DetectorRadarChart } from "@/components/analysis/DetectorRadarChart";
import { DetectorReliabilityBadge } from "@/components/analysis/DetectorReliabilityBadge";
import { GlassCard, CardTitle } from "@/components/ui/card";
import {
  COMBINED,
  DETECTORS,
  DETECTOR_ORDER,
  TOTAL_PAPERS,
} from "@/lib/constants";

export const metadata: Metadata = {
  title: "Methodology — ScholarGuard",
  description:
    "How ScholarGuard was built and evaluated on real retracted papers — " +
    "including the bugs found, the fixes, and the measured 60% accuracy ceiling.",
};

export default function MethodologyPage() {
  return (
    <div className="py-12">
      <header className="mb-14 max-w-3xl">
        <h1 className="type-section text-slate-50">
          The research journey — including the part where it broke
        </h1>
        <p className="type-body mt-4">
          Most demos show you the version that works. This page shows the
          whole arc: a pipeline that looked strong on synthetic data, an
          evaluation against real papers that inverted its scores, the
          root-cause hunt that followed, and a fix that improved things — up
          to an honestly-measured ceiling, re-checked on{" "}
          {COMBINED.sets.length} independent held-out sets ({TOTAL_PAPERS}{" "}
          papers). The debugging is the feature.
        </p>
      </header>

      <JourneyTimeline />

      {/* Where each detector stands today */}
      <section className="mt-20">
        <h2 className="type-section text-slate-100">
          Where each detector stands
        </h2>
        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_380px]">
          <div className="space-y-4">
            {DETECTOR_ORDER.map((id) => {
              const d = DETECTORS[id];
              return (
                <GlassCard key={id} className="!p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <CardTitle>{d.name}</CardTitle>
                    <DetectorReliabilityBadge detector={id} />
                  </div>
                  <p className="type-body mt-3 text-sm">{d.plainExplanation}</p>
                </GlassCard>
              );
            })}
          </div>
          <DetectorRadarChart />
        </div>
      </section>

      {/* Where the numbers live */}
      <section className="mt-16">
        <GlassCard>
          <CardTitle>Verify every number yourself</CardTitle>
          <p className="type-body mt-3 text-sm">
            All metrics on this site are sourced from a single constants file
            in the frontend, which mirrors the pipeline&apos;s Stage 7 output:
          </p>
          <ul className="mt-4 space-y-1.5">
            <li className="type-mono-metric text-xs">
              outputs/stage7_results/real_data_run/metrics_summary.md — real
              data, before the fixes
            </li>
            <li className="type-mono-metric text-xs">
              outputs/stage7_results/real_data_run_v2/metrics_summary.md —
              real data, after the fixes (the numbers shown here)
            </li>
            <li className="type-mono-metric text-xs">
              web/lib/constants.ts — the single frontend source of truth
            </li>
          </ul>
        </GlassCard>
      </section>
    </div>
  );
}

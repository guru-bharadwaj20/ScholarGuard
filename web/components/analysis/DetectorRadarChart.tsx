"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { DETECTORS, DETECTOR_ORDER, IN_SAMPLE_CAVEAT } from "@/lib/constants";
import { GlassCard, CardTitle } from "@/components/ui/card";

/**
 * Radar of all five detectors' measured false-alarm rates on clean figures —
 * makes the uneven-reliability message immediate. claim_consistency has no
 * measurement (unvalidated), plotted as 0 with an explicit annotation so
 * absence-of-data is never dressed up as a good score.
 *
 * A low bar here is NOT automatically good: splice sits near 1% because it
 * almost never fires at all (recall 0.02), which the caption says outright.
 */

const data = DETECTOR_ORDER.map((id) => ({
  detector: DETECTORS[id].shortName,
  fpr: DETECTORS[id].fprPercent ?? 0,
  measured: DETECTORS[id].fprPercent !== null,
  recall: DETECTORS[id].recallNote,
}));

export function DetectorRadarChart() {
  return (
    <GlassCard>
      <CardTitle>False-alarm rates on real clean figures</CardTitle>
      <p className="type-meta mt-2 text-xs">
        Lower is better <em>only alongside recall</em>. Measured across three
        independent held-out sets (30 retracted vs 50/46/43 clean papers each).
      </p>

      <div className="mt-4 h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="72%">
            <PolarGrid stroke="rgba(255,255,255,0.10)" />
            <PolarAngleAxis
              dataKey="detector"
              tick={{ fill: "#94a3b8", fontSize: 12, fontFamily: "var(--font-jetbrains)" }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: "#64748b", fontSize: 10, fontFamily: "var(--font-jetbrains)" }}
              tickFormatter={(v) => `${v}%`}
              stroke="rgba(255,255,255,0.06)"
            />
            <Radar
              name="false-positive rate"
              dataKey="fpr"
              stroke="#d4a054"
              fill="#d4a054"
              fillOpacity={0.22}
            />
            <Tooltip
              formatter={(value: number, _name, entry) =>
                entry?.payload?.measured
                  ? [`${value}% — recall: ${entry.payload.recall}`,
                     "false-alarm rate"]
                  : ["not measured (unvalidated)", "false-alarm rate"]
              }
              contentStyle={{
                background: "#0e131b",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontFamily: "var(--font-jetbrains)",
                fontSize: 12,
              }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      <p className="type-meta text-xs">
        <span className="text-neutralsev">Claim consistency plots at 0 only
        because it was never measured</span> — it is unvalidated, not clean.
        Splice sits near 1% because it{" "}
        <span className="text-neutralsev">almost never fires at all</span>{" "}
        (recall 0.02 on every set), not because it is discriminating well.
      </p>
      <p className="type-meta mt-3 border-t border-ink-line pt-3 text-xs">
        {IN_SAMPLE_CAVEAT}
      </p>
    </GlassCard>
  );
}

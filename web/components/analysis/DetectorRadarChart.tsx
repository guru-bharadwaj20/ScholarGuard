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
 * Radar of the four detectors' measured real-world false-positive rates —
 * makes the uneven-reliability message immediate. claim_consistency has no
 * measurement (unvalidated), plotted as 0 with an explicit annotation so
 * absence-of-data is never dressed up as a good score.
 */

const data = DETECTOR_ORDER.map((id) => ({
  detector: DETECTORS[id].shortName,
  fpr: DETECTORS[id].fprPercent ?? 0,
  measured: DETECTORS[id].fprPercent !== null,
}));

export function DetectorRadarChart() {
  return (
    <GlassCard>
      <CardTitle>False-alarm rates on real clean figures</CardTitle>
      <p className="type-meta mt-2 text-xs">
        Lower is better. Measured on 83 clean figures from 10 never-retracted
        papers.
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
                  ? [`${value}%`, "false-alarm rate"]
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
      </p>
      <p className="type-meta mt-3 border-t border-ink-line pt-3 text-xs">
        {IN_SAMPLE_CAVEAT}
      </p>
    </GlassCard>
  );
}

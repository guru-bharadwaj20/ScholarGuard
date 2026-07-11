"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ACCURACY_CEILING_NOTE, RISK_ZONES } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * Horizontal zone indicator (low / moderate / high / critical), NOT a bare
 * giant number — the score needs visual context given the measured 60%
 * accuracy ceiling. Muted colors only; the ceiling note below the track is
 * permanent and non-dismissible by design.
 */
export function RiskGauge({ score, category }: { score: number; category: string }) {
  const reduce = useReducedMotion();
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="type-mono-label">overall risk score</span>
        <span className="font-mono text-2xl text-slate-100">
          {clamped.toFixed(1)}
          <span className="text-sm text-slate-500"> /100 · {category}</span>
        </span>
      </div>

      {/* Zone track */}
      <div className="relative">
        <div className="flex h-3 w-full overflow-hidden rounded-full border border-ink-line">
          {RISK_ZONES.map((z) => (
            <div
              key={z.id}
              className={cn("h-full", z.colorClass)}
              style={{ width: `${z.to - z.from}%` }}
            />
          ))}
        </div>
        {/* Marker */}
        <motion.div
          initial={reduce ? false : { left: "0%" }}
          animate={{ left: `${clamped}%` }}
          transition={{ type: "spring", stiffness: 60, damping: 16 }}
          className="absolute -top-1.5 h-6 w-[3px] -translate-x-1/2 rounded-full bg-slate-100 shadow-[0_0_8px_rgba(255,255,255,0.5)]"
          style={{ left: `${clamped}%` }}
        />
      </div>

      {/* Zone labels */}
      <div className="mt-2 flex w-full">
        {RISK_ZONES.map((z) => (
          <span
            key={z.id}
            style={{ width: `${z.to - z.from}%` }}
            className={cn(
              "type-mono-label text-center",
              category === z.id ? z.textClass : "text-slate-600",
            )}
          >
            {z.label}
          </span>
        ))}
      </div>

      {/* PERMANENT limitation text — not a tooltip, not dismissible. */}
      <p className="type-meta mt-4 rounded-lg border border-ink-line bg-slate-900/50 p-3 text-xs leading-relaxed">
        {ACCURACY_CEILING_NOTE}
      </p>
    </div>
  );
}

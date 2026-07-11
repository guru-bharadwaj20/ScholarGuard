"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Clock, FileText, Loader2, TriangleAlert } from "lucide-react";
import type { ProgressEvent } from "@/lib/api";
import { RUNTIME_NOTE } from "@/lib/constants";
import { GlassCard } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatElapsed } from "@/lib/utils";

/**
 * Live pipeline progress. Every line shown here is a REAL event parsed from
 * the orchestrator's own logging — "Parsing PDF", "Analyzing Figure 3 of 9",
 * "Compiling report". No fabricated steps, and deliberately no progress bar:
 * real runtimes ranged ~20 s to ~12 min, so an ETA would be a lie. We show
 * elapsed time and say so instead.
 */
export function LiveProgressPanel({
  events,
  running,
  label,
}: {
  events: ProgressEvent[];
  running: boolean;
  label: string;
}) {
  const [elapsed, setElapsed] = React.useState(0);
  React.useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [running]);

  const figureEvents = events.filter((e) => e.kind === "figure");
  const latest = events[events.length - 1];
  const total = events.find((e) => e.n_figures)?.n_figures ?? null;

  return (
    <GlassCard>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {running ? (
            <Loader2 size={18} className="animate-spin text-accent" />
          ) : (
            <FileText size={18} className="text-accent" />
          )}
          <span className="type-card-title">{label}</span>
        </div>
        <span className="type-mono-metric inline-flex items-center gap-2">
          <Clock size={13} className="text-slate-500" />
          {formatElapsed(elapsed)}
        </span>
      </div>

      {/* Latest status line */}
      <div className="mt-5 min-h-[24px]">
        <AnimatePresence mode="wait">
          <motion.p
            key={latest?.message ?? "starting"}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
            className="type-body"
          >
            {latest?.message ?? "Starting…"}
          </motion.p>
        </AnimatePresence>
      </div>

      {/* Figure tick-marks stream in as the pipeline reaches each figure */}
      {total !== null && (
        <div className="mt-5">
          <p className="type-mono-label mb-2">
            figures reached: {figureEvents.length} / {total}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {Array.from({ length: total }).map((_, i) => (
              <div
                key={i}
                className={
                  i < figureEvents.length
                    ? "h-2 w-6 rounded-sm bg-accent/70"
                    : "h-2 w-6 rounded-sm bg-slate-700/60"
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* Warnings surfaced from the pipeline (e.g. LLM skipped) */}
      {events
        .filter((e) => e.kind === "warning")
        .slice(-3)
        .map((w, i) => (
          <p
            key={i}
            className="type-meta mt-3 flex items-start gap-2 text-xs text-slate-400"
          >
            <TriangleAlert size={13} className="mt-0.5 shrink-0 text-caution" />
            {w.message}
          </p>
        ))}

      <p className="type-meta mt-5 border-t border-ink-line pt-4 text-xs">
        {RUNTIME_NOTE}
      </p>

      {/* Skeleton figure cards shimmer while results are being produced */}
      {running && total !== null && (
        <div className="mt-6 grid gap-3">
          {Array.from({ length: Math.min(3, total) }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}
    </GlassCard>
  );
}

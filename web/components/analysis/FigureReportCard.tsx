"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import type { DetectorResult, FigureReport } from "@/lib/api";
import { DETECTORS, type DetectorId } from "@/lib/constants";
import { GlassCard } from "@/components/ui/card";
import { DetectorReliabilityBadge } from "./DetectorReliabilityBadge";
import { ImageOverlayToggle } from "./ImageOverlayToggle";
import { cn } from "@/lib/utils";

/**
 * Per-figure report card. Every detector that fired is listed WITH its
 * reliability badge and a plain-English explanation. Figures with no flags
 * say "no signals fired here" — never "authentic".
 */

interface Flag {
  id: DetectorId;
  headline: string;
  detail: string;
}

function flagsFor(fig: FigureReport): Flag[] {
  const flags: Flag[] = [];
  const d = fig.detectors ?? {};

  const cm = d.copy_move;
  if (cm?.status === "ok" && cm.forged) {
    flags.push({
      id: "copy_move",
      headline: "Possible duplicated region inside this figure",
      detail:
        `The detector found ${cm.n_regions ?? "one or more"} region(s) that ` +
        `appear copied within the same figure (confidence ` +
        `${(cm.confidence ?? 0).toFixed(2)} of 1). Remember its measured ` +
        `false-alarm rate before reading anything into this.`,
    });
  }

  const cf = d.cross_figure;
  if (cf?.status === "ok" && ((cf.n_exact ?? 0) > 0 || (cf.n_region_reuse ?? 0) > 0)) {
    const what =
      (cf.n_exact ?? 0) > 0
        ? `${cf.n_exact} near-exact duplicate of another figure in this paper`
        : `${cf.n_region_reuse} region(s) that resemble content from another figure`;
    flags.push({
      id: "cross_figure",
      headline: "Possible reuse across figures",
      detail:
        `Found ${what}. Legitimately similar figures (repeated experimental ` +
        `layouts, dose-response series) trigger this too.`,
    });
  }

  const sp = d.splice;
  if (sp?.status === "ok" && sp.spliced) {
    flags.push({
      id: "splice",
      headline: "Possible region pasted in from another source",
      detail:
        `${sp.n_flagged_blocks ?? "Some"} block(s) show BOTH a foreign ` +
        `sensor-noise level and a foreign compression fingerprint ` +
        `(confidence ${(sp.confidence ?? 0).toFixed(2)} of 1). This is the ` +
        `most precise signal in the tool — but it fires on only 1 figure in ` +
        `50 of those it should, so its silence elsewhere means little.`,
    });
  }

  const ai = d.ai_generation;
  if (ai?.status === "ok" && ai.verdict && ai.verdict !== "likely_real") {
    flags.push({
      id: "ai_generation",
      headline:
        ai.verdict === "likely_ai_generated"
          ? "Image statistics unusually far from real-capture baseline"
          : "Image statistics mildly unusual",
      detail:
        `Frequency score ${(ai.freq_score ?? 0).toFixed(2)}, noise score ` +
        `${(ai.noise_score ?? 0).toFixed(2)} — ` +
        (ai.classifier_used
          ? "combined forensics + classifier verdict."
          : "forensics-only verdict (no trained classifier loaded)."),
    });
  }

  const cc = d.claim_consistency;
  if (cc?.status === "ok" && cc.consistent === false) {
    flags.push({
      id: "claim_consistency",
      headline: "Text claims may not match this figure",
      detail: (cc.mismatches ?? []).join("; ") || "Mismatch reported.",
    });
  }

  return flags;
}

function skippedDetectors(fig: FigureReport): DetectorId[] {
  return (Object.entries(fig.detectors ?? {}) as [DetectorId, DetectorResult][])
    .filter(([, r]) => r.status !== "ok")
    .map(([id]) => id)
    .filter((id): id is DetectorId => id in DETECTORS);
}

export function FigureReportCard({
  fig,
  index,
}: {
  fig: FigureReport;
  index: number;
}) {
  const [open, setOpen] = React.useState(false);
  const flags = flagsFor(fig);
  const skipped = skippedDetectors(fig);

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.4), duration: 0.35 }}
    >
      <GlassCard className="!p-0">
        {/* Header row — always visible */}
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-4 p-5 text-left"
          aria-expanded={open}
        >
          <div className="flex min-w-0 items-center gap-4">
            <span className="type-card-title shrink-0 text-slate-100">
              {fig.figure}
            </span>
            {flags.length === 0 ? (
              <span className="type-meta truncate">
                no signals fired here — this does not prove authenticity
              </span>
            ) : (
              <span className="type-meta truncate">
                {flags.length} signal{flags.length > 1 ? "s" : ""} ·{" "}
                {flags.map((f) => DETECTORS[f.id].shortName).join(", ")}
              </span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className="type-mono-metric">
              {fig.risk.score.toFixed(1)}
              <span className="text-slate-500">/100</span>
            </span>
            <ChevronDown
              size={16}
              className={cn(
                "text-slate-500 transition-transform duration-200",
                open && "rotate-180",
              )}
            />
          </div>
        </button>

        {/* Expanded body */}
        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.28, ease: "easeInOut" }}
              className="overflow-hidden"
            >
              <div className="grid gap-5 border-t border-ink-line p-5 lg:grid-cols-[320px_1fr]">
                {/* Image + overlay */}
                <div>
                  {fig.image_url ? (
                    <ImageOverlayToggle
                      imageUrl={fig.image_url}
                      overlayUrl={fig.overlay_url}
                      alt={`${fig.figure} of the analyzed paper`}
                    />
                  ) : (
                    <p className="type-meta">no image available</p>
                  )}
                  {fig.caption && (
                    <p className="type-meta mt-3 line-clamp-3 text-xs">
                      {fig.caption}
                    </p>
                  )}
                </div>

                {/* Flags with badges + plain English */}
                <div className="space-y-4">
                  {flags.length === 0 && (
                    <p className="type-body text-sm">
                      No detector produced a signal on this figure. That means
                      &ldquo;nothing found by these four methods&rdquo; — it is
                      not evidence the figure is authentic.
                    </p>
                  )}
                  {flags.map((f) => (
                    <div
                      key={f.id}
                      className="rounded-xl border border-ink-line bg-slate-900/40 p-4"
                    >
                      <div className="flex flex-wrap items-center gap-2.5">
                        <span className="font-body text-sm font-medium text-slate-100">
                          {DETECTORS[f.id].shortName}
                        </span>
                        <DetectorReliabilityBadge detector={f.id} />
                      </div>
                      <p className="type-body mt-2 text-sm text-slate-200">
                        {f.headline}
                      </p>
                      <p className="type-meta mt-1.5 text-xs leading-relaxed">
                        {f.detail}
                      </p>
                    </div>
                  ))}

                  {skipped.length > 0 && (
                    <p className="type-meta text-xs">
                      not run on this figure:{" "}
                      {skipped
                        .map(
                          (id) =>
                            `${DETECTORS[id].shortName} (${fig.detectors[id]?.status})`,
                        )
                        .join(" · ")}
                    </p>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </GlassCard>
    </motion.div>
  );
}

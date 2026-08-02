"use client";

import * as React from "react";
import { ChevronRight } from "lucide-react";
import type { DetectorResult, FigureReport } from "@/lib/api";
import { DETECTORS, type DetectorId } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * The measurements behind each detector's verdict — everything the report
 * carries that the summary prose leaves out: the splice detector's per-cue
 * block counts, the AI classifier's p(AI) when a checkpoint is loaded, and the
 * vision model's actual observations of the figure alongside the claims it was
 * checking them against.
 *
 * A reviewer deciding whether to trust a flag needs the numbers, not only the
 * adjective. Collapsed by default so the card stays readable.
 */

type Row = { label: string; value: React.ReactNode };

function rowsFor(id: DetectorId, r: DetectorResult): Row[] {
  if (r.status !== "ok") return [];
  const rows: Row[] = [];

  if (id === "copy_move") {
    rows.push({ label: "duplicated regions", value: r.n_regions ?? 0 });
    rows.push({
      label: "confidence",
      value: `${(r.confidence ?? 0).toFixed(3)} of 1`,
    });
  }

  if (id === "cross_figure") {
    rows.push({ label: "near-exact duplicates", value: r.n_exact ?? 0 });
    rows.push({ label: "reused regions", value: r.n_region_reuse ?? 0 });
    rows.push({
      label: "visual-similarity leads",
      value: `${r.n_visual_similar ?? 0} (score nothing on their own)`,
    });
  }

  if (id === "splice") {
    rows.push({ label: "flagged blocks", value: r.n_flagged_blocks ?? 0 });
    rows.push({
      label: "confidence",
      value: `${(r.confidence ?? 0).toFixed(3)} of 1`,
    });
    if (r.cues) {
      rows.push({
        label: "foreign noise level",
        value: `${r.cues.noise_inconsistency_blocks} blocks`,
      });
      rows.push({
        label: "JPEG-ghost",
        value: `${r.cues.jpeg_ghost_blocks} blocks`,
      });
      rows.push({ label: "error-level", value: `${r.cues.ela_blocks} blocks` });
      rows.push({
        label: "why so few",
        value:
          "a block counts only when a foreign NOISE level and a foreign " +
          "COMPRESSION fingerprint agree on it",
      });
    }
  }

  if (id === "ai_generation") {
    rows.push({ label: "verdict", value: r.verdict ?? "—" });
    rows.push({
      label: "frequency anomaly",
      value: (r.freq_score ?? 0).toFixed(3),
    });
    rows.push({
      label: "noise residual anomaly",
      value: (r.noise_score ?? 0).toFixed(3),
    });
    rows.push({
      label: "trained classifier",
      value: r.classifier_used
        ? `p(AI) = ${(r.classifier_score ?? 0).toFixed(3)}`
        : "not loaded — forensics-only verdict",
    });
  }

  if (id === "claim_consistency") {
    rows.push({
      label: "text and figure agree",
      value: r.consistent === false ? "no" : "yes",
    });
    rows.push({
      label: "confidence a problem exists",
      value: (r.confidence ?? 0).toFixed(3),
    });
    const obs = r.observations as Record<string, unknown> | null | undefined;
    if (obs) {
      if (obs.observed_panel_count != null) {
        rows.push({
          label: "panels the model saw",
          value: String(obs.observed_panel_count),
        });
      }
      if (obs.observed_lane_count != null) {
        rows.push({
          label: "lanes the model saw",
          value: String(obs.observed_lane_count),
        });
      }
      if (Array.isArray(obs.techniques) && obs.techniques.length) {
        rows.push({
          label: "techniques identified",
          value: (obs.techniques as string[]).join(", "),
        });
      }
      if (obs.notable_observations) {
        rows.push({
          label: "notes",
          value: String(obs.notable_observations),
        });
      }
    }
    const claims = r.claims as Record<string, unknown> | null | undefined;
    if (claims?.claimed_panel_count != null) {
      rows.push({
        label: "the text claimed",
        value: `${claims.claimed_panel_count} ${
          (claims.panel_count_kind as string) ?? "elements"
        }`,
      });
    }
    if (claims?.claimed_n != null) {
      rows.push({ label: "stated sample size", value: `n = ${claims.claimed_n}` });
    }
    for (const line of r.detector_context ?? []) {
      rows.push({ label: "context", value: line });
    }
  }

  return rows;
}

export function DetectorDetail({ fig }: { fig: FigureReport }) {
  const [open, setOpen] = React.useState(false);

  const sections = (Object.keys(DETECTORS) as DetectorId[])
    .map((id) => ({ id, result: fig.detectors?.[id], rows: [] as Row[] }))
    .filter((s) => Boolean(s.result))
    .map((s) => ({ ...s, rows: rowsFor(s.id, s.result as DetectorResult) }));

  if (!sections.length) return null;

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="type-mono-label inline-flex items-center gap-1.5 hover:text-slate-200"
      >
        <ChevronRight
          size={12}
          className={cn("transition-transform", open && "rotate-90")}
        />
        detector measurements
      </button>

      {open && (
        <div className="mt-3 space-y-4">
          {sections.map(({ id, result, rows }) => (
            <div key={id}>
              <p className="font-body text-xs text-slate-300">
                {DETECTORS[id].shortName}
                <span className="ml-2 font-mono text-[11px] text-slate-500">
                  {result!.status}
                </span>
              </p>
              {rows.length ? (
                <dl className="mt-1.5 grid grid-cols-[minmax(0,11rem)_1fr] gap-x-4 gap-y-1">
                  {rows.map((row, i) => (
                    <React.Fragment key={i}>
                      <dt className="type-mono-label text-[11px]">{row.label}</dt>
                      <dd className="font-body text-xs leading-relaxed text-slate-400">
                        {row.value}
                      </dd>
                    </React.Fragment>
                  ))}
                </dl>
              ) : (
                <p className="type-meta mt-1 text-xs">
                  {result!.reason ??
                    result!.error ??
                    "no measurements — this detector did not run on this figure"}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

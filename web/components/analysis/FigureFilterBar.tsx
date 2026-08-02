"use client";

import type { FigureReport } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Ordering and filtering for the figure list. The bundled fraud example has 15
 * figures and real papers go higher, so "scroll until you find the flagged
 * one" is not a workable review flow.
 *
 * Ordering by corroboration is offered first and is the default the evaluation
 * supports: ranking by the most-corroborated figure is what lifted held-out
 * average precision, whereas ranking by raw score inherits the figure-count
 * confound. Document order stays available because it is how the reader knows
 * the paper.
 */

export type FigureSort = "corroboration" | "score" | "document";
export type FigureFilter = "all" | "flagged";

const SORTS: { id: FigureSort; label: string; hint: string }[] = [
  {
    id: "corroboration",
    label: "agreement",
    hint: "figures where the most independent detectors agree first",
  },
  { id: "score", label: "score", hint: "highest risk score first" },
  { id: "document", label: "document order", hint: "as they appear in the paper" },
];

export function sortFigures(
  figures: FigureReport[],
  sort: FigureSort,
): FigureReport[] {
  const indexed = figures.map((fig, index) => ({ fig, index }));
  if (sort === "document") return figures;
  indexed.sort((a, b) => {
    if (sort === "corroboration") {
      const delta =
        (b.fig.risk?.n_corroborating_signals ?? 0) -
        (a.fig.risk?.n_corroborating_signals ?? 0);
      if (delta !== 0) return delta;
    }
    const byScore = (b.fig.risk?.score ?? 0) - (a.fig.risk?.score ?? 0);
    // Stable within ties, so the order does not jitter between renders.
    return byScore !== 0 ? byScore : a.index - b.index;
  });
  return indexed.map((entry) => entry.fig);
}

export function filterFigures(
  figures: FigureReport[],
  filter: FigureFilter,
  threshold: number,
): FigureReport[] {
  if (filter === "all") return figures;
  return figures.filter(
    (f) =>
      (f.risk?.score ?? 0) >= threshold ||
      (f.risk?.n_corroborating_signals ?? 0) >= 2,
  );
}

export function FigureFilterBar({
  sort,
  onSort,
  filter,
  onFilter,
  shown,
  total,
  threshold,
}: {
  sort: FigureSort;
  onSort: (s: FigureSort) => void;
  filter: FigureFilter;
  onFilter: (f: FigureFilter) => void;
  shown: number;
  total: number;
  threshold: number;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-ink-line bg-slate-900/30 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="type-mono-label">order by</span>
        {SORTS.map((s) => (
          <button
            key={s.id}
            onClick={() => onSort(s.id)}
            title={s.hint}
            aria-pressed={sort === s.id}
            className={cn(
              "rounded-md px-2.5 py-1 font-mono text-[11px] transition-colors",
              sort === s.id
                ? "bg-accent/15 text-accent"
                : "text-slate-400 hover:text-slate-200",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <label className="type-mono-label inline-flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={filter === "flagged"}
            onChange={(e) => onFilter(e.target.checked ? "flagged" : "all")}
            className="h-3.5 w-3.5 accent-accent"
          />
          only figures worth reviewing
        </label>
        <span className="type-mono-label">
          {shown} / {total}
        </span>
      </div>

      {filter === "flagged" && (
        <p className="type-meta w-full text-xs">
          Showing figures scoring ≥ {threshold} or with two detectors agreeing.
          A hidden figure is one nothing fired on — which is not evidence it is
          authentic.
        </p>
      )}
    </div>
  );
}

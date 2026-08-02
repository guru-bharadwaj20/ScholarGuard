import type { RiskBreakdownEntry } from "@/lib/api";
import { DETECTORS, type DetectorId } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * The actual arithmetic behind a figure's score, which the UI previously did
 * not show at all: it rendered hand-written flag prose instead, so a reader
 * could see "30.0/100" and had no way to learn which detector contributed what.
 *
 * Every detector gets a row, including the ones that scored nothing — a
 * skipped or errored detector is information, not an absence, and hiding it
 * would let a figure look thoroughly checked when half the pipeline never ran.
 *
 * `fired` is read from the report rather than inferred from `points > 0`: a
 * lead-only detector (weight 0) fires and corroborates without scoring.
 */

const STATUS_LABEL: Record<string, string> = {
  ok: "ran",
  skipped: "skipped",
  skipped_optimization: "skipped (cost)",
  disabled: "disabled",
  error: "errored",
};

function statusTone(status: string): string {
  if (status === "ok") return "text-slate-300";
  if (status === "error") return "text-caution";
  return "text-slate-500";
}

export function DetectorScoreTable({
  breakdown,
  score,
}: {
  breakdown: RiskBreakdownEntry[];
  score: number;
}) {
  if (!breakdown?.length) {
    return (
      <p className="type-meta text-xs">No scoring breakdown in this report.</p>
    );
  }

  const maxTotal = breakdown.reduce((n, b) => n + (b.max_points ?? 0), 0);

  return (
    <div>
      <p className="type-mono-label mb-2">how this score was reached</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-collapse text-left">
          <thead>
            <tr className="border-b border-ink-line">
              <th className="type-mono-label pb-2 pr-3 font-normal">detector</th>
              <th className="type-mono-label pb-2 pr-3 font-normal">status</th>
              <th className="type-mono-label pb-2 pr-3 text-right font-normal">
                points
              </th>
              <th className="type-mono-label pb-2 font-normal">finding</th>
            </tr>
          </thead>
          <tbody>
            {breakdown.map((row) => {
              const spec = DETECTORS[row.detector as DetectorId];
              const share = row.max_points
                ? (row.points ?? 0) / row.max_points
                : 0;
              return (
                <tr
                  key={row.detector}
                  className="border-b border-ink-line/50 align-top last:border-0"
                >
                  <td className="py-2 pr-3">
                    <span className="font-body text-sm text-slate-200">
                      {spec?.shortName ?? row.detector}
                    </span>
                    {row.fired && (
                      <span
                        className="ml-2 rounded-full bg-accent/15 px-1.5 py-0.5 font-mono text-[10px] text-accent"
                        title="This detector produced a signal on this figure"
                      >
                        fired
                      </span>
                    )}
                  </td>
                  <td className={cn("py-2 pr-3 font-mono text-xs", statusTone(row.status))}>
                    {STATUS_LABEL[row.status] ?? row.status}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    <span className="type-mono-metric">
                      {(row.points ?? 0).toFixed(2)}
                      <span className="text-slate-500">/{row.max_points}</span>
                    </span>
                    {/* Proportion of this detector's own maximum. */}
                    <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-slate-700/50">
                      <div
                        className="h-full rounded-full bg-accent/60"
                        style={{ width: `${Math.round(share * 100)}%` }}
                      />
                    </div>
                  </td>
                  <td className="py-2 font-body text-xs leading-relaxed text-slate-400">
                    {row.note}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-ink-line">
              <td className="pt-2 font-body text-sm text-slate-200" colSpan={2}>
                total
              </td>
              <td className="pt-2 text-right">
                <span className="type-mono-metric">
                  {score.toFixed(2)}
                  <span className="text-slate-500">/{maxTotal}</span>
                </span>
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

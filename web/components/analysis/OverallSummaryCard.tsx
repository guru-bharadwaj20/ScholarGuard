import type { PipelineReport } from "@/lib/api";
import { GlassCard, CardTitle } from "@/components/ui/card";
import { RiskGauge } from "./RiskGauge";

/**
 * Leads with a plain-language sentence BEFORE any number, then the zone
 * gauge with its permanent limitation note.
 */
export function OverallSummaryCard({ report }: { report: PipelineReport }) {
  const figures = report.figures ?? [];
  const flagged = figures.filter((f) => f.risk.score >= 25);
  const strongMultiSignal = figures.filter((f) => {
    const firing = f.risk.breakdown.filter(
      (b) => b.status === "ok" && b.points > 0,
    );
    return firing.length >= 2 && f.risk.score >= 50;
  });

  const plainSentence =
    figures.length === 0
      ? "No figures could be extracted from this PDF, so there is nothing to review."
      : `${flagged.length} of ${figures.length} figure${figures.length === 1 ? "" : "s"} show${flagged.length === 1 ? "s" : ""} patterns worth reviewing; ` +
        (strongMultiSignal.length > 0
          ? `${strongMultiSignal.length} show${strongMultiSignal.length === 1 ? "s" : ""} agreement across multiple signals.`
          : "none show strong evidence across multiple signals.");

  return (
    <GlassCard>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <CardTitle>{report.paper.filename}</CardTitle>
        {report.job && (
          <span className="type-mono-label">
            analyzed in {Math.round(report.job.runtime_sec)}s
          </span>
        )}
      </div>

      <p className="type-body mt-4 text-slate-100">{plainSentence}</p>

      <div className="mt-7">
        <RiskGauge
          score={report.overall_risk.score}
          category={report.overall_risk.category}
        />
      </div>

      {report.pipeline_warnings?.length > 0 && (
        <div className="mt-5 border-t border-ink-line pt-4">
          <p className="type-mono-label mb-2">pipeline notes</p>
          {report.pipeline_warnings.map((w, i) => (
            <p key={i} className="type-meta text-xs leading-relaxed">
              · {w}
            </p>
          ))}
        </div>
      )}
    </GlassCard>
  );
}

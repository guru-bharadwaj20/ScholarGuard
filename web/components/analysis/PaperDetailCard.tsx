"use client";

import * as React from "react";
import { ChevronRight, Download, FileJson, FileText } from "lucide-react";
import { apiUrl, type PipelineReport } from "@/lib/api";
import { GlassCard, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Everything the report says about the paper as a whole, plus the artefacts a
 * reviewer keeps.
 *
 * The pipeline has always written a JSON report and a Markdown summary to
 * disk, and the API now serves both — before this there was no way to take the
 * result away from the browser, which makes it useless as evidence in a review
 * that outlives the tab. The raw JSON is viewable inline too: this tool asks to
 * be checked rather than believed, and that is hard to do through a summary.
 */

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div>
      <dt className="type-mono-label">{label}</dt>
      <dd className="type-mono-metric mt-0.5 text-slate-100">{value}</dd>
      {hint && <p className="type-meta mt-1 text-xs">{hint}</p>}
    </div>
  );
}

export function PaperDetailCard({ report }: { report: PipelineReport }) {
  const [showJson, setShowJson] = React.useState(false);
  const risk = report.overall_risk;
  const downloads = report.downloads ?? {};
  const sections = report.paper?.sections_found ?? [];

  return (
    <GlassCard>
      <CardTitle>Paper-level detail</CardTitle>

      <dl className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3">
        <Stat label="figures analyzed" value={risk.n_figures ?? 0} />
        <Stat
          label="worst single figure"
          value={
            risk.worst_figure_score != null
              ? `${risk.worst_figure_score.toFixed(1)}`
              : "—"
          }
          hint={risk.worst_figure_category ?? undefined}
        />
        <Stat
          label="most detectors agreeing"
          value={risk.max_corroboration ?? 0}
          hint="on any one figure"
        />
        {risk.fraud_probability != null && (
          <Stat
            label="calibrated probability"
            value={`${(risk.fraud_probability * 100).toFixed(1)}%`}
            hint="noisy-OR across figures"
          />
        )}
        <Stat
          label="analysis time"
          value={
            report.job ? `${Math.round(report.job.runtime_sec)}s` : "—"
          }
        />
        <Stat
          label="report generated"
          value={new Date(report.generated_at).toLocaleTimeString()}
          hint={report.schema_version}
        />
      </dl>

      {sections.length > 0 && (
        <div className="mt-6 border-t border-ink-line pt-4">
          <p className="type-mono-label mb-2">sections the parser found</p>
          <div className="flex flex-wrap gap-1.5">
            {sections.map((s) => (
              <span
                key={s}
                className="rounded-md border border-ink-line bg-slate-900/50 px-2 py-0.5 font-mono text-[11px] text-slate-400"
              >
                {s}
              </span>
            ))}
          </div>
          <p className="type-meta mt-2 text-xs">
            Text extraction is heuristic; a missing section means the parser
            could not identify it, not that the paper lacks one.
          </p>
        </div>
      )}

      {/* Take-away artefacts */}
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-ink-line pt-4">
        {downloads.json && (
          <a
            href={apiUrl(downloads.json)}
            download
            className="inline-flex items-center gap-2 rounded-lg border border-ink-line bg-slate-900/50 px-3 py-2 font-body text-sm text-slate-200 transition-colors hover:border-accent/50 hover:text-accent"
          >
            <FileJson size={14} /> Full report (JSON)
          </a>
        )}
        {downloads.md && (
          <a
            href={apiUrl(downloads.md)}
            download
            className="inline-flex items-center gap-2 rounded-lg border border-ink-line bg-slate-900/50 px-3 py-2 font-body text-sm text-slate-200 transition-colors hover:border-accent/50 hover:text-accent"
          >
            <FileText size={14} /> Readable summary (Markdown)
          </a>
        )}
        {!downloads.json && !downloads.md && (
          <p className="type-meta inline-flex items-center gap-2 text-xs">
            <Download size={13} /> No saved report files for this run.
          </p>
        )}
      </div>

      {/* Raw JSON, so the summary above can be checked against the source. */}
      <div className="mt-4 border-t border-ink-line pt-4">
        <button
          onClick={() => setShowJson((v) => !v)}
          aria-expanded={showJson}
          className="type-mono-label inline-flex items-center gap-1.5 hover:text-slate-200"
        >
          <ChevronRight
            size={12}
            className={cn("transition-transform", showJson && "rotate-90")}
          />
          raw report JSON
        </button>
        {showJson && (
          <pre className="mt-3 max-h-96 overflow-auto rounded-lg border border-ink-line bg-ink/60 p-4 font-mono text-[11px] leading-relaxed text-slate-400">
            {JSON.stringify(report, null, 2)}
          </pre>
        )}
      </div>
    </GlassCard>
  );
}

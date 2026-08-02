import type { FigureRisk } from "@/lib/api";
import { DETECTORS, type DetectorId } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * The calibrated evidence layer, which the backend computes on every figure and
 * the UI never showed.
 *
 * The 0–100 point score treats every detector as worth its fixed weight. This
 * does not: each detector contributes a log-likelihood ratio,
 * log P(signal | fraud) / P(signal | clean), so one whose fire rate is about
 * the same on fraud and clean papers contributes ~0 and is discounted
 * automatically. That is the honest reading of a copy-move flag whose measured
 * false-alarm rate is 43%, and it belongs in front of the reviewer.
 *
 * Bars are signed: right of centre is evidence FOR manipulation, left is
 * evidence AGAINST. A detector that ran and stayed quiet genuinely argues the
 * other way, and hiding that would overstate the case.
 */

function contributionLabel(fired: boolean | null): string {
  if (fired === null) return "did not run";
  return fired ? "fired" : "stayed quiet";
}

export function EvidencePanel({ risk }: { risk: FigureRisk }) {
  const evidence = risk?.evidence;
  if (!evidence?.contributions?.length) return null;

  const probability = risk.fraud_probability ?? evidence.fraud_probability ?? 0;
  const widest = Math.max(
    0.35,
    ...evidence.contributions.map((c) => Math.abs(c.log_likelihood_ratio)),
  );

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="type-mono-label">calibrated evidence</p>
        <p className="type-mono-metric">
          {(probability * 100).toFixed(1)}%
          <span className="text-slate-500"> posterior</span>
        </p>
      </div>

      <p className="type-meta mt-2 text-xs leading-relaxed">
        Each detector contributes its measured likelihood ratio, so a signal
        that fires nearly as often on clean papers as on fraudulent ones counts
        for almost nothing. Starts from a low per-figure prior — most figures
        are genuine even in a fraudulent paper.
      </p>

      <ul className="mt-4 space-y-2.5">
        {evidence.contributions.map((c) => {
          const spec = DETECTORS[c.detector as DetectorId];
          const llr = c.log_likelihood_ratio;
          const magnitude = Math.min(1, Math.abs(llr) / widest);
          const towardsFraud = llr > 0;
          return (
            <li key={c.detector}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-body text-xs text-slate-300">
                  {spec?.shortName ?? c.detector}
                  <span className="ml-2 text-slate-500">
                    {contributionLabel(c.fired)}
                  </span>
                </span>
                <span
                  className={cn(
                    "font-mono text-[11px]",
                    llr === 0 && "text-slate-500",
                    llr > 0 && "text-caution",
                    llr < 0 && "text-reliable",
                  )}
                >
                  {llr > 0 ? "+" : ""}
                  {llr.toFixed(2)}
                </span>
              </div>
              {/* Diverging bar: centre line is "no evidence either way". */}
              <div className="relative mt-1 h-1.5 w-full rounded-full bg-slate-800/70">
                <div className="absolute inset-y-0 left-1/2 w-px bg-slate-600" />
                <div
                  className={cn(
                    "absolute inset-y-0 rounded-full",
                    towardsFraud ? "bg-caution/70" : "bg-reliable/60",
                  )}
                  style={{
                    width: `${(magnitude * 50).toFixed(1)}%`,
                    left: towardsFraud ? "50%" : undefined,
                    right: towardsFraud ? undefined : "50%",
                  }}
                />
              </div>
            </li>
          );
        })}
      </ul>

      <div className="mt-3 flex items-center justify-between">
        <span className="type-mono-label text-[10px]">← argues clean</span>
        <span className="type-mono-label text-[10px]">
          log-odds {evidence.log_odds?.toFixed(2)}
        </span>
        <span className="type-mono-label text-[10px]">argues manipulated →</span>
      </div>
    </div>
  );
}

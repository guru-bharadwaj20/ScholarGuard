"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import {
  getResult,
  startExample,
  startUpload,
  streamProgress,
  type PipelineReport,
  type ProgressEvent,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { UploadDropzone } from "@/components/upload/UploadDropzone";
import { ExamplePaperPicker } from "@/components/upload/ExamplePaperPicker";
import { LiveProgressPanel } from "@/components/analysis/LiveProgressPanel";
import { OverallSummaryCard } from "@/components/analysis/OverallSummaryCard";
import { DetectorRadarChart } from "@/components/analysis/DetectorRadarChart";
import { FigureReportCard } from "@/components/analysis/FigureReportCard";
import { SCREENING_DISCLAIMER } from "@/lib/constants";

type Phase = "idle" | "running" | "done" | "failed";

function AnalyzeInner() {
  const search = useSearchParams();
  const [phase, setPhase] = React.useState<Phase>("idle");
  const [label, setLabel] = React.useState("");
  const [events, setEvents] = React.useState<ProgressEvent[]>([]);
  const [report, setReport] = React.useState<PipelineReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const unsubscribe = React.useRef<(() => void) | null>(null);
  const autoStarted = React.useRef(false);

  const begin = React.useCallback((jobId: string, jobLabel: string) => {
    setPhase("running");
    setLabel(jobLabel);
    setEvents([]);
    setReport(null);
    setError(null);
    unsubscribe.current = streamProgress(
      jobId,
      (ev) => setEvents((prev) => [...prev, ev]),
      async (status) => {
        try {
          const rep = await getResult(jobId);
          if (rep.status === "failed") {
            setError(rep.error ?? "The pipeline could not analyze this PDF.");
            setPhase("failed");
          } else {
            setReport(rep);
            setPhase("done");
          }
        } catch {
          setError(
            status === "failed"
              ? "The analysis failed — check the backend logs."
              : "Could not fetch the result — is the backend still running?",
          );
          setPhase("failed");
        }
      },
    );
  }, []);

  React.useEffect(() => () => unsubscribe.current?.(), []);

  // Deep-link support: /analyze?example=fraud-retracted (from Cmd+K).
  React.useEffect(() => {
    const ex = search.get("example");
    if (ex && !autoStarted.current && phase === "idle") {
      autoStarted.current = true;
      startExample(ex)
        .then(({ job_id }) => begin(job_id, "Example paper"))
        .catch((e) =>
          setError(e instanceof Error ? e.message : "Could not start the example."),
        );
    }
  }, [search, phase, begin]);

  const reset = () => {
    unsubscribe.current?.();
    setPhase("idle");
    setEvents([]);
    setReport(null);
    setError(null);
  };

  return (
    <div className="py-12">
      <motion.header
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-10"
      >
        <h1 className="type-section text-slate-50">Analyze a paper</h1>
        <p className="type-body mt-2 max-w-2xl">{SCREENING_DISCLAIMER}</p>
      </motion.header>

      {phase === "idle" && (
        <div className="space-y-10">
          <UploadDropzone
            onFile={async (file) => {
              const { job_id } = await startUpload(file);
              begin(job_id, file.name);
            }}
          />
          {error && <p className="type-body text-caution">{error}</p>}
          <div>
            <h2 className="type-card-title mb-4 text-slate-200">
              …or run a bundled real example
            </h2>
            <ExamplePaperPicker
              onStart={async (id) => {
                const { job_id } = await startExample(id);
                begin(job_id, "Example paper");
              }}
            />
          </div>
        </div>
      )}

      {phase === "running" && (
        <LiveProgressPanel events={events} running label={label} />
      )}

      {phase === "failed" && (
        <div className="glass glass-pad">
          <p className="type-body">{error}</p>
          <Button variant="ghost" className="mt-5" onClick={reset}>
            <RotateCcw size={15} /> Try another paper
          </Button>
        </div>
      )}

      {phase === "done" && report && (
        <div className="space-y-6">
          <OverallSummaryCard report={report} />

          <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
            <div className="space-y-4">
              <h2 className="type-card-title text-slate-200">
                Per-figure findings
              </h2>
              {report.figures.length === 0 && (
                <p className="type-body">No figures were extracted.</p>
              )}
              {report.figures.map((fig, i) => (
                <FigureReportCard key={i} fig={fig} index={i} />
              ))}
            </div>
            <div className="space-y-6">
              <DetectorRadarChart />
              <Button variant="ghost" onClick={reset} className="w-full">
                <RotateCcw size={15} /> Analyze another paper
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalyzePage() {
  // useSearchParams requires a Suspense boundary in the App Router.
  return (
    <React.Suspense fallback={null}>
      <AnalyzeInner />
    </React.Suspense>
  );
}

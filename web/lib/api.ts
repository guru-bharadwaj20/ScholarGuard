/**
 * Typed client for the FastAPI bridge. All calls go through the Next.js
 * rewrite (/api/* -> http://127.0.0.1:8000/*), so the browser stays
 * same-origin and EventSource works without CORS ceremony.
 */

const BASE = "/api";

// ---------------------------------------------------------------------------
// Report types — mirror the Stage 6 JSON schema (scholarguard/stage6/1.0).
// ---------------------------------------------------------------------------

export interface DetectorResult {
  status: "ok" | "skipped" | "error" | "disabled" | "skipped_optimization";
  // copy_move
  forged?: boolean;
  confidence?: number;
  n_regions?: number;
  // cross_figure
  n_exact?: number;
  n_region_reuse?: number;
  n_visual_similar?: number;
  // ai_generation
  verdict?: "likely_real" | "suspicious" | "likely_ai_generated";
  freq_score?: number;
  noise_score?: number;
  classifier_used?: boolean;
  // claim_consistency
  consistent?: boolean;
  mismatches?: string[];
  reason?: string;
  error?: string;
}

export interface RiskBreakdownEntry {
  detector: string;
  status: string;
  max_points: number;
  points: number;
  note: string;
}

export interface FigureRisk {
  score: number;
  category: "low" | "moderate" | "high" | "critical";
  breakdown: RiskBreakdownEntry[];
}

export interface FigureReport {
  figure: string;
  figure_num: number | null;
  caption: string | null;
  detectors: Record<string, DetectorResult>;
  risk: FigureRisk;
  image_url: string | null;
  overlay_url: string | null;
}

export interface OverallRisk {
  score: number;
  category: "low" | "moderate" | "high" | "critical" | "unknown";
  n_figures: number;
  worst_figure_score?: number;
  worst_figure_category?: string;
}

export interface PipelineReport {
  schema_version: string;
  generated_at: string;
  paper: { filename: string; n_figures: number; sections_found: string[] };
  status: "completed" | "completed_no_figures" | "failed";
  error: string | null;
  overall_risk: OverallRisk;
  figures: FigureReport[];
  pipeline_warnings: string[];
  disclaimer: string;
  job?: { job_id: string; label: string; runtime_sec: number };
}

export interface ExampleMeta {
  id: string;
  title: string;
  description: string;
  kind: "fraud" | "clean";
  expected_runtime: string;
  honesty_note: string | null;
  available: boolean;
}

export interface ProgressEvent {
  kind:
    | "started"
    | "parsed"
    | "figure"
    | "scored"
    | "saved"
    | "warning"
    | "completed"
    | "failed";
  message: string;
  t: number;
  index?: number;
  total?: number;
  label?: string;
  n_figures?: number;
}

// ---------------------------------------------------------------------------
// Calls
// ---------------------------------------------------------------------------

export async function getHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function getExamples(): Promise<ExampleMeta[]> {
  const res = await fetch(`${BASE}/examples`, { cache: "no-store" });
  if (!res.ok) throw new Error("Could not load example papers.");
  return res.json();
}

export async function startUpload(file: File): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "The upload could not be started.");
  }
  return res.json();
}

export async function startExample(id: string): Promise<{ job_id: string }> {
  const res = await fetch(`${BASE}/analyze/example/${id}`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "The example could not be started.");
  }
  return res.json();
}

export async function getResult(jobId: string): Promise<PipelineReport> {
  const res = await fetch(`${BASE}/analyze/${jobId}/result`, { cache: "no-store" });
  if (!res.ok) throw new Error("Result not available yet.");
  return res.json();
}

/** Absolute (same-origin) URL for a figure image path returned by the API. */
export function apiUrl(path: string): string {
  return `${BASE}${path}`;
}

/**
 * Subscribe to the SSE progress stream. Returns an unsubscribe function.
 * Events are real pipeline progress parsed from the orchestrator's own logs.
 */
export function streamProgress(
  jobId: string,
  onEvent: (ev: ProgressEvent) => void,
  onEnd: (status: "completed" | "failed") => void,
): () => void {
  const source = new EventSource(`${BASE}/analyze/${jobId}/stream`);
  const forward = (e: MessageEvent) => {
    try {
      onEvent(JSON.parse(e.data) as ProgressEvent);
    } catch {
      /* malformed frame — ignore */
    }
  };
  for (const kind of [
    "started", "parsed", "figure", "scored", "saved", "warning",
    "completed", "failed",
  ]) {
    source.addEventListener(kind, forward as EventListener);
  }
  source.addEventListener("end", ((e: MessageEvent) => {
    let status: "completed" | "failed" = "completed";
    try {
      status = JSON.parse(e.data).status;
    } catch {
      /* default to completed */
    }
    source.close();
    onEnd(status);
  }) as EventListener);
  source.onerror = () => {
    // Connection dropped (server restart, etc.). Close and report failure —
    // the UI offers a retry rather than silently hanging.
    if (source.readyState === EventSource.CLOSED) return;
    source.close();
    onEnd("failed");
  };
  return () => source.close();
}

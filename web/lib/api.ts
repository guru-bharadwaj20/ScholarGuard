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
  // splice
  spliced?: boolean;
  n_flagged_blocks?: number;
  cues?: {
    noise_inconsistency_blocks: number;
    jpeg_ghost_blocks: number;
    ela_blocks: number;
  };
  // ai_generation
  verdict?: "likely_real" | "suspicious" | "likely_ai_generated";
  freq_score?: number;
  noise_score?: number;
  /** p(AI) from the optional trained classifier; null when none is loaded. */
  classifier_score?: number | null;
  classifier_used?: boolean;
  // claim_consistency
  consistent?: boolean;
  mismatches?: string[];
  detector_context?: string[];
  observations?: Record<string, unknown> | null;
  claims?: Record<string, unknown> | null;
  reason?: string;
  error?: string;
}

export interface RiskBreakdownEntry {
  detector: string;
  status: string;
  max_points: number;
  points: number;
  /**
   * Whether the detector FIRED, recorded separately from the points it scored.
   * A lead-only detector (weight 0) still corroborates its neighbours, so
   * inferring this from points > 0 drops it out of the corroboration count.
   */
  fired: boolean;
  note: string;
}

export interface EvidenceContribution {
  detector: string;
  fired: boolean | null;
  log_likelihood_ratio: number;
}

export interface FigureRisk {
  score: number;
  category: "low" | "moderate" | "high" | "critical";
  breakdown: RiskBreakdownEntry[];
  /** How many INDEPENDENT detectors fired on this figure. */
  n_corroborating_signals: number;
  fraud_probability: number;
  evidence: {
    fraud_probability: number;
    log_odds: number;
    contributions: EvidenceContribution[];
  };
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
  /** The most detectors that agreed on any ONE figure. */
  max_corroboration?: number;
  fraud_probability?: number;
  worst_figure_score?: number;
  worst_figure_category?: string | null;
  note?: string;
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
  /** Present only once the pipeline has written the files. */
  downloads?: Partial<Record<"json" | "md", string>>;
  job?: { job_id: string; label: string; runtime_sec: number };
}

export interface BackendHealth {
  status: string;
  inflight: number;
  max_concurrent: number;
  max_inflight: number;
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

/** Backend liveness + current load, or null when it cannot be reached. */
export async function getHealth(): Promise<BackendHealth | null> {
  try {
    const res = await fetch(`${BASE}/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as BackendHealth;
  } catch {
    return null;
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
  if (!res.ok) throw await apiError(res, "The upload could not be started.");
  return res.json();
}

export async function startExample(id: string): Promise<{ job_id: string }> {
  const res = await fetch(`${BASE}/analyze/example/${id}`, { method: "POST" });
  if (!res.ok) throw await apiError(res, "The example could not be started.");
  return res.json();
}

export async function getResult(jobId: string): Promise<PipelineReport> {
  const res = await fetch(`${BASE}/analyze/${jobId}/result`, {
    cache: "no-store",
  });
  if (!res.ok) throw await apiError(res, "The result is not available.");
  return res.json();
}

/**
 * The server's own explanation, not a generic one. A 503 from /analyze carries
 * a capacity message worth reading, and the old blanket strings hid genuine
 * 500s behind "Result not available yet".
 */
async function apiError(res: Response, fallback: string): Promise<Error> {
  const detail = await res.json().catch(() => null);
  const message =
    typeof detail?.detail === "string" ? detail.detail : fallback;
  const error = new Error(message) as Error & { status?: number };
  error.status = res.status;
  return error;
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

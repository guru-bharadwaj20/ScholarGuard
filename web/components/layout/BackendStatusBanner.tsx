"use client";

import * as React from "react";
import { PlugZap, ServerCog } from "lucide-react";
import { getHealth, type BackendHealth } from "@/lib/api";

/**
 * Whether the pipeline backend is reachable, and how loaded it is.
 *
 * Without this, a backend that is down or already at capacity looked identical
 * to one that is idle right up until the upload failed — and analyses take
 * minutes, so finding out late is expensive. The server caps concurrent runs
 * and refuses beyond a queue depth; this reads /health so the page can say so
 * first.
 *
 * Silent when everything is fine and idle: a banner that is always on stops
 * being read.
 */
export function BackendStatusBanner() {
  const [health, setHealth] = React.useState<BackendHealth | null | undefined>(
    undefined,
  );

  React.useEffect(() => {
    let alive = true;
    const poll = async () => {
      const next = await getHealth();
      if (alive) setHealth(next);
    };
    poll();
    const id = setInterval(poll, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (health === undefined) return null; // first check still in flight

  if (health === null) {
    return (
      <div
        role="status"
        className="mb-6 flex items-start gap-3 rounded-xl border border-caution/40 bg-caution/5 px-4 py-3"
      >
        <PlugZap size={16} className="mt-0.5 shrink-0 text-caution" />
        <div>
          <p className="font-body text-sm text-slate-200">
            The analysis backend is not reachable.
          </p>
          <p className="type-meta mt-1 text-xs">
            Start it from the repo root with{" "}
            <code className="font-mono text-slate-300">
              uvicorn server.main:app --port 8000
            </code>
            . Nothing can be analyzed until it is running.
          </p>
        </div>
      </div>
    );
  }

  const busy = health.inflight >= health.max_concurrent;
  const full = health.inflight >= health.max_inflight;
  if (!busy) return null;

  return (
    <div
      role="status"
      className="mb-6 flex items-start gap-3 rounded-xl border border-ink-line bg-slate-900/40 px-4 py-3"
    >
      <ServerCog size={16} className="mt-0.5 shrink-0 text-accent" />
      <div>
        <p className="font-body text-sm text-slate-200">
          {full
            ? "The backend is at capacity."
            : `All ${health.max_concurrent} analysis slots are busy.`}
        </p>
        <p className="type-meta mt-1 text-xs">
          {health.inflight} of {health.max_inflight} queued or running. Each
          analysis is minutes of CPU work, so a new one{" "}
          {full ? "will be refused" : "will wait its turn"} — the machine runs
          them a few at a time rather than all at once.
        </p>
      </div>
    </div>
  );
}

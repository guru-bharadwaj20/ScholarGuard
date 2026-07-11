"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { FileSearch, FlaskConical, Info } from "lucide-react";
import { getExamples, type ExampleMeta } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { GlassCard, CardTitle } from "@/components/ui/card";

/**
 * Bundled real example papers from the Stage 7 evaluation set. The clean
 * example intentionally scores moderately because of copy-move's measured
 * over-triggering — its card says so up front (honest by example).
 */
export function ExamplePaperPicker({
  onStart,
  disabled,
}: {
  onStart: (exampleId: string) => Promise<void>;
  disabled?: boolean;
}) {
  const [examples, setExamples] = React.useState<ExampleMeta[] | null>(null);
  const [failed, setFailed] = React.useState(false);
  const [starting, setStarting] = React.useState<string | null>(null);

  React.useEffect(() => {
    getExamples()
      .then(setExamples)
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <p className="type-meta">
        Example papers unavailable — is the analysis backend running on :8000?
      </p>
    );
  }

  return (
    <div className="grid gap-5 md:grid-cols-2">
      {(examples ?? []).map((ex, i) => (
        <motion.div
          key={ex.id}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
        >
          <GlassCard className="flex h-full flex-col">
            <div className="flex items-center gap-2.5">
              {ex.kind === "fraud" ? (
                <FileSearch size={18} className="text-elevated" />
              ) : (
                <FlaskConical size={18} className="text-reliable" />
              )}
              <CardTitle>{ex.title}</CardTitle>
            </div>
            <p className="type-body mt-3 flex-1 text-sm">{ex.description}</p>

            {ex.honesty_note && (
              <p className="type-meta mt-4 flex gap-2 rounded-lg border border-caution/30 bg-caution/5 p-3 text-xs leading-relaxed">
                <Info size={14} className="mt-0.5 shrink-0 text-caution" />
                {ex.honesty_note}
              </p>
            )}

            <div className="mt-5 flex items-center justify-between gap-3">
              <span className="type-mono-label">{ex.expected_runtime}</span>
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled || !ex.available || starting !== null}
                onClick={async () => {
                  setStarting(ex.id);
                  try {
                    await onStart(ex.id);
                  } finally {
                    setStarting(null);
                  }
                }}
              >
                {starting === ex.id ? "Starting…" : "Run this example"}
              </Button>
            </div>
          </GlassCard>
        </motion.div>
      ))}
      {examples === null && (
        <p className="type-meta col-span-full">Loading examples…</p>
      )}
    </div>
  );
}

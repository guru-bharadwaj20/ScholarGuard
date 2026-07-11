"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { FileUp, FileWarning, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type DropState = "idle" | "dragging" | "uploading" | "error";

export function UploadDropzone({
  onFile,
  disabled,
}: {
  onFile: (file: File) => Promise<void>;
  disabled?: boolean;
}) {
  const [state, setState] = React.useState<DropState>("idle");
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleFile = async (file: File | undefined) => {
    if (!file || disabled) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("That doesn't look like a PDF — please choose a .pdf file.");
      setState("error");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError("That file is larger than 50 MB — please choose a smaller PDF.");
      setState("error");
      return;
    }
    setState("uploading");
    setError(null);
    try {
      await onFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong starting the analysis.");
      setState("error");
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "glass relative flex min-h-[220px] cursor-pointer flex-col items-center justify-center gap-4 p-8 text-center transition-colors",
        state === "dragging" && "border-accent/60 bg-accent/5",
        state === "error" && "border-caution/50",
        disabled && "pointer-events-none opacity-60",
      )}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        if (state !== "uploading") setState("dragging");
      }}
      onDragLeave={() => state === "dragging" && setState("idle")}
      onDrop={(e) => {
        e.preventDefault();
        setState("idle");
        handleFile(e.dataTransfer.files?.[0]);
      }}
      role="button"
      aria-label="Upload a PDF for analysis"
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0] ?? undefined)}
      />

      {state === "uploading" ? (
        <>
          <Loader2 size={30} className="animate-spin text-accent" />
          <p className="type-body">Uploading and starting the pipeline…</p>
        </>
      ) : state === "error" ? (
        <>
          <FileWarning size={30} className="text-caution" />
          <p className="type-body max-w-sm">{error}</p>
          <p className="type-meta">Click or drop another file to try again.</p>
        </>
      ) : (
        <>
          <FileUp
            size={30}
            className={cn("text-slate-400", state === "dragging" && "text-accent")}
          />
          <p className="type-body">
            {state === "dragging"
              ? "Drop it to start the analysis"
              : "Drag a paper PDF here, or click to browse"}
          </p>
          <p className="type-mono-label">PDF · up to 50 MB · analyzed locally on your machine</p>
        </>
      )}
    </motion.div>
  );
}

"use client";

import * as React from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { apiUrl } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Figure thumbnail with a toggle that overlays the copy-move detection
 * regions. The overlay image is the EXISTING Stage 2 visualization output
 * (drawn by the pipeline's own code, served by the bridge) — nothing is
 * regenerated or re-drawn client-side.
 */
export function ImageOverlayToggle({
  imageUrl,
  overlayUrl,
  alt,
}: {
  imageUrl: string;
  overlayUrl: string | null;
  alt: string;
}) {
  const [showOverlay, setShowOverlay] = React.useState(false);
  const [overlayLoading, setOverlayLoading] = React.useState(false);
  const [overlayFailed, setOverlayFailed] = React.useState(false);

  const src =
    showOverlay && overlayUrl && !overlayFailed
      ? apiUrl(overlayUrl)
      : apiUrl(imageUrl);

  return (
    <div className="relative overflow-hidden rounded-xl border border-ink-line bg-black/30">
      {/* eslint-disable-next-line @next/next/no-img-element -- API-served dynamic image */}
      <img
        src={src}
        alt={alt}
        className="max-h-72 w-full object-contain"
        onLoad={() => setOverlayLoading(false)}
        onError={() => {
          if (showOverlay) {
            setOverlayFailed(true);
            setOverlayLoading(false);
            setShowOverlay(false);
          }
        }}
      />
      {overlayUrl && (
        <button
          onClick={() => {
            if (!showOverlay) setOverlayLoading(true);
            setShowOverlay((v) => !v);
          }}
          className={cn(
            "absolute right-2 top-2 inline-flex items-center gap-1.5 rounded-lg border border-ink-line bg-ink/80 px-2.5 py-1.5 font-mono text-[11px] text-slate-200 backdrop-blur-md transition-colors hover:border-accent/50",
            showOverlay && "border-accent/60 text-accent",
          )}
        >
          {overlayLoading ? (
            <Loader2 size={12} className="animate-spin" />
          ) : showOverlay ? (
            <EyeOff size={12} />
          ) : (
            <Eye size={12} />
          )}
          {showOverlay ? "hide detected regions" : "show detected regions"}
        </button>
      )}
      {overlayFailed && (
        <p className="absolute bottom-2 left-2 rounded bg-ink/80 px-2 py-1 font-mono text-[10px] text-caution">
          overlay unavailable
        </p>
      )}
    </div>
  );
}

import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  MinusCircle,
} from "lucide-react";
import { DETECTORS, type DetectorId, type ReliabilityTier } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * The always-visible reliability pill shown NEXT TO a detector's name,
 * everywhere a detector is named. Never a tooltip — the measured number is
 * part of the result, not a footnote. Strings/numbers come from
 * lib/constants.ts only.
 */

const TIER_STYLES: Record<ReliabilityTier, { chip: string; icon: React.ReactNode }> = {
  reliable: {
    chip: "border-reliable/40 bg-reliable/10 text-reliable",
    icon: <CheckCircle2 size={12} />,
  },
  caution: {
    chip: "border-caution/40 bg-caution/10 text-caution",
    icon: <AlertTriangle size={12} />,
  },
  unvalidated: {
    chip: "border-neutralsev/40 bg-neutralsev/10 text-neutralsev",
    icon: <CircleDashed size={12} />,
  },
  // Measured, precise when it fires, but so insensitive that silence from it
  // carries almost no information. Distinct from "unvalidated", which means
  // never measured at all.
  inert: {
    chip: "border-neutralsev/40 bg-neutralsev/10 text-neutralsev",
    icon: <MinusCircle size={12} />,
  },
};

export function DetectorReliabilityBadge({
  detector,
  className,
}: {
  detector: DetectorId;
  className?: string;
}) {
  const spec = DETECTORS[detector];
  const style = TIER_STYLES[spec.tier];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
        "font-mono text-[11px] leading-none tracking-tight",
        style.chip,
        className,
      )}
    >
      {style.icon}
      {spec.badgeLabel}
    </span>
  );
}

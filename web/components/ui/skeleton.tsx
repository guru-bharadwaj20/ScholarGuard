import { cn } from "@/lib/utils";

/** Shimmer placeholder used while pipeline results stream in. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg bg-slate-800/60",
        "after:absolute after:inset-0 after:-translate-x-full",
        "after:bg-gradient-to-r after:from-transparent after:via-white/5 after:to-transparent",
        "after:animate-[shimmer_1.8s_infinite]",
        className,
      )}
      style={{
        // keyframes injected inline so no tailwind config addition is needed
        ["--tw-shimmer" as string]: "1",
      }}
    >
      <style>{`@keyframes shimmer { 100% { transform: translateX(100%); } }`}</style>
    </div>
  );
}

"use client";

import * as React from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "framer-motion";

/**
 * A slow-drifting field of ABSTRACT paper shapes — synthetic placeholders
 * only (rounded rectangles + faint line strokes suggesting text). No real
 * paper content, figures, or text ever appears here.
 *
 * Depth trick: papers with higher `depth` respond more to mouse parallax and
 * drift slightly faster, which reads as 3D without any WebGL cost.
 * prefers-reduced-motion freezes both drift and parallax entirely.
 */

interface PaperSpec {
  left: string; // CSS position
  top: string;
  width: number;
  height: number;
  rotate: number;
  depth: number; // 0 (far) .. 1 (near)
  duration: number; // drift loop seconds
  delay: number;
}

const PAPERS: PaperSpec[] = [
  { left: "4%", top: "12%", width: 120, height: 156, rotate: -9, depth: 0.9, duration: 26, delay: 0 },
  { left: "16%", top: "64%", width: 88, height: 116, rotate: 7, depth: 0.5, duration: 34, delay: 2 },
  { left: "31%", top: "24%", width: 72, height: 96, rotate: -4, depth: 0.3, duration: 40, delay: 5 },
  { left: "52%", top: "70%", width: 108, height: 140, rotate: 12, depth: 0.7, duration: 30, delay: 1 },
  { left: "66%", top: "16%", width: 84, height: 110, rotate: -13, depth: 0.45, duration: 36, delay: 4 },
  { left: "80%", top: "52%", width: 128, height: 168, rotate: 6, depth: 1.0, duration: 24, delay: 3 },
  { left: "90%", top: "8%", width: 64, height: 84, rotate: 3, depth: 0.25, duration: 44, delay: 6 },
  { left: "42%", top: "44%", width: 60, height: 80, rotate: -6, depth: 0.2, duration: 48, delay: 7 },
];

export function FloatingPapersBackground() {
  const reduce = useReducedMotion();
  const mx = useMotionValue(0); // -1 .. 1 across the viewport
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 40, damping: 20 });
  const sy = useSpring(my, { stiffness: 40, damping: 20 });

  React.useEffect(() => {
    if (reduce) return;
    const onMove = (e: MouseEvent) => {
      mx.set((e.clientX / window.innerWidth) * 2 - 1);
      my.set((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [reduce, mx, my]);

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {PAPERS.map((p, i) => (
        <Paper key={i} spec={p} sx={sx} sy={sy} frozen={!!reduce} />
      ))}
    </div>
  );
}

function Paper({
  spec,
  sx,
  sy,
  frozen,
}: {
  spec: PaperSpec;
  sx: ReturnType<typeof useSpring>;
  sy: ReturnType<typeof useSpring>;
  frozen: boolean;
}) {
  // Parallax offset scaled by depth — near papers move more.
  const px = useTransform(sx, (v) => v * 18 * spec.depth);
  const py = useTransform(sy, (v) => v * 12 * spec.depth);

  const opacity = 0.03 + spec.depth * 0.05; // 3%–8%

  return (
    <motion.div
      style={{ left: spec.left, top: spec.top, x: frozen ? 0 : px, y: frozen ? 0 : py }}
      className="absolute"
    >
      <motion.div
        animate={
          frozen
            ? undefined
            : {
                y: [0, -14 - spec.depth * 10, 0],
                x: [0, 8 * spec.depth, 0],
                rotate: [spec.rotate, spec.rotate + 2.5, spec.rotate],
              }
        }
        transition={
          frozen
            ? undefined
            : {
                duration: spec.duration,
                delay: spec.delay,
                repeat: Infinity,
                ease: "easeInOut",
              }
        }
        style={{ width: spec.width, height: spec.height, rotate: spec.rotate, opacity }}
        className="rounded-md border border-white/40 bg-white/10 p-3"
      >
        {/* Faint synthetic "text" lines — pure decoration, no real content. */}
        {Array.from({ length: Math.floor(spec.height / 18) }).map((_, li) => (
          <div
            key={li}
            className="mb-2 h-[2px] rounded bg-white/50"
            style={{ width: `${li % 4 === 3 ? 45 : 70 + ((li * 13) % 25)}%` }}
          />
        ))}
      </motion.div>
    </motion.div>
  );
}

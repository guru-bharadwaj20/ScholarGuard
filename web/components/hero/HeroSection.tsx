"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Microscope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { COMBINED, DETECTORS } from "@/lib/constants";

// Lazy-load the WebGL scene: never blocks first paint; static poster shown
// until it mounts (and permanently for reduced-motion users).
const DataNetworkCanvas = dynamic(() => import("./DataNetworkCanvas"), {
  ssr: false,
  loading: () => <CanvasPoster />,
});

function CanvasPoster() {
  return (
    <div
      aria-hidden
      className="absolute inset-0 rounded-card"
      style={{
        background:
          "radial-gradient(circle at 60% 40%, rgba(139,147,248,0.16), transparent 55%), radial-gradient(circle at 40% 70%, rgba(139,147,248,0.08), transparent 50%)",
      }}
    />
  );
}

export function HeroSection() {
  const reduce = useReducedMotion();

  return (
    <section className="relative grid min-h-[78vh] items-center gap-10 py-14 lg:grid-cols-[1.1fr_0.9fr]">
      {/* Text column */}
      <div className="relative z-10">
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="type-mono-label mb-5 inline-flex items-center gap-2 rounded-full border border-ink-line bg-slate-900/40 px-3 py-1.5 backdrop-blur-md"
        >
          <Microscope size={13} className="text-accent" />
          figure-integrity screening · limitations measured &amp; disclosed
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.08 }}
          className="font-display text-6xl font-bold leading-[0.95] tracking-tighter sm:text-7xl lg:text-8xl"
        >
          <span className="bg-gradient-to-br from-slate-50 via-slate-200 to-accent bg-clip-text text-transparent drop-shadow-[0_0_30px_rgba(139,147,248,0.25)]">
            Scholar
          </span>
          <span className="bg-gradient-to-br from-accent-soft to-accent-dim bg-clip-text text-transparent drop-shadow-[0_0_30px_rgba(139,147,248,0.35)]">
            Guard
          </span>
        </motion.h1>

        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.16 }}
          className="type-section mt-5 text-slate-300"
        >
          See what&apos;s worth <span className="text-accent">a second look.</span>
        </motion.h2>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.26 }}
          className="type-body mt-6 max-w-xl"
        >
          ScholarGuard screens the figures of a scientific paper for
          duplication, reuse, and generation artifacts — then tells you
          exactly how much to trust each signal. It is a research prototype,
          evaluated against {COMBINED.nFraud + COMBINED.nClean} real papers,
          with every limitation measured and printed next to the result.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.34 }}
          className="mt-9 flex flex-wrap items-center gap-4"
        >
          <Link href="/analyze">
            <Button size="lg">
              Analyze a paper <ArrowRight size={17} />
            </Button>
          </Link>
          <Link href="/methodology">
            <Button variant="ghost" size="lg">
              How honest is it? Read the evaluation
            </Button>
          </Link>
        </motion.div>

        {/* Honest at-a-glance numbers — sourced from constants, like everywhere */}
        <motion.dl
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-12 grid max-w-xl grid-cols-3 gap-4"
        >
          <HeroStat
            value={`${COMBINED.recallPercent}%`}
            label={`recall on ${COMBINED.nFraud} real fraud papers`}
          />
          <HeroStat
            value={`${COMBINED.bestAccuracyPercent}%`}
            label="accuracy ceiling vs. clean papers"
          />
          <HeroStat
            value={`${DETECTORS.ai_generation.fprPercent}%`}
            label="best detector's false-alarm rate"
          />
        </motion.dl>
      </div>

      {/* 3D column */}
      <div className="relative h-[340px] lg:h-[480px]">
        {reduce ? <CanvasPoster /> : <DataNetworkCanvas />}
        <p className="type-mono-label absolute bottom-2 right-2 opacity-70">
          figures &amp; their similarity graph
        </p>
      </div>
    </section>
  );
}

function HeroStat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border border-ink-line bg-slate-900/30 p-4 backdrop-blur-md">
      <dt className="font-mono text-2xl text-slate-100">{value}</dt>
      <dd className="type-meta mt-1 text-xs leading-snug">{label}</dd>
    </div>
  );
}

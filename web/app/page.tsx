import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { HeroSection } from "@/components/hero/HeroSection";
import { DetectorReliabilityBadge } from "@/components/analysis/DetectorReliabilityBadge";
import { GlassCard, CardTitle } from "@/components/ui/card";
import {
  DETECTORS,
  DETECTOR_ORDER,
  IN_SAMPLE_CAVEAT,
} from "@/lib/constants";

export default function HomePage() {
  return (
    <>
      <HeroSection />

      {/* What it measures — every detector shown WITH its reliability badge */}
      <section className="py-16">
        <h2 className="type-section text-slate-100">
          Four signals. Four very different levels of trust.
        </h2>
        <p className="type-body mt-3 max-w-2xl">
          Every detector below was measured against real published figures.
          The badges are permanent — wherever a detector&apos;s name appears in
          a report, its measured reliability appears beside it.
        </p>

        <div className="mt-10 grid gap-5 md:grid-cols-2">
          {DETECTOR_ORDER.map((id) => {
            const d = DETECTORS[id];
            return (
              <GlassCard key={id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <CardTitle>{d.name}</CardTitle>
                  <DetectorReliabilityBadge detector={id} />
                </div>
                <p className="type-body mt-4 text-sm">{d.plainExplanation}</p>
                {d.fprCi && (
                  <p className="type-mono-label mt-4">
                    measured on 83 clean real figures · {d.fprCi}
                  </p>
                )}
              </GlassCard>
            );
          })}
        </div>

        <p className="type-meta mt-8 max-w-3xl border-l-2 border-caution/50 pl-4">
          {IN_SAMPLE_CAVEAT}
        </p>

        <div className="mt-12">
          <Link
            href="/methodology"
            className="inline-flex items-center gap-2 font-body text-sm text-accent hover:text-accent-soft"
          >
            Read the full Stage 1–7 evaluation story
            <ArrowRight size={15} />
          </Link>
        </div>
      </section>
    </>
  );
}

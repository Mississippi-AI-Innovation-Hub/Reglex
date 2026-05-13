"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

const AXES = [
  {
    label: "Right state, right law",
    desc: "Cited the correct jurisdiction's rule",
    score: "8.8",
  },
  {
    label: "Honesty about guessing",
    desc: "Marked extrapolations as inferences",
    score: "8.0",
  },
  {
    label: "Tied claims to a source",
    desc: "Each statement linked to a citation",
    score: "6.6",
  },
  {
    label: "Substantively correct",
    desc: "Hardest measure. Multi-state synthesis",
    score: "5.6",
  },
];

export function Phase2ResultSlide({
  index,
  total,
}: {
  index: number;
  total: number;
}) {
  return (
    <SlideShell index={index} total={total} eyebrow="Phase 2 · Result">
      <SlideTransition className="flex-1 flex flex-col max-w-[82rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2.2rem,3.6vw,3.6rem)]">
            Held to a higher bar.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1rem,2vh,1.5rem)]" />
        </SlideItem>
        <SlideItem>
          <p className="mt-[clamp(1rem,2vh,1.4rem)] text-ink-muted font-light text-[clamp(1rem,1.2vw,1.2rem)] leading-[1.55] max-w-[62ch]">
            A 25-question multi-state evaluation, scored on four separate
            measures of trust. Not just &ldquo;did it sound right.&rdquo;
          </p>
        </SlideItem>

        <SlideItem className="mt-[clamp(1.6rem,3vh,2.4rem)]">
          <div className="grid grid-cols-1 md:grid-cols-[0.85fr_1.15fr] gap-[clamp(1.8rem,3vw,3rem)] items-start">
            <div>
              <div className="tabular font-sans font-semibold text-ink leading-none tracking-[-0.04em] text-[clamp(5.5rem,10vw,9rem)]">
                8.0
                <span className="text-g-blue text-[0.38em] align-top ml-1 font-medium">
                  /10
                </span>
              </div>
              <div className="mt-2 h-[3px] w-16 bg-g-blue rounded" />
              <p className="mt-4 text-ink font-medium text-[clamp(1rem,1.2vw,1.2rem)] leading-[1.4] max-w-[32ch]">
                For honesty about what it knows versus what it&rsquo;s guessing.
              </p>
              <p className="mt-2 text-ink-muted font-light text-[clamp(0.92rem,1.05vw,1.05rem)] leading-[1.55] max-w-[42ch]">
                When the system extrapolates beyond the source, it now flags
                it. Reviewers see a guess as a guess, not a fact.
              </p>
            </div>

            <div className="flex flex-col">
              {AXES.map((a, i) => (
                <div
                  key={i}
                  className="flex items-baseline justify-between gap-4 py-[clamp(0.6rem,1.2vh,0.9rem)] border-b border-line-soft last:border-b-0"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-sans font-medium text-ink text-[clamp(0.98rem,1.12vw,1.12rem)] tracking-[-0.01em]">
                      {a.label}
                    </div>
                    <div className="font-light text-ink-muted text-[clamp(0.82rem,0.92vw,0.92rem)] mt-0.5">
                      {a.desc}
                    </div>
                  </div>
                  <div className="tabular font-sans font-semibold text-ink text-[clamp(1.1rem,1.4vw,1.4rem)]">
                    {a.score}
                    <span className="text-ink-subtle font-normal text-[0.7em] ml-0.5">
                      / 10
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </SlideItem>

        <SlideItem className="mt-auto pt-[clamp(1.4rem,2.8vh,2rem)]">
          <p className="font-light text-ink-muted text-[clamp(0.9rem,1.05vw,1.05rem)] leading-[1.55] max-w-[90ch]">
            Strongest on questions about who has authority to act (9.2/10).
            Hardest on cross-state fee comparisons (5.2/10). A calibration gap,
            not an architecture gap.
          </p>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

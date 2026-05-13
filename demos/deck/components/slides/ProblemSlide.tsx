"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

const RISKS = [
  "Operational strain on policy staff",
  "Inconsistent compliance verification",
  "Reduced transparency for stakeholders",
  "A widening scalability gap",
];

export function ProblemSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total} eyebrow="The Problem">
      <SlideTransition className="flex-1 flex flex-col max-w-[80rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2.4rem,4.2vw,4.2rem)] max-w-[22ch]">
            A small team. An unstoppable volume of regulation.
          </h2>
        </SlideItem>

        <SlideItem>
          <div className="h-[3px] w-16 bg-g-red rounded mt-[clamp(1.2rem,2.4vh,1.8rem)]" />
        </SlideItem>

        <div className="mt-auto pt-[clamp(2rem,4vh,3rem)] grid grid-cols-1 md:grid-cols-[1.4fr_1fr] gap-[clamp(2rem,4vw,4rem)] items-start">
          <SlideItem>
            <p className="font-sans font-light italic text-ink text-[clamp(1.25rem,1.75vw,1.7rem)] leading-[1.5] max-w-[44ch]">
              &ldquo;A limited policy staff faces an ever-increasing volume of new regulations, creating a critical bottleneck that strains internal capacity and introduces the risk of inconsistency in verifying statutory compliance.&rdquo;
            </p>
          </SlideItem>
          <SlideItem>
            <ul className="flex flex-col gap-[clamp(0.9rem,1.6vh,1.2rem)]">
              {RISKS.map((r, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="mt-[0.6em] block w-1.5 h-1.5 rounded-full bg-g-red flex-shrink-0" />
                  <span className="font-sans text-ink text-[clamp(1rem,1.2vw,1.18rem)] leading-[1.45]">
                    {r}
                  </span>
                </li>
              ))}
            </ul>
          </SlideItem>
        </div>
      </SlideTransition>
    </SlideShell>
  );
}

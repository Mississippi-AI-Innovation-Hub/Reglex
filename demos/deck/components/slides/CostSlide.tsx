"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

const CARDS = [
  {
    label: "Phase 2 · Total Spend",
    unit: "$",
    amount: "751",
    prefix: "",
    desc: "All cloud costs from Feb 19 to Apr 19. Building, indexing, testing, and running the multi-state system. Verified directly from AWS billing.",
    accent: "blue" as const,
  },
  {
    label: "Steady-State · Per Month",
    unit: "$",
    amount: "375",
    prefix: "~",
    desc: "What it costs to keep Phase 2 running once it's built. Search index, AI model calls, document processing.",
    accent: "green" as const,
  },
  {
    label: "Per State Covered",
    unit: "$",
    amount: "54",
    prefix: "~",
    desc: "Monthly cost to add and maintain coverage of one additional state's regulatory corpus.",
    accent: "yellow" as const,
  },
];

const toneBar: Record<(typeof CARDS)[number]["accent"], string> = {
  blue: "bg-g-blue",
  green: "bg-g-green",
  yellow: "bg-g-yellow",
};

export function CostSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total} eyebrow="What It Costs">
      <SlideTransition className="flex-1 flex flex-col max-w-[82rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2.2rem,3.8vw,3.8rem)]">
            Two months. Seven states. Less than $800.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1.2rem,2.4vh,1.8rem)]" />
        </SlideItem>

        <SlideItem className="mt-[clamp(2rem,4vh,3rem)]">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-[clamp(1.4rem,2.2vw,2.4rem)]">
            {CARDS.map((c, i) => (
              <div key={i} className="flex flex-col gap-3 pt-4 relative">
                <div className={`absolute top-0 left-0 h-[3px] w-10 ${toneBar[c.accent]}`} />
                <div className="font-mono text-[10px] tracking-[0.22em] uppercase text-ink-muted">
                  {c.label}
                </div>
                <div className="tabular font-sans font-semibold text-ink leading-none tracking-[-0.035em] text-[clamp(3.5rem,6.5vw,6.5rem)]">
                  <span className="text-ink-muted font-light text-[0.55em] mr-1">
                    {c.prefix}
                    {c.unit}
                  </span>
                  {c.amount}
                </div>
                <p className="font-light text-ink-muted text-[clamp(0.92rem,1.05vw,1.05rem)] leading-[1.55] max-w-[38ch]">
                  {c.desc}
                </p>
              </div>
            ))}
          </div>
        </SlideItem>

        <SlideItem className="mt-auto pt-[clamp(1.4rem,2.8vh,2rem)]">
          <p className="font-light text-ink-muted text-[clamp(0.9rem,1.05vw,1.05rem)] leading-[1.55] max-w-[90ch]">
            Phase 2 added new capabilities, not new infrastructure. The same
            architecture from Phase 1 carries the entire seven-state system
            today.
          </p>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

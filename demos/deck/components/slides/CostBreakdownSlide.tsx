"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

const TODAY = [
  { lbl: "Search index", sub: "Always-on knowledge base", amt: "$215 / mo" },
  { lbl: "Development environment", sub: "Notebooks, dev tooling", amt: "~$70 / mo" },
  { lbl: "Document processing", sub: "Text extraction for 7 states", amt: "~$50 / mo" },
  { lbl: "AI model usage", sub: "Question answering + evaluation runs", amt: "~$30 / mo" },
  { lbl: "Other services", sub: "Storage, support, misc.", amt: "~$10 / mo" },
];

const TOMORROW = [
  { lbl: "Search index", sub: "Same as today", amt: "$220 / mo" },
  { lbl: "AI model calls", sub: "~10K staff questions per month", amt: "~$100 / mo" },
  { lbl: "Weekly source refresh", sub: "Re-crawl + re-index changed rules", amt: "~$50 / mo" },
  { lbl: "Other services", sub: "Public endpoint, request handler, storage", amt: "~$10 / mo" },
];

export function CostBreakdownSlide({
  index,
  total,
}: {
  index: number;
  total: number;
}) {
  return (
    <SlideShell index={index} total={total} eyebrow="Where It Goes">
      <SlideTransition className="flex-1 flex flex-col max-w-[84rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2rem,3.4vw,3.4rem)]">
            The same numbers, broken down.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1rem,2vh,1.5rem)]" />
        </SlideItem>
        <SlideItem>
          <p className="mt-[clamp(1rem,2vh,1.4rem)] text-ink-muted font-light text-[clamp(1rem,1.2vw,1.2rem)] leading-[1.55] max-w-[68ch]">
            What we actually spent during the pilot, and what the system would
            cost to operate at full production scale.
          </p>
        </SlideItem>

        <SlideItem className="mt-[clamp(1.6rem,3vh,2.4rem)]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-[clamp(1.6rem,2.5vw,3rem)]">
            <BreakdownColumn
              heading="Today · Pilot"
              tag="Verified · Feb 19 – Apr 19"
              tone="blue"
              lines={TODAY}
              total={{ lbl: "Average per month", amt: "~$375" }}
            />
            <BreakdownColumn
              heading="Tomorrow · Production"
              tag="Estimate"
              tone="green"
              lines={TOMORROW}
              total={{ lbl: "Estimated per month", amt: "~$380" }}
            />
          </div>
        </SlideItem>

        <SlideItem className="mt-auto pt-[clamp(1.4rem,2.8vh,2rem)]">
          <p className="font-light text-ink-muted text-[clamp(0.88rem,1vw,1rem)] leading-[1.5]">
            Pilot figures pulled directly from the AWS billing console.
            Production estimates assume routine staff usage and the weekly
            source-refresh loop.
          </p>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

function BreakdownColumn({
  heading,
  tag,
  tone,
  lines,
  total,
}: {
  heading: string;
  tag: string;
  tone: "blue" | "green";
  lines: { lbl: string; sub: string; amt: string }[];
  total: { lbl: string; amt: string };
}) {
  const toneText = tone === "blue" ? "text-g-blue" : "text-g-green";
  const toneBorder = tone === "blue" ? "border-g-blue/40" : "border-g-green/40";
  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between pb-3 border-b border-line">
        <h3 className="font-sans font-semibold text-ink text-[clamp(1.05rem,1.3vw,1.3rem)] tracking-[-0.015em]">
          {heading}
        </h3>
        <span className={`font-mono text-[10px] tracking-[0.18em] uppercase px-2 py-1 rounded border ${toneBorder} ${toneText} bg-surface`}>
          {tag}
        </span>
      </div>
      <div className="flex flex-col">
        {lines.map((l, i) => (
          <div
            key={i}
            className="flex items-baseline justify-between gap-4 py-[clamp(0.55rem,1.1vh,0.8rem)] border-b border-line-soft"
          >
            <div className="flex-1 min-w-0">
              <div className="font-sans text-ink text-[clamp(0.95rem,1.1vw,1.08rem)] tracking-[-0.01em]">
                {l.lbl}
              </div>
              <div className="font-light text-ink-muted text-[clamp(0.8rem,0.9vw,0.9rem)] mt-0.5">
                {l.sub}
              </div>
            </div>
            <div className="tabular font-mono text-ink text-[clamp(0.92rem,1.05vw,1.05rem)] whitespace-nowrap">
              {l.amt}
            </div>
          </div>
        ))}
        <div className="flex items-baseline justify-between gap-4 pt-[clamp(0.7rem,1.4vh,1rem)] mt-1">
          <div className="font-sans font-semibold text-ink text-[clamp(1rem,1.15vw,1.15rem)]">
            {total.lbl}
          </div>
          <div className={`tabular font-sans font-semibold ${toneText} text-[clamp(1.2rem,1.5vw,1.5rem)] whitespace-nowrap`}>
            {total.amt}
          </div>
        </div>
      </div>
    </div>
  );
}

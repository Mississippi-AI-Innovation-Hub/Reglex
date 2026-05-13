"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";
import { ArrowRight } from "lucide-react";

const STEPS = [
  {
    num: "Step 01",
    title: "Weekly Check-In",
    body: "Every Monday, the system wakes itself up and visits all 21 official regulator websites.",
  },
  {
    num: "Step 02",
    title: "Read & Compare",
    body: "Reads each rule and compares it word-for-word with what we saw last week.",
  },
  {
    num: "Step 03",
    title: "Spot the Change",
    body: "Identifies what's new, what was amended, and what was repealed since the last visit.",
  },
  {
    num: "Step 04",
    title: "Update the Library",
    body: "Re-indexes anything that changed and removes rules that no longer exist.",
  },
  {
    num: "Step 05",
    title: "Notify the Team",
    body: "Sends a weekly summary so a human can verify before anything reaches the public.",
  },
];

export function FreshnessSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total} eyebrow="How It Stays Current">
      <SlideTransition className="flex-1 flex flex-col max-w-[88rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2rem,3.6vw,3.4rem)] max-w-[32ch]">
            From a regulator&rsquo;s website to your answer, in five steps.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1rem,2vh,1.5rem)]" />
        </SlideItem>

        <SlideItem className="mt-[clamp(1.6rem,3.2vh,2.4rem)]">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-[clamp(1rem,1.6vw,1.6rem)]">
            {STEPS.map((s, i) => (
              <div key={i} className="relative flex flex-col gap-2 pt-3">
                <div className="absolute top-0 left-0 right-3 h-[2px] bg-line" />
                <div className="font-mono text-[10px] tracking-[0.22em] text-g-blue">
                  {s.num}
                </div>
                <h3 className="font-sans font-semibold text-ink text-[clamp(0.95rem,1.15vw,1.18rem)] tracking-[-0.012em] leading-[1.25]">
                  {s.title}
                </h3>
                <p className="font-light text-ink-muted text-[clamp(0.85rem,0.95vw,1rem)] leading-[1.5]">
                  {s.body}
                </p>
                {i < STEPS.length - 1 && (
                  <ArrowRight
                    className="hidden md:block absolute -right-2 top-3 text-ink-subtle/60 w-4 h-4"
                    strokeWidth={1.5}
                  />
                )}
              </div>
            ))}
          </div>
        </SlideItem>

        <SlideItem className="mt-auto pt-[clamp(1.6rem,3vh,2.4rem)]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-[clamp(1.2rem,2vw,2rem)]">
            <div className="border-l-2 border-g-green pl-4 py-2">
              <div className="font-mono text-[10px] tracking-[0.22em] uppercase text-g-green">
                Built today
              </div>
              <p className="mt-1 text-ink font-light text-[clamp(0.95rem,1.1vw,1.08rem)] leading-[1.5]">
                Steps 1 &amp; 2. The crawlers that read all 21 sources.
              </p>
            </div>
            <div className="border-l-2 border-g-yellow pl-4 py-2">
              <div className="font-mono text-[10px] tracking-[0.22em] uppercase text-g-yellow">
                Ready to activate
              </div>
              <p className="mt-1 text-ink font-light text-[clamp(0.95rem,1.1vw,1.08rem)] leading-[1.5]">
                Steps 3, 4, 5. Architecture complete; activates on production deployment.
              </p>
            </div>
          </div>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

const ROWS = [
  {
    phase: "Phase 1",
    tone: "text-g-blue",
    body: (
      <>
        <Token>Ask</Token> grounded Mississippi answer with statutory citation.
      </>
    ),
  },
  {
    phase: "Phase 2",
    tone: "text-g-green",
    body: (
      <>
        <Token>Ask</Token> multi-state research, cross-jurisdiction comparison,
        authority check. Every claim still cited.
      </>
    ),
  },
];

function Token({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-block font-mono text-[0.78em] tracking-[0.18em] uppercase px-2 py-1 mr-3 rounded border border-line bg-surface text-ink">
      {children}
    </span>
  );
}

export function FitsTogetherSlide({
  index,
  total,
}: {
  index: number;
  total: number;
}) {
  return (
    <SlideShell index={index} total={total} eyebrow="How It All Fits Together">
      <SlideTransition className="flex-1 flex flex-col justify-center max-w-[80rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2.6rem,4.4vw,4.4rem)]">
            One system. Two layers.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1.2rem,2.4vh,1.8rem)]" />
        </SlideItem>

        <SlideItem className="mt-[clamp(2rem,4vh,3rem)]">
          <div className="flex flex-col gap-[clamp(1rem,2vh,1.6rem)]">
            {ROWS.map((r) => (
              <div
                key={r.phase}
                className="grid grid-cols-[auto_1fr] items-start gap-6 border-t border-line pt-4"
              >
                <div
                  className={`font-mono text-[11px] tracking-[0.22em] uppercase ${r.tone} pt-2 min-w-[6rem]`}
                >
                  {r.phase}
                </div>
                <div className="font-sans text-ink text-[clamp(1.1rem,1.4vw,1.35rem)] leading-[1.55]">
                  {r.body}
                </div>
              </div>
            ))}
          </div>
        </SlideItem>

        <SlideItem>
          <p className="mt-[clamp(2rem,4vh,3rem)] font-light italic text-ink text-[clamp(1.05rem,1.3vw,1.3rem)]">
            Phase 1 made Mississippi&rsquo;s law searchable. Phase 2 made it
            comparable.
          </p>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

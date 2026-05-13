"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

export function ClosingSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total}>
      <SlideTransition className="flex-1 flex flex-col justify-center max-w-[68rem] mx-auto w-full">
        <SlideItem>
          <p className="font-sans font-light italic text-ink leading-[1.15] tracking-[-0.025em] text-[clamp(2.2rem,4.2vw,4rem)] max-w-[24ch]">
            &ldquo;Technology changes, but the duty of this office remains
            constant.&rdquo;
          </p>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1.2rem,2.4vh,1.8rem)]" />
        </SlideItem>
        <SlideItem>
          <p className="mt-[clamp(1rem,2vh,1.4rem)] font-mono text-[11px] tracking-[0.22em] uppercase text-ink-muted">
            Office of the Mississippi Secretary of State
          </p>
        </SlideItem>
        <SlideItem>
          <p className="mt-[clamp(2.4rem,4.8vh,3.6rem)] font-light text-ink-muted text-[clamp(1.1rem,1.35vw,1.35rem)] leading-[1.6] max-w-[58ch]">
            From a passive archive to an interactive research partner. Built in
            months, for less than a single staff salary, ready to extend.
          </p>
        </SlideItem>
        <SlideItem>
          <p className="mt-[clamp(1.8rem,3.6vh,2.6rem)] font-sans font-semibold italic text-g-blue text-[clamp(2rem,3.4vw,3.2rem)] tracking-[-0.025em]">
            Reglex
          </p>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

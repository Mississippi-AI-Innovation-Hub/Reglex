"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

export function BridgeSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total} eyebrow="Phase 1 → Phase 2">
      <SlideTransition className="flex-1 flex flex-col justify-center max-w-[72rem] mx-auto w-full">
        <SlideItem>
          <p className="font-sans font-semibold text-ink leading-[1.1] tracking-[-0.025em] text-[clamp(2.6rem,4.6vw,4.6rem)] max-w-[18ch]">
            Mississippi doesn&rsquo;t write policy{" "}
            <span className="text-g-blue">in a vacuum.</span>
          </p>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1.6rem,3.2vh,2.4rem)]" />
        </SlideItem>
        <SlideItem>
          <p className="mt-[clamp(1.6rem,3.2vh,2.4rem)] font-light text-ink-muted text-[clamp(1.15rem,1.4vw,1.4rem)] leading-[1.6] max-w-[64ch]">
            How do our fees compare to Tennessee&rsquo;s? Are our agencies
            acting within the authority the legislature granted them? When
            another state quietly amends a regulation, how would we even know?{" "}
            <span className="text-ink">
              Phase 2 was about answering those questions, without losing the
              citations.
            </span>
          </p>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

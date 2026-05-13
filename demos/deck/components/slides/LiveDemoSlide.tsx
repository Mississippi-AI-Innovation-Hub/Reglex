"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";
import { motion } from "framer-motion";

export function LiveDemoSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total}>
      <SlideTransition className="flex-1 flex flex-col items-center justify-center max-w-[60rem] mx-auto w-full text-center">
        <SlideItem>
          <div className="flex items-center justify-center gap-4">
            <motion.span
              aria-hidden
              className="block w-3 h-3 rounded-full bg-g-red"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
            />
            <span className="font-mono text-[14px] tracking-[0.3em] uppercase text-g-red">
              Live
            </span>
          </div>
        </SlideItem>
        <SlideItem>
          <h2 className="mt-6 font-sans font-semibold tracking-[-0.035em] text-ink leading-[0.95] text-[clamp(4rem,11vw,11rem)]">
            Demo.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1.6rem,3vh,2.4rem)] mx-auto" />
        </SlideItem>
        <SlideItem>
          <p className="mt-[clamp(1.4rem,3vh,2rem)] font-light text-ink-muted text-[clamp(1.05rem,1.3vw,1.3rem)] leading-[1.6] max-w-[44ch]">
            A brief walkthrough of the system in use. Ask, watch citations
            resolve, compare across states.
          </p>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

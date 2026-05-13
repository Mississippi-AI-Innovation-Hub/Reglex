"use client";

import Image from "next/image";
import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

const ORGS = [
  {
    file: "usm_logo.png",
    alt: "University of Southern Mississippi",
    sub: "University of Southern Mississippi",
  },
  {
    file: "sos_logo.png",
    alt: "Mississippi Secretary of State",
    sub: "Mississippi Secretary of State",
  },
  { file: "AWS_Logo.png", alt: "Amazon Web Services", sub: "Amazon Web Services" },
  { file: "main_logo.png", alt: "Mississippi AI Network", sub: "Mississippi AI Network" },
  {
    file: "its_logo.png",
    alt: "MS Dept. of Information Technology Services",
    sub: "MS Dept. of Information Technology Services",
  },
];

export function ThanksSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total} eyebrow="Special Thanks">
      <SlideTransition className="flex-1 flex flex-col max-w-[82rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2.4rem,4.2vw,4.2rem)]">
            None of this happens alone.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1.2rem,2.4vh,1.8rem)]" />
        </SlideItem>

        <SlideItem className="mt-auto pt-[clamp(2rem,4vh,3rem)]">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-[clamp(1rem,2vw,2rem)]">
            {ORGS.map((o) => (
              <div
                key={o.file}
                className="flex flex-col items-center justify-end gap-4 border-t border-line pt-6 pb-2"
              >
                <div className="relative w-full h-[clamp(54px,9vh,100px)]">
                  <Image
                    src={`/assets/${o.file}`}
                    alt={o.alt}
                    fill
                    sizes="16vw"
                    className="object-contain"
                  />
                </div>
                <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-ink-muted text-center leading-[1.5] min-h-[2.8em]">
                  {o.sub}
                </div>
              </div>
            ))}
          </div>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

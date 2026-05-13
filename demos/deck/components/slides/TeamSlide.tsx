"use client";

import Image from "next/image";
import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

const TEAM = [
  { num: "01", name: "Bibas Kandel", file: "bibas.png" },
  { num: "02", name: "Gunjan Sah", file: "Gunjan.png" },
  { num: "03", name: "Mandip Adhikari", file: "Mandip.png" },
  { num: "04", name: "Kapil Sharma", file: "Kapil.png" },
  { num: "05", name: "Saleep Shrestha", file: "Saleep.png" },
  { num: "06", name: "Aditya Sharma", file: "aditya.png" },
];

export function TeamSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total} eyebrow="The Team">
      <SlideTransition className="flex-1 flex flex-col max-w-[78rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2.4rem,4.2vw,4.2rem)]">
            Six engineers.<br />One charter.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1.2rem,2.4vh,1.8rem)]" />
        </SlideItem>

        <SlideItem className="mt-auto pt-[clamp(1.5rem,3vh,2.5rem)]">
          <div className="grid grid-cols-3 md:grid-cols-6 gap-[clamp(1rem,1.8vw,2rem)]">
            {TEAM.map((p) => (
              <div key={p.num} className="flex flex-col gap-3">
                <div className="relative aspect-square w-full overflow-hidden rounded-md bg-surface">
                  <Image
                    src={`/assets/${p.file}`}
                    alt={p.name}
                    fill
                    sizes="(max-width: 900px) 30vw, 13vw"
                    className="object-cover"
                  />
                </div>
                <div>
                  <div className="font-mono text-[10px] tracking-[0.22em] text-ink-subtle">
                    {p.num}
                  </div>
                  <div className="mt-1 font-sans font-medium text-ink text-[clamp(0.95rem,1.1vw,1.08rem)] tracking-[-0.01em]">
                    {p.name}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

type Props = {
  index: number;
  total: number;
  eyebrow?: string;
  title: React.ReactNode;
  subtitle?: string;
  speaker?: string;
  meta?: { left?: string; right?: string };
  accent?: "blue" | "red" | "yellow" | "green" | "google";
};

const accentClass: Record<NonNullable<Props["accent"]>, string> = {
  blue: "bg-g-blue",
  red: "bg-g-red",
  yellow: "bg-g-yellow",
  green: "bg-g-green",
  google: "g-rule",
};

export function TitleSlide({
  index,
  total,
  eyebrow,
  title,
  subtitle,
  speaker,
  meta,
  accent = "google",
}: Props) {
  return (
    <SlideShell index={index} total={total}>
      <SlideTransition className="flex-1 flex flex-col justify-center max-w-[68rem] mx-auto w-full">
        {eyebrow && (
          <SlideItem>
            <div className="font-mono text-[12px] tracking-[0.24em] uppercase text-ink-muted mb-[clamp(1.5rem,3vh,2.2rem)]">
              {eyebrow}
            </div>
          </SlideItem>
        )}

        <SlideItem>
          <h1 className="font-sans font-bold tracking-[-0.04em] text-ink leading-[0.95] text-[clamp(3.5rem,9vw,8rem)]">
            {title}
          </h1>
        </SlideItem>

        <SlideItem>
          <div
            className={`mt-[clamp(1.6rem,3.2vh,2.4rem)] ${accent === "google" ? "g-rule" : `${accentClass[accent]} h-[3px] w-16 rounded`}`}
          />
        </SlideItem>

        {subtitle && (
          <SlideItem>
            <p className="mt-[clamp(1.4rem,3vh,2rem)] text-ink-muted font-light text-[clamp(1.25rem,1.6vw,1.6rem)] leading-[1.45] max-w-[44ch]">
              {subtitle}
            </p>
          </SlideItem>
        )}

        {(speaker || meta) && (
          <SlideItem>
            <div className="mt-[clamp(2rem,4.5vh,3.5rem)] flex flex-wrap items-baseline gap-x-8 gap-y-2 font-mono text-[12px] tracking-[0.18em] uppercase text-ink-subtle">
              {speaker && <span className="text-ink">{speaker}</span>}
              {meta?.left && <span>{meta.left}</span>}
              {meta?.right && <span>{meta.right}</span>}
            </div>
          </SlideItem>
        )}
      </SlideTransition>
    </SlideShell>
  );
}

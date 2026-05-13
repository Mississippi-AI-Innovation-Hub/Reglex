"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

export type CapItem = {
  num: string;
  title: React.ReactNode;
  body: string;
  designed?: boolean;
};

type Props = {
  index: number;
  total: number;
  eyebrow: string;
  title: React.ReactNode;
  lede?: string;
  items: CapItem[];
  columns?: 2 | 3 | 4;
};

/**
 * Numbered capability grid (e.g. "What We Built" / "What's New").
 * Pure-typography variant of FeatureGridSlide — no icons.
 */
export function CapabilityGridSlide({
  index,
  total,
  eyebrow,
  title,
  lede,
  items,
  columns = 4,
}: Props) {
  const colClass =
    columns === 2
      ? "grid-cols-1 md:grid-cols-2"
      : columns === 3
        ? "grid-cols-1 md:grid-cols-3"
        : "grid-cols-2 lg:grid-cols-4";

  return (
    <SlideShell index={index} total={total} eyebrow={eyebrow}>
      <SlideTransition className="flex-1 flex flex-col max-w-[82rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2.2rem,3.8vw,3.8rem)] max-w-[26ch]">
            {title}
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1.2rem,2.4vh,1.8rem)]" />
        </SlideItem>
        {lede && (
          <SlideItem>
            <p className="mt-[clamp(1.2rem,2.4vh,1.6rem)] text-ink-muted font-light text-[clamp(1.05rem,1.3vw,1.3rem)] leading-[1.55] max-w-[68ch]">
              {lede}
            </p>
          </SlideItem>
        )}

        <SlideItem className="mt-auto pt-[clamp(2rem,4vh,3rem)]">
          <div className={`grid ${colClass} gap-x-[clamp(1.6rem,2.4vw,2.8rem)] gap-y-[clamp(1.8rem,3.6vh,2.6rem)]`}>
            {items.map((it, i) => (
              <div key={i} className="flex flex-col gap-2 border-t border-line pt-4">
                <div className="font-mono text-[10px] tracking-[0.22em] text-g-blue">
                  {it.num}
                </div>
                <h3 className="font-sans font-semibold text-ink text-[clamp(1.05rem,1.3vw,1.3rem)] tracking-[-0.015em] leading-[1.25] flex items-baseline gap-2 flex-wrap">
                  <span>{it.title}</span>
                  {it.designed && (
                    <span className="font-mono text-[9px] tracking-[0.22em] text-g-yellow">
                      DESIGNED
                    </span>
                  )}
                </h3>
                <p className="font-light text-ink-muted text-[clamp(0.92rem,1.05vw,1.05rem)] leading-[1.5]">
                  {it.body}
                </p>
              </div>
            ))}
          </div>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

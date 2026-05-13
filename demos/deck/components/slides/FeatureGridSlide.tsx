"use client";

import type { LucideIcon } from "lucide-react";
import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

export type FeatureItem = {
  icon: LucideIcon;
  title: string;
  body: string;
  accent?: "blue" | "red" | "yellow" | "green";
};

type Props = {
  index: number;
  total: number;
  eyebrow?: string;
  title: React.ReactNode;
  lede?: string;
  items: FeatureItem[];
  columns?: 2 | 3 | 4;
};

const iconColor: Record<NonNullable<FeatureItem["accent"]>, string> = {
  blue: "text-g-blue",
  red: "text-g-red",
  yellow: "text-g-yellow",
  green: "text-g-green",
};

export function FeatureGridSlide({
  index,
  total,
  eyebrow,
  title,
  lede,
  items,
  columns = 3,
}: Props) {
  const colClass =
    columns === 2
      ? "grid-cols-1 md:grid-cols-2"
      : columns === 4
        ? "grid-cols-1 md:grid-cols-2 lg:grid-cols-4"
        : "grid-cols-1 md:grid-cols-3";

  return (
    <SlideShell index={index} total={total} eyebrow={eyebrow}>
      <SlideTransition className="flex-1 flex flex-col max-w-[78rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2.4rem,4.2vw,4.2rem)] max-w-[24ch]">
            {title}
          </h2>
        </SlideItem>

        <SlideItem>
          <div className="g-rule mt-[clamp(1.2rem,2.4vh,1.8rem)]" />
        </SlideItem>

        {lede && (
          <SlideItem>
            <p className="mt-[clamp(1.2rem,2.4vh,1.6rem)] text-ink-muted font-light text-[clamp(1.05rem,1.3vw,1.3rem)] leading-[1.55] max-w-[64ch]">
              {lede}
            </p>
          </SlideItem>
        )}

        <SlideItem className={`mt-auto pt-[clamp(2rem,4vh,3rem)]`}>
          <div className={`grid ${colClass} gap-[clamp(1.5rem,2.5vw,3rem)]`}>
            {items.map((it, i) => {
              const Icon = it.icon;
              const color = iconColor[it.accent ?? "blue"];
              return (
                <div key={i} className="flex flex-col gap-[clamp(0.7rem,1.4vh,1rem)]">
                  <Icon className={`${color} w-[clamp(1.6rem,2vw,2rem)] h-[clamp(1.6rem,2vw,2rem)]`} strokeWidth={1.5} />
                  <h3 className="font-sans font-semibold text-ink text-[clamp(1.1rem,1.4vw,1.4rem)] tracking-[-0.015em] leading-[1.25]">
                    {it.title}
                  </h3>
                  <p className="font-light text-ink-muted text-[clamp(0.95rem,1.1vw,1.08rem)] leading-[1.55]">
                    {it.body}
                  </p>
                </div>
              );
            })}
          </div>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

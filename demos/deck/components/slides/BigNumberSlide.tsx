"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";

type Props = {
  index: number;
  total: number;
  eyebrow?: string;
  number: React.ReactNode;
  unit?: React.ReactNode;
  label: React.ReactNode;
  sub?: React.ReactNode;
  accent?: "blue" | "red" | "yellow" | "green";
};

const accentText: Record<NonNullable<Props["accent"]>, string> = {
  blue: "text-g-blue",
  red: "text-g-red",
  yellow: "text-g-yellow",
  green: "text-g-green",
};

export function BigNumberSlide({
  index,
  total,
  eyebrow,
  number,
  unit,
  label,
  sub,
  accent = "blue",
}: Props) {
  return (
    <SlideShell index={index} total={total} eyebrow={eyebrow}>
      <SlideTransition className="flex-1 flex flex-col items-center justify-center text-center max-w-[58rem] mx-auto w-full">
        <SlideItem>
          <div className="tabular font-sans font-semibold tracking-[-0.06em] text-ink leading-none text-[clamp(8rem,22vw,20rem)]">
            {number}
            {unit && (
              <span
                className={`${accentText[accent]} text-[0.42em] align-top ml-1 font-medium`}
              >
                {unit}
              </span>
            )}
          </div>
        </SlideItem>

        <SlideItem>
          <div
            className={`mt-[clamp(1rem,2.5vh,1.8rem)] h-[3px] w-16 ${accent === "blue" ? "bg-g-blue" : accent === "red" ? "bg-g-red" : accent === "yellow" ? "bg-g-yellow" : "bg-g-green"} rounded mx-auto`}
          />
        </SlideItem>

        <SlideItem>
          <p className="mt-[clamp(1.4rem,3vh,2rem)] text-ink font-medium text-[clamp(1.25rem,1.7vw,1.7rem)] leading-[1.4] max-w-[40ch]">
            {label}
          </p>
        </SlideItem>

        {sub && (
          <SlideItem>
            <p className="mt-[clamp(0.8rem,1.6vh,1.2rem)] text-ink-muted font-light text-[clamp(1rem,1.2vw,1.18rem)] leading-[1.55] max-w-[52ch]">
              {sub}
            </p>
          </SlideItem>
        )}
      </SlideTransition>
    </SlideShell>
  );
}

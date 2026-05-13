"use client";

import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  index: number;
  total: number;
  eyebrow?: string;
  bare?: boolean;
  className?: string;
};

/**
 * SlideShell — viewport-locked frame for every slide.
 * Provides consistent margins, top brand bar, and slide counter.
 * `bare` renders without padding/chrome (used by full-bleed screenshot slides).
 */
export function SlideShell({
  children,
  index,
  total,
  eyebrow,
  bare = false,
  className = "",
}: Props) {
  if (bare) {
    return (
      <section className={`slide-pane h-screen w-screen relative ${className}`}>
        {children}
        <SlideCounter index={index} total={total} variant="floating" />
      </section>
    );
  }

  return (
    <section
      className={`slide-pane h-screen w-screen relative flex flex-col bg-canvas ${className}`}
    >
      <header className="flex items-center justify-between px-[clamp(2rem,5vw,4.5rem)] pt-[clamp(1.4rem,3vh,2rem)]">
        <BrandMark />
        {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : <span />}
      </header>

      <div className="flex-1 px-[clamp(2rem,5vw,4.5rem)] pt-[clamp(1.5rem,3vh,2.5rem)] pb-[clamp(2rem,4vh,3.5rem)] flex flex-col min-h-0">
        {children}
      </div>

      <SlideCounter index={index} total={total} />
    </section>
  );
}

export function BrandMark() {
  return (
    <div className="font-mono text-[11px] tracking-[0.22em] uppercase text-ink-subtle">
      Reglex <span className="mx-2 text-ink-subtle/60">·</span> SoS Demo
    </div>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="font-mono text-[11px] tracking-[0.22em] uppercase text-g-blue">
      {children}
    </div>
  );
}

function SlideCounter({
  index,
  total,
  variant = "anchored",
}: {
  index: number;
  total: number;
  variant?: "anchored" | "floating";
}) {
  const text = `${String(index + 1).padStart(2, "0")} / ${String(total).padStart(2, "0")}`;
  if (variant === "floating") {
    return (
      <div className="absolute bottom-[clamp(1.4rem,3vh,2rem)] right-[clamp(2rem,5vw,4.5rem)] font-mono text-[11px] tracking-[0.22em] text-ink-subtle">
        {text}
      </div>
    );
  }
  return (
    <div className="px-[clamp(2rem,5vw,4.5rem)] pb-[clamp(1.4rem,3vh,2rem)] flex items-center justify-end">
      <div className="font-mono text-[11px] tracking-[0.22em] text-ink-subtle">
        {text}
      </div>
    </div>
  );
}

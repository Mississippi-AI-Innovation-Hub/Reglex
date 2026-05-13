"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Props = {
  children: React.ReactNode[];
};

/**
 * Deck container — handles arrow / wheel / touch / dot navigation
 * over a vertical scroll-snap surface.
 */
export function DeckShell({ children }: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [current, setCurrent] = useState(0);
  const total = children.length;
  const lockRef = useRef(false);

  const goTo = useCallback(
    (i: number) => {
      const el = scrollerRef.current;
      if (!el) return;
      const clamped = Math.max(0, Math.min(total - 1, i));
      setCurrent(clamped);
      el.scrollTo({ top: clamped * el.clientHeight, behavior: "smooth" });
    },
    [total],
  );

  const next = useCallback(() => goTo(current + 1), [current, goTo]);
  const prev = useCallback(() => goTo(current - 1), [current, goTo]);

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = e.key;
      if (k === "ArrowDown" || k === "ArrowRight" || k === "PageDown" || k === " ") {
        e.preventDefault();
        next();
      } else if (k === "ArrowUp" || k === "ArrowLeft" || k === "PageUp") {
        e.preventDefault();
        prev();
      } else if (k === "Home") {
        e.preventDefault();
        goTo(0);
      } else if (k === "End") {
        e.preventDefault();
        goTo(total - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, goTo, total]);

  // Wheel navigation (rate-limited)
  useEffect(() => {
    const onWheel = (e: WheelEvent) => {
      if (lockRef.current) return;
      if (Math.abs(e.deltaY) < 30) return;
      lockRef.current = true;
      if (e.deltaY > 0) next();
      else prev();
      window.setTimeout(() => {
        lockRef.current = false;
      }, 700);
    };
    window.addEventListener("wheel", onWheel, { passive: true });
    return () => window.removeEventListener("wheel", onWheel);
  }, [next, prev]);

  // Touch swipe
  useEffect(() => {
    let startY = 0;
    let startX = 0;
    const onStart = (e: TouchEvent) => {
      startY = e.touches[0].clientY;
      startX = e.touches[0].clientX;
    };
    const onEnd = (e: TouchEvent) => {
      const dy = e.changedTouches[0].clientY - startY;
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dy) > 60 && Math.abs(dy) > Math.abs(dx)) {
        if (dy < 0) next();
        else prev();
      }
    };
    window.addEventListener("touchstart", onStart, { passive: true });
    window.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      window.removeEventListener("touchstart", onStart);
      window.removeEventListener("touchend", onEnd);
    };
  }, [next, prev]);

  // Sync `current` when scroll snaps
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const i = Math.round(el.scrollTop / el.clientHeight);
        if (i !== current) setCurrent(i);
      });
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener("scroll", onScroll);
    };
  }, [current]);

  return (
    <main className="h-screen w-screen relative overflow-hidden bg-canvas">
      <div
        ref={scrollerRef}
        className="deck-scroll h-screen w-screen overflow-y-auto"
      >
        {children}
      </div>

      {/* Progress dots */}
      <nav
        aria-label="Slide navigation"
        className="fixed right-4 top-1/2 -translate-y-1/2 z-20 flex flex-col gap-2"
      >
        {Array.from({ length: total }).map((_, i) => (
          <button
            key={i}
            type="button"
            aria-label={`Go to slide ${i + 1}`}
            aria-current={i === current ? "true" : undefined}
            onClick={() => goTo(i)}
            className={`block transition-all duration-300 rounded-full cursor-pointer ${
              i === current
                ? "w-1.5 h-6 bg-g-blue"
                : "w-1.5 h-1.5 bg-ink-subtle/40 hover:bg-ink-subtle"
            }`}
          />
        ))}
      </nav>

      {/* Hint */}
      <div className="fixed bottom-3 left-1/2 -translate-x-1/2 z-20 font-mono text-[10px] tracking-[0.22em] text-ink-subtle/70 pointer-events-none">
        ↑ ↓ &nbsp; SCROLL &nbsp; SWIPE
      </div>
    </main>
  );
}

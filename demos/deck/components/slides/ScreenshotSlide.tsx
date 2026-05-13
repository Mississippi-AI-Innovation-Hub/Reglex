"use client";

import Image from "next/image";
import { motion, useReducedMotion } from "framer-motion";
import { SlideShell } from "@/components/SlideShell";
import { Eyebrow } from "@/components/SlideShell";

type Props = {
  index: number;
  total: number;
  eyebrow: string;
  title: React.ReactNode;
  body: string;
  badges?: string[];
  imageSrc: string;
  imageAlt: string;
  imageRatio?: number;
};

export function ScreenshotSlide({
  index,
  total,
  eyebrow,
  title,
  body,
  badges = [],
  imageSrc,
  imageAlt,
  imageRatio = 16 / 10,
}: Props) {
  const reduce = useReducedMotion();
  return (
    <SlideShell index={index} total={total} bare>
      <div className="absolute inset-0 grid grid-cols-1 lg:grid-cols-[minmax(320px,32%)_1fr]">
        {/* Meta panel */}
        <motion.div
          initial={reduce ? { opacity: 0 } : { opacity: 0, x: -16 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ amount: 0.4, once: false }}
          transition={{ type: "spring", stiffness: 110, damping: 18 }}
          className="bg-canvas border-r border-line flex flex-col justify-center gap-5 px-[clamp(2rem,3.5vw,3.5rem)] py-[clamp(3rem,6vh,5rem)] relative z-10"
        >
          <div>
            <Eyebrow>{eyebrow}</Eyebrow>
          </div>
          <h3 className="font-sans font-semibold tracking-[-0.025em] text-ink text-[clamp(1.7rem,2.4vw,2.4rem)] leading-[1.1]">
            {title}
          </h3>
          <p className="font-light text-ink-muted text-[clamp(1rem,1.2vw,1.18rem)] leading-[1.55] max-w-[40ch]">
            {body}
          </p>
          {badges.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {badges.map((b, i) => (
                <span
                  key={i}
                  className="font-mono text-[10px] tracking-[0.16em] uppercase text-ink-muted px-2.5 py-1.5 border border-line rounded bg-surface"
                >
                  {b}
                </span>
              ))}
            </div>
          )}
        </motion.div>

        {/* Image stage */}
        <motion.div
          initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.98 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ amount: 0.3, once: false }}
          transition={{ type: "spring", stiffness: 90, damping: 18 }}
          className="bg-surface flex items-center justify-center px-[clamp(2rem,3.5vw,4rem)] py-[clamp(2rem,4vh,4rem)] overflow-hidden"
        >
          <div
            className="relative w-full max-w-[1200px]"
            style={{ aspectRatio: imageRatio }}
          >
            <Image
              src={imageSrc}
              alt={imageAlt}
              fill
              sizes="(max-width: 1024px) 100vw, 68vw"
              className="object-contain rounded shadow-[0_24px_60px_-22px_rgba(32,33,36,0.32),0_8px_22px_-10px_rgba(32,33,36,0.16)] border border-line bg-canvas"
              priority={index < 3}
            />
          </div>
        </motion.div>
      </div>
    </SlideShell>
  );
}

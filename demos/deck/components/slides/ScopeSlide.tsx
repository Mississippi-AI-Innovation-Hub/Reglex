"use client";

import { SlideShell } from "@/components/SlideShell";
import { SlideTransition, SlideItem } from "@/components/SlideTransition";
import { CheckCircle2, GitBranchPlus } from "lucide-react";

const IN_SCOPE = [
  {
    title: "7 states",
    body: "Mississippi, Tennessee, Alabama, Georgia, Arkansas, Texas, Louisiana",
  },
  {
    title: "3 agency types per state",
    body: "Medical boards, dental boards, real estate commissions",
  },
  {
    title: "21 official regulator pages monitored",
    body: "One per state-agency combination",
  },
  {
    title: "Source: each state's SoS portal",
    body: "Administrative rules and the regulators that portal publicly links to",
  },
];

const EXTENDS = [
  {
    title: "Direct board crawls",
    body: "Advisory opinions, disciplinary records, internal board policies",
  },
  {
    title: "State statute corpora",
    body: "Unlocks the full authority-overreach detection capability",
  },
  {
    title: "Additional agency types",
    body: "Nursing, insurance, contractors, cosmetology, and more",
  },
  {
    title: "Additional states",
    body: "Beyond the Southeast pilot footprint",
  },
];

export function ScopeSlide({ index, total }: { index: number; total: number }) {
  return (
    <SlideShell index={index} total={total} eyebrow="Scope">
      <SlideTransition className="flex-1 flex flex-col max-w-[84rem] mx-auto w-full">
        <SlideItem>
          <h2 className="font-sans font-semibold tracking-[-0.025em] text-ink leading-[1.05] text-[clamp(2rem,3.4vw,3.4rem)] max-w-[32ch]">
            Honest about what we have, and where the architecture extends.
          </h2>
        </SlideItem>
        <SlideItem>
          <div className="g-rule mt-[clamp(1rem,2vh,1.4rem)]" />
        </SlideItem>
        <SlideItem>
          <p className="mt-[clamp(1rem,2vh,1.4rem)] text-ink-muted font-light text-[clamp(1rem,1.2vw,1.2rem)] leading-[1.55] max-w-[68ch]">
            A pilot has to draw a line somewhere. Here&rsquo;s where we drew
            ours, and where the same architecture takes you next.
          </p>
        </SlideItem>

        <SlideItem className="mt-[clamp(1.6rem,3vh,2.4rem)]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-[clamp(1.5rem,2.5vw,3rem)]">
            <ScopeColumn
              badgeIcon={CheckCircle2}
              badgeTone="green"
              badgeText="Verified"
              heading="In scope today"
              items={IN_SCOPE}
            />
            <ScopeColumn
              badgeIcon={GitBranchPlus}
              badgeTone="blue"
              badgeText="Extensible"
              heading="Where the architecture extends"
              items={EXTENDS}
            />
          </div>
        </SlideItem>

        <SlideItem className="mt-auto pt-[clamp(1.4rem,2.8vh,2rem)]">
          <p className="font-light text-ink-muted text-[clamp(0.9rem,1.05vw,1.05rem)] leading-[1.55]">
            Each agency we add costs roughly $30 to load and $50/mo to maintain.
            Same economics as adding a state.
          </p>
        </SlideItem>
      </SlideTransition>
    </SlideShell>
  );
}

function ScopeColumn({
  badgeIcon: BadgeIcon,
  badgeTone,
  badgeText,
  heading,
  items,
}: {
  badgeIcon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  badgeTone: "green" | "blue";
  badgeText: string;
  heading: string;
  items: { title: string; body: string }[];
}) {
  const toneText = badgeTone === "green" ? "text-g-green" : "text-g-blue";
  const toneBorder = badgeTone === "green" ? "border-g-green/40" : "border-g-blue/40";
  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between gap-3 pb-3 border-b border-line">
        <h3 className="font-sans font-semibold text-ink text-[clamp(1.1rem,1.4vw,1.4rem)] tracking-[-0.015em]">
          {heading}
        </h3>
        <span className={`inline-flex items-center gap-1.5 font-mono text-[10px] tracking-[0.18em] uppercase px-2 py-1 rounded border ${toneBorder} ${toneText} bg-surface`}>
          <BadgeIcon className="w-3 h-3" strokeWidth={2} />
          {badgeText}
        </span>
      </div>
      <ul className="flex flex-col">
        {items.map((it, i) => (
          <li key={i} className="py-[clamp(0.7rem,1.4vh,1rem)] border-b border-line-soft last:border-b-0">
            <div className="font-sans font-medium text-ink text-[clamp(0.98rem,1.15vw,1.12rem)] tracking-[-0.01em]">
              {it.title}
            </div>
            <div className="mt-1 font-light text-ink-muted text-[clamp(0.88rem,1vw,1rem)] leading-[1.5]">
              {it.body}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

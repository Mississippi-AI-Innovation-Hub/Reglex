"use client";

import {
  Bot,
  Globe2,
  Link2,
  MessageSquareText,
  Repeat,
  Sparkles,
} from "lucide-react";

import { DeckShell } from "@/components/DeckShell";
import { TitleSlide } from "@/components/slides/TitleSlide";
import { TeamSlide } from "@/components/slides/TeamSlide";
import { FeatureGridSlide } from "@/components/slides/FeatureGridSlide";
import { ProblemSlide } from "@/components/slides/ProblemSlide";
import { CapabilityGridSlide } from "@/components/slides/CapabilityGridSlide";
import { ScreenshotSlide } from "@/components/slides/ScreenshotSlide";
import { BigNumberSlide } from "@/components/slides/BigNumberSlide";
import { BridgeSlide } from "@/components/slides/BridgeSlide";
import { FreshnessSlide } from "@/components/slides/FreshnessSlide";
import { Phase2ResultSlide } from "@/components/slides/Phase2ResultSlide";
import { ScopeSlide } from "@/components/slides/ScopeSlide";
import { FitsTogetherSlide } from "@/components/slides/FitsTogetherSlide";
import { LiveDemoSlide } from "@/components/slides/LiveDemoSlide";
import { CostSlide } from "@/components/slides/CostSlide";
import { CostBreakdownSlide } from "@/components/slides/CostBreakdownSlide";
import { ClosingSlide } from "@/components/slides/ClosingSlide";
import { ThanksSlide } from "@/components/slides/ThanksSlide";

const TOTAL = 20;

export default function Page() {
  let i = -1;
  const next = () => ++i;

  return (
    <DeckShell>
      <TitleSlide
        index={next()}
        total={TOTAL}
        eyebrow="Mississippi Secretary of State · AI Innovation Hub"
        title={
          <>
            Reglex<span className="text-g-blue">.</span>
          </>
        }
        subtitle="Phase 1 + Phase 2 readout. From a Mississippi-only chatbot to a multi-state legal research system."
        meta={{ left: "04 / 23 / 2026", right: "Proof of Concept" }}
      />

      <TeamSlide index={next()} total={TOTAL} />

      <FeatureGridSlide
        index={next()}
        total={TOTAL}
        eyebrow="Mission"
        title="What we set out to deliver."
        items={[
          {
            icon: MessageSquareText,
            accent: "blue",
            title: "Accessibility",
            body: "Make complex statutory text searchable in plain English. No legal training required.",
          },
          {
            icon: Link2,
            accent: "red",
            title: "Transparency",
            body: "Every answer ties back to the exact statute, section, and source document.",
          },
          {
            icon: Sparkles,
            accent: "yellow",
            title: "Efficiency",
            body: "Cut the time it takes staff to verify authority from hours to seconds.",
          },
        ]}
      />

      <ProblemSlide index={next()} total={TOTAL} />

      <CapabilityGridSlide
        index={next()}
        total={TOTAL}
        eyebrow="Phase 1 · What We Built"
        title="Mississippi's first AI statutory research assistant."
        lede="A private, internal tool that lets SoS staff ask questions in plain English and get back answers grounded in the exact statute."
        columns={4}
        items={[
          {
            num: "01",
            title: "The Mississippi Knowledge Base",
            body: "Ingests and indexes Mississippi statutes and administrative regulations.",
          },
          {
            num: "02",
            title: "Grounded Answers",
            body: "Every response links back to the exact statutory authority and source text.",
          },
          {
            num: "03",
            title: "Plain-English Chat",
            body: "No legal-search syntax. No training. Ask the way you'd ask a colleague.",
          },
          {
            num: "04",
            title: "Audit-Ready Output",
            body: "Citations are pinned to the exact section, verifiable in seconds.",
          },
        ]}
      />

      <ScreenshotSlide
        index={next()}
        total={TOTAL}
        eyebrow="Phase 1 · In Action"
        title="Ask in plain English. Get back the exact statute."
        body="SoS staff type a regulatory question; the system answers with the statutory authority and section visible inline. No opaque outputs, no guesswork."
        badges={["Mississippi corpus", "Inline citations", "Audit-ready"]}
        imageSrc="/assets/Phase1_screenshot.png"
        imageAlt="Phase 1 chat interface showing a query and grounded answer with statutory citations"
      />

      <BigNumberSlide
        index={next()}
        total={TOTAL}
        eyebrow="Phase 1 · Result"
        number="75"
        unit="%+"
        accent="green"
        label="Cleared the contractual accuracy bar, with every answer paired to its source citation."
        sub="Delivered as an internal tool for SoS staff. No public deployment, no opaque outputs, no guesswork."
      />

      <BridgeSlide index={next()} total={TOTAL} />

      <FeatureGridSlide
        index={next()}
        total={TOTAL}
        eyebrow="Phase 2 · Our Approach"
        title="We extended Phase 1 in three directions."
        items={[
          {
            icon: Globe2,
            accent: "blue",
            title: "Multi-State Coverage",
            body: "Expanded from Mississippi alone to seven states across the Southeast, focused on three regulated professions: medical, dental, and real estate.",
          },
          {
            icon: Repeat,
            accent: "green",
            title: "Built to Stay Current",
            body: "Crawlers for all 21 official sources are in place today. The weekly auto-refresh and change-alert loop is designed end-to-end and ready to activate on production deployment.",
          },
          {
            icon: Bot,
            accent: "yellow",
            title: "Specialized Research Agents",
            body: "Beyond Q&A, the system now compares, benchmarks, and synthesizes. It does not just look things up.",
          },
        ]}
      />

      <FreshnessSlide index={next()} total={TOTAL} />

      <CapabilityGridSlide
        index={next()}
        total={TOTAL}
        eyebrow="Phase 2 · What's New"
        title="Six new ways to ask the question."
        columns={3}
        items={[
          {
            num: "01",
            title: "Cross-State Comparison",
            body: "Side-by-side how seven states regulate medical, dental, and real estate licensing.",
          },
          {
            num: "02",
            title: "Fee & Fine Benchmarking",
            body: "Compare licensing fees, fines, and renewals across jurisdictions in one query.",
          },
          {
            num: "03",
            title: "Term Frequency Analysis",
            body: "How often a phrase appears across the corpus, with the actual references attached.",
          },
          {
            num: "04",
            title: "Reciprocity Analysis",
            body: "Which states honor each other's licenses, and on what conditions.",
          },
          {
            num: "05",
            title: "Authority Overreach Detection",
            body: "Flags when an administrative rule may exceed the statutory authority granted to the agency.",
          },
          {
            num: "06",
            title: "Source Refresh Loop",
            body: "Crawlers in place for all 21 sources today. Weekly auto-refresh + change alerts designed end-to-end; activates on production deployment.",
            designed: true,
          },
        ]}
      />

      <ScreenshotSlide
        index={next()}
        total={TOTAL}
        eyebrow="Phase 2 · In Action"
        title="One question. Seven states. Every claim still cited."
        body="The research view turns a single prompt into a structured cross-state answer: comparison tables, fee benchmarks, or authority chains depending on what was asked."
        badges={["7 states", "Medical · Dental · Real Estate", "Same citation guarantee"]}
        imageSrc="/assets/phase_2.png"
        imageAlt="Phase 2 research interface showing a multi-state comparison with citations"
      />

      <Phase2ResultSlide index={next()} total={TOTAL} />

      <ScopeSlide index={next()} total={TOTAL} />

      <FitsTogetherSlide index={next()} total={TOTAL} />

      <LiveDemoSlide index={next()} total={TOTAL} />

      <CostSlide index={next()} total={TOTAL} />

      <CostBreakdownSlide index={next()} total={TOTAL} />

      <ClosingSlide index={next()} total={TOTAL} />

      <ThanksSlide index={next()} total={TOTAL} />
    </DeckShell>
  );
}

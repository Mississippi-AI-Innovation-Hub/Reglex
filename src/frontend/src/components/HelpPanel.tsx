/**
 * Slide-over panel that explains every transparency signal in the UI.
 * Two views: "Simple" (plain English) and "Detailed" (formulas, thresholds, caveats).
 * Triggered by the HOW IT WORKS button in the nav.
 */

import { useEffect, useState } from 'react';
import { X, ShieldCheck, Shield, ShieldAlert, AlertTriangle } from 'lucide-react';

type View = 'simple' | 'detailed';

interface HelpPanelProps {
  open: boolean;
  onClose: () => void;
}

export function HelpPanel({ open, onClose }: HelpPanelProps) {
  const [view, setView] = useState<View>('simple');

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className="fixed top-0 right-0 z-[70] h-full w-full max-w-md bg-[#0a0a0a] border-l border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-panel-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-900">
          <div>
            <h2
              id="help-panel-title"
              className="text-sm font-mono tracking-widest text-white uppercase"
            >
              How it works
            </h2>
            <p className="text-[10px] font-mono text-zinc-500 mt-1">
              Every signal you see, explained
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-zinc-900 transition-colors"
            aria-label="Close help panel"
          >
            <X size={18} />
          </button>
        </div>

        {/* View toggle */}
        <div className="px-5 pt-4">
          <div className="inline-flex items-center bg-zinc-900/80 border border-zinc-800 rounded-md p-0.5">
            <button
              onClick={() => setView('simple')}
              className={`px-3 py-1.5 text-[11px] font-mono tracking-wider rounded transition-all ${
                view === 'simple'
                  ? 'bg-white text-black'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              SIMPLE
            </button>
            <button
              onClick={() => setView('detailed')}
              className={`px-3 py-1.5 text-[11px] font-mono tracking-wider rounded transition-all ${
                view === 'detailed'
                  ? 'bg-white text-black'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              DETAILED
            </button>
          </div>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-6">
          {view === 'simple' ? <SimpleView /> : <DetailedView />}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-zinc-900 text-[10px] font-mono text-zinc-500">
          Esc to close · Pilot eval v1: primary 0.73 / overall 0.72 (24/25)
        </div>
      </aside>
    </>
  );
}

/* ---------- Reusable display fragments ---------- */

function ChipDemo({
  label,
  styles,
  icon,
}: {
  label: string;
  styles: string;
  icon?: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-widest border ${styles}`}
    >
      {icon}
      {label}
    </span>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="text-[11px] font-mono uppercase tracking-widest text-zinc-300 mb-2">
        {title}
      </h3>
      <div className="text-sm text-zinc-300 leading-relaxed space-y-2">
        {children}
      </div>
    </section>
  );
}

/* ---------- Simple view ---------- */

function SimpleView() {
  return (
    <>
      <Section title="Match chips on each citation">
        <p>
          When the system finds a document, it tags how confident it is in the
          match:
        </p>
        <div className="flex flex-wrap items-center gap-2 my-2">
          <ChipDemo
            label="Strong Match"
            styles="border-green-700/50 bg-green-900/20 text-green-300"
          />
          <ChipDemo
            label="Moderate Match"
            styles="border-amber-700/50 bg-amber-900/20 text-amber-300"
          />
          <ChipDemo
            label="Weak Match"
            styles="border-zinc-700/50 bg-zinc-900/40 text-zinc-400"
          />
        </div>
        <ul className="list-disc pl-5 space-y-1 text-zinc-400">
          <li>
            <span className="text-green-400">Strong</span> — the document hit
            on both meaning and the exact words you searched.
          </li>
          <li>
            <span className="text-amber-300">Moderate</span> — it's relevant
            but not a perfect match on either side.
          </li>
          <li>
            <span className="text-zinc-300">Weak</span> — borderline; we
            included it for transparency but trust it less.
          </li>
        </ul>
      </Section>

      <Section title="Grounding pill on each answer">
        <p>Tells you whether the model stuck to the documents:</p>
        <div className="flex flex-wrap items-center gap-2 my-2">
          <ChipDemo
            label="Grounded · 4 cited"
            styles="border-green-700/50 bg-green-900/20 text-green-300"
            icon={<ShieldCheck className="w-3 h-3" strokeWidth={2.5} />}
          />
          <ChipDemo
            label="Grounded · 4 cited · 1 inference"
            styles="border-amber-700/50 bg-amber-900/20 text-amber-300"
            icon={<Shield className="w-3 h-3" strokeWidth={2.5} />}
          />
          <ChipDemo
            label="Grounding-summary missing"
            styles="border-red-700/50 bg-red-900/20 text-red-300"
            icon={<ShieldAlert className="w-3 h-3" strokeWidth={2.5} />}
          />
        </div>
        <p className="text-zinc-400">
          When the answer goes beyond the documents, that part shows in a{' '}
          <span className="text-yellow-300">yellow inference box</span> with an{' '}
          <AlertTriangle className="inline w-3 h-3 text-yellow-400" /> icon —
          so you always know which claims came from real sources versus which
          ones the model extrapolated.
        </p>
      </Section>

      <Section title="The bottom line">
        <p className="text-zinc-300">
          You should be able to look at any answer and immediately see: (1) is
          it grounded in real documents, (2) how good were those documents,
          and (3) what did the model make up. No hidden judgment calls.
        </p>
      </Section>
    </>
  );
}

/* ---------- Detailed view ---------- */

function DetailedView() {
  return (
    <>
      <Section title="Match tier — calculation">
        <p>
          Each citation carries a <code className="text-zinc-200 bg-zinc-900 px-1 rounded text-[12px]">relevance</code> field
          which is the raw <strong>RRF (Reciprocal Rank Fusion)</strong> score
          from the backend's hybrid retrieval. RRF merges two rankers — kNN
          (semantic vector search) and BM25 (keyword) — using:
        </p>
        <pre className="text-[11px] font-mono bg-zinc-900/60 border border-zinc-800 rounded p-3 text-zinc-300 overflow-x-auto">
{`score = Σ  1 / (k + rank)   where k = 60`}
        </pre>
        <p>
          Typical observed range: <code className="text-zinc-200">0.01 – 0.06</code>.
          Thresholds:
        </p>
        <table className="w-full text-[12px] border border-zinc-800 rounded">
          <thead>
            <tr className="bg-zinc-900/60 text-zinc-300">
              <th className="text-left px-2 py-1 border-b border-zinc-800">Tier</th>
              <th className="text-left px-2 py-1 border-b border-zinc-800">Rule</th>
              <th className="text-left px-2 py-1 border-b border-zinc-800">Meaning</th>
            </tr>
          </thead>
          <tbody className="text-zinc-400">
            <tr>
              <td className="px-2 py-1.5 border-b border-zinc-900 text-green-300">STRONG</td>
              <td className="px-2 py-1.5 border-b border-zinc-900 font-mono">≥ 0.05</td>
              <td className="px-2 py-1.5 border-b border-zinc-900">Top-ranked in both kNN and BM25</td>
            </tr>
            <tr>
              <td className="px-2 py-1.5 border-b border-zinc-900 text-amber-300">MODERATE</td>
              <td className="px-2 py-1.5 border-b border-zinc-900 font-mono">0.02 – 0.05</td>
              <td className="px-2 py-1.5 border-b border-zinc-900">High in one ranker, mid in the other</td>
            </tr>
            <tr>
              <td className="px-2 py-1.5 text-zinc-300">WEAK</td>
              <td className="px-2 py-1.5 font-mono">&lt; 0.02</td>
              <td className="px-2 py-1.5">Made it into top-N but low signal</td>
            </tr>
          </tbody>
        </table>
        <p className="text-zinc-500 text-[12px]">
          Hover any chip to see the raw RRF score (<code>RRF score: 0.0XX</code>).
        </p>
      </Section>

      <Section title="Grounding pill — derivation">
        <p>
          The backend's <code className="text-zinc-200 bg-zinc-900 px-1 rounded text-[12px]">SYSTEM_PROMPT</code> requires
          every response to end with a single line:
        </p>
        <pre className="text-[11px] font-mono bg-zinc-900/60 border border-zinc-800 rounded p-3 text-zinc-300 overflow-x-auto">
{`Grounding summary: <N> grounded, <M> inferred`}
        </pre>
        <p>The frontend parses that line:</p>
        <ul className="list-disc pl-5 space-y-1 text-zinc-400">
          <li><strong>Green</strong> when M = 0 (every claim cited).</li>
          <li><strong>Amber</strong> when M ≥ 1 (some inference present, marked).</li>
          <li><strong>Red</strong> when the line is missing (the model didn't follow the prompt — treat the answer with suspicion).</li>
        </ul>
      </Section>

      <Section title="Inference callouts — how they appear">
        <p>
          When the model needs to extrapolate, the system prompt requires it to
          wrap that text in a <code className="text-zinc-200 bg-zinc-900 px-1 rounded text-[12px]">[INFERENCE]:</code> block.
          The frontend parses these out and renders them in a yellow callout —
          they never get to look like cited content.
        </p>
        <div className="border border-yellow-700/40 bg-yellow-900/20 rounded p-2.5 text-xs text-yellow-100/90">
          <div className="flex items-center gap-1.5 mb-1">
            <AlertTriangle className="w-3 h-3 text-yellow-400" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-yellow-300">
              Inference — not from cited sources
            </span>
          </div>
          Example: "Most states require renewal every 4 years."
        </div>
      </Section>

      <Section title="Honest caveats">
        <ul className="list-disc pl-5 space-y-1.5 text-zinc-400">
          <li>
            Citation tier thresholds (0.02, 0.05) were eyeballed from observed
            RRF score distributions, not empirically calibrated against human
            relevance judgments. The architecture supports tuning them against
            the offline eval when production thresholds are needed.
          </li>
          <li>
            We don't show a percentage on citations because converting an
            unbounded RRF score to a percent requires a calibration study we
            haven't done. Anything labeled <code>87% MATCH</code> would be
            fiction.
          </li>
          <li>
            Inference marking is currently <em>self-reported</em> by the model.
            The <code className="text-zinc-300">reflection_agent.py</code>
            design adds post-hoc per-claim verification so grounding becomes
            verified, not just claimed — ready to activate when the system
            is deployed to production.
          </li>
        </ul>
      </Section>

      <Section title="Pilot eval headline (v1)">
        <pre className="text-[11px] font-mono bg-zinc-900/60 border border-zinc-800 rounded p-3 text-zinc-300 overflow-x-auto whitespace-pre">
{`Primary (Groundedness × Inference Honesty):  0.73   (24/25)
Overall (4-axis mean):                        0.72

Groundedness        0.66
Inference Honesty   0.80   ← the new transparency capability
Correctness         0.56
Jurisdiction        0.88

Strongest pattern:  statutory_authority   0.92
Weakest pattern:    fee_comparison        0.52`}
        </pre>
        <p className="text-zinc-500 text-[12px]">
          Full report: <code>evals/report_v1.md</code>. Methodology:{' '}
          <code>docs/superpowers/specs/2026-04-20-pilot-accuracy-eval-design.md</code>.
        </p>
      </Section>
    </>
  );
}

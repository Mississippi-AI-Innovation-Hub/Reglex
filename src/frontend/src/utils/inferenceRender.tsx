/**
 * Parses LLM responses for [INFERENCE]: ... blocks and a trailing
 * "Grounding summary: N grounded, M inferred" line.
 *
 * Returns segments for rendering and the grounding counts for the header pill.
 *
 * Keep parseInferenceBlocks() in sync with frontend/test_inference_parser.mjs.
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';

export type Segment =
  | { kind: 'text'; content: string }
  | { kind: 'inference'; content: string };

export interface ParseResult {
  segments: Segment[];
  grounded: number;
  inferred: number;
  summaryFound: boolean;
}

export function parseInferenceBlocks(text: string): ParseResult {
  if (!text) {
    return { segments: [], grounded: 0, inferred: 0, summaryFound: false };
  }

  const summaryRe =
    /^[ \t]*Grounding summary:\s*(\d+)\s+grounded,\s*(\d+)\s+inferred[ \t]*$/m;
  const summaryMatch = text.match(summaryRe);
  const grounded = summaryMatch ? Number(summaryMatch[1]) : 0;
  const inferred = summaryMatch ? Number(summaryMatch[2]) : 0;
  const body = summaryMatch
    ? text.replace(summaryMatch[0], '').replace(/\n+$/, '')
    : text;

  const blockRe = /\[INFERENCE\]:\s*([\s\S]*?)(?=\n\s*\n|\n\[INFERENCE\]:|$)/g;
  const segments: Segment[] = [];
  let cursor = 0;
  let m: RegExpExecArray | null;
  while ((m = blockRe.exec(body)) !== null) {
    if (m.index > cursor) {
      segments.push({ kind: 'text', content: body.slice(cursor, m.index) });
    }
    segments.push({ kind: 'inference', content: m[1].trim() });
    cursor = m.index + m[0].length;
  }
  if (cursor < body.length) {
    segments.push({ kind: 'text', content: body.slice(cursor) });
  }

  return { segments, grounded, inferred, summaryFound: Boolean(summaryMatch) };
}

export function InferenceCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-3 p-3 rounded-md border border-yellow-700/40 bg-yellow-900/20">
      <div className="flex items-center gap-1.5 mb-1.5">
        <AlertTriangle
          className="w-3.5 h-3.5 text-yellow-400"
          strokeWidth={2}
        />
        <span className="text-[10px] font-mono uppercase tracking-widest text-yellow-300">
          Inference — not from cited sources
        </span>
      </div>
      <div className="text-sm text-yellow-100/90 leading-relaxed">
        {children}
      </div>
    </div>
  );
}

/**
 * Post-processes LLM markdown to make inline citations clickable.
 *
 * Detects patterns like:
 *   - Filename mentions: "00000050c.pdf"
 *   - Rule citations: "Rule §189.3", "Chapter 540-X-22", "§172.4"
 *   - Statute codes: "Miss. Code Ann. § 73-25-29"
 *
 * When clicked, opens the PDF preview at the referenced page by matching
 * against the message's citations list.
 */

import React from 'react';
import type { Citation } from '../types';

/** Safely coerce a backend field (string | string[] | number | null | undefined) to string. */
function coerceString(v: unknown): string {
  if (typeof v === 'string') return v;
  if (Array.isArray(v) && typeof v[0] === 'string') return v[0];
  return '';
}

export type OpenPageFn = (
  document: string,
  page: number,
  state?: string,
  agencyType?: string,
) => void;

/**
 * Regex patterns that identify clickable citation references.
 * Ordered from most specific to least specific.
 */
const CITATION_PATTERNS: { name: string; re: RegExp }[] = [
  // Filename like "00000050c.pdf" or "§189.3.pdf" or "540-X-22.pdf"
  { name: 'filename', re: /([A-Za-z0-9§\.\-_]+\.pdf)/g },
  // Section/Rule/Chapter references
  { name: 'section', re: /(§\s?[\d\.\-]+(?:\([a-z0-9]+\))?)/g },
  { name: 'rule', re: /(Rule\s+[\d\.\-]+[A-Z]?)/g },
  { name: 'chapter', re: /(Chapter\s+[\d\.\-A-Z]+)/g },
];


/**
 * Given a text node and a list of citations, split it into a mix of
 * plain text and clickable spans for anything that matches a citation.
 */
export function linkifyText(
  text: string,
  citations: Citation[],
  onOpenPage?: OpenPageFn,
): React.ReactNode[] {
  if (!text || !citations || citations.length === 0 || !onOpenPage) {
    return [text];
  }

  // Build a lookup: filename → citation, section → citation
  const filenameMap = new Map<string, Citation>();
  const sectionMap = new Map<string, Citation>();
  const statuteMap = new Map<string, Citation>();

  for (const c of citations) {
    const fn = coerceString(c.document).toLowerCase();
    if (fn) filenameMap.set(fn, c);

    const sec = coerceString(c.section).toLowerCase().trim();
    if (sec) sectionMap.set(sec, c);

    // Index statute codes too
    for (const sc of c.statute_codes || []) {
      const s = coerceString(sc);
      if (s) statuteMap.set(s.toLowerCase().trim(), c);
    }
  }

  // Collect all match positions
  type Match = {
    start: number;
    end: number;
    raw: string;
    citation: Citation;
    page: number;
  };
  const matches: Match[] = [];

  // 1. Direct filename matches
  for (const { re } of CITATION_PATTERNS) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const raw = m[1];
      const normalized = raw.toLowerCase().trim();

      let cite: Citation | undefined;
      if (normalized.endsWith('.pdf')) {
        cite = filenameMap.get(normalized);
      } else {
        cite = sectionMap.get(normalized) || statuteMap.get(normalized);
        // Fuzzy: partial match into sections/statutes
        if (!cite) {
          for (const [key, c] of sectionMap.entries()) {
            if (key.includes(normalized) || normalized.includes(key)) {
              cite = c;
              break;
            }
          }
        }
        if (!cite) {
          for (const [key, c] of statuteMap.entries()) {
            if (key.includes(normalized) || normalized.includes(key)) {
              cite = c;
              break;
            }
          }
        }
      }

      if (cite) {
        matches.push({
          start: m.index,
          end: m.index + raw.length,
          raw,
          citation: cite,
          page: cite.pages?.[0] || 1,
        });
      }
    }
  }

  if (matches.length === 0) return [text];

  // Sort by start, remove overlapping matches (keep earlier/longer)
  matches.sort((a, b) => a.start - b.start || b.end - b.start - (a.end - a.start));
  const nonOverlap: Match[] = [];
  let cursor = 0;
  for (const m of matches) {
    if (m.start >= cursor) {
      nonOverlap.push(m);
      cursor = m.end;
    }
  }

  // Build output: alternating plain text and clickable spans
  const out: React.ReactNode[] = [];
  let idx = 0;
  nonOverlap.forEach((m, i) => {
    if (m.start > idx) {
      out.push(text.substring(idx, m.start));
    }
    out.push(
      <CitationLink
        key={`cite-${i}-${m.start}`}
        text={m.raw}
        citation={m.citation}
        page={m.page}
        onOpenPage={onOpenPage}
      />,
    );
    idx = m.end;
  });
  if (idx < text.length) {
    out.push(text.substring(idx));
  }

  return out;
}


function CitationLink({
  text,
  citation,
  page,
  onOpenPage,
}: {
  text: string;
  citation: Citation;
  page: number;
  onOpenPage: OpenPageFn;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpenPage(citation.document, page, citation.state, citation.agency_type)}
      className="inline-flex items-center px-1 py-0 rounded text-zinc-200 bg-zinc-800/60 hover:bg-zinc-700 hover:text-white border-b border-dotted border-zinc-500 hover:border-white transition-colors cursor-pointer font-mono text-[0.9em]"
      title={`View ${citation.document} page ${page}`}
    >
      {text}
    </button>
  );
}

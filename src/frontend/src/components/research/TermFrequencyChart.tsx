import React from 'react';
import type { TermFrequencyEntry } from '../../types';

interface TermFrequencyChartProps {
  data: TermFrequencyEntry[];
  totalCount: number;
}

export const TermFrequencyChart: React.FC<TermFrequencyChartProps> = ({ data, totalCount }) => {
  if (!data.length) return null;

  // Group by state for display
  const byState: Record<string, { total: number; entries: TermFrequencyEntry[] }> = {};
  for (const entry of data) {
    if (!byState[entry.state]) {
      byState[entry.state] = { total: 0, entries: [] };
    }
    byState[entry.state].total += entry.count;
    byState[entry.state].entries.push(entry);
  }

  const maxCount = Math.max(...Object.values(byState).map(s => s.total));

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
          Term Frequency Analysis
        </span>
        <span className="text-[10px] font-mono text-zinc-400">
          Total: {totalCount} occurrences
        </span>
      </div>

      {/* Bar chart */}
      <div className="space-y-2 mb-4">
        {Object.entries(byState)
          .sort(([, a], [, b]) => b.total - a.total)
          .map(([state, { total }]) => (
            <div key={state} className="flex items-center gap-3">
              <span className="text-xs font-mono text-zinc-300 w-6">{state}</span>
              <div className="flex-1 h-5 bg-zinc-900 rounded overflow-hidden">
                <div
                  className="h-full bg-zinc-600 rounded transition-all duration-500"
                  style={{ width: `${(total / maxCount) * 100}%` }}
                />
              </div>
              <span className="text-xs font-mono text-zinc-400 w-8 text-right">{total}</span>
            </div>
          ))}
      </div>

      {/* Detail table */}
      <div className="overflow-x-auto border border-zinc-800 rounded-lg">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/50">
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Term</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">State</th>
              <th className="px-3 py-2 text-right text-zinc-400 font-medium">Count</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Document</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Context</th>
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 20).map((entry, idx) => (
              <tr key={idx} className="border-b border-zinc-800/50 hover:bg-zinc-900/30">
                <td className="px-3 py-2 text-zinc-200">{entry.term}</td>
                <td className="px-3 py-2 text-zinc-300">{entry.state}</td>
                <td className="px-3 py-2 text-right text-zinc-200">{entry.count}</td>
                <td className="px-3 py-2 text-zinc-400 truncate max-w-xs">{entry.document}</td>
                <td className="px-3 py-2 text-zinc-500 truncate max-w-sm">{entry.context_snippet}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

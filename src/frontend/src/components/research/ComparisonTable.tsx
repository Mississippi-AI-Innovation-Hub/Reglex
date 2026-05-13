import React from 'react';
import type { ComparisonRow } from '../../types';

interface ComparisonTableProps {
  rows: ComparisonRow[];
  statesCompared?: string[];
}

export const ComparisonTable: React.FC<ComparisonTableProps> = ({ rows, statesCompared }) => {
  if (!rows.length) return null;

  return (
    <div className="mt-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
          Cross-Jurisdiction Comparison
        </span>
        {statesCompared && (
          <span className="text-[10px] font-mono text-zinc-600">
            ({statesCompared.join(', ')})
          </span>
        )}
      </div>
      <div className="overflow-x-auto border border-zinc-800 rounded-lg">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/50">
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">State</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Provision</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Citation</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Section</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={idx} className="border-b border-zinc-800/50 hover:bg-zinc-900/30">
                <td className="px-3 py-2 text-zinc-200 font-semibold whitespace-nowrap">{row.state}</td>
                <td className="px-3 py-2 text-zinc-300 max-w-md">{row.provision}</td>
                <td className="px-3 py-2 text-zinc-400 truncate max-w-xs">{row.citation}</td>
                <td className="px-3 py-2 text-zinc-400 whitespace-nowrap">{row.section || 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

import React from 'react';
import type { FeeEntry } from '../../types';

interface FeeTableProps {
  fees: FeeEntry[];
  statesAnalyzed?: string[];
}

export const FeeTable: React.FC<FeeTableProps> = ({ fees, statesAnalyzed }) => {
  if (!fees.length) return null;

  return (
    <div className="mt-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
          Fee & Fine Analysis
        </span>
        {statesAnalyzed && statesAnalyzed.length > 0 && (
          <span className="text-[10px] font-mono text-zinc-600">
            ({statesAnalyzed.join(', ')})
          </span>
        )}
      </div>
      <div className="overflow-x-auto border border-zinc-800 rounded-lg">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/50">
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">State</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Fee Type</th>
              <th className="px-3 py-2 text-right text-zinc-400 font-medium">Amount</th>
              <th className="px-3 py-2 text-right text-zinc-400 font-medium">Cap</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Description</th>
              <th className="px-3 py-2 text-left text-zinc-400 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {fees.map((fee, idx) => {
              const exceedsCap = fee.statutory_cap !== null && fee.amount > fee.statutory_cap;
              return (
                <tr key={idx} className={`border-b border-zinc-800/50 hover:bg-zinc-900/30 ${exceedsCap ? 'bg-red-900/10' : ''}`}>
                  <td className="px-3 py-2 text-zinc-200 font-semibold whitespace-nowrap">{fee.state}</td>
                  <td className="px-3 py-2 text-zinc-300 capitalize">{fee.fee_type.replace('_', ' ')}</td>
                  <td className="px-3 py-2 text-right text-zinc-200">${fee.amount.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right text-zinc-400">
                    {fee.statutory_cap !== null ? `$${fee.statutory_cap.toFixed(2)}` : '—'}
                  </td>
                  <td className="px-3 py-2 text-zinc-400 max-w-xs truncate">{fee.description}</td>
                  <td className="px-3 py-2 text-zinc-500 truncate max-w-xs">{fee.document}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

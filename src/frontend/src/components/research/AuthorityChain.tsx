import React from 'react';
import type { AuthorityEntry } from '../../types';

interface AuthorityChainProps {
  chain: AuthorityEntry[];
  hasAuthority?: boolean | null;
}

export const AuthorityChain: React.FC<AuthorityChainProps> = ({ chain, hasAuthority }) => {
  if (!chain.length) return null;

  return (
    <div className="mt-6">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
          Statutory Authority Chain
        </span>
        {hasAuthority !== null && hasAuthority !== undefined && (
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
            hasAuthority ? 'bg-green-900/30 text-green-400 border border-green-800/50' : 'bg-red-900/30 text-red-400 border border-red-800/50'
          }`}>
            {hasAuthority ? 'AUTHORITY FOUND' : 'POTENTIAL ULTRA VIRES'}
          </span>
        )}
      </div>

      <div className="space-y-3">
        {chain.map((entry, idx) => (
          <div key={idx} className="border border-zinc-800 rounded-lg p-3 bg-zinc-900/30">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-mono font-semibold text-zinc-200">{entry.state}</span>
              <span className="text-[10px] font-mono text-zinc-500">{entry.document}</span>
              {entry.section && (
                <span className="text-[10px] font-mono text-zinc-600">Section: {entry.section}</span>
              )}
            </div>
            {entry.core_rule && (
              <p className="text-xs text-zinc-300 mb-2">{entry.core_rule}</p>
            )}
            {entry.authority_references.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {entry.authority_references.map((ref, i) => (
                  <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded border border-zinc-700 text-zinc-400 bg-black">
                    {ref}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

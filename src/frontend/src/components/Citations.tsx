import { FileText, BookOpen } from 'lucide-react';
import type { Citation } from '../types';

interface CitationsProps {
  citations: Citation[];
}

export const Citations = ({ citations }: CitationsProps) => {
  if (!citations || citations.length === 0) {
    return null;
  }

  return (
    <div className="mt-5 pt-4 border-t border-gray-800/50 w-full">
      <div className="flex items-center gap-1.5 mb-2.5">
        <BookOpen className="w-3.5 h-3.5 text-blue-400" strokeWidth={2} />
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Citations ({citations.length})</h4>
      </div>
      
      <div className="space-y-1.5 w-full">
        {/* Citation Rows */}
        {citations.map((citation, index) => (
          <div
            key={index}
            className="group flex items-center gap-3 p-2.5 rounded-lg bg-black/30 border border-gray-800/50 hover:border-gray-700/60 hover:bg-black/50 transition-all duration-200 w-full"
          >
            {/* Document Icon & Name */}
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <FileText className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" strokeWidth={2} />
              <span className="text-xs text-blue-300 font-mono truncate group-hover:text-blue-200 transition-colors">
                {citation.document}
              </span>
            </div>

            {/* Pages */}
            <div className="flex items-center gap-1 flex-shrink-0">
              {citation.pages.slice(0, 4).map((page, pageIndex) => (
                <span
                  key={pageIndex}
                  className="inline-flex items-center justify-center min-w-[24px] h-5 px-1.5 rounded bg-gray-900/70 border border-gray-700/50 text-[10px] font-semibold text-gray-300"
                >
                  {page}
                </span>
              ))}
              {citation.pages.length > 4 && (
                <span className="text-[10px] text-gray-500 font-medium ml-0.5">
                  +{citation.pages.length - 4}
                </span>
              )}
            </div>

            {/* Match tier (replaces misleading percentage pill) */}
            <div className="flex items-center flex-shrink-0">
              {(() => {
                const score = citation.relevance ?? 0;
                const tier =
                  score >= 0.05 ? 'strong' : score >= 0.02 ? 'moderate' : 'weak';
                const styles = {
                  strong:   'border-green-700/50 bg-green-900/20 text-green-300',
                  moderate: 'border-amber-700/50 bg-amber-900/20 text-amber-300',
                  weak:     'border-zinc-700/50 bg-zinc-900/40 text-zinc-400',
                }[tier];
                const label = tier === 'strong'   ? 'STRONG MATCH'
                            : tier === 'moderate' ? 'MODERATE MATCH'
                            :                       'WEAK MATCH';
                return (
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-widest border ${styles}`}
                    title={`RRF score: ${score.toFixed(3)}`}
                  >
                    {label}
                  </span>
                );
              })()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

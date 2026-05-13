import React from 'react';
import { STATES, AGENCY_TYPES } from '../types';
import type { ResearchFilters } from '../types';

interface FilterPanelProps {
  filters: ResearchFilters;
  onChange: (filters: ResearchFilters) => void;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({ filters, onChange }) => {
  const handleStateToggle = (code: string) => {
    const current = filters.states || [];
    const next = current.includes(code)
      ? current.filter(s => s !== code)
      : [...current, code];
    onChange({ ...filters, states: next.length ? next : undefined });
  };

  const handleAgencyChange = (value: string) => {
    onChange({ ...filters, agency_type: value || undefined });
  };

  return (
    <div className="flex flex-wrap items-center gap-3 px-2 py-2">
      {/* State Chips */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mr-1">States</span>
        {STATES.map(({ code }) => {
          const active = filters.states?.includes(code);
          return (
            <button
              key={code}
              type="button"
              onClick={() => handleStateToggle(code)}
              className={`text-[10px] font-mono px-2 py-1 rounded border transition-colors ${
                active
                  ? 'border-white bg-white text-black'
                  : 'border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500'
              }`}
            >
              {code}
            </button>
          );
        })}
      </div>

      {/* Agency Select */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mr-1">Agency</span>
        <select
          value={filters.agency_type || ''}
          onChange={e => handleAgencyChange(e.target.value)}
          className="text-[10px] font-mono px-2 py-1 rounded border border-zinc-700 bg-black text-zinc-300 focus:outline-none focus:border-zinc-500"
        >
          <option value="">All</option>
          {AGENCY_TYPES.map(({ code, name }) => (
            <option key={code} value={code}>{name}</option>
          ))}
        </select>
      </div>

      {/* Clear */}
      {(filters.states?.length || filters.agency_type) && (
        <button
          type="button"
          onClick={() => onChange({})}
          className="text-[10px] font-mono text-zinc-500 hover:text-white transition-colors"
        >
          CLEAR
        </button>
      )}
    </div>
  );
};

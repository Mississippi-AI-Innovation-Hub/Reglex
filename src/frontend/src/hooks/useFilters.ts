import { useState, useCallback } from 'react';
import type { ResearchFilters } from '../types';

export function useFilters() {
  const [filters, setFilters] = useState<ResearchFilters>({});
  const [showFilters, setShowFilters] = useState(false);

  const updateFilters = useCallback((next: ResearchFilters) => {
    setFilters(next);
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({});
  }, []);

  const toggleFilters = useCallback(() => {
    setShowFilters(prev => !prev);
  }, []);

  const hasActiveFilters = Boolean(
    filters.state || filters.agency_type || (filters.states && filters.states.length > 0)
  );

  return {
    filters,
    showFilters,
    hasActiveFilters,
    updateFilters,
    clearFilters,
    toggleFilters,
  };
}

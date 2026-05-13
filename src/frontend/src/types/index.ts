// ── Phase 1: Core Types ────────────────────────────────────────────────

export interface Citation {
  document: string;
  pages: number[];
  relevance: number;
  // Phase 2 additions
  state?: string;
  agency_type?: string;
  section?: string;
  statute_codes?: string[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isError?: boolean;
  citations?: Citation[];
  // Phase 2 additions
  intent?: string;
  metadata?: ResponseMetadata;
}

export interface ChatConfig {
  apiEndpoint: string;
}

// ── Phase 2: Research Types ───────────────────────────────────────────

export interface ResearchFilters {
  state?: string;
  agency_type?: string;
  states?: string[];
  document_type?: string;
}

export interface ResponseMetadata {
  comparison_table?: ComparisonRow[];
  states_compared?: string[];
  frequency_data?: TermFrequencyEntry[];
  total_count?: number;
  fee_table?: FeeEntry[];
  states_analyzed?: string[];
  reciprocity_data?: ReciprocityEntry[];
  authority_chain?: AuthorityEntry[];
  has_authority?: boolean | null;
}

export interface ApiResponse {
  answer?: string;
  response?: string;
  message?: string;
  citations?: Citation[];
  error?: string;
  // Phase 2 additions
  intent?: string;
  metadata?: ResponseMetadata;
  verification?: VerificationResult;
  query?: string;
}

// ── Comparison ────────────────────────────────────────────────────────

export interface ComparisonRow {
  state: string;
  provision: string;
  citation: string;
  section: string;
  statute_codes: string[];
}

// ── Term Frequency ────────────────────────────────────────────────────

export interface TermFrequencyEntry {
  term: string;
  count: number;
  document: string;
  section: string;
  pages: number[];
  state: string;
  context_snippet: string;
}

// ── Fee Analysis ──────────────────────────────────────────────────────

export interface FeeEntry {
  state: string;
  agency_type: string;
  fee_type: string;
  amount: number;
  description: string;
  statutory_cap: number | null;
  document: string;
  section: string;
  pages: number[];
}

// ── Reciprocity ───────────────────────────────────────────────────────

export interface ReciprocityEntry {
  state: string;
  provisions: string;
  license_categories: string[];
  document: string;
  section: string;
}

// ── Authority ─────────────────────────────────────────────────────────

export interface AuthorityEntry {
  state: string;
  authority_references: string[];
  document: string;
  section: string;
  core_rule: string;
}

// ── Verification ──────────────────────────────────────────────────────

export interface ClaimVerification {
  claim: string;
  supported: boolean;
  confidence: number;
  supporting_citation: string | null;
  explanation: string;
}

export interface VerificationResult {
  overall_confidence: number;
  total_claims: number;
  unsupported_count: number;
  claims: ClaimVerification[];
}

// ── Constants ─────────────────────────────────────────────────────────

export const STATES = [
  { code: 'MS', name: 'Mississippi' },
  { code: 'AL', name: 'Alabama' },
  { code: 'LA', name: 'Louisiana' },
  { code: 'TN', name: 'Tennessee' },
  { code: 'AR', name: 'Arkansas' },
  { code: 'GA', name: 'Georgia' },
  { code: 'TX', name: 'Texas' },
] as const;

export const AGENCY_TYPES = [
  { code: 'medical', name: 'Medical Board' },
  { code: 'real_estate', name: 'Real Estate Commission' },
  { code: 'dental', name: 'Dental Board' },
] as const;

export type StateCode = typeof STATES[number]['code'];
export type AgencyTypeCode = typeof AGENCY_TYPES[number]['code'];

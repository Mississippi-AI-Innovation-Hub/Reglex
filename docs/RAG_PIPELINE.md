# CLaRa RAG Pipeline — Architecture & Rationale

Legal research assistant for the Mississippi Secretary of State. Built on AWS Lambda + OpenSearch Managed + Bedrock (Mistral + Claude + Titan) with a React/Vite frontend.

## 1. Ingestion Pipeline

`ingestion/pipeline.py` — runs locally against S3 PDFs, writes to OpenSearch.

### Per-page flow
```
PyMuPDF text extraction
      │
      ├── No text? ──► Textract detect_document_text (OCR)
      │
      ├── Table-like page? ──► Textract analyze_document (TABLES) → appended as structured text
      │
      ├── Low-value page (< 80 chars / mostly whitespace)? ──► skip LLM, embed raw
      │
      └── Otherwise: Mistral Large structured extraction (batched 3 pages/call)
                    │
                    └── Titan Text v2 (1024-dim) embedding
```

### Why this shape

- **PyMuPDF first, Textract as fallback.** PyMuPDF is free and handles ~95% of pages. Textract OCR ($1.50/1K pages) runs only on scanned pages. Table extraction ($15/1K pages) runs only on pages that look like fee schedules — detected by a cheap heuristic in `extractors.is_table_page` (dollar signs, fee keywords, short-line ratio, numeric columns).
- **LLM batching (3 pages/call).** Mistral is the bottleneck both on cost and latency. Batching cuts calls by ~3x. Single-page fallback is used when batches fail, for reliability.
- **Skip LLM on low-value pages.** Title pages, blank pages, TOC, headers-only. They still get raw-text indexed and embedded so term-counting stays accurate, but we don't waste $0.012 asking an LLM to summarize "Table of Contents".
- **Structured field extraction (not just chunks).** The LLM returns a schema: `abstract_text`, `core_rule`, `statute_codes`, `compliance_requirements`, `fee_amounts`, `section_identifier`, `effective_date`, `license_categories`, `testing_requirements`, `statutory_authority_references`, `reciprocity_provisions`. This structure powers the domain-specific boosts in search and enables typed aggregations (fee comparisons, reciprocity queries) without re-reading documents.
- **Resume on SSO expiry.** Credentials are 1-hour SSO; the pipeline checkpoints after every doc and validates/refreshes clients every 10 docs. `SSOExpiredError` triggers a graceful save-and-exit.

## 2. Dual-Layer Index Design

Every PDF produces two record types in the same OpenSearch index:

| Record type | Purpose | Embedding? |
|---|---|---|
| `document` | Full text per PDF, state/agency tags | No |
| `page` | One record per page with structured fields + `text_embedding` | Yes (1024-dim) |

### Why two record types

- **Retrieval wants pages.** Citations need page numbers. Embeddings over a full 40-page PDF dilute relevance.
- **Analytics wants documents.** Term-frequency queries ("how many times does 'surety bond' appear across all MS statutes?") need the full text to run `full_text.count(term)` with page-anchored regex matches. Running this across page records would fragment counts.
- **Single index, filter by `record_type`.** Kept in one index so hybrid search can restrict to pages and term-frequency can restrict to documents — no cross-index federation.

### Two physical indexes
- `ms-phase1-legal` — Mississippi only (chat mode, scoped research).
- `multistate-phase2-legal` — 7 states × 3 agencies (cross-jurisdiction research).

Chat mode is strictly scoped to Phase 1; research mode to Phase 2. This prevents Phase 2's multistate noise from leaking into focused Mississippi queries.

## 3. Retrieval — Hybrid Search

`lambda_handler.search_pages` runs two queries in parallel and fuses them.

### kNN (semantic)
Titan embedding of the query against `text_embedding` (HNSW, cosine similarity, FAISS engine, `ef_search=512`). Uses a candidate pool of `top_k * 3`.

### BM25 (keyword) with domain boosts
```
statute_codes               x 4.0
statutory_authority_refs    x 3.5
section_identifier          x 3.0
abstract_text, core_rule    x 2.0
raw_text                    x 1.5
compliance_requirements     x 1.5
testing_requirements        x 1.5
reciprocity_provisions      x 1.5
legal_entities              x 1.0
```

### RRF fusion
Reciprocal Rank Fusion with `k=60`: `score = Σ 1/(k + rank)`. Model-free, no score normalization issues, robust when kNN and BM25 return wildly different absolute scores.

### Why hybrid
- **Pure semantic fails on statute codes.** "Miss. Code § 75-24-5" is a string, not a concept. Titan embeds it poorly. BM25 nails it with the 4.0 boost.
- **Pure keyword fails on paraphrase.** "What do I need to do to renew my license?" won't hit "reinstatement requirements" — semantic does.
- **RRF is sturdy.** Avoids the calibration headache of weighted score sums across heterogeneous scoring systems.

## 4. Query Routing — Intent Detection

`detect_intent()` classifies queries by cheap regex patterns:

| Intent | Trigger | Branch |
|---|---|---|
| `term_count` | "how many times", "frequency of", "count of" | Scroll over `document` records, regex page markers, count per-doc |
| `reciprocity` | "reciprocity", "moved to", "transfer license" | Multi-state search forced to include MS |
| `comparison` | "compare", "differ", "vs", 2+ state names in query | Per-state search budget, results merged by score |
| `general` | default | Single hybrid search |

### Why regex, not an LLM classifier
- An LLM classifier adds a full Bedrock round-trip before retrieval — 500–1500ms extra.
- The patterns cover >90% of actual queries observed; misclassifications fall back to `general` which still returns useful results.
- Phase 2B can swap this for a real classifier (`backend/agents/query_classifier.py` already exists as scaffolding).

### Per-state budgeting in comparison mode
Instead of one top-10 search, we run one top-k per state. Budget scales inversely:
- ≤2 states → 6 results each
- 3–4 states → 4 results each
- 5+ states → 3 results each

This guarantees every state is represented. A naive pooled search would starve smaller-corpus states, making comparisons look artificially one-sided.

## 5. Generation

`call_bedrock_llm` uses the **Bedrock Converse API** (not `invoke_model`). Rationale: model-agnostic schema — the same code swaps between Claude 3.5 Sonnet, Mistral Large, Nova, etc. without rewriting prompts or response parsing.

The prompt enforces citation discipline:
> "You MUST cite specific statutory authority for EVERY claim. Citations must include document name, section identifier, and page numbers."

`maxTokens=2048` is deliberate — API Gateway's 29s timeout is the hard ceiling on sync requests, and long generations risk hitting it. Longer answers surface the wrong tradeoff (timeout > truncation).

## 6. Async Execution — Why Not Sync?

Originally the Lambda was synchronous. We broke past API Gateway's 29s limit by moving to an async job model:

```
POST /v2/query  ──► enqueue DynamoDB job ──► self-invoke Lambda (Event) ──► return 202 {job_id}
                                                        │
GET /v2/query/status/{job_id} ◄─── poll ─── job: pending → done/failed
```

### Why
- Cross-state comparisons fan out to 7 states × top-k searches + 7 embedding calls + 1 long Mistral generation. Easily >29s.
- DynamoDB jobs table with TTL=1hr means clients can resume/reconnect; the frontend polls every 1–2s via `useChat.ts`.
- Self-invocation via `lambda_client.invoke(InvocationType='Event')` avoids spinning up Step Functions / SQS for a simple enqueue.
- `sync=true` body flag preserved for debugging and fast chat-mode queries.

## 7. Frontend

- **Two modes.** Chat (Phase 1, MS-scoped) and Research (Phase 2, multistate with filters).
- **Polling loop** in `useChat.ts` handles the 202 → poll → done lifecycle.
- **Citation formatting** (`utils/citationFormat.ts`, `inlineCitations.tsx`) turns `[1]`-style references into clickable previews that open the PDF via presigned S3 URLs (`usePDF.ts` calls the `docs_lamda.py` handler).
- **Filter panel** (state/agency chips) surfaces the Phase 2 `filters` param to the backend.

## 8. Cost Shape (approximate)

Per page processed:
- PyMuPDF: $0 (local)
- Mistral extraction (batched): ~$0.004/page
- Textract OCR (only scanned ~5%): ~$0.00008/page amortized
- Textract tables (only tables ~25%): ~$0.004/page amortized
- Titan embedding: ~$0.0001/page
- **Total: ~$0.008–$0.012 per page**

Per query:
- 2× OpenSearch (kNN + BM25): ~$0 (pay-for-instance)
- 1× Titan embed query: ~$0.0001
- 1× Bedrock generation: ~$0.005–$0.02 depending on context size

## 9. Key Design Decisions Recap

| Decision | Rationale |
|---|---|
| Dual-layer index (doc + page) | Citations need pages; term-counting needs full text |
| Two physical indexes | Prevent multistate noise in MS chat mode |
| Hybrid search (RRF) | Semantic misses statute codes; keyword misses paraphrase |
| Domain-specific BM25 boosts | `statute_codes` and `section_identifier` are high-signal |
| Mistral structured extraction | Enables typed retrieval + aggregations (fees, dates) |
| Batch LLM calls (3 pages) | Biggest cost lever; ~3x reduction |
| Skip LLM on low-value pages | ~10% of pages wasted $0.012 for no retrieval gain |
| Textract only when needed | Gated by cheap heuristic; keeps per-page cost bounded |
| Converse API | Swap Claude/Mistral/Nova without code changes |
| Async Lambda + DynamoDB | Multi-state fan-out exceeds API Gateway 29s limit |
| Regex intent detection | Sub-ms classification; LLM classifier adds a full round-trip |
| Per-state top-k budgeting | Small-corpus states would be starved otherwise |
| Resume via checkpoint file | SSO tokens expire hourly; 500+ page batches need recovery |

# Architecture

This document describes the major components of Reglex and how a query
flows through the system. For an interactive, browsable version of much
of this content, see `demos/internal-docs.html`.

## Component map

| Layer | Component | Path | Notes |
|---|---|---|---|
| UI | Vite + React app | `src/frontend/` | Renders grounding pill, inference callout, qualitative tier chips. |
| Edge | API Gateway | `infra/scripts/` | Two endpoints: `POST /v2/query`, `GET /v2/query/status/{job_id}`. |
| Compute | Async query Lambda | `src/backend/lambdas/lambda_handler.py` | Self-invokes for long jobs; tracks state in DynamoDB. |
| Compute | Docs Lambda | `src/backend/lambdas/docs_lamda.py` | Serves source-document content. |
| Orchestration | Multi-agent orchestrator | `src/backend/agents/orchestrator.py` | Routes queries to specialist agents. |
| Agents | Specialist agents | `src/backend/agents/*_agent.py` | Search, authority, comparison, fee analysis, reciprocity, term frequency, reflection. |
| Storage | OpenSearch Service | external | kNN + BM25 hybrid retrieval; two indexes (Phase 1 MS, Phase 2 multi-state). |
| Storage | DynamoDB | external | `JOBS_TABLE` for async query state. |
| Storage | S3 | external | Source documents staging bucket. |
| LLM | Amazon Bedrock | external | Claude Sonnet 4.6 (generation) + Titan embeddings. |
| OCR | Amazon Textract | external | Fallback for scanned/image-only PDFs. |

## Query lifecycle

```
1. UI POST /v2/query  → API Gateway
2. Lambda handler creates a DynamoDB job row (status: PENDING)
   and self-invokes asynchronously, returning {job_id}.
3. Background Lambda runs:
     a. query_classifier classifies the question
        (e.g. STATUTORY_LOOKUP, FEE_COMPARISON, RECIPROCITY).
     b. orchestrator dispatches one or more specialist agents.
     c. each agent issues hybrid retrieval against OpenSearch:
        kNN (Titan embedding) + BM25, fused by reciprocal rank.
     d. reflection_agent reviews the synthesised answer and adds
        [INFERENCE] tags + a grounding summary.
     e. the final answer + citations are written back to the DynamoDB row
        (status: COMPLETED).
4. UI polls GET /v2/query/status/{job_id} every ~1.5s until COMPLETED,
   then renders the answer with all trust signals.
```

## Two ingestion pipelines

Phase 1 and Phase 2 of the PoC built the OpenSearch indexes using two
different ingestion variants, both included in this repository:

- **`ingestion/lambda-pipeline/`** — the production-style pipeline used
  for the multi-state Phase 2 index. Uses a JSON _lease ledger_
  (`lease.py`) so multiple workers can claim documents without stepping
  on each other; resumable across SSO token refreshes.
- **`ingestion/sagemaker-pipeline/`** — the original notebook-driven
  pipeline used for the Phase 1 Mississippi pilot. Runs in a SageMaker
  notebook environment with parallel chunking + Bedrock-based abstract
  compression.

Both pipelines write to the same OpenSearch vector store, but use
different index schemas. The Phase 2 schema adds richer metadata (state,
agency type, document type, effective date) to support routing in the
orchestrator.

## Trust surfaces

Three explicit signals surface in the UI:

1. **Match tier** — _Strong / Moderate / Weak_ chips per cited passage,
   derived from a confidence threshold on the kNN score.
2. **Inference callout** — every `[INFERENCE]: ...` block emitted by the
   LLM is parsed (`src/frontend/src/utils/inlineCitations.tsx`) and
   surfaced as a distinct visual block.
3. **Grounding summary** — a final line emitted by the LLM
   summarising what was retrieved and what was missing; rendered as a
   pill at the top of the answer.

See `RAG_PIPELINE.md` (also reproduced in `demos/internal-docs.html`)
for the prompt engineering and retrieval scoring details.

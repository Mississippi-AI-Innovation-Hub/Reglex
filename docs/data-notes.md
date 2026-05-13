# Data Notes

> This repository does not include real data. Any included datasets are
> placeholder samples or illustrative only.

## What data the PoC uses (when populated by you)

Reglex indexes **public** regulatory documents from the Secretary of
State and related professional licensing boards of seven Southeastern
states:

| Code | State | Crawler |
|---|---|---|
| MS | Mississippi | `src/backend/crawlers/ms_sos_crawler.py` |
| TN | Tennessee | `src/backend/crawlers/tn_crawler.py` |
| GA | Georgia | `src/backend/crawlers/specialized/ga_*_crawler.py` |
| AR | Arkansas | `src/backend/crawlers/specialized/ar_*_crawler.py` |
| TX | Texas | `src/backend/crawlers/specialized/tx_*_crawler.py` |
| LA | Louisiana | `src/backend/crawlers/specialized/la_doa_crawler.py` |
| AL | Alabama | `src/backend/crawlers/specialized/al_admin_crawler.py` |

All target documents are **public records** — administrative rules,
statutes, and licensing handbooks already published by the issuing
agency.

## What is NOT in this repository

- No crawled documents (no `crawled_documents/`, no `tn_documents/`).
- No ingestion ledgers (`ingestion_ledger_*.json`,
  `ingestion_progress_*.json`).
- No evaluation results captured against real responses
  (`results.jsonl`, `*.log`).
- No screenshots of real agency records or staff PII.
- No agency contact lists, internal correspondence, or operational
  workflow data.

## Document schema (vector index)

Each document chunk is stored in OpenSearch with this shape (Phase 2
multi-state index):

```json
{
  "doc_id": "string",
  "chunk_id": "string",
  "state": "MS | TN | GA | AR | TX | LA | AL",
  "agency_type": "secretary_of_state | medical_board | real_estate | ...",
  "doc_type": "statute | administrative_rule | handbook",
  "title": "string",
  "section": "string",
  "effective_date": "YYYY-MM-DD | null",
  "text": "string (chunked passage, ~1000 tokens)",
  "embedding": "float[1024]   (Titan embed-text-v2)",
  "source_url": "string"
}
```

The Phase 1 (Mississippi-only pilot) index uses a simpler schema with
just `doc_id`, `text`, `embedding`, and `source_url`. See
`ingestion/sagemaker-pipeline/models.py` and
`ingestion/lambda-pipeline/models.py` for the full Pydantic models.

## Reproducing the data

To stand up your own copy of the index:

1. Run the crawlers in `src/backend/crawlers/` against the live source
   sites. They emit JSON manifests and PDFs into your configured S3
   bucket.
2. Run one of the ingestion pipelines
   (`ingestion/lambda-pipeline/pipeline.py` or
   `ingestion/sagemaker-pipeline/ingest_pipeline.py`) to extract,
   chunk, embed, and index the documents.

Crawl-throttling and source-agency request etiquette are baked into the
crawlers (rate limits, exponential backoff). Respect each agency's terms
of use.

## Sample / synthetic data

The directories `data/sample/` and `data/synthetic/` are reserved for
illustrative placeholders. They are intentionally empty in this initial
release. Future contributors may add small, synthetic, clearly-fake
documents here to support smoke tests, but **no real agency document
will ever ship in this repository**.

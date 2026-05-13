# Changelog

All notable changes to this Proof of Concept are recorded here.
This project follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [1.0.0] — 2026-05-13

Initial public Innovation Hub release.

### Added
- Curated, scrubbed source from the internal `Sos-Phase-1` development repository.
- `src/backend/` — multi-agent orchestrator (search, authority, comparison,
  fee analysis, reciprocity, term frequency, reflection, query classifier)
  plus state-specific crawlers (MS, TN, GA, AR, TX, LA, AL).
- `src/backend/lambdas/` — async query Lambda (`lambda_handler.py`) with
  DynamoDB job tracking and self-invocation for long-running work.
- `src/frontend/` — Vite + React research UI with grounding pills,
  inference callouts, qualitative match tiers, and a HOW_IT_WORKS panel.
- `ingestion/lambda-pipeline/` — production ingestion pipeline with a
  lease ledger for resumable crawling and re-indexing.
- `ingestion/sagemaker-pipeline/` — notebook-driven Bedrock-backed
  ingestion variant with parallel chunking and OpenSearch vector storage.
- `evaluation/` — 4-axis LLM-as-judge framework
  (Groundedness × Inference Honesty × Correctness × Jurisdiction) with a
  25-question pilot golden set and a markdown report generator.
- `infra/` — Lambda + API Gateway deploy scripts and an IAM policy
  template with placeholder identifiers.
- `demos/` — public-facing deck source, walkthrough video, one-pager,
  poster, QR codes, and an internal engineering architecture page.
- Full Innovation Hub-compliant documentation set in `docs/`.

### Pilot eval results (2026-04-20)
- Primary score (Groundedness × Inference Honesty): **0.73** / 24 of 25 questions
- Overall 4-axis mean: 0.72
- Strong patterns: `statutory_authority` (0.92), `amendment_dates` (0.83)
- Weak patterns: `fee_comparison` (0.52), `renewal_fees` (0.68)
- Per-axis weak spot: Correctness 0.56

### Security
- All real AWS account IDs, OpenSearch domain endpoints, and API Gateway
  IDs replaced with documented placeholders.
- All ingestion ledgers, run-state JSONs, and execution logs excluded.
- All `.env`-style credentials excluded; see `.env.example` for the full
  configuration surface.
- Notebook output cells stripped before publication.

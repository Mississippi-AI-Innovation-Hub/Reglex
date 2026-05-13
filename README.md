# Reglex — Mississippi Secretary of State Legal RAG

A retrieval-augmented question-answering system over state Secretary of
State regulatory documents, built as a Mississippi AI Innovation Hub
Proof of Concept.

## Overview

Reglex is a Proof of Concept built for the Mississippi Secretary of
State's office. It lets staff ask plain-English questions about state
regulations — across barbering, real estate, securities, medical and
dental licensing, and more — and get answers grounded in cited statutes
and rules from multiple states. Every claim ships with a citation, a
qualitative confidence tier, and explicit `[INFERENCE]` markers wherever
the model extrapolates beyond what the retrieved sources literally say.

This repository contains the application source, the ingestion pipelines
that built the underlying vector indexes, the evaluation framework used
to measure answer quality, and the deployment scripts used to ship the
prototype to AWS. It is published under the Innovation Hub repository
standard for completed PoC projects.

## Agency Problem

SoS staff spend significant time hunting through statutes, administrative
rules, and licensing handbooks to answer comparison-style questions —
for example, _"How does Tennessee's barber reciprocity compare to
Mississippi's?"_ or _"Which Southeastern states fund a real estate
Recovery Fund through licensee fees?"_. These questions cross document
boundaries, jurisdictions, and agency types, and the manual lookup is
slow and error-prone.

Reglex explores whether a multi-agent RAG system, grounded in a curated
index of public regulatory documents and equipped with explicit grounding
and inference signals, can shorten that workflow while keeping the
agency's _no-hallucination_ requirement front and center.

## PoC Scope and Demonstrated Capabilities

Within this prototype environment, Reglex demonstrates:

- **Multi-state grounded Q&A** over Mississippi (Phase 1 pilot) and a
  multi-state index (Phase 2 — TN, GA, AR, TX, LA, AL).
- **Multi-agent orchestration** — a query classifier routes each
  question to one or more specialist agents (search, authority,
  comparison, fee analysis, reciprocity, term frequency, reflection).
- **Hybrid retrieval** — kNN vector search + BM25 + reciprocal rank
  fusion against an Amazon OpenSearch vector store backed by Amazon
  Titan embeddings.
- **Async lambda execution** — long-running queries are tracked in a
  DynamoDB jobs table with a self-invocation pattern so the frontend can
  poll for partial and final results.
- **Trust surfaces** — qualitative match tiers (Strong / Moderate /
  Weak), an inference callout that surfaces every `[INFERENCE]` block,
  and a grounding pill summarising what was and was not retrieved.
- **Pilot evaluation** — a 25-question, 6-pattern golden set scored on
  a 4-axis rubric (Groundedness × Inference Honesty × Correctness ×
  Jurisdiction) by an LLM-as-judge with self-calibration scaffolding.

## Architecture Overview

```
                        ┌─────────────────────┐
                        │   Vite + React UI   │
                        │  (src/frontend/)    │
                        └──────────┬──────────┘
                                   │ POST /v2/query, GET /v2/query/status/:id
                                   ▼
                        ┌─────────────────────┐
                        │   API Gateway       │
                        └──────────┬──────────┘
                                   ▼
                        ┌─────────────────────┐         ┌──────────────┐
                        │  Lambda handler     │◀───────▶│  DynamoDB    │
                        │  (async, self-      │  jobs   │  jobs table  │
                        │   invoking)         │         └──────────────┘
                        └──────────┬──────────┘
                                   ▼
                        ┌─────────────────────┐
                        │ Multi-agent         │
                        │ orchestrator        │
                        │ (src/backend/agents)│
                        └──────────┬──────────┘
                                   ▼
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
    ┌──────────────┐      ┌──────────────┐      ┌──────────────────┐
    │  OpenSearch  │      │   Bedrock    │      │    Textract      │
    │ (kNN + BM25) │      │ (LLM + emb.) │      │  (OCR fallback)  │
    └──────────────┘      └──────────────┘      └──────────────────┘
            ▲
            │   indexed by
            │
    ┌─────────────────────────────────────────┐
    │  Ingestion pipelines                    │
    │  ├── ingestion/lambda-pipeline/         │  ← production, lease-ledger
    │  └── ingestion/sagemaker-pipeline/      │  ← notebook-driven, parallel
    └─────────────────────────────────────────┘
            ▲
            │   crawled by
            │
    ┌─────────────────────────────────────────┐
    │  src/backend/crawlers/                  │
    │  (MS, TN, GA, AR, TX, LA, AL)           │
    └─────────────────────────────────────────┘
```

See `docs/architecture.md` for a deeper walkthrough and the full
component map. A standalone, browsable engineering reference is also
available at `demos/internal-docs.html`.

## Repository Structure

```
Reglex/
├── README.md                ← this file
├── LICENSE                  ← MIT (Innovation Hub default)
├── CHANGELOG.md
├── .env.example
├── .gitignore
├── docs/                    ← Innovation Hub required documentation
│   ├── architecture.md
│   ├── setup.md
│   ├── data-notes.md
│   ├── testing.md
│   ├── limitations.md
│   ├── security-notes.md
│   └── images/
├── src/
│   ├── backend/             ← agents, crawlers, async lambda handlers
│   │   ├── agents/
│   │   ├── crawlers/
│   │   └── lambdas/
│   └── frontend/            ← Vite + React + Tailwind research UI
├── ingestion/
│   ├── lambda-pipeline/     ← production ingestion (resumable, lease-ledger)
│   └── sagemaker-pipeline/  ← notebook-driven parallel ingestion variant
├── evaluation/              ← 4-axis judge, golden set, runner, reports
├── infra/
│   ├── scripts/             ← deploy.sh, add_status_endpoint.sh, build.sh
│   └── iam/                 ← iam_policy.json (placeholders)
├── demos/
│   ├── deck/                ← Next.js pitch deck source
│   ├── walkthrough/         ← Demo.mp4 + landing page
│   ├── onepager/            ← one-pager (HTML + PDF)
│   ├── poster/              ← printable poster
│   ├── qr/                  ← QR codes for the demo URL
│   ├── screenshots/
│   ├── sample-prompts/
│   ├── internal-docs.html   ← browsable internal architecture reference
│   └── reglex-sos-demo.html
├── data/
│   ├── sample/              ← placeholder — no real agency data ships
│   └── synthetic/
└── tests/
```

## Setup

Full instructions in `docs/setup.md`. The short version:

```bash
# 1. Clone and create a Python environment for backend + ingestion
git clone <this-repo>
cd Reglex
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # see docs/setup.md for the file list

# 2. Configure environment
cp .env.example .env
# edit .env with your AWS account, OpenSearch endpoint, etc.

# 3. Frontend
cd src/frontend
npm install
npm run dev

# 4. (Optional) Deploy the lambda to your own AWS account
cd ../../infra/scripts
./deploy.sh
```

**Prerequisites:** Python 3.11+, Node 20+, an AWS account with access to
Amazon Bedrock (Claude Sonnet 4.6 + Titan embeddings), OpenSearch
Service, Lambda, DynamoDB, S3, and Textract.

## Configuration

All configuration is environment-variable driven. The full surface is
documented in `.env.example` and `docs/setup.md`. No credentials are
ever committed to this repository.

## Data Notes

> This repository does not include real data. Any included datasets are
> placeholder samples or illustrative only.

The PoC operates on **public** Secretary of State documents (statutes,
administrative rules, and licensing handbooks) from Mississippi,
Tennessee, Georgia, Arkansas, Texas, Louisiana, and Alabama. None of
those documents are bundled in this repository — they are crawled from
their source agencies at ingestion time using the crawlers in
`src/backend/crawlers/`. See `docs/data-notes.md` for the full data
schema, source list, and crawl methodology.

## Usage

Sample prompts and example queries live in `demos/sample-prompts/`. A
short walkthrough video is in `demos/walkthrough/Demo.mp4`, and a
browsable one-pager is in `demos/onepager/reglex-onepager.html`.

A typical session:

1. User submits a question through the React UI.
2. The query Lambda enqueues a job in DynamoDB, self-invokes
   asynchronously, and returns a `job_id`.
3. The orchestrator classifies the query, dispatches one or more
   specialist agents, runs hybrid retrieval, and synthesises a
   grounded answer with `[INFERENCE]` markers and a grounding summary.
4. The frontend polls `GET /v2/query/status/{job_id}` and renders the
   answer with trust signals (match tier chips, inference callouts,
   citation cards).

## Testing and Evaluation

The PoC was validated against a 25-question, 6-pattern pilot golden set
scored on a 4-axis LLM-as-judge rubric. See `docs/testing.md` and
`evaluation/report_v1.md` for the full results.

**Headline (2026-04-20):**

| Axis | Score |
|---|---|
| Groundedness × Inference Honesty (primary) | **0.73** |
| Overall (4-axis mean) | 0.72 |
| Groundedness | 0.66 |
| Inference Honesty | 0.80 |
| Correctness | 0.56 |
| Jurisdiction | 0.88 |

The strongest pattern was `statutory_authority` (0.92); the weakest was
`fee_comparison` (0.52). Open evaluation gaps and known failure modes
are documented in `docs/limitations.md`.

## Limitations

> This PoC was developed within a limited timeline and controlled
> environment. It may contain simplified workflows, mock integrations,
> limited testing coverage, and prototype user interfaces.

Key limitations specific to Reglex are detailed in `docs/limitations.md`.
Headlines:

- Correctness on fee-comparison queries is currently below acceptable
  for production use.
- The pilot golden set is small (25 questions); broader coverage is
  needed before any production decision.
- The retrieval index covers seven Southeastern states only.
- No automated regression suite covers the frontend yet; UI behaviour is
  exercised manually.

## Disclaimer

This repository contains code and supporting materials developed as part
of a Mississippi Artificial Intelligence Innovation Hub Proof of Concept
project. The contents are provided for prototype demonstration purposes.
They are not production ready by default and may include simplified
workflows, incomplete security guardrails, placeholder integrations, or
reduced controls appropriate only for a Proof-of-Concept environment.

**Do not use this code with production data or in production
environments without additional architecture, security, privacy,
testing, and stakeholder review.**

## License

MIT License — see [`LICENSE`](LICENSE). Confirm compatibility with
third-party dependencies before redistributing.

## Contributors

Mississippi AI Innovation Hub PoC team, 2026.
See `git log` for full commit attribution.

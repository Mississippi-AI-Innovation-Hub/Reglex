# Setup

This document covers local development, ingestion, and AWS deployment
for Reglex. The project is **sandbox-only** — it cannot be reproduced
end-to-end without an AWS account that has Bedrock model access enabled.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | Backend, ingestion, eval. |
| Node.js | 20+ | Frontend (Vite + React). |
| AWS CLI | v2 | SSO-friendly; the ingestion pipeline assumes SSO refresh. |
| AWS account | — | With access to Bedrock (Claude Sonnet 4.6 + Titan embeddings v2), OpenSearch Service, Lambda, DynamoDB, S3, API Gateway, and Textract. |
| OpenSearch | 2.x | One vector-search-enabled domain. |

## 1. Clone and configure

```bash
git clone <this-repo>
cd Reglex
cp .env.example .env
# Edit .env — fill in AWS_REGION, OPENSEARCH_ENDPOINT, JOBS_TABLE,
# S3_BUCKET, BEDROCK_LLM_MODEL, BEDROCK_EMBEDDING_MODEL, API_ID, etc.
```

## 2. Python backend + ingestion

```bash
python3 -m venv .venv
source .venv/bin/activate
# Required packages (combined from all three Python entry points):
pip install \
    boto3 \
    botocore \
    opensearch-py \
    requests \
    beautifulsoup4 \
    pypdf \
    pdfplumber \
    python-dotenv \
    pydantic
```

> A pinned `requirements.txt` is not bundled with this PoC repository.
> The list above reflects the libraries actually imported across
> `src/backend/`, `ingestion/lambda-pipeline/`, and
> `ingestion/sagemaker-pipeline/`. Pin versions when you set up your
> own environment.

## 3. Frontend

```bash
cd src/frontend
npm install
npm run dev   # http://localhost:5173
```

The frontend expects `VITE_API_ENDPOINT` in its environment. For local
dev against your deployed API, create `src/frontend/.env.local`:

```
VITE_API_ENDPOINT=https://<your-api-id>.execute-api.us-east-1.amazonaws.com/prod
```

## 4. Run ingestion

Two pipelines are included; choose one depending on your environment.

### 4a. Lambda-style ingestion (recommended for production-like runs)

```bash
cd ingestion/lambda-pipeline
AWS_PROFILE=<your-profile> python pipeline.py \
    --s3-bucket <your-bucket> \
    --s3-prefix source-documents \
    --index-name <your-index>
```

- Uses `lease.py` to claim work units; safe to run multiple workers.
- Resumable: SSO token refresh and retry-on-throttle are built in.

### 4b. Notebook-driven ingestion (Phase 1 pilot path)

```bash
cd ingestion/sagemaker-pipeline
jupyter notebook run_ingestion.ipynb
# Set the env-var cell, then run all cells.
```

## 5. Deploy the Lambda

```bash
cd infra/scripts
# Review deploy.sh — it references resource names ms-sos-legal-v2,
# ms-sos-query-jobs, etc. Rename to match your environment.
./deploy.sh
./add_status_endpoint.sh
```

The IAM policy template is in `infra/iam/iam_policy.json` — replace
`123456789012` with your AWS account ID and adjust resource names to
match.

## 6. Run evaluations

```bash
cd evaluation
python run_eval.py --golden golden_v1.json --endpoint <your-api-url>
python -c "import judge; print(judge.summarize('results.jsonl'))"
```

See `evaluation/README.md` for the full eval workflow and rubric
definitions.

## Known setup limitations

- **Bedrock model access** is region-gated and requires per-model
  approval through the AWS Bedrock console. Without Claude Sonnet 4.6
  and Titan Embeddings v2 enabled in your region, neither the
  orchestrator nor ingestion will work.
- **OpenSearch vector engine** must be enabled at domain creation; you
  cannot retrofit kNN onto an existing classic-search index.
- **SSO sessions** for the ingestion pipeline expire roughly every hour;
  the pipeline auto-detects and refreshes, but you must have a valid
  SSO session open in your AWS CLI before starting.
- **No data is bundled.** You must point the crawlers at your own
  source-document set before ingestion produces a usable index.

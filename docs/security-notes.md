# Security Notes

These notes summarise the security posture of the published Reglex
repository and the guardrails that should be added before any
production-style deployment.

## What is sanitised in this published repository

The following have been removed or replaced with documented placeholders
before publication:

| Item | Treatment |
|---|---|
| AWS account ID | Replaced with `123456789012` in all scripts and IAM policy. |
| Real OpenSearch domain endpoints | Replaced with `search-<your-domain>.<region>.es.amazonaws.com` placeholders. |
| Real API Gateway IDs | Replaced with `<API_ID>` placeholders. |
| Ingestion ledgers / progress files | Excluded from the repository (see `.gitignore`). |
| `.env` / credential files | Excluded — only `.env.example` with placeholder values ships. |
| Notebook output cells | Stripped before publication so that no captured response payloads leak. |
| Run logs | Excluded (`*.log`, `results.jsonl`, `ingestion_monitor.log`). |

## What is intentionally retained

AWS resource _names_ (such as `ms-sos-legal-v2`, `ms-sos-query-jobs`,
and `ms-sos-legal-documents`) are kept as informative defaults. These
are not credentials; they describe what to call your own resources and
make the deployment scripts self-documenting. You should rename them
to match your environment.

## Recommended pre-production hardening

If a downstream team picks up Reglex for production, they should:

1. **Add authentication to the API Gateway** (API key, IAM auth, or
   Cognito). The PoC sandbox endpoint had none.
2. **Add rate limiting** on the API Gateway (usage plans) and on the
   Lambda (reserved concurrency). The Bedrock spend ceiling is the
   highest-impact uncapped failure mode.
3. **Tighten Textract IAM permissions** from `Resource: "*"` to
   specific bucket prefixes.
4. **Add a secrets-rotation runbook** for any API keys introduced.
5. **Enable AWS CloudTrail, OpenSearch audit logs, and Lambda
   structured logging** so that misuse and degradation are observable.
6. **Add a content review step** before serving regulatory answers to
   non-staff users — even with high inference-honesty scores, a
   policy/legal review is required.
7. **Rotate any AWS account that was used during the PoC** — pre-public
   commit history may reference resource names that, combined with
   external knowledge, could leak operational context.

## How to report a vulnerability

This is a Mississippi AI Innovation Hub PoC repository. For security
concerns, contact the Innovation Hub team — do **not** file a public
GitHub issue.

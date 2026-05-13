# Limitations

> This PoC was developed within a limited timeline and controlled
> environment. It may contain simplified workflows, mock integrations,
> limited testing coverage, and prototype user interfaces.

The following limitations apply specifically to Reglex and should be
weighed before any production decision.

## Answer-quality limitations

- **Correctness on fee comparisons is weak** (0.52 on the pilot eval).
  The system frequently retrieves the right statutes but either skips
  the comparative arithmetic or omits one side of the comparison.
- **Inference labelling is good but imperfect** (0.80). The model
  sometimes presents an extrapolation as a grounded claim without a
  `[INFERENCE]` tag. The grounding summary helps catch this in review,
  but it is not a hard guarantee.
- **The pilot golden set is small** (25 questions across 6 patterns).
  Performance on out-of-pattern questions is unknown.
- **Citations are passage-level, not span-level.** The UI surfaces the
  retrieved chunk; finding the exact sentence inside it is left to the
  reader.

## Coverage limitations

- **Seven Southeastern states only** (MS, TN, GA, AR, TX, LA, AL).
  Other jurisdictions are out of scope.
- **No live-update mechanism.** When source agencies amend rules, the
  index goes stale until you re-run the relevant crawler and ingestion
  pipeline.
- **Scanned-image PDFs** rely on Amazon Textract OCR as a fallback;
  recognition errors on heavily-formatted historical documents are
  possible.

## Technical / architectural limitations

- **Single-region.** All AWS resources (OpenSearch, Lambda, DynamoDB)
  are provisioned in `us-east-1`. No cross-region failover.
- **Async query response time** depends on Bedrock latency for both
  embeddings and generation. Median ~6–12 seconds for a typical query.
- **No streaming response.** The frontend polls a job-status endpoint;
  it does not consume server-sent events.
- **The two ingestion pipelines diverged** during development. They
  index to OpenSearch with similar but not identical schemas. A future
  cleanup should consolidate them.
- **No automated regression suite for the frontend.** Visual regressions
  are caught manually by exercising the UI before each deploy.

## Security limitations

- **IAM policy is least-privilege but not least-resource.** Textract
  permissions are scoped to `Resource: "*"` — acceptable for a PoC but
  should be tightened before production.
- **No authentication on the API Gateway** for the PoC sandbox endpoint.
  Production deployment would need API keys, IAM auth, or Cognito.
- **No rate limiting** beyond Lambda's reserved concurrency. Public
  exposure without rate limiting could lead to Bedrock spend abuse.

## What remains out of scope

- Productionising the system — auth, rate limiting, multi-region,
  observability dashboards, audit logging, retention policy, and the
  legal/policy review for serving regulatory information at scale.
- Onboarding new states beyond the current seven.
- Custom UI for non-staff users (citizen-facing search).
- Integration with the SoS office's existing case-management or content
  systems.

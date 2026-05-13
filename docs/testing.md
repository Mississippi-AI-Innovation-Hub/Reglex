# Testing and Evaluation

Reglex was validated through three independent practices:

1. **Manual QA** of the UI and end-to-end query path against the
   deployed sandbox lambda.
2. **A pilot evaluation suite** — a 25-question, 6-pattern golden set
   scored on a 4-axis LLM-as-judge rubric.
3. **Spot-checks** of individual agents during development.

## The pilot evaluation suite

Location: `evaluation/`

| File | Purpose |
|---|---|
| `golden_v1.json` | 25 AI-curated questions across 6 patterns (Colby legal-question taxonomy). |
| `judge.py` | 4-axis LLM-as-judge with self-calibration scaffolding. |
| `run_eval.py` | Pilot eval runner. POSTs each golden question to the deployed lambda, captures the system answer, and scores it. |
| `report_v1.md` | Generated markdown report (v1, captured 2026-04-20). |
| `curation_notes.md` | Notes on how the golden set was assembled. |
| `test_judge.py` | Unit-style tests for the judge prompts and scoring. |

### Patterns covered

| Pattern | What it tests |
|---|---|
| `statutory_authority` | "Which statute authorises X?" |
| `amendment_dates` | "When was rule X last amended?" |
| `testing_requirements` | "What testing requirements apply to a Y license?" |
| `reciprocity` | "How does state A's reciprocity for occupation Z compare with state B's?" |
| `renewal_fees` | "What is the renewal fee and timeline for license type W?" |
| `fee_comparison` | Cross-state fee comparison questions. |

### Rubric (4 axes, each scored 0–1)

| Axis | Definition |
|---|---|
| **Groundedness** | Every factual claim is cited; citations point at real retrieved passages. |
| **Inference Honesty** | Every extrapolation beyond the cited text is tagged `[INFERENCE]`; a `Grounding summary:` line is present. |
| **Correctness** | The answer addresses the substantive legal point correctly. |
| **Jurisdiction** | The right statutes / rules from the right states are cited. |

The **primary score** reported is _Groundedness × Inference Honesty_,
because for this PoC the agency's no-hallucination requirement matters
more than raw correctness — a wrong-but-honest answer is operationally
recoverable; a confidently-hallucinated one is not.

## Headline pilot results (v1, 2026-04-20)

| Axis | Score |
|---|---|
| Groundedness × Inference Honesty (primary) | **0.73** (24 of 25 questions) |
| Overall (4-axis mean) | 0.72 |
| Groundedness | 0.66 |
| Inference Honesty | 0.80 |
| Correctness | 0.56 |
| Jurisdiction | 0.88 |

### Per-pattern breakdown

| Pattern | Mean overall |
|---|---|
| `statutory_authority` | 0.92 |
| `amendment_dates` | 0.83 |
| `testing_requirements` | 0.82 |
| `reciprocity` | 0.74 |
| `renewal_fees` | 0.68 |
| `fee_comparison` | 0.52 |

### Worst patterns

- `fee_comparison` — the system either fails to retrieve the relevant
  fee schedules from both states or cites them but skips the comparative
  arithmetic. Worth investigating an agent specialised for numeric
  cross-tabulation.
- `renewal_fees` — partial extractions; the system sometimes returns
  the fee amount without the timeline, or vice versa.

## How to run the eval against your own deployment

```bash
cd evaluation
python run_eval.py \
    --golden golden_v1.json \
    --endpoint https://<your-api>.execute-api.<region>.amazonaws.com/prod/v2/query \
    --out results.jsonl
python -c "from judge import report; report('results.jsonl', 'report_v2.md')"
```

`results.jsonl` is git-ignored on purpose — every run produces a new
report. Re-run after each prompt or retrieval change to compare deltas.

## Manual UI QA checklist

- [ ] Submit a known-good `statutory_authority` question → expect a
      Strong-tier citation chip and no `[INFERENCE]` blocks.
- [ ] Submit a known-weak `fee_comparison` question → expect at least
      one `[INFERENCE]` block and a grounding summary that admits the
      gap.
- [ ] Submit an out-of-scope question (e.g., "What's the weather?") →
      expect the system to decline rather than confabulate.
- [ ] Refresh mid-poll → expect the UI to recover the job from
      `?job_id=...` in the URL.

## What is not tested

- No automated frontend regression suite.
- No load testing; concurrency limits are governed by Lambda + DynamoDB
  defaults.
- No security testing beyond the standard IAM-least-privilege review
  performed during deployment.

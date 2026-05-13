# Pilot Eval (v1)

AI-curated 25-question pilot evaluation set for the SoS Phase 1 PoC.

**Curation date:** 2026-04-20
**Curator:** Bibas (no Colby review yet — Phase 2)
**Source policy:** state SoS sites, state legislature portals, Justia codes, official board pages only.

## How to re-run

```bash
cd /Users/bibas/Work/Sos-Phase-1
python3 evals/run_eval.py
# → writes evals/results.jsonl + evals/report_v1.md
```

## File layout

- `golden_v1.json` — frozen 25-question test set (DO NOT REGENERATE; copy + bump version if changes needed)
- `judge.py` — 4-axis LLM-as-judge
- `run_eval.py` — orchestrator + report aggregator
- `report_v1.md` — auto-generated output
- `curation_notes.md` — provenance audit trail
- `test_judge.py` — unit test for judge

## Pattern coverage (target distribution)

| Pattern (Colby use case #) | Target N |
|---|---|
| Reciprocity (#3)              | 6 |
| Renewal fees (#4)             | 5 |
| Cross-state fee comparison (#5) | 5 |
| Amendment dates (#6)          | 4 |
| Statutory authority (#7)      | 3 |
| Testing requirements (#10)    | 2 |
| **Total**                     | **25** |

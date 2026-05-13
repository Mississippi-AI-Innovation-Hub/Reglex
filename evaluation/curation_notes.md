# Curation Notes — Pilot Golden Set v1

**Curator:** Bibas (AI-curated, no Colby legal review)
**Date:** 2026-04-20
**Output:** `evals/golden_v1.json` (25 questions)

## Methodology

1. Explored the live OpenSearch corpus (`ms-phase1-legal`, `multistate-phase2-legal`)
   via two probe scripts (`_explore_corpus.py`, `_explore2.py`) to discover what
   regulatory topics are actually covered and what the canonical filenames are.
2. For each of the 6 Colby-workable patterns, drafted candidate questions
   anchored on documents I had already confirmed exist in the corpus.
3. For each candidate, performed a targeted web search restricted to the
   allowlisted source domains (state SoS sites, state legislature portals,
   Justia codes, official board pages — never blogs, avvo, legalzoom).
4. For each question, the ideal_answer cites the rule/statute and includes
   the verified source URL. No fabricated URLs.
5. Verified with `_verify_golden.py` that every `expected_doc_filename_substring`
   resolves to ≥1 hit in the appropriate OpenSearch index. **25/25 verified.**

## Pattern distribution (final, matches target)

| Pattern               | Target | Final |
|-----------------------|--------|-------|
| reciprocity           | 6      | 6     |
| renewal_fees          | 5      | 5     |
| fee_comparison        | 5      | 5     |
| amendment_dates       | 4      | 4     |
| statutory_authority   | 3      | 3     |
| testing_requirements  | 2      | 2     |
| **Total**             | **25** | **25** |

## State coverage (incidental, not balanced by design)

- MS: 8 questions (q-004, q-007, q-015, q-016, q-021, q-023, q-025, plus implicit overlap)
- TN: 6 (q-001, q-008, q-012, q-013, q-014, q-017, q-022)
- AL: 4 (q-002, q-003, q-011, q-020)
- AR: 3 (q-009, q-010, q-019)
- GA: 2 (q-005, q-024)
- TX: 2 (q-006, q-018)
- LA: 0 (LA appears in retrieval results but no LA-specific question survived
  curation; Phase 2 should add ≥2 LA questions)

## AWS verification — STATUS: PERFORMED (not deferred)

`aws --profile <your-aws-profile> sts get-caller-identity` succeeded at curation time, so
all 25 questions were verified live against OpenSearch via `_verify_golden.py`.
Every `expected_doc_filename_substring` produced ≥1 hit in either
`ms-phase1-legal` or `multistate-phase2-legal` filtered by `expected_state`.
Hit counts ranged 2–161; lowest were q-006 (TX, sub="103.3", 2 hits) and
q-023 (MS, sub="00000375c", 2 MS2 hits + 2 MS1 hits) — both adequate but worth
re-checking after any re-ingest.

## Dropped candidates / known limitations

The following candidates were drafted but DROPPED because they would have
manufactured failures the system can't legitimately answer:

1. **"What is the Mississippi LLC formation filing fee?"** — DROPPED.
   The corpus does not include the Mississippi Business Corporation Act fee
   schedule (Title 79 statutes); only secondary references in administrative
   rules surfaced. Phase 2: ingest `https://www.sos.ms.gov/business-services/general-information`
   fee table.

2. **"What is the Mississippi notary application fee?"** — DROPPED as a
   standalone fee question (kept the bond/structure aspect in q-015 as a
   comparison). The $25 application fee is documented at sos.ms.gov but
   the ingested PDF (`00000172c.pdf`) covers Rule 2.4 bond/oath process,
   not the fee schedule itself. The fee answer would have to come from the
   SoS web page, which is not in the index.

3. **"What is the Mississippi athlete agent registration fee?"** — DROPPED.
   Athlete-agent search produced only secondary references (broker-dealer
   registration in 00000179c.pdf), no dedicated athlete-agent rule page.
   This is a known Phase 2 ingestion gap; flagged for Colby use case #5
   completeness.

4. **"What is the trademark registration fee in Mississippi?"** — DROPPED.
   Same gap — trademark search returned tangential results (securities,
   permits, agriculture). Phase 2 should ingest the SoS trademark registration
   instructions/fee schedule.

5. **"How does Texas dental faculty licensure compare to Tennessee dental
   faculty licensure?"** — DROPPED. While both states have rules (`§117.1.pdf`
   for TX, `0460-` series for TN), the comparison would require fee tables
   from each that aren't in cleanly comparable form. Replaced with broader
   real-estate fee comparisons (q-012, q-014).

6. **"What is the Alabama physician reciprocity statute?"** — DROPPED. The
   relevant statute (Code of Ala. § 34-24-507) was repealed in 2022 by
   Act 2022-302. The corpus may still reference the old section. To avoid
   asking a question whose ideal_answer is "this is repealed; use IMLC instead,"
   we kept the AL reciprocity question on the dental side (q-003, § 34-9-10,
   still in force).

7. **Statute-only questions** (e.g., "What does Miss. Code Ann. § 73-43-13
   say about board composition?") — DROPPED categorically. The corpus is
   admin rules, not statutes themselves. Per Bibas's project memory
   (`project_phase2_use_cases.md`), statute-only questions are blocked
   Phase 2 work and would manufacture failures.

## Confidence-of-corpus-match notes

Two questions had lower hit counts and may need spot-checking:

- **q-006** (TX, "103.3"): only 2 multistate hits. The exact rule § 103.3
  on dental hygiene licensure by credentials is in the corpus (`§103.3.pdf`,
  `§103.4.pdf`); 2 hits is correct because each is a single-page record.
- **q-023** (MS, "00000375c"): 2 hits in each index. The MS Real Estate
  Commission rule on the Commission's composition is on a single page;
  2 page-records and 2 document-records = 4 total is consistent with a
  short-rule document.

## Recommended Phase 2 expansion

1. Add LA-specific questions (corpus has 524 LA records; we have 0 LA questions).
2. Add 5+ business-services questions (LLC, corp, trademark, charitable,
   athlete agent) — requires re-crawling SoS business pages, not just rules.
3. Wire `ingestion/aws_session.py` SSO refresh into a scheduled re-verify
   so curation_notes.md can be auto-stamped with last-verified date.
4. Have Colby spot-review 5 questions before any external publication.
   Particularly review q-007 ($25 figure depends on which version of
   Regulation 13 was ingested) and q-008 ($90/$75 figures depend on TN
   1260-01 revision currently in corpus).

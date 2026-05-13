# Pilot Eval Report v1

_Generated: 2026-04-20T00:48:39_

## Headline

- **Primary score (Groundedness x Inference Honesty):** **0.73** across 24 of 25 questions
- **Overall (4-axis mean):** 0.72
- **Failed runs:** 1

## Per-axis

| Axis | Score |
|---|---|
| Groundedness        | 0.66 |
| Inference Honesty   | 0.80 |
| Correctness         | 0.56 |
| Jurisdiction        | 0.88 |

## Per-pattern

| Pattern | Mean Overall |
|---|---|
| statutory_authority | 0.92 |
| amendment_dates | 0.83 |
| testing_requirements | 0.82 |
| reciprocity | 0.74 |
| renewal_fees | 0.68 |
| fee_comparison | 0.52 |

## Worst 5 questions

### q-010 (renewal_fees) - overall 0.00

**Q:** What is the renewal fee and timeline for an Arkansas educational academic license issued to a physician?

- Groundedness: 0.0 - _The SYSTEM_ANSWER is incomplete and does not provide any citations or factual claims that can be evaluated for groundedness._
- Inference Honesty: 0.0 - _The SYSTEM_ANSWER is incomplete and does not contain any content, hence there are no inferences to evaluate or 'Grounding summary:' line present._
- Correctness: 0.0 - _The SYSTEM_ANSWER is incomplete and does not provide any information to compare against the IDEAL_ANSWER._
- Jurisdiction: 0.0 - _The SYSTEM_ANSWER is incomplete and does not provide any citations or information regarding jurisdiction._

### q-014 (fee_comparison) - overall 0.00

**Q:** Among the states that fund a real estate Recovery Fund through licensee fees, what fees do Alabama and Tennessee assess?

- Groundedness: 0.0 - _The SYSTEM_ANSWER does not provide any citations to real sources that would contain the claims made about Alabama and Tennessee's Recovery Fund fees._
- Inference Honesty: 0.0 - _The SYSTEM_ANSWER does not contain any [INFERENCE]: tags to mark extrapolations and does not include a 'Grounding summary:' line. All content is presented as fact without proper grounding._
- Correctness: 0.0 - _The SYSTEM_ANSWER does not provide any information about the fees assessed by Alabama and Tennessee, thus it does not match the IDEAL_ANSWER on the substantive legal point._
- Jurisdiction: 0.0 - _The SYSTEM_ANSWER does not cite any statutes or rules from Alabama or Tennessee, thus it fails to meet the jurisdiction requirement._

### q-016 (fee_comparison) - overall 0.38

**Q:** How does the Mississippi securities registration fee structure compare with Arkansas's real estate timeshare registration fee structure?

- Groundedness: 0.5 - _The SYSTEM_ANSWER provides citations for some factual claims, particularly regarding procedural requirements and exemptions. However, it fails to cite specific fee structures for either Mississippi or Arkansas, which are central to the question._
- Inference Honesty: 0.5 - _The SYSTEM_ANSWER correctly marks some inferred content with [INFERENCE] tags, but it also presents some extrapolations as if they were grounded in the provided context. Additionally, the 'Grounding summary:' line is present but could be more detailed._
- Correctness: 0.0 - _The SYSTEM_ANSWER does not correctly address the substantive legal point. It focuses on timeshare registration requirements rather than securities registration fees in Mississippi and real estate timeshare registration fees in Arkansas, as required by the question._
- Jurisdiction: 0.5 - _The SYSTEM_ANSWER correctly identifies the relevant commissions in Mississippi and Arkansas but fails to cite the specific statutes or rules (e.g., Mississippi Securities Act Rule 4.03 and Arkansas Real Estate Commission Rule 13.1) that would provide the necessary fee structures._

### q-004 (reciprocity) - overall 0.50

**Q:** What does Mississippi require of a non-resident real estate broker applicant from a state without a reciprocity agreement?

- Groundedness: 0.5 - _The SYSTEM_ANSWER contains several grounded claims with citations, such as the general licensing requirements and cooperation rules for nonresident brokers. However, it also includes ungrounded assertions, particularly regarding the inferred requirements for non-resident brokers from non-reciprocal states._
- Inference Honesty: 0.5 - _The SYSTEM_ANSWER correctly marks some inferred content with [INFERENCE]: tags, but it presents other extrapolations as if they were grounded in the sources. Additionally, the 'Grounding summary:' line is present but could be more detailed._
- Correctness: 0.0 - _The SYSTEM_ANSWER does not match the IDEAL_ANSWER on the substantive legal point. It fails to accurately describe the specific requirements for non-resident real estate broker applicants from states without a reciprocity agreement as outlined in the Mississippi Real Estate Commission rules._
- Jurisdiction: 1.0 - _All cited statutes and rules appear to be from Mississippi, aligning with the jurisdiction of the question._

### q-015 (fee_comparison) - overall 0.50

**Q:** Compare Mississippi's notary commission cost components (application fee plus bond) with Alabama's real estate Recovery Fund fee structure.

- Groundedness: 0.5 - _Half of the claims are properly cited (Alabama exemption rule and Mississippi real estate licensing fees), but the core information about Mississippi's notary commission costs and Alabama's Recovery Fund fee structure is not cited._
- Inference Honesty: 1.0 - _All inferred content is correctly marked with [INFERENCE]: tags, and the 'Grounding summary:' line is present._
- Correctness: 0.0 - _The SYSTEM_ANSWER does not provide the correct information about the notary commission cost components in Mississippi or the Recovery Fund fee structure in Alabama as per the IDEAL_ANSWER._
- Jurisdiction: 0.5 - _The cited statutes and rules are partially relevant but do not cover the notary and Recovery Fund fee structures as required by the question._

## Limitations

- N=25, AI-curated golden set, no counsel review (Phase 2: 80-question Colby-validated set)
- Light self-calibration (5 hand-graded), no full LLM-vs-human alignment study
- Single run, no variance analysis
- Inference marking is self-reported by the model (Phase 2: post-hoc verification via reflection_agent.py)

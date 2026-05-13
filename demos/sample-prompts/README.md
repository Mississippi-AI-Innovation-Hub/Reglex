# Sample Prompts

These prompts exercise each of the six question patterns covered by the
pilot golden set. Use them to do a quick manual sanity check after any
prompt or retrieval change.

## Statutory authority
- _What Mississippi statute authorises the SoS to issue notary commissions?_
- _Which Tennessee rule governs the renewal of a real estate broker's license?_

## Amendment dates
- _When was Arkansas's barbering reciprocity rule last amended?_
- _When did Georgia adopt its current securities registration rule?_

## Testing requirements
- _What testing requirements apply to a Louisiana cosmetologist licence?_
- _What examination must a Texas notary public pass before commissioning?_

## Reciprocity
- _How does Tennessee's barber reciprocity compare to Mississippi's?_
- _Which Southeastern states grant a real-estate licence by endorsement?_

## Renewal fees
- _What is the renewal fee and timeline for an Arkansas educational academic license issued to a physician?_
- _What is the renewal cycle for an Alabama administrative licence?_

## Fee comparison
- _Among the states that fund a real estate Recovery Fund through licensee fees, what fees do Alabama and Tennessee assess?_
- _How does the Mississippi securities registration fee structure compare with Arkansas's real estate timeshare registration fee structure?_

## Expected behaviour

Every answer should:

1. Cite at least one source per substantive claim.
2. Tag every extrapolation with `[INFERENCE]: ...`.
3. End with a `Grounding summary:` line describing what was retrieved
   and what was missing.

If any of those is missing, the prompt or the orchestrator's reflection
step has regressed.

# medivation Agent Verification

## Run Metadata

- Slug: medivation
- Target: MEDIVATION INC
- Acquirer: PFIZER INC
- Run ID: ab03f0bae9b940df9a57cfc09461043c
- Model: gpt-5.5
- Reasoning effort: high
- Audit path: output/audit/medivation/runs/ab03f0bae9b940df9a57cfc09461043c
- Filing source: EX-99.(A)(1)(A) d249052dex99a1a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/78003/000119312516696889/d249052dex99a1a.htm
- Verification generated: 2026-05-05T20:22:37.376789Z

## Commands

- set -a; [ -f .env ] && source .env; set +a; python -m pipeline.run_pool --filter reference --workers 4 --re-validate
- python scoring/diff.py --slug medivation
- python scripts/check_reference_verification.py --slugs medivation
- python -m pipeline.reconcile --scope reference

## Extraction And Flag Summary

- Status: passed_clean
- Hard flags: 0
- Soft flags: 0
- Info flags: 0
- Current review flags: 0
- Actors: 11
- Events/review rows: 13 / 13
- Participation counts: 0
- Actor relations: 7
- Estimation bidder rows: 2
- Exact quote audit: 24 graph evidence spans and 13 review-row quotes checked against Filing page text; failures=0

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Comparator status | Filing page evidence was reviewed directly because `scoring/diff.py` still targets the retired row-event surface and matched 0 current AI rows for this deal. | Alex is calibration material, not ground truth; no deal-specific Alex/reference JSON update is required for this verification. |
| Current output shape | Filing page quotes bind every current review row and graph evidence span exactly; quote audit failures=0. | Verified against SEC filing text under `deal_graph_v1`. |
| Alex-only legacy rows | Old comparator reported Alex-only rows=19, deal-level disagreements=5. | Not treated as blockers because the comparator does not project `deal_graph_v1`; current filing-cited review and estimator rows are the live authority. |

## Filing Evidence Review

The reviewer checked the live Background-section projection against `data/filings/medivation/pages.json`. Every `source_quote` listed below is an exact substring of the cited Filing page. Estimator rows are accepted only through source-backed boundary events.

### Estimation Rows

| Actor | bI | bI_lo | bI_hi | bF | admitted | T | Unit | Boundary | Filing event date |
|---|---:|---:|---:|---:|---|---|---|---|---|
| Pfizer | 65 | 65 | 65 | 81.5 | True | financial | per_share | final_round_bid | 2016-08-20 |
| Sanofi | 52.5 | 52.5 | 52.5 |  | False | unknown | per_share | first_round_bid | 2016-04-13 |

### Review Row Evidence

| Filing page | Date | Event subtype | Actor | Value | Quote excerpt |
|---|---|---|---|---:|---|
| Filing page 27 | 2016-08-20 | merger_agreement_executed |  |   | Pfizer, Purchaser and Medivation each executed the Merger Agreement on the afternoon of Saturday, August 20, 2016 |
| Filing page 26 | 2016-08-08 | first_round_bid | Pfizer |   | On August 8, 2016, Pfizer submitted a non-binding preliminary proposal to Medivation (the “August 8 Proposal”) |
| Filing page 27 | 2016-08-19 | first_round_bid | Pfizer | 77 per_share | On August 19, 2016, Pfizer submitted a revised written proposal to acquire Medivation for cash consideration of $77.00 per Share |
| Filing page 25 | 2016-04-20 | contact_initial | Pfizer |   | On April 20, 2016, Douglas Giordano, Senior Vice President, Worldwide Business Development at Pfizer, attempted to contact Dr. Hung by phone and by email to propose a discussion |
| Filing page 24 | 2016-04-13 | first_round_bid | Sanofi | 52.5 per_share | a letter dated April 13, 2016 from the Chief Executive Officer of Sanofi, setting forth a non-binding proposal to acquire Medivation for $52.50 per share |
| Filing page 26 | 2016-08-10 | advancement_admitted | Pfizer |   | On August 10, 2016, Medivation notified Pfizer that it was inviting Pfizer to a subsequent round of the potential sale process |
| Filing page 25 | 2016-04-29 | excluded_by_target | Sanofi |   | Sanofi’s proposal was publicly announced on April 28, 2016 and unanimously rejected by Medivation’s Board of Directors on April 29, 2016 |
| Filing page 25 | 2016-06-29 | nda_signed | Pfizer |   | On June 29, 2016, Pfizer executed a confidentiality and standstill agreement with Medivation, and Medivation invited Pfizer to participate in a potential sale process |
| Filing page 25 |  | nda_signed | Sanofi |   | Medivation issued a press release announcing that it had entered into confidentiality agreements with several parties, including Sanofi |
| Filing page 26 | 2016-08-08 | first_round_bid | Pfizer | 65 per_share | On August 8, 2016, Pfizer submitted a non-binding preliminary proposal to Medivation (the “August 8 Proposal”), subject to, among other conditions, satisfactory completion of Pfizer’s due diligence, to acquire Medivation for cash consideration of $65.00 per Sh... |
| Filing page 27 | 2016-08-20 | final_round_bid | Pfizer |   | Pfizer communicated a “best and final” proposal to acquire Medivation for cash consideration of $81.50 per Share on August 20, 2016 |
| Filing page 26 | 2016-08-10 | advancement_admitted | several other interested parties |   | inviting Pfizer to a subsequent round of the potential sale process, together with several other interested parties |
| Filing page 27 | 2016-08-20 | final_round_bid | Pfizer | 81.5 per_share | Pfizer communicated a “best and final” proposal to acquire Medivation for cash consideration of $81.50 per Share on August 20, 2016 |

## Contract Updates

No deal-specific prompt, rulebook, reference JSON, fallback, or compatibility update was required for this verification. The verification pass did apply the current systematic estimator projection rule to cached audit-v3 raw responses before reports were written.

## Conclusion

Conclusion: VERIFIED

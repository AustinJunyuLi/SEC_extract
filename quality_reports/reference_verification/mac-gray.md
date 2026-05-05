# mac-gray Agent Verification

## Run Metadata

- Slug: mac-gray
- Target: MAC GRAY CORP
- Acquirer: CSC SERVICEWORKS, INC.
- Run ID: f3ce50a9c1e944bcaba88c388777c492
- Model: gpt-5.5
- Reasoning effort: high
- Audit path: output/audit/mac-gray/runs/f3ce50a9c1e944bcaba88c388777c492
- Filing source: DEFM14A a2217482zdefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/1038280/000104746913010973/a2217482zdefm14a.htm
- Verification generated: 2026-05-05T20:22:37.592363Z

## Commands

- set -a; [ -f .env ] && source .env; set +a; python -m pipeline.run_pool --filter reference --workers 4 --re-validate
- python scoring/diff.py --slug mac-gray
- python scripts/check_reference_verification.py --slugs mac-gray
- python -m pipeline.reconcile --scope reference

## Extraction And Flag Summary

- Status: passed_clean
- Hard flags: 0
- Soft flags: 0
- Info flags: 0
- Current review flags: 0
- Actors: 20
- Events/review rows: 24 / 24
- Participation counts: 6
- Actor relations: 9
- Estimation bidder rows: 4
- Exact quote audit: 52 graph evidence spans and 27 review-row quotes checked against Filing page text; failures=0

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Comparator status | Filing page evidence was reviewed directly because `scoring/diff.py` still targets the retired row-event surface and matched 0 current AI rows for this deal. | Alex is calibration material, not ground truth; no deal-specific Alex/reference JSON update is required for this verification. |
| Current output shape | Filing page quotes bind every current review row and graph evidence span exactly; quote audit failures=0. | Verified against SEC filing text under `deal_graph_v1`. |
| Alex-only legacy rows | Old comparator reported Alex-only rows=35, deal-level disagreements=5. | Not treated as blockers because the comparator does not project `deal_graph_v1`; current filing-cited review and estimator rows are the live authority. |

## Filing Evidence Review

The reviewer checked the live Background-section projection against `data/filings/mac-gray/pages.json`. Every `source_quote` listed below is an exact substring of the cited Filing page. Estimator rows are accepted only through source-backed boundary events.

### Estimation Rows

| Actor | bI | bI_lo | bI_hi | bF | admitted | T | Unit | Boundary | Filing event date |
|---|---:|---:|---:|---:|---|---|---|---|---|
| CSC/Pamplona | 18.5 | 18.5 | 18.5 | 21.25 | True | strategic | per_share | final_round_bid | 2013-09-21 |
| Party A |  | 17 | 19 |  | True | unknown | per_share | final_round_bid | 2013-09-18 |
| Party B |  | 17 | 18 | 21.5 | True | unknown | per_share | final_round_bid | 2013-09-18 |
| Party C |  | 15 | 17 |  | False | unknown | per_share | first_round_bid | 2013-09-10 |

### Review Row Evidence

| Filing page | Date | Event subtype | Actor | Value | Quote excerpt |
|---|---|---|---|---:|---|
| Filing page 47 | 2013-10-14 | merger_agreement_executed |  |   | Later in the day, on October 14, 2013, the merger agreement was executed |
| Filing page 38 | 2013-06-28 | nda_signed | Party B |   | Later on June 28, 2013, Party B, entered into a confidentiality and standstill agreement with Mac-Gray |
| Filing page 42 | 2013-09-18 | final_round_bid | Party A | 18-19 per_share | Party A reiterated in a telephone call to a representative of BofA Merrill Lynch that its previous indication of interest with an all-cash purchase price of $18.00 to $19.00 per share was its best and final offer |
| Filing page 36 | 2013-06-21 | first_round_bid | Party A | 17-19 per_share | On June 21, 2013, Party A submitted an unsolicited proposal to the Mac-Gray Board of Directors offering to purchase Mac-Gray for an all-cash purchase price of $17.00 to $19.00 per share |
| Filing page 42 | 2013-09-18 | final_round_bid | Party B | 21.5 per_share | On September 18, 2013, Party B also submitted a revised indication of interest with a purchase price that Party B valued at $21.50 per share, including $19.00 of cash to be paid at closing and the remaining per share price to be paid in the form of options to ... |
| Filing page 41 | 2013-09-10 | first_round_bid | Party A | 18-19 per_share | On September 10, 2013, Party A submitted a revised indication of interest with an all-cash purchase price of $18.00 to $19.00 per share |
| Filing page 41 | 2013-09-09 | first_round_bid | Party B | 18.5 per_share | On September 9, 2013, Party B also submitted a revised indication of interest with an all-cash purchase price of $18.50 per share |
| Filing page 44 | 2013-09-24 | exclusivity_grant | CSC/Pamplona |   | On September 24, 2013, CSC, Pamplona and Mac-Gray executed the exclusivity agreement providing for exclusive negotiations until 5 p.m. ET on October 12, 2013 |
| Filing page 39 | 2013-07-23 | first_round_bid | CSC/Pamplona | 18.5 per_share | On July 23, 2013, CSC/Pamplona submitted a preliminary indication of interest at an all-cash purchase price of $18.50 per share. |
| Filing page 47, 47 | 2013-10-14 | financing_committed | Pamplona |   | the Pamplona capital commitment letter \| the Pamplona commitment letter was delivered |
| Filing page 41 | 2013-09-09 | first_round_bid | CSC/Pamplona | 19.5 per_share | On September 9, 2013, CSC/Pamplona submitted a revised indication of interest with an all-cash purchase price of $19.50 per share |
| Filing page 40 | 2013-08-05 | nda_signed | Party A |   | On August 5, 2013, Party A entered into a confidentiality and standstill agreement with Mac-Gray |
| Filing page 39 | 2013-07-24 | first_round_bid | Party B | 17-18 per_share | On July 24, 2013, Party B submitted a preliminary indication of interest at an all-cash purchase price of $17.00 to $18.00 per share. |
| Filing page 47 | 2013-10-12 | exclusivity_grant | CSC/Pamplona |   | On October 12, 2013, CSC, Pamplona and Mac-Gray executed a letter agreement extending exclusivity until 11:59 p.m. ET on October 15, 2013. |
| Filing page 33 | 2013-04-08 | contact_initial | Party A |   | On April 8, 2013, representatives of BofA Merrill Lynch, as instructed by the Board, telephoned a representative of Party A to discuss generally a possible business combination between Party A and Mac-Gray. |
| Filing page 41 | 2013-09-10 | first_round_bid | Party C | 16-17 per_share | a representative of Party C indicated that it was submitting a revised oral indication of interest with an all-cash purchase price of $16.00 to $17.00 per share |
| Filing page 42 | 2013-09-18 | non_responsive | Party C |   | Party C did not submit a revised indication of interest or reiterate its prior indication of interest of an all-cash purchase price of $16.00 to $17.00 per share nor did it specify any reasons in connection therewith. |
| Filing page 40 | 2013-07-25 | first_round_bid | Party C | 16-16.5 per_share | Later on July 25, 2013, Party C submitted a written indication of interest at an all-cash purchase price of $16.00 to $16.50 per share. |
| Filing page 42 | 2013-09-18 | final_round_bid | CSC/Pamplona | 20.75 per_share | On September 18, 2013, CSC/Pamplona submitted a proposal for an all-cash purchase price of $20.75 per share |
| Filing page 39 | 2013-07-11 | nda_signed | CSC/Pamplona |   | On July 11, 2013, CSC/Pamplona entered into a confidentiality and standstill agreement with Mac-Gray |
| Filing page 39 | 2013-07-24 | first_round_bid | Party C | 15-17 per_share | Also on July 24, 2013, representatives from Party C called BofA Merrill Lynch and presented an oral preliminary indication of interest at an all-cash purchase price of $15.00 to $17.00 per share. |
| Filing page 39, 40, 40 | 2013-07-25 | advancement_admitted | Party A, Party B, Party C and CSC/Pamplona |   | BofA Merrill Lynch recommended that management meetings be arranged between members of Mac-Gray management (other than Mr. MacDonald) and each of Party A (if Party A \| agreed to enter into a confidentiality agreement), Party B, Party C and CSC/Pamplona to prov... |
| Filing page 43 | 2013-09-21 | final_round_bid | CSC/Pamplona | 21.25 per_share | CSC/Pamplona were willing to increase their all-cash purchase price to $21.25 per share as a last and best offer |
| Filing page 38 | 2013-06-30 | nda_signed | Party C |   | On June 30, 2013, Party C entered into a confidentiality and standstill agreement with Mac-Gray |

## Contract Updates

No deal-specific prompt, rulebook, reference JSON, fallback, or compatibility update was required for this verification. The verification pass did apply the current systematic estimator projection rule to cached audit-v3 raw responses before reports were written.

## Conclusion

Conclusion: VERIFIED

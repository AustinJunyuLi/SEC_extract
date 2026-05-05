# providence-worcester Agent Verification

## Run Metadata

- Slug: providence-worcester
- Target: PROVIDENCE & WORCESTER RR CO
- Acquirer: GENESEE & WYOMING INC
- Run ID: b440f13bb26c4940820d221d9aad0e83
- Model: gpt-5.5
- Reasoning effort: high
- Audit path: output/audit/providence-worcester/runs/b440f13bb26c4940820d221d9aad0e83
- Filing source: DEFM14A d224035ddefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/831968/000119312516713780/d224035ddefm14a.htm
- Verification generated: 2026-05-05T20:22:37.318047Z

## Commands

- set -a; [ -f .env ] && source .env; set +a; python -m pipeline.run_pool --filter reference --workers 4 --re-validate
- python scoring/diff.py --slug providence-worcester
- python scripts/check_reference_verification.py --slugs providence-worcester
- python -m pipeline.reconcile --scope reference

## Extraction And Flag Summary

- Status: passed_clean
- Hard flags: 0
- Soft flags: 0
- Info flags: 0
- Current review flags: 0
- Actors: 25
- Events/review rows: 29 / 29
- Participation counts: 6
- Actor relations: 6
- Estimation bidder rows: 6
- Exact quote audit: 48 graph evidence spans and 30 review-row quotes checked against Filing page text; failures=0

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Comparator status | Filing page evidence was reviewed directly because `scoring/diff.py` still targets the retired row-event surface and matched 0 current AI rows for this deal. | Alex is calibration material, not ground truth; no deal-specific Alex/reference JSON update is required for this verification. |
| Current output shape | Filing page quotes bind every current review row and graph evidence span exactly; quote audit failures=0. | Verified against SEC filing text under `deal_graph_v1`. |
| Alex-only legacy rows | Old comparator reported Alex-only rows=36, deal-level disagreements=5. | Not treated as blockers because the comparator does not project `deal_graph_v1`; current filing-cited review and estimator rows are the live authority. |

## Filing Evidence Review

The reviewer checked the live Background-section projection against `data/filings/providence-worcester/pages.json`. Every `source_quote` listed below is an exact substring of the cited Filing page. Estimator rows are accepted only through source-backed boundary events.

### Estimation Rows

| Actor | bI | bI_lo | bI_hi | bF | admitted | T | Unit | Boundary | Filing event date |
|---|---:|---:|---:|---:|---|---|---|---|---|
| G&W | 21.15 | 21.15 | 21.15 | 25 | True | unknown | per_share | first_round_bid | 2016-08-12 |
| Party B | 24 | 24 | 24 |  | False | unknown | per_share | first_round_bid |  |
| Party C | 19.3 | 19.3 | 19.3 |  | False | unknown | per_share | first_round_bid | 2016-07-12 |
| Party D | 21 | 21 | 21 |  | False | unknown | per_share | first_round_bid | 2016-08-01 |
| Party E | 21.26 | 21.26 | 21.26 |  | False | financial | per_share | first_round_bid | 2016-08-01 |
| Party F | 19.2 | 19.2 | 19.2 |  | False | financial | per_share | first_round_bid |  |

### Review Row Evidence

| Filing page | Date | Event subtype | Actor | Value | Quote excerpt |
|---|---|---|---|---:|---|
| Filing page 37 |  | first_round_bid | Party D | 21 per_share | • Party D (a financial buyer) submitted an LOI to acquire the Company for a price of $21.00 per share (subject to a four-week diligence period). |
| Filing page 36 |  | nda_signed | Party C |   | After executing a confidentiality agreement, Party C was provided the memorandum concerning the Company provided to the other potential buyers. |
| Filing page 36 | 2016-07-12 | ioi_submitted | Party C |   | On July 12, 2016, Party C submitted an IOI with an offer price per share of $21.00 (implying an equity value of $108 million). |
| Filing page 36 |  | advancement_admitted | remaining seven potential buyers |   | The Transaction Committee authorized representatives of GHF to schedule in-person management presentations with the remaining seven potential buyers and allow these parties to conduct additional due diligence. |
| Filing page 37 | 2016-08-02 | withdrawn_by_bidder | Party E |   | Party E withdrew its revised proposal on August 2, 2016 (but confirmed its original proposal of $21.26 per share) |
| Filing page 36 | 2016-07-21 | first_round_bid | G&W | 21.15 per_share | • G&W submitted an LOI on July 21, 2016 to acquire the Company for a price of $21.15 per share (subject to a three-week exclusive diligence period). The price included $20.02 cash at closing and $1.13 in the form of a contingent value right, the value of which... |
| Filing page 36 | 2016-07-26 | first_round_bid | G&W | 22.15 per_share | On July 26, 2016, in response to feedback from representatives of GHF indicating its price and CVR structure were not competitive, G&W submitted a revised LOI, which increased its offer to $22.15 per share (including $21.02 in cash and $1.13 CVR). |
| Filing page 36 |  | excluded_by_target | two low bidders |   | the Transaction Committee concluded that the two low bidders should be excluded from that process. |
| Filing page 35 |  | contact_initial | G&W |   | Between April 3, 2016 and April 6, 2016, representatives of GHF and members of the Company’s management held a series of introductory meetings with five potential strategic buyers (including G&W) at the American Short Line and Regional Railroad Association’s 2... |
| Filing page 37 |  | advancement_admitted | G&W and Party B |   | The Transaction Committee concluded that the Company should proceed with confirmatory due diligence and negotiations with G&W and Party B because of the higher offers made by each of G&W and Party B relative to the other potential buyers. |
| Filing page 35 | 2016-04-21 | contact_initial | Party B |   | Subsequently, on April 21, 2016, the Company and representatives of GHF held an introductory meeting with another potential strategic buyer (“Party B”). |
| Filing page 37 | 2016-08-01 | first_round_bid | Party E | 23.81 per_share | On August 1, 2016, Party D submitted a revised LOI at a price of $24.00 per share and Party E submitted a revised LOI, along with financing support, from Party F, at a price of $23.81 per share. |
| Filing page 37 | 2016-08-01 | financing_committed | Party E |   | On August 1, 2016, Party D submitted a revised LOI at a price of $24.00 per share and Party E submitted a revised LOI, along with financing support, from Party F, at a price of $23.81 per share. |
| Filing page 36 |  | ioi_submitted | potential buyers |   | Between May 19, 2016 and June 1, 2016, the Company received nine written indications of interest (“IOIs”) from potential buyers, with offer prices per share ranging from $17.93 to $26.50 (assuming the conversion of preferred stock into common stock), implying ... |
| Filing page 39 |  | merger_agreement_executed | G&W |   | Shortly thereafter, Hinckley Allen and Simpson Thacher finalized the transaction documents and the Company and G&W executed the merger agreement, and the Company, G&W and the Eder Trusts executed the voting agreement. |
| Filing page 37 |  | first_round_bid | Party E | 21.26 per_share | • Party E (a strategic buyer) submitted an LOI to acquire the Company for a price of $21.26 per share (subject to a 60-day exclusivity period for due diligence and negotiation of definitive documentation). |
| Filing page 36 | 2016-07-12 | first_round_bid | Party C | 21 per_share | On July 12, 2016, Party C submitted an IOI with an offer price per share of $21.00 (implying an equity value of $108 million). |
| Filing page 35 |  | nda_signed | potential strategic buyers and 14 potential financial buyers |   | Each of the potential strategic buyers and 14 potential financial buyers subsequently executed confidentiality agreements. |
| Filing page 36 |  | final_round_bid | LOI bidders |   | In late July 2016, the Company received six LOIs with offer prices per share ranging from $19.20 to $24.00 (implying equity values of $96 million to $121 million). |
| Filing page 38 | 2016-08-12 | first_round_bid | G&W | 25 per_share | On the morning of August 12, 2016, following a discussion between representatives of BMO and G&W in which G&W indicated it would be submitting a revised LOI, G&W submitted a revised LOI to acquire the Company for a price of $25.00 per share in cash, which excl... |
| Filing page 37 |  | excluded_by_target | remaining bidders |   | At the direction of the Transaction Committee, representatives of GHF subsequently contacted the remaining bidders to inform them that they were no longer involved in the process. |
| Filing page 35 |  | contact_initial | potential strategic buyers and potential financial buyers |   | During the week of March 28, 2016, in accordance with the Transaction Committee’s directives, representatives of GHF contacted 11 potential strategic buyers (including Party A) and 18 potential financial buyers. |
| Filing page 37 |  | non_responsive | one strategic buyer and one financial buyer |   | One strategic buyer and one financial buyer elected not to submit an LOI. |
| Filing page 34, 34 |  | contact_initial | Party A |   | In the fourth quarter of 2015, Robert H. Eder (the Company’s Chairman and Chief Executive Officer) and Frank K. Rogers (the Company’s Vice President and Chief Commercial Officer) met with one of the Company’s Class I rail partners (“Party A”) to discuss joint ... |
| Filing page 37 |  | first_round_bid | Party C | 19.3 per_share | • Party C submitted an LOI to acquire the Company for a price of $19.30 per share (subject to a 30-day diligence period). |
| Filing page 37 |  | first_round_bid | Party F | 19.2 per_share | • Party F (a strategic buyer) submitted an LOI to acquire the Company for a price of $19.20 per share (subject to a 30-day due diligence period). |
| Filing page 37 |  | withdrawn_by_bidder | Party D |   | at which point Party D indicated that it would not proceed with further due diligence at that time. |
| Filing page 36 |  | first_round_bid | Party B | 24 per_share | • Party B submitted an LOI to acquire the Company for a price of $24.00 per share (subject to an expedited diligence review). |
| Filing page 37 | 2016-08-01 | first_round_bid | Party D | 24 per_share | On August 1, 2016, Party D submitted a revised LOI at a price of $24.00 per share and Party E submitted a revised LOI, along with financing support, from Party F, at a price of $23.81 per share. |

## Contract Updates

No deal-specific prompt, rulebook, reference JSON, fallback, or compatibility update was required for this verification. The verification pass did apply the current systematic estimator projection rule to cached audit-v3 raw responses before reports were written.

## Conclusion

Conclusion: VERIFIED

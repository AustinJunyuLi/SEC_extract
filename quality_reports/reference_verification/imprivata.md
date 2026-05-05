# imprivata Agent Verification

## Run Metadata

- Slug: imprivata
- Target: IMPRIVATA INC
- Acquirer: THOMA BRAVO, LLC
- Run ID: 741356dc053e43769cae5091cea9159e
- Model: gpt-5.5
- Reasoning effort: high
- Audit path: output/audit/imprivata/runs/741356dc053e43769cae5091cea9159e
- Filing source: DEFM14A d226798ddefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/1328015/000119312516677939/d226798ddefm14a.htm
- Verification generated: 2026-05-05T20:22:37.425867Z

## Commands

- set -a; [ -f .env ] && source .env; set +a; python -m pipeline.run_pool --filter reference --workers 4 --re-validate
- python scoring/diff.py --slug imprivata
- python scripts/check_reference_verification.py --slugs imprivata
- python -m pipeline.reconcile --scope reference

## Extraction And Flag Summary

- Status: passed_clean
- Hard flags: 0
- Soft flags: 0
- Info flags: 0
- Current review flags: 0
- Actors: 16
- Events/review rows: 21 / 21
- Participation counts: 7
- Actor relations: 6
- Estimation bidder rows: 3
- Exact quote audit: 46 graph evidence spans and 29 review-row quotes checked against Filing page text; failures=0

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Comparator status | Filing page evidence was reviewed directly because `scoring/diff.py` still targets the retired row-event surface and matched 0 current AI rows for this deal. | Alex is calibration material, not ground truth; no deal-specific Alex/reference JSON update is required for this verification. |
| Current output shape | Filing page quotes bind every current review row and graph evidence span exactly; quote audit failures=0. | Verified against SEC filing text under `deal_graph_v1`. |
| Alex-only legacy rows | Old comparator reported Alex-only rows=29, deal-level disagreements=5. | Not treated as blockers because the comparator does not project `deal_graph_v1`; current filing-cited review and estimator rows are the live authority. |

## Filing Evidence Review

The reviewer checked the live Background-section projection against `data/filings/imprivata/pages.json`. Every `source_quote` listed below is an exact substring of the cited Filing page. Estimator rows are accepted only through source-backed boundary events.

### Estimation Rows

| Actor | bI | bI_lo | bI_hi | bF | admitted | T | Unit | Boundary | Filing event date |
|---|---:|---:|---:|---:|---|---|---|---|---|
| Sponsor A | 16.5 | 16.5 | 16.5 |  | False | unknown | per_share | first_round_bid | 2016-06-09 |
| Sponsor B |  | 17 | 18 |  | False | unknown | per_share | first_round_bid | 2016-06-09 |
| Thoma Bravo | 15 | 15 | 15 | 19.25 | True | financial | per_share | final_round_bid | 2016-07-09 |

### Review Row Evidence

| Filing page | Date | Event subtype | Actor | Value | Quote excerpt |
|---|---|---|---|---:|---|
| Filing page 36, 36 | 2016-07-08 | final_round_bid | Thoma Bravo | 19 per_share | On July 8, 2016, the date by which Sponsor B and Thoma Bravo had been invited to submit their final bids, only Thoma Bravo submitted a bid for the Company. \| Thoma Bravo’s bid was at a price of $19.00 per share in cash |
| Filing page 33 | 2016-06-09 | non_responsive | Strategic 3 |   | while Strategic 3 had executed a confidentiality agreement and met with management, it did not submit a bid by the June 9, 2016 deadline |
| Filing page 31 |  | contact_initial | Barclays |   | During the period from May 6 through June 9, 2016, at the direction of the Board, Barclays contacted and had discussions with the 15 potentially interested parties discussed by the Board at its April 28 and May 5, 2016 meetings, including Thoma Bravo. |
| Filing page 37, 38 | 2016-07-09 | final_round_bid | Thoma Bravo | 19.25 per_share | Later on July 9, 2016, Barclays received a revised written, non-binding proposal from Thoma Bravo setting forth its best and final offer of $19.25 per share \| Barclays reviewed its financial analyses of the $19.25 per share cash consideration with the Special ... |
| Filing page 36 | 2016-07-08 | non_responsive | Sponsor B |   | On July 8, 2016, the date by which Sponsor B and Thoma Bravo had been invited to submit their final bids, only Thoma Bravo submitted a bid for the Company. |
| Filing page 33 | 2016-06-12 | advancement_admitted |  |   | the Board authorized Barclays to advance all three parties to the second phase of the strategic process |
| Filing page 32, 32 | 2016-06-09 | first_round_bid | Thoma Bravo | 17.25 per_share | On June 9, 2016, three parties (Sponsor A, Sponsor B and Thoma Bravo) presented written preliminary non-binding indications of interest \| Thoma Bravo indicated a price of $17.25 per share, and also provided a form of equity commitment letter and draft merger a... |
| Filing page 33 | 2016-06-14 | withdrawn_by_bidder | Strategic 3 |   | On June 14, 2016, Strategic 3 informed representatives of Barclays that because of its internal focus on other corporate transactions and a perceived overlap in technologies, it was no longer interested in exploring a potential transaction with the Company. |
| Filing page 36 | 2016-07-08 | financing_committed | Thoma Bravo |   | Thoma Bravo’s bid was at a price of $19.00 per share in cash, provided for an equity commitment for the entire purchase price |
| Filing page 35 | 2016-06-24 | advancement_admitted |  |   | Barclays sent final bid process letters to Sponsor B and Thoma Bravo, requesting marked drafts of the Company’s proposed form of merger agreement (which would be provided in due course) by July 7, 2016, and setting a final bid deadline of July 8, 2016. |
| Filing page 34 | 2016-06-23 | withdrawn_by_bidder | Strategic 4 |   | On June 23, 2016, Strategic 4 informed Barclays that an acquisition of the Company would not be a strategic fit for it and that it was not interested in participating in the strategic process. |
| Filing page 31 | 2016-05-10 | nda_signed | Thoma Bravo |   | Of the parties contacted, three strategic parties and four financial sponsors executed confidentiality agreements with the Company, including Thoma Bravo on May 10, 2016. |
| Filing page 28, 28 |  | contact_initial | Thoma Bravo |   | In early 2015, and again in June 2015, representatives of Thoma Bravo informally approached and had brief meetings with representatives of the Company, and expressed Thoma Bravo’s potential interest in exploring a possible business transaction with the Company... |
| Filing page 33, 33 | 2016-06-15 | withdrawn_by_bidder | Sponsor A |   | On June 15, 2016, Sponsor A informed Barclays that in light of its view of the Company after its diligence, if it were to submit a second round bid, it would not be meaningfully higher than the price indicated in its June 9, 2016 preliminary indication of inte... |
| Filing page 39, 39 | 2016-07-13 | merger_agreement_executed | Thoma Bravo |   | On July 13, 2016, before the stock market opened, the parties finalized and executed the merger agreement and received executed final copies of the equity commitment letter and the voting agreements. \| Later on July 13, 2016, before the stock market opened, th... |
| Filing page 32 | 2016-06-08 | withdrawn_by_bidder | Strategic 1 |   | On June 8, 2016, Strategic 1 informed Barclays that after further internal consideration, an acquisition of the Company would not be a strategic fit for it, and therefore it was no longer interested in participating in the strategic process and would not be su... |
| Filing page 29 | 2016-03-09 | first_round_bid | Thoma Bravo | 15 per_share | On March 9, 2016, Thoma Bravo sent an unsolicited, non-binding indication of interest letter addressed to the Board indicating that Thoma Bravo would be interested in acquiring the Company for cash at a purchase price of $15.00 per share of Imprivata’s common ... |
| Filing page 32, 32 | 2016-06-09 | first_round_bid | Sponsor A | 16.5 per_share | On June 9, 2016, three parties (Sponsor A, Sponsor B and Thoma Bravo) presented written preliminary non-binding indications of interest \| Sponsor A indicated a price of $16.50 per share. |
| Filing page 34 | 2016-06-17 | contact_initial | Strategic 4 |   | On June 17, 2016, representatives of Barclays contacted representatives of Strategic 4 to inquire whether it would be interested in participating in the Company’s strategic process. |
| Filing page 32, 32 | 2016-06-09 | first_round_bid | Sponsor B | 17-18 per_share | On June 9, 2016, three parties (Sponsor A, Sponsor B and Thoma Bravo) presented written preliminary non-binding indications of interest \| Sponsor B indicated a range of $17.00 - $18.00 per share. |
| Filing page 32 | 2016-06-12 | withdrawn_by_bidder | Strategic 2 |   | On June 12, 2016, Strategic 2 informed representatives of Barclays that because of other internal corporate priorities, it was no longer interested in exploring a potential transaction with the Company. |

## Contract Updates

No deal-specific prompt, rulebook, reference JSON, fallback, or compatibility update was required for this verification. The verification pass did apply the current systematic estimator projection rule to cached audit-v3 raw responses before reports were written.

## Conclusion

Conclusion: VERIFIED

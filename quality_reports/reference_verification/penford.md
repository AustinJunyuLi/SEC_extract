# penford Agent Verification

## Run Metadata

- Slug: penford
- Target: PENFORD CORP
- Acquirer: INGREDION INC
- Run ID: e4b9b005833043848deb4a6bceb08238
- Model: gpt-5.5
- Reasoning effort: high
- Audit path: output/audit/penford/runs/e4b9b005833043848deb4a6bceb08238
- Filing source: DEFM14A d834783ddefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/739608/000119312514455030/d834783ddefm14a.htm
- Verification generated: 2026-05-05T20:22:37.551239Z

## Commands

- set -a; [ -f .env ] && source .env; set +a; python -m pipeline.run_pool --filter reference --workers 4 --re-validate
- python scoring/diff.py --slug penford
- python scripts/check_reference_verification.py --slugs penford
- python -m pipeline.reconcile --scope reference

## Extraction And Flag Summary

- Status: passed_clean
- Hard flags: 0
- Soft flags: 0
- Info flags: 0
- Current review flags: 0
- Actors: 18
- Events/review rows: 26 / 26
- Participation counts: 4
- Actor relations: 6
- Estimation bidder rows: 2
- Exact quote audit: 46 graph evidence spans and 29 review-row quotes checked against Filing page text; failures=0

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Comparator status | Filing page evidence was reviewed directly because `scoring/diff.py` still targets the retired row-event surface and matched 0 current AI rows for this deal. | Alex is calibration material, not ground truth; no deal-specific Alex/reference JSON update is required for this verification. |
| Current output shape | Filing page quotes bind every current review row and graph evidence span exactly; quote audit failures=0. | Verified against SEC filing text under `deal_graph_v1`. |
| Alex-only legacy rows | Old comparator reported Alex-only rows=25, deal-level disagreements=5. | Not treated as blockers because the comparator does not project `deal_graph_v1`; current filing-cited review and estimator rows are the live authority. |

## Filing Evidence Review

The reviewer checked the live Background-section projection against `data/filings/penford/pages.json`. Every `source_quote` listed below is an exact substring of the cited Filing page. Estimator rows are accepted only through source-backed boundary events.

### Estimation Rows

| Actor | bI | bI_lo | bI_hi | bF | admitted | T | Unit | Boundary | Filing event date |
|---|---:|---:|---:|---:|---|---|---|---|---|
| Ingredion | 17 | 17 | 17 | 19 | True | financial | per_share | final_round_bid | 2014-10-14 |
| Party A |  | 16 | 18 | 16 | True | unknown | per_share | final_round_bid | 2014-10-14 |

### Review Row Evidence

| Filing page | Date | Event subtype | Actor | Value | Quote excerpt |
|---|---|---|---|---:|---|
| Filing page 31 | 2014-08-10 | ioi_submitted | Ingredion |   | On August 10, 2014, Penford received a letter from Mr. Fortnum, confirming Ingredion’s interest in a possible business combination between Ingredion and the Company, citing certain strategic reasons for the proposed acquisition, and providing an indicative val... |
| Filing page 36 | 2014-10-02 | first_round_bid | Ingredion | 19 per_share | On October 2, 2014, Penford received a letter from Ingredion regarding its indication of interest and increasing the proposed price to $19.00 per share of outstanding Penford capital stock on a fully diluted basis. |
| Filing page 35 | 2014-09-23 | nda_signed | Party D |   | On September 23, 2014, Penford and Party D executed a nondisclosure and standstill agreement, which included standard confidentiality restrictions and a standstill provision that automatically expired upon the public announcement of the entering into a definit... |
| Filing page 39 | 2014-10-14 | merger_agreement_executed | Ingredion |   | During the evening on October 14, 2014, Penford and Ingredion finalized and executed the merger agreement, and Penford, Ingredion and SEACOR executed the voting and support agreement. |
| Filing page 35 | 2014-09-17 | first_round_bid | Ingredion | 18.25-18.5 per_share | On September 17, 2014, Mr. Fortnum contacted Mr. Malkoski to update him on Ingredion’s board meeting that was held on September 16, 2014, reporting that Ingredion’s board had discussed Ingredion’s strategy, including the proposed acquisition of Penford. Mr. Fo... |
| Filing page 34 | 2014-09-15 | nda_signed | Party C |   | On September 15, 2014, Penford and Party C executed a nondisclosure and standstill agreement, which included standard confidentiality restrictions and a standstill provision that automatically expired upon the public announcement of the entering into a definit... |
| Filing page 34 |  | contact_initial | six potential strategic counterparties |   | Throughout early- to mid-September, in accordance with the board’s authorization, Deutsche Bank contacted six potential strategic counterparties in the same or similar industries to gauge initial interest regarding a potential transaction with Penford. |
| Filing page 32 | 2014-08-11 | contact_initial | Party A |   | Also on August 11, 2014, Mr. Malkoski met with the Chief Executive Officer of Party A. Mr. Malkoski and Party A’s Chief Executive Officer briefly discussed the recent SEACOR Filing. Party A’s Chief Executive Officer also informally discussed Party A’s potentia... |
| Filing page 38 | 2014-10-14 | final_round_bid | Party A | 16 per_share | Later on October 14, 2014, Party A provided a formal letter with its indication of interest with respect to an acquisition of the Company at a price of $16.00 per share, citing increased volatility in the markets as the reason for the decrease in the offer pri... |
| Filing page 34 |  | non_responsive | Party E |   | Also on September 12, 2014, Deutsche Bank left a voicemail for another strategic counterparty (referred to as Party E) regarding a potential transaction. In the following two weeks, Deutsche Bank also left several other voicemails for Party E regarding a poten... |
| Filing page 31 | 2014-08-10 | first_round_bid | Ingredion | 18 per_share | On August 10, 2014, Penford received a letter from Mr. Fortnum, confirming Ingredion’s interest in a possible business combination between Ingredion and the Company, citing certain strategic reasons for the proposed acquisition, and providing an indicative val... |
| Filing page 33 | 2014-08-21 | nda_signed | Ingredion |   | On August 21, 2014, Ingredion and Penford executed a nondisclosure and standstill agreement that superseded the prior Secrecy Agreement. |
| Filing page 38, 38 | 2014-10-14 | final_round_bid | Ingredion | 19 per_share | On October 14, 2014, Mr. Fortnum called Mr. Malkoski to confirm the proposed price of $19.00 and discuss finalizing the draft merger agreement and proceeding with the transaction as previously planned. \| Ingredion had confirmed that it desired to promptly ente... |
| Filing page 32 | 2014-08-12 | withdrawn_by_bidder | SEACOR |   | On August 12, 2014, Mr. Hatfield discussed the Ingredion indication of interest with Mr. Behrens to determine if SEACOR was interested in acquiring the Company. Mr. Behrens stated that SEACOR was not interested in participating in any potential sale process at... |
| Filing page 37 | 2014-10-08 | withdrawn_by_bidder | Party D |   | Also on October 8, 2014, Deutsche Bank met with representatives from Party D, who indicated that it did not intend to move forward with discussions regarding a potential transaction involving the Company. |
| Filing page 29, 29 |  | ioi_submitted | two parties engaged in the Company’s industry |   | In 2007 and 2009, the Company received unsolicited indications of interest to acquire Penford from two parties engaged in the Company’s industry. \| These discussions did not result in offers to acquire the Company. |
| Filing page 36 | 2014-10-02 | first_round_bid | Ingredion | 18.5 per_share | On October 2, 2014, Mr. Malkoski and Mr. Fortnum had a call to discuss the October 1 discussion between Deutsche Bank and J.P. Morgan Securities. Mr. Fortnum asked Mr. Malkoski to confirm whether Penford’s board was unwilling to move forward with a transaction... |
| Filing page 36 | 2014-09-29 | withdrawn_by_bidder | Party F |   | On September 29, 2014, Party F communicated to Deutsche Bank that a combination with Penford was not a suitable strategic fit and declined to pursue further discussions regarding a transaction. |
| Filing page 36 | 2014-09-30 | nda_signed | Party A |   | On September 30, 2014, Penford and Party A executed a nondisclosure and standstill agreement, which included standard confidentiality restrictions and a standstill provision that automatically expired upon the public announcement of the entering into a definit... |
| Filing page 37 | 2014-10-03 | advancement_admitted | Ingredion |   | After further discussion, with input from Deutsche Bank, the directors present at the board meeting unanimously directed management to proceed to negotiate and finalize a definitive agreement with Ingredion. |
| Filing page 30 | 2014-07-17 | contact_initial | Ingredion |   | On July 17, 2014, Mr. Malkoski and Ms. Gordon met for lunch, during which meeting Ms. Gordon advised Mr. Malkoski of Ingredion’s interest in acquiring Penford. |
| Filing page 31 | 2014-08-06 | first_round_bid | Ingredion | 17 per_share | On August 6, 2014, Mr. Malkoski met with Mr. Fortnum, at which meeting Mr. Fortnum indicated Ingredion was prepared to submit a proposal to acquire the Company. Mr. Fortnum suggested that a price of $17.00 per share on a fully diluted basis could likely get su... |
| Filing page 35, 35 | 2014-09-24 | excluded_by_target | Party G |   | On September 24, 2014, the board of directors met with members of management and representatives of Perkins Coie and Deutsche Bank. \| The board determined that Party F should be approached regarding a potential transaction with Penford, but due to the factors ... |
| Filing page 34 | 2014-09-12 | withdrawn_by_bidder | Party B |   | On September 12, 2014, Party B informed Deutsche Bank that it had decided not to move forward with discussions or sign a nondisclosure agreement with respect to a potential transaction. |
| Filing page 38 | 2014-10-13 | first_round_bid | Party A | 16-18 per_share | On October 13, 2014, Deutsche Bank had a discussion with representatives of Party A, who indicated that its value range for a potential transaction had been reduced from $17.50 - $18.00 per share to $16.00 - $18.00 per share, due to increased volatility in the... |
| Filing page 30 | 2014-07-20 | nda_signed | Ingredion |   | Subsequently, Penford and Ingredion executed a Secrecy Agreement, effective as of July 20, 2014, providing for limited exchange of confidential information and obligating the companies to keep their discussions confidential in order to facilitate the providing... |

## Contract Updates

No deal-specific prompt, rulebook, reference JSON, fallback, or compatibility update was required for this verification. The verification pass did apply the current systematic estimator projection rule to cached audit-v3 raw responses before reports were written.

## Conclusion

Conclusion: VERIFIED

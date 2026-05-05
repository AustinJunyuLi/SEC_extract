# zep Agent Verification

## Run Metadata

- Slug: zep
- Target: ZEP INC
- Acquirer: NEW MOUNTAIN CAPITAL
- Run ID: 466fad1751284c2b8b0d430ff2b2f53b
- Model: gpt-5.5
- Reasoning effort: high
- Audit path: output/audit/zep/runs/466fad1751284c2b8b0d430ff2b2f53b
- Filing source: DEFM14A a2224840zdefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/1408287/000104746915004989/a2224840zdefm14a.htm
- Verification generated: 2026-05-05T20:22:37.468352Z

## Commands

- set -a; [ -f .env ] && source .env; set +a; python -m pipeline.run_pool --filter reference --workers 4 --re-validate
- python scoring/diff.py --slug zep
- python scripts/check_reference_verification.py --slugs zep
- python -m pipeline.reconcile --scope reference

## Extraction And Flag Summary

- Status: passed_clean
- Hard flags: 0
- Soft flags: 0
- Info flags: 0
- Current review flags: 0
- Actors: 13
- Events/review rows: 30 / 30
- Participation counts: 12
- Actor relations: 3
- Estimation bidder rows: 4
- Exact quote audit: 47 graph evidence spans and 33 review-row quotes checked against Filing page text; failures=0

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Comparator status | Filing page evidence was reviewed directly because `scoring/diff.py` still targets the retired row-event surface and matched 0 current AI rows for this deal. | Alex is calibration material, not ground truth; no deal-specific Alex/reference JSON update is required for this verification. |
| Current output shape | Filing page quotes bind every current review row and graph evidence span exactly; quote audit failures=0. | Verified against SEC filing text under `deal_graph_v1`. |
| Alex-only legacy rows | Old comparator reported Alex-only rows=26, deal-level disagreements=5. | Not treated as blockers because the comparator does not project `deal_graph_v1`; current filing-cited review and estimator rows are the live authority. |

## Filing Evidence Review

The reviewer checked the live Background-section projection against `data/filings/zep/pages.json`. Every `source_quote` listed below is an exact substring of the cited Filing page. Estimator rows are accepted only through source-backed boundary events.

### Estimation Rows

| Actor | bI | bI_lo | bI_hi | bF | admitted | T | Unit | Boundary | Filing event date |
|---|---:|---:|---:|---:|---|---|---|---|---|
| New Mountain Capital | 19.25 | 19.25 | 19.25 | 20.05 | True | financial | per_share | final_round_bid | 2015-03-13 |
| Party X |  | 21.5 | 23 |  | False | unknown | per_share | first_round_bid | 2014-05-09 |
| Party Y |  | 19.5 | 20.5 |  | False | unknown | per_share | first_round_bid | 2014-05-20 |
| five parties submitting preliminary indications of interest on April 14, 2014 |  | 20 | 22 |  | False | unknown | per_share | first_round_bid | 2014-04-14 |

### Review Row Evidence

| Filing page | Date | Event subtype | Actor | Value | Quote excerpt |
|---|---|---|---|---:|---|
| Filing page 40 | 2015-02-27 | exclusivity_grant | New Mountain Capital |   | On February 27, 2015, we signed an agreement with New Mountain Capital extending the term of the confidentiality provision, the "standstill" provision and the employee non-solicitation provision in our original confidentiality agreement with them as well as pr... |
| Filing page 37 | 2014-05-09 | ioi_submitted | Party X |   | On May 9, 2014, Party X submitted a preliminary and non-binding indication of interest to BofA Merrill Lynch |
| Filing page 37 | 2014-04-14 | ioi_submitted | five parties submitting preliminary indications of interest on April 14, 2014 |   | On April 14, 2014, five parties, comprising four financial buyers and one strategic buyer, submitted preliminary and non-binding indications of interest. |
| Filing page 42 | 2015-05-07 | non_responsive | parties contacted during the go-shop process |   | As of the end of the go-shop period, none of the parties contacted during the go-shop process had submitted a competing acquisition proposal to us or our representatives, and no such party remained engaged in discussions or negotiations with us or our represen... |
| Filing page 40 | 2015-03-18 | exclusivity_grant | New Mountain Capital |   | After further discussion, based upon progress in negotiations with New Mountain Capital and New Mountain Capital's reiteration that any definitive merger agreement would contain a "go-shop" provision, our board of directors authorized an extension of exclusivi... |
| Filing page 39 | 2015-02-26 | first_round_bid | New Mountain Capital | 20.05 per_share | On February 26, 2015, New Mountain Capital delivered a revised indication of interest reflecting an increased per share price of $20.05, and indicated that this was the highest price it was willing to offer. |
| Filing page 39 | 2015-02-19 | ioi_submitted | New Mountain Capital |   | On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest to the Company to acquire us for a per share price of $19.25. |
| Filing page 37, 37 | 2014-04-14 | first_round_bid | five parties submitting preliminary indications of interest on April 14, 2014 | 20-22 per_share | On April 14, 2014, five parties, comprising four financial buyers and one strategic buyer, submitted preliminary and non-binding indications of interest. \| The bids received in the preliminary indications of interest ranged from $20.00 per share to $22.00 per ... |
| Filing page 42 | 2015-04-08 | go_shop_started | BofA Merrill Lynch |   | Representatives of BofA Merrill Lynch commenced the go-shop process on our behalf on April 8, 2015. |
| Filing page 38 |  | withdrawn_by_bidder | five of the remaining six interested parties |   | Over the next few weeks, five of the remaining six interested parties communicated to representatives of BofA Merrill Lynch that they were unable to proceed with the process due to concerns regarding valuation and, in some cases, the interested parties' own in... |
| Filing page 40 | 2015-03-13 | final_round_bid | New Mountain Capital |   | On March 13, 2015, New Mountain Capital communicated that the $20.05 per share offer price was New Mountain Capital's "best and final" offer. |
| Filing page 37 | 2014-03-19 | nda_signed | New Mountain Capital |   | We entered into a confidentiality agreement with New Mountain Capital on March 19, 2014. |
| Filing page 39 | 2015-02-26 | ioi_submitted | New Mountain Capital |   | On February 26, 2015, New Mountain Capital delivered a revised indication of interest reflecting an increased per share price of $20.05, and indicated that this was the highest price it was willing to offer. |
| Filing page 37, 37 | 2014-05-09 | first_round_bid | Party X | 21.5-23 per_share | On May 9, 2014, Party X submitted a preliminary and non-binding indication of interest to BofA Merrill Lynch \| The bid submitted by Party X ranged from $21.50 to $23.00 per share. |
| Filing page 37 |  | advancement_declined | New Mountain Capital |   | While New Mountain Capital received the marketing materials and the first round process letter, it decided at the time not to submit a preliminary indication of interest. |
| Filing page 38, 38 | 2014-05-20 | first_round_bid | Party Y | 19.5-20.5 per_share | On May 20, 2014, Party Y submitted a preliminary and non-binding indication of interest \| The indication of interest submitted by Party Y ranged from $19.50 to $20.50 per share. |
| Filing page 42 | 2015-05-07 | go_shop_ended |  |   | during the "go-shop period" that began on the date of the merger agreement and continued until 11:59 p.m., New York City time, on May 7, 2015 |
| Filing page 38 | 2014-05-22 | advancement_admitted | six remaining bidders in May 2014 |   | On May 22, 2014, a draft of the merger agreement was distributed to the six remaining bidders (Party X having withdrawn from the process on May 14, 2014) that had submitted preliminary indications of interest. |
| Filing page 39 | 2015-02-19 | first_round_bid | New Mountain Capital | 19.25 per_share | On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest to the Company to acquire us for a per share price of $19.25. |
| Filing page 37 |  | contact_initial | Party X |   | two additional parties, comprising one financial party ("Party X") and one strategic party ("Party Y"), contacted representatives of BofA Merrill Lynch on an unsolicited basis to inquire about the process. |
| Filing page 38 |  | non_responsive | sixth remaining interested party |   | The sixth remaining interested party declined to respond to BofA Merrill Lynch's communications regarding a potential transaction. |
| Filing page 37 | 2014-04-16 | advancement_admitted | five parties submitting preliminary indications of interest on April 14, 2014 |   | After further discussion, our board of directors determined to continue the process with the parties who had submitted preliminary indications of interest. |
| Filing page 38 | 2014-05-20 | ioi_submitted | Party Y |   | On May 20, 2014, Party Y submitted a preliminary and non-binding indication of interest |
| Filing page 40 | 2015-03-13 | final_round_bid | New Mountain Capital | 20.05 per_share | On March 13, 2015, New Mountain Capital communicated that the $20.05 per share offer price was New Mountain Capital's "best and final" offer. |
| Filing page 39 | 2015-02-10 | contact_initial | New Mountain Capital |   | On February 10, 2015, New Mountain Capital met with representatives of BofA Merrill Lynch and expressed its interest in discussions with the Company regarding a potential transaction. |
| Filing page 37 | 2014-03-20 | contact_initial | New Mountain Capital |   | On March 20, 2014, management delivered the marketing materials and held an introductory meeting with representatives of New Mountain Capital. |
| Filing page 38 | 2014-06-26 | cohort_closure |  |   | At a June 26, 2014 meeting of our board of directors, based on the lack of buyer interest and the uncertainty surrounding the impact of the fire at our aerosol manufacturing facility in Marietta, Georgia, our board of directors decided to terminate the process... |
| Filing page 37 |  | contact_initial | Party Y |   | two additional parties, comprising one financial party ("Party X") and one strategic party ("Party Y"), contacted representatives of BofA Merrill Lynch on an unsolicited basis to inquire about the process. |
| Filing page 38 | 2014-05-14 | withdrawn_by_bidder | Party X |   | May 14, 2014, prior to receiving access to the electronic data room or meeting with the Company's management, Party X informed representatives of BofA Merrill Lynch that it was no longer interested in pursuing a potential transaction with the Company. |
| Filing page 42 | 2015-04-08 | merger_agreement_executed | New Mountain Capital |   | Following the meeting of our board of directors, the parties executed the merger agreement and the related transaction documents and issued a press release announcing the transaction on the morning of April 8, 2015. |

## Contract Updates

No deal-specific prompt, rulebook, reference JSON, fallback, or compatibility update was required for this verification. The verification pass did apply the current systematic estimator projection rule to cached audit-v3 raw responses before reports were written.

## Conclusion

Conclusion: VERIFIED

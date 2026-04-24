# Providence & Worcester clean ref-9 adjudication

Run artifact reviewed: `/tmp/sec_extract_ref9_clean/providence-worcester.raw.json`  
Diff reviewed: `scoring/results/providence-worcester_20260423T212321Z.md` and JSON  
Filing reviewed: `data/filings/providence-worcester/pages.json`  
Reference reviewed: `reference/alex/providence-worcester.json`

## Status / Disposition

Disposition: **not clean yet; extraction is directionally stronger than Alex, but needs targeted fixes before Austin marks the deal verified.**

The current AI extraction correctly captures the main Providence pattern that Alex's legacy reference compresses: a large initial NDA pool, non-binding IOI and LOI rounds, later narrowing to G&W and Party B, Party D/E re-engagement, G&W's August 12 topping bid, and same-day execution. Alex's reference is wrong or stale on several high-signal points: aggregated NDAs/IOIs, `DateEffective`, Party B "Executed", G&W execution date, filing-verbatim names, and public-company flags.

The AI's main remaining problems are narrower but material:

- It over-emits an April 27 `Final Round Inf Ann` row for the initial IOI request. That was an initial non-binding IOI deadline, not a final-round event under the current vocabulary.
- It mishandles identity continuity in the May 19 to June 1 IOI cohort. The filing supports nine IOIs and later two low-bidder cuts plus one strategic and one financial non-LOI participant, but the raw placeholders do not consistently map the nine IOIs into those later fates.
- The `Executed` row carries the $25 value; that value belongs on the August 12 G&W bid row, not on the legal execution event.
- The rulebook has a latent conflict around `all_cash`: final merger consideration is all cash, but earlier G&W offers include a CVR.

Recommended status after this adjudication: **requires extraction-side rerun/fix; no rulebook block except the `all_cash` clarification and optional "subsequently" date guidance.**

## Evidence Basis

Core filing chronology, with source pages:

- Page 8: deal identity. The filing defines "PWRR" and "Company" as `Providence and Worcester Railroad Company`, and "G&W" as `Genesee & Wyoming Inc.`
- Page 9: G&W public-company evidence: "G&W's common stock is listed on the New York Stock Exchange under the ticker symbol 'GWR'."
- Page 12: closing timing. The proxy says the merger is expected in Q4 2016 and "we cannot predict the actual timing, or whether the closing of the merger will occur at all."
- Page 34: Q4 2015 Party A approach and January 27, 2016 GHF engagement.
- Page 35: March 2016 process launch and initial NDAs: during the week of March 28, GHF contacted 11 strategic and 18 financial buyers; "Each of the potential strategic buyers and 14 potential financial buyers subsequently executed confidentiality agreements."
- Page 36: April 27 IOI request; May 19 to June 1 nine IOIs; two low bidders excluded; mid-June LOI instruction; early-July Party C approach/NDA/IOI; late-July LOIs including Party B and G&W.
- Page 37: Party E/D/C/F LOIs, one strategic and one financial buyer not submitting LOIs, July 27 narrowing to G&W and Party B, July 29 Party D/E re-engagement, August 1 revised LOIs, and August 2 Party E/D withdrawal/stopping language.
- Page 38: August 12 G&W $25 revised LOI with merger-agreement and voting-agreement markups and short expiry.
- Page 39: Party B refused to increase; Board chose G&W; merger agreement executed; press release on Monday, August 15 before market open.
- Page 41/42: termination fee evidence, including $3.785 million and approximately 3% of transaction value.

Short filing snippets Austin can verify quickly:

- Page 35, initial NDAs: "representatives of GHF contacted 11 potential strategic buyers ... and 18 potential financial buyers. Each of the potential strategic buyers and 14 potential financial buyers subsequently executed confidentiality agreements."
- Page 36, first IOIs: "Between May 19, 2016 and June 1, 2016, the Company received nine written indications of interest ... ranging from $17.93 to $26.50."
- Page 36, two low bidders: "the Transaction Committee concluded that the two low bidders should be excluded from that process."
- Page 36, informal LOI instruction: "representatives of GHF instructed all potential buyers to submit non-binding letters of intent ('LOIs') by July 20, 2016."
- Page 37, late-July LOIs: "the Company received six LOIs with offer prices per share ranging from $19.20 to $24.00."
- Page 37, no-LOI parties: "One strategic buyer and one financial buyer elected not to submit an LOI."
- Page 37, narrowed process: "proceed with confirmatory due diligence and negotiations with G&W and Party B ... remaining bidders ... no longer involved."
- Page 38, G&W final bid: "G&W submitted a revised LOI ... $25.00 per share in cash ... together with mark-ups of the merger agreement and the voting agreement."
- Page 39, Party B drop: "Party B indicated that it would not increase its price."
- Page 39, execution/announcement: "the Company and G&W executed the merger agreement ... The Company issued a press release publicly announcing the transaction on Monday, August 15, 2016."

## Validator-Flag Interpretation

Re-running `pipeline.validate()` on the raw extraction produces **15 soft row flags** and **0 deal flags**.

All 15 row flags are `nda_without_bid_or_drop`, attached to initial March 28-week NDA rows that have no later bidder-specific bid, drop, or execution. These are mostly expected for Providence because the filing says 25 parties executed confidentiality agreements, but only a subset later appears by name or cohort.

Flag disposition:

- Raw rows 3, 8-11, and 18-27, BidderIDs 4, 9-12, and 19-28: **dismiss as expected soft flags** for silent NDA signers. The filing supports the NDA count; it does not narrate each silent party's later fate.
- Raw row 3 / BidderID 4 / Party A: **dismiss Alex's implied 7/22 Party A drop.** The filing supports Party A's Q4 2015 interest and inclusion in the NDA pool, but does not say Party A specifically failed or dropped on July 22.
- Do not synthesize generic drops for these NDA-only parties. That would violate the current NDA-only rule and would fabricate fates the filing does not provide.

The soft flags are useful audit markers, not blockers. The bigger extraction problem is not that silent NDA signers lack drops; it is that the named/placeholder IOI cohort needs to line up with the later two low-bidder exclusions and two no-LOI parties.

## Material Diff Adjudication

### Deal-Level Disagreements

| Field | Verdict | Basis |
|---|---|---|
| `TargetName` | **AI correct, Alex wrong** | Page 8 and cover language use `Providence and Worcester Railroad Company`. Alex's `PROVIDENCE & WORCESTER RR CO` is a legacy uppercase ticker-style name, not filing-verbatim. |
| `Acquirer` | **AI correct, Alex wrong** | Page 8 defines G&W as `Genesee & Wyoming Inc.` Alex's uppercase `GENESEE & WYOMING INC` is not filing-verbatim. |
| `DateEffective` | **AI correct, Alex wrong** | This DEFM14A predates closing. Page 12 says the parties cannot predict actual timing. Alex's `2016-11-01` may be a later actual closing date, but it is not stated as effective in this filing. Keep `null`. |

### Matched Field Disagreements

| Row | Verdict | Notes |
|---|---|---|
| Party C `Bid`, 2016-07-12, AI BidderID 44 | **AI correct, Alex wrong/reference stale** | Page 36 calls Party C a "potential strategic buyer." Current schema requires boolean `public`; since the filing does not say public, `public=false` is the correct boolean. Alex's `public=null` is converter/reference drift. |
| G&W `Bid`, 2016-07-21, AI BidderID 46 | **AI correct, Alex wrong/reference stale** | Page 9 says G&W is NYSE-listed (`GWR`), so `public=true`. |
| G&W `Bid`, 2016-07-26, AI BidderID 54 | **AI correct on `bid_type`; Alex wrong** | The bid is a revised LOI in the non-binding LOI round. Page 36 states the round used "non-binding letters of intent." The CVR revision did not become final/binding. G&W `public=true` is also correct. |
| Party D `Bid`, 2016-08-01, AI BidderID 62 | **AI correct, Alex wrong/reference stale** | Page 37 explicitly says Party D is "a financial buyer"; PE/financial bidders are `public=false` under the current boolean schema unless stated otherwise. |
| G&W `Bid`, 2016-08-12, AI BidderID 66 | **AI correct, Alex wrong/reference stale** | Page 9 supports G&W `public=true`; page 38 supports formal treatment through $25 cash, merger-agreement/voting-agreement markups, short expiry, and same-day execution path. |

### `Bidder Interest` Cardinality

Diff bucket: AI rows 3 (`2015-11-15`, `2016-07-29` x2) vs Alex row 1 (`2016-07-22`).

Verdict: **AI mostly correct, Alex wrong.**

- AI BidderID 1 / raw row 0 / Party A / `Bidder Interest` / `2015-11-15`: correct. Page 34 says Party A "expressed some interest in acquiring equity" in Q4 2015. The rough-date mapping to 2015-11-15 is per rules.
- AI BidderIDs 60-61 / raw rows 59-60 / Party D and Party E / `Bidder Interest` / `2016-07-29`: correct as re-engagement rows. Page 37 says both "expressed interest in reengaging and enhancing their offers."
- Alex BidderID 18 / Party A / `2016-07-22`: unsupported. Page 37 says the Transaction Committee reviewed LOIs on July 22, but does not say Party A was present, bid, failed to bid, or dropped on that date.

### `NDA` Cardinality

Diff bucket: AI rows 26 vs Alex rows 3.

Verdict: **AI correct on atomization and count; Alex wrong.**

AI raw rows 3-27 / BidderIDs 4-28 emit the 25 initial confidentiality agreements from the March 28-week outreach, and raw row 42 / BidderID 43 emits Party C's early-July NDA. This matches page 35 (11 strategic + 14 financial confidentiality agreements) plus page 36 (Party C executed a confidentiality agreement after approaching in early July).

Alex's aggregated rows (`G&W` at 2016-04-13, `Party C` at early July, `25 parties, including Parties A, B`) are not current-rule compliant:

- The filing does not state an April 13 G&W NDA date in the pages reviewed.
- The 25 initial NDAs should be atomized under current `rules/bidders.md` atomization rules.
- The AI's March 28-week date is properly midpoint-collapsed to `2016-03-30`, with `bid_date_rough="During the week of March 28, 2016"`.

One caution: the AI's named placeholders inside the 25-NDA pool are only as good as later linkage. Party A, Party B, G&W, Party D, Party E, and Party F can be linked through later named participation; the remaining strategic/financial placeholders should remain generic and should not be over-interpreted.

### `Final Round Inf Ann` Cardinality

Diff bucket: AI rows 2 vs Alex row 1.

Verdict: **both wrong at bucket level.**

- AI BidderID 41 / raw row 40 / `Final Round Inf Ann` / `2016-06-15`: correct. Page 36 says in mid-June GHF instructed all potential buyers to submit non-binding LOIs by July 20. This is the informal LOI round announcement.
- AI BidderID 29 / raw row 28 / `Final Round Inf Ann` / `2016-04-27`: wrong. Page 36 says potential buyers were advised to submit non-binding IOIs by May 10, later postponed to May 19. That is an initial IOI request to the broad pool, not a final round or subset invitation under `rules/events.md` K2.
- Alex has the right concept but stores the date as rough/null in a way the diff cannot match. Under current date rules, mid-June should map to `2016-06-15` with `bid_date_rough="mid-June 2016"`.

Extraction fix: delete raw row 28 / BidderID 29.

### `Bid` Cardinality

Diff bucket: AI rows 15 vs Alex rows 8. This bucket contains several distinct issues.

Verdict: **mixed; AI is better on the late-July/August bidding path, but both sides are wrong for the first IOI cohort.**

Correct AI bid rows:

- Raw rows 43, 45-50, 53, 61-62, and 65 are supported by pages 36-38.
- Party C `Bid` / AI BidderID 44 / `2016-07-12` / $21.00: correct from page 36.
- G&W `Bid` / AI BidderID 46 / `2016-07-21` / $21.15 with $20.02 cash + $1.13 CVR: correct from page 36.
- G&W `Bid` / AI BidderID 54 / `2016-07-26` / $22.15 with $21.02 cash + $1.13 CVR: correct and informal, not formal.
- Party B, E, D, C, F late-July LOIs / AI BidderIDs 47-51 / rough date `late July 2016` mapped to `2016-07-25`: correct date handling under the deterministic rough-date rule. Alex's July 20 date is the submission deadline, not an explicit receipt date for all LOIs.
- Party D and Party E revised LOIs / AI BidderIDs 62-63 / `2016-08-01`: correct. Page 37 states Party D submitted $24.00 and Party E submitted $23.81 with financing support from Party F.
- G&W final revised LOI / AI BidderID 66 / `2016-08-12` / $25.00 cash / formal: correct.

Incorrect or needs-cleanup AI bid rows:

- Raw rows 29-37 / BidderIDs 30-38 atomize the nine May 19 to June 1 IOIs, which is directionally correct, but the bidder aliases are too confident. Page 36 gives a collective nine-IOI count and price range, then says two low bidders were excluded. The later narrative implies a seven-buyer continuation and then two no-LOI parties, but the raw identity mapping does not consistently preserve that funnel.
- Specifically, the AI has a `DropAtInf` row for `Financial Buyer 3` on July 25 but no corresponding May-June IOI row for that financial buyer. If that financial buyer was one of the seven remaining potential buyers who later chose not to submit an LOI, it must have been among the nine IOI submitters.
- The safer reconstruction is: nine IOI rows = Party B, G&W, Party D, Party E, Party F, one strategic no-LOI buyer, one financial no-LOI buyer, and two low-bidder placeholders. Then two low-bidder placeholders drop on June 1, and the strategic/no-LOI and financial/no-LOI placeholders drop in late July for not submitting LOIs.

Incorrect Alex bid rows:

- Alex's aggregated `9 parties` bid row loses event-level atomization required by the current rulebook.
- Alex's Party B `Bid` and `Executed` at July 20 are unsupported. Page 36 gives late-July Party B LOI language and page 38 shows Party B/G&W diligence and agreement negotiations, but the filing never says Party B executed a merger agreement.
- Alex's Party E/F `Bid` at August 2 for $21.26 overstates the filing. Page 37 says Party E withdrew the revised proposal and confirmed its original $21.26 proposal. That is not a new August 2 bid from a joint Party E/F bidder.

### Drop / Cut Rows

Verdict: **AI generally has better dropout semantics; some identity/date cleanup needed.**

- June 1 two low bidders: Alex has `16 parties Drop` and `2 parties DropTarget`. AI emits only two `DropBelowInf` rows for `Financial Buyer 1` and `Financial Buyer 2` (raw rows 38-39 / BidderIDs 39-40). The AI is closer on count (two low bidders), but the exact identities should be tied to the corrected nine-IOI cohort. Code `DropBelowInf` is better than `DropTarget` because the reason is lower bids in an informal IOI round.
- Late-July one strategic and one financial no-LOI party: AI raw rows 51-52 / BidderIDs 52-53 are correct in concept and supported by page 37. They should map to the strategic and financial placeholders that were part of the nine IOI / seven-buyer continuation.
- July 27 remaining-bidders cut: AI raw rows 55-58 / BidderIDs 56-59 for Party C/D/E/F are correct in concept as `DropBelowInf` or target-cut rows, because page 37 says GHF contacted remaining bidders to say they were no longer involved. The exact date is not stated; leaving date null with `date_unknown` is defensible unless the rulebook decides that "subsequently" should anchor to July 27 plus a deterministic offset.
- Alex's `DropTarget` for Party E/D/C/F dated July 27 is understandable but less precise. The filing's stated reason is lower offers relative to G&W/Party B, so `DropBelowInf` is a better current-code mapping than generic `DropTarget`.
- Party D and Party E re-engagement after the July 27 cut is real. AI raw rows 59-64 handle this better than Alex's simpler drop-only view.
- Party E August 2: AI `DropAtInf` is defensible because Party E withdrew its revised proposal, but the note should make clear that Party E confirmed its original $21.26 proposal. Do not create a new $21.26 August 2 bid.
- Party D August 2: AI `DropAtInf` is correct. Page 37 says Party D "would not proceed with further due diligence at that time."
- Party B August 12: AI `DropBelowM` is correct enough. Page 39 says Party B refused to increase after G&W's higher $25 bid. Alex's generic `Drop` is less informative.
- Alex's Party E/F August 12 `Drop` is unsupported. I did not find an August 12 filing statement that Party E/F dropped then; their relevant withdrawal/stopping language is on August 2.

### `Executed` Cardinality / Dates

Diff bucket: AI `2016-08-12`; Alex `2016-07-20` Party B and `2016-08-15` G&W.

Verdict: **AI correct on the executed event; Alex wrong.**

- AI raw row 67 / BidderID 68 / G&W / `Executed` / source page 39 is correct. The filing says the Company and G&W executed the merger agreement shortly after the August 12 Board approval.
- Alex's Party B `Executed` on July 20 is wrong. No Party B merger agreement was executed.
- Alex's G&W `Executed` on August 15 is wrong for signing. August 15 is the press release / public announcement date, and current instructions fold that announcement into `Executed`; the event date remains the signing date, August 12.

Extraction-side cleanup: clear the bid-value fields from the `Executed` row. The $25 price is already captured on G&W's August 12 formal `Bid` row.

## Extraction-Side Fixes Needed

1. **Delete raw row 28 / BidderID 29 (`Final Round Inf Ann`, 2016-04-27).** The April 27 IOI request is not a final-round event.

2. **Rebuild the May 19-June 1 IOI cohort with identity continuity.** Keep nine atomized IOI rows, but map them so later fates are coherent:
   - five later named LOI parties: Party B, G&W, Party D, Party E, Party F;
   - one strategic buyer that later elected not to submit an LOI;
   - one financial buyer that later elected not to submit an LOI;
   - two low-bidder placeholders excluded on June 1.
   This prevents the current error where `Financial Buyer 3` drops for not submitting an LOI without a corresponding first-round IOI row.

3. **Keep the initial 25 NDA atomization.** Raw rows 3-27 are broadly correct in count and date. Do not collapse to Alex's aggregate NDA rows.

4. **Keep Party C as a separate early-July entrant.** Raw rows 41-43 are correct in concept: Party C approached in early July, executed an NDA, and submitted a $21.00 IOI on July 12. The rough-date mapping to July 5 for the approach/NDA is correct under current rules.

5. **Keep G&W July 26 as informal unless the rulebook changes.** It is a revised LOI in the non-binding LOI process and remains CVR-based. Do not convert it to formal just because it is a revision.

6. **Keep August 12 G&W bid as formal.** It has the strongest formal evidence in the filing: $25 cash, merger-agreement/voting-agreement markups, short expiry, and same-day execution.

7. **Do not emit a Party B `Executed` row.** Party B negotiated drafts and was the leading bidder for a period, but no merger agreement with Party B was executed.

8. **Date `Executed` on August 12, not August 15.** Fold the August 15 press release into the August 12 `Executed` row's note/evidence, per current convention.

9. **Clear value fields on the `Executed` row.** Use the August 12 G&W `Bid` row for $25 value; `Executed` should represent signing.

10. **Review `deal.all_cash`.** Final merger consideration is pure cash, but earlier G&W bid rows include `cash+cvr`. The extraction's `all_cash=true` matches the final merger summary and Alex, but the rules contain language that could imply any bid-history CVR makes `all_cash=false`.

## Reference-Side Corrections Needed

Alex reference should be corrected or regenerated for Providence before using it as calibration:

- Replace legacy uppercase `TargetName` and `Acquirer` with filing-verbatim names.
- Set `DateEffective=null` for this filing.
- Add deal-level legal counsel and termination-fee fields if the reference target is meant to carry the current schema's deal fields.
- Atomize the initial 25 March confidentiality agreements and Party C's later confidentiality agreement.
- Remove or replace unsupported G&W NDA date `2016-04-13`; I found no filing support for that date in the reviewed proxy text.
- Replace the aggregated `9 parties` IOI row with nine atomized IOI rows if reference JSONs are intended to reflect current rules.
- Remove Party A `Bidder Interest` and `Drop` on `2016-07-22`; the filing does not support Party A-specific activity on that date.
- Remove Party B `Executed` on `2016-07-20`; no Party B merger agreement was executed.
- Change G&W `Executed` from `2016-08-15` to `2016-08-12`; August 15 is announcement, not signing.
- Correct public flags: G&W `public=true`; unnamed strategic/financial bidders and PE/financial bidders should have boolean `public=false` unless the filing states public-company status.
- Correct Party F type where applicable: page 37 calls Party F "a strategic buyer," not financial.
- Revisit Party E/F treatment. Page 37 says Party E submitted the revised LOI with financing support from Party F; it does not clearly make Party F a joint bidder.

## Rule / Prompt Recommendations

1. **Clarify initial IOI requests vs final-round announcements.** The extractor treated the April 27 first IOI request as `Final Round Inf Ann`. Add prompt language: broad initial IOI solicitations to the whole contacted pool are not final-round rows unless the filing narrows the field or uses process-letter/final-round language.

2. **Clarify cohort identity continuity for count-only rounds.** Providence needs a deterministic pattern for "nine IOIs, two low bidders cut, seven proceed, later one S and one F do not submit LOIs." The extractor should maintain placeholder identities through the funnel rather than creating a no-LOI financial buyer with no prior IOI.

3. **Clarify `all_cash`.** `rules/schema.md` says `all_cash` is derived from the merger-agreement summary, while `rules/bids.md` says every bid event must be cash-only. Providence exposes the conflict because the final deal is all cash but earlier G&W offers included a CVR. Decide whether `all_cash` means final merger consideration or all extracted bid consideration.

4. **Clarify date treatment for "subsequently contacted."** The current AI left the July 27 remaining-bidder cuts undated, with `date_unknown` flags. That is defensible under current `B3`, but if Austin wants deterministic anchoring, add "subsequently" to the anchored phrase table.

5. **Strengthen prompt instruction on `Executed` fields.** The extractor should not copy final price fields onto the `Executed` row when the immediately preceding winning bid row already carries the price.

6. **Document how non-binding LOIs with merger markups are classified.** Providence's July LOI round includes non-binding LOIs plus agreement markups. The current AI treats non-binding LOI context as controlling and labels the bids informal. If that is the intended rule, state explicitly that "non-binding LOI" overrides the mere presence of draft/markup materials for informal-round bids.

## Confidence

Overall confidence: **high** for the main deal chronology, NDA atomization, G&W execution date, deal-level fields, and the conclusion that Alex's reference is stale on this deal.

Medium confidence areas needing Austin's judgment:

- The exact identity mapping among the nine initial IOI submitters, the two low bidders, and the later strategic/financial no-LOI parties. The filing provides counts and later categories, not a fully named bridge.
- Whether the July 27 remaining-bidder cut rows should stay undated or be assigned an inferred date from "subsequently."
- Whether Party E plus Party F financing support should ever be represented as a joint bidder. My reading is no: Party E is the bidder; Party F is financing support.
- Whether `all_cash` should follow final merger consideration only or every extracted bid row's consideration structure.

Lowest-risk next action: fix the April 27 over-emission, repair the IOI cohort identity mapping, clear `Executed` value fields, and regenerate Providence before Austin does final manual verification.

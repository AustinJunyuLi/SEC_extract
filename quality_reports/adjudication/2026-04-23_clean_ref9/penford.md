# Penford adjudication - clean reference-9 run

Deal: `penford`  
Artifacts reviewed: `/tmp/sec_extract_ref9_clean/penford.raw.json`, `data/filings/penford/pages.json`, `reference/alex/penford.json`, `scoring/results/penford_20260423T212321Z.md`, `scoring/results/penford_20260423T212321Z.json`  
Ground truth: Penford DEFM14A filing, especially Background of the Merger on `source_page` 29-39.

## Status / Disposition

Disposition: not clean as-is. The AI is directionally better than Alex on the main Penford chronology and on several reference-side stale-workbook issues, but the raw extraction still needs correction before Austin should mark Penford verified.

Primary reasons:

- Running `pipeline.validate()` directly on the raw extraction raises hard structural flags: non-monotone `BidderID` order, same-date rank violation, and `BidderID` gaps. These are mechanical extraction/finalization problems, not SEC-text judgment calls.
- The AI correctly captures many filing-backed events that Alex omitted or miscoded: Ingredion's July 17 approach, Party A/B/C/D market-check interest, Party B and Party D drops, J.P. Morgan as Ingredion's financial advisor, execution on October 14, and filing-verbatim deal names.
- The AI over-extracts or miscoded some rows: stale 2007/2009 drops should not be `DropAtInf` without agency evidence; the September 29 Ingredion bid duplicates the earlier September 17 range; the September 25 Party C management presentation should not be a separate `Bidder Interest`; Party F's September 29 decline is missing; Party C needs a follow-up/drop resolution.
- Alex's reference has several stale legacy/converter artifacts: uppercase/truncated deal names, external `DateEffective`, null `public` bidder_type fields, wrong October 8 execution/formal-bid dating, wrong October 3 date for Party A, and an unsupported `Final Round Ann`.

Recommended current disposition: extraction-side fixes required, reference-side corrections required, no rulebook change required except one prompt tightening around management-presentation rows and grouped market-check end summaries.

## Evidence Basis

High-signal filing anchors:

- Deal names and pending close: `source_page` 2 says the agreement is among "Penford Corporation, Ingredion Incorporated, and Prospect Sub, Inc." and says "If the merger is completed..." shareholders will receive $19.00, so `DateEffective` should remain null in this DEFM14A.
- Stale priors: `source_page` 29 says "In 2007 and 2009" Penford received "unsolicited indications of interest to acquire Penford" from two industry parties, entered confidentiality agreements, and "These discussions did not result in offers."
- Ingredion start: `source_page` 30 says that on July 17, 2014, Ingredion's CEO "advised Mr. Malkoski of Ingredion's interest in acquiring Penford"; the July 20 secrecy agreement is separately stated on the same page.
- Deutsche Bank: `source_page` 31 says the Executive Committee directed management on July 24 to "proceed to retain Deutsche Bank"; on August 11, Deutsche Bank reviewed Ingredion's proposal and alternatives with the Executive Committee.
- Party A initial interest: `source_page` 32 says on August 11 Party A's CEO "informally discussed Party A's potential interest in acquiring or combining with Penford."
- Market check: `source_page` 34 says Deutsche Bank contacted six strategic counterparties; Party A and Party B expressed interest on September 9, Party C on September 10, Party D on September 11, and Party B declined on September 12.
- Ingredion range: `source_page` 35 says on September 17 Ingredion "could potentially increase its proposal from $18.00 to $18.25 or $18.50 per share."
- Party F: `source_page` 35 says Party F was contacted on September 24; `source_page` 36 says on September 29 Party F "declined to pursue further discussions."
- October bids and signing: `source_page` 36 says Ingredion moved to $18.50 orally and then sent a $19.00 letter on October 2; `source_page` 37 says Party A said on October 4 any offer would be below "$17.50 - $18.00"; `source_page` 38 says Party A gave a formal indication at $16.00 on October 14; `source_page` 39 says Penford and Ingredion executed the merger agreement during the evening of October 14.

## Validator-Flag Interpretation

Direct validation of the raw extraction produces:

- Hard `bidder_id_date_order_violation`: raw row order places the Deutsche Bank `IB` row dated 2014-08-11 before Ingredion bid rows dated 2014-08-06 and 2014-08-10. This is a mechanical ordering/finalization issue.
- Hard `bidder_id_same_date_rank_violation`: on 2014-08-21, Ingredion `NDA` is ordered after J.P. Morgan `IB`, contrary to same-date rank ordering.
- Hard `bidder_id_structural_error`: raw `BidderID` values have gaps, with max 39 but only 37 events. The gaps are visible at missing IDs 18 and 29.
- Soft `nda_without_bid_or_drop`: Party C's NDA row, raw `BidderID` 24 on 2014-09-15, has no later bid/drop/executed row. This flag is upheld. The filing later says the remaining market-check parties either did not move forward in a timely manner or submitted lower value; Party C is identifiable by process of elimination and should receive a guarded drop row, or the rule should explicitly say not to split grouped end summaries.

Embedded row flags:

- `date_inferred_from_rough` on stale 2007/2009 rows is correct; year-only maps to July 1 under `rules/dates.md` section B1.
- `drop_agency_ambiguous` on stale 2007/2009 drops is correct, but the rows should be `Drop`, not `DropAtInf`, because the quote does not say the party voluntarily withdrew.
- `activist_sale_classification_borderline` on SEACOR is appropriate. The filing shows activist pressure through director nominations, not an explicit sale demand.
- `bid_range` on the September 17 Ingredion range and Party A ranges is correct.
- `bid_value_ambiguous` on Party A's October 4 "below $17.50 - $18.00" row is correct; the filing gives a referenced range, not a firm lower/upper offer.
- `informal_vs_formal_borderline` on Party A's October 14 letter is correct. The filing says "formal letter" but also "indication of interest"; absent binding/final-round language, informal is defensible.

## Material Diff Adjudication

### Deal-Level Disagreements

- `TargetName`: AI correct, Alex wrong. Use `Penford Corporation`, not `PENFORD CORP`. Filing caption and shareholder letter use "Penford Corporation."
- `Acquirer`: AI correct, Alex wrong. Use `Ingredion Incorporated`, not `INGREDION INC`.
- `DateEffective`: AI correct, Alex wrong for this filing. The DEFM14A predates closing and speaks conditionally ("If the merger is completed"). Alex's 2015-03-11 is external closing data and should not be in AI-produced `DateEffective`.

### 2007 / 2009 Stale Prior Processes

Diff rows: AI-only raw `BidderID` 1-6; Alex-only `BidderID` 1-4.

Adjudication: both partly wrong, AI mostly closer to current rules.

- AI correct: include stale prior process rows with `process_phase = 0`. `rules/events.md` section L1 explicitly says Penford's 2007 and 2009 prior attempts are included but do not count toward auction threshold.
- AI correct: year-only dates should be `2007-07-01` and `2009-07-01` with `bid_date_rough` equal to `2007` / `2009`. Alex's `2007-01-15 00:00:00` and `2009-01-15 00:00:00` are stale converter artifacts.
- AI defensible: `Bidder Sale` for the two unsolicited "indications of interest to acquire Penford" is plausible under the current rule's "unambiguous intent-to-buy" language, even though no offer followed.
- AI wrong: the two stale drop rows should be `Drop`, not `DropAtInf`, unless Austin wants "did not result in offers" to imply voluntary at-informal withdrawal. The filing does not identify the initiator.
- Alex wrong: the first stale row's comment says "[EVERYTHING IN GREY SHOULD NOT BE HERE]," which conflicts with current section L1 inclusion. Alex also omits the start-of-process event.

### SEACOR

Diff row: AI-only raw `BidderID` 7, `Activist Sale`, 2014-07-11.

Adjudication: AI correct under current rules; Alex omission defensible only under a narrower "activist demands sale" interpretation.

Evidence: `source_page` 30 says SEACOR filed a Schedule 13D amendment intending to nominate four directors. The Background then repeatedly treats the SEACOR filing as part of the strategic context, including checking whether SEACOR was interested in acquiring Penford. Keep the row with the borderline flag.

### Ingredion Initiation and NDA

Diff rows: AI-only raw `BidderID` 8 `Bidder Sale` on 2014-07-17; matched `NDA` on 2014-07-20; Alex residual `Bidder Interest` on 2014-07-20.

Adjudication: AI correct, Alex wrong.

The first sale-relevant event is July 17, when Ingredion expressed interest in acquiring Penford. The secrecy agreement is July 20. Alex's `Bidder Interest` on July 20 collapses two events and misdates the approach.

### Financial Advisor Rows

Diff bucket: `IB` residual mismatch. AI has Deutsche Bank `IB` on 2014-08-11 and J.P. Morgan Securities `IB` on 2014-08-21; Alex has one Deutsche Bank row on 2014-08-21.

Adjudication: AI correct on including both advisors; Alex wrong/incomplete. Minor open nuance on Deutsche Bank's exact date.

- Deutsche Bank: the filing first says on July 24 that the Executive Committee directed management to proceed to retain Deutsche Bank, but the first clear advisory action is August 11, when Deutsche Bank reviewed Ingredion's proposal and strategic alternatives. Under current section J1 "earliest narrated date acting in advisory capacity," AI's August 11 date is acceptable.
- J.P. Morgan Securities: `source_page` 33 identifies J.P. Morgan Securities as Ingredion's financial advisor at the August 21 management presentation. Alex omits the acquirer-side IB row.
- Reference correction: Alex's Deutsche Bank date of August 21 is unsupported for target advisor retention/action; it appears to be copied from the Ingredion presentation date.

### Target Sale Rows

Diff rows: AI-only raw `BidderID` 14 on 2014-08-13 and raw `BidderID` 17 on 2014-08-28.

Adjudication: mixed; 2014-08-28 AI correct, 2014-08-13 both defensible.

- 2014-08-13: the board directed management to proceed with further investigation and development of Ingredion's proposal. This is a real target-side process step but weaker than a board resolution to sell. Keeping it as `Target Sale` is defensible; omitting it is also defensible if Austin wants only the first broad sale-process authorization.
- 2014-08-28: the board authorized management and Deutsche Bank to proceed with the market-check process. This is a stronger `Target Sale` / sale-process event. Alex should not omit it under current rules.

Recommendation: no rulebook change unless Austin wants only one target-side start row. If so, specify whether the anchor should be first board engagement with Ingredion (August 13) or first market-check authorization (August 28).

### Market-Check Bidder Interest and Drops

Diff bucket: `Bidder Interest` residual mismatch; AI-only Party B drop; AI-only Party F target interest; Alex-only Party A/C drops.

Adjudication: AI mostly correct, with two extraction omissions/over-emissions.

- Party A 2014-08-11 `Bidder Interest`, raw `BidderID` 13: AI correct. Filing says Party A "informally discussed Party A's potential interest in acquiring or combining with Penford."
- Party A 2014-09-09 `Bidder Interest`, raw `BidderID` 19: AI correct with `bidder_reengagement` info flag. Filing says Party A expressed interest in further discussions during the market check.
- Party B 2014-09-09 interest and 2014-09-12 `DropAtInf`, raw `BidderID` 20 and 23: AI correct. Filing says Party B expressed interest, then "decided not to move forward with discussions or sign a nondisclosure agreement."
- Party C 2014-09-10 interest and 2014-09-15 NDA, raw `BidderID` 21 and 24: AI correct.
- Party C 2014-09-25 `Bidder Interest`, raw `BidderID` 28: AI wrong. This is a management presentation after the NDA, not a new bidder-interest event. Remove it.
- Party D 2014-09-11 interest, 2014-09-23 NDA, and 2014-10-08 `DropAtInf`, raw `BidderID` 22, 26, and 35: AI correct; Alex's generic `Drop` on October 8 is less precise.
- Party F 2014-09-24 `Target Interest`, raw `BidderID` 27: AI correct, but incomplete. Add Party F `DropAtInf` on 2014-09-29, citing `source_page` 36: Party F "declined to pursue further discussions."
- Party C drop: AI wrong/incomplete. Add a guarded Party C drop on 2014-10-14, probably `Drop` with an ambiguity flag, citing the board-summary language that the remaining market-check parties "either did not move forward in a timely manner or made a lower indication of value." Alex is directionally right to have a Party C drop but should not leave it uncited/generic.
- Party A drop: Alex's 2014-10-14 drop is defensible as an implicit target cut after Party A submitted a $16.00 indication and the board signed with Ingredion. The AI has Party A's October 14 bid but no explicit drop. This is lower priority than Party C because Party A already has a final observed bid; add a `DropBelowInf` only if the rulebook wants final losing bids closed explicitly.

### Bid Rows and Values

Diff bucket: `Bid` residual mismatch; field disagreements on ranges.

Adjudication:

- Ingredion 2014-08-06 $17.00 and 2014-08-10 $18.00: matched; AI correct.
- Ingredion 2014-09-17 range $18.25-$18.50, raw `BidderID` 25: AI correct on value structure; Alex wrong to populate `bid_value_pershare = 18.25`. Section H1 says ranges use `bid_value_lower` and `bid_value_upper`, with `bid_value_pershare = null`.
- Ingredion 2014-09-29 $18.50, raw `BidderID` 30: AI wrong. The board discussion refers back to the current $18.25/$18.50 proposal; it is not a new bid from Ingredion. Remove this row.
- Ingredion 2014-10-02 $18.50 call and $19.00 letter, raw `BidderID` 32 and 33: AI correct; Alex also has these matched rows.
- Party A 2014-10-04 below $17.50-$18.00, raw `BidderID` 34: AI correct on date and ambiguity; Alex wrong on October 3 date and overly firm `bid_value_pershare = 17.5`. Keep AI's soft `bid_value_ambiguous` flag.
- Party A 2014-10-13 reduced range $16.00-$18.00, raw `BidderID` 36: AI correct on range structure; Alex wrong to populate `bid_value_pershare = 16`.
- Ingredion 2014-10-14 price confirmation, raw `BidderID` 37: AI defensible. Filing says Mr. Fortnum called to confirm the $19.00 proposed price and proceed with the transaction as planned. Do not replace this with Alex's unsupported October 8 formal bid.
- Party A 2014-10-14 $16.00 formal letter, raw `BidderID` 38: AI correct to classify as informal/borderline; "formal letter" is not the same as a binding final-round bid.

### Final Round Ann

Diff row: Alex-only `Final Round Ann`, rough date 2014-10-03.

Adjudication: AI correct, Alex wrong.

The October 3 board direction was to "proceed to negotiate and finalize a definitive agreement with Ingredion." There was no subset invitation, process letter, final bid deadline, or final-round instruction. Do not emit `Final Round Ann`.

### Executed Date

Diff row: `Ingredion` `Executed`, AI 2014-10-14 vs Alex 2014-10-08.

Adjudication: AI correct, Alex wrong.

`source_page` 39 says "During the evening on October 14, 2014, Penford and Ingredion finalized and executed the merger agreement." October 8 was only circulation of a revised draft merger agreement by Sidley Austin.

### `bidder_type.public` Field Disagreements

Adjudication: AI correct under schema; Alex/converter wrong or stale.

The schema requires `public: bool`, not null. For Ingredion, `public: true` is supported by the filing's party description: "Ingredion ... common stock is traded on the New York Stock Exchange" (`source_page` 7 / proxy summary page 1). For unnamed strategic parties, `base: "s"` is supported by "six potential strategic counterparties in the same or similar industries" (`source_page` 34). `public: false` is acceptable unless the filing states public-traded status.

## Extraction-Side Fixes Needed

1. Re-run through finalization/canonical ordering or otherwise fix raw `BidderID` sequence:
   - remove gaps 18 and 29;
   - order 2014-08-06 and 2014-08-10 Ingredion bid rows before the 2014-08-11 Deutsche Bank `IB`;
   - order the 2014-08-21 Ingredion `NDA` before the 2014-08-21 J.P. Morgan `IB` if same-date rank requires it.

2. Recode stale prior drops:
   - raw `BidderID` 3 and 6 should be `Drop` with `drop_agency_ambiguous`, not `DropAtInf`, unless Austin explicitly decides that "did not result in offers" is enough for `DropAtInf`.

3. Remove over-emitted rows:
   - raw `BidderID` 28, Party C `Bidder Interest` on 2014-09-25. This is a management presentation, not a new expression of interest.
   - raw `BidderID` 30, Ingredion `Bid` on 2014-09-29 at $18.50. This repeats the September 17 range in a board status discussion.

4. Add missing follow-up rows:
   - Party F `DropAtInf` on 2014-09-29, `source_page` 36, quote: "Party F ... declined to pursue further discussions."
   - Party C drop on 2014-10-14, probably `Drop` plus ambiguity flag, sourced to the October 14 board/market-check summary that the remaining market-check parties "either did not move forward in a timely manner or made a lower indication of value."
   - Consider Party A `DropBelowInf` on 2014-10-14 only if Austin wants an explicit closeout row for the final losing lower indication.

5. Keep these AI rows unless Austin makes a narrower rule decision:
   - SEACOR `Activist Sale` with soft borderline flag.
   - Ingredion `Bidder Sale` on 2014-07-17.
   - Party B `DropAtInf` on 2014-09-12.
   - Party D `DropAtInf` on 2014-10-08.
   - J.P. Morgan `IB` on 2014-08-21.
   - Executed on 2014-10-14.

## Reference-Side Corrections Needed

1. Change deal identity fields to filing-verbatim:
   - `TargetName = "Penford Corporation"`
   - `Acquirer = "Ingredion Incorporated"`
   - `DateEffective = null`

2. Populate `bidder_type.public` booleans instead of nulls, or suppress these converter artifacts from material diffs. Ingredion should be `public: true`; unnamed strategic parties should not remain null under the current schema.

3. Stale priors:
   - use `2007-07-01` / `2009-07-01` for year-only rough dates;
   - include phase-0 rows per current rulebook;
   - if keeping drop rows, use `Drop` rather than uncited generic legacy drops.

4. Replace Alex's collapsed/misdated Ingredion initiation:
   - add July 17 `Bidder Sale`;
   - keep July 20 `NDA`;
   - remove July 20 `Bidder Interest`.

5. Fix advisor rows:
   - Deutsche Bank should not be dated August 21; use August 11 under current J1, or July 24 if Austin decides board selection counts as retention.
   - add J.P. Morgan Securities as Ingredion's financial advisor on August 21.

6. Delete unsupported `Final Round Ann` on October 3.

7. Fix October bid/signing dates:
   - Party A's below-$17.50/$18.00 discussion is October 4, not October 3.
   - Remove Ingredion formal bid on October 8; the filing only has merger-agreement draft circulation then.
   - `Executed` is October 14, not October 8.

8. Keep/reference Party D and Party A/C drops only with filing-supported notes:
   - Party D October 8 can be `DropAtInf`.
   - Party C October 14 should carry an ambiguity note because the filing uses grouped summary language.
   - Party A October 14 is defensible as a losing-bid closeout, but the filing does not separately say "Party A withdrew" or "Penford rejected Party A."

## Rule / Prompt Recommendations

No mandatory rulebook change. Current rules are mostly sufficient.

Prompt tightening recommended:

- Tell the extractor not to emit `Bidder Interest` for ordinary post-NDA diligence activity or management presentations unless the bidder newly expresses interest or changes process status. This would prevent raw `BidderID` 28.
- Tell the extractor to add drop rows for specifically identifiable market-check parties when the filing later summarizes the contacted group as not moving forward, but to use `Drop` plus an ambiguity flag when the grouped language does not assign a precise reason to each party. This would close Party C without overclaiming.
- Tell the extractor that repeated board descriptions of an already-stated proposal are not new bids unless the filing narrates a new communication from the bidder or advisor changing the value/terms. This would prevent raw `BidderID` 30.

Potential Austin decision, not urgent:

- For Penford-like stale priors, decide whether "unsolicited indications of interest to acquire" should always become `Bidder Sale` or instead `Bidder Interest` when the same sentence says discussions did not result in offers. The current wording supports `Bidder Sale` through "unambiguous intent-to-buy," but a narrower interpretation would also be reasonable.
- For target-side process starts, decide whether both August 13 and August 28 should be emitted, or whether only the strongest sale-process authorization should survive. I would keep August 28 regardless.

## Confidence

Confidence: high on deal-level fields, execution date, DateEffective null, range value structure, Party B/D drops, unsupported Final Round Ann, and Alex's October 8 errors.

Confidence: medium on the exact coding of stale prior start/drop rows, whether to keep both Target Sale rows, and whether to add an explicit Party A drop after its October 14 lower indication.

Lowest-confidence item: splitting the October 14 grouped market-check summary into Party C (and possibly Party A) drop rows. The filing supports the inference by elimination, but the evidence is grouped rather than party-specific, so any emitted row should carry an ambiguity flag.

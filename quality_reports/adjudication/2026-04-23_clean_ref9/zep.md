# Zep clean reference-9 adjudication

## Status / disposition

Disposition: needs targeted extraction-side revision and reference-side correction before this run should be treated as verified.

The AI extraction is directionally closer to the filing than Alex's reference on the main structure: it atomizes the 2014 NDA and bid counts, preserves range bids as ranges, dates most events from the filing, captures the 2014 termination / 2015 restart, and cites every row. Alex's reference remains a useful calibration artifact but contains stale grouping, legacy rough-date conventions, final-round rows that are not supported by the filing, and several inferred bid values/dates.

That said, the current raw AI JSON is not clean. The main extraction fixes are:

- Remove or merge raw BidderID 3, the second `Target Sale` row dated 2014-02-27.
- Retain raw BidderID 29 as New Mountain Capital's 2014 informal-stage dropout, but date it to the April 14, 2014 first-round deadline or flag the date as inferred from the March 27 process letter / April 14 deadline.
- Fix raw BidderID 37, Party Y's bid: the `unsolicited_first_contact` exemption is not valid because Party Y continued into data-room access and management presentation.
- Recode raw BidderIDs 38-43 as six identity-ambiguous generic dropout rows, or otherwise avoid assigning the "five unable to proceed" outcome to specific bidders the filing does not identify.
- Remove raw BidderID 51 as a separate formal bid; the April 2015 text is a price reaffirmation during merger-agreement negotiations, not a new bid event.

## Sources reviewed

- Raw extraction: `/tmp/sec_extract_ref9_clean/zep.raw.json`
- Filing text: `data/filings/zep/pages.json`, especially pages 1-2 and 35-42
- Alex reference: `reference/alex/zep.json`
- Fresh diff: `scoring/results/zep_20260423T212321Z.md` and `.json`
- Relevant rules: `rules/events.md`, `rules/bidders.md`, `rules/bids.md`, `rules/dates.md`, `rules/schema.md`, `prompts/extract.md`

No older adjudication reports or prior quality reports were used.

## Evidence basis

Key filing evidence:

- Page 1 identifies the registrant as "Zep Inc."; page 2 states the merger agreement is among Zep Inc., NM Z Parent Inc. and NM Z Merger Sub Inc., with Parent indirectly owned by funds advised by New Mountain Capital.
- Page 35: "At a January 28, 2014 board meeting... our board of directors decided to engage in a process to consider strategic alternatives." This supports a single `Target Sale` row on 2014-01-28.
- Pages 35-36: the board approved BofA Merrill Lynch's engagement letter at the January 28, 2014 meeting; page 36 continues that BofA would act as financial advisor.
- Page 36: after the February 27, 2014 board meeting, the board approved contacting potential buyers, executing confidentiality agreements, and management meetings.
- Pages 36-37: BofA contacted 50 potential buyers; 25 declined to enter confidentiality agreements and 25 executed confidentiality agreements, received marketing materials and/or met management.
- Page 37: New Mountain Capital was one of the financial buyers, signed a confidentiality agreement on March 19, 2014, received materials/process letter, and decided not to submit a preliminary indication.
- Page 37: first-round process letter was distributed on March 27, 2014, with non-binding preliminary indications due no later than April 14, 2014.
- Page 37: five parties, comprising four financial buyers and one strategic buyer, submitted preliminary non-binding indications on April 14, 2014; the bids ranged from $20.00 to $22.00 per share.
- Pages 37-38: Party X submitted a $21.50-$23.00 non-binding indication on May 9 and withdrew on May 14 before data-room access or management meetings.
- Page 38: Party Y submitted a $19.50-$20.50 non-binding indication on May 20; data-room access was subsequently made available and management met with Party Y.
- Page 38: on May 22, draft merger agreement was distributed to six remaining bidders; over the next few weeks, five remaining interested parties were unable to proceed and a sixth stopped responding.
- Page 38: on June 26, 2014, the board terminated the process.
- Page 39: on February 10, 2015, New Mountain met BofA and expressed interest; on February 19, it delivered a $19.25 unsolicited indication; on February 26, it delivered a revised $20.05 indication.
- Page 40: on February 27, 2015, Zep signed an agreement extending New Mountain's original confidentiality / standstill / employee non-solicitation provisions and providing exclusivity through March 31.
- Page 40: on March 13, 2015, New Mountain communicated that $20.05 was its "best and final" offer.
- Page 41: in April, New Mountain reiterated that $20.05 was its best and final offer; the April 6 board meeting reviewed remaining transaction terms, including a 30-day go-shop, $8.75 million go-shop termination fee, $17.5 million post-go-shop termination fee, and $33.75 million reverse termination fee.
- Page 42: on April 7, 2015, the board approved the transaction and the parties executed the merger agreement after the meeting; the press release was issued the morning of April 8.

## Validator-flag interpretation

Python validation of the raw extraction raised 19 soft `nda_without_bid_or_drop` row flags and no deal-level flags. These correspond to raw event indices 9-27, i.e. BidderIDs 10-28 (`Potential Buyer 1` through `Potential Buyer 19`) that signed or are included in the 25 March 2014 confidentiality-agreement count but have no individually narrated later bid/drop/execution.

Interpretation: uphold as expected soft advisories, not extraction misses. The filing gives exact NDA counts, so these rows should exist under `rules/bidders.md` §E2.b / §E5. The filing does not give signer-specific follow-up for these 19 placeholders. `rules/events.md` §I1 specifically says to keep NDA-only rows and not fabricate catch-all drops from a generic shared quote. Austin can dismiss these flags after confirming the 25-CA passage on pages 36-37.

Extractor-added row flags:

- `date_inferred_from_context` on raw BidderIDs 5-28 is acceptable. The 24 non-New-Mountain 2014 NDA rows are inferred from "During the next several weeks" after the February 27 board authorization, with page 36-37 evidence.
- `bidder_type_ambiguous` on raw BidderIDs 10-28 is acceptable. The filing does not identify the 19 silent NDA signers as strategic or financial; defaulting to financial with a soft ambiguity flag follows §F2.
- `bid_range` on raw BidderIDs 30-35 and 37 is correct. The filing states ranges, and `rules/bids.md` §H1 requires range bids to populate lower/upper, not `bid_value_pershare`.
- `unsolicited_first_contact` on raw BidderID 35, Party X, is correct because Party X contacted BofA unsolicited, bid, and withdrew before data-room access or management meetings.
- `unsolicited_first_contact` on raw BidderID 37, Party Y, should be removed or replaced. Party Y did not withdraw before diligence; the filing says data-room access was subsequently made available and management met with Party Y. This falls outside §D1.a's exemption conditions.
- `drop_identity_ambiguous` on raw BidderIDs 38-43 is correctly raised, but the row labels should be made less specific. The filing identifies six remaining bidders as a group and does not map which five were unable to proceed versus which one stopped responding.
- `nda_revived_from_stale` on raw BidderID 49 is correct. Page 40 explicitly extends New Mountain's original confidentiality, standstill, and employee non-solicitation provisions into the restarted 2015 phase.

## Material diff adjudication

### Deal-level fields

- `TargetName`: AI correct, Alex wrong. The filing's registrant line on page 1 is "Zep Inc." Alex's all-caps `ZEP INC` is EDGAR/header styling, not the filing-verbatim company name for the deal identity field.
- `Acquirer`: AI correct, Alex wrong only in casing. The economic buyer is New Mountain Capital; page 2 describes Parent as indirectly owned by funds advised by New Mountain Capital. Alex's all-caps value should be normalized to filing casing.
- `DateEffective`: AI correct, Alex wrong for this extraction. The same proxy filing predates closing and does not state a June 26, 2015 effective/closing date. Per `prompts/extract.md`, `DateEffective` stays null unless the same filing explicitly states it.

### Target Sale / IB

- Raw BidderID 1 `Target Sale`, 2014-01-28: AI correct. Page 35 says the board decided to engage in a process to consider strategic alternatives.
- Raw BidderID 2 `IB`, 2014-01-28: AI correct. Pages 35-36 say the board approved the BofA Merrill Lynch engagement letter at that meeting.
- Raw BidderID 3 `Target Sale`, 2014-02-27: AI wrong. The February 27 board action approved next steps in an already-launched process. It is useful context, but it is not a second `Target Sale` event under §D1.
- Alex row 1 `Target Sale` dated rough 2014-01-31 and aliased to BofA Merrill Lynch: Alex wrong. January 31 was a Board Representatives / BofA next-steps meeting, not the board's sale-process decision; the target-side event should not be aliased to BofA.

Verdict for the `Target Sale` cardinality bucket: both wrong as emitted. Correct target state is one `Target Sale` row dated 2014-01-28 plus one `IB` row dated 2014-01-28.

### March 2014 NDA count

- Raw BidderID 4 `New Mountain Capital` `NDA`, 2014-03-19: AI correct. Page 37 explicitly states the March 19 confidentiality agreement and identifies New Mountain as one of the financial buyers.
- Raw BidderIDs 5-28, 24 other March 2014 NDA placeholders: AI substantially correct. Pages 36-37 state 25 potential buyers executed confidentiality agreements. One is New Mountain, so 24 additional NDA rows are needed. The first five of those can be promoted to the later April 14 bidder composition (four financial, one strategic); the remaining 19 must remain silent placeholders.
- Alex row 3 `24 parties` `NDA`: Alex wrong under the current rulebook. It preserves the count but violates the atomization rule for numeric-count NDAs.
- Alex row 19 `Party Y` `NDA`: both defensible, but unresolved under the current rules. Page 38 says data-room access was made available to Party Y after its bid, which strongly implies confidentiality protection in ordinary M&A practice, but the filing does not explicitly state that Party Y executed a confidentiality agreement. A plain unflagged `NDA` row is stronger than the text supports unless the rulebook accepts data-room access as implied NDA evidence.
- Raw BidderID 49 `New Mountain Capital` `NDA`, 2015-02-27: AI correct, Alex missing. Page 40 explicitly extends the original confidentiality provisions in the restarted phase.

Verdict for the `NDA` residual bucket: AI mostly correct, Alex mostly wrong, with Party Y requiring a rule/prompt decision.

### Final-round rows

Alex-only rows 4 (`Final Round Inf Ann`), 13 (`Final Round Inf`), and 14 (`Final Round`) are unsupported. AI correctly omits them.

- March 27, 2014 process letter: page 37 says first-round non-binding indications were due April 14. This is a first-round process letter, not a final-round announcement.
- April 14, 2014 indications: page 37 says five preliminary non-binding indications were received. It does not say final-round bids were submitted.
- May 7, 2014 data-room access: page 37 says data-room access was made available for diligence. It does not announce a final bid deadline, and no final bids were later submitted.

Verdict: AI correct, Alex wrong.

### April 14, 2014 preliminary bids

- Raw BidderIDs 30-34: AI correct on count, bidder composition, date, bid type, and range treatment. Page 37 says five parties, four financial and one strategic, submitted preliminary non-binding indications on April 14, and the bids ranged from $20.00 to $22.00.
- Alex rows 6-10: Alex partially correct on count but wrong on value allocation. The filing does not identify one bidder at $20, one at $22, and three with $20-$22 ranges. Alex's allocation comes from his own ambiguous workbook note, not the filing.
- Recommended extraction polish: add an `aggregate_basis` or clearer note to raw BidderIDs 30-34 stating that the $20-$22 range is the filing's aggregate range across the five preliminary bids, not a bidder-specific range.

Verdict: AI correct, Alex wrong, with a non-blocking AI clarity improvement.

### New Mountain 2014 dropout

- Raw BidderID 29 `DropAtInf`: AI correct to include a dropout and better than Alex's generic `Drop` code. Page 37 says New Mountain received the materials and first-round process letter but decided not to submit a preliminary indication.
- Raw BidderID 29 date 2014-03-27: AI likely wrong. The event is New Mountain's non-submission by the April 14 first-round deadline, or at least a decision sometime after the March 27 process letter and before/no later than April 14. The source quote does not support March 27 as the decision date.
- Alex row 11 `Drop`, 2014-04-14: Alex is closer on date but less precise on dropout code.

Verdict: both wrong as emitted. Correct row should be New Mountain `DropAtInf`, dated 2014-04-14 or explicitly flagged as inferred from the March 27 process letter / April 14 deadline.

### Party X

- Raw BidderID 35 `Bid`, 2014-05-09, informal range $21.50-$23.00: AI correct. Page 37 states the exact range. `bid_value_pershare` should be null under §H1.
- Alex row 15 `Bid`, 2014-05-09, `bid_value_pershare=21.5`: Alex wrong on `bid_value_pershare`; the lower bound is not a point bid.
- Raw BidderID 36 `DropAtInf`, 2014-05-14: AI correct. Page 38 says Party X was no longer interested before data-room access or management meeting. Alex's generic `Drop` row is less specific.
- `bidder_type.public`: AI correct relative to the current schema; Alex's `public=null` is converter/reference policy drift.

Verdict: AI correct, Alex wrong.

### Party Y

- Raw BidderID 37 `Bid`, 2014-05-20, informal range $19.50-$20.50: AI correct on date, range, and `bid_value_pershare=null`. Alex row 20 incorrectly copies the lower bound into `bid_value_pershare`.
- Raw BidderID 37 `bidder_type.base=s`, `public=false`: AI correct under current §F2/F1. Page 37 describes Party Y as one strategic party; the filing does not state it is publicly traded.
- Raw BidderID 37 `unsolicited_first_contact`: AI wrong. Page 38 says Party Y received data-room access and a management presentation after its bid, so the row does not satisfy §D1.a's "withdraws before any NDA is signed" condition.
- Alex row 19 `Party Y` `NDA`: defensible but not proven. Page 38's data-room access language is strong circumstantial evidence but does not explicitly say Party Y signed a confidentiality agreement.

Verdict: mixed. AI correct on the bid fields; AI wrong on the exemption flag. Alex's Party Y NDA is a defensible interpretation only if the rulebook accepts data-room access as enough NDA evidence.

### Six remaining 2014 bidders drop out

- Filing: page 38 says the draft merger agreement was distributed to six remaining bidders on May 22; over the next few weeks, five were unable to proceed and the sixth declined to respond.
- Raw BidderIDs 38-43: AI correct to emit six rows and correct to flag identity ambiguity. It is also reasonable to infer a rough date around 2014-06-12 from "over the next few weeks" after May 22.
- Raw BidderIDs 38-42 `DropAtInf` assigned to Financial Buyer 1-4 and Strategic Buyer 1, plus raw BidderID 43 `Drop` assigned to Party Y: AI over-allocates facts. The filing does not identify which five were unable to proceed or which one stopped responding.
- Alex rows 21-22 (`5 parties` and `Party Y`) are wrong under the current atomization rule and use an unsupported rough date of May 23. Alex's row 21 comment itself asks what date should be used.

Verdict: both wrong as emitted. Correct extraction should contain one dropout row for each of the six remaining bidders, all carrying the group quote and an ambiguity flag; use generic `Drop` unless the rulebook decides it is acceptable to assign `DropAtInf` to all six because every outcome reflects failure to continue at the informal stage.

### Termination

- Raw BidderID 44 `Terminated`, 2014-06-26: AI correct. Page 38 states the board decided at a June 26 meeting to terminate the process.
- Alex row 17 has the same underlying event but stores the date in legacy rough form.

Verdict: AI correct, Alex wrong on date representation.

### 2015 restart and New Mountain bids

- Raw BidderID 45 `Restarted`, 2015-02-10: AI correct. Page 39 says New Mountain met BofA on February 10 and expressed interest after the 2014 process had been terminated.
- Raw BidderID 46 `Bidder Interest`, 2015-02-10: AI correct. The same page supports an interest row before any 2015 price proposal.
- Alex row 18 `Restarted`, rough 2015-02-19: Alex wrong. February 19 is the first 2015 price indication, not the restart.
- Raw BidderID 47 `Bid`, 2015-02-19, $19.25 informal: AI correct. Alex row 23 incorrectly dates this bid to February 10.
- Raw BidderID 48 `Bid`, 2015-02-26, $20.05 informal: AI correct. Page 39 states the revised indication and increased price.
- Raw BidderID 50 `Bid`, 2015-03-13, $20.05 formal: AI correct. Page 40 states New Mountain communicated that $20.05 was its "best and final" offer.
- Alex row 25 `Bid`, 2015-03-29 formal: Alex wrong. March 29 is a revised draft merger agreement date, not the price communication date.
- Raw BidderID 51 `Bid`, 2015-04-06, $20.05 formal: AI wrong as a separate event. Page 41 says New Mountain reiterated its previous position during April negotiations. This is a reaffirmation of the March 13 best-and-final price, not a new bid or revised offer.

Verdict: AI mostly correct, Alex wrong on the February 10/19 and March 13/29 bid dates. Remove or merge raw BidderID 51.

### Executed

- Raw BidderID 52 `Executed`, 2015-04-07: AI correct. Page 42 says the board approved the transaction at the April 7 meeting and, following that meeting, the parties executed the merger agreement. The April 8 press release is folded into `Executed` but should not drive the event date.
- Alex row 26 rough 2015-04-08: Alex wrong for the execution date, though April 8 is correct for the announcement morning.

Verdict: AI correct, Alex wrong.

### Deal terms not surfaced in the markdown diff

The raw AI deal-level fields for `go_shop_days=30`, `termination_fee=17500000.0`, and `reverse_termination_fee=33750000.0` are supported by pages 41-42. Page 41 also supports the $8.75 million go-shop termination fee, but the current deal schema appears to store only one termination fee plus reverse fee. Alex's null values should not be treated as ground truth.

## Extraction-side fixes needed

1. Delete raw BidderID 3 or fold its source quote into raw BidderID 1 / comments. Keep only one `Target Sale` event dated 2014-01-28.
2. Update raw BidderID 29 to `bid_date_precise=2014-04-14` with a date-inference note, or use a rough/inferred date anchored to the March 27 process letter and April 14 deadline. Keep `DropAtInf`.
3. Keep raw BidderIDs 5-28 as atomized March 2014 NDA placeholders. Do not add synthetic drops for BidderIDs 10-28 solely to silence validator soft flags.
4. Add `aggregate_basis` or a clearer `additional_note` to raw BidderIDs 30-34 explaining that $20.00-$22.00 is the aggregate range across the five April 14 preliminary indications.
5. Remove `unsolicited_first_contact` from raw BidderID 37. Resolve Party Y through a rule decision: either add an explicitly flagged/implied NDA row based on data-room access, or leave no NDA and accept/handle the validator issue explicitly.
6. Rework raw BidderIDs 38-43 so they do not assign the five "unable to proceed" outcomes to named placeholders. Prefer six generic `Drop` rows, all with `drop_identity_ambiguous` and the page 38 group quote.
7. Remove raw BidderID 51 as a separate bid row. Preserve the April price-reaffirmation language as an `additional_note` on raw BidderID 50 if desired.
8. Keep raw BidderIDs 45, 46, 47, 48, 49, 50, and 52 with the current dates and citations.

## Reference-side corrections needed

1. Normalize `TargetName` to `Zep Inc.` and `Acquirer` to `New Mountain Capital`; set `DateEffective=null` for this proxy-based extraction.
2. Replace Alex row 1 with a single target-side `Target Sale` dated 2014-01-28; do not alias the target-side event to BofA.
3. Convert Alex's grouped `24 parties` NDA row into 24 atomized NDA placeholders, plus the matched New Mountain NDA, so the reference reflects the filing's 25-CA count and current §E2.b / §E5 rules.
4. Delete Alex final-round rows 4, 13, and 14 unless Austin makes a new rule that first-round process letters and diligence access count as final rounds. Under current §K2, they do not.
5. Replace Alex's April 14 bid value allocation with five atomized preliminary bid rows carrying the aggregate $20.00-$22.00 filing range and a note that individual bid values are not identified.
6. Change New Mountain's 2014 dropout from generic `Drop` to `DropAtInf`, with an inferred deadline-based date.
7. Keep Party X and Party Y bid values as ranges only; remove lower-bound values from `bid_value_pershare`.
8. Replace Alex's grouped 2014 dropout rows with six atomized ambiguous dropout rows, dated from "over the next few weeks" after May 22.
9. Date New Mountain's 2015 restart / interest to 2015-02-10, the $19.25 bid to 2015-02-19, and the formal best-and-final $20.05 bid to 2015-03-13.
10. Add New Mountain's 2015 NDA revival/extension row dated 2015-02-27.
11. Date `Executed` to 2015-04-07 rather than April 8.
12. If the reference includes deal terms, fill go-shop and fee fields from pages 41-42 rather than leaving them null.

## Rule / prompt recommendations

1. Add a rule for data-room-access-implied NDAs. Zep Party Y is the concrete case: page 38 gives data-room access and management presentation but no explicit "confidentiality agreement" sentence. The rule should say whether data-room access is sufficient NDA evidence, and if yes require a flag such as `nda_inferred_from_data_room_access` with the supporting quote.
2. Tighten `unsolicited_first_contact`: the extractor should not attach it when an unsolicited bidder continues into diligence or management meetings. Party X qualifies; Party Y does not.
3. Clarify aggregate range handling for multiple unnamed bids. When the filing says "five bids ranged from X to Y" without bidder-specific values, the extractor should atomize five bid rows but must mark the range as aggregate, not bidder-specific.
4. Clarify ambiguous group-drop representation. When the filing says "five of six did X and the sixth did Y" without identities, the extractor should not assign X/Y to specific aliases. Prefer all rows generic `Drop` plus `drop_identity_ambiguous`, or document a deterministic convention.
5. Add a prompt self-check for price reaffirmations. Repeated "best and final" language can be a real bid if it is the first formalization, but a later reiteration during merger-agreement negotiation should usually be an `additional_note`, not a new `Bid` row.

## Confidence

High confidence on the main chronology, the unsupported Alex final-round rows, the 2014 NDA/bid atomization, the bid range treatment, New Mountain's 2015 bid dates, and the April 7 execution date.

Medium confidence on the best representation of Party Y's implied NDA and the six ambiguous 2014 dropout rows. The filing text is clear about the facts, but the current rulebook needs one more explicit convention for data-room-implied confidentiality agreements and unmapped group dropout outcomes.

# Penford adjudication - 2026-04-27 production ref9

Fresh diff: `scoring/results/penford_20260427T200927Z.md`

Ground truth reviewed: `data/filings/penford/pages.json`

## Summary

Reviewed every divergence in the fresh Penford diff: 3 deal-level disagreements, 2 matched field disagreements, 3 cardinality buckets, 1 matched date mismatch, 12 AI-only rows, and 8 Alex-only rows.

Headline adjudication counts, consolidated into tightly related buckets:

| Verdict | Buckets |
|---|---:|
| ai-right | 13 |
| alex-right | 0 |
| both-defensible | 0 |
| both-wrong | 3 |
| needs-Austin | 0 |

Main conclusions:

- The AI is right on the deal identity fields, `DateEffective = null`, range-bid structure, IB coverage, the execution date, SEACOR activist row, the current-process Bidder Sale / Target Sale additions, and the narrated Party B / Party D drops.
- Two AI buckets need correction despite mostly useful extraction: the stale 2007/2009 prior approaches should use generic `Drop`, not `DropAtInf`; the July 8 Ingredion voicemail should not be a `Bidder Interest`.
- The October 4 Party A value indication is mixed: AI has the right date, but the filing supports the prior range of `$17.50 - $18.00`, not only an upper bound.
- No divergence requires an Austin-only decision.

## Deal-level disagreements

### TargetName, Acquirer, DateEffective

Verdict: ai-right.

Evidence:

- Page 2 identifies the transaction as the merger agreement "by and among Penford Corporation, Ingredion Incorporated, and Prospect Sub, Inc." and states that Penford would become 100% owned by Ingredion.
- Page 8 describes Prospect Sub, Inc. as a wholly owned subsidiary organized solely to complete the merger, confirming Ingredion Incorporated is the operating acquirer.
- The proxy is dated December 29, 2014 and asks shareholders to vote at a January 29, 2015 special meeting; page 2 says "If the merger is completed," so this filing predates closing. No filing page reviewed states a March 11, 2015 effective date.

Action implication: update reference. Keep AI `TargetName = "Penford Corporation"`, `Acquirer = "Ingredion Incorporated"`, and `DateEffective = null`. No rule change.

## Matched/cardinality divergences

### Range bid fields: Ingredion 2014-09-17 and Party A 2014-10-13

Verdict: ai-right.

Evidence:

- Page 35 says Ingredion could increase its proposal from `$18.00` to `$18.25 or $18.50 per share`.
- Page 38 says Party A's value range was reduced from `$17.50 - $18.00` to `$16.00 - $18.00 per share`.
- Current `rules/bids.md` says true ranges populate `bid_value_lower` and `bid_value_upper`; `bid_value_pershare` is not populated for a range.

Action implication: update reference. Alex's `bid_value_pershare = 18.25` and `16` on these range rows should be removed; keep lower / upper bounds. No rule change.

### Bidder Interest residual bucket

Verdict: both-wrong.

Evidence:

- Page 30 says Ingredion's July 8 voicemail sought a meeting but "did not indicate the purpose of the meeting"; that does not support a bidder-interest row.
- Page 30 says that on July 17, Ingredion advised Penford of its interest in acquiring Penford; this supports `Bidder Sale`, not a July 20 `Bidder Interest`.
- Page 34 supports the market-check interest rows: Party B expressed interest on September 9, Party C expressed interest on September 10, and Party D expressed interest on September 11.

Action implication: update extraction and reference. Delete AI's July 8 Ingredion `Bidder Interest`; keep AI's separate July 17 Ingredion `Bidder Sale`; add / keep Party B, Party C, and Party D `Bidder Interest` rows on September 9, 10, and 11. Replace Alex's July 20 Ingredion `Bidder Interest` with the supported July 17 `Bidder Sale` plus the July 20 NDA. No rule change.

### IB residual bucket

Verdict: ai-right.

Evidence:

- Page 31 says representatives of Deutsche Bank attended the August 11 meeting and Deutsche Bank reviewed Ingredion's proposal and analysis with the Executive Committee. Under the IB date-anchor rule, this is Deutsche Bank's first narrated advisory action.
- Page 33 says J.P. Morgan Securities attended the August 21 management presentation as Ingredion's financial advisor.

Action implication: update reference. Keep AI rows for Deutsche Bank on August 11 and J.P. Morgan Securities on August 21. No rule change.

### Bid residual bucket: Party A October 4 and Alex's Ingredion October 8 bid

Verdict: both-wrong.

Evidence:

- Page 37 says that on October 4, Deutsche Bank followed up with Party A, and Party A indicated any offer would be below `$17.50 - $18.00 per share in cash`. Page 38 later describes the October 13 range as reduced "from $17.50 - $18.00 per share to $16.00 - $18.00 per share," confirming the earlier range.
- Page 37 says October 8 involved Sidley Austin circulating a revised merger-agreement draft and Party D declining to move forward. It does not narrate an Ingredion bid on October 8.

Action implication: update extraction and reference. The October 4 Party A row should use date `2014-10-04` and range `17.5` to `18.0`; AI should add the lower bound, and Alex should move the row from October 3 to October 4. Drop Alex's October 8 Ingredion formal bid. No rule change.

### Ingredion Executed date

Verdict: ai-right.

Evidence:

- Page 38 says that on October 14, Mr. Fortnum confirmed the proposed `$19.00` price and discussed finalizing the draft merger agreement.
- Page 39 says that during the evening on October 14, Penford and Ingredion finalized and executed the merger agreement; press releases were issued on October 15.
- Page 37's October 8 event is only circulation of a revised draft merger agreement.

Action implication: update reference. `Executed` should be dated `2014-10-14`, not `2014-10-08`. No rule change.

## AI-only rows

### 2007 and 2009 industry-party prior approaches

Rows covered: AI-only `2007 industry party` Bidder Sale / NDA / DropAtInf; AI-only `2009 industry party` Bidder Sale / NDA / DropAtInf.

Verdict: both-wrong.

Evidence:

- Page 29 says that in 2007 and 2009 Penford received unsolicited indications of interest from two industry parties, entered into confidentiality agreements in each case, exchanged information, and that the discussions did not result in offers.
- The "indications of interest to acquire Penford" support `Bidder Sale` rows for both stale prior approaches.
- The confidentiality-agreement language supports one NDA row for each stale prior approach.
- "These discussions did not result in offers" supports a drop outcome, but it does not identify bidder-initiated withdrawal. Under the agency requirement, this should default to generic `Drop`, not `DropAtInf`.
- Year-only dates map to July 1 under `rules/dates.md`; Alex's January 15 rough dates are not the current rule.

Action implication: update extraction and reference. Keep AI's two `Bidder Sale` rows and two NDA rows with year-only July 1 inferred dates; change AI's two `DropAtInf` rows to generic `Drop`; update the reference to include the missing `Bidder Sale` rows and current date mapping. No rule change.

### SEACOR Activist Sale on 2014-07-11

Verdict: ai-right.

Evidence:

- Page 30 says SEACOR filed a Schedule 13D amendment stating its intent to nominate four directors.
- Page 31 says Penford management and the Executive Committee discussed the SEACOR Filing.
- Page 32 says Deutsche Bank identified SEACOR as a possible acquisition counterparty, and the Executive Committee determined that the chairman should contact SEACOR's representative to ask whether SEACOR had interest in acquiring the Company.

Action implication: update reference. Keep the SEACOR `Activist Sale` row. No rule change.

### Ingredion Bidder Sale on 2014-07-17

Verdict: ai-right.

Evidence:

- Page 30 says Ingredion's CEO advised Penford's CEO of Ingredion's interest in acquiring Penford.
- The same passage discusses valuation reference points and a follow-up meeting with Ingredion's CFO to discuss valuation.

Action implication: update reference. Keep AI's July 17 `Bidder Sale`; do not use Alex's July 20 `Bidder Interest` as the start-of-process row. No rule change.

### Party A Bidder Sale on 2014-08-11

Verdict: ai-right.

Evidence:

- Page 32 says Party A's CEO informally discussed Party A's potential interest in acquiring or combining with Penford and discussed how Party A would value Penford.

Action implication: update reference. Keep the Party A `Bidder Sale` row. No rule change.

### Target Sale on 2014-08-28

Verdict: ai-right.

Evidence:

- Page 33 says the board discussed the market-check process and authorized management and Deutsche Bank to proceed with the market check while continuing negotiations with Ingredion.

Action implication: update reference. Keep the `Target Sale` row. No rule change.

### Party B DropAtInf on 2014-09-12

Verdict: ai-right.

Evidence:

- Page 34 says Party B informed Deutsche Bank that it had decided not to move forward with discussions or sign a nondisclosure agreement.

Action implication: update reference. Keep `DropAtInf` for Party B. No rule change.

### Party D DropAtInf on 2014-10-08

Verdict: ai-right.

Evidence:

- Page 37 says Party D indicated that it did not intend to move forward with discussions regarding a potential transaction.

Action implication: update reference. Keep AI's `DropAtInf`; replace Alex's generic Party D `Drop`. No rule change.

## Alex-only rows

### 2007 and 2009 generic NDA / Drop rows

Rows covered: Alex-only `1 party` NDA, `A diffferent party` NDA, `1 party` Drop, `A diffferent party` Drop.

Verdict: both-wrong.

Evidence:

- Page 29 supports two stale prior industry-party approaches, two confidentiality agreements, and failed discussions.
- The reference omits the supported `Bidder Sale` rows and uses obsolete rough-date handling.
- For drops, Alex's generic `Drop` code is better supported than AI's `DropAtInf`, but the reference still needs current date mapping and the missing initiation rows.

Action implication: update reference and extraction as described in the stale-prior AI-only bucket. No rule change.

### Final Round Ann

Verdict: ai-right.

Evidence:

- Page 37 says the board directed management to negotiate and finalize a definitive agreement with Ingredion. It does not invite a bidder subset to submit final proposals, send process letters, or announce a final round.

Action implication: update reference. Delete Alex's `Final Round Ann`. No rule change.

### Party D Drop on 2014-10-08

Verdict: ai-right.

Evidence:

- Page 37 states Party D "did not intend to move forward," which is a voluntary informal-stage withdrawal.

Action implication: update reference. Use AI's `DropAtInf`, not generic `Drop`. No rule change.

### Party A Drop on 2014-10-14

Verdict: ai-right.

Evidence:

- Page 38 says Party A provided a formal letter with an indication of interest at `$16.00 per share` on October 14. It does not say Party A withdrew or that Penford dropped Party A on October 14.
- Page 39 says Penford executed the Ingredion agreement that evening, but the execution with Ingredion alone is not a narrated Party A drop.

Action implication: update reference. Delete Alex's Party A `Drop`. No rule change.

### Party C Drop on 2014-10-14

Verdict: ai-right.

Evidence:

- Page 34 says Party C executed an NDA on September 15.
- Page 35 says Party C received a management presentation on September 25.
- The filing does not narrate a Party C withdrawal on October 14. AI already emits a `DropSilent` row, which is filtered out of the diff under the current scoring note.

Action implication: update reference. Delete Alex's dated generic Party C `Drop`; keep the AI `DropSilent` convention for silent NDA signers. No rule change.

## Rulebook/reference implications

- Reference updates needed:
  - Deal identity: use filing-verbatim `Penford Corporation` and `Ingredion Incorporated`; set `DateEffective = null`.
  - Range bids: remove `bid_value_pershare` on true ranges and keep lower / upper bounds.
  - Add missing current-process rows supported by the filing: SEACOR `Activist Sale`, Ingredion July 17 `Bidder Sale`, Party A August 11 `Bidder Sale`, August 28 `Target Sale`, Party B / C / D interest rows, Party B `DropAtInf`, Party D `DropAtInf`, and the acquirer-side J.P. Morgan `IB` row.
  - Delete unsupported Alex rows: July 20 Ingredion `Bidder Interest`, October 8 Ingredion formal bid, October 8 `Executed`, `Final Round Ann`, Party A October 14 `Drop`, and Party C October 14 generic `Drop`.
  - Regenerate stale 2007/2009 prior rows to include `Bidder Sale`, NDA, and generic `Drop` for each prior industry party with current year-only date mapping.
- Extraction prompt / rulebook updates needed: none. The observed extraction errors are application errors under existing rules, not gaps in the rulebook.
- Extraction corrections needed before treating Penford as clean:
  - Delete AI's July 8 Ingredion `Bidder Interest`.
  - Change stale-prior `DropAtInf` rows to generic `Drop`.
  - Add `bid_value_lower = 17.5` to the October 4 Party A range row.
- Austin decision needed: none.

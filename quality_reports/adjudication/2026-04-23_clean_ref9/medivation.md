# Medivation adjudication — clean reference-9 run

Run artifact reviewed: `/tmp/sec_extract_ref9_clean/medivation.raw.json` directly, plus `data/filings/medivation/pages.json`, `reference/alex/medivation.json`, and `scoring/results/medivation_20260423T212321Z.{md,json}`. SEC filing text is treated as ground truth. Raw extraction row identifiers below refer to raw `BidderID`; the diff report uses finalized/canonicalized IDs, so raw rows 15 and 16 appear swapped after chronological finalization.

## Status / disposition

**Disposition: pass with extraction fixes needed.** The AI is materially better than Alex on the Sanofi receipt date, public-announcement date, target rejection, financial-advisor rows, July 5 NDA atomization, and omission of synthetic August 20 drops. However, the raw extraction should be corrected before treating Medivation as clean:

- Delete raw row 10 (`Target Sale`, 2016-06-28) or recode only if the rulebook wants a `Target Interest` row for target advisors approaching Pfizer. The cited text is a Pfizer-specific confidential-information/NDA setup, not a board-level target sale decision.
- Delete raw row 15 (`Final Round Inf Ann`, 2016-07-19). The July 19 letter requested an initial non-binding preliminary proposal and expressly contemplated that a later limited subset might be invited; it was not itself a final-round invitation.
- Revisit final-round structure around August 10 / August 14 / August 19 / August 20. The AI’s Aug. 10 `Final Round Ann`, Aug. 19 `Final Round`, and Aug. 19 `Final Round Ext Ann` are broadly defensible, but the source/evidence mapping should be made internally consistent. If the current K1/K2 contract requires a no-`Ann` event for extension submissions, the AI may also be missing an Aug. 20 `Final Round Ext` row.
- Normalize placeholder aliases for the July 5 unnamed NDA parties if strict §E5 naming is required. The AI used `Unidentified party 1/2`; rule text suggests type-based placeholders such as `Financial 1/2` when ambiguity defaults to `f`.

Reference-side corrections are also needed: Alex’s April 13 dates are not receipt/publication dates; the single J.P. Morgan IB row undercounts advisors and uses the wrong role/date; the Aug. 20 Sanofi/Party A/Party B drops are not supported by bidder-specific withdrawal/cut language in this filing.

## Evidence basis

Key filing passages:

- p.24: Sanofi’s first concrete proposal was **received** April 15 even though the letter was dated April 13: “received a letter dated April 13, 2016 ... non-binding proposal ... $52.50 per share.”
- p.25: Sanofi public announcement and rejection: “Sanofi’s proposal was publicly announced on April 28, 2016 and unanimously rejected ... on April 29, 2016.”
- p.25: Pfizer May 2 interest: “expressed Pfizer’s interest in a possible transaction when, and if, Medivation decided to pursue such a transaction.”
- p.25: Advisor evidence: “Centerview ... a financial advisor to Pfizer” contacted “J.P. Morgan” and “Evercore ... financial advisors to Medivation” on May 11.
- p.25: Pfizer May 20 sale intent: “reiterated Pfizer’s interest in pursuing a negotiated transaction with Medivation.”
- p.25: Sanofi activist pressure: “filed with the SEC a preliminary consent solicitation seeking to remove and replace Medivation’s Board.”
- p.25: Pfizer NDA: “On June 29, 2016, Pfizer executed a confidentiality and standstill agreement.”
- p.25: Sanofi/unnamed NDAs: “On July 5, 2016, Medivation issued a press release announcing that it had entered into confidentiality agreements with several parties, including Sanofi.”
- p.25: Guggenheim first advisor evidence: “On July 7 through July 11, 2016, representatives of Pfizer, Guggenheim ... a financial advisor to Pfizer, and Centerview had discussions...”
- p.26: July 19 initial process letter: “requesting that Pfizer submit a written, non-binding preliminary proposal ... on August 8” and only later “a limited number of qualified parties may be invited.”
- p.26: Pfizer Aug. 8 bid: “non-binding preliminary proposal ... $65.00 per Share” and “not subject to any financing condition.”
- p.26: Aug. 10 subset invitation: Medivation invited Pfizer “to a subsequent round ... together with several other interested parties.”
- p.26: Aug. 14 process letter: advisors requested a merger-agreement markup on Aug. 18 and “a definitive proposal ... on August 19.”
- p.27: Pfizer Aug. 19 bid and best-and-final request: revised written proposal at `$77.00` and instruction that Pfizer “should submit its ‘best and final’ offer” Aug. 20.
- p.27: Pfizer Aug. 20 final bid and execution: best-and-final proposal at `$81.50`; the Board approved; Pfizer, Purchaser, and Medivation executed the Merger Agreement that afternoon.

## Validator-flag interpretation

- Raw row 1 `pre_nda_informal_bid` is appropriate. Sanofi made a concrete `$52.50` non-binding proposal before the later July 5 NDA disclosure, and §C4 says this is an informal `Bid`, not a duplicate `Bidder Sale`.
- Raw rows 5-7 and 16 `date_inferred_from_context` are appropriate. The filing identifies the banks as acting as financial advisors but does not narrate actual retention dates; §J1 says to use first narrated advisor action with this soft flag.
- `resolved_name_not_observed` on Pfizer and advisor registry entries is a registry hygiene issue, not a substantive extraction problem. The filing often observes shortened aliases (`Pfizer`, `Centerview`, `J.P. Morgan`, `Evercore`, `Guggenheim`) while the registry resolved names use legal suffixes. Either include both aliases in `aliases_observed` or relax that validator for legal-suffix expansions.
- Raw row 12 `unnamed_count_placeholder` is correct: “several parties, including Sanofi” supports at least three NDA parties total under §E5.
- Raw rows 13-14 `bidder_type_ambiguous` are correct. The unnamed NDA parties are not typed by the filing; defaulting to `f` with a soft flag follows §F2.
- Validator `nda_without_bid_or_drop` on the unnamed NDA parties is expected and should not be fixed by synthetic drops. §I1 explicitly says NDA-only rows with no bidder-specific follow-up remain as NDA-only.
- Raw row 15 `round_structure_code_ambiguous` correctly identifies the problem, but the row should not be force-fit into `Final Round Inf Ann`.
- `final_round_inferred` on raw rows 18, 19, and 21 is reasonable, but the final-round cluster should be reviewed for exact row taxonomy and dates as noted below.

## Material diff adjudication

### Deal-level fields

- `TargetName`: **AI correct / Alex wrong.** AI `Medivation, Inc.` preserves filing-verbatim casing/punctuation; Alex `MEDIVATION INC` is workbook normalization.
- `Acquirer`: **AI correct / Alex wrong.** AI `Pfizer Inc.` preserves filing-verbatim casing/punctuation; Alex `PFIZER INC` is workbook normalization.
- `DateEffective`: **AI correct / Alex wrong for this filing.** The Offer to Purchase states the tender-offer expiration date as September 27, 2016 and defines future `Effective Time`, but the reviewed filing does not state that the merger became effective September 28, 2016. Per project convention, `DateEffective` should remain `null` unless this same filing explicitly states closing/effectiveness.

### Sanofi opening sequence

- Raw row 1 `Sanofi` `Bid` dated 2016-04-15 vs Alex `Bid` dated 2016-04-13: **AI correct / Alex wrong.** §B5 anchors incoming communications on receipt date. The filing says received April 15, letter dated April 13.
- Alex-only `Sanofi` `Bidder Sale` dated 2016-04-13: **AI correct / Alex wrong.** §D1.a says an unsolicited first-contact bid is represented by the `Bid` row only; do not add a duplicate standalone `Bidder Sale`.
- Raw row 2 `Sanofi` `Bid Press Release` dated 2016-04-28 vs Alex `Bid Press Release` dated 2016-04-13 with no bidder: **AI correct / Alex wrong.** The filing’s public-announcement date is April 28.
- Raw row 3 `Sanofi` `DropTarget` dated 2016-04-29: **AI correct / Alex omission wrong.** Medivation’s Board unanimously rejected Sanofi’s proposal on April 29; `DropTarget` is the right agency because the target rejected the proposal.
- Sanofi `bidder_type` difference hidden by the date mismatch: **AI defensible under filing-only policy; Alex reflects external/common-knowledge typing.** Pages 24-27 do not state that Sanofi is non-U.S. or publicly traded. If the project wants public/non-U.S. inferred from known company identity, that is a policy change; do not silently make it a prompt fix.

### Pfizer pre-NDA and advisor rows

- Raw row 4 `Pfizer` `Bidder Interest` dated 2016-05-02: **AI correct / Alex omission wrong.** Pfizer expressed interest in a possible transaction only if Medivation pursued one; no price or concrete proposal appears in that passage.
- IB residual bucket: raw rows 5 `Centerview`, 6 `J.P. Morgan`, 7 `Evercore`, and 16 `Guggenheim` vs Alex one `J.P. Morgan` `IB` row dated 2016-06-29: **AI correct / Alex wrong.** §J1 requires one `IB` row per named financial advisor on either side. The filing identifies Centerview as Pfizer’s advisor and J.P. Morgan/Evercore as Medivation’s advisors on May 11, and Guggenheim as Pfizer’s advisor on July 7-11. Alex also incorrectly leaves the role as bidder-side rather than `advisor_financial`.
- Raw row 8 `Pfizer` `Bidder Sale` dated 2016-05-20: **AI correct / Alex omission wrong.** The passage says Pfizer reiterated interest in pursuing a negotiated transaction with Medivation; this is a concrete intent-to-buy signal even without price.
- Raw row 9 `Sanofi` `Activist Sale` dated 2016-05-25: **AI correct / Alex omission wrong.** Sanofi’s consent solicitation to replace the Board is activist pressure preceding/inside the process.
- Raw row 10 `Target Sale` dated 2016-06-28: **AI wrong / Alex correct to omit as coded.** The passage says Medivation’s advisors contacted Pfizer about providing confidential information subject to a confidentiality and standstill agreement. That supports the June 29 Pfizer NDA row and perhaps a target-specific outreach event if rulebook wants one, but it is not evidence that the target board resolved to sell or publicly/private launched a sale process at that moment.
- Raw row 11 `Pfizer` `NDA` dated 2016-06-29: **AI correct.** The filing explicitly says Pfizer executed a confidentiality and standstill agreement on June 29.

### July 5 NDA atomization

- Raw row 12 `Sanofi` `NDA` dated 2016-07-05 vs Alex `Sanofi` NDA with rough date: **both defensible, AI more operationally useful.** The filing gives July 5 as the press-release announcement date for confidentiality agreements already entered into; it does not state each execution date. Using July 5 as the extracted NDA anchor is reasonable, but the row should be understood as “announced by July 5,” not necessarily signed that day.
- Raw rows 13-14 unnamed NDA parties dated 2016-07-05 vs Alex `Party A`/`Party B` rough-date rows: **AI correct on count/date evidence; placeholder naming needs cleanup.** “Several parties, including Sanofi” supports three total NDA parties minimum, so two unnamed rows plus Sanofi is the correct atomization. If strict rulebook naming is enforced, aliases should be type-based placeholders rather than `Unidentified party 1/2`.

### Final-round cluster

- Raw row 15 `Pfizer` `Final Round Inf Ann` dated 2016-07-19: **AI wrong / Alex correct to omit this specific row.** The July 19 letter requested an initial non-binding preliminary proposal by August 8 and said a limited number may later be invited. That is not a final-round announcement.
- Raw row 17 `Pfizer` `Bid` dated 2016-08-08 at `$65.00`: **AI correct / Alex correct on matched row.** The bid is non-binding/preliminary and therefore informal.
- Raw row 18 `Pfizer` `Final Round Ann` dated 2016-08-10 vs Alex `Final Round Ann` dated 2016-08-14: **both defensible on date anchor; AI preferred if treating subset invitation as the round announcement.** August 10 is when Medivation invited Pfizer to a subsequent round with several other parties. August 14 is when process instructions/deadlines were sent. The extraction should avoid duplicating both unless the rulebook wants separate “invitation” and “process-letter” rows.
- Alex-only `Final Round Inf Ann` dated 2016-08-14 and `Final Round Inf` dated 2016-08-14: **AI correct / Alex wrong.** The August 14 letter asked for a merger-agreement markup and a definitive proposal; this is formal-round evidence, not informal-round evidence.
- Raw row 19 `Pfizer` `Final Round` dated 2016-08-19 vs Alex `Final Round` dated 2016-08-14: **AI mostly correct / Alex date wrong if this row represents the submission/deadline event.** §K1 treats no-`Ann` `Final Round` as bids submitted at final round; the Aug. 19 date matches the requested definitive proposal date and actual `$77.00` revised written proposal. The row’s `source_quote` currently cites the Aug. 14 request rather than the Aug. 19 submission; evidence would be cleaner if paired with the p.27 Aug. 19 bid passage or kept as a deadline row only if that is intended.
- Raw row 21 `Pfizer` `Final Round Ext Ann` dated 2016-08-19: **AI correct / Alex omission wrong.** After the `$77.00` proposal, Pfizer was told to submit its “best and final” offer on Aug. 20; that is an extension / best-and-final announcement.
- Potential missing row: **review needed, not an Alex-vs-AI divergence.** If §K1’s `Final Round Ext` is meant to mirror `Final Round` for the extension submission, the raw extraction should add an Aug. 20 `Final Round Ext` row tied to Pfizer’s `$81.50` best-and-final proposal. If bid rows alone are intended to carry submissions, then raw row 21 is enough.

### Pfizer bids and execution

- Raw row 20 `Pfizer` `Bid` dated 2016-08-19 at `$77.00`: **AI correct / Alex correct on matched row.** Formal classification is supported by the final-round/process-letter context and the revised written proposal.
- Raw row 22 `Pfizer` `Bid` dated 2016-08-20 at `$81.50`: **AI correct / Alex correct on matched row.** The filing calls it a “best and final” proposal.
- Raw row 23 `Pfizer` `Executed` dated 2016-08-20 at `$81.50`: **AI correct / Alex partially wrong.** Execution date and winning consideration are directly supported by p.27 plus offer-price evidence. Alex has the `Executed` row but leaves bid value/unit null; the AI’s value fields are useful and supported.
- Pfizer `bidder_type.public=false` vs Alex `public=null` on matched Pfizer rows: **AI correct under current schema/policy; reference converter issue.** The current schema wants a boolean. Alex’s `null` comes from converter policy that refuses to infer public/private from plain strategic notes. This should be solved reference-side or in diff normalization, not by changing extraction behavior for this deal.

### Alex-only August 20 drops

- Alex-only `Sanofi` `Drop` dated 2016-08-20: **AI correct / Alex wrong.** The filing does not say Sanofi withdrew, was cut, or failed to submit on Aug. 20. Sanofi’s earlier proposal was rejected Apr. 29 and Sanofi later entered an NDA; no bidder-specific Aug. 20 dropout language appears.
- Alex-only `Party A` and `Party B` `Drop` dated 2016-08-20: **AI correct / Alex wrong.** The filing does not identify the unnamed July 5 NDA parties as the “several other interested parties” invited Aug. 10, nor does it narrate their withdrawal/cut. §I1 says not to fabricate catch-all drops for NDA-only parties.

## Extraction-side fixes needed

1. Remove raw row 10 `Target Sale` unless there is a deliberate rulebook decision to record target-specific outreach to a bidder. As coded, it overstates the evidence.
2. Remove raw row 15 `Final Round Inf Ann`; July 19 is an initial non-binding proposal request, not a final-round event.
3. Tighten final-round row evidence:
   - Keep Aug. 10 `Final Round Ann` if subset invitation is the chosen anchor.
   - Keep Aug. 19 `Final Round` only if no-`Ann` round rows are meant to represent submission/deadline dates in addition to bid rows.
   - Keep Aug. 19 `Final Round Ext Ann` for the best-and-final request.
   - Decide whether Aug. 20 requires a `Final Round Ext` row.
4. Add or adjust note/flag on July 5 NDA rows to clarify that July 5 is the announcement anchor, not necessarily the execution date.
5. Fix placeholder aliases for unnamed NDA parties if strict rulebook naming is enforced.
6. Registry hygiene: include observed short/legal aliases consistently so `resolved_name_not_observed` does not fire for benign legal-suffix expansions.

## Reference-side corrections needed

1. Change Sanofi’s initial `Bid` date from 2016-04-13 to 2016-04-15 under §B5 receipt-date anchoring.
2. Delete Alex’s duplicate Sanofi `Bidder Sale` row for the unsolicited first-contact bid.
3. Change Alex’s `Bid Press Release` date from 2016-04-13 to 2016-04-28 and attach Sanofi as the bidder if retaining the row.
4. Add or accept AI’s April 29 Sanofi `DropTarget`.
5. Replace Alex’s single J.P. Morgan `IB` row with advisor rows for Centerview, J.P. Morgan, Evercore, and Guggenheim, with `role="advisor_financial"` and earliest-action dates.
6. Add or accept AI’s May 2 Pfizer `Bidder Interest`, May 20 Pfizer `Bidder Sale`, and May 25 Sanofi `Activist Sale`.
7. Keep July 5 atomized NDA rows for Sanofi plus two unnamed parties, but decide whether the reference should store a precise July 5 anchor or an “announced by July 5” rough/date caveat.
8. Remove the Aug. 14 informal final-round rows from Alex; the August final-round process is formal after the Aug. 8 informal bid.
9. Remove Alex’s Aug. 20 Sanofi/Party A/Party B drops unless another filing passage outside pages 24-27 explicitly narrates those bidder-specific outcomes.
10. Resolve reference-converter `bidder_type.public=null` policy for Pfizer. Under the current boolean schema, nulls create noise against otherwise correct AI output.

## Rule / prompt recommendations

- Add prompt guidance for initial non-binding process letters: a request for the **first** preliminary proposal is not a `Final Round Inf Ann` when the same quote says a later subset may be invited.
- Clarify final-round duplication: when a subset invitation is followed by a process letter with deadlines, should the extractor emit one `Final Round Ann` at invitation, one at process-letter date, or one plus deadline/source details? Medivation exposes this ambiguity.
- Clarify whether `Final Round Ext` rows are mandatory whenever a `Final Round Ext Ann` is followed by an actual bid, or whether the bid row alone represents the submission.
- Clarify NDA date anchoring when the filing says “on date X announced it had entered into confidentiality agreements” without stating the signing date. Recommended: allow the announcement date with a required `date_inferred_from_context` or `announced_by_date` flag/note.
- Settle bidder-type public/non-U.S. policy explicitly. If extraction is filing-only, named companies like Sanofi/Pfizer should not be externally upgraded to `public=true`/`non_us=true`. If public-company identity may be inferred from common issuer identity, state that as an exception and require evidence/provenance.

## Confidence

**High confidence** on Sanofi April 15 receipt date, April 28 press release, April 29 target rejection, advisor-row undercount, Pfizer June 29 NDA, Aug. 8 / Aug. 19 / Aug. 20 bid values, Aug. 20 execution, and rejection of synthetic Aug. 20 drops.

**Medium confidence** on the exact final-round taxonomy because the current rules permit inferred final-round rows but do not fully specify how to handle a sequence of Aug. 10 subset invitation, Aug. 14 process letter, Aug. 19 formal bid, and Aug. 20 best-and-final request.

**Medium confidence** on July 5 NDA precise-date treatment because the filing gives a press-release date for confidentiality agreements already entered into, not individual execution dates.

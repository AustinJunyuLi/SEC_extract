# MASTER ADJUDICATION — clean reference-9 run

Date: 2026-04-23  
Run artifacts reviewed in-session: `/tmp/sec_extract_ref9_clean/{slug}.raw.json`  
Committed raw artifact copies: `quality_reports/adjudication/2026-04-23_clean_ref9/raw_extractions/{slug}.raw.json`  
Pipeline outputs: `output/extractions/{slug}.json`  
Fresh diffs: `scoring/results/{slug}_20260423T212321Z.{md,json}`  
Per-deal reports: `quality_reports/adjudication/2026-04-23_clean_ref9/{slug}.md`

## Bottom Line

The clean reference-9 extraction run finished and all nine deals pass the deterministic Python validator with **zero hard flags** after canonical preparation/finalization. That is not the same thing as filing-level clean. The adjudication pass found that the AI output is generally much closer to the SEC filings than Alex's converted reference JSONs, but most deals still need targeted extraction-side cleanup before Austin should mark them verified.

Status after adjudication:

| Deal | Pipeline status | Adjudication disposition | Extraction-side action |
|---|---:|---|---|
| `imprivata` | passed, hard=0 | Materially correct | No core extraction fix; only policy/optional final-round convention |
| `mac-gray` | passed, hard=0 | Mostly correct | Austin review: `Acquirer`; Party A dropout code/source |
| `medivation` | passed, hard=0 | Pass with fixes needed | Delete/recode over-emitted target/final-round rows; tighten final-round cluster |
| `zep` | passed, hard=0 | Needs targeted revision | Remove duplicate/over-specific rows; fix Party Y and New Mountain details |
| `providence-worcester` | passed, hard=0 | Not clean yet | Repair IOI cohort mapping; delete initial IOI-as-final-round row; clear `Executed` values |
| `penford` | passed, hard=0 | Not clean as-is | Remove over-emitted rows; add missing Party F/Party C follow-up; recode stale drops |
| `petsmart-inc` | passed, hard=0 | Not verified clean yet | Add missing October informal-round markers; remove/recode June 18 row; decide NDA/acquirer policy |
| `saks` | passed, hard=0 | Not clean as-is | Fix Sponsor A attribution; recode ambiguous drops; decide Morgan Stanley IB |
| `stec` | passed, hard=0 | Not fully clean | Remove premature Company D drop; decide BofA IB date; optional WDC same-price bid policy |

The 392 target-deal gate remains closed. This run improved the state materially, especially by clearing Penford's prior hard-blocker, but the manual verification/stability clock should not start until the extraction-side fixes below are applied and the reference side is refreshed or explicitly quarantined as legacy calibration.

## Validator vs. Adjudicator

All nine finalized outputs pass hard validation. A direct check using `pipeline.prepare_for_validate()` followed by `pipeline.validate()` confirms:

| Deal | Hard | Soft | Info-style validator flags |
|---|---:|---:|---:|
| `imprivata` | 0 | 8 | 0 |
| `mac-gray` | 0 | 16 | 0 |
| `medivation` | 0 | 18 | 0 |
| `penford` | 0 | 1 | 0 |
| `petsmart-inc` | 0 | 0 | 0 |
| `providence-worcester` | 0 | 15 | 0 |
| `saks` | 0 | 0 | 0 |
| `stec` | 0 | 0 | 0 |
| `zep` | 0 | 19 | 0 |

Two per-deal reports mention raw ordering/gap issues on `penford` and `saks`. Those are not current pipeline blockers: canonical preparation/finalization clears raw ordering artifacts and the current finalized files have `hard=0`. The substantive adjudication findings in those reports still stand.

Most remaining validator soft flags are expected `nda_without_bid_or_drop` flags on count-supported NDA placeholders. These should not be silenced by fabricated drops. They should be dismissed during manual verification when the filing gives a count but no party-specific follow-up.

## Deal Findings

### Medivation

Disposition: pass with extraction fixes needed.

AI is clearly better than Alex on:

- Sanofi first bid date: filing says Medivation received Sanofi's April 13 letter on April 15; AI uses receipt date.
- Sanofi public announcement/rejection: April 28 press release and April 29 target rejection.
- Pfizer pre-NDA chronology: May 2 `Bidder Interest`, May 20 `Bidder Sale`, June 29 NDA.
- Advisor rows: filing supports Centerview, J.P. Morgan, Evercore, and Guggenheim, not just one J.P. Morgan row.
- July 5 NDA atomization: "several parties, including Sanofi" supports Sanofi plus two unnamed placeholders.
- Avoiding Alex's synthetic August 20 Sanofi/Party A/Party B drop rows.

Extraction-side fixes:

1. Delete raw row 10, `Target Sale`, 2016-06-28. The passage is a Pfizer confidentiality/NDA setup, not a target sale decision.
2. Delete raw row 15, `Final Round Inf Ann`, 2016-07-19. The July 19 letter requested initial non-binding preliminary proposals and said a later subset might be invited; it is not a final-round event.
3. Reconcile the August final-round cluster:
   - Aug. 10 subset invitation can be `Final Round Ann`.
   - Aug. 19 formal bid/submission row is defensible but needs cleaner evidence.
   - Aug. 19 best-and-final request is `Final Round Ext Ann`.
   - Decide whether Aug. 20 also needs a no-bidder `Final Round Ext` row or whether Pfizer's bid row is enough.
4. Add a note/flag that July 5 NDA rows are announcement-anchored, not necessarily exact signing dates.
5. Normalize unnamed NDA aliases if strict placeholder naming is required.

Reference-side corrections:

- Change Sanofi first bid from April 13 to April 15.
- Delete duplicate Sanofi `Bidder Sale`.
- Change `Bid Press Release` to April 28 and attach Sanofi.
- Add/accept April 29 Sanofi `DropTarget`.
- Replace the single advisor row with all four advisor rows.
- Add/accept Pfizer May 2 and May 20 rows and Sanofi activist row.
- Remove unsupported August 20 drop rows.
- Resolve Pfizer `public=null` converter noise.

### Imprivata

Disposition: materially correct against the filing.

AI is better than Alex on:

- January 2016 Thoma Bravo interest date.
- March 9 Thoma Bravo concrete pre-NDA bid.
- April 15 Barclays engagement.
- May 5 target sale process.
- Seven NDA signers, including the unnamed extra financial sponsor.
- Sponsor A `DropBelowInf` on June 15.
- Sponsor B's June 9 range encoded as lower/upper rather than point value.
- June 24 final bid process letters.
- July 8 and July 9 Thoma Bravo formal bids.
- July 13 execution.

No required extraction-side fix was identified for core event facts.

Open policy/optional item:

- Decide whether a standalone July 8 `Final Round` row is required in addition to the July 8 formal bid row. If yes, the extractor should add it; if bid rows carry submission events, the current output is sufficient.

Reference-side corrections:

- Filing-verbatim `TargetName`, `Acquirer`, and `DateEffective=null`.
- Thoma Bravo interest to January 2016.
- Barclays IB to April 15.
- Range/date handling for seven NDA signers.
- Sponsor B range value structure.
- Remove June 9 final-round rows and June 24 extension rows.
- Execution date to July 13.
- Populate/suppress `bidder_type.public=null` converter artifacts.

### Zep

Disposition: needs targeted extraction-side revision and reference-side correction.

AI is better than Alex on:

- 2014 process / 2015 restart structure.
- 25 confidentiality-agreement count.
- Range bids as ranges.
- New Mountain 2015 bid dates and NDA revival.
- April 7, 2015 execution date rather than April 8 announcement.
- Omitting unsupported 2014 final-round rows from Alex.

Extraction-side fixes:

1. Remove or merge raw BidderID 3, duplicate `Target Sale` on 2014-02-27. Correct state is one `Target Sale` dated 2014-01-28 plus the BofA IB row.
2. Keep New Mountain's 2014 `DropAtInf`, but date it to 2014-04-14 or explicitly flag it as inferred from the March 27 process letter / April 14 deadline.
3. Remove `unsolicited_first_contact` from Party Y's 2014-05-20 bid. Party Y continued into data-room access and management presentation.
4. Rework the six remaining 2014 dropout rows so the filing's "five unable to proceed / sixth stopped responding" group outcome is not assigned to specific identities. Use generic `Drop` plus `drop_identity_ambiguous` unless Austin chooses a deterministic convention.
5. Remove raw BidderID 51, April 2015 price reaffirmation, as a separate bid. Preserve as an additional note on the March 13 best-and-final row if useful.
6. Add clearer aggregate-basis notes on the five April 14 preliminary bid rows: the $20-$22 range is an aggregate range across five bids, not bidder-specific.

Reference-side corrections:

- Atomize 25 NDAs.
- Delete unsupported 2014 final-round rows.
- Preserve April 14 bids as aggregate-range rows.
- Re-date New Mountain restart/bids to Feb. 10 / Feb. 19 / Feb. 26 / Mar. 13.
- Add Feb. 27 NDA revival.
- Change execution to Apr. 7.
- Remove lower-bound values from `bid_value_pershare` on range bids.

### Providence & Worcester

Disposition: not clean yet; extraction is stronger than Alex but needs targeted fixes.

AI is better than Alex on:

- Filing-verbatim deal names.
- `DateEffective=null`.
- 25 initial NDA rows plus separate Party C later NDA.
- G&W public status.
- Late-July and August bidding chronology.
- No Party B `Executed` row.
- G&W execution dated Aug. 12, not Aug. 15 announcement.

Extraction-side fixes:

1. Delete raw row 28 / BidderID 29, `Final Round Inf Ann`, 2016-04-27. The April 27 IOI request is an initial broad IOI request, not a final-round event.
2. Rebuild the May 19-June 1 IOI cohort so placeholder identities carry coherently:
   - Party B, G&W, Party D, Party E, Party F;
   - one strategic no-LOI party;
   - one financial no-LOI party;
   - two low-bidder placeholders.
3. Preserve the two low-bidder exits and late-July no-LOI exits, but tie them to the corrected cohort identities.
4. Keep Party C as a separate early-July entrant.
5. Keep G&W July 26 bid informal unless the rulebook changes; it remains a non-binding LOI with CVR structure.
6. Keep Aug. 12 G&W bid formal.
7. Clear value fields from the `Executed` row; the $25 value belongs on the winning bid row.
8. Review `deal.all_cash`: final consideration is cash, but earlier G&W bids included CVR.

Reference-side corrections:

- Filing-verbatim deal names and `DateEffective=null`.
- Atomize NDAs and IOIs.
- Remove unsupported Party A July 22 activity.
- Remove Party B `Executed`.
- Change G&W `Executed` to Aug. 12.
- Correct Party F as strategic and G&W `public=true`.
- Avoid treating Party F financing support as a joint Party E/F bidder unless Austin explicitly wants that.

### Penford

Disposition: not clean as-is. AI is much better than Alex, but extraction-side corrections are needed.

Important reconciliation: the report notes raw ordering/gap hard flags, but current pipeline preparation/finalization validates Penford with **hard=0**. Treat raw ordering as resolved mechanically. The filing-level fixes below remain material.

AI is better than Alex on:

- Filing-verbatim deal names and `DateEffective=null`.
- Including 2007/2009 stale prior attempts in phase 0.
- July 17 Ingredion initiation and July 20 secrecy agreement.
- Deutsche Bank and J.P. Morgan advisor rows.
- Party A/B/C/D market-check chronology.
- Range bid structure.
- Party B and Party D dropouts.
- October 14 execution date.

Extraction-side fixes:

1. Recode stale 2007/2009 drop rows as generic `Drop` with ambiguity, not `DropAtInf`, unless Austin decides "did not result in offers" implies voluntary informal withdrawal.
2. Remove Party C 2014-09-25 `Bidder Interest`; it is a management presentation, not new interest.
3. Remove Ingredion 2014-09-29 $18.50 bid; it repeats the earlier Sept. 17 range in a board status discussion.
4. Add Party F `DropAtInf` on 2014-09-29 from the explicit "declined to pursue further discussions" language.
5. Add a guarded Party C drop on 2014-10-14, likely generic `Drop` with ambiguity, from the grouped summary that remaining market-check parties did not move forward or made lower indications.
6. Consider a Party A losing-bid closeout on 2014-10-14 only if Austin wants every final losing bid closed explicitly.
7. Decide whether to keep both Aug. 13 and Aug. 28 target sale rows, or only the stronger Aug. 28 market-check authorization.

Reference-side corrections:

- Filing-verbatim names and `DateEffective=null`.
- Year-only stale dates to July 1, not January 15.
- July 17 Ingredion `Bidder Sale`, July 20 NDA, remove July 20 `Bidder Interest`.
- Deutsche Bank date correction and add J.P. Morgan.
- Remove unsupported Oct. 3 `Final Round Ann`.
- Correct Party A / Ingredion October dates and range structure.
- Execution date to Oct. 14.
- Fix `public=null` artifacts, especially Ingredion `public=true`.

### Mac Gray

Disposition: AI mostly correct; limited Austin review needed.

AI is better than Alex on:

- Filing-verbatim target name.
- BofA engagement/termination/re-hire dates.
- Party A June 21 pre-NDA informal bid.
- Exact-count NDA atomization.
- Range-value handling.
- Informal and formal round dates.
- Party C September 18 dropout.
- CSC/Pamplona September 21 formal bid and October 14 execution.

Extraction-side review items:

1. Decide `Acquirer` field semantics. AI uses `CSC ServiceWorks, Inc.`, while the legal acquisition vehicle is Spin Holdco Inc.; Alex's old "CSC purchased by Pamplona..." string is wrong.
2. Review raw BidderID 44, Party A `DropBelowM` on 2013-09-19. Date is correct, but `DropTarget` may be cleaner because the filing records target selection of CSC/Pamplona based on value/certainty rather than an explicit below-minimum rejection.
3. No fix needed for the 16 unnamed financial NDA rows; soft flags are expected and should not produce synthetic drops.
4. No fix needed for Party A Sept. 18 range/formal soft flag; this is the intended manual-review marker.

Reference-side corrections:

- Correct deal identity and `DateEffective=null`.
- Remove duplicate June 21 Party A `Bidder Sale`; keep the bid.
- Atomize 16 unnamed financial NDAs.
- Delete synthetic July 25 aggregate drop.
- Move final-round dates to Aug. 27 / Sept. 9 and Sept. 11 / Sept. 18.
- Move execution from Sept. 21 to Oct. 14.
- Normalize range values and `public` booleans.
- Decide CSC/Pamplona `base` globally: mixed strategic+sponsor vs filing's strategic-process label.

### Petsmart

Disposition: not verified clean yet despite validator-clean output.

AI is better than Alex on:

- Separate JANA and Longview activist rows.
- Industry Participant interest/drop sequence.
- August 13 target sale and August 19 public announcement.
- 15 October financial-buyer NDAs.
- October range/lower-bound bid structure.
- November 3 final-round selection and 11 `DropBelowInf` rows.
- December bids and December 14 execution.

Extraction-side fixes:

1. Delete or recode raw row 2, `Target Sale`, 2014-06-18. The cited passage is capital-structure/strategic review, not a sale-process decision.
2. Add `Final Round Inf Ann` around 2014-10-15 from "During October..." preliminary indication instructions.
3. Add `Final Round Inf` on 2014-10-30 for the preliminary indication deadline.
4. Resolve `Acquirer`: legal Parent (`Argos Holdings Inc.`) vs ultimate Buyer Group. Recommendation for research schema: use ultimate Buyer Group; store legal Parent elsewhere if needed.
5. Decide whether raw rows 45 and 53, Longview/bidder confidentiality agreements, are in-scope `NDA` rows. If `NDA` means target-bidder auction funnel CAs, drop them or flag them separately.
6. Keep Bidder 3's December 10 verbal valuation borderline; do not force until rulebook decides verbal non-written final-deadline valuations.

Reference-side corrections:

- Split activist rows.
- Add Industry Participant rows.
- Move public sale announcement rows to Aug. 19.
- Change J.P. Morgan rough month date to July 15.
- Change October NDA rough date to Oct. 5.
- Correct range/single-bound values.
- Replace generic October drops with Nov. 3 `DropBelowInf`.
- Add Dec. 14 `Executed`.
- Set `DateEffective=null`.
- Resolve `public=null` converter noise.

### Saks

Disposition: substantively stronger than Alex, but not clean as-is.

AI is better than Alex on:

- Sponsor A and Hudson's Bay early interest chronology.
- April and June target-sale decisions.
- July 2 final-round announcement and July 11 bids.
- Company H skip.
- Sponsor E/G July 11 bidder identity.
- July 23 Sponsor A/E below-minimum treatment.
- Company I NDA timing.
- July 28 execution and `DateEffective=null`.

Extraction-side fixes:

1. Raw row 5 should be Sponsor A only, not Sponsor A/Sponsor E. Sponsor E attended the meeting, but the filing says Sponsor A made the price indication.
2. Raw row 19, Sponsor G, should be generic `Drop`, not `DropAtInf`, with `date_unknown` and agency ambiguity.
3. Raw row 26, Company I, should probably be generic `Drop`, not `DropAtInf`, unless Austin decides go-shop no-proposal-by-deadline is `DropAtInf`.
4. Raw row 18, Company F, may also be safer as generic `Drop` because the filing only says Company F did not participate in the ultimately submitted offer.
5. Ensure canonical same-date ordering. Current final pipeline validates clean, but raw report noted ordering artifacts.
6. Decide whether Morgan Stanley `IB` belongs. It is described as a long-time advisor and attended board meetings, but no discrete engagement is narrated.

Reference-side corrections:

- Filing-verbatim target/acquirer names and `DateEffective=null`.
- Delete Sponsor A April 26 drop; that is an NDA date.
- Remove or replace Sponsor A/E July 7 rough drop.
- Remove Company H drop; skip with info flag.
- Remove July 2 no-`Ann` final-round row.
- Change July 11 bidder identity from Sponsor A/E to Sponsor E/G.
- Replace July 28 Sponsor A/E `DropTarget` with split July 23 Sponsor A and Sponsor E `DropBelowM`, or otherwise use AI's page 34 evidence.
- Change Company I NDA to about Aug. 11.
- Normalize `public` fields and default Company I ambiguity.

### STec

Disposition: not fully clean, but AI is materially closer to the filing than Alex.

AI is better than Alex on:

- Early Company A, target sale, activist, Company B, Company D, and Company H chronology.
- Range bid value structure.
- Correct final-round dates.
- WDC's May 31 withdrawal and June 10 re-engagement.
- June 23 execution date.
- `DateEffective=null`.

Extraction-side fixes:

1. Remove AI row `BidderID=26`, Company D `DropAtInf`, 2013-05-28. Company D remained interested and requested more time; it did not drop until June 5.
2. Decide BofA Merrill Lynch `IB` date:
   - 2013-03-26 if board approval to retain counts;
   - 2013-03-28 if formal engagement-letter execution counts.
   Alex's 2013-04-04 date is unsupported.
3. Optional: decide whether WDC's 2013-05-30 same-price best-and-final confirmation is a separate bid row. It is defensible but economically duplicates May 28.

Reference-side corrections:

- Filing-verbatim names and `DateEffective=null`.
- Add missing early process rows.
- Remove April 23 final-round rows; those were initial IOI process letters.
- Convert ranges to lower/upper fields.
- Correct dropout codes/dates for Company F/E/G/H/D.
- Add WDC May 31 drop and June 10 re-engagement.
- Correct final-round dates to May 16 / May 28 / May 29 / May 30.
- Correct execution to June 23.
- Fix `public=null` artifacts.

## Cross-Deal Rule / Prompt Decisions

The same issues recur across deals. These should be resolved in `rules/*.md` before the next reference rerun.

1. **Initial IOI requests vs. final-round rows.** Medivation, Providence, Petsmart, and STec show the extractor sometimes labels broad initial non-binding IOI requests as `Final Round Inf Ann`. Rule should say initial broad IOI solicitations are not final-round rows unless the filing narrows the field, uses final-round language, or sends a process letter to a subset after an initial round.

2. **Standalone final-round terminal rows.** Imprivata and Medivation expose ambiguity about whether a formal bid row on a deadline is enough, or whether a separate no-bidder `Final Round` / `Final Round Ext` row is mandatory.

3. **`Acquirer` semantics.** Petsmart and Mac Gray show legal merger counterparty vs. ultimate economic buyer vs. operating buyer. The schema needs one rule.

4. **`all_cash` semantics.** Providence final merger consideration is cash, but earlier G&W bids included CVR. Decide whether `all_cash` means final merger consideration only or every extracted bid consideration.

5. **NDA scope.** Petsmart Longview/bidder confidentiality agreements are real but not target-bidder auction NDAs. Zep Party Y has data-room access but no explicit NDA sentence. Add rules for inter-bidder CAs and data-room-implied NDAs.

6. **Drop agency and ambiguous group outcomes.** Zep, Saks, Providence, and Penford show group dropout language and passive "no longer participating" language. Rule should default to generic `Drop` with ambiguity unless voluntary withdrawal, target cut, or below-minimum reason is explicit.

7. **Cohort identity continuity.** Providence and Zep need deterministic handling when the filing gives counts and later group outcomes but does not map identities. The extractor should maintain placeholder identities through funnel stages without over-assigning outcomes.

8. **Range and aggregate range handling.** Zep, Providence, Imprivata, Petsmart, Mac Gray, Penford, and STec all confirm the importance of keeping range values out of `bid_value_pershare`. Aggregate ranges across multiple bidders need explicit notes/fields.

9. **`bidder_type.public=null` reference noise.** Many field diffs are caused by Alex/reference converter nulls. Either regenerate reference JSONs with booleans or suppress legacy null-vs-false in the diff as converter noise.

10. **IB date policy.** STec and Penford show board approval to retain, engagement-letter execution, and first advisory action can differ. §J1 should specify which anchor wins.

11. **Repeated price confirmations.** Zep, Penford, and STec show repeated same-price communications. Rule should say when a reaffirmation is a new bid versus an `additional_note`.

12. **`Executed` value fields.** Providence flags whether execution rows should carry deal price when the immediately preceding winning bid row already carries it. Clarify and enforce consistently.

## Recommended Next Work Order

1. Fix high-confidence extraction-side errors in `medivation`, `zep`, `providence-worcester`, `penford`, `petsmart-inc`, `saks`, and `stec`.
2. Make the small Austin-review calls for `mac-gray` and `imprivata`:
   - Mac Gray `Acquirer` and Party A drop code.
   - Imprivata standalone July 8 `Final Round` policy.
3. Update `rules/*.md` for the cross-deal decisions above before another full rerun.
4. Regenerate or quarantine Alex reference JSONs for known reference-side defects. Do not use raw AI-vs-Alex diff counts as a grade until reference-side modernization is done.
5. Rerun all nine reference deals from clean raw extraction only after rules and prompt decisions land.
6. Start the 3-clean-run stability clock only after a full reference rerun has no high-confidence extraction-side fixes from adjudication.

## Report Set

- `quality_reports/adjudication/2026-04-23_clean_ref9/medivation.md`
- `quality_reports/adjudication/2026-04-23_clean_ref9/imprivata.md`
- `quality_reports/adjudication/2026-04-23_clean_ref9/zep.md`
- `quality_reports/adjudication/2026-04-23_clean_ref9/providence-worcester.md`
- `quality_reports/adjudication/2026-04-23_clean_ref9/penford.md`
- `quality_reports/adjudication/2026-04-23_clean_ref9/mac-gray.md`
- `quality_reports/adjudication/2026-04-23_clean_ref9/petsmart-inc.md`
- `quality_reports/adjudication/2026-04-23_clean_ref9/saks.md`
- `quality_reports/adjudication/2026-04-23_clean_ref9/stec.md`

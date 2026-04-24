# Mac Gray adjudication — clean reference-9 run

Deal: `mac-gray`  
Run artifacts reviewed: `/tmp/sec_extract_ref9_clean/mac-gray.raw.json`, `data/filings/mac-gray/pages.json`, `reference/alex/mac-gray.json`, `scoring/results/mac-gray_20260423T212321Z.md`, and the paired JSON diff.  
Scope: adjudication only. No extraction, reference, rule, code, raw, output, or state files were edited.

## Status / disposition

Disposition: **AI mostly correct against the filing; Alex reference needs substantial modernization for this deal.**

The raw extraction passes the deterministic validator in dry-run:

- status: `passed`
- hard flags: `0`
- soft flags: `17`
- info flags: `33`

The material AI-vs-Alex diffs are not a single extraction failure. They mainly reflect:

- current rulebook range-bid encoding versus Alex's legacy lower-bound-in-`bid_value_pershare` encoding;
- current exact-count NDA atomization versus Alex's aggregate `16 financial bidders` row;
- filing-grounded date anchoring versus Alex rough/blank dates;
- current `Bid` + `pre_nda_informal_bid` treatment of Party A's June 21 proposal versus Alex's separate `Bidder Sale` row;
- Alex's incorrect execution date of September 21, 2013; the filing execution event is October 14, 2013.

Extraction-side fixes are limited. The only substantive AI-side issues I would send back for Austin review are the deal-level `Acquirer` precision and the Party A dropout code/source specificity. The rest of the main divergences are either AI-correct or rulebook-policy questions rather than raw-extraction errors.

## Evidence basis

I used the SEC filing text in `data/filings/mac-gray/pages.json` as ground truth, especially filing source pages 33-47 from the Background of the Merger, plus the front summary pages for deal identity.

Key filing anchors:

- source page 33: target name, prior CSC/Pamplona context, April 5 board discussion, April 8 Party A call, May 9 board review;
- source pages 35-36: May 15 BofA termination, May 31 BofA engagement, June 21 Party A unsolicited $17.00-$19.00 proposal;
- source pages 37-40: June 24 sale-process decision, 50-party outreach universe, 20 NDA count, Party B/Party C/CSC-Pamplona NDAs and initial indications;
- source pages 41-43: August 27 revised-proposal request, September 9/10 revised indications, September 11 final-proposal request, September 18 final submissions and Party C non-submission, September 19 selection of CSC/Pamplona, September 21 $21.25 offer;
- source pages 44 and 47: merger-agreement negotiations and October 14 execution.

Short filing snippets Austin can search quickly:

- target identity: `Mac-Gray Corporation`
- acquirer summary: `acquired by Spin Holdco Inc.`
- prior BofA engagement: `engaged BofA Merrill Lynch on October 23, 2012`
- NDA-count range phrase: `Over the next two months`
- Party A final-bid trigger: `best and final offer`

## Validator-flag interpretation

The validator flags do not show a blocking extraction problem.

`nda_without_bid_or_drop`, soft, raw BidderIDs 12-27 (`Financial 1` through `Financial 16`): **expected / AI correct.** The filing gives an exact total of 20 NDA signers: two strategic bidders, Party A and CSC/Pamplona, plus 18 financial bidders including Party B and Party C. After the named Party B and Party C rows, the 16 unnamed financial bidders are count-supported NDA-only placeholders. Current `rules/events.md` §I1 says to keep NDA-only rows and not fabricate generic drops. Alex's aggregate `16 financial bidders` NDA plus generic July 25 drop reflects the legacy workbook style, not the current rulebook.

`range_with_formal_trigger`, soft, raw BidderID 40 (`Party A`, `Bid`, 2013-09-18): **expected / AI correct.** Party A reiterated its prior $18.00-$19.00 range while also saying it was final. Current `rules/bids.md` §G1 says the formal trigger wins but the coexistence of a range and formal trigger should be flagged for manual review. The row should remain formal with lower/upper populated, not a point value.

Info flags are also explainable:

- `pre_nda_informal_bid` on raw BidderID 6 is correct: Party A's concrete $17.00-$19.00 proposal was before its August 5 NDA.
- `bid_range` flags on raw BidderIDs 6, 28, 29, 30, 36, 37, and 40 are correct under §H1.
- `date_range_collapsed` on raw BidderIDs 12-27 is correct for the unnamed NDA signer range.
- `joint_nda_aggregated` on raw BidderID 10 is correct because CSC/Pamplona is narrated as one confidentiality agreement.
- `final_round_inferred` flags on raw BidderIDs 32, 35, 38, and 43 are appropriate; the filing uses process-letter and final-indication language rather than a clean labeled final-round heading.
- `contingent_type_ambiguous` on raw BidderID 41 is reasonable because Party B's $21.50 headline includes $19.00 cash plus option value dependent on later performance.

## Deal-level disagreements

### `TargetName`

Verdict: **AI correct / Alex wrong.**

AI has `Mac-Gray Corporation`; Alex has `MAC GRAY CORP`. The filing uses the long corporate name and hyphenated styling. Keep AI.

### `Acquirer`

Verdict: **AI directionally correct; extraction-side precision issue. Alex wrong.**

Alex's `CSC purchased by Pamplona in May/2013` is a prior-transaction fact from the 2011-2012 CSC sale process, not the acquirer in the Mac Gray merger.

AI's `CSC ServiceWorks, Inc.` is defensible as the business acquirer / buyer entity, but the front summary states the acquisition would be by Spin Holdco Inc., a wholly owned subsidiary of CSC ServiceWorks, Inc. If the schema wants the legal acquisition vehicle, extraction should use `Spin Holdco Inc.`. If it wants the recognizable business buyer, `CSC ServiceWorks, Inc.` is acceptable. This should be a rule/schema convention decision, not an Alex-side override.

Recommended disposition: keep AI for diff purposes; add an extraction-side note for Austin to decide whether `Acquirer` should store legal parent vehicle or operating buyer in these sponsor-owned portfolio-company deals.

### `DateEffective`

Verdict: **AI correct / Alex wrong.**

The definitive proxy was dated December 4, 2013 and described a January 8, 2014 stockholder meeting. It did not state that the merger had become effective. Alex's January 9, 2014 date is external/post-filing information and should remain out of the extraction under the current rule that same-filing evidence controls `DateEffective`. Keep `null`.

## Material diff adjudication

### Start-of-process and advisor rows

Verdict: **AI correct / Alex mostly wrong on dates.**

- raw BidderID 1, `BofA Merrill Lynch`, `IB`, 2012-10-23: correct for the 2011-2012 Discussions. The filing explicitly anchors this older engagement to October 23, 2012 on source page 33.
- raw BidderID 2, `Target Sale`, 2013-04-05: defensible as early board authorization to explore transactional opportunities. Alex omits it.
- raw BidderID 3, `Party A`, `Target Interest`, 2013-04-08: correct. BofA, at the Board's instruction, called Party A; Party A said it might consider a combination. Alex's rough-date row is directionally right but should be precise.
- raw BidderID 4, `BofA Merrill Lynch`, `IB Terminated`, 2013-05-15: correct. The filing has a dated termination letter.
- raw BidderID 5, `BofA Merrill Lynch`, `IB`, 2013-05-31: correct for the current strategic-alternatives engagement. Alex has the event but not the precise date.
- raw BidderID 7, `Target Sale`, 2013-06-24: correct. The Special Committee concluded a potential sale should be considered and began the concrete buyer-universe process. Alex instead labels June 24 as `Final Round Inf Ann`, which overstates the initial process stage.

Extraction-side fix: none, except that raw BidderID 2 and raw BidderID 7 create two target-side sale-process rows. That is defensible here because April 5 is exploratory authorization and June 24 is a Special Committee process decision after Party A's concrete proposal. If Austin prefers only the latter, this should be a rule clarification about board-review versus formal sale-process launch.

Reference-side correction: Alex should carry exact dates for the BofA rows and not use a June 24 final-round label for the process launch.

### Party A June 21 proposal

Verdict: **AI correct / Alex wrong.**

raw BidderID 6 is `Party A`, `Bid`, `bid_type=informal`, 2013-06-21, $17.00-$19.00 lower/upper, source page 36. Party A's proposal was concrete and pre-NDA; Party A signed its NDA later on August 5. Current §C4 says this should be a `Bid` row with `pre_nda_informal_bid`, not a separate `Bidder Sale` row.

Alex-only `Party A` / `Bidder Sale` / 2013-06-21 should be removed from the reference JSON. It duplicates the bid event under deprecated semantics.

Reference-side correction: remove Alex BidderID 6 `Bidder Sale`; keep the June 21 bid as a range-valued informal bid.

### NDA cardinality and dates

Verdict: **AI correct / Alex wrong, with one date-policy caveat.**

The AI emits:

- raw BidderID 8: `Party B`, `NDA`, 2013-06-28, source page 38.
- raw BidderID 9: `Party C`, `NDA`, 2013-06-30, source page 38.
- raw BidderID 10: `CSC/Pamplona`, `NDA`, 2013-07-11, source page 39, with `joint_nda_aggregated`.
- raw BidderIDs 12-27: `Financial 1` through `Financial 16`, `NDA`, rough phrase collapsed to 2013-07-24, source page 38.
- raw BidderID 31: `Party A`, `NDA`, 2013-08-05, source page 40.

This matches the filing's total of 20 NDA signers: Party A, CSC/Pamplona, Party B, Party C, and 16 additional financial bidders. Alex's `Party C` date of June 20 is wrong; the filing has June 30. Alex's aggregate `16 financial bidders` row undercounts current atomized rows.

Date-policy caveat: the 16 unnamed financial bidders are exactly count-supported, but the filing gives only a broad period. The current midpoint rule yields July 24, 2013. Alex's July 15 rough date is not grounded in a specific filing date. AI is correct under current `rules/dates.md` §B4.

Extraction-side fix: none.

Reference-side correction: atomize the 16 unnamed financial NDA rows or regenerate Alex's Mac Gray reference from the current rulebook; correct Party C NDA date to 2013-06-30.

### Initial informal bids: July 23-25

Verdict: **AI correct / Alex wrong on range field placement.**

AI rows:

- raw BidderID 11: `CSC/Pamplona`, `Bid`, informal, 2013-07-23, $18.50 point value, source page 39.
- raw BidderID 28: `Party B`, `Bid`, informal, 2013-07-24, $17.00-$18.00 range, source page 39.
- raw BidderID 29: `Party C`, `Bid`, informal, 2013-07-24, $15.00-$17.00 oral range, source page 39.
- raw BidderID 30: `Party C`, `Bid`, informal, 2013-07-25, $16.00-$16.50 written range, source page 40.

Alex matches the event set but stores lower bounds in `bid_value_pershare` for range bids. Current §H1 requires `bid_value_pershare=null`, `bid_value_lower`, and `bid_value_upper`. AI is correct.

Reference-side correction: regenerate range bids so lower/upper fields carry the range and `bid_value_pershare` is null.

### Alex-only July 25 drop for `16 financial bidders`

Verdict: **AI correct / Alex wrong.**

Alex has `16 financial bidders`, `Drop`, 2013-07-25. The filing does not narrate a bidder-specific withdrawal or target cut for these 16 unnamed NDA signers. It only tells us that they entered confidentiality agreements within the broad process period and then the narrative focuses on the four interested bidders. Current §I1 says not to fabricate drop rows for silent NDA-only signers.

Extraction-side fix: none.

Reference-side correction: delete the aggregate July 25 drop. The 16 unnamed financial bidders should remain NDA-only with validator soft flags, not synthetic drops.

### Informal round / final-round structure

Verdict: **AI mostly correct; Alex's extension rows are not supported by current rulebook.**

AI rows:

- raw BidderID 32: `Final Round Inf Ann`, 2013-08-27, source page 41.
- raw BidderID 33: `CSC/Pamplona`, `Bid`, informal, 2013-09-09, $19.50, source page 41.
- raw BidderID 34: `Party B`, `Bid`, informal, 2013-09-09, $18.50, source page 41.
- raw BidderID 35: `Final Round Inf`, 2013-09-09, source page 41.
- raw BidderID 36: `Party A`, `Bid`, informal, 2013-09-10, $18.00-$19.00 range, source page 41.
- raw BidderID 37: `Party C`, `Bid`, informal, 2013-09-10, $16.00-$17.00 range, source page 41.

The actual process letter requesting revised written proposals was sent on August 27 with a September 9 deadline. That supports AI's `Final Round Inf Ann` and `Final Round Inf` pair.

Alex's `Final Round Inf Ext Ann` on July 25 and `Final Round Inf Ext` on September 9 are not necessary under the current vocabulary. July 25 was an internal decision to stage diligence and arrange management meetings, not a standalone extension event with a clear revised deadline. If Austin wants to encode that staging decision, the rulebook needs a distinct policy for "second-stage diligence authorization"; the current final-round extension labels are a poor fit.

Extraction-side fix: none.

Rule recommendation: clarify whether an internal committee decision to stage diligence before sending a later process letter should generate any round-structure row. My recommendation is no: emit the actual process-letter event, not the internal planning step.

### Formal final round: September 11-18

Verdict: **AI correct / Alex wrong on `Final Round` date.**

AI rows:

- raw BidderID 38: `Final Round Ann`, 2013-09-11, source page 42.
- raw BidderID 39: `CSC/Pamplona`, `Bid`, formal, 2013-09-18, $20.75, source page 42.
- raw BidderID 40: `Party A`, `Bid`, formal, 2013-09-18, $18.00-$19.00 range, source page 42.
- raw BidderID 41: `Party B`, `Bid`, formal, 2013-09-18, $21.50 headline, $19.00 cash plus $2.50 contingent option value, source page 42.
- raw BidderID 42: `Party C`, `DropAtInf`, 2013-09-18, source page 42.
- raw BidderID 43: `Final Round`, 2013-09-18, source page 42.

The filing says the September 11 calls requested final indications by September 18. Under §K2, the announcement/invitation row is September 11 and the final-round submission row is September 18. Alex's `Final Round` dated September 11 conflates invitation date with bid deadline.

Party A row 40 is correctly formal despite a range because Party A characterized its prior indication as final; the soft flag is the right treatment. Party B row 41 correctly preserves the $21.50 headline and decomposes it into cash plus contingent value.

Extraction-side fix: none.

Reference-side correction: set `Final Round` to September 18, not September 11; convert Party A and Party C range values to lower/upper fields.

### Party C September 18 dropout

Verdict: **AI more specific / Alex less specific; AI correct.**

AI raw BidderID 42 uses `DropAtInf`; Alex has generic `Drop`. The filing says Party C did not submit or reiterate a final indication and gave no reason. That is bidder-side non-participation rather than a target rejection. `DropAtInf` is the more informative current-code interpretation.

Extraction-side fix: none.

Reference-side correction: change Alex's generic `Drop` to `DropAtInf` if the current rulebook remains in force.

### Party A / Party B target rejection after September 18 bids

Verdict: **AI correct on Party B; Party A code is defensible but should be reviewed. Alex wrong on dates.**

AI rows:

- raw BidderID 44: `Party A`, `DropBelowM`, 2013-09-19, source page 43.
- raw BidderID 45: `Party B`, `DropTarget`, 2013-09-19, source page 43.

The September 19 Special Committee meeting is the substantive decision point. The committee compared Party A, Party B, and CSC/Pamplona, determined CSC/Pamplona offered better value/certainty, and authorized moving into exclusivity at $21.25. September 24 is only the later exclusivity-agreement execution date; the filing does not narrate a separate Party A or Party B rejection on that date.

Party B: AI is correct. Party B's headline value was facially higher, but the committee focused on contingent/deferred option value and financing risk. `DropTarget` is the right code.

Party A: AI's date is correct, but `DropBelowM` is a judgment call. Party A's final range was lower than CSC/Pamplona's selected path, and the committee sought $21.25 from CSC/Pamplona. However, the source quote does not say Mac-Gray communicated a minimum/reserve to Party A or explicitly rejected Party A because it was below a stated threshold. `DropTarget` may be cleaner because the decision was a target selection of CSC/Pamplona based on value and certainty. I would not block the run on this, but I recommend Austin review raw BidderID 44.

Extraction-side fix: consider changing raw BidderID 44 from `DropBelowM` to `DropTarget` or improving its source quote to include the September 19 comparative-selection language. Do not use Alex's September 24 date.

Reference-side correction: change Alex's Party A and Party B `DropTarget` dates from September 24 to September 19. For Party A, code should be resolved consistently with the extraction-side review above.

### CSC/Pamplona September 21 bid and execution

Verdict: **AI correct / Alex wrong on execution date.**

AI rows:

- raw BidderID 46: `CSC/Pamplona`, `Bid`, formal, 2013-09-21, $21.25, source page 43.
- raw BidderID 47: `CSC/Pamplona`, `Executed`, 2013-10-14, $21.25, source page 47.

September 21 is a revised final proposal plus request for two weeks of exclusivity. It is not merger-agreement execution. The merger agreement was executed on October 14, and the public announcement followed before market open on October 15. Alex's `Executed` row dated September 21 is wrong.

Extraction-side fix: none.

Reference-side correction: move `Executed` to October 14, 2013, and keep September 21 as the final formal $21.25 bid/exclusivity proposal.

### Bidder type disagreements

Verdict: **AI correct on `public=false` where Alex has `public=null`; CSC/Pamplona `base` is a rule-policy issue.**

For Party A, Party B, Party C, and the unnamed financial bidders, the AI's `public=false` is correct under current structured `bidder_type` semantics. The filing does not state they are public companies, and financial/private-equity bidders should not carry `public=null`. Alex's `public=null` reflects converter policy drift, not filing uncertainty.

For CSC/Pamplona, AI uses `base="mixed"` and Alex uses `base="s"`. The filing gives two competing signals:

- it labels the buyer group as one of the two strategic bidders in the process;
- it also narrates CSC together with Pamplona, with Pamplona funding the transaction and CSC as the operating portfolio company.

Current `rules/bidders.md` §F2/§F3 supports AI's `mixed` for a strategic + sponsor group. If the research variable should follow the filing's process-category label instead, Alex's `s` is defensible. This should be clarified once globally, because sponsor-owned portfolio-company bidders will recur.

Extraction-side fix: none unless Austin decides "portfolio-company buyer backed by PE sponsor" should be `s` when the filing labels it strategic.

Reference-side correction: set `public=false` rather than null for all non-public/non-stated bidder types. Defer CSC/Pamplona `base` until the global policy is settled.

## Extraction-side fixes needed

1. **Review deal-level `Acquirer`.** AI's `CSC ServiceWorks, Inc.` is better than Alex's prior-transaction string, but the filing's legal acquisition vehicle is Spin Holdco Inc. Decide whether this field stores the legal acquisition vehicle or the recognizable operating buyer / buyer group.

2. **Review raw BidderID 44 (`Party A`, `DropBelowM`, 2013-09-19).** Date is correct. Code may be better as `DropTarget` because the filing records comparative target selection of CSC/Pamplona, not an explicit below-minimum rejection of Party A. If kept as `DropBelowM`, the source quote should be widened to include the comparative September 19 decision context.

3. **No fix needed for raw BidderIDs 12-27.** The validator's NDA-only soft flags are expected under current rules and should not lead to synthetic drop rows.

4. **No fix needed for raw BidderID 40.** The range/formal soft flag is the intended manual-review marker.

## Reference-side corrections needed

1. Correct deal identity:
   - `TargetName`: `Mac-Gray Corporation`.
   - `Acquirer`: remove `CSC purchased by Pamplona in May/2013`; that is prior-process context, not the merger acquirer.
   - `DateEffective`: set to `null` unless the reference workflow is explicitly allowed to use post-filing outside information.

2. Remove Alex's duplicate June 21 `Party A` / `Bidder Sale` row. Keep the June 21 proposal as a `Bid`, informal, range $17.00-$19.00.

3. Atomize the exact-count NDA group:
   - keep Party B, Party C, CSC/Pamplona, and Party A named NDA rows;
   - add 16 unnamed financial-bidder NDA placeholders;
   - do not keep a single aggregate `16 financial bidders` row under the current rulebook.

4. Correct Party C NDA date from June 20 to June 30.

5. Delete Alex's synthetic July 25 `16 financial bidders` `Drop` row.

6. Regenerate range bids so `bid_value_pershare=null` and lower/upper fields hold the range:
   - Party A June 21: $17.00-$19.00.
   - Party B July 24: $17.00-$18.00.
   - Party C July 24: $15.00-$17.00.
   - Party C July 25: $16.00-$16.50.
   - Party A September 10: $18.00-$19.00.
   - Party C September 10: $16.00-$17.00.
   - Party A September 18: $18.00-$19.00, formal with manual-review flag.

7. Rework final-round rows:
   - use August 27 / September 9 for the informal revised-proposal process;
   - use September 11 / September 18 for the formal final-indication process;
   - remove unsupported July 25 and September 9 extension labels unless a new rule explicitly retains them.

8. Move `Executed` from September 21 to October 14.

9. Correct target-rejection dates:
   - Party B `DropTarget`: September 19, not September 24.
   - Party A drop: September 19, with code to be aligned after Austin reviews `DropBelowM` versus `DropTarget`.

10. Normalize `bidder_type.public` to `false` rather than `null` for non-public or non-stated private bidders. Defer CSC/Pamplona `base` until the sponsor-backed strategic-buyer policy is clarified.

## Rule / prompt recommendations

1. **Clarify `Acquirer` field semantics.** The current rule says filing-verbatim, but sponsor-backed deals often have a legal parent, merger sub, operating buyer, and sponsor label. Decide whether `Acquirer` should be the legal acquisition vehicle, ultimate operating buyer, or background-section bidder alias.

2. **Clarify portfolio-company buyer classification.** Mac Gray has CSC as the operating strategic buyer and Pamplona as the sponsor/funder. The filing labels CSC/Pamplona strategic, while the current structured type rule points to `mixed`. Add an explicit rule for PE-owned portfolio-company acquisitions.

3. **Clarify internal staging decisions versus process-letter events.** Mac Gray's July 25 meeting staged disclosure and contemplated revised bids, but the actual revised-proposal request was sent August 27. The extractor should probably emit the actual sent process letter only. If internal staging decisions matter, create a rule rather than overloading `Final Round Inf Ext Ann`.

4. **Tighten drop-code guidance for "selected another bidder" cases.** When a target selects a preferred bidder and stops pursuing lower or less certain alternatives, the current boundary between `DropBelowM` and `DropTarget` is blurry. Mac Gray Party A is a good example.

5. **Keep the prompt's exact-count NDA instruction.** The Mac Gray run demonstrates why it is needed: the filing commits to 20 NDA signers, and current atomization makes the auction funnel auditable.

## Confidence

Overall confidence: **high** that the AI extraction is closer to the filing than Alex's converted reference for Mac Gray.

High-confidence AI-correct calls:

- exact dates for BofA engagement/termination/re-engagement;
- Party A June 21 as pre-NDA informal `Bid`, not separate `Bidder Sale`;
- exact-count NDA atomization and NDA-only treatment for unnamed financial bidders;
- range values stored as lower/upper rather than `bid_value_pershare`;
- August 27 / September 9 informal revised-proposal round;
- September 11 / September 18 final formal round;
- Party B target rejection on September 19;
- CSC/Pamplona execution on October 14.

Medium-confidence / policy-sensitive calls:

- deal-level `Acquirer` value;
- CSC/Pamplona `bidder_type.base` as `mixed` versus `s`;
- Party A September 19 dropout code (`DropBelowM` versus `DropTarget`);
- whether April 5 and June 24 should both be retained as `Target Sale` rows or whether only the more concrete June 24 process launch should remain.

No low-confidence material calls remain after filing review.

# STec adjudication - clean reference-9 run

Deal: `stec`  
Raw extraction reviewed: `/tmp/sec_extract_ref9_clean/stec.raw.json`  
Diff reviewed: `scoring/results/stec_20260423T212321Z.md` / `.json`  
Filing ground truth: `data/filings/stec/pages.json`, especially pages 31-43

## Status / Disposition

Disposition: **not fully clean, but AI is materially closer to the filing than Alex's reference.** The extraction should not be accepted without fixes, mainly because it adds a premature Company D dropout on 2013-05-28 and likely dates the BofA Merrill Lynch `IB` row two days early if the intended event is formal engagement. The Alex reference needs larger correction: it misses the early target/activist/Company A/Company H chronology, mishandles range bids by putting lower bounds into `bid_value_pershare`, dates multiple final-round milestones on the invitation date, omits WDC's 2013-05-31 withdrawal/reengagement arc, and dates execution on the 2013-06-14 proposal rather than the 2013-06-23 merger-agreement execution.

High-level verdict:

- **AI correct / Alex wrong:** deal names, `DateEffective = null`, range-bid value structure, most early process rows, most dropout specialization, May 28 / May 29 / May 30 final-round milestone dates, WDC 2013-05-31 drop, WDC 2013-06-23 `Executed`.
- **AI wrong / Alex correct:** Company D should not have a dropout row on 2013-05-28; Alex is correct to omit that specific row.
- **Both defensible / needs policy clarity:** BofA Merrill Lynch `IB` date if the event is board approval to retain (2013-03-26) versus executed engagement letter (2013-03-28).
- **Both wrong:** no high-confidence both-wrong material divergence after filing review. If the `IB` policy is later fixed to require engagement-letter execution, then AI 2013-03-26 and Alex 2013-04-04 would both be wrong and the correct date would be 2013-03-28.

## Evidence Basis

Core filing chronology:

- Page 32: board determined a formal review of strategic alternatives was beneficial and, in "mid-November, 2012," authorized management to contact financial advisors about strategic alternatives, including a potential sale. This supports AI row `BidderID=2`, `Target Sale`, 2012-11-15.
- Page 32: on 2012-11-14, Company A's investment bank requested a preliminary meeting and provided a draft NDA for evaluating a possible business transaction; the meeting was later cancelled. This supports AI row `BidderID=1`, `Company A`, `Bidder Interest`, 2012-11-14.
- Page 33: Balch Hill and Potomac jointly increased holdings and Balch Hill's 2012-12-06 Schedule 13D amendment and letter urged the board to "explore strategic alternatives." This supports AI row `BidderID=3`, `Balch Hill and Potomac`, `Activist Sale`, 2012-12-06.
- Pages 33-34: Company B's president said on 2013-02-13 that he intended to present sTec as a possible acquisition target; approximately two weeks later Company B's management determined it was not interested. This supports AI rows `BidderID=4` `Bidder Interest` and `BidderID=5` `DropAtInf`, with the latter date inferred to 2013-02-27.
- Page 35: in mid-March 2013 Company D contacted management to explore a potential acquisition; on 2013-03-26 sTec received a draft NDA from Company D. This supports AI row `BidderID=6`, `Company D`, `Bidder Interest`, dated 2013-03-15 under the rough-date rule.
- Page 35: on 2013-03-26 the board approved retaining BofA Merrill Lynch; on 2013-03-28 sTec entered into the engagement letter. This supports an `IB` row before April 2013, but the strict engagement date is 2013-03-28.
- Pages 35-36: NDA dates are explicit: Company E 2013-04-04, Company D 2013-04-10, Company F 2013-04-11, Company G 2013-04-17, WDC addendum 2013-04-17, and Company H later on 2013-05-08.
- Page 36: Company F "declined the invitation" and was only interested in limited assets; Company E "shortly thereafter" also indicated limited-asset interest and the special committee decided not to continue discussions with Company E. This distinguishes Company F as voluntary (`DropAtInf`) and Company E as target cut / scope mismatch (`DropTarget`).
- Page 36: on 2013-04-23 BofA sent process letters to WDC and Company D requesting non-binding indications by 2013-05-03, and Company D verbally indicated interest above $5.60/share. This is an initial non-binding IOI process, not the final round.
- Page 37: WDC submitted a $6.60-$7.10/share cash range on 2013-05-03; Company G indicated it would not continue; Company H entered the process on 2013-05-01 and signed an NDA on 2013-05-08; Company D submitted $5.75/share on 2013-05-10; Company H submitted a $5.00-$5.75/share range on 2013-05-15.
- Page 38: after the 2013-05-16 board meeting, BofA sent final-round process letters and a draft merger agreement to WDC and Company D, requesting responses by 2013-05-28. This supports AI row `BidderID=22`, `Final Round Ann`, 2013-05-16 and AI row `BidderID=25`, `Final Round`, 2013-05-28.
- Page 38: Company H was told its range was insufficient; on 2013-05-23 it remained interested but could not increase its range. This supports AI row `BidderID=23`, `DropBelowInf`.
- Page 38: WDC submitted a second-round indication at $9.15/share on 2013-05-28, with merger-agreement markup and ancillary drafts. This supports AI row `BidderID=24`, `Bid`, formal, 2013-05-28.
- Pages 38-39: on 2013-05-29 the board requested "best and final" proposals by 2013-05-30; on 2013-05-30 WDC verbally confirmed $9.15/share was its best possible price and Company D still needed more time. This supports AI rows `BidderID=27` and `BidderID=29` for the extension, and supports a defensible AI `BidderID=28` WDC best-and-final bid.
- Page 39: on 2013-05-31 WDC said it was reevaluating and was not prepared to move forward; it discontinued due diligence. This supports AI row `BidderID=30`, `Drop`, WDC.
- Page 40: on 2013-06-05 Company D said it would not be able to conduct active diligence for more than two weeks and was disengaging. This supports a Company D dropout on 2013-06-05, not 2013-05-28.
- Page 40: on 2013-06-10 WDC submitted a revised range of $6.60-$7.10/share; on 2013-06-14 WDC submitted $6.85/share cash as best and final. Range structure belongs in lower/upper fields, not `bid_value_pershare`.
- Page 43: on 2013-06-23 sTec, WDC, and Merger Sub executed the merger agreement; on 2013-06-24 they announced it. This supports AI row `BidderID=34`, `Executed`, 2013-06-23. Page 31 supplies the $6.85/share cash consideration.

## Validator-Flag Interpretation

No validator hard failures are apparent for STec in the fresh run flags. The emitted flags are mostly useful provenance:

- `date_inferred_from_rough` on AI `BidderID=2` (`Target Sale`, "mid-November, 2012") and `BidderID=6` (`Company D`, "In mid-March, 2013") are correct applications of the deterministic date table.
- `date_inferred_from_context` on AI `BidderID=5` (`Company B` 2013-02-27) is appropriate because the filing says "Approximately two weeks later" after 2013-02-13.
- `date_inferred_from_context` on AI `BidderID=15` (`Company E` 2013-05-01) is appropriate because the filing says "Shortly thereafter" after Company F's 2013-04-24 decline; the rule maps this to anchor + 7 days.
- `bid_lower_only` on AI `BidderID=13` is correct because Company D's 2013-04-23 verbal interest was "greater than $5.60 per share."
- `bid_range` on AI `BidderID=17`, `BidderID=21`, and `BidderID=32` is correct. Alex's lower-bound-as-headline treatment is reference-side noise.
- `final_round_inferred` on AI `BidderID=22`, `BidderID=25`, `BidderID=27`, and `BidderID=29` is appropriate, but the prompt/rule should distinguish initial non-binding IOI process letters from actual final-round process letters.
- `bidder_reengagement` on AI `BidderID=32` is correct because WDC dropped on 2013-05-31 and returned with a revised range on 2013-06-10.
- Deal-level `partial_bid_skipped` flags for Company C and six limited-asset acquirers are appropriate. Company C and the six limited-asset parties should not be full-company bid rows.

One validator gap: AI `BidderID=26` (`Company D`, `DropAtInf`, 2013-05-28) is substantively wrong but not flagged. A bidder requesting more time while expressly "continued to have an interest" should not be a dropout until the later disengagement language.

## Material Diff Adjudication

### Deal-Level Fields

| Field | Verdict | Adjudication |
|---|---|---|
| `TargetName`: AI `sTec, Inc.` vs Alex `S T E C INC` | AI correct / Alex wrong | Filing page 1 names registrant as `sTec, Inc.`. Alex is seed/workbook uppercase normalization. |
| `Acquirer`: AI `Western Digital Corporation` vs Alex `WESTERN DIGITAL CORP` | AI correct / Alex wrong | Filing page 2 says the agreement was with `Western Digital Corporation`; page 4 defines WDC. Alex is normalized ticker-style name. |
| `DateEffective`: AI `null` vs Alex `2013-09-12` | AI correct / Alex wrong | This DEFM14A predates closing and says the special meeting was scheduled for 2013-09-12. It does not state that the merger became effective on that date. Per schema, `DateEffective` should be null if the filing predates closing. |

### Bidder Type Field Disagreements

All 13 `bidder_type.public` disagreements are **reference-side**, not extraction-side. The raw extraction uses `public: false`; Alex converted reference has `public: null`. The current schema requires a boolean and the rules say `public: true` only if the filing states public-company status. The STec background identifies unnamed companies as industry participants and does not state public-company status. For this run, treat AI `public=false` as correct and update the reference converter or diff policy so `null` does not masquerade as a substantive disagreement.

### Bid Value Field Disagreements

| Row | Verdict | Adjudication |
|---|---|---|
| WDC 2013-05-03 `Bid` (`BidderID=17` AI; Alex `BidderID=14`) | AI correct / Alex wrong | Filing page 37 states a range of `$6.60 - $7.10 per share in cash`. Per §H1, `bid_value_pershare=null`, `bid_value_lower=6.60`, `bid_value_upper=7.10`. Alex incorrectly also sets `bid_value_pershare=6.6`. |
| Company H 2013-05-15 `Bid` (`BidderID=21` AI; Alex `BidderID=18`) | AI correct / Alex wrong | Filing page 37 states a range of `$5.00 - $5.75 per share in cash`. AI lower/upper structure is correct; Alex's `bid_value_pershare=5` is not. |
| WDC 2013-06-10 `Bid` (`BidderID=32` AI; Alex `BidderID=26`) | AI correct / Alex wrong | Filing page 40 states a revised range of `$6.60 to $7.10 per share in cash`. AI lower/upper structure is correct; Alex's `bid_value_pershare=6.6` is not. |

### Early Process / Bidder Interest Cardinality

Verdict: **AI mostly correct / Alex wrong.**

- AI `BidderID=1`, Company A `Bidder Interest`, 2012-11-14: correct. The filing says Company A's investment bank requested a meeting and sent a draft NDA agenda for a possible business transaction. Alex omits this.
- AI `BidderID=2`, `Target Sale`, 2012-11-15: correct. The board authorized management in mid-November 2012 to contact financial advisors about strategic alternatives, including a potential sale. Alex omits this.
- AI `BidderID=3`, Balch Hill and Potomac `Activist Sale`, 2012-12-06: correct. The filing describes an activist campaign urging strategic alternatives. Alex omits this.
- AI `BidderID=4`, Company B `Bidder Interest`, 2013-02-13: correct. Alex's 2013-04-04 date is unsupported.
- AI `BidderID=5`, Company B `DropAtInf`, 2013-02-27: correct. The date is inferred from "approximately two weeks later"; Alex folds the dropout text into an interest row and dates it 2013-04-04.
- AI `BidderID=6`, Company D `Bidder Interest`, 2013-03-15: correct under the "mid-March" date rule. Alex's 2013-04-04 date is unsupported.
- AI `BidderID=16`, Company H `Bidder Interest`, 2013-05-01: correct. Company H contacted BofA expressing interest on that date. Alex omits the interest row but includes later Company H rows.

### IB Date

Verdict: **both defensible against different event definitions; Alex's 2013-04-04 date is wrong.**

AI `BidderID=7` dates BofA Merrill Lynch `IB` to 2013-03-26, when the board approved retaining BofA. The stricter filing date for the engagement is 2013-03-28, when sTec entered into the engagement letter. Alex's 2013-04-04 date appears to be a process/NDA anchor and is not the retention date. If the extraction contract wants "board approval to retain," keep 2013-03-26; if it wants "engagement became effective," change to 2013-03-28 and cite the engagement-letter sentence on page 35.

### April 23 "Final Round Inf" Rows

Verdict: **AI correct / Alex wrong.**

Alex has two 2013-04-23 rows: `Final Round Inf Ann` and `Final Round Inf`. The AI omits them. The omission is correct. Page 36 says the April 23 process letters requested non-binding indications of interest by May 3. The filing later uses actual final-round language on page 38: after the May 16 board meeting, BofA sent "final round process letters and a draft merger agreement" requesting responses by May 28. April 23 is an initial IOI process, not a final round.

### Dropout Rows

| Event | Verdict | Adjudication |
|---|---|---|
| Company F 2013-04-24 | AI correct / Alex wrong | AI `BidderID=14` uses `DropAtInf`; Alex uses `DropTarget`. Filing says Company F "declined the invitation" and had no further communications. The agency is voluntary, even though the reason was limited-asset interest. |
| Company E 2013-05-01 | AI correct / Alex wrong on date | AI `BidderID=15` uses `DropTarget` with "shortly thereafter" mapped to 2013-05-01. Filing says the special committee decided not to continue discussions with Company E. Alex's 2013-04-24 date copies Company F's date and is not stated for Company E. |
| Company G 2013-05-03 | AI correct / Alex less precise | AI `BidderID=18` uses `DropAtInf`; Alex uses generic `Drop`. Filing says Company G indicated it would not continue in the process. |
| Company H 2013-05-23 | AI correct / Alex less precise | AI `BidderID=23` uses `DropBelowInf`; Alex uses generic `Drop`. Filing says BofA told Company H its range was insufficient to move forward and Company H could not increase. |
| Company D 2013-05-28 | AI wrong / Alex correct to omit | AI `BidderID=26` emits `DropAtInf`. Filing says Company D continued to have interest and needed about two additional weeks. Company D was still given another opportunity after WDC paused. This row should be removed. |
| WDC 2013-05-31 | AI correct / Alex wrong omission | AI `BidderID=30` correctly records WDC's temporary withdrawal. Filing says WDC was reevaluating, was not prepared to move forward, and discontinued diligence. |
| Company D 2013-06-05 | AI correct / Alex less precise | AI `BidderID=31` uses `DropAtInf`; Alex uses generic `Drop`. Filing says Company D was disengaging from the process. |

### Final-Round Dates

Verdict: **AI correct / Alex wrong.**

- AI `BidderID=22`, `Final Round Ann`, 2013-05-16: correct. Page 38 says final-round process letters and a draft merger agreement were sent after the May 16 board meeting.
- AI `BidderID=25`, `Final Round`, 2013-05-28: correct. The final-round process letters requested responses by 2013-05-28, and WDC submitted on that date.
- AI `BidderID=27`, `Final Round Ext Ann`, 2013-05-29: correct. Page 38 says the board directed BofA to request "best and final" proposals by 2013-05-30.
- AI `BidderID=29`, `Final Round Ext`, 2013-05-30: correct. Page 39 says BofA requested the best-and-final proposals, and WDC and Company D responded on 2013-05-30.
- Alex incorrectly dates `Final Round`, `Final Round Ext Ann`, and `Final Round Ext` all to 2013-05-16.

### WDC 2013-05-30 Best-and-Final Bid

Verdict: **AI correct, but somewhat duplicative.**

AI `BidderID=28` records WDC's 2013-05-30 verbal best-and-final response at $9.15/share as a formal bid. This is defensible because it was a response to the board's May 29 "best and final" request and directly led the board to move forward with WDC at $9.15/share. It repeats the 2013-05-28 price, so if Austin wants to suppress same-price confirmations, this row is a candidate. Under the current event vocabulary and formal-trigger rules, keeping it is acceptable.

### Executed Date

Verdict: **AI correct / Alex wrong.**

AI `BidderID=34` dates `Executed` to 2013-06-23. Page 43 explicitly states that on 2013-06-23 sTec, WDC, and Merger Sub executed the merger agreement. Alex dates execution to 2013-06-14, which is WDC's final $6.85/share indication, not signing.

## Extraction-Side Fixes Needed

1. **Remove AI row `BidderID=26`, Company D `DropAtInf`, 2013-05-28.** Evidence says Company D remained interested and requested additional time; later events show it remained alive until the 2013-06-05 disengagement.
2. **Decide and normalize the BofA Merrill Lynch `IB` date.** If the rule is board approval to retain, keep AI `BidderID=7` at 2013-03-26. If the rule is formal engagement, change it to 2013-03-28 and quote "sTec entered into an engagement letter with BofA Merrill Lynch to provide financial advisory services." Do not use Alex's 2013-04-04 date.
3. **Optional: review whether same-price best-and-final confirmations should be separate bid rows.** AI `BidderID=28`, WDC 2013-05-30, is defensible under current rules, but it duplicates the 2013-05-28 $9.15/share bid economically.
4. **Minor metadata:** raw `DateFiled` is null while Alex reference has 2013-08-08. The scoring report did not surface this as a deal-level disagreement. If `DateFiled` is intended to be populated from SEC metadata, this is a pipeline/metadata fill issue, not an extraction judgment issue.

## Reference-Side Corrections Needed

1. Replace normalized deal names with filing-verbatim names: `sTec, Inc.` and `Western Digital Corporation`.
2. Set `DateEffective = null` for this DEFM14A. The 2013-09-12 date is the shareholder meeting date in this filing, not the merger effective date.
3. Add missing early rows: Company A 2012-11-14 `Bidder Interest`; 2012-11-15 `Target Sale`; 2012-12-06 Balch Hill/Potomac `Activist Sale`; Company B 2013-02-13 `Bidder Interest`; Company B 2013-02-27 `DropAtInf`; Company H 2013-05-01 `Bidder Interest`.
4. Correct Company D's first interest date to 2013-03-15 under the "mid-March" date rule.
5. Correct or remove the 2013-04-23 `Final Round Inf Ann` and `Final Round Inf` rows. They are initial non-binding IOI process rows, not final-round rows.
6. Convert range bids to §H1 structure: WDC 2013-05-03 lower/upper 6.60/7.10, Company H 2013-05-15 lower/upper 5.00/5.75, WDC 2013-06-10 lower/upper 6.60/7.10, all with `bid_value_pershare=null`.
7. Update dropout codes: Company F 2013-04-24 should be `DropAtInf`; Company E should be `DropTarget` dated 2013-05-01; Company G should be `DropAtInf`; Company H should be `DropBelowInf`; Company D 2013-06-05 should be `DropAtInf`.
8. Add WDC 2013-05-31 `Drop` and retain the 2013-06-10 WDC reengagement bid.
9. Correct final-round dates: `Final Round` 2013-05-28, `Final Round Ext Ann` 2013-05-29, `Final Round Ext` 2013-05-30.
10. Correct `Executed` to 2013-06-23 and cite page 43.
11. Resolve `bidder_type.public = null` in the converted Alex reference. The current nulls are converter artifacts, not filing-backed disagreements.

## Rule / Prompt Recommendations

1. **Clarify process-letter final-round inference.** Current §K2 says process letters to a subset typically imply a final round. STec shows a counterexample: April 23 process letters requested initial non-binding IOIs, while the same filing later explicitly labels May 16 letters as "final round process letters." Recommendation: add a negative rule that initial non-binding IOI process letters are not `Final Round Inf Ann` when the filing later narrates a separate final round or when the invited parties have not yet submitted first-round indications.
2. **Clarify dropout timing for "needs more time."** A bidder that remains interested and asks for more diligence time has not dropped. Emit a dropout only when the target cuts the bidder or the bidder says it is disengaging / not continuing. This would prevent AI `BidderID=26`.
3. **Clarify limited-asset drop agency.** "Only interested in select assets" is not always `DropTarget`. If the bidder declined or self-withdrew, use `DropAtInf`; if the special committee decided not to continue because of scope mismatch, use `DropTarget`.
4. **Settle the `IB` date policy.** Choose board-approval date versus engagement-letter date. STec has both 2013-03-26 and 2013-03-28; future adjudications will stay noisy unless §J1 is explicit.
5. **Decide whether same-value best-and-final confirmations are independent bids.** STec's 2013-05-30 WDC communication is a clean example. Keeping it preserves auction-process events; suppressing it avoids duplicate economic bids.
6. **Fix reference converter public-field policy.** `public=null` in Alex JSONs produces many false field disagreements. The schema says `public` is boolean; either infer `false` absent filing evidence or have the diff ignore legacy nulls after explicit converter annotation.

## Confidence

Confidence: **high** for the major adjudications: range handling, DateEffective null, execution date, final-round dates, Company B / D / H interest rows, Company F/E/G/H dropout classifications, and WDC's 2013-05-31 drop.  

Confidence: **medium** for the BofA `IB` date because the filing separately narrates 2013-03-26 board approval and 2013-03-28 engagement-letter execution, and the rule can reasonably choose either.  

Confidence: **medium-high** for keeping WDC's 2013-05-30 best-and-final bid as a separate row. It is process-relevant and rule-supported, but economically duplicates the 2013-05-28 $9.15/share bid.

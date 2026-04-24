# Imprivata adjudication - clean reference-9 run

Deal: `imprivata`  
Raw extraction reviewed: `/tmp/sec_extract_ref9_clean/imprivata.raw.json`  
Filing text reviewed: `data/filings/imprivata/pages.json`  
Reference reviewed: `reference/alex/imprivata.json`  
Fresh diff reviewed: `scoring/results/imprivata_20260423T212321Z.md` and `.json`

## Status and disposition

Disposition: **AI extraction is materially correct against the filing. Alex/reference needs correction on most material divergences.**

I would not treat the fresh diff as evidence of a failed extraction. Most differences are caused by:

- Alex/reference using workbook-era dates or labels where current rules require filing-derived dates and current event vocabulary.
- The converter/reference leaving `bidder_type.public = null` while current schema expects a boolean and the filing supports `false` for the financial-sponsor rows.
- Alex/reference carrying redundant or misdated final-round rows.
- Alex/reference recording Sponsor B's `$17.00 - $18.00` range as a point value in `bid_value_pershare`.

No extraction JSON edits were made. No reference, rule, state, raw, or code files were edited.

## Evidence basis

Key filing passages used for adjudication:

- Page 28: Thoma Bravo's pre-bid contact - "In January 2016... reiterated Thoma Bravo's interest... No specific proposal was made."
- Page 29: March 9 Thoma Bravo proposal - "unsolicited, non-binding indication of interest... acquiring the Company for cash... $15.00 per share."
- Page 30: Barclays retention - on April 15 the Board "engaged Barclays as the Company's financial advisor," with the engagement letter countersigned April 19.
- Page 31: Target sale process and NDAs - on May 5 the Board determined to "take steps to further explore a potential business combination" and directed Barclays to contact the party list; during May 6-June 9, three strategic parties and four financial sponsors executed confidentiality agreements, including Thoma Bravo on May 10.
- Page 31: Seventh NDA signer and drop - "one financial sponsor... declined interest shortly after executing its confidentiality agreement."
- Page 32: Strategic 1 drop and initial bids - Strategic 1 said on June 8 it was "no longer interested... and would not be submitting an indication of interest"; on June 9 Sponsor A bid `$16.50`, Thoma Bravo bid `$17.25`, and Sponsor B gave a `$17.00 - $18.00` range.
- Page 33: Strategic 2, Strategic 3, and Sponsor A - Strategic 2 withdrew on June 12, Strategic 3 withdrew on June 14, and Sponsor A said on June 15 it would not bid meaningfully higher; Barclays said the Board likely would not be interested at essentially the same valuation.
- Page 35: Final bid process - on June 24 Barclays sent final bid process letters to Sponsor B and Thoma Bravo, with July 7 marked merger-agreement drafts and a July 8 final bid deadline.
- Page 35: Sponsor B drop - on June 29 Sponsor B said a final bid would be "significantly below" its June 9 indication; Barclays said the Special Committee likely would not be interested, and discussions ended.
- Page 36: July 8 bid - only Thoma Bravo submitted a final bid, at `$19.00 per share in cash`.
- Page 37: July 9 best and final - Barclays received Thoma Bravo's revised proposal at `$19.25 per share`.
- Page 39: Execution - on July 13 the parties "finalized and executed the merger agreement" and issued the announcement before market open.
- Page 10: Merger consideration - `$19.25 in cash`.

## Validator-flag interpretation

The raw extraction contains only evidence, info, and soft judgment flags in the inspected rows. I saw no hard validator-style issue in the raw content.

- Deal-level evidence flags for Goodwin, Kirkland, and the termination fee are appropriate and supported by pages 29, 36, 13, and 42.
- Raw row 1 `Thoma Bravo / Bidder Interest / 2016-01-15` has `date_inferred_from_rough` from "January 2016." This is correct under the month-only rough-date rule.
- Raw row 3 `Thoma Bravo / Bid / 2016-03-09` has `pre_nda_informal_bid`. This is correct: the $15.00 indication preceded Thoma Bravo's May 10 NDA but Thoma Bravo later did sign an NDA.
- Raw rows 7-12, the non-Thoma NDA rows, carry `date_range_collapsed` from "During the period from May 6 through June 9, 2016" to midpoint `2016-05-23`. This is rule-compliant.
- Raw row 13 `Financial Sponsor 1 / DropAtInf / 2016-05-30` carries `date_inferred_from_context` because the filing says "shortly after executing its confidentiality agreement." The exact date is not in the filing; the soft flag is appropriate.
- Raw row 16 `Thoma Bravo / Bid / 2016-06-09` has `informal_vs_formal_borderline`. The row is correctly `informal`: despite a draft merger agreement, the filing calls all three June 9 submissions "preliminary non-binding indications" subject to due diligence.
- Raw row 21 `Final Round Ann / 2016-06-24` has `final_round_inferred`. This is correct: the filing does not need the exact words "final round"; it says Barclays sent final bid process letters and set the final bid deadline.
- Raw row 24 `Thoma Bravo / Bid / 2016-07-09` has `informal_vs_formal_borderline`. `formal` is defensible and, under the current process-position rules, correct: the proposal is called non-binding, but it was a best-and-final proposal after the final-bid deadline, with a revised equity commitment and imminent signing.

## Material diff adjudication

### Deal-level fields

| Field | AI | Alex/reference | Verdict | Reason |
|---|---:|---:|---|---|
| `TargetName` | `Imprivata, Inc.` | `IMPRIVATA INC` | AI correct, Alex wrong | Current contract says filing-verbatim casing/punctuation. The filing uses "Imprivata, Inc." |
| `Acquirer` | `Thoma Bravo, LLC` | `THOMA BRAVO, LLC` | AI correct, Alex wrong | Filing-verbatim name is "Thoma Bravo, LLC"; workbook uppercase is not filing-verbatim. |
| `DateEffective` | `null` | `2016-09-16` | AI correct, Alex wrong | The DEFM14A filing predates closing and does not state a September 16 effective date in the reviewed text. Current contract says keep null unless this filing explicitly states the effective/closing date. |

### Early Thoma Bravo and Barclays chronology

- Raw row 1: `BidderID=1`, `Thoma Bravo`, `Bidder Interest`, `2016-01-15`, page 28.  
  Verdict: **AI correct, Alex wrong on date.** The filing's January 2016 passage is the clean `Bidder Interest`: interest reiterated, no proposal. Alex's `2016-03-09` date duplicates the later concrete proposal.

- Raw rows 2-3: `BidderID=2` `Bidder Sale` and `BidderID=3` `Bid`, both `Thoma Bravo`, `2016-03-09`, page 29.  
  Verdict: **Both substantively correct on event/date; AI correct on `bidder_type.public=false`.** The March 9 letter is both the concrete sale approach and the $15.00 pre-NDA informal bid.

- Raw row 4: `BidderID=4`, `Barclays`, `IB`, `2016-04-15`, page 30.  
  Verdict: **AI correct, Alex wrong.** The Board engaged Barclays on April 15, subject to a satisfactory engagement letter; Barclays then joined and advised at that meeting. Earlier March 14/24 activity was only the advisory committee considering whether Barclays would be available.

### Target sale process

- Raw row 5: `BidderID=5`, `Target Sale`, `2016-05-05`, page 31.  
  Verdict: **AI correct, Alex omission.** The Board determined it was in stockholders' best interests to "take steps to further explore a potential business combination" and directed Barclays to contact the approved list. This is a `Target Sale` event under the current rulebook.

### NDA rows and the seventh financial sponsor

- Raw row 6: `Thoma Bravo / NDA / 2016-05-10`, page 31.  
  Verdict: **AI correct.** Exact date is stated.

- Raw rows 7-12: `Strategic 1`, `Strategic 2`, `Strategic 3`, `Sponsor A`, `Sponsor B`, and `Financial Sponsor 1`, each `NDA / 2016-05-23`, page 31.  
  Verdict: **AI correct, Alex wrong/incomplete on dates; AI and Alex both capture the unnamed extra financial sponsor.** The filing states exactly seven NDA signers: three strategic parties and four financial sponsors, including Thoma Bravo. It later names the six that attended management presentations and separately identifies the one financial sponsor that declined. Current range-date rules collapse the May 6-June 9 period to midpoint `2016-05-23` for the non-Thoma NDA dates. Alex/reference leaves the date precise as null and uses a rough `2016-05-06` workbook artifact.

- Label note: AI's `Financial Sponsor 1` and Alex's `Another financial sponsor` refer to the same filing party. This is not a material disagreement; if the project wants stricter placeholder wording, prefer the rulebook's `"Financial k"` style on regeneration.

### Drops before and at the informal stage

- Raw row 13: `Financial Sponsor 1 / DropAtInf / 2016-05-30`, page 31.  
  Verdict: **AI correct on event type; AI date is rule-compliant but inherently inferred; Alex date is wrong.** The filing says the sponsor "declined interest shortly after executing its confidentiality agreement." `DropAtInf` is the right code because the party self-withdrew before submitting an indication. The exact date is unknown, so the AI's soft context-inference flag is necessary.

- Raw row 14: `Strategic 1 / DropAtInf / 2016-06-08`, page 32.  
  Verdict: **AI correct, Alex less precise.** Alex has a generic `Drop` row. The filing says Strategic 1 told Barclays it was no longer interested and would not submit an indication; this is a voluntary informal-stage withdrawal, so `DropAtInf` is the current-rule code.

- Raw rows 18-19: `Strategic 2 / DropAtInf / 2016-06-12`, page 32, and `Strategic 3 / DropAtInf / 2016-06-14`, page 33.  
  Verdict: **AI correct, Alex less precise.** Both strategic parties voluntarily stopped participating before any bid; current vocabulary supports `DropAtInf`, not generic `Drop`.

- Raw row 20: `Sponsor A / DropBelowInf / 2016-06-15`, page 33.  
  Verdict: **AI correct, Alex wrong.** Sponsor A said it would not bid meaningfully above its June 9 $16.50 indication, then Barclays told Sponsor A the Board likely would not be interested at essentially the same valuation and discussions ended. That is best represented as a target-side failure to advance past the informal round, `DropBelowInf`, not `DropAtInf`.

- Raw row 22: `Sponsor B / DropBelowInf / 2016-06-29`, page 35.  
  Verdict: **AI correct.** Sponsor B said any final bid would be significantly below its June 9 range; Barclays said the Special Committee likely would not be interested, and discussions ended.

### June 9 initial bids and Sponsor B range

- Raw row 15: `Sponsor A / Bid / informal / 2016-06-09 / $16.50`, page 32.  
  Verdict: **AI correct.**

- Raw row 16: `Thoma Bravo / Bid / informal / 2016-06-09 / $17.25`, page 32.  
  Verdict: **AI correct.** The draft merger agreement does not override the filing's "preliminary non-binding indication" and due-diligence condition.

- Raw row 17: `Sponsor B / Bid / informal / 2016-06-09 / lower=17.00, upper=18.00`, page 32.  
  Verdict: **AI correct, Alex wrong on `bid_value_pershare`.** The filing says "range of $17.00 - $18.00 per share." Current rules require `bid_value_pershare=null`, `bid_value_lower=17`, `bid_value_upper=18`, and `bid_range` info flag. Alex/reference currently has `bid_value_pershare=17` while also carrying lower/upper bounds, which violates the current range convention.

### Final-round rows

- Raw row 21: `Final Round Ann / 2016-06-24`, page 35.  
  Verdict: **AI correct, Alex wrong on competing June 9 final-round date.** The first clear final-round event is June 24, when Barclays sent final bid process letters and set the July 8 final bid deadline.

- Alex-only `Final Round Inf Ann / 2016-06-09` and `Final Round Inf / 2016-06-09`.  
  Verdict: **AI correct to omit; Alex wrong.** June 9 is the initial indication deadline and bid date. The Board/Special Committee had not yet sent final bid process letters. The later June 24 final bid letters supersede the idea that June 9 was final-round announcement or final-round event.

- Alex-only `Final Round Ext Ann / 2016-06-24` and `Final Round Ext / 2016-06-24`.  
  Verdict: **AI correct to omit; Alex wrong.** The filing says June 24 set the final bid deadline. It does not describe an extension of an earlier final deadline.

- Alex-only `Final Round / 2016-06-24`.  
  Verdict: **Alex wrong as dated.** If the live rulebook requires a separate non-bidder `Final Round` row in addition to bid rows, the correct date would be July 8, the final bid deadline/submission date, not June 24. The AI already has Thoma Bravo's July 8 final bid as raw row 23. This is the only remaining extraction-side ambiguity I would send back to the rule/prompt owner: decide whether a standalone `Final Round` row is required when the formal bid row already cites the final-bid deadline.

### Formal bids and execution

- Raw row 23: `Thoma Bravo / Bid / formal / 2016-07-08 / $19.00`, page 36.  
  Verdict: **AI correct.** The filing says only Thoma Bravo submitted a bid by the final bid deadline, at `$19.00 per share in cash`, with completed diligence and readiness to execute.

- Raw row 24: `Thoma Bravo / Bid / formal / 2016-07-09 / $19.25`, page 37.  
  Verdict: **AI correct.** Although the filing calls the July 9 proposal non-binding, the process context is formal/final: best-and-final, revised equity commitment, and imminent signing.

- Raw row 25: `Thoma Bravo / Executed / 2016-07-13 / $19.25`, pages 39 and 10.  
  Verdict: **AI correct, Alex wrong on date.** The merger agreement was executed July 13 before market open. Alex's July 9 date is the best-and-final offer date, not execution. The `$19.25` merger consideration is supported by page 10.

### Bidder type field disagreements

Verdict: **AI correct, reference/converter policy needs correction.**

The nine `bidder_type` field disagreements are all `public=false` in AI versus `public=null` in Alex/reference. Current schema defines `public` as a boolean. For the financial sponsors, false is directly supported by the filing's financial-sponsor/private-equity language. For anonymous strategic parties, current rule text says `public: true` only if the filing states the bidder is publicly traded; the filing does not do so. The reference-side `null` values are converter artifacts, not filing-grounded corrections to the AI.

## Extraction-side fixes needed

Required extraction fixes: **none on core event facts.**

Optional / policy-dependent extraction follow-up:

- Decide whether to require a standalone `Final Round` row dated `2016-07-08` in addition to raw row 23 (`Thoma Bravo / Bid / formal / 2016-07-08`). If yes, the extractor missed that row and should add it in a future run. If no, raw row 21 plus the formal bid rows are sufficient.
- Consider standardizing the unnamed extra financial sponsor alias from `Financial Sponsor 1` to the rulebook's shorter placeholder style (`Financial 1`) if placeholder naming is intended to be strict. This is not a substantive data error.

## Reference-side corrections needed

Regenerate or patch the Imprivata reference side to align with the filing and current rules:

- Set deal fields to filing-verbatim `TargetName="Imprivata, Inc."`, `Acquirer="Thoma Bravo, LLC"`, and `DateEffective=null`.
- Change Thoma Bravo `Bidder Interest` to January 2016 mapped date `2016-01-15`, with rough-date flag if reference JSONs are intended to carry current-rule date metadata.
- Change Barclays `IB` date to `2016-04-15`.
- Add/keep `Target Sale` dated `2016-05-05`.
- Represent all seven NDA signers: Thoma Bravo exact `2016-05-10`; the other six NDA rows as May 6-June 9 range-collapsed `2016-05-23`.
- Convert the unnamed financial sponsor's post-NDA withdrawal to `DropAtInf` with the context-inferred date under current section B3 handling, or else explicitly document a reference exception if Alex wants exact unknown dates to remain null.
- Convert Strategic 1, Strategic 2, and Strategic 3 from generic `Drop` to `DropAtInf`.
- Convert Sponsor A from `DropAtInf` to `DropBelowInf`.
- Remove June 9 `Final Round Inf Ann` and `Final Round Inf`.
- Keep only a June 24 `Final Round Ann` for the final bid process letters; remove `Final Round Ext Ann` and `Final Round Ext`.
- If a standalone final-round terminal row is kept, date it July 8, not June 24.
- For Sponsor B's June 9 bid, set `bid_value_pershare=null`, `bid_value_lower=17`, `bid_value_upper=18`, and keep the range flag/convention.
- Set `bidder_type.public` booleans consistently, at least for all financial sponsors (`false`).
- Change `Executed` to `2016-07-13`.

## Rule and prompt recommendations

1. Clarify whether final-round announcement rows require paired terminal `Final Round` / `Final Round Inf` rows when the actual bids already appear as `Bid` rows. Imprivata exposes the ambiguity: June 24 is clearly `Final Round Ann`; July 8 is the final bid deadline and formal bid date. The current output has the bid row but not a separate `Final Round` row.

2. Clarify placeholder labels for extra unnamed financial sponsors. Current rules mention `"Financial k"` placeholders, while this raw extraction uses `Financial Sponsor 1`. The meaning is clear, but stable labels will reduce false diffs.

3. Keep the range-bid rule prominent in the converter and prompt. Sponsor B's `$17.00 - $18.00` bid should never populate `bid_value_pershare`; the raw AI extraction handles this correctly.

4. Resolve the known converter-side `bidder_type.public=null` issue. The Imprivata diff confirms it creates noise without adding filing-grounded information.

5. Preserve the current pre-NDA bid handling. Imprivata is a clean example: Thoma Bravo made a priced pre-NDA indication on March 9, signed an NDA on May 10, and therefore the `pre_nda_informal_bid` row is correct without any no-NDA exemption.

## Confidence

Overall confidence: **High**.

High-confidence items: deal names, `DateEffective=null`, January 2016 Thoma Bravo interest, April 15 Barclays IB row, May 5 `Target Sale`, seven NDA signers, Sponsor B range handling, June 24 final-round announcement, July 8 and July 9 Thoma Bravo bids, July 13 execution.

Medium-confidence / policy-dependent items: the inferred date for the unnamed financial sponsor's "shortly after" drop, because the exact NDA date is not known; and whether to add a separate July 8 `Final Round` row in addition to the July 8 formal bid row.

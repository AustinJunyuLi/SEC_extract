# Petsmart Inc. adjudication - clean reference-9 run

## Status / disposition

Disposition: **not verified clean yet**. The raw extraction passes the deterministic validator when run read-only against `data/filings/petsmart-inc/pages.json` (`row_flags=[]`, `deal_flags=[]`), and most large AI-vs-Alex divergences are AI-correct under the current rulebook. However, the extraction needs targeted fixes before Austin treats it as manually verified:

- Add the missing October preliminary informal-round marker rows: `Final Round Inf Ann` around 2014-10-15 from "During October..." and `Final Round Inf` on 2014-10-30.
- Delete or recode raw row 2 (`Target Sale`, 2014-06-18): the cited passage is a broader strategic/capital-structure review, not yet a board decision to explore a sale.
- Resolve deal-level `Acquirer`: raw uses legal Parent (`Argos Holdings Inc.`), while Alex/manifest use the ultimate Buyer Group. The filing supports both labels, so the rule should specify which field means what.
- Decide whether post-final-round confidentiality agreements between Longview and bidders are in-scope `NDA` rows. Raw rows 45 and 53 are cited, but they are inter-bidder/rollover confidentiality agreements, not the initial target-bidder NDAs used for auction counting.

Overall confidence: **medium-high** for the event adjudication; **medium** on Acquirer and Longview confidentiality agreement policy because the current schema does not fully disambiguate legal acquirer vs ultimate buyer group or target-bidder NDA vs inter-bidder NDA.

## Evidence basis

Sources read for this adjudication:

- Raw extraction: `/tmp/sec_extract_ref9_clean/petsmart-inc.raw.json`
- Filing text: `data/filings/petsmart-inc/pages.json`
- Alex reference: `reference/alex/petsmart-inc.json`
- Fresh diff: `scoring/results/petsmart-inc_20260423T212321Z.md` and `.json`

Key filing evidence:

- Page 28 / raw source page 28: first-quarter 2014 Industry Participant history: board considered a merger/acquisition with a privately held industry participant and in March authorized management to contact that party. This supports raw row 1 (`Target Interest`, 2014-03-15), but not a broad `Target Sale`.
- Page 29 / raw source page 29: July 3 JANA 13D and July 7 Longview public letter are separately narrated. This supports two `Activist Sale` rows, raw rows 3 and 4, not Alex's single collapsed row.
- Page 29 / raw source page 29: August 13 board decision to explore strategic alternatives, including a possible sale, supports raw row 7 (`Target Sale`, 2014-08-13).
- Page 30 / raw source page 30: August 19 press release announcing exploration of strategic alternatives including possible sale supports raw rows 8 and 9 (`Target Sale Public`, `Sale Press Release`) on 2014-08-19.
- Page 30 / raw source page 30: August 27 Industry Participant was told it would not be invited into the exploratory process; no further contact followed. This supports raw row 10 (`DropTarget`, 2014-08-27).
- Page 30 / raw source page 30: first week of October 2014, 15 potentially interested financial buyers entered confidentiality and standstill agreements. This supports raw rows 11-25 as 15 atomized NDA rows, with date `2014-10-05` under `rules/dates.md` section B1.
- Page 31 / raw source page 31: October 30 six parties submitted indications; Buyer Group range was `$81.00-$83.00`, another bidder was `$80.00-$85.00`, Bidder 2 first indicated `$78.00` and then increased to `$81.00-$84.00` during calls from October 30 to November 2. This supports raw rows 26-32 more closely than Alex rows 22-28.
- Page 31 / raw source page 31: November 3 board allowed four bidders at/above `$80.00` into final round and notified eliminated parties. This supports raw row 33 (`Final Round Ann`) and raw rows 34-44 (`DropBelowInf`) for the 11 NDA signers not proceeding.
- Page 32 / raw source page 32: December 10 final bid letters from Buyer Group and Bidder 2, plus verbal indication from Bidder 3 not above approximately `$78`. This supports raw rows 47-49 and raw rows 50-51 (`DropBelowM`) for the Bidder 3 constituents.
- Page 33 / raw source page 33: December 12 improved bids: Bidder 2 at `$81.50`, Buyer Group oral `$82.50`, later best and final `$83.00`. This supports raw rows 54-57.
- Page 33 / raw source page 33: December 14 execution of merger agreement, voting agreement, related transaction agreements, and press release. This supports raw row 58 (`Executed`, 2014-12-14); no separate post-execution sale press release row should be emitted under the current rulebook.

## Validator-flag interpretation

The deterministic validator is clean on the raw file:

- `pipeline.validate(raw, filing)` returned no row flags and no deal flags.
- Therefore there are no hard validator blockers and no Python-raised soft flags.

The raw extraction itself contains useful extractor-authored flags:

- `date_inferred_from_rough`: row 1 (`March, 2014` -> 2014-03-15), row 5 (`July, 2014` -> 2014-07-15), and rows 11-25 (`first week of October 2014` -> 2014-10-05). These are correct under `rules/dates.md` section B1.
- `bid_range`, `bid_lower_only`, `bid_upper_only`, and `bid_value_unspecified`: correct audit flags for rows 26-32 and 49 under `rules/bids.md` section H1.
- `date_range_collapsed`: raw row 32 correctly collapses "From October 30 to November 2, 2014" to 2014-10-31.
- `final_round_inferred`: rows 33, 46, 52, and 57 are reasonable inferred final-round markers.
- `informal_vs_formal_borderline`: row 49 (`Bidder 3`, 2014-12-10) is a real judgment point. Current rules tilt to `formal` because it occurs at the final-bid deadline, but the filing says only a verbal indication and no written offer.
- `joint_nda_aggregated`: rows 45 and 53 are not validator problems, but they need a policy decision because they are Longview/bidder confidentiality agreements rather than the initial 15 target-process NDAs.

## Material diff adjudication

### Deal-level fields

- `TargetName`: **AI correct / Alex wrong.** Raw `PetSmart, Inc.` matches the filing's naming in the proxy; Alex/manifest `PETSMART INC` is legacy all-caps.
- `Acquirer`: **both defensible; rule clarification needed.** Raw `Argos Holdings Inc.` is the legal Parent in the merger agreement. Alex's Buyer Group string is the ultimate owner group; the filing says Parent "will be owned by the Buyer Group." If `Acquirer` means legal merger counterparty, AI is correct. If it means ultimate economic buyer for the research dataset, Alex is correct. Current rules say "filing-read" but do not choose between these two filing-supported labels.
- `DateEffective`: **AI correct / Alex wrong for this filing.** The DEFM14A predates closing and says completion is anticipated in the first half of 2015; `rules/schema.md` says `DateEffective = null` if the filing predates closing. Alex's `2015-03-11` appears to be external closing knowledge, not from this filing.

### Start-of-process and activist rows

- Raw row 1, `Industry Participant` `Target Interest`, 2014-03-15: **AI correct / Alex wrong by omission.** The filing says the board authorized management in March 2014 to contact Industry Participant about exploratory merger/acquisition discussions.
- Raw row 2, `Target Sale`, 2014-06-18: **AI wrong / Alex correct by omission.** The cited June 18 passage is about reviewing strategic/financial alternatives and focusing on capital structure/returning capital. It does not yet say the board resolved to explore a sale.
- Raw rows 3-4, `JANA Partners` and `Longview` `Activist Sale`, 2014-07-03 and 2014-07-07: **AI correct / Alex wrong.** The filing narrates separate activist pressure on separate dates. This is also explicitly the Petsmart example in `rules/events.md` section D1.b.
- Raw row 5, `J.P. Morgan` `IB`, 2014-07-15: **AI correct / Alex wrong on date.** Filing says "In July"; current date rule maps month-only to the 15th. Alex uses July 1.
- Raw row 6, `Industry Participant` `Bidder Interest`, 2014-08-07: **AI correct / Alex wrong by omission.** The party contacted J.P. Morgan and said it might be interested if PetSmart pursued strategic alternatives.
- Raw row 7, `Target Sale`, 2014-08-13: **AI correct / Alex incomplete.** The board determined to explore strategic alternatives including possible sale and to commence a process to determine sale value.
- Raw rows 8-9, `Target Sale Public` and `Sale Press Release`, 2014-08-19: **AI correct / Alex partially wrong.** Alex has the press release but places `Target Sale Public` on August 13. Public announcement occurred on August 19.
- Raw row 10, `Industry Participant` `DropTarget`, 2014-08-27: **AI correct / Alex wrong by omission.** Target/J.P. Morgan declined to invite Industry Participant because of antitrust/process concerns.

### October NDAs

- Raw rows 11-25, 15 financial-buyer NDA rows, 2014-10-05: **AI correct / Alex mostly correct on count but wrong on date under current rules.** The filing states exactly 15 financial buyers entered confidentiality and standstill agreements in the first week of October. Current date mapping gives 2014-10-05; Alex uses 2014-10-07. The atomized shape is correct under section E2.b because the filing gives a numeric count.
- Raw rows 45 and 53, `Longview and the Buyer Group` NDA rows, 2014-12-09 and 2014-12-12: **both defensible; policy clarification needed.** The cited confidentiality agreements are real. But they are not the initial Company-to-potential-bidder sale-process NDAs; they are Longview/bidder confidentiality arrangements around rollover and bid-price sharing. If `NDA` is any confidentiality agreement in the sale process, AI is correct. If `NDA` is only target-bidder confidentiality agreements relevant to the auction funnel, these rows should be dropped or excluded from the auction count.

### October 30 informal bids and eliminated parties

- Raw row 26, Buyer Group `$81-$83`: **AI correct / Alex wrong on value shape.** This is a range; `bid_value_pershare` should be null, lower 81, upper 83. Alex carries 81 as `bid_value_pershare`.
- Raw row 27, another bidder `$80-$85`: **AI correct on event/value; alias assignment is inherently synthetic.** The filing gives one additional bidder with this range. Alex captures a comparable row as `Unnamed party 4`; AI's "another bidder" alias is closer to the filing phrase.
- Raw row 28, third bidder at least `$80`: **AI correct / Alex incomplete.** The filing says three bidders initially had ranges reaching at least `$80`, and only two ranges are fully specified; the third is a lower-bound-only event. AI records lower 80 and leaves upper null.
- Raw rows 30-31, two additional unspecified-price indications: **AI correct / Alex partially correct.** Six parties submitted indications; after Buyer Group, another bidder, the third at-least-80 bidder, and Bidder 2, two indication events remain without stated prices. Keeping unspecified-price bid rows with info flags is correct under section H1.
- Raw rows 29 and 32, Bidder 2 `$78` then `$81-$84`: **AI correct / Alex wrong on date of revised range.** The initial `$78` indication is tied to October 30. The increase occurred during J.P. Morgan calls from October 30 to November 2, so AI's `2014-10-31` midpoint with `date_range_collapsed` is correct. Alex puts both on October 30.
- Alex-only rows 29-36, generic `Drop` rows on 2014-10-30: **AI correct / Alex wrong.** The actual target cut occurs after the November 3 board decision, not on October 30, and the agency is target-side/non-advancement, not voluntary generic `Drop`.
- Raw rows 34-44, `DropBelowInf` for Financial Buyers 5-15 on 2014-11-03: **AI correct.** Fifteen NDA signers minus four finalists equals eleven eliminated parties. The filing says the eliminated parties were notified after the November 3 board meeting and none showed ability/interest above their initial indications.

### Missing preliminary informal-round markers

- Alex row 4, `Final Round Inf Ann`, rough 2014-10-15: **Alex correct / AI wrong by omission.** The filing says "During October, the potential bidders were informed that non-binding preliminary indications of interest would be due on October 30, 2014." Under the current final-round vocabulary this should be an informal-round announcement. Date should be inferred from "During October" as 2014-10-15.
- Alex row 39, `Final Round Inf`, 2014-10-30: **Alex correct / AI wrong by omission.** The October 30 preliminary indication deadline should be represented as the corresponding informal-round deadline/submission marker.

### November 3 / formal final round

- Raw row 33, `Final Round Ann`, 2014-11-03: **AI correct / Alex wrong on date.** The board on November 3 determined to allow four bidders to proceed to final round. Alex uses a rough mid-November date, which is not supported by the filing.
- Alex rows 37-38, `DropTarget` for unnamed parties on 2014-11-03: **AI correct / Alex wrong.** The parties not proceeding because they did not meet/maintain price levels belong as `DropBelowInf`, not `DropTarget`.

### December final bids, Bidder 3, and execution

- Raw rows 47-48, Buyer Group `$80.70` and Bidder 2 `$80.35`, 2014-12-10: **AI correct.** These are final bid letters with revised merger documents, so formal point bids.
- Raw row 49, Bidder 3 verbal indication not above approximately `$78`: **both defensible on bid type; AI correct on value shape.** The value should be upper-only (`bid_value_upper=78`, `bid_value_pershare=null`). On `bid_type`, the filing cuts both ways: it is at the final-bid deadline, but it is verbal and expressly not a written offer. Current rules support AI's `formal` via process-position fallback; Alex's `informal` is also a plausible economic interpretation.
- Raw rows 50-51, Bidder 3 constituent `DropBelowM` rows: **AI correct under current consortium-drop rule.** Bidder 3 was a two-party consortium and did not submit a written offer after being told its valuation was unlikely to be competitive; splitting the drop per original NDA signer follows `rules/events.md` section I1.
- Raw row 46, `Final Round Ext Ann`, 2014-12-10; row 52, `Final Round`, 2014-12-10; row 57, `Final Round Ext`, 2014-12-12: **AI correct / Alex only rough.** The dates are explicit in the filing. Alex has comparable rows but stores them as rough dates.
- Raw rows 54-56, December 12 improved bids: **AI correct.** Bidder 2 `$81.50`, Buyer Group oral `$82.50`, and later best-and-final `$83.00` are all stated in the filing.
- Raw row 58, `Executed`, 2014-12-14: **AI correct / Alex wrong by omission.** The filing explicitly states the parties executed the merger agreement, voting agreement, and related transaction agreements and issued a press release on December 14. Under the current rulebook, the press release is folded into `Executed`.

## Extraction-side fixes needed

1. Delete raw row 2 (`Target Sale`, 2014-06-18) unless Austin wants a new non-sale strategic-review event, which the current closed vocabulary does not have.
2. Add `Final Round Inf Ann` with rough phrase "During October" mapped to 2014-10-15, citing the page 30 sentence that non-binding preliminary indications were due October 30.
3. Add `Final Round Inf` on 2014-10-30, tied to the preliminary indication deadline and the six October 30 indications.
4. Resolve `Acquirer`. My recommendation for the current research schema is to use the ultimate Buyer Group string from the filing/manifest, and keep legal Parent (`Argos Holdings Inc.`) in evidence or a future legal-counterparty field if needed. If the schema intentionally wants legal Parent, add a clear rule and require a `deal_identity_mismatch` flag against manifest.
5. Decide whether rows 45 and 53 are in-scope `NDA`s. If `NDA` means target-bidder confidentiality for auction-funnel counting, drop them. If broader confidentiality agreements remain in scope, keep them but ensure downstream auction counts distinguish target-process NDAs from rollover/inter-bidder CAs.
6. Keep row 49's `informal_vs_formal_borderline` visible for Austin. I would not force a change until the rulebook decides whether a non-written verbal indication at a final-bid deadline is formal.

## Reference-side corrections needed

Alex/reference should be regenerated or patched to align with filing-grounded current rules:

- Split the single `Activist Sale` row into JANA Partners on 2014-07-03 and Longview on 2014-07-07.
- Add Industry Participant rows: `Target Interest` on 2014-03-15, `Bidder Interest` on 2014-08-07, and `DropTarget` on 2014-08-27.
- Move `Target Sale Public` to 2014-08-19 and keep `Sale Press Release` on 2014-08-19; add/keep `Target Sale` on 2014-08-13.
- Change J.P. Morgan `IB` rough date from July 1 to 2014-07-15 under month-only mapping.
- Change October NDA rough date from 2014-10-07 to 2014-10-05 under "first week" mapping.
- Preserve range/single-bound bid values per section H1: ranges should not populate `bid_value_pershare`; Bidder 3's December 10 valuation should be upper-only.
- Replace Alex's generic October 30 `Drop` rows and November 3 `DropTarget` rows with the AI-style November 3 `DropBelowInf` rows for the 11 non-finalist NDA signers.
- Represent Bidder 2's revised `$81-$84` indication as a date-range-collapsed row on 2014-10-31, not a second October 30 row.
- Add a single `Executed` row for Buyer Group on 2014-12-14 with `$83.00` cash consideration and financing-contingency evidence.
- Set `DateEffective` to null for this DEFM14A-derived extraction unless a future rule allows post-filing external closing dates in reference JSON.
- Resolve `bidder_type.public`: Alex converter currently leaves `public=null` while AI uses `false` for financial buyers. This is a converter/reference-policy issue rather than a filing disagreement.

## Rule / prompt recommendations

- Clarify `Acquirer`: choose "legal merger counterparty" versus "ultimate economic buyer group." Petsmart proves both can be filing-verbatim and materially different.
- Clarify whether `NDA` includes inter-bidder / rollover confidentiality agreements. If included, add a field or flag so auction-threshold NDA counts use only target-process bidder NDAs.
- Add an extractor reminder for preliminary informal bid deadlines: phrases like "non-binding preliminary indications of interest would be due on [date]" should emit both `Final Round Inf Ann` and `Final Round Inf`.
- Clarify row 49 pattern: a verbal non-written valuation at a final-bid deadline. Current process-position fallback says formal; a written-offer requirement would say informal or perhaps no formal bid. This should be a named rule example because Petsmart will otherwise remain unstable across runs.
- Keep the Petsmart activist atomization example in section D1.b; the AI followed it correctly and the reference is the stale side.

## Confidence

High confidence:

- Activist atomization, Industry Participant rows, August 13/August 19 sale-process rows, October NDA atomization/count, October bid value shapes, November 3 final-round cut and `DropBelowInf` rows, December 12 bids, and December 14 execution.

Medium confidence:

- Deal-level `Acquirer`, because both `Argos Holdings Inc.` and the Buyer Group are supported by different filing definitions.
- Longview confidentiality rows 45 and 53, because the filing supports the facts but the current schema does not clearly say whether inter-bidder/rollover CAs belong in the `NDA` event set.
- Bidder 3's December 10 `bid_type`, because the filing says both "final bid" context and "verbal indication/no written offer."

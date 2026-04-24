# Saks Clean Ref-9 Adjudication

Deal: `saks`  
Raw extraction reviewed: `/tmp/sec_extract_ref9_clean/saks.raw.json`  
Filing reviewed: `data/filings/saks/pages.json` pages 1-4, 8, 10, 30-36, and merger-agreement appendix pages referenced by search  
Reference reviewed: `reference/alex/saks.json`  
Fresh diff reviewed: `scoring/results/saks_20260423T212321Z.md` and `.json`

## Status / Disposition

Status: **passes the substantive filing chronology better than Alex, but not clean as-is**.

The AI output captures the core Saks auction chronology correctly: Sponsor A initial interest in February 2013, Hudson's Bay initial interest on April 1, board exploration on April 4 and June 5, April confidentiality agreements, June indicative ranges, July 2 final-round request, July 11 proposals, July 23-24 narrowing to Hudson's Bay at $16, July 28 execution, and go-shop Company I activity through September 6.

However, the raw extraction needs targeted fixes before this deal should be marked verified:

- Correct raw row 5: the April 15 week price indication was made by **Sponsor A**, not jointly by Sponsor A and Sponsor E. Sponsor E participated in the meeting, but the filing says "Each of Hudson's Bay and Sponsor A indicated..." the $15-or-more price.
- Recode ambiguous dropout rows where the filing does not identify a voluntary withdrawal. In particular raw row 19 for Sponsor G should be generic `Drop`, not `DropAtInf`; raw row 26 for Company I is also better as generic `Drop` unless the rulebook explicitly treats "no proposal submitted by deadline" as `DropAtInf`.
- Fix same-date ordering violations flagged by the validator: June 5 `Target Sale` should sort before June 5 informal bids, and July 11 informal bid should sort before July 11 formal bid under the current rank table.
- Treat raw row 23 Morgan Stanley `IB` as a judgment call. The filing calls Morgan Stanley a "long-time advisor" and places it in board meetings, but does not narrate a discrete engagement/retention event.

Reference-side corrections are more substantial. Alex's Saks reference still contains legacy artifacts the current rulebook should not preserve: Company H should be skipped under the Saks-specific §M1 migration note; the July 11 Sponsor A/E bid should instead be Sponsor E/G; the July 28 "Spnosor A/E" `DropTarget` row should be replaced by July 23 constituent `DropBelowM` rows or removed in favor of AI's split handling; DateEffective should be null for this filing; and public-status fields should not be imported from outside the filing.

## Evidence Basis

Key filing passages Austin can verify quickly:

- Page 1: registrant name is **Saks Incorporated**.
- Page 2: the merger agreement is dated July 28, 2013 and is among Hudson's Bay Company, Harry Acquisition Inc., and the Company; consideration is "$16 in cash".
- Page 10: the proxy states the merger is anticipated to complete in November 2013, not that it already closed on a specific date.
- Page 30: Goldman Sachs participated in strategic reviews for years; "One such review took place in December 2012."
- Page 30: Sponsor A made the first contact: "In February 2013... received an unsolicited phone call... Sponsor A... expressing interest..."
- Page 30: Hudson's Bay first-contact: "On April 1, 2013... discussed a potential acquisition... No specific proposals..."
- Page 30: April 4 board exploration: the board reviewed interest from Hudson's Bay and Sponsor A and "directed Mr. Sadove and Saks management to continue exploring these potential transactions."
- Page 31: April 15 week bids: "Each of Hudson's Bay and Sponsor A indicated that they were considering making an offer... for at least $15 per share, in cash." The same sentence block says Sponsor E participated in Sponsor A's meeting, but does not say Sponsor E made the indication.
- Page 31: April 26 NDAs with Sponsor A and Sponsor E; April 30 NDA with Hudson's Bay.
- Page 32: June 3 week ranges: Hudson's Bay at "$15 to $15.25" and Sponsor A/Sponsor E at "$15 to $16".
- Page 32: June 5 board authorization: the board authorized "the implementation of a process" with acquirors that had executed confidentiality agreements.
- Page 32: Company F indicated interest in participating with Sponsor A and Sponsor E, conducted diligence, but "did not participate in the offer that was ultimately submitted".
- Page 32: July 2 final-round invitation: Goldman Sachs distributed draft merger agreement and process details, requesting offers by July 11.
- Page 33: early July Sponsor A role change, Sponsor G entry, and July 8 Sponsor G NDA.
- Page 33: July 11 proposals: Hudson's Bay submitted $15.25 with revised merger agreement and committed financing documents; Sponsor E/Sponsor G submitted an indicative $14.50-$15.50 range with more diligence needed and no financing support.
- Page 33: Sponsor G later exit: "Sponsor G was no longer participating in the process"; no date or initiator is stated.
- Page 34: Company H: unsolicited $2.6 billion aggregate-price letter, no details, no successful follow-up, and no subsequent communications.
- Page 34: July 23 Sponsor A/E status: no indication they would increase beyond the $14.50-$15.50 range or finish diligence faster.
- Page 34: July 24 Hudson's Bay advised it was prepared to offer $16, subject to definitive agreement.
- Page 35: July 28 board approval and execution; July 29 press release.
- Page 35: go-shop ended September 6; Company I was the only go-shop party that executed a confidentiality agreement and conducted diligence; no go-shop party submitted an acquisition proposal.
- Page 36: Company I NDA timing: Saks stated Company I "had not signed a confidentiality agreement until approximately two weeks after the merger agreement was executed."

## Validator-Flag Interpretation

I reran `pipeline.validate(raw, load_filing("saks"))` read-only. It returned two hard row-order flags and no deal-level flags:

- `bidder_id_same_date_rank_violation`, row_index 11: same date 2013-06-05, raw row 11 Sponsor A/E informal `Bid` appears before raw row 12 `Target Sale`. Under §A3, `Target Sale` rank 2 precedes informal bids rank 6. This is an ordering/canonicalization problem, not a substantive extraction problem.
- `bidder_id_same_date_rank_violation`, row_index 16: same date 2013-07-11, raw row 16 Hudson's Bay formal `Bid` appears before raw row 17 Sponsor E/G informal `Bid`. Under §A3, informal bids rank 6 and formal bids rank 7. Again, this is ordering only.

Extractor self-flags are mostly appropriate:

- Raw rows 5, 10, 11, 13: `date_range_collapsed` / inferred rough-date flags are appropriate for "During the week of..." language. The midpoint dates 2013-04-17, 2013-06-05, and 2013-06-12 are consistent with §B4.
- Raw row 17: `informal_vs_formal_borderline` is appropriate. Even though the July 11 submission responded to a formal process request, the filing calls Sponsor E/G's proposal indicative, says they required more diligence, and says they lacked revised merger agreement and financing support.
- Raw row 18: `date_inferred_from_context` is appropriate if Company F is kept as a dropout. The filing only says Company F did not participate in the ultimately submitted offer; anchoring to the July 11 offer date is inferential.
- Raw row 19: `date_unknown` and `drop_agency_ambiguous` are appropriate, but the event code should follow the ambiguity flag: generic `Drop`, not `DropAtInf`.
- Raw row 26: `bidder_type_ambiguous` is appropriate for Company I. The filing does not identify whether Company I is strategic or financial.
- Deal flag `unsolicited_letter_skipped` for Company H is correct under the Saks §M1 migration note.
- Deal flag `out_of_scope_company_b_track_skipped` is correct. Company B was a target Saks considered acquiring, not a bidder for Saks.

## Material Diff Adjudication

### Deal-Level Fields

| Diff | Verdict | Rationale |
|---|---|---|
| `TargetName`: AI `Saks Incorporated`, Alex `SAKS INC` | AI correct / Alex wrong | Page 1 and page 2 identify the registrant/company as Saks Incorporated. Alex uses legacy uppercase shorthand. |
| `Acquirer`: AI `Hudson's Bay Company`, Alex `HUDSON'S BAY COMPANy` | AI materially correct / Alex wrong | Page 2 names Hudson's Bay Company. Alex has all-caps plus typo. If enforcing exact filing punctuation, AI should use the filing's curly apostrophe, but this is not a substantive disagreement. |
| `DateEffective`: AI null, Alex `2013-11-04` | AI correct / Alex wrong | The proxy predates closing. Page 10 only anticipates completion in November 2013. Under schema, DateEffective stays null unless this filing explicitly states the effective/closing date. |

### Bidder-Type Field Disagreements

| Rows | Verdict | Rationale |
|---|---|---|
| Sponsor A, Sponsor E, Sponsor G public field: AI `false`, Alex `null` | AI correct / Alex reference stale | The filing calls these "private equity firm" bidders. Under §F2, PE sponsors have `public: false`. |
| Hudson's Bay public field: AI `false`, Alex `true` | AI correct under current filing-only rule | The filing states Hudson's Bay is Canadian and gives operating-company facts, supporting `base=s` and `non_us=true`. It does not state that Hudson's Bay is publicly traded. §F2 says `public: true` iff the filing states publicly traded status. |
| Company I base: AI defaults `f` with ambiguity flag, Alex `s` | AI more consistent with rulebook | The filing only says Company I executed an NDA and conducted diligence during the go-shop. It does not identify industry, public status, or strategic nature. §F2 defaults ambiguous cases to `f` with a soft flag. |

### Process Start, Interest, and IB Rows

| Rows | Verdict | Rationale |
|---|---|---|
| Raw row 1 Goldman Sachs `IB` 2012-12-15 vs Alex row 1 | Both defensible on date form; AI has better role typing | Filing page 30 says Goldman participated in reviews and one review occurred in December 2012. AI infers the first narrative date; Alex rough date has same substance. |
| Raw row 23 Morgan Stanley `IB` 2013-07-26, Alex missing | Both defensible | Page 35 calls Morgan Stanley a "long-time advisor" and includes it in July 26 and July 28 board meetings. That supports advisor participation. But the filing does not narrate a discrete retention/engagement, so omitting it is also defensible if `IB` is limited to the principal banker or formal retention. |
| Raw row 2 Sponsor A `Bidder Interest` 2013-02-15 vs Alex row 2 | AI correct | Page 30 states Sponsor A expressed interest and no terms were discussed. |
| Raw row 3 Hudson's Bay `Bidder Interest` 2013-04-01, Alex missing | AI correct / Alex wrong | Page 30 says Hudson's Bay discussed a potential acquisition and no specific proposal or terms. This is a textbook `Bidder Interest` row before the April 15 price indication. |
| Raw row 13 Company F `Bidder Interest` 2013-06-12, Alex missing | AI correct / Alex wrong | Page 32 says Company F indicated interest in participating and conducted diligence. It is bidder-relevant even though no direct meetings occurred. |

### Target Sale and Final-Round Rows

| Rows | Verdict | Rationale |
|---|---|---|
| Raw row 4 `Target Sale` 2013-04-04, Alex missing | AI correct / Alex wrong | Page 30 says the board reviewed acquisition interest and directed management to continue exploring potential transactions. This meets the current `Target Sale` / explore-sale rule. |
| Raw row 12 `Target Sale` 2013-06-05, Alex missing | AI correct / Alex wrong | Page 32 says the board authorized implementation of a process with potential acquirors that had signed confidentiality agreements. Strong `Target Sale` evidence. |
| Raw row 14 `Final Round Ann` 2013-07-02 vs Alex row 11 | AI correct | Page 32 says Goldman distributed a draft merger agreement and process details, requesting offers by July 11. |
| Alex row 15 `Final Round` 2013-07-02, AI missing | AI correct / Alex wrong | July 2 is the announcement/invitation date, not the submission date. The actual submissions were July 11 and are captured as bid rows. |

### Bid Rows

| Rows | Verdict | Rationale |
|---|---|---|
| Raw row 6 Hudson's Bay informal bid 2013-04-17 vs Alex row 3 rough 2013-04-15 | AI correct on date mapping; both correct on substance | Page 31 says "During the week of April 15" and at least $15 per share. §B4 midpoint mapping supports 2013-04-17. |
| Raw row 5 Sponsor A/E informal bid 2013-04-17 vs Alex row 4 Sponsor A bid | AI wrong on bidder attribution; Alex correct on bidder | Page 31 says Sponsor E participated in the meeting, but only "Sponsor A indicated" it was considering an offer at at least $15. This should be Sponsor A only, with Sponsor E mentioned in `additional_note`, not `joint_bidder_members`. |
| Raw row 10 Hudson's Bay informal range 2013-06-05 vs Alex row 9 rough 2013-06-03 | AI correct on date mapping; both correct on substance | Page 32 says "During the week of June 3" and gives $15-$15.25. §B4 midpoint is 2013-06-05. |
| Raw row 11 Sponsor A/E informal range 2013-06-05 vs Alex row 10 rough 2013-06-03 | AI correct on date mapping and filing label | Page 32 expressly says Sponsor A and Sponsor E were preliminarily prepared to submit at $15-$16. |
| Raw row 16 Hudson's Bay formal bid 2013-07-11 vs Alex row 18 | AI correct | Page 33 states price $15.25, revised merger agreement, and committed debt/equity financing documents. Formal classification is correct. |
| Raw row 17 Sponsor E/G informal bid 2013-07-11 vs Alex row 17 Sponsor A/E | AI correct / Alex wrong on bidder identity | Page 33 says "Sponsor E, together with Sponsor G" submitted the July 11 indicative $14.50-$15.50 proposal. Sponsor A rejoined later after Sponsor G exited; it did not submit this July 11 proposal. |
| Raw row 22 Hudson's Bay formal revised bid 2013-07-24 vs Alex row 19 | AI correct | Page 34 says Hudson's Bay was prepared to offer $16, subject to a definitive agreement, and substantially agreed on merger/financing issues. |

### Drop / Exclusion Rows

| Rows | Verdict | Rationale |
|---|---|---|
| Alex row 7 Sponsor A `Drop` 2013-04-26, AI missing | AI correct / Alex wrong | April 26 is Sponsor A's NDA date. Page 31 shows Sponsor A continued into diligence; no dropout occurred. |
| Alex row 12 Sponsor A/E `Drop` rough 2013-07-07, AI missing | Mostly AI correct; Alex row not valid as written | Page 33 says Sponsor A was no longer intending to be a primary participant and Sponsor E had entered discussions with Sponsor G. Sponsor E did not drop, and Sponsor A later rejoined. This is a role-change/temporary de-emphasis, not a clean Sponsor A/E dropout under the current vocabulary. |
| Raw row 18 Company F `DropAtInf` 2013-07-11, Alex missing | AI correct to capture exit; event code/date are inferential | Page 32 says Company F did not participate in the ultimately submitted offer. A dropout row is useful, but because agency and exact date are inferred, generic `Drop` with a soft context-date flag may be safer than `DropAtInf`. |
| Raw row 19 Sponsor G `DropAtInf` undated vs Alex row 13 `Drop` undated | AI wrong on event code; Alex closer | Page 33 only says Sponsor G was "no longer participating"; it does not say Sponsor G withdrew voluntarily. Under §I1 ambiguity rule, use generic `Drop` with `drop_agency_ambiguous` and `date_unknown`. |
| Alex row 14 Company H `Drop`, AI skipped with info flag | AI correct / Alex wrong | Page 34 describes an unsolicited, detail-free aggregate-price letter, unsuccessful follow-up, and no later contact. This matches the Saks §M1 skip/migration note. |
| Raw rows 20-21 Sponsor A and Sponsor E `DropBelowM` 2013-07-23 vs Alex row 21 `Spnosor A/E` `DropTarget` 2013-07-28 | AI correct / Alex wrong | Page 34 says Sponsor A/E gave no indication they would increase beyond $14.50-$15.50 after the board pushed Hudson's Bay to at least $16. Because Sponsor A and Sponsor E had separate NDAs, split constituent dropout rows are consistent with §I1 consortium-drop handling. July 28 execution is not the first dropout evidence. |
| Raw row 26 Company I `DropAtInf` 2013-09-06 vs Alex row 23 `Drop` 2013-09-06 | Alex closer on event code; AI correct on event/date | Page 35 says no go-shop party, including Company I, submitted an acquisition proposal by the September 6 go-shop end. Because agency is not explicit, generic `Drop` is safer unless the rulebook treats "no proposal submitted by deadline" as `DropAtInf`. |

### NDA Rows

| Rows | Verdict | Rationale |
|---|---|---|
| Raw rows 7-8 Sponsor A and Sponsor E NDAs 2013-04-26 vs Alex rows 5-6 | AI correct; Alex public-field null should be updated | Page 31 says Saks entered into a confidentiality agreement with each of Sponsor A and Sponsor E. |
| Raw row 9 Hudson's Bay NDA 2013-04-30 vs Alex row 8 | AI correct on event; Alex wrong on public field | Page 31 states the Hudson's Bay NDA. |
| Raw row 15 Sponsor G NDA 2013-07-08 vs Alex row 16 | AI correct; Alex public-field null should be updated | Page 33 states the Sponsor G NDA. |
| Raw row 25 Company I NDA 2013-08-11 vs Alex row 20 rough 2013-07-29 | AI correct / Alex wrong | Page 36 says Company I had not signed until approximately two weeks after the July 28 merger agreement. Approximate two weeks after July 28 maps to 2013-08-11. |

### Executed Row

| Rows | Verdict | Rationale |
|---|---|---|
| Raw row 24 Hudson's Bay `Executed` 2013-07-28 vs Alex row 22 rough 2013-07-28 | AI correct | Page 35 states the board approved the merger agreement and that Saks, Hudson's Bay, and Merger Sub finalized and executed transaction documents later on July 28. Page 35 also states the July 29 press release, correctly folded into the Executed row rather than emitted separately. |

## Extraction-Side Fixes Needed

1. Raw row 5: change bidder alias from `Sponsor A and Sponsor E` to `Sponsor A`; remove `joint_bidder_members`; keep `bid_value_lower=15`, `bid_type=informal`, `bid_date_precise=2013-04-17`, page 31 evidence. Add note that Sponsor E participated in the meeting but did not make the price indication.
2. Raw row 19: change `bid_note` from `DropAtInf` to `Drop`; keep no date; retain `date_unknown` and `drop_agency_ambiguous`.
3. Raw row 26: consider changing `DropAtInf` to generic `Drop`, unless Austin decides go-shop "no proposal submitted by deadline" should be coded as `DropAtInf`.
4. Raw row 18: consider changing Company F `DropAtInf` to generic `Drop` because the filing says Company F "did not participate" but does not give agency. Keep the Company F `Bidder Interest` row.
5. Reorder same-date rows or run canonical sorting before validation:
   - 2013-06-05: `Target Sale` before informal bids.
   - 2013-07-11: Sponsor E/G informal bid before Hudson's Bay formal bid under §A3.
6. Decide whether raw row 23 Morgan Stanley `IB` belongs. If kept, add a note that there is no discrete engagement date and first process mention is July 26. If omitted, no substantive auction chronology is lost.
7. Minor identity polish: if "filing-verbatim punctuation" is enforced strictly, use `Hudson's Bay Company` only if straight-apostrophe normalization is accepted; the filing text uses a curly apostrophe in most places.

## Reference-Side Corrections Needed

1. Set `TargetName` to `Saks Incorporated`.
2. Set `Acquirer` to `Hudson's Bay Company` or the exact filing-punctuation equivalent.
3. Set `DateEffective` to null for this DEFM14A.
4. Remove Alex row 7 Sponsor A `Drop` on 2013-04-26; it is actually the NDA date and Sponsor A continued.
5. Remove or replace Alex row 12 Sponsor A/E `Drop`; the filing narrates Sponsor A stepping back from primary participation, not a Sponsor A/E withdrawal.
6. Remove Alex row 14 Company H `Drop`; the rulebook's Saks §M1 migration note says this unsolicited no-follow-up letter should be skipped, with an info flag only.
7. Remove Alex row 15 `Final Round` on July 2; retain only `Final Round Ann` for the July 2 process-letter event.
8. Change Alex row 17 bidder identity from Sponsor A/E to Sponsor E/G for the July 11 $14.50-$15.50 proposal.
9. Replace Alex row 21 `Spnosor A/E` `DropTarget` dated July 28 with split Sponsor A and Sponsor E `DropBelowM` rows dated July 23, or otherwise remove it in favor of the AI's page 34 evidence.
10. Change Company I NDA date from rough 2013-07-29 to approximate 2013-08-11.
11. Revisit Company I bidder type. The filing does not support strategic classification; current rulebook says default ambiguous bidders to financial with a soft flag.
12. Normalize `public` fields per §F2: PE sponsors should be `public=false`; Hudson's Bay should not be `public=true` unless the filing itself states public trading status.

## Rule / Prompt Recommendations

1. Add a prompt reminder for **meeting participant vs bidder attribution**: if a party "participated in the meeting" but the filing says only another party "indicated" a price, do not make the bid joint. This directly addresses raw row 5.
2. Tighten dropout coding in the prompt: `DropAtInf` requires a voluntary-withdrawal signal. Passive language like "was no longer participating" or "did not participate" should default to `Drop` with `drop_agency_ambiguous`.
3. Clarify go-shop no-proposal handling. Current Saks row 26 exposes a recurring ambiguity: should a go-shop NDA signer that submits no proposal by go-shop end be `Drop`, `DropAtInf`, or no dropout row plus a validator soft flag? I recommend generic `Drop` unless the filing states the party declined/withdrew.
4. Clarify whether "long-time advisor attended board meetings" is sufficient for an `IB` row. Morgan Stanley is a clean test case: named as advisor, but no formal retention event.
5. Ensure the orchestration validates after canonical same-date sorting, or make raw-extractor validation warnings clearly non-final. The two hard flags here are ordering artifacts, not substantive extraction misses.

## Confidence

Overall confidence: **high** for the main auction chronology, deal-level fields, Company H skip, July 11 bidder identities, July 23 Sponsor A/E below-minimum treatment, and DateEffective=null.

Medium confidence: Morgan Stanley `IB` inclusion, Company F dropout coding/date, and Company I `Drop` vs `DropAtInf`. These are not primarily filing-reading disputes; they are schema-policy boundary cases.

Low residual risk: Hudson's Bay `public=false` may look odd if compared to external market facts, but under the current filing-only §F2 rule it is correct because the proxy does not state public trading status for Hudson's Bay.

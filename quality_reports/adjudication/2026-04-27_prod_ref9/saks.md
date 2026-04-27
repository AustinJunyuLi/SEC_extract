# Saks adjudication - 2026-04-27 production reference run

Fresh diff: `scoring/results/saks_20260427T200927Z.md`

## Summary

The SEC filing is closer to the AI extraction than to Alex's converted reference on most disputed rows. Main patterns:

- AI correctly adds filing-supported process detail that Alex omitted or aggregated: Hudson's Bay first interest, Sponsor E atomization, Company F interest, go-shop interested-party placeholders, Morgan Stanley IB, Target Sale, execution date/value, and more specific drop coding for Sponsor G / Company I.
- Alex is right on the deal-level acquirer string: the filing identifies the operating acquirer as "Hudson's Bay Company" and then defines the shorthand "Hudson's Bay."
- Two buckets need correction beyond either side: Sponsor A's early-July temporary step-back/re-entry is not cleanly represented by either output, and the `Final Round` row should be tied to the July 11 offer-submission deadline rather than Alex's July 2 duplicate announcement date.

Headline verdict counts, using tightly-related buckets rather than raw diff lines:

| Verdict | Count |
|---|---:|
| ai-right | 17 |
| alex-right | 1 |
| both-defensible | 2 |
| both-wrong | 2 |
| needs-Austin | 0 |

Action counts:

| Action implication | Count |
|---|---:|
| no rule change / update reference or diff normalization only | 17 |
| update extraction prompt/rulebook | 3 |
| Austin decision needed | 0 |

## Deal-level disagreements

| Field | Verdict | Filing evidence | Action implication |
|---|---|---|---|
| `TargetName`: AI `Saks Incorporated`; Alex `SAKS INC` | ai-right | Cover page names registrant as "Saks Incorporated"; shareholder letter says Saks Incorporated is the Tennessee corporation. Source pages 1-2. | Update reference to filing-verbatim target name; no rule change. |
| `Acquirer`: AI `Hudson's Bay`; Alex `Hudson's Bay Company` | alex-right | The merger agreement is "by and among Hudson's Bay Company ... Harry Acquisition Inc. ... and the Company"; filing then defines shorthand "Hudson's Bay." Source pages 2 and 4. | Update extraction prompt/checking so deal-level `Acquirer` uses the full operating acquirer name, not only the shorthand alias. |
| `DateEffective`: AI `null`; Alex `2013-11-04` | ai-right | The proxy is dated October 3, 2013, calls for an October 30 shareholder vote, and states the merger "will be" completed only if conditions are satisfied. Source pages 2, 4. | Update reference; no rule change. The filing predates closing, so `DateEffective = null` under `rules/schema.md`. |

## Matched/cardinality divergences

### `IB` residual bucket

**Verdict: ai-right.**

Filing evidence:

- Goldman Sachs had participated in Saks strategic reviews for several years, including the December 2012 review that opens the background chronology. Source page 30.
- Morgan Stanley is described as "a long-time advisor to Saks" and attended the July 26 and July 28 board meetings on the Hudson's Bay proposal. Source page 35.

AI's two IB rows are supported. Alex records only Goldman Sachs. Action: update reference to include Morgan Stanley; no rule change.

### `Bidder Interest` residual bucket

**Verdict: ai-right.**

Filing evidence:

- Sponsor A expressed interest in February 2013, with no specific proposal or terms. Source page 30.
- Richard Baker of Hudson's Bay met Sadove on April 1, 2013 to discuss a potential acquisition, again with no specific proposal or terms. Source page 30.
- Company F "indicated interest in participating with Sponsor A and Sponsor E" and conducted due diligence but did not join the ultimate offer. Source page 32.
- During the go-shop process, Goldman contacted 58 third parties; exactly six expressed interest, only Company I signed an NDA, and no go-shop party submitted a proposal. Source page 35.

AI correctly atomizes the exact count of six go-shop interested parties into Company I plus five placeholders. Alex's single `Bidder Interest` row undercounts the filing. Action: update reference; no rule change.

### `Bid` residual bucket

**Verdict: ai-right, with one extraction follow-up noted below.**

Filing evidence:

- During the week of April 15, Hudson's Bay and Sponsor A each indicated they were considering an offer for at least $15/share; Sponsor E participated in the Sponsor A meeting as a potential joint participant. Source page 31.
- During the week of June 3, Hudson's Bay indicated $15.00-$15.25/share and Sponsor A/Sponsor E indicated $15.00-$16.00/share. Source page 32.
- On July 11, Hudson's Bay submitted $15.25/share with a revised merger agreement and financing documentation; Sponsor E together with Sponsor G submitted an indicative $14.50-$15.50/share range that needed more diligence and lacked financing support. Source page 33.
- On July 21, Company H sent an unsolicited aggregate $2.6 billion cash proposal with no details; Goldman could not make further contact and there were no subsequent communications. Source page 34.
- On July 24, Hudson's Bay was prepared to offer $16/share subject to a definitive agreement. Source page 34.

AI is right to split Sponsor A and Sponsor E where the filing identifies both as participants, to split Sponsor E and Sponsor G on the July 11 joint proposal, to treat range bids as informal, and to capture Company H's aggregate cash proposal as a bid rather than a generic drop. Alex's reference aggregates Sponsor A/E and assigns the July 11 range to the wrong joint-party label.

Extraction follow-up: the April 15 Sponsor E bid attribution is filing-supported but inferential because the price indication is grammatically from Sponsor A while Sponsor E "participated" in that meeting. AI already carries a `joint_bid_attribution_ambiguous` soft flag. No rule change needed unless this ambiguity recurs without flags.

Action: update reference for atomization and party labels; no rule change.

### `Company I` `NDA` date mismatch

**Verdict: ai-right.**

Filing evidence: Saks told Company I that Company I had not signed a confidentiality agreement until approximately two weeks after the July 28 merger agreement execution. Source page 36.

AI maps that relative phrase to August 11, 2013 and preserves the rough phrase. Alex's July 29 rough date is not supported. Action: update reference; no rule change.

## AI-only rows

### Hudson's Bay `NDA` - April 30, 2013

**Verdict: both-defensible.**

Filing evidence: Saks and Hudson's Bay entered into a confidentiality agreement on April 30, 2013. Source page 31.

This is not a substantive miss: Alex has the same NDA as an Alex-only row using ASCII apostrophe/name normalization, while AI uses the filing's shorthand with curly apostrophe. Action: improve diff alias normalization if useful; no extraction or reference rule change.

### `Target Sale` - June 5, 2013

**Verdict: ai-right.**

Filing evidence: on June 5, the board authorized "the implementation of a process" to determine whether a transaction with potential acquirors that had executed confidentiality agreements could be reached. Source page 32.

This is a board-level authorization to run a sale process and fits `Target Sale`. Alex omitted it. Action: update reference; no rule change.

### Sponsor A and Sponsor E `DropBelowM` - July 23, 2013

**Verdict: ai-right.**

Filing evidence: the board would not agree to an acquisition below $16/share; Sponsor A and Sponsor E did not indicate readiness to improve beyond the $14.50-$15.50 range or finish diligence faster. Source page 34.

AI's split rows are better than Alex's later misspelled/aggregated `Spnosor A/E` `DropTarget` row. The exact agency is inferential, but the below-minimum reason is grounded in the filing. Action: update reference; no rule change.

### Hudson's Bay `Executed` - July 28, 2013

**Verdict: ai-right.**

Filing evidence: after board approval, Saks, Hudson's Bay and Merger Sub finalized and executed the merger agreement later on July 28; the July 29 joint press release announced entry into the transaction. Source page 35.

AI correctly dates execution on July 28, folds the next-day press release into the execution row, and records the $16/share consideration. Alex's rough-date execution row lacks the same fidelity. Action: update reference; no rule change.

### Company I `DropAtInf` - September 6, 2013

**Verdict: ai-right.**

Filing evidence: the go-shop period ended September 6, no excluded party was designated, and no contacted party, including Company I, submitted an acquisition proposal. Source page 35.

AI's `DropAtInf` is more specific than Alex's generic `Drop`; Company I reached diligence but did not submit a proposal. Action: update reference; no rule change.

### Sponsor G `DropAtInf` - undated

**Verdict: ai-right.**

Filing evidence: after the July 11 Sponsor E/Sponsor G proposal, Saks was informed that Sponsor G was no longer participating, and Sponsor E would again be joined by Sponsor A. Source page 33.

AI correctly records the drop with unknown date because the filing gives no calendar date for the "subsequently informed" event. Alex has a generic undated `Drop`; AI's stage-specific code is better. Action: update reference; no rule change.

## Alex-only rows

### Sponsor A `Drop` - April 26, 2013

**Verdict: ai-right.**

Filing evidence: April 26 is the date Saks entered into confidentiality agreements with Sponsor A and Sponsor E. Source page 31. The filing does not describe a Sponsor A drop on that date.

Action: remove from reference; no rule change.

### Hudson's Bay `NDA` - April 30, 2013

**Verdict: both-defensible.**

Filing evidence: same April 30 NDA passage as above. Source page 31.

This is the same event as AI's Hudson's Bay NDA, split only by alias/typography. Action: no substantive change; optionally improve diff normalization.

### Sponsor A/E `Drop` - early July 2013

**Verdict: both-wrong.**

Filing evidence: in early July, Sponsor E informed Saks that Sponsor A was no longer intending to be a primary participant and that Sponsor E had entered discussions with Sponsor G; after the July 11 Sponsor E/G proposal, Sponsor G left and Sponsor E was again joined by Sponsor A. Source page 33.

Correct filing-based treatment should capture Sponsor A's temporary step-back from primary-participant status and later re-entry, not an aggregated Sponsor A/E drop. AI misses the temporary Sponsor A drop/re-entry; Alex wrongly attributes the event to Sponsor A/E as a combined bidder. Action: update extraction prompt/rulebook examples for temporary consortium membership changes and re-engagement flags; update reference after the rule application is decided.

### Sponsor G `Drop` - undated

**Verdict: ai-right.**

Filing evidence: Sponsor G was "no longer participating" after the July 11 joint Sponsor E/G proposal. Source page 33.

AI captures the same event as `DropAtInf` with unknown date; Alex's generic `Drop` is less precise. Action: update reference; no rule change.

### Company H `Drop` - undated

**Verdict: ai-right.**

Filing evidence: Company H sent an unsolicited aggregate $2.6 billion cash proposal on July 21; Goldman tried and failed to contact the appropriate person; neither Saks nor Goldman received later communications. Source page 34.

The filing supports a single unsolicited bid row with no separate drop row. Alex's generic undated drop is not the right event shape. Action: update reference; no rule change, though the existing Saks/Company H migration note should be reconciled with the filing's aggregate-price language when the reference is regenerated.

### `Final Round` - July 2, 2013

**Verdict: both-wrong.**

Filing evidence: on July 2, Goldman distributed draft merger agreement and process details and requested all-cash offers by July 11; the offers were then submitted on July 11. Source pages 32-33.

AI correctly has `Final Round Ann` on July 2 but omits the corresponding `Final Round` submission event. Alex includes a `Final Round` row but dates it July 2, duplicating the announcement date rather than the July 11 submission/deadline. Action: update extraction prompt/rulebook examples to ensure `Final Round` is emitted on the offer-submission date when `Final Round Ann` requests offers by a deadline; update reference.

### `Spnosor A/E` `DropTarget` - July 28, 2013

**Verdict: ai-right.**

Filing evidence: July 28 is the board approval/execution date for the Hudson's Bay merger agreement. Source page 35. The filing does not narrate a separate July 28 target rejection of Sponsor A/E.

The better-supported disposition of Sponsor A and Sponsor E is the July 23 below-minimum bucket discussed above, plus the separate early-July Sponsor A temporary step-back issue. Action: remove this reference row; no rule change.

### Hudson's Bay Company `Executed` - July 28 rough date

**Verdict: ai-right.**

Filing evidence: the merger agreement was executed later on July 28, 2013, and announced July 29. Source page 35.

AI's execution row is precise and includes consideration; Alex's row is the same event in less complete form. Action: update reference; no rule change.

### Company I `Drop` - September 6, 2013

**Verdict: ai-right.**

Filing evidence: no go-shop party, including Company I, submitted an acquisition proposal by the end of the September 6 go-shop period. Source page 35.

AI's `DropAtInf` better captures the stage and non-submission than Alex's generic `Drop`. Action: update reference; no rule change.

## Rulebook/reference implications

- Update reference: `TargetName`, `DateEffective`, Morgan Stanley IB, Hudson's Bay bidder-interest row, Company F interest, go-shop interested-party atomization, Target Sale, bid atomization/party labels, Company I NDA date, execution row, and specific drop codes for Sponsor G / Company I should be brought in line with the filing.
- Update extraction prompt/rulebook examples: ensure deal-level `Acquirer` uses the full operating acquirer name, not merely a filing-defined shorthand.
- Update extraction prompt/rulebook examples: clarify temporary consortium membership changes. Saks needs Sponsor A's early-July step-back and later re-entry handled explicitly; Alex's combined Sponsor A/E row is wrong, but AI's omission loses a real filing event.
- Update extraction prompt/rulebook examples: when a final-round announcement sets a submission deadline and bids arrive on that deadline, emit `Final Round Ann` on the invitation date and `Final Round` on the submission/deadline date.
- Reconcile reference-build notes for Saks/Company H with the filing and current aggregate-bid rule. The filing contains an aggregate $2.6 billion cash proposal, so treating Company H as "no price" is not filing-accurate.
- No Austin decision needed from this pass.

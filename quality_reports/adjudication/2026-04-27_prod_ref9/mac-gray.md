# Mac Gray production adjudication

Fresh diff: `scoring/results/mac-gray_20260427T200927Z.md`

## Summary

Adjudicated all fresh AI-vs-Alex divergences against the Mac-Gray DEFM14A filing. The SEC filing supports the AI side on every substantive divergence in this diff. Most disagreements are reference-side legacy coding artifacts: range bids were copied into `bid_value_pershare`, dates were omitted, grouped NDA/drop/execute rows were not atomized, and the execution date was coded as the September 21 price agreement rather than the October 14 merger-agreement execution.

Headline adjudication counts, by tightly related bucket:

| Verdict | Buckets | Notes |
|---|---:|---|
| `ai-right` | 14 | Filing supports AI value structure, dates, atomization, selected dropout coding, and execution row. |
| `alex-right` | 0 | None. |
| `both-defensible` | 0 | None in this diff. |
| `both-wrong` | 0 | None requiring output/rule correction from this diff. |
| `needs-Austin` | 0 | No Austin-only judgment needed. |

Raw diff items covered: 2 deal-level disagreements, 7 matched bid-value disagreements, 3 cardinality mismatches, 5 date mismatches, 3 AI-only rows, and 7 Alex-only rows.

## Deal-level disagreements

### TargetName: AI `Mac-Gray Corporation` vs Alex `MAC GRAY CORP`

**Verdict: `ai-right`.**

**Filing evidence.** The cover letter uses the legal/display name "Mac-Gray Corporation" in running text, and the notice describes "Mac-Gray Corporation, a Delaware corporation" (pages 2 and 4). Alex's value drops the hyphen and abbreviates "Corporation" to "CORP"; that is not filing-verbatim.

**Action implication.** Update reference if this field is regenerated/reconciled. No rule change.

### DateEffective: AI `null` vs Alex `2014-01-09`

**Verdict: `ai-right`.**

**Filing evidence.** The proxy is dated December 4, 2013, calls the January 8, 2014 stockholder meeting a future meeting, and repeatedly phrases closing conditionally: "If the merger is completed..." (pages 2, 4, and 11). The filing states the merger agreement was entered into on October 14, 2013, but does not state that the merger had become effective or would become effective on January 9, 2014.

**Action implication.** Keep `DateEffective = null` for this filing. Update reference if reconciled. No rule change.

## Matched/cardinality divergences

### Range bid value structure: seven matched `Bid` rows

Rows covered:

| Party | Date | Filing value | AI | Alex |
|---|---:|---|---|---|
| Party A | 2013-06-21 | `$17.00 to $19.00` | `bid_value_pershare=null`, lower 17, upper 19 | `bid_value_pershare=17` |
| Party B | 2013-07-24 | `$17.00 to $18.00` | `bid_value_pershare=null`, lower 17, upper 18 | `bid_value_pershare=17` |
| Party C | 2013-07-24 | `$15.00 to $17.00` | `bid_value_pershare=null`, lower 15, upper 17 | `bid_value_pershare=15` |
| Party C | 2013-07-25 | `$16.00 to $16.50` | `bid_value_pershare=null`, lower 16, upper 16.5 | `bid_value_pershare=16` |
| Party A | 2013-09-10 | `$18.00 to $19.00` | `bid_value_pershare=null`, lower 18, upper 19 | `bid_value_pershare=18` |
| Party C | 2013-09-10 | `$16.00 to $17.00` | `bid_value_pershare=null`, lower 16, upper 17 | `bid_value_pershare=16` |
| Party A | 2013-09-18 | reaffirmed `$18.00 to $19.00` | `bid_value_pershare=null`, lower 18, upper 19 | `bid_value_pershare=18` |

**Verdict: `ai-right`.**

**Filing evidence.** The filing states the exact ranges on pages 36, 39, 40, 41, and 42. These are range bids, not point-value bids. The September 18 Party A row is a same-price reaffirmation of the $18.00-$19.00 range in response to the September 11 final-indications request (page 42).

**Action implication.** Update reference. No prompt/rulebook change; the current rulebook range structure is correct.

### NDA residual bucket: AI 17 residual rows vs Alex 2 residual rows

**Verdict: `ai-right`.**

**Filing evidence.** Page 38 states that over the next two months "a total of 20 potential bidders, including two strategic bidders (Party A and CSC/Pamplona) and 18 financial bidders (including Party B and Party C), entered into confidentiality agreements." Separately dated rows exist for Party B on June 28, Party C on June 30, CSC/Pamplona on July 11, and Party A on August 5 (pages 38-40). Therefore the residual unnamed count is 16 financial bidders, not one aggregated "16 financial bidders" row. Alex's Party C June 20 NDA date is not supported; the filing says June 30.

**Action implication.** Update reference to atomize the 16 unnamed financial NDA signers and correct Party C's NDA date. No rule change.

### DropTarget / target-rejection residual bucket

**Verdict: `ai-right`.**

**Filing evidence.** On September 19, 2013, the Special Committee evaluated the remaining proposals. For Party B, the committee discussed the contingent/deferred option value and financing risk even though Party B's headline value was facially higher (page 43). For Party A, the same meeting selected CSC/Pamplona over the other indications and authorized the Transaction Committee to seek exclusivity at $21.25, above Party A's $18.00-$19.00 best-and-final range (pages 42-43). The filing's operative target-side decision occurs on September 19, not September 24. September 24 is the later execution of exclusivity with CSC/Pamplona (page 44).

**Action implication.** Keep AI's Party B `DropTarget` on 2013-09-19 and AI's Party A `DropBelowM` on 2013-09-19. Update reference. No rule change.

### Executed residual bucket

**Verdict: `ai-right`.**

**Filing evidence.** Page 47 states: "Later in the day, on October 14, 2013, the merger agreement was executed, the Pamplona commitment letter was delivered..." Page 2 also says the company entered into the merger agreement on October 14, 2013. September 21 was a price/exclusivity negotiation milestone: CSC/Pamplona confirmed willingness to increase to $21.25, subject to exclusivity (page 43). It was not execution. Pamplona's role was funding sponsor via commitment letter, not a separate operating acquirer execution row.

**Action implication.** Keep one `Executed` row dated 2013-10-14 for the operating acquirer CSC, with Pamplona in the note. Update reference. No rule change.

### Missing dates on matched process rows

Rows covered:

| Event | AI date | Alex date | Filing evidence |
|---|---:|---:|---|
| BofA Merrill Lynch `IB` | 2012-10-23 | null | Mac-Gray engaged BofA Merrill Lynch on October 23, 2012 (page 33). |
| Party A `Target Interest` | 2013-04-08 | null | BofA Merrill Lynch called Party A on April 8, 2013 (page 33). |
| BofA Merrill Lynch `IB Terminated` | 2013-05-15 | null | Mac-Gray sent termination letter on May 15, 2013 (page 35). |
| BofA Merrill Lynch `IB` | 2013-05-31 | null | Mac-Gray entered the new engagement letter on May 31, 2013 (page 36). |
| `Final Round Inf Ann` | 2013-08-27 | null | BofA Merrill Lynch sent letters on August 27, 2013 requesting revised written proposals by September 9 (page 41). |

**Verdict: `ai-right`.**

**Action implication.** Update reference dates. No rule change.

## AI-only rows

### `Target Sale` on 2013-06-24

**Verdict: `ai-right`.**

**Filing evidence.** At the June 24 meeting, the Special Committee concluded that it was in stockholders' best interests "to consider a potential sale of Mac-Gray" and compare that alternative against stand-alone execution (pages 36-37). That is a target-side sale-process decision, separate from Party A's June 21 unsolicited proposal.

**Action implication.** Keep AI row. Update reference to include it if reference is regenerated. No rule change.

### Party C `DropAtInf` on 2013-09-18

**Verdict: `ai-right`.**

**Filing evidence.** Party C did not submit a revised indication or reiterate its prior $16.00-$17.00 indication by the September 18 final-indications deadline and gave no reason (page 42). That is a voluntary/non-response dropout at the informal stage, more specific than Alex's generic `Drop`.

**Action implication.** Keep AI row and replace Alex's generic Party C `Drop` with `DropAtInf` if reference is updated. No rule change.

### Party A `DropBelowM` on 2013-09-19

**Verdict: `ai-right`.**

**Filing evidence.** Party A's September 18 best-and-final remained $18.00-$19.00 (page 42). On September 19, the Special Committee chose CSC/Pamplona over the other indications and authorized moving toward exclusivity only if CSC/Pamplona increased above $20.75 to $21.25 (page 43). Party A was rejected because its price was below the target-side acceptable path.

**Action implication.** Keep AI row. Update reference, which currently has a later generic `DropTarget`. No rule change.

## Alex-only rows

### Party A `Bidder Sale` on 2013-06-21

**Verdict: `ai-right`.**

**Filing evidence.** Party A submitted a concrete all-cash $17.00-$19.00 proposal on June 21, 2013 (page 36), and later signed an NDA on August 5 (page 40). The AI captures the concrete proposal as a pre-NDA informal `Bid` with the range preserved. A separate `Bidder Sale` row would double-count the same price communication.

**Action implication.** Do not add Alex row to AI. Update reference/remove row under the current unified-bid/pre-NDA-bid convention. No rule change.

### Alex-only `Final Round Inf`, `Final Round Inf Ext Ann`, and `Final Round Inf Ext`

Rows covered: Alex `Final Round Inf` with null date, Alex `Final Round Inf Ext Ann` with null date, Alex `Final Round Inf Ext` with null date.

**Verdict: `ai-right`.**

**Filing evidence.** The filing has a preliminary-indication process by July 23/24/25 (pages 38-40), a later August 27 request for revised proposals by September 9 (page 41), and a September 11 request for final indications by September 18 (page 42). It does not narrate a distinct extension announcement or extension completion event corresponding to Alex's null-dated extension rows. The supported final-request row is the September 11 `Final Round Ann`; the supported August 27 row already appears as a dated matched row in the diff.

**Action implication.** Do not add these Alex-only legacy rows. Update reference if regenerated. No rule change.

### `16 financial bidders` `Drop` on 2013-07-25

**Verdict: `ai-right`.**

**Filing evidence.** Page 38 gives the exact count: 18 financial bidders signed NDAs, including Party B and Party C. After Party B and Party C bid, the remaining 16 financial NDA signers have no later bidder-specific narrative in the filing. The correct current treatment is atomized unnamed NDA rows plus `DropSilent` rows, not a single aggregated dated `Drop` row. The July 25 meeting selected the four interested bidders for continued management-meeting access (pages 39-40), but the filing does not individually narrate a July 25 withdrawal by the 16 unnamed financial bidders.

**Action implication.** Do not add Alex aggregate drop row. Reference should be atomized and aligned with `DropSilent` convention. No rule change.

### `Final Round` on 2013-09-11

**Verdict: `ai-right`.**

**Filing evidence.** September 11 is the date BofA Merrill Lynch was instructed to request final indications by September 18, and representatives called the four bidders with those instructions (page 42). That is an announcement/request row (`Final Round Ann`), which AI has. It is not the final-round bid-submission/completion row itself.

**Action implication.** Do not add Alex's duplicate/miscoded `Final Round` row. Update reference. No rule change.

### Party C generic `Drop` on 2013-09-18

**Verdict: `ai-right`.**

**Filing evidence.** Party C did not submit or reiterate a revised indication by the September 18 deadline and gave no reason (page 42). The AI's `DropAtInf` captures the agency/stage more precisely than Alex's generic `Drop`.

**Action implication.** Replace Alex generic `Drop` with AI's `DropAtInf` if reference is updated. No rule change.

### CSC ServiceWorks and Pamplona `Executed` rows on 2013-09-21

**Verdict: `ai-right`.**

**Filing evidence.** September 21 is the last-and-best $21.25 price confirmation subject to two weeks of exclusivity (page 43). The merger agreement was executed on October 14; the Pamplona commitment letter was delivered the same day (page 47). Pamplona is a funding sponsor/commitment source, not a separate September 21 merger execution event.

**Action implication.** Do not add the Alex rows. Update reference to one October 14 operating-acquirer execution row with Pamplona noted as funding sponsor. No rule change.

### Party A and Party B `DropTarget` rows on 2013-09-24

**Verdict: `ai-right`.**

**Filing evidence.** The target-side rejection decision is supported by the September 19 Special Committee meeting (page 43). September 24 is when CSC, Pamplona, and Mac-Gray executed the exclusivity agreement (page 44). That later exclusivity execution confirms the path chosen, but it is not the best date for the target's decision to drop Party A and Party B.

**Action implication.** Keep AI's September 19 drop rows; update reference dates/types. No rule change.

## Rulebook/reference implications

No rulebook or prompt change is required from this diff. The current rules already cover the observed patterns:

- Range bids belong in `bid_value_lower` / `bid_value_upper`, not in `bid_value_pershare`.
- Exact-count unnamed NDA groups should be atomized; Mac-Gray has 16 residual unnamed financial NDA signers after Party B and Party C.
- Silent NDA signers should receive `DropSilent`, not one aggregated dated `Drop`.
- Filing-dated process events should carry their filing dates rather than nulls.
- Execution is the October 14 merger-agreement execution; September 21 is the final price/exclusivity negotiation.
- Pamplona belongs in notes/financing context for this deal, not as a separate operating-acquirer execution row.

Reference update recommended for Mac Gray if/when the reference set is regenerated: correct deal identity/effective date, fill filing-supported dates, reinterpret range bids, atomize residual NDAs/silent drops, remove unsupported legacy final-round/extension rows, and replace the September 21/24 execution/drop coding with the filing-supported September 19 and October 14 events.

# Penford Corp (acq. Ingredion, 2014) — Three-Way Extraction Audit

**Filing:** DEFM14A filed 2014-12-29 (SEC CIK 739608).
**Ground truth:** `data/filings/penford/raw.md` Background of the Merger (pp. 29–39, filing lines 968–1168).
**Deal slug:** `penford`. Alex's 9 reference deals, archetype: *two stale prior auction attempts (2007, 2009); near-single-bidder endgame.*

Inputs audited (three-way, Verdict ∈ {AlexRight, BPRight, TryRight, BothAIRight, NoneRight, JudgmentCall, AlexFlagged}):

| Source | Rows | File |
|---|---|---|
| `bids_pipeline` | **33** | `inputs/penford_bids_pipeline.csv` |
| `bids_try` | **26** | `inputs/penford_bids_try.csv` |
| Alex reference | 25 | `inputs/penford_alex.csv` (generated from `reference/alex/penford.json`, 25 events) |

---

## TL;DR

**Which pipeline is closer to the filing:** `bids_pipeline` wins on *coverage* (33 rows; includes Party B, Party E, Party F, SEACOR as dropouts; cleanly distinguishes July 20 Secrecy Agreement from Aug 21 full NDA as separate NDA events; picks up Aug 28 Target Sale). `bids_try` wins on *cite hygiene, provenance, and prior-process handling* (carries `source_page` + `source_quote` on every row; emits the 2007/2009 stale attempts Alex tracks; correctly classifies Aug 10 as informal and flags Ingredion Aug 28–Oct 3 process events). **Net:** `bids_pipeline` has the more complete bidder-funnel; `bids_try` has the more defensible provenance and rulebook compliance. **Both AI sources materially outperform Alex's 25-row reference** on this deal.

**Bidder-type accuracy verdict (the central question for this deal):**
- Ingredion is **unambiguously `s` + `public: true`** per the filing p. 18: *"Ingredion was incorporated as a Delaware corporation in 1997 and its common stock is traded on the New York Stock Exchange."*
- Both AI pipelines correctly emit `public S` (bids_pipeline as string; bids_try as `base=s, public=true` via `bidder_type_note`).
- Alex's JSON emits `bidder_type.public: null` for Ingredion and for Parties A/C/D — **this is the converter-side `public` inference bug flagged in CLAUDE.md (13 `bidder_type` diffs). Alex's underlying xlsx already has `public S` on the Ingredion rows (see `penford_alex.csv` col `bidder_type_note`); the defect is isolated to `scripts/build_reference.py`, not to Alex's data.** Both AI sources + Alex's workbook **agree** that Ingredion is `public S`; only the reference JSON drops the `public` bit.
- All six "Party X" strategic counterparties are explicitly tagged by the filing as *"strategic counterparty"* or *"company in the industry"* — `base = "s"`, `public = null` is the right call (the filing does not reveal whether any of them were publicly traded). All three sources agree.
- The two stale 2007/2009 parties: filing says *"two parties engaged in the Company's industry"* → `base = "s"`, `public = null` is correct. All three sources agree.

**Stale-attempt handling verdict (the other archetype-critical question):**
- Alex includes 2007 + 2009 as 4 rows (1 NDA + 1 Drop per stale party, both anonymized as "1 party" / "A diffferent party" [sic], `bid_date_rough = 2007-01-15` and `2009-01-15`).
- `bids_try` includes them as 4 rows: Bidder Interest + NDA per stale party, dated `2007-07-01` / `2009-07-01` rough, with `bidder_alias = "2007 Industry Party"` / `"2009 Industry Party"`. Omits the matching Drops. Note: rules §L1 says *"prior sale processes are always included"*, and §L2 says they are `process_phase = 0` — but `bids_try` emits `process_phase = 1` on these rows (visible in row 2 of `penford_bids_try.csv`: `all_cash` field is being used as `process_phase` flag in Alex-format output; the underlying JSON should carry `process_phase = 0` per §L2). **CHECK: is the internal JSON `process_phase` correct but the CSV export of `process_phase` to `all_cash` column an exporter bug?**
- `bids_pipeline` **omits the 2007/2009 stale attempts entirely.** This is a miss against both Alex and rules §L1.

**Stale verdict:** `bids_try` partially correct (includes priors but adds `Bidder Interest` rows Alex doesn't have; omits Drop; may have wrong `process_phase` in CSV export). Alex most structurally clean (NDA + Drop per stale party, phase-0 convention). `bids_pipeline` wrong (priors missing).

**Top 3 divergences:**
1. **bids_pipeline is missing the 2007/2009 stale prior attempts.** Alex has 4 rows; bids_try has 4 rows; bids_pipeline has 0 rows. *Verdict: BothAlexTryRight (bids_pipeline wrong).*
2. **bids_pipeline catches 4 dropouts Alex + bids_try both miss** (Party B on 9/12 Drop; Party F on 9/29 Drop; SEACOR on 8/12 Target Interest + Drop; Party E as Target Interest). The filing explicitly narrates each. *Verdict: BPRight, NoneElseRight — on the bidder funnel, bids_pipeline is closer to the filing.*
3. **Ingredion's first-contact classification (July 17, 2014).** Alex: `Bidder Interest` with decimal-wedge `BidderID=4.5` (date_rough 7/17, date_precise 7/20). bids_pipeline: `Bidder Interest` on 7/17. bids_try: **`Bidder Sale`** on 7/17 citing §D1 "unambiguous intent-to-buy." Filing: *"Ms. Gordon advised Mr. Malkoski of Ingredion's interest in acquiring Penford... Ms. Gordon did not cite a specific number..."* — *interest in acquiring* is unambiguous intent but no concrete proposal; the concrete proposal arrives Aug 6 (*"Mr. Fortnum indicated Ingredion was prepared to submit a proposal... $17.00 per share"*). Per §D1 guidance *"When in doubt → `Bidder Interest`. The transition to `Bidder Sale` is recorded on a later date when the concrete proposal is made. Do NOT retcon the earlier row"* → **Alex + bids_pipeline correct; bids_try overclassifies.** bids_try should emit `Bidder Interest` 7/17 + `Bidder Sale` 8/6 (two rows per §D1 Imprivata pattern). *Verdict: AlexRight + BPRight; TryWrong.*

---

## Filing event timeline (ground truth, p. 29–39)

| # | Date (filing-stated) | Event | Page | Key quote |
|---|---|---|---|---|
| T-2 | 2007 (year only) | 2 unsolicited indications of interest + NDAs from 2 industry parties; no offers resulted | 29 | *"In 2007 and 2009, the Company received unsolicited indications of interest to acquire Penford from two parties engaged in the Company's industry... entered into a confidentiality agreement... These discussions did not result in offers to acquire the Company."* |
| T-1 | 2009 (year only) | second of the two stale prior indications | 29 | same block as T-2 |
| 1 | 2014-07-08/09 | Gordon voicemail to Malkoski seeking meeting | 30 | *"Ilene Gordon... left a voicemail message for Penford's Chief Executive Officer Thomas Malkoski, seeking a meeting."* |
| 2 | 2014-07-11 | SEACOR files amended 13D | 30 | *"SEACOR filed an amendment to its Schedule 13D... in which SEACOR stated its intent to nominate four candidates for election as directors."* — this is **activist context, not a bid-process event** |
| 3 | 2014-07-17 | Gordon–Malkoski lunch; **Ingredion interest in acquiring Penford** | 30 | *"Ms. Gordon advised Mr. Malkoski of Ingredion's interest in acquiring Penford... Ms. Gordon did not cite a specific number."* → `Bidder Interest` per §D1 |
| 4 | 2014-07-20 | **Secrecy Agreement** (pre-NDA, limited scope) | 30 | *"executed a Secrecy Agreement, effective as of July 20, 2014, providing for limited exchange of confidential information"* → `NDA` with `additional_note = "Secrecy Agreement"` (superseded Aug 21) |
| 5 | 2014-07-24 | Executive Committee directs retention of Deutsche Bank | 30 | *"directed management to proceed to retain Deutsche Bank as the Company's financial advisor... An engagement letter with Deutsche Bank was executed on September 11, 2014."* → this is when the *decision* is made; formal engagement 9/11 |
| 6 | 2014-08-01 | Party A representative emails Malkoski for a call | 31 | *"a representative acting on behalf of a company in the industry (referred to as Party A) sent Mr. Malkoski an email"* — preliminary |
| 7 | 2014-08-06 | **Ingredion prepared to submit proposal at $17.00/share (informal)** | 31 | *"Mr. Fortnum indicated Ingredion was prepared to submit a proposal to acquire the Company. Mr. Fortnum suggested that a price of $17.00 per share on a fully diluted basis could likely get support from Ingredion's board."* → `Bidder Sale` transition + first informal `Bid $17` |
| 8 | 2014-08-10 | **Ingredion letter, indicative $18.00/share** (informal) | 31 | *"received a letter from Mr. Fortnum, confirming Ingredion's interest... providing an indicative valuation of $18.00 per share in cash for all of the outstanding capital stock of Penford on a fully diluted basis."* → informal range bid |
| 9 | 2014-08-11 | **Party A CEO expresses interest** (preliminary, no price) | 32 | *"Party A's Chief Executive Officer also informally discussed Party A's potential interest in acquiring or combining with Penford."* → `Bidder Interest` |
| 10 | 2014-08-12 | **SEACOR declines potential acquisition interest** | 32 | *"Mr. Behrens stated that SEACOR was not interested in participating in any potential sale process at that time."* → target-initiated inquiry + `Drop`. SEACOR is the 9.28% holder, not a traditional bidder — target-reached-out pattern (Mac-Gray §D1) |
| 11 | 2014-08-21 | **Full nondisclosure + standstill agreement (supersedes Secrecy)**; Penford management presentation to Ingredion + J.P. Morgan (Ingredion's IB) | 33 | *"Ingredion and Penford executed a nondisclosure and standstill agreement that superseded the prior Secrecy Agreement."* + first narrated appearance of J.P. Morgan Securities as Ingredion's financial advisor |
| 12 | 2014-08-28 | **Board authorizes market-check process** (Target Sale) | 33 | *"The board also authorized management and Deutsche Bank to proceed with the market check process as described at the meeting."* |
| 13 | 2014-09-06 | J.P. Morgan sends Deutsche Bank initial merger-agreement draft | 34 | *"On September 6, 2014, J.P. Morgan Securities provided Deutsche Bank with an initial draft of a merger agreement"* |
| 14 | 2014-09-09 | Party A + Party B express interest during market check | 34 | *"Party A expressed interest... another strategic counterparty contacted by Deutsche Bank (referred to as Party B) expressed interest"* |
| 15 | 2014-09-10 | Party C expresses interest | 34 | *"a third potential strategic counterparty... (referred to as Party C) expressed interest in pursuing a transaction"* |
| 16 | 2014-09-11 | Party D expresses interest; Deutsche Bank engagement letter formally signed | 34 | *"a fourth potential strategic counterparty... (referred to as Party D) expressed interest"* + *"An engagement letter with Deutsche Bank was executed on September 11, 2014"* |
| 17 | 2014-09-12 | Party B declines (does not sign NDA); Deutsche Bank voicemail to Party E (never responds) | 34 | *"Party B informed Deutsche Bank that it had decided not to move forward with discussions or sign a nondisclosure agreement."* + Party E voicemail sequence |
| 18 | 2014-09-15 | **Party C executes NDA** | 34 | *"Penford and Party C executed a nondisclosure and standstill agreement"* |
| 19 | 2014-09-17 | **Ingredion revised $18.25–$18.50/share verbal** (informal range) | 35 | *"Ingredion could potentially increase its proposal from $18.00 to $18.25 or $18.50 per share on a fully diluted basis."* |
| 20 | 2014-09-23 | **Party D executes NDA** | 35 | *"Penford and Party D executed a nondisclosure and standstill agreement"* |
| 21 | 2014-09-24 | Board discusses adding Party F, Party G; authorizes Party F outreach only; Deutsche Bank contacts Party F | 35 | *"Deutsche Bank contacted Party F regarding a potential transaction"* |
| 22 | 2014-09-25 | Party C management presentation | 35 | *"members of Penford's management team provided a presentation to Party C"* |
| 23 | 2014-09-29 | **Party F declines** (not a suitable strategic fit) | 36 | *"Party F communicated to Deutsche Bank that a combination with Penford was not a suitable strategic fit and declined to pursue further discussions"* |
| 24 | 2014-09-30 | **Party A executes NDA** | 36 | *"Penford and Party A executed a nondisclosure and standstill agreement"* + Deutsche Bank tells Party A not to expect management presentations below $20/share |
| 25 | 2014-10-02 | **Ingredion verbal confirm $18.50; then letter raising to $19.00** | 36 | two events same day: *"Mr. Fortnum then stated that Ingredion was prepared to move forward based on a proposed price of $18.50 per share"* + *"Penford received a letter from Ingredion... increasing the proposed price to $19.00 per share"* |
| 26 | 2014-10-03 | **Board authorizes finalizing merger with Ingredion** | 36–37 | *"the directors present at the board meeting unanimously directed management to proceed to negotiate and finalize a definitive agreement with Ingredion."* → `Final Round Ann` / implicit winner-selection |
| 27 | 2014-10-04 | **Party A verbal: offer would be below $17.50–$18.00 range** (informal) | 37 | *"Deutsche Bank followed up with Party A... pursuant to which Party A indicated any offer would be below $17.50 - $18.00 per share in cash."* |
| 28 | 2014-10-08 | **Party D drops** (does not intend to move forward) | 37 | *"Party D, who indicated that it did not intend to move forward with discussions"* |
| 29 | 2014-10-13 | **Party A revises range downward to $16.00–$18.00** | 38 | *"Party A indicated that its value range... had been reduced from $17.50 - $18.00 per share to $16.00 - $18.00 per share, due to increased volatility"* |
| 30 | 2014-10-14 | **Party A formal letter at $16.00** (per-share point, below floor); **Ingredion confirms $19.00**; **merger agreement executed evening** | 38–39 | *"Party A provided a formal letter with its indication of interest... at a price of $16.00 per share"* + *"Penford and Ingredion finalized and executed the merger agreement"* |
| 31 | 2014-10-14 | Deutsche Bank reports at board meeting: "remaining three of which either did not move forward in a timely manner or made a lower indication of value" — this retrospectively confirms Party C dropped + Party A's bid rejected | 38 | *"six potential counterparties, two of which declined to enter into nondisclosure agreements, one of which never returned Deutsche Bank's voicemail... remaining three of which either did not move forward in a timely manner or made a lower indication of value."* → decomposes: 2 no-NDA (B + F), 1 no-response (E), 3 NDA-signers either-late-or-lower (A + C + D). |

**Deal-level facts:** Merger consideration $19.00/share all-cash; announced 10/15/2014; effective 3/11/2015; **target legal counsel = Perkins Coie LLP** (p. 30); **acquirer legal counsel = Sidley Austin LLP** (p. 37); **target IB = Deutsche Bank** (engagement letter 9/11, decision 7/24); **acquirer IB = J.P. Morgan Securities** (first narrated 8/21). **Termination fee = $7.6M** (p. 34); **shareholder termination fee = $2.0M**; **no financing contingency**.

---

## Source-by-source row counts and structure

### Alex reference (25 rows; from `reference/alex/penford.json`)

| Bidder | # rows | `bidder_type` | Notable |
|---|---|---|---|
| "1 party" (2007 stale) | 2 (NDA 2007-01-15, Drop 2007-01-15) | `base=s, public=null` | `comments = "[EVERYTHING IN GREY SHOULD NOT BE HERE]"` on first row — **Alex's own annotation flagging these rows as problematic/maybe-should-not-be-included**; not in `alex_flagged_rows.json` but the comment is a yellow flag |
| "A diffferent party" (2009 stale) | 2 (NDA, Drop at 2009-01-15) | `base=s, public=null` | note the triple-f typo Alex carried from workbook |
| Ingredion | 10 (Bidder Interest, NDA 7/20, 3× informal Bid 8/6, 8/10, 9/17, 10/2-×2, 10/8 formal Bid, Executed 10/14) | `base=s, public=null` | **public=null is the converter bug**; workbook says `public S`. Note Alex uses decimal BidderIDs (5.5, 14.5, 18.5, 21.5) for "wedge" events (IB, Final Round Ann, Executed) — legacy xlsx convention stripped per §A1 in regenerated JSON |
| Deutsche Bank | 1 (IB 2014-08-21 precise, 2014-07-30 rough) | `null` | comment flags the IB-date ambiguity: *"It looks like DB was already selected on July 30... engagement letter was signed on Sep 11. Which date should be used?"* — **Alex is asking Austin which date, not resolving it** |
| Party C | 2 (NDA 9/15, Drop 10/14) | `base=s, public=null` | |
| Party D | 2 (NDA 9/23, Drop 10/8) | `base=s, public=null` | |
| Party A | 4 (NDA 9/30, 3× informal Bid at 10/3, 10/13, 10/14 per-share point, Drop 10/14) | `base=s, public=null` | |
| Final Round Ann | 1 (no bidder) | `null` | BidderID=14.5, date_rough 10/3, comment quotes the 10/3 board-authorize-Ingredion event |

**Missing from Alex:** Party B (NDA-declined dropout, 9/12), Party E (no-response, 9/12 voicemail), Party F (9/29 declined), SEACOR (8/12 declined), acquirer IB J.P. Morgan (8/21). **Party G never contacted per board decision, so correctly omitted.**

Total: 25 rows. Alex's BidderIDs jump: 1, 2, 3, 4, 4.5, 5, 5.5, 6, 7, 8, 9, 10, 11, 12, 14.5, 13, 14, 15 (out-of-order!), 17 (skips 16!), 18, 18.5, 19, 20, 21, 21.5. The out-of-order / skipped structure reflects Alex's legacy xlsx "decimal-wedge" convention, preserved via the `bidder_ids_renumbered_per_a1` deal flag in the JSON. The xlsx `BidderID` column is *not* a bidder-identity but an event-sequence with holes where Alex inserts/deletes mid-edit.

### bids_pipeline (33 rows)

| Bidder | # rows | `bidder_type` | Notable |
|---|---|---|---|
| Ingredion Inc. | 11 (Bidder Interest 7/17, NDA 7/20, 3× informal Bid 8/6, 8/10, 9/17, NDA 8/21, 2× informal Bid 10/2, Formal Bid 10/14, Executed 10/14) | `public S` | correct; splits Secrecy (7/20) vs full NDA (8/21) as two NDA rows |
| Party A | 7 (Bidder Interest 8/11, Bidder Interest 9/9, NDA 9/30, 2× informal Bid 10/4, 10/13, informal Bid 10/14, Drop 10/14 [no date]) | `S` | correctly atomizes two Bidder Interest events (8/11 independent + 9/9 market-check) |
| Party B | 2 (Bidder Interest 9/9, Drop 9/12) | `S` | **bids_pipeline uniquely captures Party B dropout** |
| Party C | 3 (Bidder Interest 9/10, NDA 9/15, Drop 10/14) | `S` | |
| Party D | 3 (Bidder Interest 9/11, NDA 9/23, Drop 10/8) | `S` | |
| Party E | 1 (Target Interest 9/12) | `S` | **uniquely captures Party E no-response event** |
| Party F | 2 (Target Interest 9/24, Drop 9/29) | `S` | **uniquely captures Party F** |
| SEACOR | 2 (Target Interest 8/12, Drop 8/12) | `S` | **uniquely captures SEACOR as a declined target-initiated inquiry**. Note filing: Deutsche Bank identified SEACOR as potential counterparty, Hatfield contacted Behrens (SEACOR board rep), SEACOR declined. Matches Mac-Gray "Target Interest" pattern per §D1. |
| Deutsche Bank | 1 (IB 9/11) | none | dates to engagement-letter execution; comments acknowledge 7/24 was the board directive |
| NA (deal-level) | 2 (Target Sale 8/28, Target Sale 10/3) | none | 10/3 is the board's authorization to finalize with Ingredion |

**Missing from bids_pipeline:** 2007 + 2009 stale attempts (4 rows missing); J.P. Morgan Securities as Ingredion's IB (the filing names it on 8/21 as "Ingredion's financial advisor" — per §J1 "Advisors to acquirers are also emitted"; bids_pipeline skips).

**BidderIDs:** 0.5 to 30 (uses Alex-style decimal wedges: 0.5, 14.5, 18.5, 21.5, 23.5, 28.5). No gaps. Carries no `source_page` / `source_quote` columns. Uses legacy `bid_note = "" + bid_type = "Informal"` for bid rows (not §C3-compliant `bid_note = "Bid"`).

### bids_try (26 rows)

| Bidder | # rows | `bidder_type` | Notable |
|---|---|---|---|
| 2007 Industry Party | 2 (Bidder Interest 2007-07-01, NDA 2007-07-01) | `S` with `bidder_type_ambiguous` soft flag | captures stale prior; **omits the implicit Drop** (filing says "did not result in offers" which is implicit drop) |
| 2009 Industry Party | 2 (Bidder Interest, NDA) | `S` with `bidder_type_ambiguous` | same structure as 2007 |
| Ingredion | 8 (Bidder Sale 7/17, NDA 7/20, informal Bid 8/10 $18, NDA 8/21, informal Bid 9/17 $18.25–$18.50, informal Bid 10/2 $19, Executed 10/14) | `public S` | **missing the 8/6 $17 bid!** — filing explicitly narrates *"a price of $17.00 per share on a fully diluted basis"* (p. 31). bids_try omits this event. Also missing the 10/14 formal Bid (filing: *"Mr. Fortnum called Mr. Malkoski to confirm the proposed price of $19.00"* + *"exchanged successive drafts of the merger agreement"* — the formal confirmation). Pipeline appears to have collapsed Ingredion to 8 rows (losing 3 events vs Alex's 10). Also, row 2 misclassifies 7/17 as **Bidder Sale** (see TL;DR analysis) |
| J.P. Morgan Securities | 1 (IB 8/21) | none | **correctly emits acquirer IB per §J1**; bids_pipeline misses this |
| Deutsche Bank | 1 (IB 8/11) | none | anchor date = *"Executive Committee met with... representatives of... Deutsche Bank"* — earliest narrated advisory action per §J1. More defensible than bids_pipeline's 9/11 (formal engagement letter) or Alex's 8/21 (comment-flagged, under-documented) |
| Party A | 5 (Bidder Interest 8/11, NDA 9/30, 3× informal Bid 10/4, 10/13, 10/14) | `S` | **missing Drop row** (filing doesn't narrate explicit Party A withdrawal, but the 10/14 $16 bid below the $20 floor plus Deutsche Bank's "remaining three... lower indication of value" implicitly ends Party A's candidacy). bids_pipeline has a Drop row (no date); Alex has Drop at 10/14. |
| Party B | 2 (Bidder Interest 9/9, Drop 9/12) | `S` | present, matches bids_pipeline |
| Party C | 2 (Bidder Interest 9/10, NDA 9/15) | `S` with `nda_without_bid_or_drop` soft flag | **missing Drop row** (filing retroactively identifies Party C as one of the "remaining three... did not move forward in a timely manner" on p. 38). bids_pipeline + Alex both emit Drop 10/14. This is the Providence-iter-7 soft-flag pattern Austin flagged in CLAUDE.md as open. |
| Party D | 3 (Bidder Interest 9/11, NDA 9/23, DropTarget 10/8) | `S` | — DropTarget classification per §I1 vs Drop is a judgment call (filing says *"Party D... indicated that it did not intend to move forward"* — the `indicated` verb is bidder-side voluntary, not target-rejected; bids_try flags `drop_agency_ambiguous`). Alex + bids_pipeline both use `Drop`. **`Drop` is more defensible here; §I1 gives voluntary language priority.** |
| NA (deal-level) | 0 | — | **missing Target Sale 8/28** (board authorization for market check); **missing Target Sale / Final Round 10/3** (board authorizes Ingredion) |

**Missing from bids_try:** Party E (9/12 no-response), Party F (9/24 Target Interest + 9/29 Drop), SEACOR (8/12 declined), Target Sale 8/28, Target Sale/Final Round Ann 10/3, Ingredion 8/6 $17 bid, Ingredion 10/14 formal bid, Party A 10/14 Drop, Party C 10/14 Drop, stale 2007/2009 Drops.

**Carries:** `source_page` + `source_quote` on every row. Carries detailed `additional_note` per-row including §G1 informal justification. Carries soft flags (`bidder_type_ambiguous`, `drop_agency_ambiguous`, `nda_without_bid_or_drop`, `resolved_name_not_observed`). Uses §C3-compliant `bid_note = "Bid"` + `bid_type = informal | formal`.

**BidderIDs:** 1..26 strict sequence per §A1. No gaps.

---

## Divergence table

| # | Event / date | Alex | bids_pipeline | bids_try | Verdict | Notes |
|---|---|---|---|---|---|---|
| 1 | 2007 stale prior (NDA + Drop) | ✓ 2 rows, `base=s`, date_rough | — missing | ✓ 2 rows (BI + NDA, no Drop), date rough `2007-07-01` | **AlexRight** on count (NDA+Drop); TryPartial (BI+NDA but no Drop); BPMiss | §L1 requires inclusion |
| 2 | 2009 stale prior (NDA + Drop) | ✓ 2 rows | — missing | ✓ 2 rows (BI + NDA) | **AlexRight**; TryPartial; BPMiss | same as above |
| 3 | Ingredion first contact 7/17 classification | Bidder Interest | Bidder Interest | **Bidder Sale** | **AlexRight + BPRight** | Per §D1 "When in doubt → Bidder Interest... Do NOT retcon"; filing says "interest in acquiring" without price → Interest. Transition to Bidder Sale happens 8/6 with $17. bids_try overclassifies. |
| 4 | Ingredion Bidder Sale / transition 8/6 | — missing (jumps to bid) | — missing (jumps to bid, conflates with Interest) | — missing (no Bidder Sale row emitted) | **NoneRight** | Per §D1 Imprivata pattern, should emit `Bidder Sale` on 8/6 to mark the interest→concrete-proposal transition. All three omit. |
| 5 | Ingredion Secrecy Agreement 7/20 | NDA (1 row) with comment noting it's a Secrecy Agreement | NDA (separate row) | NDA with `additional_note` noting supersession by 8/21 | **BothAIRight + AlexOK** | bids_pipeline + bids_try both emit 2 NDA rows (7/20 + 8/21); Alex emits only the 7/20 row. Filing narrates two separate agreements. |
| 6 | Ingredion full NDA + standstill 8/21 | — missing (second NDA) | ✓ | ✓ | **BothAIRight; AlexMiss** | Filing explicitly says *"executed a nondisclosure and standstill agreement that superseded the prior Secrecy Agreement."* Two NDAs, two rows per §E1. |
| 7 | Ingredion $17 informal bid 8/6 | ✓ `Inf $17` | ✓ `Informal $17` | **— missing** | **AlexRight + BPRight; TryMiss** | Filing explicitly states *"a price of $17.00 per share on a fully diluted basis could likely get support from Ingredion's board."* This is a narrated informal price. bids_try's omission is a bid-data loss. |
| 8 | Ingredion $18 informal bid 8/10 | ✓ | ✓ | ✓ | **All agree** | |
| 9 | Ingredion $18.25–$18.50 range 9/17 | ✓ `Inf $18.25, lower=18.25, upper=18.50` | ✓ `Informal $18.25`, range | ✓ range (lower=$18.25, upper=$18.50), `bid_value_pershare=NA` | **JudgmentCall** | All three emit range. bids_try drops the `bid_value_pershare` (valid per §H range-only convention). Minor shape diff. |
| 10 | Ingredion $18.50 verbal 10/2 | ✓ separate row (Inf $18.50) | ✓ separate row (Informal $18.50) | — missing (conflated with $19 letter same day) | **AlexRight + BPRight; TryMiss** | Filing narrates two 10/2 events: morning call ($18.50) then afternoon letter ($19.00). bids_try emits only the $19 letter. |
| 11 | Ingredion $19 informal letter 10/2 | ✓ | ✓ | ✓ | **All agree** | |
| 12 | Board authorizes market check 8/28 (`Target Sale`) | — missing | ✓ `Target Sale` | — missing | **BPRight** | Filing: *"The board also authorized management and Deutsche Bank to proceed with the market check process."* This is a board-level sale-process decision; per §D1 `Target Sale` on its authorization date. |
| 13 | Board authorizes Ingredion finalize 10/3 (`Final Round Ann`) | ✓ `Final Round Ann` BidderID=14.5 | ✓ `Target Sale` 10/3 | — missing | **AlexRight** on the event; **BPWrong** on classification (`Target Sale` vs `Final Round Ann`); **TryMiss** | Filing: *"the directors present at the board meeting unanimously directed management to proceed to negotiate and finalize a definitive agreement with Ingredion."* This is not `Target Sale` (already happened 8/28) — it's **implicit final-round selection** per §K2 ("the Board authorized [IB] to advance [subset] to [final]"). Alex's `Final Round Ann` is more defensible than bids_pipeline's second `Target Sale`. |
| 14 | Ingredion 10/14 formal bid $19 | ✓ `Formal Bid $19` (bid_type="Formal") | ✓ `Formal $19` | — missing (Ingredion's last row is Executed 10/14) | **AlexRight + BPRight; TryMiss** | Filing: *"Mr. Fortnum called Mr. Malkoski to confirm the proposed price of $19.00"* + *"Perkins Coie and Sidley Austin exchanged successive drafts of the merger agreement"* — this is the formal confirmation preceding same-day execution. Should be a separate `Bid` row with `bid_type=formal`. |
| 15 | Executed 10/14 | ✓ BidderID=21.5 | ✓ BidderID=30 | ✓ BidderID=26 | **All agree** | |
| 16 | Party A 8/11 CEO meet (`Bidder Interest`) | — missing (treats 9/30 NDA as first Party A event) | ✓ `Bidder Interest` 8/11 | ✓ `Bidder Interest` 8/11 | **BothAIRight; AlexMiss** | Filing: *"Party A's Chief Executive Officer also informally discussed Party A's potential interest in acquiring or combining with Penford."* This is a first-contact event independent of the 9/9 market-check re-engagement. |
| 17 | Party A 9/9 re-engagement (`Bidder Interest`) | — missing | ✓ `Bidder Interest` 9/9 | — missing | **BPRight** | Per §I2 re-engagement after initial non-commitment; filing *"Party A expressed interest in having further discussions regarding a transaction."* bids_pipeline correctly emits. |
| 18 | Party A 10/14 Drop | ✓ `Drop` (date 10/14) | ✓ `Drop` (no date) | — missing | **AlexRight + BPPartial (no date); TryMiss** | Filing pp. 38 says Deutsche Bank reported Party A gave a "lower indication of value." Implicit end to candidacy. bids_try missed it. |
| 19 | Party B 9/9 interest + 9/12 Drop | — missing | ✓ (2 rows) | ✓ (2 rows) | **BothAIRight; AlexMiss** | Alex's reference skips Party B entirely. Filing explicitly names Party B and narrates the decline. |
| 20 | Party C 10/14 Drop | ✓ `Drop` | ✓ `Drop` | — missing (soft flag `nda_without_bid_or_drop`) | **AlexRight + BPRight; TryMiss-with-softflag** | Per CLAUDE.md Austin's open question: bids_try is following the "don't fabricate catch-all drops" stance but the filing DOES narrate "remaining three... did not move forward in a timely manner" which is evidence enough for a Drop on 10/14. **Alex + bids_pipeline interpret correctly; bids_try is overcautious.** |
| 21 | Party D 10/8 Drop vs DropTarget classification | `Drop` | `Drop` | `DropTarget` with `drop_agency_ambiguous` soft flag | **AlexRight + BPRight; TryWrong** | Filing: *"Party D... indicated that it did not intend to move forward"* — `indicated` is voluntary-withdrawal agency per §I1. Default should be `Drop`, not `DropTarget`. bids_try's flag is good instinct but wrong code. |
| 22 | Party E 9/12 voicemail (no response) | — missing | ✓ `Target Interest` 9/12 | — missing | **BPRight** | Filing narrates target-initiated outreach to Party E who never responded. Per Mac-Gray §D1 pattern. |
| 23 | Party F 9/24 Target Interest + 9/29 Drop | — missing | ✓ (2 rows) | — missing | **BPRight** | Filing explicitly narrates both events. |
| 24 | SEACOR 8/12 Target Interest + Drop | — missing | ✓ (2 rows `Target Interest` + `Drop`) | — missing | **BPRight** | Filing: Hatfield asked Behrens (SEACOR board rep) whether SEACOR interested; Behrens declined. Per §D1 this is target-initiated inquiry + voluntary decline. bids_pipeline correctly includes SEACOR in the bidder funnel even though SEACOR is also a 9.28% holder (who later signs the voting agreement). Alex + bids_try omit. |
| 25 | J.P. Morgan Securities as Ingredion's IB 8/21 | — missing | — missing | ✓ `IB` 8/21 | **TryRight** | Per §J1 "Advisors to acquirers are also emitted." Filing explicitly names J.P. Morgan Securities as Ingredion's financial advisor. Alex + bids_pipeline omit. |
| 26 | Deutsche Bank IB date | 8/21 precise (with comment flagging ambiguity) | 9/11 (engagement letter) | 8/11 (first advisory action) | **JudgmentCall** | Per §J1 "earliest narrated date on which the filing describes the bank acting in an advisory capacity" → **bids_try is most compliant with §J1.** 7/24 is when the board decided to retain; 8/11 is when Deutsche Bank first acts advisory (attends EC meeting); 9/11 is formal engagement letter. Alex's 8/21 (management presentation) is also defensible but later than the first advisory action. |
| 27 | Ingredion `public` field | `public: null` (converter bug; xlsx has `public S`) | `public S` | `public S` | **BothAIRight; AlexRefWrong (converter bug)** | Alex's underlying xlsx `bidder_type_note` column has `public S` on Ingredion rows (visible in `penford_alex.csv`); `scripts/build_reference.py` drops the `public` bit during xlsx→JSON conversion. Not an Alex-workbook error; a converter error. |
| 28 | Ingredion Sept 6 J.P. Morgan sends merger draft | — missing | — missing | — missing | **NoneRight** | Filing: *"J.P. Morgan Securities provided Deutsche Bank with an initial draft of a merger agreement"* — could argue this is process-meta, not a bid event. Informational only; no rule requires. |
| 29 | TargetName casing | `PENFORD CORP` | `PENFORD CORP` | `Penford Corporation` | **JudgmentCall** | Filing uses both "Penford Corporation" and "PENFORD CORP". bids_try reflects the filing's corporate-name casing; the other two use xlsx's uppercase convention. Same residual across iters per CLAUDE.md. |
| 30 | Acquirer casing | `INGREDION INC` | `INGREDION INC` | `Ingredion Incorporated` | **JudgmentCall** | Same as #29. Filing's verbatim `Ingredion Incorporated` is most source-faithful. |
| 31 | DateEffective | `2015-03-11` | blank | `NA` | **AlexRight** | Alex has DateEffective; bids_pipeline + bids_try miss. This is deal-level meta typically sourced from the xlsx header, not the filing narrative. AI pipelines presumably didn't have access to the xlsx-side DateEffective. |
| 32 | Target legal counsel | null | not emitted | not emitted | **NoneRight** | Per §J2 should be deal-level field; filing p. 30 says *"Perkins Coie LLP... Penford's legal counsel"*. All three miss. |
| 33 | Acquirer legal counsel | null | not emitted | not emitted | **NoneRight** | §J2 deal-level; filing p. 37 says *"Sidley Austin LLP... Ingredion's legal counsel"*. All three miss. |
| 34 | Termination fee | null | not emitted | not emitted | **NoneRight** | Filing p. 34 says *"termination fee of $7.6 million"*. §schema requires. |

Row-count summary: Alex **25**, bids_pipeline **33**, bids_try **26**.
Unique events captured by bids_pipeline that both others miss: **Party B, Party E, Party F, SEACOR, second Ingredion Target Sale row (Aug 28)** = 8 rows.
Unique events captured by bids_try that both others miss: **J.P. Morgan as acquirer IB, 2007/2009 Bidder Interest rows (prior-process richer than Alex's NDA-only)** = 3 rows.
Unique events in Alex alone: **2007/2009 Drops (implicit), 10/14 Party A Drop with date, Final Round Ann 10/3** = 4 rows. (Alex's Final Round Ann 10/3 is analytically correct; the 2007/2009 drops are debatable — filing says "did not result in offers" but doesn't narrate a Drop event.)

---

## Systemic findings

### 1. Bidder typing (the central question for this deal)

**The AI pipelines are correct; the reference-JSON converter has a bug.**

Evidence:
- The filing p. 18 explicitly states Ingredion trades on the NYSE → `public: true`.
- Alex's **underlying xlsx** (penford_alex.csv col `bidder_type_note`) already has `public S` on Ingredion rows — the data is correct at the xlsx level.
- The converter (`scripts/build_reference.py`) is dropping the `public` bit during xlsx → JSON conversion, producing `public: null` in the reference JSON.
- Both AI pipelines independently classify Ingredion as `public S` matching the filing.
- For Parties A/C/D (all "strategic counterparty" / "company in the industry"), `public: null` is correct because the filing doesn't reveal their trading status. All three sources agree here.
- For 2007/2009 stale parties, `public: null` is correct (filing only says "industry parties"). Alex + bids_try agree.

**Action item:** Fix the converter per Austin's flagged open question in CLAUDE.md — "Resolve the `bidder_type.public` inference policy in `scripts/build_reference.py`." More aggressive public-strategic inference in the converter would collapse 13 of Penford's 13 `bidder_type` field diffs to 0 (Ingredion's 8 rows + Parties A/C/D's 5 rows where AI says `public=null`). Actually the diff count may be just the Ingredion rows — Parties A/C/D should still be `public=null` on both sides.

**Base-type question:** All bidders are **strategic** (`base = "s"`). The filing p. 32 explicitly differentiates: *"Deutsche Bank also reviewed with the Executive Committee certain categories of potential counterparties, including financial sponsors and strategic purchasers, and noted their view that... strategic purchasers likely would be able to provide a more compelling valuation relative to a financial sponsor purchaser."* Deutsche Bank's market check per p. 34 was to *"six potential strategic counterparties in the same or similar industries"* — no PE sponsors are in this deal. All three sources correctly emit `base = "s"` across the board.

### 2. Stale-attempt handling

The filing narrates a **single sentence block** (p. 29): *"In 2007 and 2009, the Company received unsolicited indications of interest to acquire Penford from two parties engaged in the Company's industry. In each case, the Company entered into a confidentiality agreement and engaged in discussions and exchanged information with the party expressing interest. These discussions did not result in offers to acquire the Company."*

- **Alex:** emits 4 rows (NDA + Drop for each party at `2007-01-15` / `2009-01-15` rough dates). Alex's own comment on the 2007 NDA row says *"[EVERYTHING IN GREY SHOULD NOT BE HERE]"* — suggesting Alex himself is unsure whether these priors should be included. They **are** in the workbook and the reference JSON but carry this internal ambiguity marker.
- **bids_pipeline:** omits entirely. This is a **miss** against rules §L1 ("prior sale processes are always included") and against Alex.
- **bids_try:** emits 4 rows (Bidder Interest + NDA per stale party at `2007-07-01` / `2009-07-01`). **Missing the Drop** (filing says "did not result in offers" which is implicit drop; §L1 doesn't require explicit Drop narration but §I1 dropout agency requirements make it hard to emit a Drop without a specific quote). bids_try's approach of Bidder Interest + NDA with no Drop is more conservative than Alex but arguably under-counts the funnel.

**Nit on bids_try's `process_phase`:** CSV col `all_cash` is `1` on the 2007/2009 rows but per rules §L2 stale priors should carry `process_phase = 0`. Check whether the underlying JSON is correct and only the CSV export is wrong, or whether the extractor emits `process_phase = 1` which would be a rulebook violation.

**Verdict:** Alex and bids_try both include the priors (correct per §L1); bids_pipeline misses. Exact shape (NDA+Drop vs BI+NDA) is a judgment call given the filing's compressed narration.

### 3. Date precision

- **Alex:** Mix of precise and rough dates; uses `bid_date_rough` column even for precise dates in some legacy formatting. Strong on `bid_date_precise` for key Ingredion events (7/20, 8/6, 8/10, 9/17, 10/2, 10/8). Puts `Drop` + `NDA` dates in the xlsx `bid_date_precise` column in most cases.
- **bids_pipeline:** Precise dates throughout (MM/DD/YYYY). Strong coverage. One Drop row has no date (Party A Drop).
- **bids_try:** Precise dates throughout (YYYY-MM-DD). Strongest §B compliance — explicitly carries `bid_date_precise` null with `bid_date_rough` populated for 2007/2009 priors (informational rough phrase "2007" / "2009"), emits `date_inferred_from_rough` info flag where applicable.

**No systemic date errors in any source** on the main 2014 process.

### 4. Source-quote presence

- **Alex:** no `source_quote` / `source_page` columns (reference JSON intentionally omits evidence fields per `reference/alex/README.md`).
- **bids_pipeline:** no `source_quote` / `source_page` columns. Uses `comments_1/2/3` for narrative but not verbatim filing text + page cite.
- **bids_try:** full `source_quote` + `source_page` on every row. **Best-in-class provenance.** Every row is auditable against the filing text without re-reading the filing.

Per CLAUDE.md "every extracted row must carry `source_quote` and `source_page`. Rows without evidence are rejected by the validator." → **bids_pipeline output would fail the live `pipeline.validate()` hard check.** This matches the "bids_pipeline" label being a legacy / non-current-pipeline artifact; not a comparison between two equally-current pipelines.

### 5. Coverage philosophy

- **bids_pipeline** is maximalist: captures every named party and every narrated target-side outreach. Includes SEACOR and Party E even though neither becomes a real bidder. This mirrors the Providence-worcester pattern where NDA-signers-that-never-bid are kept in the funnel.
- **bids_try** is more conservative: emits rows only where the filing narrates a concrete event per-party. Omits Party E (no response = no event) and Party F (filing narrates just the target's outreach + the decline, which IS two events — bids_try still misses this).
- **Alex** is selective in a different way: omits entire branches (Party B, E, F, SEACOR) but captures the prior-process.

**None of the three captures the full funnel exactly.** For research purposes, bids_pipeline's 33 rows are closer to a "complete bidder funnel" view than Alex's 25 or bids_try's 26.

---

## Specific rule/prompt fixes

### Fix 1: Converter-side `public` inference (`scripts/build_reference.py`)
**Issue:** Reference JSON emits `public: null` even when Alex's xlsx `bidder_type_note` says `public S`.
**Fix:** When `bidder_type_note` contains `"public"`, set `bidder_type.public = true`.
**Impact:** Eliminates ~13 of 13 Penford `bidder_type` field diffs; likely reduces `bidder_type` diffs across stec/mac-gray/providence/penford by ~50+ rows total per CLAUDE.md's 65-diff estimate.
**Policy note:** Austin's CLAUDE.md flags this as an open question ("More aggressive public-strategic inference in the converter would collapse ~65 field diffs in one sweep. Converter-policy question, not rulebook."). This audit confirms: for Penford the fix is correct and unambiguous.

### Fix 2: §D1 "interest" vs "sale" prompt guidance
**Issue:** `bids_try` classified Ingredion's 7/17 first contact as `Bidder Sale` based on §D1's "unambiguous intent-to-buy even without a named price" clause. But the filing's phrase *"advised... of Ingredion's interest in acquiring Penford"* is expressing **interest**, not making a **proposal**. The concrete proposal is 8/6 ($17).
**Fix:** Tighten `prompts/extract.md` guidance on §D1 to emphasize: *"Bidder Interest" is the default for first-contact where the filing uses words like "interest," "interested in exploring," "potential interest," "interest in acquiring." "Bidder Sale" requires the filing to use words like "proposed to acquire," "offered to purchase," "indicated prepared to submit a proposal," OR the filing to cite a price.*
**Impact:** Reduces overclassification of first-contact events.

### Fix 3: §I1 "Drop" vs "DropTarget" agency guidance
**Issue:** `bids_try` classified Party D's 10/8 withdrawal as `DropTarget` despite the filing saying *"Party D... indicated that it did not intend to move forward"* — which is bidder-side voluntary phrasing.
**Fix:** Add to §I1 agency decision tree: *"When the bidder's own statement/action is the agent (`indicated it did not intend`, `informed the Company it would not`, `declined to proceed`), classify as `Drop` (voluntary). `DropTarget` is reserved for cases where the target actively rejects the bidder for reasons other than price cut (strategic, financing, regulatory)."* bids_try's `drop_agency_ambiguous` flag is good instinct but the default should be `Drop`.
**Impact:** Reduces Party D-style misclassifications.

### Fix 4: §K2 implicit final-round inference
**Issue:** Alex emits `Final Round Ann` on 10/3 (board authorizes finalizing with Ingredion). bids_pipeline emits `Target Sale` on 10/3 (misclassification — Target Sale was 8/28). bids_try misses the event entirely.
**Fix:** Add to `prompts/extract.md` §K2: *"When the filing narrates the board authorizing management to finalize a definitive agreement with a specific bidder (selection of winner), emit `Final Round Ann` on that date with `bidder_name = <winner>` (if attributable to a single bidder) or null (if framed as deal-level event). Do NOT emit a second `Target Sale` row — that event is already captured by the market-check authorization."*
**Impact:** Corrects bids_pipeline's double-Target-Sale pattern; prompts bids_try to include this event.

### Fix 5: §J1 acquirer-IB emission reminder
**Issue:** `bids_pipeline` omits J.P. Morgan Securities (Ingredion's IB) even though §J1 explicitly says *"Advisors to acquirers are also emitted."*
**Fix:** Add assertion-style language to `prompts/extract.md`: *"When the filing names a financial advisor to the acquirer (`Firm, [acquirer]'s financial advisor`), emit an `IB` row for that firm. Do NOT treat acquirer-side advisors as out-of-scope."*
**Impact:** Restores completeness of IB events.

### Fix 6: §P-D5 / §I1 implicit-drop for "remaining three... did not move forward" language
**Issue:** `bids_try` emits `nda_without_bid_or_drop` soft flag on Party C. But the filing p. 38 explicitly narrates (retroactively, on 10/14 board meeting): *"the remaining three of which either did not move forward in a timely manner or made a lower indication of value."* This IS filing evidence of a Drop — the three are Party A (made lower bid), Party C (did not move forward), Party D (did not move forward; already separately narrated on 10/8). Party C + the Party A Drop both have filing support here.
**Fix:** Add to §I1: *"When the filing retrospectively groups NDA signers as 'did not move forward' or 'failed to advance in a timely manner' (typically in a board-meeting summary), treat each NDA signer in the named subset as having a Drop event on the date of the board meeting. The shared `source_quote` is acceptable because each Drop row identifies its own bidder via separate enumeration in the filing narrative or by filing-provided list (e.g., p. 38 of Penford explicitly says the three are the remaining NDA signers other than Ingredion — Party A, Party C, Party D)."*
**Rationale:** This is distinguishable from the Providence §R2 problem because the filing DOES narrate the drop event even if not per-bidder: *"remaining three of which either did not move forward..."* is specific enough to justify one Drop row per NDA signer in the named set.
**Impact:** Resolves 2 of bids_try's `nda_without_bid_or_drop` soft flags on Penford (Party C + Party A where applicable).

---

## Open questions for Austin

1. **Accept the bids_try `Bidder Sale` classification for 7/17 Ingredion, or treat as AI overclassification?** This is a §D1 judgment call. The filing's "interest in acquiring" is short of "proposed to acquire" but arguably not short of "unambiguous intent-to-buy." Current rulebook language "When in doubt → Bidder Interest" suggests Interest is the right call, but bids_try's reading is not unreasonable. Decision impacts the prompt fix #2 above.

2. **Include or exclude the 2007/2009 stale attempts?** Alex's own comment `[EVERYTHING IN GREY SHOULD NOT BE HERE]` on the 2007 row suggests Alex himself is ambivalent. Rules §L1 says include. The deal-level `process_phase` field is designed to handle exactly this case (phase 0 = stale prior). **Confirm §L1 is still the policy and review bids_try's `process_phase` emission on these rows.**

3. **Party D: `Drop` or `DropTarget`?** `bids_try` says `DropTarget` with `drop_agency_ambiguous` flag. Alex + bids_pipeline both say `Drop`. Per §I1 the bidder-side phrasing should default to `Drop`. Confirm fix #3 above should land.

4. **Should the extractor emit a `Final Round Ann` on 10/3 board-authorizes-Ingredion event?** Alex does. bids_pipeline emits a second `Target Sale` (wrong). bids_try skips. This is the "implicit final round" §K2 pattern — confirm the prompt fix #4 is the right direction.

5. **Party A's 10/14 Drop:** Alex dates it 10/14; bids_pipeline has the event but no date; bids_try omits. The filing p. 38 implicitly ends Party A's candidacy via Deutsche Bank's "remaining three... lower indication of value" language at the 10/14 board meeting. Confirm fix #6 covers this too.

6. **SEACOR and Party E:** bids_pipeline captures these as `Target Interest` / `Drop` pairs; Alex + bids_try both skip. These are real filing events per §D1. **Should the extractor include target-initiated inquiries that are immediately declined?** My read of §D1 "Mac-Gray pattern" suggests yes, these should be included. But Alex's workbook chose not to. **Austin's call on whether bids_pipeline's more-complete funnel is the intended shape.**

7. **Deutsche Bank IB date — 7/24 (decision), 8/11 (first advisory action), 8/21 (management presentation), or 9/11 (engagement letter)?** §J1 says *"earliest narrated date on which the filing describes the bank acting in an advisory capacity."* bids_try's 8/11 (attends EC meeting advising on Ingredion proposal) is the earliest advisory action narrated in the filing and is the §J1-compliant choice. Alex's 8/21 precise (management presentation) is later but still advisory; bids_pipeline's 9/11 (engagement letter) is the latest and **least** §J1-compliant. Confirm bids_try's 8/11 is the target.

8. **Ingredion 8/6 $17 bid — why did bids_try miss it?** The filing explicitly narrates the $17 price. This is an extraction miss, not a judgment call. Worth checking bids_try's prompt / context window to see whether the entire Aug 6 sentence was dropped.

9. **Ingredion 10/14 formal bid $19 — why did bids_try miss it?** Same class of miss as #8. The formal confirmation preceding execution is a distinct event from the execution itself.

10. **Alex's legacy `BidderID` decimals (4.5, 5.5, 14.5, 21.5) — preserve as wedges or renumber?** The deal-level flag `bidder_ids_renumbered_per_a1` in the reference JSON says they are renumbered. But `penford_alex.csv` still shows decimal BidderIDs in the xlsx column (the CSV is a direct xlsx dump). Confirm scoring logic tolerates both forms.

---

## Summary table

| Dimension | Alex | bids_pipeline | bids_try | Winner |
|---|---|---|---|---|
| Row count | 25 | 33 | 26 | bids_pipeline (most complete funnel) |
| Stale priors (2007/2009) | ✓ | ✗ | ✓ | Alex + bids_try |
| Ingredion 8/6 $17 bid | ✓ | ✓ | ✗ | Alex + bids_pipeline |
| Ingredion 10/14 formal bid $19 | ✓ | ✓ | ✗ | Alex + bids_pipeline |
| Ingredion `public: true` | ✗ (converter bug) | ✓ | ✓ | bids_pipeline + bids_try |
| Party B / E / F / SEACOR coverage | ✗ | ✓ | ✗ (partial) | bids_pipeline |
| J.P. Morgan acquirer IB | ✗ | ✗ | ✓ | bids_try |
| Target legal counsel | — | — | — | none (all miss) |
| 7/17 Bidder Interest vs Sale | Interest (correct) | Interest (correct) | Sale (wrong) | Alex + bids_pipeline |
| 10/3 Final Round Ann | ✓ | Target Sale (wrong) | ✗ | Alex |
| §C3 bid_note compliance (`"Bid"`) | — (converter handles) | ✗ (legacy null) | ✓ (`"Bid"`) | bids_try |
| `source_page` + `source_quote` | ✗ (by design) | ✗ | ✓ | bids_try |
| §D1 unsolicited-first-contact flags | ✗ | ✗ | ✓ (`bidder_type_ambiguous`) | bids_try |
| Drop classification (Party D) | Drop (correct) | Drop (correct) | DropTarget (wrong) | Alex + bids_pipeline |
| Party A 10/14 Drop | ✓ | ✓ (no date) | ✗ | Alex + bids_pipeline |
| Party C 10/14 Drop | ✓ | ✓ | ✗ (soft flag) | Alex + bids_pipeline |
| Ingredion 7/20 vs 8/21 two-NDA split | ✗ (1 row) | ✓ (2 rows) | ✓ (2 rows) | bids_pipeline + bids_try |
| Tgt Sale 8/28 (market check authorization) | ✗ | ✓ | ✗ | bids_pipeline |
| §J1 earliest-advisory-action IB date | 8/21 (OK) | 9/11 (late) | 8/11 (compliant) | bids_try |
| BidderID sequence clean 1..N | ✗ (decimals, gaps) | ✗ (decimals) | ✓ (1..26) | bids_try |

**Overall winner for research use:** **bids_pipeline** on raw bidder-funnel coverage (captures the most distinct dropouts); **bids_try** on rule-compliance and provenance (cite on every row, §C3 / §J1 compliant, §A1 clean sequencing). Neither is complete. **Recommended composite:** take bids_try as the base output (compliance + provenance), merge in bids_pipeline's Party B/E/F/SEACOR coverage, fix bids_try's Aug 6 and Oct 14 Ingredion bid misses, and resolve the 7/17 and 10/3 classifications per the prompt fixes above.

**Alex's reference:** most trustworthy on archetypal structure (stale priors + Final Round Ann + Drop rows with dates) but misses entire bidder branches (Party B, Party E, Party F, SEACOR, J.P. Morgan acquirer IB) and has the `public: null` converter bug. On Penford, Alex's reference is **not ground truth** — it is a defensible legacy extraction that needs the AI-side corrections merged back.

# Mac-Gray three-way extraction audit

**Target:** Mac-Gray Corporation
**Acquirer:** CSC ServiceWorks, Inc. (CSC/Pamplona; CSC purchased by Pamplona in May 2013)
**Announcement:** 2013-10-15 | **Effective:** 2014-01-09 | **Form:** DEFM14A
**Filing:** `/Users/austinli/bids_try/data/filings/mac-gray/raw.md`
**Archetype under test:** banker terminated + rehired; target drops highest (nominal) formal bid; §E2.b NDA aggregation vs atomization

---

## TL;DR

- **Which pipeline is closer to Alex:** `bids_try` (45 rows) is dramatically closer to Alex (34) than `bids_pipeline` (65). The 11-row gap between `bids_try` and Alex is almost entirely (a) a 16-vs-1 split of the unnamed-financial-bidder NDAs (§E2.b atomization decision) and (b) four defensible extra events `bids_try` captures that Alex omits (Bid Press Release, merger-agreement Executed as distinct from the $21.25 bid row, DropAtInf for Party C at informal round, extra DropTarget for Party A). `bids_pipeline` additionally creates 16 synthetic per-placeholder `Drop` rows on 07/25 that have no bidder-specific narration in the filing — these are the primary cause of its inflation to 65.
- **65 / 45 / 34 row split explained:**
  - **Alex (34):** uses 1 aggregated NDA row (BidderID=2) for the 16 unnamed financials AND 1 aggregated `Drop` row (BidderID=9) for the same 16 on 07/25. §C3 migration: legacy `bid_note` blank + `Informal` bid rows, so bid rows become `Bid` `informal` in schema-conformant form.
  - **bids_try (45):** atomizes the 16 unnamed financial NDAs into 16 placeholder rows (`Financial 1..16`), then emits only the 4 named bidders' drops / final-round events going forward (no separate 16-way Drop). Adds IB initial-retention, `Bid Press Release`, `Bidder Sale` initiation, final-round announcements, and a separate `Executed` row. Good `source_quote`/`source_page` on every row.
  - **bids_pipeline (65):** atomizes the 16 NDA signers to placeholders (`bidder_1..bidder_16`, all dated 07/15 which is a guess) AND also emits 16 matching `Drop` rows for the same placeholders on 07/25 — essentially mirroring Alex's aggregate `Drop` row but per-placeholder. This is the single biggest source of its 20-row surplus over `bids_try`. bids_pipeline has NO `source_page` / `source_quote` columns at all (fields absent from header).
- **Acquirer-name verdict:**
  - Filing-verbatim canonical name is **"CSC ServiceWorks, Inc."** (it appears as the cover counterparty and in the precedent-transactions table, filing p. 47). `bids_try` uses `"CSC ServiceWorks, Inc."` (filing-verbatim). `bids_pipeline` uses `"CSC SERVICEWORKS, INC."` (upper-cased version — matches Alex's xlsx verbatim cell-casing, not the filing). Alex's workbook uses BOTH: some rows `"CSC SERVICEWORKS, INC."` and others `"CSC purchased by Pamplona in May/2013"`. The reference JSON picks `"CSC purchased by Pamplona in May/2013"` as the deal-level Acquirer (Alex's legacy commentary string, not the filing-correct name). **`bids_try` wins on acquirer naming**; bids_pipeline is close (right entity, wrong casing); Alex's reference is wrong (uses a parenthetical about Pamplona/CSC ownership instead of the actual merger counterparty).
- **Alex row 6960 (BidderID=21 Executed) confirmation:** Verified against filing. Alex's row 6957 already carries BidderID=21 (CSC/Pamplona $21.25 formal bid of 2013-09-21), so the Executed row on 2013-10-14 that also carries BidderID=21 is indeed a duplicate in the xlsx — confirmed per `reference/alex/alex_flagged_rows.json`. Alex's reference JSON already renumbers it to BidderID=32 via §Q4 (flag `bidder_id_renumbered_from_alex`). `bids_try` assigns BidderID=44 to the Executed event; `bids_pipeline` assigns BidderID=24. Both AI pipelines correctly avoid the duplication.
- **Top three divergences:**
  1. **NDA atomization vs aggregation (§E2.b).** Alex: 1 row for "16 financial bidders"; both AI sources atomize into 16 placeholder rows. This is the judgment-call axis §E2.b now codifies and is **AI-correct per the current rulebook** (filing gives a numeric count of 16 → §E2.b orders atomization, one row per signer). Alex's reference is stale on this axis. +16 rows each for AI vs Alex.
  2. **Synthetic drop rows for the 16 placeholders (bids_pipeline only).** `bids_pipeline` emits 16 `Drop` rows on 2013-07-25 for `bidder_1..bidder_16` with generic `comments_1="Did not advance after the preliminary indication stage."` and **no source_quote** — this violates §R2 evidence-specificity (the filing does NOT narrate 16 specific drops on 07/25; the narration is generic: the Special Committee "staged disclosure" only to the four advanced bidders and the rest simply don't reappear). Alex collapses this into a single aggregate `Drop` row; `bids_try` correctly emits no catch-all drops (`§I1` NDA-only rule after the iter-7 Providence decision). **AI correct = bids_try; bids_pipeline wrong.** +16 rows for bids_pipeline that shouldn't exist.
  3. **Initial IB retention + `Bid Press Release` + separate `Executed` row (bids_try adds that Alex omits).** `bids_try` emits 4-row IB trajectory (BofA hired 2012-10-23 for 2011-2012 discussions → terminated 2013-05-15 → re-hired 2013-05-31) whereas Alex collapses the first retention into a 2013-04-05 IB row. `bids_try` also emits a `Bid Press Release` for the 2013-10-15 joint announcement that Alex omits (but which §C1 explicitly lists as vocabulary — Alex's reference is undercovering announcement events). `bids_try` emits the `Executed` on 2013-10-14 as a bidder-side `CSC/Pamplona` row AND has a 2013-09-21 formal $21.25 bid row preceding it — matches §E2.a (one Executed row per deal).

---

## Filing event timeline (ground truth — all page cites from `raw.md`)

Page numbers below are the filing's printed page (Background of the Merger = pp. 27-41 in the PDF, corresponding to `<!-- PAGE 34 -->` through `<!-- PAGE 48 -->` in the markdown).

| # | Date | Event | Filing page | Notes |
|---|---|---|---|---|
| 1 | 2012-10-23 | Mac-Gray engages BofA Merrill Lynch for **2011-2012 Discussions** (contemplating acquiring CSC) | 33 | Pre-current-process IB engagement; `process_phase = 0` candidate |
| 2 | 2013-04-05 | Board meeting: authorizes BofA to explore transactional opportunities including with Party A | 33 | Target-side **sale-exploration authorization**; antecedes board-level `Target Sale` resolution |
| 3 | 2013-04-08 | BofA contacts Party A; Party A "might consider a business combination" | 33 | `Target Interest` per §D1's Mac-Gray carve-out (not yet a committed sale) |
| 4 | 2013-05-09 | Board meeting: reviews strategic alternatives with BofA; forms Transaction Committee | 33-34 | Deliberation only, not an event row (no §C1 code fits) |
| 5 | 2013-05-15 | **IB Terminated:** Mac-Gray terminates BofA's 2011-2012 engagement letter | 35 | **BANKER TERMINATION** (first flagged archetype event) |
| 6 | 2013-05-22 | Transaction Committee evaluates BofA presentation | 35 | Deliberation only |
| 7 | 2013-05-29 | Two other IB candidates present to Transaction Committee | 35 | Competing IB pitch; role="advisor_financial" candidates |
| 8 | 2013-05-30 | Board approves re-engagement of BofA | 35 | Authorization event |
| 9 | 2013-05-31 | **IB re-hired:** Mac-Gray signs new engagement letter with BofA for current sale process | 36 | **BANKER RE-HIRE** (second flagged archetype event) |
| 10 | 2013-06-21 | **Party A submits unsolicited $17.00-$19.00 all-cash proposal** | 36 | §D1 `Bidder Sale` + §H1 range bid; NDA signed only 08/05 so §C4 `pre_nda_informal_bid` applies |
| 11 | 2013-06-24 | Special Committee forms; authorizes contact with 50 parties (15 strategic + 35 financial) | 36-38 | §K2 inferred `Final Round Inf Ann` — staged process begins |
| 12 | 2013-06-24 to 2013-07-15ish | **20 confidentiality agreements signed over ~2 months** (2 strategic + 18 financial; Party B and Party C among the 18) | 38 | §E2.b: filing commits to count 18 financial → if Alex's 2 are pulled out, 16 anon-placeholder financial NDAs |
| 13 | 2013-06-28 | Party B signs NDA | 38 | |
| 14 | 2013-06-30 | Party C signs NDA | 38 | |
| 15 | 2013-07-11 | **CSC/Pamplona signs NDA** (joint / consortium — CSC + Pamplona PE owner) | 38 | §E2.b aggregated row; one of the 2 strategic |
| 16 | 2013-07-23 | **CSC/Pamplona preliminary IOI: $18.50/share all-cash** | 39 | §C3 `Bid` `informal`; point value |
| 17 | 2013-07-24 | **Party B preliminary IOI: $17.00-$18.00/share all-cash** (written) | 39 | §C3 `Bid` `informal`; range |
| 18 | 2013-07-24 | **Party C preliminary IOI: $15.00-$17.00/share all-cash (oral)** | 39 | `Bid` `informal`; range; `oral_bid` info flag |
| 19 | 2013-07-25 | Special Committee reviews IOIs; **the 16 unnamed financials implicitly drop out** (not advanced to management meetings) | 39-40 | §I1 ambiguous: filing says SC selected the four for management meetings, implying others are `DropBelowInf`; but not bidder-specifically narrated — §R2 evidence concern |
| 20 | 2013-07-25 | **Party C written IOI $16.00-$16.50** (written follow-up to 07/24 oral) | 40 | `Bid` `informal`; range; §H5 revision |
| 21 | 2013-07-25 | **Final Round Inf Ext Ann** — SC announces staged second-round process for 4 advanced bidders | 40 | Alex encodes as `Final Round Inf Ext Ann`; `bids_try` encodes as `Final Round Inf Ann` / final-round-inferred |
| 22 | 2013-08-05 | **Party A signs NDA** (after NDA-terms negotiation from 07/27) | 40 | Closes the §C4 `pre_nda_informal_bid` loop — NDA exists later in same phase |
| 23 | 2013-08-06 to 2013-08-14 | Management presentations for Party B, C, CSC/Pamplona, Party A | 40 | Deliberation / due diligence, no event row |
| 24 | 2013-08-27 | BofA sends revised-proposal process letter to the four; deadline 2013-09-09 | 41 | §K2 inferred `Final Round Inf Ann`; bids_try captures this, Alex does not (collapses into the 07/25 announcement) |
| 25 | 2013-09-09 | **CSC/Pamplona revised IOI: $19.50/share all-cash, 100% Pamplona-funded, 2-wk exclusivity request** | 41 | `Bid` `informal`; point value; `exclusivity_days=14` candidate |
| 26 | 2013-09-09 | **Party B revised IOI: $18.50/share all-cash, no firm financing** | 41 | `Bid` `informal`; point value |
| 27 | 2013-09-10 | **Party A revised IOI: $18.00-$19.00 all-cash range** | 41 | `Bid` `informal`; range |
| 28 | 2013-09-10 | **Party C revised oral IOI: $16.00-$17.00 all-cash** | 41 | `Bid` `informal`; range |
| 29 | 2013-09-11 | SC instructs BofA: final IOIs due 2013-09-18 | 42 | `Final Round Ann` (§K2 inferred → formal, since "exclusive negotiations with one of the bidders" + final) |
| 30 | 2013-09-18 | **CSC/Pamplona final: $20.75/share all-cash, exclusivity** | 42 | `Bid` `formal`; point value |
| 31 | 2013-09-18 | **Party A reiterates $18.00-$19.00 "best and final"** (telephone, no new submission) | 42 | `Bid` `formal` per §G1 "best and final" trigger; range + formal trigger → §G1 soft flag `range_with_formal_trigger` |
| 32 | 2013-09-18 | **Party B final: $19.00 cash + $2.50 options = $21.50 total** (valued by Party B) | 42 | **HIGHEST NOMINAL FORMAL BID**; §H2 composite — `cash_per_share=19`, `contingent_per_share=2.5`; `all_cash=false` for this row |
| 33 | 2013-09-18 | **Party C does NOT submit** (no revised indication, no reiteration, no stated reason) | 42 | §I1 `DropAtInf` (voluntary; "did not submit") |
| 34 | 2013-09-19 | **SC adjudicates 3 revised proposals: selects CSC/Pamplona for exclusivity at $20.75; authorizes asking for $21.25; Party B's $21.50 dropped due to options uncertainty + financing risk** | 42-43 | **TARGET-DROPS-HIGHEST-FORMAL-BID** archetype event. Drops Party A and Party B = `DropTarget`. Per §I1 voluntary-vs-target agency, the narration clearly shows target rejection ("concluded CSC/Pamplona had the potential of delivering the most value... provided greater certainty and involved less potential risk than the other indications") → `DropTarget` for Party A and Party B |
| 35 | 2013-09-21 | **CSC/Pamplona raises to $21.25/share all-cash; target accepts exclusivity** | 43 | `Bid` `formal` per §G1 "last and best" trigger; 2-wk exclusivity |
| 36 | 2013-09-24 | Exclusivity agreement executed (CSC, Pamplona, Mac-Gray) | 43 | `exclusivity_days=18` attribute on the $21.25 Bid row (through 10/12); not a separate event under §O1 |
| 37 | 2013-09-25 to 2013-10-14 | Merger-agreement negotiations: reverse termination fee $15M, target termination fee settles at $11M, $50M Pamplona liability cap | 43-47 | Pre-signing deal-level fields: `reverse_termination_fee=15000000`, `termination_fee=11000000`, `termination_fee_pct=3.2%` |
| 38 | 2013-10-14 | **Merger agreement executed**; Pamplona commitment letter delivered; Moab + MacDonald voting agreements effective | 47 | `Executed` — §E2.a one-row-only rule; `bidder_alias="CSC/Pamplona"`, `joint_bidder_members=["CSC", "Pamplona"]` |
| 39 | 2013-10-15 | **Joint press release** by Mac-Gray and CSC before U.S. markets open | 47 | `Bid Press Release` per §C1 |

**Key archetype-specific events (re the task flags):**
- **Banker termination:** 2013-05-15 (row 5 in table) — `IB Terminated`, bidder_name="BofA Merrill Lynch".
- **Banker re-hire:** 2013-05-31 (row 9) — new `IB` row, same canonical ID as the prior BofA row per §E3 (same legal entity).
- **Target drops highest formal bid:** 2013-09-18/19 (row 34) — Party B's nominal $21.50 is dropped in favor of CSC/Pamplona's $20.75 → $21.25. This is correctly captured by **all three** sources as a `DropTarget` for Party B on 2013-09-24 (Alex) or 2013-09-19 (bids_try).
- **Acquirer-naming complication:** Filing calls the counterparty "CSC ServiceWorks, Inc." on its cover and in the precedent transactions table (p. 47). The body of the Background section uses "CSC/Pamplona" throughout to denote the consortium of CSC + its PE owner Pamplona. Alex's workbook acquirer field uses both "CSC SERVICEWORKS, INC." and the free-text "CSC purchased by Pamplona in May/2013" inconsistently; the reference JSON surfaces the latter at deal-level.

---

## Source-by-source row counts and structure

### Alex (34 rows; slice of xlsx 6927-6960)

| Category | Count | Notes |
|---|---|---|
| `IB` (initial retention) | 1 (2013-04-05) | Compresses the 2012-10-23 + 2013-05-31 re-engagement into one row with comment "Sale process discussed since May 9; BofA offered some valuations on May 30 before being reengaged as IB" |
| `IB Terminated` | 1 (2013-05-15) | |
| `IB` (re-engagement) | 1 (2013-05-31) | |
| `Target Interest` | 1 (2013-04-08) | Party A |
| `Bidder Sale` | 1 (2013-06-21) | Party A |
| `Bid` informal (bid rows) | 9 | Party A 6/21 ($17-19), CSC/Pamplona 7/23 ($18.5), Party B 7/24 ($17-18), Party C 7/24 ($15-17), Party C 7/25 ($16-16.5), CSC/P 9/9 ($19.5), Party B 9/9 ($18.5), Party A 9/10 ($18-19), Party C 9/10 ($16-17) |
| `Bid` formal | 4 | CSC/P 9/18 ($20.75), Party A 9/18 ($18-19), Party B 9/18 ($21.5), CSC/P 9/21 ($21.25) |
| `NDA` | 5 | Party C 6/20 [**date wrong? filing says 6/30**], 16 financial bidders (aggregate, 7/15), Party B 6/28, CSC/P 7/11, Party A 8/5 |
| `Drop` | 1 (2013-07-25) | **Aggregated** for the 16 financial bidders |
| `DropTarget` | 2 (2013-09-24) | Party A, Party B |
| `Drop` (Party C not submitting) | 1 (2013-09-18) | Coded as `Drop` not `DropAtInf` |
| `Final Round Inf Ann` | 1 (2013-06-24) | |
| `Final Round Inf` | 1 (2013-07-23) | |
| `Final Round Inf Ext Ann` | 1 (2013-07-25) | |
| `Final Round Inf Ext` | 1 (2013-09-09) | |
| `Final Round Ann` | 1 (2013-09-11) | |
| `Final Round` | 1 (2013-09-18) | |
| `Executed` | 1 (2013-10-14, xlsx row 6960 flagged) | Alex's original BidderID=21 duplicates row 6957; reference JSON renumbers to 32 |
| **Total** | **34** | No `Bid Press Release`; one aggregate 16-financial row for NDA and for Drop |

Alex's unique bidders: `Party A` (strategic), `Party B` (financial), `Party C` (financial), `CSC/Pamplona` (strategic — Alex treats as pure S, not mixed), `16 financial bidders` (aggregate placeholder), `BofA Merrill Lynch` (advisor).

**Note on Alex's Party C NDA date:** Alex's row 6936 has `bid_date_precise=2013-06-20` but `bid_date_rough=2013-06-30`. The filing (p. 38) clearly states **"On June 30, 2013, Party C entered into a confidentiality and standstill agreement"** — Alex's precise date appears to be a typo (6/20 vs 6/30). Both AI sources correctly use 2013-06-30.

### bids_try (45 rows)

| Category | Count | Notes |
|---|---|---|
| `IB` | 2 (2012-10-23, 2013-05-31) | First narrates 2011-2012 engagement explicitly; §J1 retention-action rule applied |
| `IB Terminated` | 1 (2013-05-15) | |
| `Target Sale` | 1 (2013-04-05) | Board authorizes BofA to explore — coded as `Target Sale` rather than Alex's implicit "IB only" |
| `Target Interest` | 1 (2013-04-08) | Party A |
| `Bid` informal | 1 (Party A 2013-06-21) + 9 others = 10 total | Including `pre_nda_informal_bid` flag on the 6/21 Party A row per §C4 |
| `Bid` formal | 3 (CSC/P 9/18, Party A 9/18, CSC/P 9/21) + 1 "formal-trigger" Party A range = 4 | Party B 9/18 $21.5 is emitted as `informal` in bids_try (because composite/contingent options cost Party B the formal classification) |
| `NDA` | 20 (Party B, Party C, CSC/P, 16 unnamed `Financial 1..16`, Party A) | §E2.b atomization of 16 unnamed; midpoint date 2013-07-24 with date-inferred-from-context flag |
| `DropAtInf` | 1 (Party C 2013-09-18) | Per §I1 voluntary (no submission = voluntary self-withdrawal at informal stage) |
| `DropTarget` | 2 (Party A, Party B — 2013-09-19) | Day after the 9/18 deadline, matches the SC's 9/19 adjudication meeting |
| `Final Round Inf Ann` | 2 (2013-08-27, 2013-09-11) — first is process-letter, second is final-IOI call | |
| `Executed` | 1 (2013-10-14) | CSC/Pamplona, joint_nda_aggregated aliases for consortium |
| `Bid Press Release` | 1 (2013-10-15) | Joint announcement |
| **Total** | **45** | |

bids_try unique bidders: `Party A`, `Party B`, `Party C`, `CSC/Pamplona` (mixed base), `Financial 1..16` (placeholders), `BofA Merrill Lynch`. Adds structured flags and inference notes on every bid row. **Every row carries `source_quote` and `source_page`.**

### bids_pipeline (65 rows)

| Category | Count | Notes |
|---|---|---|
| `IB` | 3 (2013-04-05, 2013-05-31, and another implicit) | |
| `IB Terminated` | 1 (2013-05-15) | |
| `Target Interest` | 2 (Party A 2013-04-08, CSC/Pamplona 2013-06-28) | **Extra Target Interest for CSC/Pamplona on 06/28** with Pamplona expressing interest in a transaction — is this correct? Filing language says "Pamplona emphasized that business and legal due diligence would be minimal given its familiarity with Mac-Gray..." — reads as target-initiated discovery by BofA, not bidder initiation. Dubious classification. |
| `Bidder Sale` | 1 (Party A 2013-06-21) | Separate row from the $17-19 bid row on same date |
| `Bid` informal | 10 | Mirrors Alex's bid set + extras |
| `Bid` formal | 4 | CSC/P 9/18 $20.75, Party A 9/18 $18-19, Party B 9/18 $21.5, CSC/P 9/21 $21.25 |
| `NDA` | 20 (Party B, Party C, CSC/P, Party A, and 16 `bidder_1..bidder_16`) | §E2.b atomization; 16 placeholders dated 2013-07-15 (a guess — filing says "over the next two months" after 6/24) |
| **`Drop` rows** | **17** (16 for placeholders 2013-07-25 + 1 for Party C 9/18) | **The 16 placeholder drops are the single biggest error: generic `comments_1="Did not advance after the preliminary indication stage."` with no source_quote, no bidder-specific narration** |
| `DropTarget` | 2 (Party A 9/24, Party B 9/24) | Same as Alex |
| `Final Round Inf Ann` | 1 (2013-06-24) | |
| `Final Round Inf` | 1 (2013-07-23) | |
| `Final Round Ext Ann` | 1 (2013-07-25) | Differs from Alex's `Final Round Inf Ext Ann` — coded as non-informal Ext (§K1 matrix wrong suffix) |
| `Final Round Ext` | 1 (2013-09-09) | |
| `Final Round Ann` | 1 (2013-09-11) | |
| `Final Round` | 1 (2013-09-18) | |
| `Executed` | 1 (2013-10-14) | |
| **Total** | **65** | **No `source_quote` / `source_page` columns in CSV at all.** |

bids_pipeline uses decimal-wedge BidderIDs (0.5, 0.7, 0.8, ..., 2.058823..., 9.029411...). This is a leftover of Alex's old xlsx convention — not §E2 compliant. Per §E2 as amended 2026-04-19, "`BidderID` is an **event-sequence number, not a bidder-identity number**"; decimals are Alex's legacy wedges and should be renumbered to strict 1..N per `pipeline._canonicalize_order()`. bids_pipeline appears to output the pre-renumber BidderID values.

---

## Divergence table (selected — not exhaustive)

Verdict codes: `AlexRight` · `BPRight` (bids_pipeline) · `TryRight` · `BothAIRight` · `NoneRight` · `JudgmentCall` · `AlexFlagged` (known alex_flagged_rows.json entry)

| # | Event date | Event / field | Alex | bids_try | bids_pipeline | Filing says | Verdict | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | 2013-04-05 | Initial start-of-process row | `IB` (BofA retention) | `Target Sale` on 4/5 + `IB` on 5/31 (explicit re-engagement) | `IB` on 4/5 | "at an in-person meeting of the Board on April 5, 2013, the Board... authorized Mac-Gray management to work with BofA Merrill Lynch to explore transactional opportunities" — 4/5 is a **board authorization of the EXPLORATION process**, not an IB retention; IB retention for current process happens 5/31 | **TryRight** | bids_try correctly separates target-side authorization from advisor retention; §D1 `Target Sale` fits the board-resolution semantics |
| 2 | 2012-10-23 | BofA first retention | (not present; 4/5 IB subsumes) | `IB` on 2012-10-23 with `process_phase=null`, comment "2011-2012 Discussions engagement" | (not present) | "Mac-Gray engaged BofA Merrill Lynch on October 23, 2012" (p. 33) | **TryRight** | This is a §L1 prior-process event; §L2 `process_phase=0` would be most correct but bids_try leaves `process_phase=null`. Still, capturing it is right (§L1 inclusion rule). Alex and bids_pipeline both miss it. |
| 3 | 2013-04-08 | Party A first contact | `Target Interest` | `Target Interest` | `Target Interest` | "representatives of BofA Merrill Lynch, as instructed by the Board, telephoned a representative of Party A to discuss generally a possible business combination" — target-initiated; Party A "might consider" | **BothAIRight & AlexRight** | All three agree. `Target Interest` is the Mac-Gray-specific §D1 carve-out. |
| 4 | 2013-06-21 | Party A first proposal ($17-19) | `Bidder Sale` + separate Inf bid row (2 rows, same date) | `Bid` `informal` row only, with `pre_nda_informal_bid` flag per §C4 | `Bidder Sale` + separate `Bid` `informal` row (mirrors Alex) | "Party A submitted an unsolicited proposal... offering to purchase Mac-Gray for an all-cash purchase price of $17.00 to $19.00 per share" | **TryRight** per current rulebook | §D1.a (unsolicited-first-contact exemption) says when an unsolicited bid IS the first concrete sale proposal and the bidder later signs an NDA, **emit the Bid only** (not a separate `Bidder Sale` row). Wait — §D1.a carves out the case with **no later NDA**; §C4 covers **later NDA exists** (Party A signs NDA 8/5). §C4 says emit the `Bid` with `pre_nda_informal_bid` info flag. bids_try's single-bid-row with §C4 flag is the cleanest rulebook-compliant interpretation. Alex's two-row (`Bidder Sale` + `Bid`) is the legacy pre-§C4 pattern. bids_pipeline mirrors Alex. **Current rules prefer bids_try.** |
| 5 | 2013-06-20/30 | Party C NDA | `bid_date_precise=2013-06-20`, `bid_date_rough=2013-06-30` | 2013-06-30 | 2013-06-30 | Filing p. 38: "On June 30, 2013, Party C entered into a confidentiality and standstill agreement" | **BothAIRight** | Alex's 6/20 appears to be a typo/transcription error. AlexFlagged candidate (but not in alex_flagged_rows.json). Recommend Austin file a new flag or fix reference JSON. |
| 6 | 2013-06-24 to 2013-07-15ish | 20 NDAs over two months (incl. 16 unnamed financials) | 1 aggregate row "16 financial bidders" 2013-07-15 | 16 placeholder rows (`Financial 1..16`) dated 2013-07-24 with date-inferred flag | 16 placeholder rows (`bidder_1..bidder_16`) dated 2013-07-15 | "Over the next two months a total of 20 potential bidders, including two strategic bidders (Party A and CSC/Pamplona) and 18 financial bidders (including Party B and Party C), entered into confidentiality agreements" (p. 38) | **JudgmentCall / BothAIRight per §E2.b** | §E2.b says when the filing commits to a numeric count, emit N rows. 18-2 named = 16 unnamed financials → atomization is rulebook-compliant. Alex's aggregate row is legacy behavior. **Both AI pipelines atomize correctly** per current rulebook; Alex's reference JSON is stale. |
| 7 | 2013-07-11 | CSC/Pamplona NDA | `bidder_type=S` (strategic) | `bidder_type.base=mixed`, `bidder_type_mixed=1` | `bidder_type.base=mixed`, `bidder_type_mixed=1` | "CSC/Pamplona" is a consortium of CSC (operating company strategic) + Pamplona (PE firm financial); filing p. 38 describes Pamplona's interest "including an acquisition of Mac-Gray by its portfolio company, CSC" | **JudgmentCall** | §F2 rule 5: "Consortium explicitly described as including **both** PE and strategic members" → `base="mixed"`. CSC is the strategic operator, Pamplona is the PE sponsor. **Both AI pipelines correctly apply §F2/§F3 via §F1 mixed base.** Alex's pure-S is a legacy simplification. **BothAIRight per current rulebook.** |
| 8 | 2013-07-25 | 16 financial bidders dropping out | 1 aggregate `Drop` row | **no catch-all Drop row** | 16 generic `Drop` rows with no source_quote | Filing p. 39-40 narrates: "the Special Committee concluded that it would be advisable to stage the disclosure of such information to each of the bidders to the extent that a bidder's indication of interest and other actions demonstrated its seriousness" — i.e., the SC advances only the 4 named, and the other 16 implicitly fall away; **filing does NOT narrate 16 specific drop events** | **TryRight** | Per §I1 NDA-only-rows clause (finalized iter-7), "Do **not** fabricate a catch-all `Drop` row with a generic shared `source_quote`." bids_try correctly leaves 16 NDA rows as `nda_without_bid_or_drop` soft flags. bids_pipeline fabricates 16 drops (the Providence iter-7 failure mode repeating). Alex's aggregate Drop predates the §I1 rule and is a stale legacy pattern. |
| 9 | 2013-07-25 | Staged second-round announcement | `Final Round Inf Ext Ann` | `Final Round Inf Ann` (treats 8/27 process letter as the announcement) | `Final Round Ext Ann` (no `Inf` suffix — wrong matrix entry) | Filing p. 40: SC authorizes "staged disclosure" and requests revised IOIs from 4 bidders | **JudgmentCall/AlexRight** | §K1 matrix: `Final Round Inf Ext Ann` = informal + extension + announcement. Alex's code is the tightest match (still in informal round, extended window). bids_pipeline's `Final Round Ext Ann` drops the `Inf` — **bids_pipeline wrong on suffix grammar.** bids_try collapses the two announcements into one `Final Round Inf Ann` at 8/27 — plausible but loses the 7/25 event. |
| 10 | 2013-09-18 | Party B final $19 cash + $2.5 options = $21.50 | `Bid` `formal`, `bid_value=21.5`, `bid_value_pershare=21.5`, `all_cash=0`, comment "19 in cash, rest in options/earnouts (2.5 is the bidder's valuation of these)" | `Bid` `informal` (!), `bid_value_pershare=21.5`, flag `contingent_type_ambiguous` classifies options as `cvr` | `Bid` `formal`, `bid_value_pershare=21.5`, comment "$19.00 cash at closing plus options valued by Party B at $2.50 per share" | "Party B valued at $21.50 per share, including $19.00 of cash to be paid at closing and the remaining per share price to be paid in the form of options" (p. 42) | **AlexRight + BPRight** | This is in response to the 8/27 process letter ("submit revised written proposals" + final-round solicitation) → §G1 process-position → `formal`. bids_try classifies as `informal` citing "contingent options component renders this non-definitive" — but §G1 says if bid is in response to process letter or final-round invitation, default is formal unless an informal trigger fires. Contingent consideration alone is not an informal trigger per §G1; §H2 allows composite/contingent for formal bids. **bids_try miscategorizes; both Alex and bids_pipeline correct.** |
| 11 | 2013-09-18 | Party C does not submit | `Drop` on 9/18 | `DropAtInf` on 9/18 with `drop_agency_ambiguous` flag | `Drop` on 9/18 | "Party C did not submit a revised indication of interest or reiterate its prior indication" (p. 42) | **JudgmentCall/TryRight** | §I1 requires agency-ambiguity flag when unclear. "Did not submit" is passive — voluntary self-withdrawal (`DropAtInf`) is the cleaner per-§I1 call (bidder failed to act at informal stage). bids_try's `DropAtInf + drop_agency_ambiguous` is the most rulebook-faithful. Alex's generic `Drop` is acceptable but less specific. |
| 12 | 2013-09-19 | Target rejects Party A ($18-19 "best and final") and Party B ($21.50 with options) | `DropTarget` on 2013-09-24 | `DropTarget` on 2013-09-19 | `DropTarget` on 2013-09-24 | SC meets 9/19 and concludes CSC/P proposal is best; exclusivity entered 9/24 but target-rejection decision is 9/19 | **JudgmentCall/TryRight** | Filing p. 43: "Following a discussion, the Special Committee concluded that the revised indication of interest submitted by CSC/Pamplona had the potential of delivering the most value to stockholders, provided greater certainty and involved less potential risk than the other indications." — this IS the rejection moment, 9/19. The 9/24 date is the exclusivity-agreement execution, not the rejection. **bids_try gets the date right**; Alex and bids_pipeline use the later exclusivity-execution date. |
| 13 | 2013-10-14 | Executed row | Alex original BidderID=21 (Alex-flagged as duplicate of row 6957); reference JSON renumbered to 32; `bidder_alias="CSC/Pamplona"` | `CSC/Pamplona`, BidderID=44, `bid_value_pershare=21.25` (carries price on executed row) | `CSC/Pamplona`, BidderID=24, `bid_value_pershare=NA` | "the merger agreement was executed" (p. 47) | **AlexFlagged (row 6960) + BothAIRight** | Both AI sources correctly avoid the Alex duplicate-BidderID error. Whether to repeat the price on the Executed row is a schema-policy choice not a correctness question — bids_try's approach shows it; bids_pipeline's approach doesn't. |
| 14 | 2013-10-15 | Joint press release | (not emitted) | `Bid Press Release` | (not emitted) | "Mac-Gray and CSC jointly announced the execution of the merger agreement" (p. 47) | **TryRight** | §C1 explicitly lists `Bid Press Release` / `Sale Press Release` as vocabulary. Filing clearly narrates it. Both Alex and bids_pipeline omit. |
| 15 | Acquirer field | `"CSC SERVICEWORKS, INC."` (most rows) / `"CSC purchased by Pamplona in May/2013"` (some rows) / Reference JSON `"CSC purchased by Pamplona in May/2013"` | `"CSC ServiceWorks, Inc."` (filing-verbatim case) | `"CSC SERVICEWORKS, INC."` (upper-case) | Filing cover + precedent-transactions table (p. 47): "CSC ServiceWorks, Inc." | **TryRight** (best casing) | bids_pipeline has the right entity, wrong casing. Alex's inconsistency across rows + wrong reference JSON acquirer is an xlsx-provenance artifact. **Recommend reference JSON fix.** |

---

## Systemic findings

### 1. NDA atomization-vs-aggregation (§E2.b)

This is the single biggest driver of the row-count split. Filing commits to a numeric count ("18 financial bidders including Party B and Party C" = 16 unnamed). Per §E2.b Case 2 ("Numeric count OR named individual signers"), this is an atomization case: 16 rows, one per signer, placeholder names per §E3.

- Alex's reference: 1 aggregate row → **stale vs current §E2.b**.
- bids_try: 16 atomized rows with placeholder names `Financial 1..Financial 16`, date-inferred flag → **rulebook-compliant**.
- bids_pipeline: 16 atomized rows with placeholder names `bidder_1..bidder_16` (lowercase, non-placeholder-style — doesn't follow §E3's `Strategic k` / `Financial k` convention but close enough in spirit) → **rulebook-compliant on atomization but wrong placeholder-name convention.**

**Action for Austin:** Same adjudication call as zep / mac-gray / providence / petsmart per CLAUDE.md "Immediate open questions" (2): either regenerate Alex's reference to atomize, or loosen §E2.b back to an aggregation default for Mac-Gray-style narrative granularity.

### 2. Banker termination/re-hire (§J1)

All three sources capture the `IB Terminated` (2013-05-15) and `IB` re-hire (2013-05-31) correctly. The only difference is whether to also include the 2012-10-23 prior-engagement retention — bids_try does (§L1 prior-process inclusion rule); Alex and bids_pipeline don't. **TryRight**.

### 3. Acquirer naming

Filing-verbatim is "CSC ServiceWorks, Inc." (capitalized as in the Form cover; uppercase elsewhere in the xlsx-processing era). bids_try matches; bids_pipeline is close (uppercase variant); Alex's reference JSON uses a free-text provenance note ("CSC purchased by Pamplona in May/2013") as the Acquirer field, which is wrong for a machine-readable dataset. **Recommend fix:** `build_reference.py` should prefer the filing-verbatim counterparty name and relegate provenance commentary to `deal_flags[].reason`.

### 4. Dates

Alex has a transcription error on Party C NDA (6/20 vs filing's 6/30). Both AI sources use 6/30. Recommend filing this as an **AI-identified correction** in alex_flagged_rows.json.

No other date divergences that matter. The 2013-09-19 vs 2013-09-24 `DropTarget` date is the only "semantic" date question — TryRight per the filing's narration that the SC decided on 9/19.

### 5. Source-quote presence (§R2)

- **bids_try: 100%** — every row has `source_page` and `source_quote`.
- **bids_pipeline: 0%** — CSV has no `source_page` or `source_quote` columns at all. The 16 synthetic Drop rows are the most egregious consequence: no evidence for rows the filing doesn't narrate.
- **Alex: 0%** — per schema convention (reference JSONs omit evidence fields). Acceptable for reference but means Alex's aggregate Drop row also lacks per-bidder evidence.

This is the single largest gap between pipelines. bids_pipeline is failing the §R2 non-negotiable ("no un-cited rows ship"). bids_try passes it cleanly.

### 6. `Bid` `formal` classification for Party B 9/18 composite-contingent bid

bids_try's `informal` classification for Party B 9/18 ($19 cash + $2.50 options = $21.50) is the only clear AI-wrong/Alex-right verdict in the set. Per §G1, process-position (in response to process-letter final-round invite) default is `formal`; contingent consideration alone (§H2) is not an informal trigger. bids_try's inference note rationalizes informal on "contingent options component renders this non-definitive" — but that reasoning isn't in §G1.

**Action:** file this as a §G1 interpretation clarification in a future rulebook pass, or treat as a bids_try classification error for Austin's manual verdict.

### 7. Structural bonus: bids_try captures `Bid Press Release` for 2013-10-15

This is a §C1 vocabulary event that Alex omits. Not an error in Alex's workbook (press releases aren't always emitted), but a **data-completeness win** for bids_try.

---

## Specific rule / prompt fixes suggested

1. **§G1 clarification** — add explicit language that **composite / contingent consideration alone is not an informal trigger**. Current §G1 informal triggers list "subject to due diligence (without financing commitments)" and the range structural signal. Extend with a line: *"Non-cash components (§H2) — options, earnouts, CVRs — do not by themselves downgrade a process-letter-response bid to informal; §G1's formal triggers (process-letter invitation, 'best and final' language) take precedence."* This would prevent bids_try's Party B 9/18 miscategorization.

2. **§E2.b reconfirmation** — Austin's NDA atomization-vs-aggregation pending decision (CLAUDE.md "Immediate open questions" #2) applies here. Mac-Gray's filing gives an exact count (18 financial, minus 2 named = 16) which is the cleanest "atomize per §E2.b" case. Confirming atomization means regenerating Alex's reference; confirming aggregation means tightening §E2.b's "numeric count" trigger.

3. **bids_pipeline §I1 fix** — the 16 placeholder `Drop` rows on 2013-07-25 violate §I1's "Do **not** fabricate a catch-all `Drop` row with a generic shared `source_quote`" rule. bids_pipeline needs the iter-7 Providence rule applied: NDA-only rows should stay as NDA-only with `nda_without_bid_or_drop` soft flags, not synthetic drops.

4. **bids_pipeline evidence fix** — bids_pipeline needs `source_page` and `source_quote` columns added. Without them the pipeline is failing the §R2 / SKILL.md non-negotiable.

5. **`build_reference.py` acquirer-name fix** — prefer filing-verbatim counterparty name over Alex's legacy xlsx commentary string. Mac-Gray's deal-level Acquirer should be `"CSC ServiceWorks, Inc."` not `"CSC purchased by Pamplona in May/2013"`.

6. **`build_reference.py` Party C NDA date fix** — file a new `alex_flagged_rows.json` entry for xlsx row 6936 (Party C NDA `bid_date_precise=2013-06-20` contradicts filing's 2013-06-30), and correct the reference JSON. Or add §Q6 to the build_reference.py docstring.

7. **`bids_pipeline` BidderID §E2 fix** — decimal-wedge BidderIDs (0.5, 0.7, 0.8, 2.058823..., 9.029411...) should be renumbered to strict 1..N per `pipeline._canonicalize_order()` / §E2 as amended 2026-04-19. bids_try correctly uses 1..N.

8. **§D1/§C4 interpretation for Party A 6/21** — Alex's 2-row (`Bidder Sale` + `Bid`) and bids_try's 1-row (`Bid` + `pre_nda_informal_bid` flag) differ on same-date `Bidder Sale` → `Bid` splitting. Per §D1.a's interaction with §C4, the 1-row form is preferred because §D1.a says "emit the `Bid` row only; do NOT emit a duplicate standalone `Bidder Sale` row" for unsolicited-first-contact. bids_pipeline's 2-row form and Alex's 2-row form are both legacy. Depending on Austin's call, regenerating Alex's reference JSON for Mac-Gray could collapse these.

---

## Open questions for Austin

1. **§E2.b for Mac-Gray 16 financials:** atomize (regenerate Alex) or aggregate (tighten §E2.b)? Same axis as zep/providence/petsmart.
2. **Party B $21.50 composite-contingent bid type:** formal (Alex + bids_pipeline) or informal (bids_try)? Rulebook §G1 should be clarified either way.
3. **Same-date `Bidder Sale` + `Bid` vs single `Bid` with `pre_nda_informal_bid` flag (Party A 6/21):** which convention is canonical for unsolicited-first-contact bids that later sign NDAs? §D1.a and §C4 both exist; §D1.a's language ("emit the `Bid` row only") seems to apply even when NDA comes later — but §D1.a's header says it covers the case with no later NDA. Needs clarification.
4. **`DropTarget` date for Party A / Party B: 2013-09-19 (SC decision) or 2013-09-24 (exclusivity-execution)?** Filing narrates decision on 9/19, exclusivity execution on 9/24. Ambiguous per §A/§B rules — pick a convention.
5. **Alex Party C NDA date typo:** confirm 6/20 → 6/30 in reference JSON + add alex_flagged entry?
6. **Reference JSON acquirer field:** fix `"CSC purchased by Pamplona in May/2013"` → `"CSC ServiceWorks, Inc."` at deal level, demote the commentary to `deal_flags[].reason`?
7. **Executed-row price field:** bids_try carries `bid_value_pershare=21.25` on the Executed row; Alex and bids_pipeline leave it null. Policy question — is this useful redundancy or noise?
8. **bids_pipeline production gate:** with no `source_quote` / `source_page` and a systemic §I1-violating 16-Drop pattern, bids_pipeline's Mac-Gray output is failing §R2. What's the remediation path — regenerate with the iter-7-rule-compliant extractor, or fix bids_pipeline's schema to match bids_try?

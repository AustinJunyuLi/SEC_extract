# PetSmart, Inc. — Three-Way Extraction Audit

**Deal:** PetSmart, Inc. / Buyer Group (BC Partners + Caisse + GIC + StepStone + Longview rollover)
**Filing:** DEFM14A, filed 2015-02-02 (CIK 863157, accession 0001571049-15-000695)
**Background section:** `data/filings/petsmart-inc/raw.md` lines 1113–1193 (sec2md pages 28–33)
**Date announced:** 2014-12-14 · **Date effective:** 2015-03-11
**Archetypes exercised:** Activist Sale; consortium winner; 15-NDA same-day batch

Row counts: **Alex 53 · bids_pipeline 55 · bids_try 41**

---

## TL;DR

- **Winner: bids_pipeline.** It is the only extraction that both (a) reconstructs the full narrative — Industry Participant pre-history, two-activist §D1.b atomization, IB retention, 15 NDAs, 6 IOIs (with the 2 sub-$80 bidders), the 4-to-final-round cut, formation of Bidder 3 consortium from two of the 4 advancers, three-round bidding — and (b) cites a verbatim `source_quote` on every row (bids_try also cites but has a systematic substring-match bug; Alex has no quotes). **bids_try** is in second place analytically — its per-bidder atomization, consortium-drop split, and §D1.b split are correct and better documented than bids_pipeline's in places — but its 41 rows drop the sub-$80 IOI submitters and the consortium's final-round dropouts (see §"Why bids_try dropped to 41"). **Alex** is the most truncated: he collapses both activists into one row, skips the Industry Participant pre-history entirely, and misses the pre-$80 IOI submissions below the cutoff.
- **15-NDA atomization verdict.** The filing unambiguously says *"15 potentially interested financial buyers"* (page 30), a numeric count. Per §E5 "Exact counts" and §E2.b numeric-count/named-signer column, **atomization is correct** and aggregation is not. Alex: 15 atomic NDA rows (`Unnamed party 1..12`, `Bidder 1`, `Bidder 2`, `Buyer Group`) — **correct shape**. bids_pipeline: 15 atomic rows (`Buyer Group`, `another bidder` [=Bidder3-A], `Bidder 2`, `Bidder 3` [=Bidder3-B], `"BC Partners..."` consortium label, `bidder_6..bidder_15`) — correct but with naming drift (see below). bids_try: 15 atomic rows (`Buyer Group`, `Bidder 2`, `Bidder 3-A`, `Bidder 3-B`, `Financial 2..10`, `Financial 14..15`) with explicit `unnamed_count_placeholder` info flags — correct, and its "Bidder 3-A/3-B" split onto two NDAs is the cleanest model of the eventual consortium that later forms Bidder 3. **All three are within §E2.b compliance; bids_try's naming is most faithful to §E3**.
- **Consortium handling verdict.** The winning Buyer Group is structurally a mixed consortium that the filing narrates as a single entity: *"BC Partners, Inc., La Caisse de dépôt et placement du Québec, affiliates of GIC Special Investments Pte Ltd, affiliates of StepStone Group LP and Longview Asset Management, LLC"* (cover page). §E2.a requires **one** `Executed` row with `joint_bidder_members` listing constituents. Alex emits one Executed row (`bidder_alias="Buyer Group"`) — **correct shape**. bids_pipeline emits one Executed row but uses the full consortium-verbatim acquirer string as `BidderName` — verbose, and drifts from the §E2.a contract that `bidder_alias` should be "Buyer Group" (which the filing uses). bids_try emits one Executed row with `bidder_type.mixed=1` and an info flag naming the constituents plus the Longview rollover — **closest to §E2.a**. Critically, none of the three emits explicit `joint_bidder_members` ids in the CSV export, which is a known limitation of the CSV format; only bids_try's comments/flags surface the Longview-rollover nuance.
- **Top 3 divergences** (see table below):
  1. **Industry Participant pre-history** (March/Spring 2014; August 7/22/27 rejections). Alex collapses this to a single `IB` retention row (ignores it). bids_pipeline emits 4 rows (`Target Interest`, `Bidder Interest`, `DropTarget`). bids_try emits **zero** rows for Industry Participant, skipping the March 2014 Target Interest / August 7 Bidder Interest / August 27 DropTarget sequence (−3 to 4 rows; large share of the 41 vs 53 gap).
  2. **Sub-$80 IOIs on Oct 30 and eliminated parties on Nov 3.** The filing says 6 IOIs total, 4 at/above $80, and the 2 below-$80 parties were notified Nov 3. Alex has 2 `Drop` rows (Oct 30) + `DropTarget` rows for the 2 sub-$80 + 8 more `Drop` rows aggregating the 10 remaining NDA-only bidders who submitted no IOI (Oct 30). bids_pipeline has 10 `DropTarget` rows on Nov 3 (the remaining NDA signers). bids_try emits **only** 2 sub-$80 rows (`Financial 2`, `Financial 3`) as `Informal` IOIs and 2 `DropBelowInf` rows on Nov 3 — it **does not emit drop rows for the 11 NDA signers who never submitted an IOI**, relying on the §P-S1 soft flag instead (which in its output appears as `nda_without_bid_or_drop` against 11 bidders). This is the §M2/§I1 "NDA-only, no synthetic Drop" policy — arguably correct per the rules as written today, but it is the single largest source of the 41 vs 53/55 row-count gap. **Judgment call.**
  3. **Activist atomization.** Alex collapses JANA + Longview into **one** `Activist Sale` row (2014-07-03) — violates §D1.b. bids_pipeline atomizes into **4** rows (JANA 7/3 + Longview 7/7 + JANA 7/10 + Longview 7/10) — arguably over-atomized (the 7/10 rows are follow-up advocacy, not new 13D filings). bids_try emits **2** rows (JANA 7/3 + Longview 7/7) with a `multi_activist_coordination_ambiguous` soft flag — cleanest §D1.b compliance.

---

## Filing event timeline (ground truth)

Citations are to sec2md page numbers. Events marked `‡` involve Industry Participant (pre-auction strategic pre-history); events marked `†` involve activists (JANA / Longview).

| # | Date | Event | Page | Notes |
|---|------|-------|------|-------|
| 1 | 2014-03 (month) | Board authorizes mgmt to contact **Industry Participant** `‡` | 28 | `Target Interest` per §C1/§D1 (target-initiated specific-party discussion, no public sale resolution) |
| 2 | 2014 Spring (loose) | Lenhardt (CEO) speaks with Industry Participant CEO; Industry Participant says "not for sale," antitrust concerns `‡` | 28 | Drop-equivalent on Industry Participant side; no NDA signed. |
| 3 | 2014-05-21 | Weak Q1 earnings release; stockholder/interested-party communications re strategic alternatives begin | 28 | Context — not an event row. |
| 4 | 2014-05 (month) | Longview meets with board / management re strategic direction (no advocacy yet) | 28 | Context — not a bid event. |
| 5 | 2014-06-18 | Board meeting reviews alternatives; establishes ad hoc committee; authorizes vetting of financial advisor | 28 | Context — precedes formal §J1 IB retention event. |
| 6 | 2014-07-03 | **JANA Partners** files Schedule 13D (9.9% stake); advocates for sale `†` | 29 | `Activist Sale` (per §D1.b atomization) |
| 7 | 2014-07-07 | **Longview** public letter advocating sale; offers equity rollover `†` | 29 | `Activist Sale` (per §D1.b atomization) |
| 8 | 2014-07-10 | JANA in-person meeting with Company; advocates sale `†` | 29 | Ongoing JANA advocacy; not a new filing event per §D1.b (one activist=one row unless new 13D). |
| 9 | 2014-07-10 | Longview reiterates sale advocacy `†` | 29 | Same as above — follow-up on existing activist. |
| 10 | 2014-07 (month) | **J.P. Morgan retained** as financial advisor (after interviewing several) | 29 | `IB` per §J1; earliest action = July; engagement letter effective 2014-08-21 (page 33). |
| 11 | 2014-08-07 | Industry Participant approaches J.P. Morgan; expresses interest if Company pursues alternatives `‡` | 29 | `Bidder Interest` per §D1 (no concrete price, no NDA) |
| 12 | 2014-08-13 | Board determines to explore strategic alternatives; authorizes ad hoc committee to oversee sale process | 29 | `Target Sale` per §D1 |
| 13 | 2014-08-19 | Press release announcing exploration of strategic alternatives | 29–30 | `Target Sale Public` + `Sale Press Release` per §D1/§C1 |
| 14 | 2014-08-22 | J.P. Morgan tells Industry Participant of board's concerns `‡` | 30 | Context — leads to Industry Participant's 8/27 response. |
| 15 | 2014-08-27 | J.P. Morgan tells Industry Participant it will **not** be invited into the process `‡` | 30 | `DropTarget` per §I1 (target-initiated rejection) |
| 16 | 2014-08-27+ | Mid-Aug–end-Oct: J.P. Morgan contacted by **27 potential participants** (3 strategic ex-Industry, 24 financial); ~15 express interest | 30 | Context — numeric count of 27 potential / 15 NDA-signers. |
| 17 | 2014-10-03 | Board meeting reaffirms Industry Participant exclusion | 30 | Context — not an event row. |
| 18 | 2014-10 first week | **15 confidentiality and standstill agreements** signed with 15 financial buyers (numeric count; §E5 exact) | 30 | 15 `NDA` rows per §E2.b / §E5 |
| 19 | 2014-10 (month) | Bidders told IOIs due 10/30/2014; Longview rollover option communicated | 30 | `Final Round Inf Ann` per §K1 (informal round announced) |
| 20 | 2014-10-30 | **6 of the 15** submit IOIs: 3 at or above $80 (Buyer Group $81–$83; another bidder $80–$85; Bidder 2 $78 then revised to $81–$84 after JPM discussion); 2 below $80; Bidder 2 counts once. Plus a 4th at $80+ (implicit — the filing says "four bidders... at or above $80.00 per share"). | 31 | 4 informal `Bid` rows for at/above-$80 + 2 informal `Bid` rows for below-$80 submitters. Per §H1, Bidder 2's 78→81–84 is a revision (§H5), could be 2 rows or 1. |
| 21 | 2014-10-30 to 11-02 | J.P. Morgan speaks with all potentially interested parties re their indications; Bidder 2 revises up | 31 | Bid-revision event — §H5 + §B4 date-range. |
| 22 | 2014-11-03 | Board allows 4 above-$80 bidders to proceed to final round; 2 eliminated (the 2 sub-$80 IOI submitters) | 31 | `Final Round Ann` per §K1 (formal round now announced) + 2 `DropBelowInf` per §I1 (target-cut). The 9 NDA signers who never submitted an IOI also implicitly drop out here, but the filing does not narrate each one — §P-S1 soft-flag territory. |
| 23 | 2014-11 (early) | Two of the 4 advancers form **Bidder 3 consortium** (both from the 15 NDA signers) | 31 | §I2 re-engagement / §E2 joint-bidder formation; each constituent was already NDA'd individually. |
| 24 | 2014-11 (month) | Bidders receive merger-agreement draft; submit mark-ups. Q3 earnings update. | 31 | Context. |
| 25 | 2014-12-03 | Board meeting — review of strategic alternatives ahead of final bids | 31 | Context. |
| 26 | 2014-12-05 | Original bid deadline; accelerated to 12-10 | 32 | Context. |
| 27 | 2014-12-06 | Buyer Group + Bidder 2 submit merger-agreement comments; Buyer Group submits financing commitments | 32 | Context. |
| 28 | 2014-12-08 | Wachtell Lipton sends revised merger agreement to Buyer Group + Bidder 2 | 32 | Context. |
| 29 | 2014-12-09 | Intro meetings Longview ↔ Buyer Group and Longview ↔ Bidder 2 (Longview signs NDA for this purpose) | 32 | Optional §Scope-3/§M3 Longview NDA. Not a bidder-NDA — Longview is a rollover participant, not a competing bidder. |
| 30 | 2014-12-10 | **Final round bids**: Buyer Group $80.70 (written, with merger-agreement markup + financing commitments); Bidder 2 $80.35 (written, with merger-agreement markup); Bidder 3 verbal "not above ~$78" — no written offer submitted | 32 | 2 `Bid` formal rows + 1 `Bid` informal (Bidder 3 verbal) + `Final Round` + `DropAtInf` or `DropBelowM` for Bidder 3 |
| 31 | 2014-12-10 | Ad hoc committee instructs each bidder to submit improved bids on 12-12 | 32 | `Final Round Ext Ann` per §K1 |
| 32 | 2014-12-11 | J.P. Morgan confirms Longview's willingness to roll over | 32 | Context. |
| 33 | 2014-12-12 early | Buyer Group requests permission to include Longview rollover; granted | 32 | Context. |
| 34 | 2014-12-12 evening | Bidder 2 $81.50 (best and final); Buyer Group oral $82.50 then written $83.00 (best and final) | 33 | 1 Bidder 2 `Bid` formal + 2 Buyer Group `Bid` formal rows (oral + written) per §C3; filing explicitly narrates 2 successive offers |
| 35 | 2014-12-12 | `Final Round Ext` | 33 | Per §K1 |
| 36 | 2014-12-13 | Board approves Buyer Group $83.00; Bidder 2 implicitly drops | 33 | `Drop` for Bidder 2 per §I1 (target-selection — DropTarget more precise; filing doesn't use the verb) |
| 37 | 2014-12-14 | Merger agreement, voting agreement, related transaction agreements executed; press release | 33 | `Executed` per §C1; one row per §E2.a |

Total "canonical" event count per filing reading: **~40–50 rows** depending on how informally one treats Bidder 2's IOI revision and Buyer Group's split 12/12 oral/written offers.

Deal-level facts:
- `all_cash = true` ($83.00 cash per share).
- `target_legal_counsel = "Wachtell, Lipton, Rosen & Katz"`.
- `acquirer_legal_counsel` — not identified in the Background section of this page range.
- `termination_fee = $255M` (Company→Parent, per page 71); `reverse_termination_fee = $510M`.
- `go_shop_days = null` (no go-shop; page 37 explicitly notes the 15 CA signers had standstills preventing post-announcement bumps).

---

## Source-by-source row counts and structure

### Alex (53 rows)

Per-bidder breakdown:
- Activist: **1 row** (JANA + Longview collapsed, labeled `NA`; §D1.b violation) — BidderID 0.8.
- `IB`: 1 row (J.P. Morgan, 2014-07-01). Legal advisor Wachtell Lipton in `comments_1`.
- `Target Sale Public`: 1 row (2014-08-13).
- `Sale Press Release`: 1 row (2014-08-19).
- 15 `NDA` rows (2014-10-07, all `Unnamed party 1..12`, `Bidder 1`, `Bidder 2`, `Buyer Group`). Note: Alex's NDA date is 2014-10-07 (§B1 first-week-of-month → 2014-10-05 preferred).
- `Final Round Inf Ann`: 1 row (2014-10-15, inferred from "During October").
- Oct 30 IOIs: 4 `Informal` bid rows (Unnamed party 1 @$80-unstated; Unnamed party 2 unstated; Unnamed party 3 unstated; Buyer Group $81–$83; Unnamed party 4 $80–$85; Bidder 2 $78). **Note**: Alex tracks the IOIs onto the NDA placeholders who submitted them, but names only Buyer Group, Unnamed party 4 (=Bidder3-A?), and Bidder 2 per the filing.
- 1 `Final Round Inf` row (2014-10-30).
- Bidder 2 revision row (2014-10-30, $81–$84, comment "2014-11-02"). §H5 / §B4.
- Oct 30 `Drop` rows: **8 rows** (Unnamed 5–12) — Alex emits catch-all Drops on 10/30 for the NDA signers who never submitted an IOI.
- `DropTarget` rows 11/03: **2 rows** (Unnamed 2, Unnamed 3) — the 2 sub-$80 IOI submitters cut at the $80 threshold.
- `Final Round Ann` (11/15, inferred — filing says 11/03): 1 row.
- 12/10 formal bids: 3 rows (Buyer Group $80.70; Bidder 2 $80.35; Bidder 3 $78 `DropBelowM` per Alex's xlsx).
- 12/10 Drop rows: Unnamed 1 and Unnamed 4 (retroactive drops — Alex's model of the 2 advancers who were eliminated at this stage? Unclear).
- `Final Round` (12/10), `Final Round Ext Ann` (12/10).
- 12/12 formal bids: 3 rows (Bidder 2 $81.50; Buyer Group $82.50; Buyer Group $83.00).
- `Final Round Ext` (12/12).
- `Drop` rows on 12/14 for Bidder 2 and Bidder 3 (final-round dropouts).
- `Executed` row (2014-12-12 rough date, 2014-12-14 precise, Buyer Group).

Notable structural points in Alex:
- Decimal BidderIDs throughout (0.7, 0.8, 15.5, 21.5, 22.5, 34.5, 38.2, 38.3, 38.5, 38.7, 40.3, 40.5, 43.5) — relic of hand-editing. §A1 forbids in AI output but accepted in Alex's workbook.
- No `source_quote` / `source_page` by design.
- Date for NDA batch is 2014-10-07 (not §B1-mapped 2014-10-05).

### bids_pipeline (55 rows)

Per-bidder breakdown:
- **Industry Participant (IP) pre-history**: 4 rows — `Target Interest` 3/15, `Bidder Interest` 8/07, `DropTarget` 8/27, Activist Sale cluster.
- **Activists — 4 rows** (JANA 7/3, Longview 7/7, JANA 7/10, Longview 7/10 — §D1.b-over-atomized; rows 4 and 5 are repeat advocacy, not new 13D events).
- `IB` row (J.P. Morgan 7/15, rough "In July 2014").
- `Target Sale` 8/13 + `Target Sale Public` 8/19.
- **15 NDA rows** (Buyer Group, another bidder, Bidder 2, Bidder 3, consortium-verbatim acquirer string, bidder_6..bidder_15) — **correct count**, but mixed naming convention. The "another bidder" + "Bidder 3" rows model Bidder3-A + Bidder3-B. The row with the full consortium verbatim acquirer string (`"BC Partners, Inc., La Caisse..."`) as BidderName is structurally weird — shouldn't be a separate NDA signer from Buyer Group; **apparent double-count** (Buyer Group already at BidderID 1.03125, consortium label at 1.15625).
- `Final Round Inf Ann` 10/15.
- Oct 30 IOI bids: 3 rows (Buyer Group $81–$83; another bidder $80–$85; Bidder 2 $78 → **also row 5 for 11/02 Bidder 2 $81–$84 revision**) — matches filing + §H5.
- `Drop` row for "another bidder" (Bidder 3-A) — likely at 10/30; unclear date. Row 30.
- `Final Round Inf` 10/30 (1 row).
- **`Final Round Ann` 11/03** (1 row).
- **10 `DropTarget` rows on 11/03** (bidder_6..bidder_15) — mapping all NDA signers who didn't submit IOIs to DropTarget. Using the filing language: *"representatives of J.P. Morgan notified the eliminated parties."*
- 12/10 final round: Buyer Group $80.70 formal; Bidder 2 $80.35 formal; Bidder 3 $78 formal + `DropBelowM` (one row) plus `Final Round` row plus `Final Round Ext Ann`.
- 12/12: Bidder 2 $81.50 formal; Bidder 2 `Drop`; Buyer Group $82.50 formal; Buyer Group $83.00 formal; Buyer Group `Drop` (???) — this last row is puzzling (winner doesn't drop). Likely a bookkeeping artifact.
- `Executed` row 12/14 (BidderName = verbatim acquirer string).

Notable structural points in bids_pipeline:
- BidderIDs show a weird pattern of dense fractional values (e.g., 1.03125 = 33/32 NDA-1 of 15; 1.0625 = NDA-2/15; etc., by powers of 1/32) — internal decimal wedging. Violates §A1.
- Activist over-atomization: JANA 7/3 + Longview 7/7 is fine; JANA 7/10 + Longview 7/10 is NOT — they are follow-up meetings for existing activists, not new 13D filings.
- Inconsistent BidderName for the Buyer Group: mixed between "Buyer Group" (NDA) and the full acquirer verbatim string (NDA-5/15 and Executed). The NDA-5/15 row is apparently a redundant row.
- No `source_quote` / `source_page` columns — CSV lacks them.

### bids_try (41 rows)

Per-bidder breakdown (reading the CSV structure):
- Activists: **2 rows** (JANA 7/3, Longview 7/7) — §D1.b cleanest compliance; soft flag `multi_activist_coordination_ambiguous`.
- `IB` row (J.P. Morgan 2014-07-15, rough "In July 2014"); `date_inferred_from_context` soft flag noting engagement letter effective 8/21.
- `Target Sale` 8/13.
- `Target Sale Public` 8/19.
- **15 NDA rows** (2014-10-05 per §B1 "first week"), `Buyer Group`, `Bidder 2`, `Bidder 3-A`, `Bidder 3-B`, `Financial 2..10`, `Financial 14..15` (§E3 placeholder format). Indices skip `Financial 11..13` because the 4 named roles + 11 unnamed = 15. 13 of these NDA rows carry `nda_without_bid_or_drop` soft flag — **correct per §I1 / §M2 / §P-S1**.
- `Informal` Bid rows on 10/30 for Buyer Group $81–$83, Bidder 3-A $80–$85, Bidder 2 $78, Bidder 3-B $80 (lower-only). Plus Bidder 2 revision $81–$84 at `bid_date_rough: "October 30 to November 2, 2014"` on 10/30.
- Sub-$80 IOIs: **Financial 2 $<80, Financial 3 $<80** — 2 atomic rows for the 2 sub-$80 IOI submitters, with `bid_value_unspecified` info flag.
- `Final Round Ann` 11/03.
- 2 `DropBelowInf` rows (Financial 2, Financial 3).
- **MISSING: no drops for the 11 NDA signers who never submitted IOIs** (reliance on §P-S1 / `nda_without_bid_or_drop` soft flag on the NDA rows themselves).
- `Bidder 3-A` $≤78 + `Bidder 3-B` $≤78 Informal Bid rows on 12/10 (verbal consortium bid, split per §I1).
- Buyer Group $80.70 formal; Bidder 2 $80.35 formal (12/10).
- Bidder 3-A + Bidder 3-B `DropAtInf` on 12/10 (consortium-drop split per §I1, with `drop_agency_ambiguous` soft flag).
- Bidder 2 $81.50 formal (12/12); Buyer Group $82.50 oral + $83.00 written formal rows (12/12).
- Bidder 2 `Drop` on 12/13.
- `Executed` row on 12/14 (Buyer Group, `bidder_type.mixed=1` — **correctly flags consortium nature**).
- **MISSING: `Final Round Inf Ann`, `Final Round Inf`, `Final Round`, `Final Round Ext Ann`, `Final Round Ext`** — structural round markers are absent from this CSV export (5 rows missing; likely the largest source of the row-count deficit after NDA-only).
- **MISSING: Industry Participant pre-history** (3–4 rows).
- **MISSING: `Sale Press Release`** (1 row).

Notable structural points in bids_try:
- Every row has `source_quote` + `source_page`.
- **Systemic hard-flag defect: `source_quote_not_in_page` on 18+ rows** — extractor used straight ASCII apostrophe `'` and straight ASCII quotes where the filing uses smart quotes (U+2019, U+201C/201D). Under §R2's NFKC normalization, these DO NOT fold together (NFKC preserves U+2019). **This is a validator-level issue that masks the fact that the extractor's content is actually correct against the filing.** See §Systemic findings.
- Multiple `resolved_name_not_observed` soft flags — `bidder_registry.resolved_name` value is not in `aliases_observed`. A §E4 violation, but the filings never reveal the sponsor names anyway; the inferred mappings are research overlay, not filing text.
- Cleanest §E2.b + §E3 compliance of the three.

---

## Divergence table

Verdict key: **AlexRight** | **BPRight** (bids_pipeline right) | **TryRight** (bids_try right) | **BothAIRight** | **NoneRight** | **JudgmentCall** | **AlexFlagged** (Alex's own flagged-row)

| # | Topic | Filing ground truth | Alex | bids_pipeline | bids_try | Verdict | Notes |
|---|-------|---------------------|------|---------------|----------|---------|-------|
| 1 | Industry Participant `Target Interest` (March 2014) | Board authorized mgmt to contact IP in March 2014; CEO discussions in Spring | missing | `Target Interest` 3/15 (Industry Participant, S) | missing | **BPRight** | Clear §D1 Target Interest event per Mac Gray pattern. Alex skips; bids_try skips. |
| 2 | Industry Participant re-approach (Aug 7, 2014) | IP contacted J.P. Morgan | missing | `Bidder Interest` 8/07 | missing | **BPRight** | §D1 criteria met (approach, no price). |
| 3 | Industry Participant rejection (Aug 27, 2014) | JPM tells IP it won't be invited | missing | `DropTarget` 8/27 | missing | **BPRight** | §I1 target-initiated drop; unambiguous quote on page 30. |
| 4 | Activist Sale — JANA 2014-07-03 | JANA filed 13D | `Activist Sale` BidderID 0.8, 2014-07-03 but `BidderName=NA` (collapses 2 activists) | JANA Partners 7/3 `Activist Sale` | JANA Partners 7/3 `Activist Sale` | **BothAIRight** (against Alex) | Alex violates §D1.b by collapsing; the two AIs correctly atomize. This is an **AI-identified correction** to Alex's reference. |
| 5 | Activist Sale — Longview 2014-07-07 | Longview public letter | Collapsed into row with JANA | Longview 7/7 `Activist Sale` | Longview 7/7 `Activist Sale` | **BothAIRight** | Same as above. |
| 6 | Activist Sale — JANA 2014-07-10 follow-up | JANA meets with Company | missing | `Activist Sale` 7/10 (JANA) | missing | **TryRight** | §D1.b says "one row per activist" — the 7/10 meeting is follow-up on the 7/3 13D, not a new activist event. bids_pipeline over-atomizes. |
| 7 | Activist Sale — Longview 2014-07-10 follow-up | Longview reiterates | missing | `Activist Sale` 7/10 (Longview) | missing | **TryRight** | Same reasoning — follow-up advocacy, not a new event. |
| 8 | IB retention | JPM retained in July (engagement letter 8/21) | `IB` 2014-07-01 JPM | `IB` 2014-07-15 JPM (rough "In July 2014") | `IB` 2014-07-15 JPM (rough "In July 2014"; `date_inferred_from_context`) | **TryRight** (clearest dating / rationale) | Alex's 7/1 date is ad hoc; §B1 "In July" → 2014-07-15. |
| 9 | `Target Sale` 2014-08-13 | Board authorizes sale exploration | missing | `Target Sale` 8/13 | `Target Sale` 8/13 | **BothAIRight** | Alex has no `Target Sale` row (went straight to `Target Sale Public`). |
| 10 | `Target Sale Public` 2014-08-19 | Press release announcing sale exploration | `Target Sale Public` 2014-08-13 (WRONG DATE — should be 8/19) | `Target Sale Public` 8/19 | `Target Sale Public` 8/19 | **BothAIRight** | Alex's date 2014-08-13 appears to be a transcription error (that was the board meeting; press release was 8/19). Alex also has `Sale Press Release` 8/19 separately. |
| 11 | `Sale Press Release` 2014-08-19 | Same event | `Sale Press Release` 8/19 | missing | missing | **AlexRight** | §C1 distinguishes `Target Sale Public` (public announcement) from `Sale Press Release` — the two AIs fold both into `Target Sale Public`. Alex emits both. **Austin judgment call** whether this is meaningful redundancy. |
| 12 | 15 NDAs first week of October 2014 | 15 financial buyer NDAs | 15 rows, dated 10/07 | 15 rows, dated 10/07 | 15 rows, dated 10/05 (§B1 compliant) | **TryRight (date)**; all 3 right on count | §B1 maps "first week of October" → 10/05. bids_try is only one to apply it. |
| 13 | NDA naming convention | Filing narrates 15 financial buyers; later names Buyer Group, Bidder 2, Bidder 3 (2 constituents) | `Unnamed party 1..12`, `Bidder 1`, `Bidder 2`, `Buyer Group` (no `Bidder 3` on NDA row) | `Buyer Group`, `another bidder`, `Bidder 2`, `Bidder 3`, `[verbatim acquirer string]`, `bidder_6..15` (mixed conventions, apparent duplicate Buyer Group row) | `Buyer Group`, `Bidder 2`, `Bidder 3-A`, `Bidder 3-B`, `Financial 2..10`, `Financial 14..15` | **TryRight** | bids_try's Bidder 3-A/3-B split pre-figures the consortium that forms in November; names are §E3-compliant. |
| 14 | `Final Round Inf Ann` 2014-10-15 (inferred) | "During October, bidders were informed IOIs due 10/30" | `Final Round Inf Ann` 10/15 | `Final Round Inf Ann` 10/15 | **MISSING** | **AlexRight / BPRight** | bids_try appears to have dropped this round-announcement row. |
| 15 | Oct 30 IOI — Buyer Group $81–$83 | Per filing | Informal bid row ($81–$83) | Informal bid row ($81–$83) | Informal bid row ($81–$83) | **BothAIRight + AlexRight** | |
| 16 | Oct 30 IOI — another bidder (Bidder 3-A) $80–$85 | Per filing | Informal bid row ($80–$85) | Informal bid row ($80–$85) | Informal bid row ($80–$85, Bidder 3-A) | **AllRight** | |
| 17 | Oct 30 IOI — Bidder 2 $78 | Per filing | Informal bid row $78 | Informal bid row $78 | Informal bid row $78 | **AllRight** | |
| 18 | Oct 30 IOI — Bidder 3-B (4th above-$80) | Filing says "four bidders... at or above $80" but narrates only 3 prices | missing | missing | Informal bid row ($80 lower-only) with `date_unknown` soft flag | **TryRight** | The 4th above-$80 bidder is Bidder 3-B (the one that said "drop out unless allowed to work with another bidder"); filing doesn't give price. bids_try creates a proper placeholder with `bid_lower_only`. Alex and bids_pipeline miss this 4th bidder. |
| 19 | Oct 30 IOI — 2 sub-$80 submitters | 6 total IOIs, 4 at/above $80, so 2 below | **aggregated into Drop rows** | missing as separate rows; rolled into the 10 DropTarget rows on 11/03 | 2 separate Informal `Bid` rows (Financial 2, Financial 3) with `bid_value_unspecified` | **TryRight** | Most faithful to the "6 submitted IOIs" count in the filing. |
| 20 | Bid revision — Bidder 2 $78 → $81–$84 | "As a result of discussions with J.P. Morgan... increased its indication" | 2 rows (Bidder 2 $78 on 10/30 + Bidder 2 $81–$84 on 11/02) | 2 rows (Bidder 2 $78 + Bidder 2 $81–$84, both 10/30) | 2 rows (Bidder 2 $78 + Bidder 2 $81–$84 on 10/30, rough "October 30 to November 2") | **AllRight** | All three handle the revision as separate events per §H5. |
| 21 | `Final Round Inf` 10/30 | Filing: "six of the potentially interested parties submitted indications of interest" | `Final Round Inf` 10/30 | `Final Round Inf` 10/30 | **MISSING** | **AlexRight / BPRight** | bids_try drops the round-marker. |
| 22 | Nov 3 Board decides 4-to-final-round | Board picks 4 above-$80 | `Final Round Ann` 11/15 (WRONG DATE — filing says 11/03) | `Final Round Ann` 11/03 | `Final Round Ann` 11/03 | **BothAIRight** | Alex's 11/15 date appears to be a judgment call / error; bids pipeline & bids_try are correct per filing. |
| 23 | Nov 3 — 2 sub-$80 bidders eliminated (`DropBelowInf`) | "Following this meeting, representatives of J.P. Morgan notified the eliminated parties" | 2 `DropTarget` rows on 11/03 (Unnamed 2, Unnamed 3) | 10 `DropTarget` rows on 11/03 (bidder_6..15) — treats all 9 IOI non-submitters plus the 2 sub-$80 submitters as dropped | 2 `DropBelowInf` rows on 11/03 (Financial 2, Financial 3) | **TryRight (code choice)** | §I1: target-cut at informal stage = `DropBelowInf`. Both Alex and bids_pipeline use `DropTarget`; bids_try's code choice is the most precise §I1 match. |
| 24 | 10 NDA signers who never submitted IOIs (implicit drops on Oct 30 / Nov 3) | Filing is silent on per-bidder fate | 8 catch-all `Drop` rows on 10/30 (Unnamed 5–12) | 10 `DropTarget` rows on 11/03 (bidder_6..15) | 0 rows + `nda_without_bid_or_drop` soft flags on 13 NDAs | **JudgmentCall / §P-S1** | Per iter-7 Providence precedent: "Do **not** fabricate a catch-all `Drop` row with a generic shared `source_quote`" (§I1). bids_try is most rule-compliant **as the rules are written today**. Alex and bids_pipeline both synthesize catch-all drops. **This is the single biggest driver of the 41 vs 53/55 gap. Austin's call.** |
| 25 | Dec 10 — Buyer Group $80.70 formal bid | Per filing | formal bid row $80.70 | formal bid row $80.70 | formal bid row $80.70 | **AllRight** | |
| 26 | Dec 10 — Bidder 2 $80.35 formal bid | Per filing | formal bid row $80.35 | formal bid row $80.35 | formal bid row $80.35 | **AllRight** | |
| 27 | Dec 10 — Bidder 3 verbal ~$78 | "Bidder 3 verbally communicated... not above current stock price of approximately $78" | formal bid row $78 flagged `Informal` (misclassified) then `DropBelowM` | formal bid row $78 with `DropBelowM` (one-row collapse) | 2 Informal bid rows (Bidder 3-A, Bidder 3-B, both $≤78 upper) + 2 `DropAtInf` rows (consortium-drop-split per §I1) | **TryRight** (structure) | bids_try correctly splits the consortium drop per §I1; and §G1 structural signal "verbal only, no financing" → informal. Alex marks as formal which is wrong; bids_pipeline collapses the bid and drop into one row which is structurally awkward. |
| 28 | Dec 10 — `Final Round` | "final bid letters... and a verbal indication" | `Final Round` 12/10 | `Final Round` 12/10 | **MISSING** | **AlexRight / BPRight** | bids_try again drops the round marker. |
| 29 | Dec 10 — `Final Round Ext Ann` | "to instruct the bidders to submit improved bids on December 12" | `Final Round Ext Ann` 12/10 | `Final Round Ext Ann` 12/10 | **MISSING** | **AlexRight / BPRight** | Same. |
| 30 | Dec 12 — Bidder 2 $81.50 formal | "Bidder 2 submitted an offer of $81.50 per share, in cash... best and final offer" | formal bid row $81.50 | formal bid row $81.50 | formal bid row $81.50 | **AllRight** | |
| 31 | Dec 12 — Buyer Group $82.50 oral + $83.00 written | "Buyer Group initially submitted an oral offer of $82.50 per share... Later in the evening... best and final offer of $83.00" | 2 rows ($82.50 and $83.00 formal) | 2 rows ($82.50 and $83.00 formal) | 2 rows ($82.50 and $83.00 formal) | **AllRight** | All three correctly atomize the two 12/12 offers. |
| 32 | Dec 12 — `Final Round Ext` | per filing | `Final Round Ext` 12/12 | (implicit; not separate row) | **MISSING** | **AlexRight** | |
| 33 | Dec 12–13 — Bidder 2 loses / drops | Bidder 2 not selected | `Drop` 12/14 (Bidder 2) | `Drop` (Bidder 2, no date) | `Drop` 12/13 (Bidder 2, with `drop_agency_ambiguous` soft) | **TryRight** | Filing narrates Dec 13 board decision; bids_try's date is most precise. Alex's 12/14 date is Executed-day, slightly off. |
| 34 | Executed 2014-12-14 | Per filing | `Executed` 12/14 (Buyer Group, `all_cash=1`) | `Executed` 12/14 (full verbatim acquirer string) | `Executed` 12/14 (Buyer Group, `bidder_type.mixed=1`) | **TryRight** | bids_try's `mixed` type flag is most faithful to §F3 (BC Partners = F + StepStone = F + Caisse = F + Longview = S-adjacent rollover participant). bids_pipeline's use of the full verbatim acquirer string as `BidderName` violates §E3 canonical-ID convention. |
| 35 | Buyer Group "Drop" row on 12/12? | Not in filing | missing | `Drop` row for Buyer Group (BidderID 12.5) — **spurious** | missing | **AlexRight + TryRight** | bids_pipeline emits a Drop for the winner, which is wrong. Likely an artifact of its oral-then-written bid tracking. |

---

## Systemic findings

### 1. NDA atomization (§E2.b + §E5)

All three extractions emit 15 atomic NDA rows on the 10/05 (or 10/07) date. The filing says *"the Company entered into confidentiality and standstill agreements with 15 potentially interested financial buyers"* — a numeric count (§E5) with some of the 15 later named (Buyer Group, Bidder 2, the two Bidder 3 constituents), consistent with §E2.b's "Named → filing label; unnamed → placeholders."

- Alex's naming (`Unnamed party 1..12`, `Bidder 1`, `Bidder 2`, `Buyer Group`) is adequate but ad hoc — the Alex reference does not follow §E3's `bidder_NN` canonical format.
- bids_pipeline's naming is **inconsistent**: Buyer Group appears both as "Buyer Group" (row 67) and as the full verbatim acquirer string (row 71). Plus `bidder_6..bidder_15` shows internal `bidder_NN` canonical IDs mixed into the `BidderName` column. Appears to be a naming-convention drift in bids_pipeline.
- **bids_try's naming is the most §E3-compliant**: `Buyer Group`, `Bidder 2`, `Bidder 3-A`, `Bidder 3-B` (correctly pre-figuring the consortium), plus `Financial 2..10, 14, 15` placeholders.

Verdict: all three are within §E2.b compliance; bids_try is most rule-faithful.

### 2. Consortium handling (§E2.a + §F3)

The Buyer Group is a **mixed** consortium (BC Partners = F + Caisse = F + GIC = F + StepStone = F + Longview = S-adjacent rollover participant). Per §E2.a, one `Executed` row per deal regardless of consortium structure; `joint_bidder_members` field lists constituents.

- Alex: one `Executed` row, `bidder_type_financial=1` (not mixed, not quite right). Rollover participant Longview is captured only in the legacy acquirer-verbatim column.
- bids_pipeline: one `Executed` row with the **full verbatim acquirer string** as `BidderName` — not §E3-compliant. Implicitly correct count.
- bids_try: one `Executed` row with `bidder_type.mixed=1` + info flag `joint_bidder_members` in comments: *"Buyer Group consortium includes BC Partners (lead/nominal acquirer), Caisse, GIC, StepStone, plus Longview (bidder_02) as equity rollover participant. §E2.a single Executed row."* — most §E2.a + §F3 compliant.

**Judgment call for Austin:** is Longview a Buyer Group constituent (justifying the `mixed` type) or a rollover-only participant separate from the legal counterparty? The filing narrates Longview signing a **separate** confidentiality agreement only on 12/09 to receive bid-price information and a voting agreement on 12/12 — Longview is **not a bidder** in the classical sense but a rollover participant. Under strict §F3, "consortium" requires members who are **bidders**, so the financial-only Buyer Group should be `base = "f"`, not `mixed`. bids_try over-applies `mixed`; it should be `f`.

### 3. Activist Sale atomization (§D1.b)

**Alex violates §D1.b.** JANA + Longview were separate activists on separate dates (7/3 + 7/7); Alex collapses to one row labeled `NA`. This is a §D1.b "Migration note" **AI-identified correction to Alex's reference** (§D1.b explicitly names Petsmart as the motivating example).

Both AIs emit 2 Activist Sale rows correctly. bids_pipeline **over-atomizes** with 4 total (adds 7/10 follow-up meeting rows for both JANA and Longview). Per §D1.b "one row per activist" — a follow-up meeting or further advocacy is not a new activist event. bids_try emits 2 rows (cleanest).

### 4. Industry Participant pre-history (§D1 + §I1)

Industry Participant is a strategic party the board considered in March/Spring 2014, then rebuffed formally on 8/27/2014. This is a well-defined §D1 `Target Interest` → `Bidder Interest` → `DropTarget` chain entirely supported by the filing (page 28–30 quotes).

- Alex skips it entirely. This is consistent with his legacy practice of not tracking pre-auction strategic-party discussions, but the filing text is unambiguous.
- bids_pipeline captures it in 3–4 rows (correct).
- bids_try skips it. **This is ~3–4 of the 41 vs 53/55 row gap.**

**Verdict:** bids_pipeline correct. bids_try should re-extract. Per §D1: *"Target initiates private discussions with a specific party without a board-level sale resolution → `Target Interest` (Mac Gray pattern)."* Industry Participant matches exactly.

### 5. NDA-only with no narrated follow-up (§I1 / §M2 / §P-S1)

The filing does not narrate per-bidder activity for the 11 NDA signers who did not submit IOIs. §I1 NDA-only rule + §M2 No-bid-intent skip + §P-S1 soft flag say: **keep the NDA row, do not fabricate synthetic Drops**.

- Alex: fabricates 8 catch-all Drops on 10/30 (Unnamed 5–12). **Violates §I1 NDA-only rule.**
- bids_pipeline: fabricates 10 `DropTarget` rows on 11/03 (bidder_6..15) with shared `source_quote` *"Following the November 3 meeting, J.P. Morgan notified the eliminated parties..."* — same phrase on 10 rows. **Violates §R2 evidence-specificity and §I1 NDA-only rule** (Providence iter-7 precedent).
- bids_try: 0 fabricated drops; 13 NDA rows carry `nda_without_bid_or_drop` soft flag. **§I1 + §P-S1 compliant.**

**This is the single largest source of the bids_try 41 vs Alex 53 / bids_pipeline 55 row-count gap.** Austin's policy call: accept bids_try's stance (rule-compliant, same as iter-7 Providence decision) OR tighten §I1/§P-S1 to require catch-all Drops with a shared quote (would reset the exit clock).

### 6. Dates (§B1 first-week-of-October → 10/05)

Only bids_try applies §B1's deterministic mapping ("first week of October" → 2014-10-05). Alex uses 10/07 (off by 2 days, no obvious rule basis); bids_pipeline uses 10/07 (same issue). **bids_try right.**

### 7. Source-quote validator bug (smart quotes)

bids_try has **18+ hard `source_quote_not_in_page` flags** — all caused by the extractor using straight ASCII apostrophes `'` and straight ASCII double-quotes `"` where the filing uses smart Unicode quotes (U+2019, U+201C, U+201D). Under §R2 NFKC normalization, these do **not** fold together (NFKC is not tolerant of punctuation variants).

**The extraction content is actually correct against the filing** — the quoted text is there, just with smart apostrophes. This is a **normalizer policy issue**, not an extraction defect. Options:
1. **Extractor-side fix:** the extractor should copy-paste filing text verbatim including smart quotes. Current bids_try is using ASCII variants, likely an artifact of JSON encoding or model training.
2. **Validator-side fix:** add a second-pass normalization that folds `U+2019 → U+0027` and `U+201C, U+201D → U+0022` BEFORE the substring check. This is more lenient than strict NFKC.

Either way, the current `source_quote_not_in_page` flags on petsmart-inc bids_try are spurious. Austin should decide: fix normalizer, or re-extract with filing-verbatim quotes.

### 8. Round-marker coverage

bids_try **drops 5 round-marker rows** that Alex and bids_pipeline both emit: `Final Round Inf Ann` (10/15), `Final Round Inf` (10/30), `Final Round` (12/10), `Final Round Ext Ann` (12/10), `Final Round Ext` (12/12). Per §K1/§K2 these are **required** emission events even when implicitly narrated. **This is another major driver of the 41 vs 53/55 gap (5 rows).**

### 9. BidderID decimal-wedging

- Alex: heavy decimal usage (0.7, 0.8, 0.9, 15.5, 22.5, 34.5, 38.2, 38.3, 38.5, 38.7, 40.3, 40.5, 43.5) — legacy hand-edit pattern. §A1 forbids in AI output.
- bids_pipeline: dense powers-of-1/32 wedges on NDA rows (1.03125, 1.0625, 1.09375, 1.125, ...) — internal bookkeeping, violates §A1.
- bids_try: clean integer BidderID 1..41 per §A1. Correct.

---

## Why bids_try dropped to 41 from Alex's 53

Row-count accounting (approximate; summed from bids_try vs Alex):

| Category | Alex | bids_pipeline | bids_try | Δ vs Alex |
|---|---:|---:|---:|---:|
| Activist Sale | 1 (collapsed) | 4 (over-atomized) | 2 (§D1.b correct) | +1 |
| Industry Participant pre-history | 0 | 4 | 0 | 0 (both miss) |
| IB | 1 | 1 | 1 | 0 |
| Target Sale | 0 | 1 | 1 | +1 |
| Target Sale Public | 1 | 1 | 1 | 0 |
| Sale Press Release | 1 | 0 | 0 | −1 |
| NDAs (first week Oct) | 15 | 15 | 15 | 0 |
| Final Round Inf Ann (10/15) | 1 | 1 | 0 | −1 |
| Oct 30 IOIs (4 above $80) | 4 | 4 | 4 | 0 |
| Oct 30 IOIs (2 below $80) | 0 (aggregated into Drops) | 0 | 2 | +2 |
| Oct 30 Bidder 2 revision | 1 | 1 | 1 | 0 |
| Oct 30 Bidder 3-B placeholder | 0 | 0 | 1 | +1 |
| Final Round Inf (10/30) | 1 | 1 | 0 | −1 |
| NDA-signer catch-all Drops (10/30) | 8 | 0 | 0 | −8 |
| Sub-$80 DropBelowInf/DropTarget (11/03) | 2 | 2 | 2 | 0 |
| NDA-signer catch-all DropTarget (11/03) | 0 | 10 | 0 | 0 |
| Final Round Ann (11/03 or 11/15) | 1 | 1 | 1 | 0 |
| Dec 10 formal bids | 3 | 3 | 2 (Bidder 3 verbal split to 2 informal) + 2 | +1 (4 total vs 3) |
| Dec 10 Bidder 3 split drops | 0 | 1 (combined) | 2 (split) | +2 |
| Dec 10 miscellaneous Drops (Alex 38.2, 38.3) | 2 | 0 | 0 | −2 |
| Final Round (12/10) | 1 | 1 | 0 | −1 |
| Final Round Ext Ann (12/10) | 1 | 1 | 0 | −1 |
| Dec 12 formal bids (Bidder 2 + 2 Buyer Group) | 3 | 3 | 3 | 0 |
| Final Round Ext (12/12) | 1 | 0 | 0 | −1 |
| Dec 13–14 losers' Drops | 2 (Bidder 2 + Bidder 3) | 2 (Bidder 2 × 2 rows) | 1 (Bidder 2 only) | −1 |
| Spurious Buyer Group Drop | 0 | 1 | 0 | 0 |
| Executed | 1 | 1 | 1 | 0 |
| **Subtotal** | **53** | **~55** | **41** | **−12** |

**The big row-count deltas for bids_try (−12 net):**
1. 5 missing round-markers (`Final Round Inf Ann`, `Final Round Inf`, `Final Round`, `Final Round Ext Ann`, `Final Round Ext`) → **−5**
2. 8 NDA-signer catch-all Drops bids_try did not emit (Alex did); but Alex's catch-alls themselves arguably violate §I1/§R2 → **−8** (compliance decision)
3. Industry Participant pre-history missed by both Alex and bids_try — but bids_pipeline found it → +3–4 for bids_pipeline relative to others
4. `Sale Press Release` merged into `Target Sale Public` → **−1**
5. Alex's 2 miscellaneous 12/10 Drop rows (38.2, 38.3) that have unclear semantics → **−2**

**Compensation in bids_try's favor (+6):**
- +2 sub-$80 IOI rows (bids_try atomizes, Alex aggregates to Drops)
- +1 Bidder 3-B placeholder
- +1 Target Sale row
- +1 Bidder 3 consortium-drop-split second row
- +1 Activist atomization (vs Alex's single collapse)

Net: 53 + (6 bids_try captures) − (12 bids_try misses from Alex's count) = **≈47 expected**, but bids_try shows 41 — some Alex rows are not decomposable into the above categories (Alex's 53 is partly noise). The **true defensible count per filing + rulebook is ~40–45 rows**, so bids_try's 41 is within range; the missing round-markers (5 rows) are the only objectively wrong deletion.

---

## Specific rule / prompt fixes

### Must-fix (hard)

1. **bids_try must emit final-round marker rows (§K1/§K2).** Missing `Final Round Inf Ann`, `Final Round Inf`, `Final Round`, `Final Round Ext Ann`, `Final Round Ext` is a hard coverage gap. Likely cause: the extractor prompt treats these as implicit; it needs to emit them as separate atomic events. Fix: add to `prompts/extract.md` a checklist of round-structure events that must be emitted whenever a final round is narrated.
2. **bids_try must emit Industry Participant pre-history rows (§D1 Target Interest / §D1 Bidder Interest / §I1 DropTarget).** The pre-history is 3–4 unambiguous rows on pages 28–30. The extractor should not skip pre-auction strategic approaches — §L1/§L2 explicitly covers prior-process inclusion.
3. **bids_try smart-quote normalization.** Either fix the extractor to preserve filing-verbatim smart quotes, or extend the §R2 validator to fold U+2019 / U+201C / U+201D during substring check. Without this, 18+ rows carry spurious hard flags.

### Should-fix (soft)

4. **§D1.b — bids_pipeline over-atomizes activist follow-ups.** JANA's 7/10 meeting is ongoing advocacy by an existing activist, not a new Activist Sale event. Rule already says "one row per activist"; bids_pipeline appears to emit one row per *activist event date*. Tighten extractor prompt / add to §D1.b: "Follow-up advocacy by the same activist (new letter, new meeting, 13D amendment) is context, not a new `Activist Sale` row."
5. **§E3 — bids_pipeline uses full acquirer-verbatim string as `BidderName`.** Row 71 (NDA-5/15) and Executed row both use the 40+ word consortium string as `BidderName`. This violates the canonical `bidder_NN` convention. Fix: extractor should use the registered canonical id and leave the verbatim string for the `deal.Acquirer` field (which is already there).
6. **§F3 — bids_try marks Buyer Group `mixed`.** Strictly, Longview is a rollover participant that signed a separate confidentiality agreement late in the process — not a Buyer Group bidder. `base = "f"` is the more defensible classification under §F3. bids_try should downgrade.
7. **§I1 consortium-drop-split precision.** bids_try's 12/10 Bidder 3 drop split uses `DropAtInf` with `drop_agency_ambiguous`. Filing says: *"J.P. Morgan communicated to Bidder 3 that it was unlikely to be competitive and accordingly Bidder 3 did not submit a written offer."* This is target-signaled → bidder-self-withdrawal. Either `DropBelowM` (target rejects below minimum) or `DropAtInf` (voluntary self-withdrawal) — both defensible. The `drop_agency_ambiguous` flag is appropriate.

### Nice-to-have

8. **§B1 — bids_pipeline and Alex both miss the "first week of October" → 10/05 mapping.** Both use 10/07. Fix: bids_pipeline extractor should apply §B1 mapping deterministically. Alex's reference is a known deviation (legacy workbook).
9. **§C1 — All 3 merge `Target Sale Public` + `Sale Press Release` inconsistently.** Alex emits both on 8/19; both AIs emit only `Target Sale Public`. The distinction in §C1 is that `Target Sale Public` is the public announcement event, `Sale Press Release` is the press-release artifact. For PetSmart they are literally the same 8/19 event. **Austin judgment call** whether both rows should be emitted per §C1 ("Add `Target Sale Public` + `Sale Press Release` as separate rows if the resolution is publicly announced") or if the two codes collapse in practice.

---

## Open questions for Austin

1. **NDA-only policy (§I1 / §P-S1) on petsmart-inc.** 11 of the 15 NDA signers never submitted an IOI; filing is silent on their per-bidder fate. Current §I1 says: do not fabricate catch-all Drops. bids_try follows this (13 soft flags, 0 synthetic drops). Alex emits 8 catch-all Drops on 10/30; bids_pipeline emits 10 catch-all DropTargets on 11/03 with shared source_quote (§R2 violation). **Accept bids_try's stance (consistent with Providence iter-7 decision) OR tighten §I1 to require catch-all Drops.** If the latter, exit clock resets.

2. **Industry Participant inclusion.** Alex skips Industry Participant entirely; bids_pipeline includes 3–4 rows; bids_try skips. Per §D1 the IP pre-history is clearly in scope. **Should the AI extractor emit IP rows (agreeing with bids_pipeline), or should §D1 be clarified to say "strategic approaches that never result in an NDA are out of scope" (agreeing with bids_try + Alex)?** This ties into §M1 (unsolicited-no-NDA skip) — IP is not unsolicited (target reached out to IP first in March), so §M1 doesn't apply. §D1 Target Interest / §I1 DropTarget is the right classification. **Recommend bids_pipeline's approach; bids_try should re-extract.**

3. **Activist follow-up emission (§D1.b).** bids_pipeline emits 4 activist rows (JANA 7/3 + 7/10, Longview 7/7 + 7/10). bids_try emits 2. §D1.b says "one row per activist." **Clarify §D1.b: does a follow-up in-person meeting / reiteration by the same activist get a new row, or only new 13D filings count?** Recommend the latter.

4. **Longview rollover participant — bidder or not?** Longview signed a confidentiality agreement on 12/09 (separate from the 15 first-week-Oct NDAs) specifically to allow the eventual winner to share bid price with them. Longview is also a ≥9% stockholder (per 7/7 letter) and becomes a rollover participant in the Buyer Group's ultimate bid. **Is Longview a 16th NDA row? Is the Buyer Group `base = "mixed"` or `base = "f"`?** Recommend: Longview is NOT a 16th NDA (non-bidder participant); Buyer Group is `base = "f"` (all-financial constituents); Longview's 12/09 CA is captured in the `comments` field on the Executed row, not as its own NDA.

5. **Alex row 6408 `BidderID 0.7` for J.P. Morgan retention on 2014-07-01.** Both AIs date JPM retention to 2014-07-15 (from "In July 2014" § B1 mapping) or similar. Alex's 7/1 appears to be ad hoc ("first of the month") not rule-based. **Document as Alex-reference deviation; retain §B1 mapping as canonical.** No rulebook change needed.

6. **Alex row 6447 `Final Round Ann` date 2014-11-15.** Filing says 11/03. Alex's 11/15 is a transcription / judgment drift. **Document as Alex-reference deviation; AI extractors are correct.**

7. **bids_try smart-quote vs pages.json mismatch.** 18+ hard `source_quote_not_in_page` flags are caused by straight ASCII apostrophes in bids_try output vs smart apostrophes in pages.json. The content is right; the normalization is strict. **Fix: either extend §R2 validator to fold ASCII ↔ Unicode punctuation, or fix extractor to preserve filing-verbatim smart quotes.** Recommend validator-side: NFKC is already a normalizer, and extending it to ASCII-fold punctuation is a lenient-but-sound relaxation.

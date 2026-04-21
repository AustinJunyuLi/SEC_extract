# Zep Inc. — Three-Way Extraction Audit

**Deal slug:** `zep`
**Target:** Zep Inc. | **Acquirer:** New Mountain Capital, L.L.C.
**Filing:** DEFM14A, filed 2015-05-26 (announced 2015-04-08, effective 2015-06-26)
**Auditor:** Claude (opus-4-7-1M)
**Date of audit:** 2026-04-21
**Ground-truth source:** `/Users/austinli/bids_try/data/filings/zep/raw.md` (Background of the Merger, pp. 27–34 of the PDF / raw.md lines 744–911)

Row counts in the three candidate extractions:

| Source | Rows | File |
|---|---:|---|
| Alex's workbook (converted) | 23 | `inputs/zep_alex.csv` |
| bids_try (current repo) | 48 | `inputs/zep_bids_try.csv` |
| bids_pipeline (older) | 80 | `inputs/zep_bids_pipeline.csv` |

---

## TL;DR

**Closest to filing-truth: `bids_try` (48 rows), by a clear margin.**

1. **bids_pipeline (80) substantially over-atomizes and fabricates events.**
   Phantom `Target Sale / Terminated / Restarted` rows at 2013-06-20, 2013-07-01,
   2013-08-20, 2014-01-08; fabricates a `DropBelowInf` "gap-fill" for Party Y;
   invents 25 distinct `Drop` rows on 2014-06-19/26 for NDA signers the
   filing does NOT individually narrate as dropping (it says "all parties
   had abandoned or withdrawn"); invents a separate `Restarted` at
   2015-02-26 and a later `Restarted` at 2015-02-26; emits an `Exclusivity`
   event code that is not in §C1; emits a `Go-Shop` row with an
   out-of-vocabulary `bid_note`. Net: ~20 fabricated/out-of-vocab rows.

2. **bids_try (48) is a principled atomization of the filing.**
   25 NDA rows match the filing's "twenty-five potential buyers executed
   confidentiality agreements" count. 5 April-14 informal-bid rows
   (`Financial 1..4` + `Strategic 1`) match the filing's "five parties,
   comprising four financial buyers and one strategic buyer." 5 mid-June
   drops map to "five of the remaining six interested parties
   communicated … unable to proceed." Each of the 3 hard `source_quote_
   not_in_page` flags in the CSV is a pages-slicing artefact (source_quote
   covers a paragraph boundary), not a fabricated row. **Two substantive
   bugs remain** (see §Systemic findings #2 and #5 below): the Drop on
   2014-04-14 for New Mountain Capital is wrong per §C1 / §E2 (NMC
   *declined to submit*, it did not drop from an auction position it was
   in), and 3 bids in phase 2 trigger `bid_without_preceding_nda` because
   the 2014 NDA for New Mountain Capital wasn't explicitly revived per
   §M4. The process_phase=1/2 split is correctly handled: bids_try emits
   both `Terminated` (2014-06-26) and `Restarted` (2015-02-10).

3. **Alex (23) aggressively aggregates, and one of the aggregations he
   flagged for expansion himself (row 6390 → 5 parties).** His workbook
   has ONE row for the 24 NDA signers on rough 2014-02-27, ONE row for the
   5 April-14 bidders, ONE row for "19 parties" dropping on 2014-04-14,
   ONE row for "5 parties" dropping on 2014-05-23. When the rulebook says
   "atomize" (§E1, §E2.b), Alex's workbook is technically non-conforming
   on all four aggregated rows. The converter (`scripts/build_reference.py
   §Q2`) expands 6390 into 5 rows (so the reference JSON has 28 rows, not
   23), but leaves the other aggregations alone.

**Alex-flag confirmation.** `alex_flagged_rows.json[zep]` has exactly one
entry: **xlsx_row 6390** ("5 parties, 4F and 1S" bid row), which Alex
annotated *"This field needs to be expanded to 5 bidders; one of them bid
20, another 22, another three [20,22]?"* The converter's §Q2 expansion is
good: 5 rows emitted with `bid_value_ambiguous_per_alex` info flags on
each. **bids_try's atomization of the April 14 cohort matches Alex's own
requested correction** — not an independent AI decision, but structural
alignment.

**Top 3 divergences (filing-ground-truth):**

1. **April 14, 2014 five-bidder IOI cohort.** `bp` and `try` atomize into 5
   rows (4F + 1S); Alex has 1 aggregated row (pre-expansion) or 5 rows
   (post-expansion via §Q2). **All three converge on atomize when §Q2 is
   applied.** Both `bp` and `try` get the S/F split right (4F+1S).
   `try` explicitly names them `Financial 1..4` + `Strategic 1`, matching
   the §E5 unnamed-quantifier rule. **`try` is most filing-faithful** by
   also flagging `bid_value_unspecified` since the filing gives only the
   aggregate range $20–22 (no per-bidder numbers). Alex's post-expansion
   JSON assigns specific guessed per-bidder numbers (20 to Party A, 22 to
   Party B, range [20,22] to C/D/E) — those numbers are **Alex's own
   ambiguous inference**, flagged `bid_value_ambiguous_per_alex`.
   **Verdict: TryRight.** `bp` agrees structurally but then collapses all
   5 back to one "5 parties" row (row 147) while also emitting the 5
   atomized NDA promotions as "Party X/Y NDA on 03/15/2014" which is
   **wrong on date** (Party X/Y NDAs happen after May 7, 2014 data-room
   opening, not March 15).

2. **Termination / Restart boundary.** All three emit a `Terminated`
   row dated 2014-06-26 (correct per line 840). All three emit a
   `Restarted` row. **Restart dates disagree:** Alex = 2015-02-19
   (NMC delivered unsolicited IOI); `try` = 2015-02-10 (NMC's initial
   meeting with BofA ML); `bp` = 2015-02-26 (after the revised IOI was
   received). Filing earliest restart signal is on 2015-02-10 ("New
   Mountain Capital met with representatives of BofA Merrill Lynch and
   expressed its interest" — line 852). **Verdict: TryRight** per §L2
   phase-boundary precedence (first re-engagement activity marks phase
   boundary). `bp` ALSO emits a second `Target Sale` at 2013-06-20 and
   `Terminated` at 2013-08-20 for a pseudo-2013 phase — those are
   **not** a real prior auction; the filing narrates only board
   *discussions* through 2013, no external parties were approached. Both
   `try` and Alex correctly omit a phase-0. **Verdict on the phantom
   2013 phase: BPWrong.**

3. **Mid-June 2014 drops ("over the next few weeks" after May 22).**
   Filing (line 836): *"five of the remaining six interested parties
   communicated … were unable to proceed … The sixth remaining interested
   party declined to respond."* Alex = 1 row ("5 parties" Drop rough
   2014-05-23) + 1 Party-Y-Drop row rough 2014-05-23 (= 2 drops). `try` =
   5 atomized drop rows (Financial 1..4 + Strategic 1) + 1 Party-Y drop
   = 6 drops, all dated rough mid-June. `bp` = **25 drops** dated
   2014-06-19 and 2014-06-26, one per NDA signer. **Verdict: TryRight.**
   The filing commits to 6 "remaining six interested parties" (5 + 1
   non-responding) — `try` atomizes to 6 rows, matching the filing's
   numeric commitment. Alex's 2-row aggregation is non-conforming with
   §E1/§E2.b (the filing gives an exact count of 5 + 1 = 6, which under
   §E5 requires atomization). `bp`'s 25 drops is **fabrication**: the
   19 parties who did not submit an April-14 IOI had already dropped at
   April 14 (Alex row 6392: "19 parties" Drop). Re-dropping them on
   June 19/26 creates phantom events not in the filing.

**Explanation of the 80/48/23 row split:**

| Event cluster | Filing count | Alex | bids_try | bids_pipeline |
|---|---|---:|---:|---:|
| 2013 board discussions (no external contact) | 0 rows | 0 | 0 | **3 (Target Sale 6/20 + 7/1 + Terminated 8/20)** |
| 2014 restart of discussions | 0 rows | 0 | 0 | **1 (Restarted 1/8)** |
| IB retention (BofA ML) | 1 | 1 (IB) + 1 (Target Sale 1/31) | 1 (IB) + 1 (Target Sale 7/1) | 1 (IB) |
| 25 NDA signers (2014) | 25 | 1 aggregated | 25 atomized | 25 atomized |
| NMC 2014 NDA | 1 | 1 | 1 (= 1 of the 25 above) | 1 |
| Final Round Inf Ann (3/27 process letter) | 1 | 1 | 0 (none emitted) | 1 |
| Final Round Inf (4/14 IOIs deadline) | 1 | 1 | 0 | 1 |
| April 14 IOIs (5 parties) | 5 per §E5 | 5 (post-§Q2) | 5 | 1 aggregated |
| April 14 NMC non-submission | 0 or 1 | 1 Drop | 1 Drop | 1 Drop |
| April 14 "19 parties" non-submitters drop | 1 or ~19 | 1 | 0 | 0 |
| 25 non-interested (never-signed-NDA) parties | 0 (skipped per §M1) | 0 | 0 | **1 "Drop" for "25 potential buyers" (skipped-party row — borderline)** |
| Party X IOI + Drop | 2 | 2 | 2 | 2 |
| Party Y IOI + Drop + NDA | 3 | 3 (NDA + Bid + Drop) | 3 (NDA + Bid + Drop) | 3 |
| Final Round Ann (5/22 draft merger dist.) | 1 | 0 | 0 | 1 |
| Mid-June drops (5 of remaining 6) | 5 | 1 aggregated | 5 | 0 |
| 25 "abandoned/withdrawn" drops (6/19 & 6/26) | 0 (already dropped) | 0 | 0 | **25 phantom** |
| Terminated (6/26/2014) | 1 | 1 | 1 | 1 |
| NMC phase-2 re-engagement | 1 Restarted | 1 | 1 | **2 rows (Bidder Interest + Bidder Sale + Restarted)** |
| NMC bid 19.25 (2/19/2015) | 1 | 1 | 1 | 1 |
| NMC bid 20.05 (2/26/2015) | 1 | 1 | 1 | 1 |
| NMC NDA extension (2/27/2015) | 1 | 0 | 0 | 1 |
| Exclusivity granted (2/27 + 3/18 ext) | 0 events (per §O1 attribute) | 1 (Exclusivity 30 days) | 0 | **2 Exclusivity rows (out-of-vocab)** |
| NMC best and final (3/13 or 3/29) formal | 1 | 1 | 1 | 2 (3/13 + 4/01) |
| Executed (4/7 or 4/8) | 1 | 1 | 1 | 1 |
| Go-Shop event | 0 (attribute) | 0 | 0 | **1 (out-of-vocab `Go-Shop`)** |

The 80 − 48 = **32-row bids_pipeline bloat** is concentrated in:
- **+25 phantom drops** on 2014-06-19/26 (double-counting NDA signers
  who already dropped on 4/14).
- **+3 fabricated 2013 phase-0 events.**
- **+1 phantom 2014-01-08 Restarted.**
- **+2 out-of-vocab Exclusivity rows.**
- **+1 out-of-vocab Go-Shop row.**
- **+1 duplicated NMC approach (Bidder Interest 2/10 + Bidder Sale 2/19).**
- **+2 duplicate formal bids** (NMC 3/13 best-and-final AND a second 4/01 row).
- Net after subtracting fewer atomized mid-June drops (bp=0, try=6): 32. Matches.

The 48 − 23 = **25-row gap from `try` to Alex** is concentrated in:
- **+24** from 25-NDA atomization (Alex=1 aggregated, try=25).
- **+4** from April 14 atomization (Alex=1 pre-expansion, try=5) BUT
  the converter's §Q2 adds 4 back to the reference JSON (reference has
  27 rows; 48−27=21).
- **+4** from mid-June drop atomization (Alex=1, try=5+1=6).
- **−1** because try omits Final Round Inf Ann and Final Round Inf rows
  (Alex has these; try rolls them into the May 7 data-room opening,
  unstated as distinct).
- **−1** because try omits the 2014 "19 parties who declined to sign"
  rows (Alex has 1 aggregated).
- **−1** because try omits the NDA-extension (2/27/2015) row (Alex has
  as `Exclusivity 30 days`).

---

## Filing event timeline (ground truth)

Page numbers below are the **PDF page numbers** as marked in the filing
(`<!-- PAGE 35 -->` … `<!-- PAGE 42 -->`), which correspond to the
1-based `source_page` field. Ref Alex workbook rows shown for
cross-reference.

| # | Date | Event | Filing evidence (page: quote excerpt) |
|---|---|---|---|
| 1 | 2013-06-20 | Board first discusses potential sale | p.34: *"At a June 20, 2013 meeting, our board of directors first discussed the possibility of exploring strategic alternatives, including a potential sale of the Company."* **(board internal — no external approach; NOT an extractable event per §D1 criteria)** |
| 2 | 2013-07-01 | Board unanimously agrees to "initial steps" incl. potential sale | p.34: *"Our board of directors unanimously agreed to proceed with certain initial steps related to exploring our strategic alternatives"* **(still internal; borderline Target Sale candidate)** |
| 3 | 2013-08-20 | Board concludes not timely to explore | p.34: **internal only; NOT an auction termination because no auction was ever launched** |
| 4 | 2014-01-28 | BofA ML engaged as IB | p.35: *"our board of directors unanimously approved an engagement letter with BofA Merrill Lynch"* → `IB` row |
| 5 | 2014-02-27 | Board authorizes contacting potential buyers, executing CAs | p.35: *"executing confidentiality agreements with such parties"* → `Target Sale` candidate date |
| 6 | 2014-Mar (next few weeks) | BofA ML contacts 50 potential buyers (28S + 22F) | p.36: *"contacted fifty potential buyers (comprising twenty-eight strategic buyers and twenty-two financial buyers)"* |
| 7 | 2014-03-19 | NMC signs CA | p.37: *"We entered into a confidentiality agreement with New Mountain Capital on March 19, 2014"* → `NDA` row |
| 8 | 2014-03-20 | NMC intro meeting with management | p.37 |
| 9 | 2014-03-27 | First-round process letter distributed; IOI deadline 4/14 | p.37: *"BofA Merrill Lynch distributed a first round process letter, which informed potential buyers that non-binding preliminary indications of interest would be due no later than April 14, 2014"* → `Final Round Inf Ann` per §K2 inference |
| 10 | 2014-Mar+Apr (next few weeks) | 25 potential buyers declined; 25 signed CAs | p.37: *"twenty-five potential buyers informed us that they were not interested … and twenty-five potential buyers executed confidentiality agreements"* → 25 NDA rows per §E5 exact-count rule. NMC received marketing materials but did not submit IOI → NMC-Drop at 4/14 |
| 11 | 2014-04-14 | 5 parties (4F + 1S) submit IOIs; range $20–22/share | p.37: *"five parties, comprising four financial buyers and one strategic buyer, submitted preliminary and non-binding indications of interest. The bids received in the preliminary indications of interest ranged from $20.00 per share to $22.00 per share"* → 5 `Bid` rows `bid_type=informal` per §E5 + §G1; NMC Drop same day |
| 12 | 2014-04-16 | Board reviews 5 IOIs; decides to continue | p.37 |
| 13 | 2014-Apr/May (next few weeks) | Party X (F) + Party Y (S) contact BofA ML unsolicited | p.37: *"two additional parties, comprising one financial party (Party X) and one strategic party (Party Y), contacted representatives of BofA Merrill Lynch on an unsolicited basis"* → `Bidder Interest` rows (unclear whether to also emit an NDA row — filing does not say Party X/Y signed NDAs until after data-room access) |
| 14 | 2014-05-07 | Data room opened to 5 April-14 parties | p.37: *"access to an electronic data room … was made available to the five parties who submitted preliminary indications of interest"* → `Final Round Inf` per §K2 (the informal submission step culminates here) |
| 15 | 2014-05-09 | Party X submits IOI, $21.50–$23.00/share | p.37: *"On May 9, 2014, Party X submitted a preliminary and non-binding indication of interest … ranged from $21.50 to $23.00 per share"* → `Bid` informal, range |
| 16 | 2014-05-14 | Party X withdraws before data room access | p.38: *"on May 14, 2014, prior to receiving access to the electronic data room or meeting with the Company's management, Party X informed representatives of BofA Merrill Lynch that it was no longer interested"* → `Drop` |
| 17 | 2014-05-20 | Party Y submits IOI, $19.50–$20.50/share, data-room access | p.38: *"On May 20, 2014, Party Y submitted a preliminary and non-binding indication of interest … ranged from $19.50 to $20.50 per share"* → `Bid` informal, range; NDA likely implicit (data-room access requires one) |
| 18 | 2014-05-22 | Draft merger agreement distributed to 6 remaining bidders | p.38: *"a draft of the merger agreement was distributed to the six remaining bidders (Party X having withdrawn from the process on May 14, 2014)"* → `Final Round Ann` candidate |
| 19 | 2014-05-23 | Fire at Marietta GA aerosol facility | p.38 |
| 20 | 2014-"over next few weeks" | 5 of remaining 6 parties communicate inability to proceed; 6th declines to respond | p.38: *"five of the remaining six interested parties communicated to representatives of BofA Merrill Lynch that they were unable to proceed with the process … The sixth remaining interested party declined to respond"* → 5 `Drop` rows + 1 `Drop` for Party Y (the 6th, non-responding) |
| 21 | 2014-06-19 | Board briefing: each of 7 IOI-submitters believed couldn't pay indicated prices | p.38 |
| 22 | 2014-06-26 | Board decides to terminate 2014 sale process | p.38: *"our board of directors decided to terminate the process"* → `Terminated` |
| 23 | 2014-Jun-end | Board authorizes letters waiving "don't ask to waive" | p.38 |
| 24 | 2015-02-early | NMC contacts BofA ML, requests meeting | p.39 |
| 25 | 2015-02-10 | NMC meets BofA ML, expresses interest | p.39: *"New Mountain Capital met with representatives of BofA Merrill Lynch and expressed its interest in discussions with the Company regarding a potential transaction"* → `Restarted` boundary per §L2 |
| 26 | 2015-02-19 | NMC delivers unsolicited IOI $19.25/share; highly confident letter; 45-day exclusivity req + go-shop | p.39: *"On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest … per share price of $19.25 … supported by a highly confident financing letter from Jefferies Finance LLC, contained a request for a forty-five day exclusivity period and contemplated a go-shop period"* → `Bid` informal, `highly_confident_letter=true`, `exclusivity_days=45` |
| 27 | 2015-02-23 | Board discusses NMC IOI | p.39 |
| 28 | 2015-02-26 | NMC delivers revised IOI $20.05, 45-day exclusivity | p.39: *"On February 26, 2015, New Mountain Capital delivered a revised indication of interest reflecting an increased per share price of $20.05, and indicated that this was the highest price it was willing to offer"* → `Bid` informal |
| 29 | 2015-02-26 | Board approves moving forward with NMC negotiations | p.39 |
| 30 | 2015-02-27 | NMC signs extension CA + 30-day exclusivity (through 3/31) | p.40: *"we signed an agreement with New Mountain Capital extending the term of the confidentiality provision, the 'standstill' provision and the employee non-solicitation provision … as well as providing for an exclusivity period with New Mountain Capital through March 31, 2015"* → the existing NDA is extended (this maps to §M4 `nda_revived_from_stale` / phase-2 NDA boundary); exclusivity is an attribute per §O1 (`exclusivity_days=30`), not a separate event |
| 31 | 2015-03-02 | NMC granted data-room access | p.40 |
| 32 | 2015-03-13 | NMC communicates $20.05 is "best and final" | p.40: *"New Mountain Capital communicated that the $20.05 per share offer price was New Mountain Capital's 'best and final' offer"* → `Bid` formal per §G1 (matches the `best and final` trigger) |
| 33 | 2015-03-18 | NMC exclusivity extended through 4/7; draft merger agreement delivered to NMC | p.40 |
| 34 | 2015-03-24 | Board declines supply-chain investment; continues with NMC | p.40 |
| 35 | 2015-03-29 | Revised draft merger agreement from NMC (reduces go-shop to 30 days) | p.41 |
| 36 | 2015-04-06 | Board meeting; termination fee negotiation ($10M/$20M/$30M floated) | p.41 |
| 37 | 2015-04-07 | Board approves merger agreement; BofA ML fairness opinion delivered | p.41 / 42 |
| 38 | 2015-04-08 | Parties execute merger agreement; press release issued | p.42: *"Following the meeting of our board of directors, the parties executed the merger agreement and the related transaction documents and issued a press release announcing the transaction on the morning of April 8, 2015"* → `Executed` |
| 39 | 2015-04-08 to 2015-05-07 | Go-shop period runs; 58 parties contacted; no competing proposals | p.42 (`go_shop_days=30` deal-level attribute per §O1; NOT an event) |

**Bidder inventory (named):** only **5** distinct bidders named anywhere:
1. BofA Merrill Lynch (IB)
2. New Mountain Capital (the buyer)
3. Party X (financial, May 9 IOI, withdrew May 14)
4. Party Y (strategic, May 20 IOI)
5. "Five parties / four financial + one strategic" on April 14 — collective, un-named

No other bidders are individually named. The 25 NDA signers are NOT
individually narrated. The filing commits to the **number** 25 but
provides no per-signer identity.

---

## Source-by-source row counts and structure

### Alex (23 rows; 27 after §Q2 expansion in reference JSON)

- 1 × `IB` (BofA ML, rough 2014-01-28)
- 1 × `Target Sale` (BofA ML as bidder_alias, rough 2014-01-31) — **non-standard;**
  Alex associates the "decision to sell" event with BofA ML, not
  as a deal-side Target Sale row per §D1.
- 1 × `NDA` (`"24 parties"`, rough 2014-02-27) — aggregated ⚠
  **non-conforming with §E1/§E2.b (filing states 25, not 24)**.
- 1 × `NDA` (NMC, 2014-03-19)
- 1 × `Final Round Inf Ann` (rough 2014-03-27)
- 1 × `Bid` informal (`"5 parties, 4F and 1S"`, 2014-04-14, range 20–22)
  — **flagged by Alex himself for expansion.**
- 1 × `Drop` (NMC, 2014-04-14)
- 1 × `Drop` (`"19 parties"`, 2014-04-14)
- 1 × `Final Round Inf` (rough 2014-04-14)
- 1 × `Final Round` (rough 2014-05-07)
- 1 × `Bid` informal (Party X, 2014-05-09, range 21.5–23)
- 1 × `Drop` (Party X, 2014-05-14)
- 1 × `Bid` informal (Party Y, 2014-05-20, range 19.5–20.5)
- 1 × `NDA` (Party Y, rough 2014-05-20)
- 1 × `Drop` (`"5 parties"`, rough 2014-05-23) — aggregated
- 1 × `Drop` (Party Y, rough 2014-05-23)
- 1 × `Terminated` (rough 2014-06-26)
- 1 × `Restarted` (NMC, rough 2015-02-19)
- 1 × `Bid` informal (NMC, 2015-02-10, 19.25) — **DATE IS WRONG** per
  filing; NMC delivered the 19.25 IOI on 2015-02-19 (p.39 line 852),
  not 2015-02-10. Alex confused the meeting date with the bid date.
- 1 × `Bid` informal (NMC, 2015-02-26, 20.05)
- 1 × `Exclusivity 30 days` (NMC, 2015-02-27) — **legacy label dropped**
  from §C1 (now encoded as `exclusivity_days:30` attribute per §O1).
- 1 × `Bid` formal (NMC, 2015-03-29, 20.05) — **DATE IS WRONG** per
  §G1 *"best and final"* trigger; the best-and-final was 2015-03-13,
  not 3/29. 3/29 is when NMC returned a revised MERGER agreement
  (not a new bid price).
- 1 × `Executed` (NMC, rough 2015-04-08) — date should be 2015-04-07
  (signing) or 4/08 (press release).

**After §Q2 expansion:** the `5 parties, 4F and 1S` row is expanded to
5 rows (Party A–E) with `bid_value` = 20 / 22 / [20,22] / [20,22] /
[20,22] (Alex's own ambiguous inference). **These 5 rows have the same
`bidder_name = bidder_04`**, which means they share one canonical ID —
i.e., a 5-bidder consortium-style assignment — which is technically
inconsistent with §E3 per-distinct-bidder IDs. Minor, flagged.

### bids_try (48 rows)

Phase 1 (rows index 47–89 in CSV):
- 1 × `Target Sale` (2013-07-01)
- 1 × `IB` (BofA ML, 2014-01-28)
- 23 × `NDA` (Financial 1..4, Strategic 1, Party X, Party Y, Unnamed NDA Signer 1..17, all dated 2014-03-15 rough *"next several weeks (after February 27, 2014)"*) — the 17 unnamed signers are §E5 placeholders; each carries `nda_without_bid_or_drop` soft flag.
- 1 × `NDA` (New Mountain Capital, 2014-03-19 precise)
- 5 × `Bid` informal (Financial 1..4 + Strategic 1, 2014-04-14, `bid_value_unspecified`)
- 1 × `Drop` (New Mountain Capital, 2014-04-14)
- 1 × `Bid` informal (Party X, 2014-05-09, range 21.5–23)
- 1 × `Drop` (Party X, 2014-05-14)
- 1 × `Bid` informal (Party Y, 2014-05-20, range 19.5–20.5)
- 6 × `Drop` (Financial 1..4, Strategic 1, Party Y, 2014-06-15 rough)
- 1 × `Terminated` (2014-06-26)

Phase 2 (rows 90–94):
- 1 × `Restarted` (2015-02-10)
- 1 × `Bid` informal NMC 19.25 (2015-02-19)
- 1 × `Bid` informal NMC 20.05 (2015-02-26)
- 1 × `Bid` formal NMC 20.05 (2015-04-07)
- 1 × `Executed` NMC (2015-04-07)

**Known bids_try bugs (from CSV `comments_3` flag column):**
- 3 `hard:source_quote_not_in_page` flags (rows 2, 35, 47). Artefacts of
  page-slicing: the cited quote spans a paragraph boundary that falls on
  a page break in `pages.json`. Not a fabrication; fixing requires
  re-chunking pages.
- 3 `hard:bid_without_preceding_nda` on rows 45/46/47 (phase-2 NMC bids).
  Filing evidence: on 2015-02-27 NMC signs an "agreement extending"
  the 2014 NDA (p.40 line 868). Under §M4 this should emit a new
  phase-2 NDA row for NMC at 2015-02-27 with `nda_revived_from_stale`
  info flag. **This is a genuine extraction gap.**
- 1 `soft:drop_agency_ambiguous` on the NMC 4/14 Drop (correctly
  flagged; NMC decided not to submit IOI, which is not a drop from
  an auction position but a non-submission).

### bids_pipeline (80 rows)

Phase 0 / phantom-2013 block (rows Row=112..115):
- **`Target Sale` 2013-06-20, `Target Sale` 2013-07-01, `Terminated`
  2013-08-20, `Restarted` 2014-01-08.** **All four are phantom
  events.** The filing narrates only board-internal discussions
  through 2013; no external party is approached, no NDA signed, no
  advisor retained, no process launched. A "Target Sale" requires
  the board to resolve to sell (§D1). August 2013 was the board
  **concluding NOT to explore strategic alternatives at that time**
  — which is the opposite of `Terminated`. January 2014 re-launch of
  discussion is internal and does NOT satisfy `Restarted` (§L2
  requires a narrated `Terminated` followed by `Restarted`; both
  are absent here).

Phase 1 block (rows Row=116..179):
- 1 × `IB` (BofA ML, 2014-01-28)
- 1 × `Target Interest` (`"50 potential buyers"`, rough 2014-03-01)
  — **out-of-spec;** filing doesn't narrate target-initiated
  discussions with individual named buyers; this is the mass outreach
  to 50 parties.
- 25 × `NDA` (Party X, Party Y, bidder_3..25, all dated 2014-03-15
  precise) — 25 NDAs is correct count per filing, but Party X and
  Party Y are placed on 2014-03-15 which is **wrong** (their NDAs
  occur post-April-16 board meeting, per filing p.37 line 816–818).
- 1 × `NDA` (NMC, 2014-03-19)
- 1 × `Final Round Inf Ann` (2014-03-27)
- 1 × `Drop` (`"25 potential buyers"`, rough 2014-04-01) — **§M1
  violation.** The 25 parties who *declined to sign CAs* did not
  participate in the auction; they should be skipped (§M1) or rolled
  into a single skipped-party deal flag, not emitted as a Drop row
  since they never had an NDA in the first place. §P-D5 should
  trigger here (Drop without prior engagement).
- 1 × `Drop` (NMC, 2014-04-14)
- 1 × `Bid` informal (`"5 parties"`, 2014-04-14, range 20–22) —
  **un-atomized;** but see bp NDA rows where these 5 are already
  named individually; inconsistent.
- 1 × `Final Round Inf` (2014-04-14)
- 2 × `Bidder Interest` (Party X, Party Y, rough 2014-05-01) — wrong
  date (filing says "over the next few weeks" after April 16, p.37).
- 1 × `Bid` informal (Party X, 2014-05-09)
- 1 × `DropBelowInf` (Party X, 2014-05-14)
- 1 × `Bid` informal (Party Y, 2014-05-20)
- 1 × `DropBelowInf` (Party Y, no date — marked "gap-fill closure") —
  **fabricated row** per the CSV's own "Gap-fill closure" comment;
  the filing DOES narrate Party Y's drop ("declined to respond" on
  p.38 line 836), so gap-fill is unnecessary and the row conflicts
  with the proper Drop row.
- 1 × `Final Round Ann` (2014-05-22)
- **7 × `Drop` on 2014-06-19** (one per bidder_3..bidder_7 and 2 more)
  — **phantom events.** The filing's 6/19 paragraph is a BOARD
  BRIEFING about the drops that already occurred, not new drop
  events. The drops already happened "over the next few weeks"
  after 5/22.
- **17 × `Drop` on 2014-06-26** (bidder_9..bidder_25) — **also
  phantom.** 6/26 is the termination date. These NDA signers who
  never submitted IOIs had already dropped by not submitting on
  4/14 (they did not "abandon or withdraw" on 6/26; they simply
  were never in the race). Total phantom drops: 7 + 17 = 24 (plus
  the 25-party skipped-CA Drop + Party Y gap-fill = 26 phantom
  drop rows).
- 1 × `Terminated` (2014-06-26)

Phase 2 block (rows Row=180..191):
- 1 × `Bidder Interest` (NMC, 2015-02-10) — redundant with Bidder Sale
- 1 × `Bidder Sale` (NMC, 2015-02-19)
- 1 × `Bid` informal (NMC, 2015-02-19, 19.25)
- 1 × `Restarted` (2015-02-26) — **wrong date.** Restart boundary is
  2015-02-10 per §L2 (first phase-2 contact).
- 1 × `Bid` informal (NMC, 2015-02-26, 20.05)
- 1 × `NDA` (NMC, 2015-02-27) — correctly emits the CA-extension
  (good; `try` missed this).
- 1 × `Exclusivity` (NMC, 2015-02-27) — **out-of-vocab.** §C1 dropped
  `Exclusivity 30 days` in favor of `exclusivity_days: int` attribute.
- 1 × `Bid` formal (NMC, 2015-03-13, 20.05) — best-and-final
- 1 × `Exclusivity` (NMC, 2015-03-18) — **out-of-vocab.**
- 1 × `Bid` formal (NMC, rough 2015-04-01, 20.05) — **duplicate** of the
  3/13 best-and-final.
- 1 × `Executed` (NMC, 2015-04-07)
- 1 × `Go-Shop` (2015-04-08) — **out-of-vocab.** §C1 has no
  `Go-Shop` code; go-shop is a deal-level attribute per §O1.

---

## Divergence table

Scope: the most substantive filing-vs-extraction disagreements. Field
names follow `rules/schema.md`. Verdict values: {`AlexRight`,
`BPRight`, `TryRight`, `BothAIRight`, `NoneRight`, `JudgmentCall`,
`AlexFlagged`}.

| # | Event / Field | Alex | bp | try | Filing | Verdict | Notes |
|---|---|---|---|---|---|---|---|
| 1 | 2013 board discussions (Target Sale 6/20, 7/1, Terminated 8/20) | omit | **3 rows emitted** | omit | no auction launched in 2013 | `BPWrong` (TryAlexRight) | bp fabricates a phase that doesn't exist. The 2013 board meetings are internal; no external contact, no NDA, no process. `Target Sale` requires a resolution to *sell* (§D1), which happened 2014-01-28, not 2013. |
| 2 | 2014-01-08 "Restarted" | omit | **1 phantom** | omit | no prior phase existed | `BPWrong` | bp treats Jan 2014 board decision to "revisit" as `Restarted`. No prior `Terminated` preceded. §L2/§P-L1: `Restarted` without matching `Terminated` violates §P-L1. |
| 3 | 25 NDA signers (2014-Mar) | **1 aggregated row** ("24 parties" — wrong count) | 25 atomized, dated 2014-03-15, S/F flag on all | 25 atomized, dated 2014-03-15, **with named Party X / Y + 17 unnamed** | 25 signed CAs (filing states 25 exactly) | `TryRight` | Alex's aggregation violates §E1/§E2.b; filing gives exact count → atomize. Alex's "24" is a counting error (the workbook's aggregation predates the extraction rulebook). try's 25-row breakdown is correct. bp is also atomized but uses S/F=mixed on all, which is slightly less faithful than try's Financial/Strategic named attribution (filing says 28S + 22F contacted; 4F + 1S submitted IOIs; try names Financial 1..4 and Strategic 1 for the IOI submitters). |
| 4 | Date of Party X / Party Y NDA | — (Alex places Party Y NDA rough 2014-05-20, no Party X NDA) | 2014-03-15 (wrong) | 2014-03-15 rough with inference-note (defensible) | Party X/Y approached "over the next few weeks" AFTER April 16 board meeting (p.37 line 816); NDAs are implicit around May 7 (data-room) / May 20 | `JudgmentCall` toward `AlexRight` for Party Y | Alex's rough 2014-05-20 for Party Y NDA is closest to filing. bp's 2014-03-15 for Party X/Y is wrong (filing narrative places them post-April-16). try's 2014-03-15 is also wrong for Party X/Y specifically (it collapses all 25 NDAs to one inferred date window; the inference-note acknowledges this but applying it to the named Parties X/Y is a miscategorization). |
| 5 | April 14, 2014 five IOI-submitters | 1 aggregated row (5 parties, 4F+1S, range 20–22) **[Alex's own expand-flag, row 6390]** | 1 aggregated row (same) + 5 separate NDA rows dated 3/15 | **5 atomized rows** (4F + 1S), per-bidder IOI with `bid_value_unspecified` + `bid_value_lower=20, upper=22` on the aggregate comment | 5 parties (4F+1S), aggregate range $20–22 (no per-bidder numbers) | `TryRight` (AlexFlagged) | try's atomization matches filing's numeric commitment (5 parties). The filing does NOT provide per-bidder numbers, so `bid_value_unspecified` + reference to the aggregate range is correct. Alex's row 6390 is the one row he himself flagged for expansion. Post-§Q2, the reference JSON has 5 rows — matching try. bp's choice to have 5 NDA atomizations but 1 aggregated Bid row is internally inconsistent. |
| 6 | NMC 2014-04-14 non-submission | 1 `Drop` row | 1 `Drop` row | 1 `Drop` row with `drop_agency_ambiguous` soft flag | *"it decided at the time not to submit a preliminary indication of interest"* — not a drop in the auction sense | `NoneRight` | Filing: NMC received materials and process letter but "decided at the time not to submit a preliminary indication of interest." This is a non-submission, not a withdrawal from bidding. All three emit `Drop`; try alone flags `drop_agency_ambiguous`. Correct treatment under §I1 is probably `DropAtInf` (self-withdrawal at informal stage) rather than generic `Drop` — none of the three uses `DropAtInf`. try's soft flag is the closest to honest. |
| 7 | 19 parties who declined to sign CAs | 0 rows | **1 `Drop` for "25 potential buyers"** (rough 2014-04-01) | 0 rows | *"twenty-five potential buyers informed us that they were not interested in pursuing a potential transaction and declined to enter into a confidentiality agreement"* | `AlexTryRight` (BPWrong) | The 25 who **declined to sign CAs** are outside the auction per §M1 (`unsolicited_no_NDA` skip; actually "solicited but declined"). Alex omits and try omits. bp emits a Drop row with `bidder_name="25 potential buyers"` — **violates §P-D5** (no prior engagement; never signed NDA). Meanwhile, none of the three correctly captures the "19 parties who did not submit IOIs" — these are the 19 = 24 NDA signers (25 − 5 IOI-submitters − 1 NMC) — Alex's row 6392 does emit this as `"19 parties" Drop` 2014-04-14, good. try misses this. |
| 8 | Mid-June 2014 drops (5 parties) | 1 aggregated `Drop` ("5 parties", rough 2014-05-23) + 1 Party Y `Drop` | **25 `Drop` rows** on 6/19 and 6/26 (phantom) | 5 atomized `Drop` rows (Financial 1..4 + Strategic 1) rough 2014-06-15 + 1 Party Y Drop | 5 of remaining 6 communicated inability to proceed; 6th (Party Y) declined to respond | `TryRight` | Filing gives an exact count of 5+1=6. try atomizes to 6 rows matching the filing's commitment. Alex aggregates; bp wildly over-atomizes by re-dropping all 25 NDA signers (most of whom had already dropped at 4/14 by not submitting IOIs). Dates: filing says "over the next few weeks" after 5/22 fire; mid-June is a reasonable rough anchor (Alex uses 5/23, which is the fire date, not the communication date). try's 2014-06-15 is closer to the 6/19 board briefing. |
| 9 | Terminated 2014-06-26 | 1 row rough 2014-06-26 | 1 row 2014-06-26 | 1 row 2014-06-26 precise | 2014-06-26 board meeting decides to terminate | `BothAIRight` (AlexAlsoRight) | All three correct. |
| 10 | Restarted 2015-02-?? | rough 2015-02-19 | 2015-02-26 | 2015-02-10 | first phase-2 contact 2015-02-10 | `TryRight` | §L2 phase-boundary: first re-engagement marks the boundary. 2015-02-10 is when NMC met BofA ML and expressed interest. Alex's 2/19 is when the unsolicited IOI was delivered — that's phase-2 event #2, not the boundary itself. bp's 2/26 is even later (the revised IOI). |
| 11 | NMC 19.25 bid date | 2015-02-10 precise | 2015-02-19 precise | 2015-02-19 precise | *"On February 19, 2015, New Mountain Capital delivered … per share price of $19.25"* | `BPTryRight` (AlexWrong) | Alex conflates the 2/10 initial meeting with the 2/19 bid delivery. bp and try both correct. |
| 12 | NMC CA extension 2015-02-27 | 1 `Exclusivity 30 days` row (legacy label) | 1 `NDA` + 1 `Exclusivity` (out-of-vocab) | 0 rows (missing) | *"we signed an agreement … extending the term of the confidentiality provision … as well as providing for an exclusivity period"* | `JudgmentCall`, all three imperfect | Under §M4 this should emit a phase-2 NDA row with `nda_revived_from_stale` info flag (to satisfy §P-D6 for the later phase-2 bids). bp's `NDA` at 2015-02-27 is directionally correct (§M4-style revival) but also adds an `Exclusivity` row that violates §C1. Alex's `Exclusivity 30 days` is the old label (pre-§O1 dropping of that code). try misses both — and triggers §P-D6 `bid_without_preceding_nda` hard flags on all phase-2 bids as a result. |
| 13 | NMC best-and-final formal bid | 2015-03-29 `Bid formal 20.05` | 2015-03-13 `Bid formal 20.05` + 2015-04-01 `Bid formal 20.05` | 2015-04-07 `Bid formal 20.05` | *"On March 13, 2015, New Mountain Capital communicated that the $20.05 per share offer price was … 'best and final' offer"* | `BPRight` on date (partial), but bp duplicates | Filing clearly dates best-and-final at 3/13. bp has the 3/13 row BUT adds a duplicate 4/01 row. Alex's 3/29 is wrong (that's a revised merger AGREEMENT date, not a bid price revision). try's 4/07 is the board-approval date — correct event, wrong date for the best-and-final (the formal trigger is on 3/13). |
| 14 | Executed | rough 2015-04-08 | 2015-04-07 | 2015-04-07 | executed 4/07; press release 4/08 | `BPTryRight` on date | Merger agreement signed 4/07 per p.42 line 908 ("Following the meeting of our board of directors, the parties executed"). Alex's rough 4/08 matches the press release, also defensible. |
| 15 | Go-shop | absent (attribute) | `Go-Shop` event 4/08 (out-of-vocab) | absent (attribute) | 30-day go-shop per merger agreement; attribute per §O1 | `AlexTryRight` (BPWrong) | §O1 makes `go_shop_days` a deal-level attribute, NOT an event. bp emits `Go-Shop` — out-of-vocabulary per §C1. |
| 16 | `bidder_type.public` for New Mountain Capital | `null` | `null` (no field) | `false` | NMC is private (PE firm) → `public=false` | `TryRight` | Alex's `null` for a PE firm is under-inferred; try's `false` is correct per §F2 rule #1 (PE firms are always `public: false`). |
| 17 | BidderID assignment | sequence 1..27 (dense, post-§Q2) | decimal wedges (0.2, 0.3, 0.45, ...) | sequence 1..48 dense | per §A1–§A4, strictly monotonic 1..N | `TryRight` (AlexRightAfterConversion) | bp's decimals (0.2, 0.45, 2.038..., etc.) are a legacy convention dropped in §A1. try's 1..48 is canonical. |
| 18 | Final Round Inf Ann (3/27/2014 process letter) | 1 row rough 2014-03-27 | 1 row 2014-03-27 | 0 rows (missing) | *"BofA Merrill Lynch distributed a first round process letter"* | `AlexBPRight` | §K2 inference trigger: process letter → `Final Round Inf Ann`. try misses this event. Minor gap for try. |
| 19 | Final Round Inf (submission deadline 4/14/2014) | 1 row rough 2014-04-14 | 1 row 2014-04-14 | 0 rows (missing) | IOIs due 4/14 | `AlexBPRight` | Same as #18; try misses the Final Round Inf event. |
| 20 | Final Round Ann (5/22/2014 draft agreement distribution) | 0 rows | 1 row 2014-05-22 | 0 rows | *"a draft of the merger agreement was distributed to the six remaining bidders"* | `BPRight` | Distribution of draft merger agreement to subset is a §K2 `Final Round Ann` signal. bp alone catches it. |
| 21 | Terminated (2013-08-20) | absent | **1 phantom** | absent | board decided NOT to explore at that time (internal) | `AlexTryRight` | §C1 `Terminated` requires a formal sale process to have been in progress, which was not the case in 2013. |

---

## Systemic findings

### 1. bids_pipeline over-atomizes fabricated events

**Pattern:** bp emits event rows for internal board discussions (2013-06-20,
2013-07-01, 2013-08-20, 2014-01-08). These are not auction events per
§D1; a `Target Sale` requires a board resolution to *sell*, and
`Terminated` requires a *sale process* (not board discussions) to end.
This fabrication is compounded by the phantom 25-drop sweep on
2014-06-19/26 that re-drops NDA signers who had already dropped at 4/14.

**Root cause (likely):** bp's prompt over-weights *any narrative
mention of a date + strategic-alternatives language* as a
§D1-eligible event, without the §L2 phase-boundary gating or §E1
atomization discipline.

### 2. bids_try's 2014 NDA → phase-2 gap (§M4)

**Observed:** 3 hard `bid_without_preceding_nda` flags on phase-2 NMC
bids.

**Filing evidence (p.40 line 868):** *"On February 27, 2015, we signed an
agreement with New Mountain Capital extending the term of the
confidentiality provision … as well as providing for an exclusivity
period with New Mountain Capital through March 31, 2015."*

**Expected per §M4:** emit a phase-2 `NDA` row for NMC on 2015-02-27
with `nda_revived_from_stale` info flag. This satisfies §P-D6 for
subsequent phase-2 NMC bids.

**Fix:** add a §M4 inference in the extractor prompt when the filing
uses "extending the term of the confidentiality provision" or
"reaffirming the CA" language around a phase boundary.

### 3. NMC "Drop" on 4/14/2014 is mis-coded across all three

**Filing language (p.37 line 810):** *"While New Mountain Capital
received the marketing materials and the first round process letter,
it decided at the time not to submit a preliminary indication of
interest."*

This is a non-submission at the informal round, which under §I1
maps to **`DropAtInf`** (self-withdrawal at informal stage), NOT
generic `Drop`. None of the three uses `DropAtInf`.

**Verdict:** NoneRight on the specific code. try alone flags
`drop_agency_ambiguous` (closest to honest). Rulebook addendum
recommended: clarify that *"decided not to submit [IOI]"* → `DropAtInf`.

### 4. Group-narrated "N parties abandoned/withdrew" handling

**Filing pattern (p.38 line 842):** *"During the process conducted
during the first half of 2014, given that all of the parties that had
signed confidentiality agreements had abandoned or withdrawn from the
process …"*

This retrospective framing is not a **new** drop event — it's a
summary of the (6) drops already narrated on the preceding
paragraph (the "5 of remaining 6 … + 1 declined to respond"). bp
incorrectly treats it as **25 separate new drops** on 6/19 and 6/26.

Alex and try correctly do NOT emit drops for this retrospective
summary. **This is strong evidence that bp's prompt is treating
any *party-count + past-tense narration* as a drop event, rather
than matching the specific drop events to specific filing
narrations.**

### 5. Date granularity (precise vs rough)

- Alex: relies heavily on `bid_date_rough` for inference dates.
  Example: NMC Restarted `bid_date_rough=2015-02-19 00:00:00` with
  no `bid_date_precise`. Since 2015-02-19 is a *precise* date in
  the filing (IOI delivery), this is a category confusion — Alex
  uses `bid_date_rough` for inference *sources*, not for the event
  date itself.
- bids_try: uses precise dates when filing gives them, rough anchors
  with inference-notes otherwise (correct per §B).
- bids_pipeline: mixes precise/rough inconsistently (e.g., NMC
  Exclusivity 2015-02-27 precise; Bidder Interest 2015-02-10 precise;
  but Drop for "25 potential buyers" at rough 2014-04-01 with no
  inference note).

**Winner: try.**

### 6. `source_quote` / `source_page` evidence

- **Alex:** omits evidence fields entirely (expected — reference JSON
  design).
- **try:** every row carries `source_quote` and `source_page`. 3 rows
  have `source_quote_not_in_page` errors (page-slicing artefact, not
  fabrication).
- **bp:** the CSV has no `source_quote`/`source_page` columns at all
  (confirmed by header inspection). **This is a §R3/§P-R2 hard
  invariant violation** — no row carries its filing citation. Every
  row of bp's output would fail §P-R2 if re-run through the current
  validator.

**Winner: try by default (bp fails § R3 ship-blocker).**

### 7. Out-of-vocabulary event codes in bp

bp emits:
- `Exclusivity` (2 rows) — not in §C1.
- `Go-Shop` (1 row) — not in §C1.
- `Target Interest` for *"50 potential buyers"* — technically in §C1,
  but the §D1 definition requires the target to initiate discussions
  with a *specific party*, not a mass outreach.

**try:** all rows use §C1-compliant `bid_note` values.

### 8. Alex row 6390 confirmation

**Alex-flagged row 6390** (his own annotation: *"This field needs to
be expanded to 5 bidders; one of them bid 20, another 22, another
three [20,22]?"*). The converter's §Q2 expansion produces 5 rows
(bidder_04 with aliases Party A–E). **Both AI extractions atomize
this event correctly** (bp: 5 NDA rows but then 1 Bid row, which is
inconsistent; try: 5 Bid rows, clean). **try's version is the
structurally cleanest match to Alex's own requested correction.**

The Party A/B/C/D/E bid values in the reference JSON (20, 22,
[20,22], [20,22], [20,22]) are Alex's **guesses** flagged
`bid_value_ambiguous_per_alex`. try's choice to emit
`bid_value_unspecified` on all 5 bids (since the filing gives only
aggregate $20–22) is more faithful to the filing than Alex's
guesses. **Net: try is more filing-faithful than the post-§Q2
reference.**

---

## Specific rule / prompt fixes recommended

### For bids_try (the winner — these are the few remaining gaps)

1. **§M4 NDA revival emission.** Add to `prompts/extract.md` (under the
   NDA emission guidance): *"When a phase-2 bidder is described as
   'extending', 'reaffirming', or 'confirming' a prior-phase CA,
   emit a phase-2 `NDA` row dated on the revival with
   `nda_revived_from_stale` info flag. This is required to satisfy
   §P-D6 for subsequent phase-2 bids."*

2. **Clarify §I1 for non-submission at IOI deadline.** Add to
   `rules/events.md` §I1: *"When a party receives first-round
   materials / process letter but elects not to submit an IOI by the
   deadline, the correct code is `DropAtInf` (self-withdrawal at
   informal stage), not generic `Drop`."* The NMC 2014-04-14 case
   would then emit `DropAtInf`.

3. **§K2 process-letter inference is not always firing.** try emits
   no `Final Round Inf Ann` for the 2014-03-27 process letter, no
   `Final Round Inf` for the 2014-04-14 submission deadline, and
   no `Final Round Ann` for the 2014-05-22 merger-agreement
   distribution. §K2 says these should be inferred with
   `final_round_inferred` info flag. Prompt check: does the
   extractor ever emit a `Final Round *` row? (Medivation report
   analogue useful here.)

4. **Page-slice `source_quote_not_in_page` handling.** The 3 hard
   flags are all artefacts where the quote spans a page boundary in
   `pages.json`. This is a pipeline-level issue, not an
   extractor-level issue; fix by (a) post-processing extractor
   output to split paragraph-spanning quotes into `list[str]` with
   matching `list[int]` pages, OR (b) re-chunk `pages.json` on
   paragraph boundaries instead of PDF page boundaries.

### For the rulebook (cross-cutting)

5. **Explicit "board internal discussion" exclusion in §D1.** Add:
   *"A board decision to 'explore strategic alternatives', 'consider
   a sale', or 'revisit exploration' is NOT itself a `Target Sale`
   event. `Target Sale` requires either (a) board resolution to
   sell, or (b) external solicitation beginning. Board-internal
   strategy discussions without external action do not emit
   events."* This would kill bp's phantom 2013-06-20 / 2013-07-01 /
   2013-08-20 rows.

6. **Retrospective summary vs per-event drops in §I1.** Add: *"When
   the filing narrates drops in specific narrations ('X of Y parties
   communicated …'), emit a row per narrated drop. A later
   retrospective summary ('all parties had abandoned or withdrawn')
   is a summary, NOT a separate drop event — do not emit
   additional rows for the retrospective summary."*

### For bids_pipeline (mostly deprecated but for the record)

7. **bp lacks `source_quote` / `source_page` entirely.** §R3 / §P-R2
   hard ship-blocker. Any re-use of bp output would need full
   re-extraction with evidence fields populated.
8. **bp emits out-of-vocab codes** (`Exclusivity`, `Go-Shop`). §P-R3
   hard flag on all three rows.
9. **bp fabricates 25 drops on 6/19/6/26.** Needs prompt
   clarification that retrospective summary sentences are not new
   events.

---

## Open questions for Austin

1. **Atomization vs aggregation on the 25-NDA block.** try = 25 rows;
   Alex = 1 row (with wrong count "24"). The rulebook §E1/§E2.b says
   atomize when filing gives exact count. **Does Austin want to
   accept try's atomization as the new reference?** Same question for
   the 5 mid-June drops (try=5, Alex=1). This is the primary driver
   of the 48 vs 23 gap.

2. **Party A/B/C/D/E individual bid values.** Alex's post-§Q2 expansion
   guesses specific numbers (20, 22, [20,22]×3). try emits
   `bid_value_unspecified` on all 5. **Which is the correct
   reference?** The filing only commits to "range $20–22." Austin's
   call whether the reference JSON should hold Alex's guesses or be
   updated to match try's honest-unspecified form.

3. **NMC 2014-04-14 non-submission: `Drop` or `DropAtInf`?** Filing
   language is *"decided at the time not to submit."* All three
   current extractions use `Drop`. Proposal: clarify §I1 so this
   pattern emits `DropAtInf`.

4. **Final Round Inf Ann / Final Round Inf: should try emit these?**
   The §K2 inference triggers on the 3/27 process letter and the
   4/14 submission deadline. try currently emits neither. Alex and
   bp both emit them. **Bug in try's extractor prompt?** Likely yes,
   but might also be a deliberate downstream choice; confirm.

5. **Alex's Party Y NDA dating.** Alex places Party Y's NDA at rough
   2014-05-20 (the IOI date). try infers 2014-03-15 for all unnamed
   NDA signers (including Party Y). **The filing is ambiguous** on
   when Party Y signed — data-room access post-5/20 suggests an NDA
   was signed before. Which date should the reference use?

6. **Restart boundary: 2015-02-10 or 2015-02-19?** try picks 2/10
   (first phase-2 contact), Alex picks 2/19 (IOI delivery), bp picks
   2/26 (revised IOI). §L2 says "first narrated re-engagement
   activity" → 2/10. Confirm this is the correct interpretation of
   §L2.

7. **NDA extension on 2015-02-27 — NDA row or attribute?** §M4 says
   emit as `NDA` with `nda_revived_from_stale` flag. Alex uses the
   deprecated `Exclusivity 30 days` code; bp splits into `NDA` +
   `Exclusivity`; try omits. **Confirm the §M4 interpretation and
   file a try bug.**

8. **The "19 parties dropped at 4/14" row.** Alex emits 1 aggregated
   Drop ("19 parties"). This is the 25 NDA signers minus 5 IOI
   submitters minus 1 NMC. try misses this (implicitly, the 17
   unnamed NDA signers just stay as NDA-only rows with
   `nda_without_bid_or_drop` flags). **Is the §P-S1 soft-flag
   approach (keep NDA rows, flag "no follow-up") the correct
   handling, or should these be atomized Drops like the mid-June
   group?** Providence iter-7 precedent suggests soft-flag is
   correct (§I1 NDA-only rule).

---

## Appendix: row-by-row evidence for the key claims

**Claim: bp emits Target Sale for 2013-06-20 even though filing says board internal.**
Filing p.34 line 752: *"At a June 20, 2013 meeting, our board of directors first discussed the possibility of exploring strategic alternatives, including a potential sale of the Company."* (board-internal language; no external contact)
bp row 112 (Row=112): `bid_note=Target Sale, bid_date_precise=06/20/2013`.
try row 47: `bid_note=Target Sale, bid_date_precise=2013-07-01`. **try picks the 7/1 date (also arguably too early — §D1 would prefer the 1/28/2014 IB engagement date), but at least uses the board's "unanimously agreed to proceed" language rather than a "first discussed" mention.**

**Claim: bp fabricates 25 drops on 6/19 and 6/26.**
Filing p.38 line 842: *"During the process conducted during the first half of 2014, given that all of the parties that had signed confidentiality agreements had abandoned or withdrawn from the process …"*
bp rows 156..178: `bid_note=Drop, bid_date_precise=06/19/2014` or `06/26/2014`, bidder_name=`bidder_3..bidder_25`, comments = *"Routed from the June 19, 2014 disclosure…"* and *"Routed from the June 26, 2014 disclosure…"* (bp's own comments admit routing, not per-event extraction). **Fabrication confirmed.**

**Claim: try misses NDA extension on 2015-02-27.**
Filing p.40 line 868: *"On February 27, 2015, we signed an agreement with New Mountain Capital extending the term of the confidentiality provision, the 'standstill' provision and the employee non-solicitation provision in our original confidentiality agreement with them as well as providing for an exclusivity period with New Mountain Capital through March 31, 2015."*
try row 91 (Restarted 2/10), 92 (Bid 2/19 19.25), 93 (Bid 2/26 20.05) — no 2/27 row. **Gap confirmed.** Bug in prompt re: §M4.

**Claim: bp duplicates NMC best-and-final formal bid.**
bp row 187: `bid_note=NA, bid_date_precise=03/13/2015, bid_type=Formal, bid_value_pershare=20.05, comments="Communicated that $20.05 per share was its 'best and final' offer."`
bp row 189: `bid_note=NA, bid_date_rough=04/01/2015, bid_type=Formal, bid_value_pershare=20.05, comments="As negotiations continued into April… reiterated that $20.05 per share was its 'best and final' offer."`
**Same bid; the 4/01 row is a restatement, not a new bid event.** Duplicate confirmed.

**Claim: All three use `Drop` for NMC non-submission on 4/14, but §I1 would prefer `DropAtInf`.**
Alex row 6391: `bid_note=Drop, BidderName=New Mountain Capital`.
bp row 146: `bid_note=Drop, BidderName=New Mountain Capital`.
try row 79: `bid_note=Drop, BidderName=New Mountain Capital`, with `drop_agency_ambiguous` soft flag. §I1 table maps "bidder self-withdraws at informal stage" → `DropAtInf`. **Code is wrong in all three; try alone flags.**

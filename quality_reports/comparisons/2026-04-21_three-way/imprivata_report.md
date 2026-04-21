# Imprivata three-way extraction audit

**Deal:** Thoma Bravo → Imprivata, Inc. (DEFM14A filed 2016-08-10; announced 2016-07-13; closed 2016-09-16)
**Filing:** `data/filings/imprivata/raw.md` (4,252 lines, 170 pages) — Background on pp. 26–36 (sec2md pages 28–37)
**Sources:** `imprivata_alex.csv` (29 rows) · `imprivata_bids_pipeline.csv` (34 rows) · `imprivata_bids_try.csv` (26 rows)

---

## TL;DR

**Winner: `bids_try` is closest to filing-truth,** largely because it correctly (a) skips the §M1 "contacted-but-no-NDA" and Strategic 4 rows that `bids_pipeline` over-emits, (b) classifies Sponsor A's 6/15 exit as `DropBelowInf` per the filing's target-initiated agency language, and (c) ties Barclays' IB retention date to the April 15 Board decision (§B5 sent-date / §J1 earliest-narrated-action).
`bids_pipeline` is close behind and has two advantages over `bids_try`: it explicitly atomizes the three 2015-era Thoma Bravo approaches (early 2015 / June 2015 / Jan 2016) rather than only two, and it carries a richer narrative in comments. But it fires event rows for parties that §M1 says to skip.
`Alex` is a correct-in-spirit calibration, but (i) mis-dates the Barclays IB row to 2016-03-09, (ii) labels the 6/24 final-round announcement as `Final Round Ext Ann` + `Final Round Ann` (wrongly implying a prior announced final round got extended), and (iii) classifies Sponsor A at 6/15 as `DropAtInf` while classifying the structurally identical Sponsor B at 6/29 as `DropBelowInf` — internal inconsistency.

**Top 3 divergences (filing-grade):**
1. **Sponsor A dropout agency (6/15/2016)** — Alex `DropAtInf` vs both AIs `DropBelowInf`. Filing text is target-initiated ("Barclays informed Sponsor A that it did not believe the Board would be interested"). **BothAIRight, AlexWrong.** Also internally inconsistent with Alex's own Sponsor B 6/29 treatment.
2. **Barclays IB retention date** — Alex `2016-03-09`, `bids_pipeline` `2016-04-19`, `bids_try` `2016-04-15`. Filing narrates the Board's decision to engage Barclays on April 15, 2016, subject to execution of an engagement letter countersigned April 19. Per §J1 (earliest advisor action) and §B5 (outgoing = sent / decision date), **2016-04-15 is best (TryRight)**; April 19 is defensible as the formal countersign date; Alex's 3/09 is filing-wrong.
3. **June 24 round code** — Alex `Final Round Ext Ann` + `Final Round Ann` (two rows), both AIs `Final Round Ann` (one row). Filing describes the final-bid process letters as the *first* formal-final announcement; the informal IOIs on 6/9 were a preliminary round, not a final round that got extended. **BothAIRight.**

**Alex-flag confirmations:** None of Alex's formally-flagged rows (`alex_flagged_rows.json`) are in this deal. However, this audit finds three new Alex defects (#1–#3 above) worth recording as AI-identified corrections per the §CLAUDE.md 4-verdict framework (Verdict 1).

---

## Filing event timeline (ground truth)

Page numbers are sec2md-assigned (from `pages.json`). Filing "Background of the Merger" begins at sec2md page 28 (file line 901).

| # | Date | Event | Actors | Page | Key quote |
|---|------|-------|--------|------|-----------|
| 1 | Early 2015 | Bidder Interest (no price) | Thoma Bravo | 28 | *"In early 2015, and again in June 2015, representatives of Thoma Bravo informally approached … expressed Thoma Bravo's potential interest … No specific proposals were made"* |
| 2 | June 2015 | Bidder Interest (no price) | Thoma Bravo | 28 | Same sentence as above (compound phrasing) |
| 3 | Jan 2016 | Bidder Interest (no price) | Thoma Bravo | 28 | *"In January 2016, representatives of Thoma Bravo met with members of Company management during an industry conference and reiterated … No specific proposal was made"* |
| 4 | 2016-03-09 | Bidder Sale + informal Bid @ $15.00/sh | Thoma Bravo | 29 | *"On March 9, 2016, Thoma Bravo sent an unsolicited, non-binding indication of interest letter … acquiring the Company for cash at a purchase price of $15.00 per share … prepared to finance … entirely with equity … confirmatory diligence and execute a definitive merger agreement in 30 days or less"* |
| 5 | 2016-04-15 | IB retained (Barclays) | Board | 30 | *"The Board engaged Barclays as the Company's financial advisor … subject to execution of a mutually satisfactory engagement letter"* (countersigned April 19) |
| 6 | 2016-05-05 | Target Sale (Board authorizes strategic process contacting 15 parties) | Board | 31 | *"…it was in the best interests of the Company and its stockholders to take steps to further explore a potential business combination transaction … the Board also approved the indicative list of parties"* |
| 7 | 2016-05-10 | NDA | Thoma Bravo | 31 | *"…including Thoma Bravo on May 10, 2016"* — only bidder with a specific NDA date |
| 8 | May 6–Jun 9 | NDAs (6 more, date-unspecified) | Strategic 1, Strategic 2, Strategic 3, Sponsor A, Sponsor B, "one financial sponsor" (4th fin sponsor) | 31 | *"three strategic parties and four financial sponsors executed confidentiality agreements"* — 7 total including TB |
| 9 | ~mid-May | Drop (4th fin sponsor) | "one financial sponsor" | 31 | *"one financial sponsor that declined interest shortly after executing its confidentiality agreement"* — did NOT attend management presentation |
| 10 | 2016-06-03 | Final Round Inf Ann (bid instruction letter to 6 parties) | Barclays (target-side) | 32 | *"Barclays distributed a bid instruction letter … to the six parties that had executed a confidentiality agreement and attended meetings with Company management by that date"* |
| 11 | 2016-06-03 | [Skip per §M1] strategic party declines | unnamed strategic | 32 | *"one of the strategic parties contacted by Barclays, but that did not execute a confidentiality agreement or receive a bid process letter, informed Barclays that it was not interested"* |
| 12 | 2016-06-08 | Drop (no IOI by deadline) | Strategic 1 | 32 | *"…an acquisition of the Company would not be a strategic fit for it … no longer interested … would not be submitting an indication of interest"* |
| 13 | 2016-06-09 | Informal Bid @ $16.50/sh | Sponsor A | 32 | *"Sponsor A indicated a price of $16.50 per share"* (non-binding, equity-financed) |
| 14 | 2016-06-09 | Informal Bid @ $17.00–$18.00/sh | Sponsor B | 32 | *"Sponsor B indicated a range of $17.00 - $18.00 per share"* |
| 15 | 2016-06-09 | Informal Bid @ $17.25/sh | Thoma Bravo | 32 | *"Thoma Bravo indicated a price of $17.25 per share, and also provided a form of equity commitment letter and draft merger agreement"* |
| 16 | 2016-06-09 | Final Round Inf (deadline) | — | 32 | *"On June 9, 2016, three parties … presented written preliminary non-binding indications of interest"* |
| 17 | 2016-06-11 | [Skip per §M1] strategic party declines | unnamed strategic | 32 | Identical pattern to #11, never signed NDA |
| 18 | 2016-06-12 | Drop | Strategic 2 | 32 | *"because of other internal corporate priorities, it was no longer interested"* — voluntary |
| 19 | 2016-06-14 | Drop | Strategic 3 | 33 | *"internal focus on other corporate transactions and a perceived overlap in technologies, … no longer interested"* — voluntary |
| 20 | 2016-06-15 | **DropBelowInf** (Sponsor A) | Sponsor A | 33 | *"Sponsor A informed Barclays that … if it were to submit a second round bid, it would not be meaningfully higher than the price indicated in its June 9, 2016 preliminary indication of interest … **Barclays informed Sponsor A that it did not believe that the Board would be interested in a transaction at a valuation at essentially the same level** … no further discussions"* — target-initiated cut |
| 21 | 2016-06-17 | [Skip per §M1] Strategic 4 contacted (no NDA, declines 6/23) | Strategic 4 | 33 | *"Special Committee directed Barclays to contact an additional strategic party … Strategic 4 informed Barclays that an acquisition … would not be a strategic fit"* |
| 22 | 2016-06-24 | Final Round Ann (final bid process letters to SponB + TB) | Barclays | 35 | *"Barclays sent final bid process letters to Sponsor B and Thoma Bravo, requesting marked drafts … by July 7, 2016, and setting a final bid deadline of July 8, 2016"* |
| 23 | 2016-06-29 | DropBelowInf (Sponsor B) | Sponsor B | 35 | *"if it were to submit a final bid, it would be significantly below the price indicated in its June 9, 2016 preliminary indication of interest … Barclays informed Sponsor B that it did not believe that the Special Committee would be interested"* — target-initiated cut |
| 24 | 2016-07-08 | Formal Bid @ $19.00/sh | Thoma Bravo | 36 | *"Thoma Bravo's bid was at a price of $19.00 per share in cash … completed all of its due diligence and was prepared to execute its revised draft of the merger agreement"* |
| 25 | 2016-07-08 | Final Round (deadline) | — | 36 | *"only Thoma Bravo submitted a bid for the Company"* |
| 26 | 2016-07-09 | Formal Bid (best-and-final) @ $19.25/sh | Thoma Bravo | 37 | *"Barclays received a revised written, non-binding proposal from Thoma Bravo setting forth its best and final offer of $19.25 per share"* (note: filing says "non-binding" but it's the best-and-final formal bid in §G1/§C3 terms) |
| 27 | 2016-07-13 | Executed | Thoma Bravo | 39 | *"the parties finalized and executed the merger agreement"* + joint press release |

**~17 in-scope event types** from the filing (treating the 7 NDAs + 3 6/9 informal bids + 3 drops on 6/12–6/15 as parallel same-day groups). Total expected rows once atomized (each NDA/drop/bid per bidder): **≈24–28 rows** depending on how the three 2015-era TB Bidder Interest meetings are atomized (1 or 3 rows) and on §M1 decisions.

---

## Source-by-source row counts and structure

| Source | Row count | Bidder Interest | NDA | Informal Bid | Formal Bid | Drop-family | Round / IB / Target-Sale / Bidder-Sale / Executed | Notes |
|---|---|---|---|---|---|---|---|---|
| **Alex** | 29 | 2 (TB 3/09 split as Bidder Interest + Bidder Sale) | 7 (TB + 3 Strategic + Sponsor A + Sponsor B + "Another financial sponsor") | 4 (TB 3/09 $15 + 3 on 6/9) | 2 (TB 7/08 $19, TB 7/09 $19.25) | 5 (Strategic 1–3 "Drop", Sponsor A DropAtInf, Sponsor B DropBelowInf, "Another financial sponsor" Drop) | IB ×1, Target Sale ×1, Final Round Inf Ann ×1, Final Round Inf ×1, **Final Round Ext Ann ×1**, **Final Round Ann ×1**, Final Round ×1, **Final Round Ext ×1**, Executed ×1 | Odd: uses `Final Round Ext Ann` + `Final Round Ann` + `Final Round Ext` over-coding the 6/24 event. Missing: atomization of the 3 pre-3/09 TB meetings into Bidder Interest rows (only 2). Missing: Strategic 4. No `process_phase`. |
| **bids_pipeline** | 34 | 3 (TB early-2015, June 2015, Jan 2016) + 1 Bidder Sale (3/09) | 7 (TB + 3 Strategic + 2 Sponsor + 1 "one financial sponsor") | 4 (TB 3/09 $15 + 3 on 6/9) + TB 7/09 $19.25 **marked Informal (wrong)** | 1 (TB 7/08 $19) | 8 (incl. §M1-skippable: Jun-3 unnamed strategic, Jun-11 unnamed strategic, Strategic 4, + correct drops) | IB ×1, Target Sale ×1, Final Round Inf Ann ×1, Final Round Inf ×1, Final Round Ann ×1, Final Round ×1, Target Interest ×1, Executed ×1 | **Over-emits 3 §M1 parties** (Jun-3 strategic, Jun-11 strategic, Strategic 4). Misclassifies 7/09 best-and-final as `Informal`. Barclays IB date 2016-04-19 (countersign) rather than 2016-04-15 (Board decision). |
| **bids_try** | 26 | 2 (early 2015, Jan 2016) + 1 Bidder Sale (3/09) | 7 (TB + 3 Strategic + 2 Sponsor + 1 "Sponsor C") | 3 (Sponsor A $16.50, Sponsor B range, TB $17.25) | 2 (TB 7/08 $19 + TB 7/09 $19.25) | 7 (5 DropBelowInf + 1 Sponsor A DropBelowInf + Sponsor B DropBelowInf + Sponsor C DropBelowInf) | IB ×1, Target Sale ×1, Final Round Inf Ann ×1, Final Round Ann ×1, Executed ×1 | Correctly skips the §M1 parties. Classifies all 6 named-bidder drops as `DropBelowInf` uniformly (ok per filing for Sponsor A/B; defensible but harsher than Alex's `Drop` for Strategic 1/2/3 and "Sponsor C"). Missing: the `Final Round Inf` + `Final Round` deadline-only rows; missing the June 2015 Bidder Interest. Has full `source_quote` + `source_page` citations. |

---

## Divergence table

Verdicts: `AlexRight` / `BPRight` (bids_pipeline) / `TryRight` (bids_try) / `BothAIRight` / `NoneRight` / `JudgmentCall` / `AlexFlagged`.

### A. Pre-process Thoma Bravo approaches (2015–Jan 2016)

| Event | Alex | bp | try | Filing | Verdict | Notes |
|---|---|---|---|---|---|---|
| Early 2015 TB approach | not emitted | 1 row `Bidder Interest` dated 2015-01-01 rough="early 2015" | 1 row `Bidder Interest` dated 2015-02-15 rough="early 2015" | *"In early 2015 … representatives of Thoma Bravo informally approached"* | **BothAIRight** (both atomize; Alex misses); try's 2015-02-15 maps "early 2015" per §B1 as Q1 midpoint = **Feb 15**, which is the canonical mapping; bp's 2015-01-01 is an off-rulebook interpretation. But bp also flags this is a `soft:date_phrase_unmapped`. **Try is closer to §B1.** |
| June 2015 TB approach | not emitted | 1 row `Bidder Interest` dated 2015-06-15 | **not emitted** (try atomizes compound sentence as 1 rather than 2 rows) | Same sentence: *"In early 2015, **and again in June 2015**, representatives of Thoma Bravo informally approached … expressed … potential interest … No specific proposals were made during these meetings"* | **BPRight** | This is a clear second event per filing. Alex and try both miss it (probably reading the compound sentence as one event). Per §E1 atomization, two separate meetings = two separate rows. |
| January 2016 TB approach | not emitted | 1 row `Bidder Interest` dated 2016-01-15 | 1 row `Bidder Interest` dated 2016-01-15 | *"In January 2016, representatives of Thoma Bravo met with … reiterated … interest"* | **BothAIRight** | Alex compresses this event into the later 3/09 Bidder Interest row. |
| March 9, 2016 TB unsolicited IOI | Bidder Interest (BidderID=0.5, 2016-03-09) + Bidder Sale (BidderID=0.7, 2016-03-09) + Bid `$15` Informal (BidderID=1) | Bidder Sale + Bid `$15` Informal (no Bidder Interest row on 3/09) | Bidder Sale + Bid `$15` Informal (no Bidder Interest row on 3/09) | Filing: single "unsolicited, non-binding indication of interest letter" stating concrete price $15. Per §D1 the concrete-price-on-first-contact pattern is `Bidder Sale`, not a separate `Bidder Interest` | **BothAIRight** | Alex's Bidder Interest row on 3/09 is redundant and not supported by the filing for that specific date. Both AIs correctly treat 3/09 as `Bidder Sale` (transition) + `Bid`. |

### B. Barclays IB retention

| Event | Alex | bp | try | Filing | Verdict | Notes |
|---|---|---|---|---|---|---|
| Barclays IB row | dated 2016-03-09, rough=2016-04-15 | dated 2016-04-19 (countersign), comments say "April 15 Board approved" | dated 2016-04-15 with explicit §B5 rationale in comments | *"On April 15, 2016, the Board held a meeting … The Board engaged Barclays as the Company's financial advisor … subject to execution of a mutually satisfactory engagement letter"* + *"On April 19, 2016, the Company countersigned an engagement letter with Barclays, dated April 15, 2016"* | **TryRight (with BPRight also defensible)** | Per §J1 earliest-narrated-action: Barclays is first named as acting in advisor capacity around April 15. Per §B5 outgoing directionality: the Board's act of engagement is the target-side sent-date = 4/15. Alex's 2016-03-09 is clearly wrong (Barclays not considered as an advisor until 3/14, and not Board-approved until 4/15). |

### C. NDA granularity

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| NDA atomization | 7 rows (TB 5/10 + 3 Strategic at rough=5/6 + 2 Sponsor at rough=5/6 + "Another financial sponsor" at rough=5/6) | 7 rows (TB 5/10 + 3 Strategic at 5/15 + 2 Sponsor at 5/15 + "one financial sponsor" at 5/15) | 7 rows (TB 5/10 + 3 Strategic at 5/23 rough="Between May 6 and June 9" + 2 Sponsor at 5/23 + "Sponsor C" at 5/23) | *"three strategic parties and four financial sponsors executed confidentiality agreements … including Thoma Bravo on May 10, 2016"* — only TB has a specific date; others are dated only as "during the period from May 6 through June 9, 2016" | **BothAIRight on count; TryRight on date inference** | All three sources correctly atomize to 7 rows. Date handling: only Thoma Bravo's 5/10 date is filing-stated; the other 6 NDAs are in a date range. Per §B4 (date-range events → midpoint), try's 5/23 = midpoint of 5/6–6/9 is the rulebook-conformant choice. Alex's 5/6 is the range start (biases early, §B4 explicitly rejects); bp's 5/15 is a month-midpoint approximation. |

### D. 4th-financial-sponsor drop ("declined shortly after NDA")

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| 4th-sponsor Drop classification | `Drop` (voluntary) | `Drop` (voluntary) | `DropBelowInf` (target-initiated) | *"Except for one financial sponsor that declined interest shortly after executing its confidentiality agreement, each party … attended a high-level management presentation"* — the verb is **declined** = voluntary | **BothAIRight (Alex + bp); try slightly wrong** | Filing language "declined interest" is a textbook voluntary-withdrawal phrase per §I1 agency table. Drop is more accurate than DropBelowInf. This is a try-side misclassification. |
| 4th-sponsor drop date | rough=2016-05-07 (right after NDA, if NDA ~5/6) | 2016-05-20 (ad-hoc inference) | 2016-05-30 rough="shortly after NDA in May-June 2016" (1 week after inferred 5/23 NDA) | Filing says "shortly after" with no calendar anchor; per §B1 anchored-relative table "shortly after" = +7 days | **JudgmentCall** | All three are defensible. try's +7 is closest to §B1 rule. |

### E. Strategic 1/2/3 drop classification

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| Strategic 1 Drop (6/8) | `Drop` (voluntary) | `Drop` (voluntary) | `DropBelowInf` (target-initiated) | *"Strategic 1 informed Barclays that after further internal consideration, an acquisition … would not be a strategic fit … no longer interested … would not be submitting an indication of interest"* — voluntary ("informed … no longer interested") | **AlexRight + BPRight** | try is slightly harsh; §I1 "informed … not interested" is the voluntary Drop pattern. |
| Strategic 2 Drop (6/12) | `Drop` | `Drop` | `DropBelowInf` | *"Strategic 2 informed … because of other internal corporate priorities, it was no longer interested"* | **AlexRight + BPRight** | Same pattern. try is harsh. |
| Strategic 3 Drop (6/14) | `Drop` | `Drop` | `DropBelowInf` | *"Strategic 3 informed … internal focus on other corporate transactions and a perceived overlap in technologies … no longer interested"* | **AlexRight + BPRight** | Same pattern. try is harsh. |

### F. Sponsor A drop (6/15)

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| Sponsor A Drop 6/15 | `DropAtInf` (voluntary, at informal stage) | `DropAtInf` (voluntary) | `DropBelowInf` (target-initiated) | *"Sponsor A informed Barclays that … if it were to submit a second round bid, it would not be meaningfully higher than the price indicated in its June 9, 2016 preliminary indication of interest, and inquired whether it should continue in the strategic process. **Barclays informed Sponsor A that it did not believe that the Board would be interested in a transaction at a valuation at essentially the same level as Sponsor A's previous indication of interest** … no further discussions"* | **TryRight (or JudgmentCall)** | **Target-initiated language dominates**: Sponsor A asked "should I continue?" and Barclays said "no, not at that price." The deciding agency is the Board/Barclays. Per §I1 "`[Target] informed [bidder] that its bid was insufficient`" — this is precisely the `DropBelowInf` pattern (target rejects because bid is below minimum/reserve). try is correct; Alex and bp are reading the first half of the quote ("Sponsor A informed") rather than the decisive second half. |

### G. Sponsor B drop (6/29)

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| Sponsor B Drop 6/29 | `DropBelowInf` | `DropBelowInf` | `DropBelowInf` | *"if it were to submit a final bid, it would be significantly below … Barclays informed Sponsor B that it did not believe that the Special Committee would be interested in a transaction at a valuation significantly lower"* | **All three agree — correct** | Structurally identical to Sponsor A at 6/15. Alex's choice of `DropBelowInf` here but `DropAtInf` for Sponsor A is **internally inconsistent**. |

### H. Final-round coding

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| 6/3/2016 round letter | `Final Round Inf Ann` (rough=6/3, precise=6/9) | `Final Round Inf Ann` dated 6/3 | `Final Round Inf Ann` dated 6/3 | Letter sent 6/3 with 6/9 deadline. Per §B5 outgoing = sent date = 6/3. | **BothAIRight; Alex's 6/9 precise is §B5-wrong (uses deadline, not sent date)** |
| 6/9 `Final Round Inf` deadline | 1 row (BidderID=13.5) | 1 row (row 44) | **missing** | Filing: *"On June 9, 2016, three parties … presented written preliminary non-binding indications of interest"* | **AlexRight + BPRight** | try skips the deadline-only row, which is legitimate per §K1 (the 3 bid rows on 6/9 already carry the same-date information). But emitting it makes the round structure explicit. |
| 6/24 final-bid letters | `Final Round Ext Ann` (6/24) + `Final Round Ann` (6/24) + `Final Round Ext` (6/24 rough=7/8) | `Final Round Ann` (6/24) | `Final Round Ann` (6/24) | *"Barclays sent final bid process letters to Sponsor B and Thoma Bravo … setting a final bid deadline of July 8, 2016"* — this is the **first and only** formal final-round announcement | **BothAIRight** | Alex's triple-coding is overkill and confuses the round structure: `Final Round Ext Ann` / `Final Round Ext` imply an EXTENSION of a prior final round, but the prior round (June 9) was labeled informal. The correct code is `Final Round Ann` (on 6/24) + `Final Round` (on 7/8). |
| 7/8 deadline row | `Final Round` (7/8 rough=6/24) | `Final Round` (7/8) | **missing** | Filing: *"only Thoma Bravo submitted a bid"* | **AlexRight + BPRight** | try misses. |

### I. §M1 no-NDA skips

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| 6/3 unnamed strategic declines (no NDA) | not emitted | emits `Drop` row | not emitted | *"one of the strategic parties contacted by Barclays, but that **did not execute a confidentiality agreement or receive a bid process letter**, informed Barclays that it was not interested"* | **AlexRight + TryRight (bp wrong)** | §M1: no NDA + no price + no bid intent → skip. Emit a deal-level `partial_bid_ambiguous` or `unsolicited_letter_skipped` info flag instead. |
| 6/11 unnamed strategic declines (no NDA) | not emitted | emits `Drop` row | not emitted | Same §M1 pattern | **AlexRight + TryRight** | Same. |
| Strategic 4 (6/17 Target Interest, 6/23 Drop — no NDA, no price) | not emitted | emits `Target Interest` + `Drop` (2 rows) | not emitted | Strategic 4 never signed NDA, never priced anything. Target reached out, Strategic 4 said no. | **AlexRight + TryRight** | Pure §M1 skip (no NDA + no price + no bid intent). bp over-emits. |

### J. Bid classification §G1

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| TB 7/09 $19.25 best-and-final | `Formal` | `Informal` | `Formal` | *"best and final offer"* — per §G1 formal trigger table: "best and final" ∈ formal triggers | **AlexRight + TryRight; bp wrong** | bp's Informal classification is the single clearest misclassification in this deal. "Best and final" is an explicit formal trigger. |
| Sponsor B 6/9 range bid | Informal, `bid_value_lower=17` `bid_value_upper=18`, `bid_value_pershare=17` (populated lower) | Informal, lower/upper/per-share all 17/18/17 (bp keeps same triplet as Alex) | Informal, `bid_value_lower=17.0` `bid_value_upper=18.0`, `bid_value_pershare=NA` (per §H1 range bids leave per-share null) | *"Sponsor B indicated a range of $17.00 - $18.00 per share"* | **TryRight** | Per rulebook §H1, range bids populate lower+upper and leave `bid_value_pershare` null. Alex's pattern of setting per-share to the lower bound is legacy xlsx practice, deprecated per §H1 migration note. bp faithfully replicated Alex's legacy pattern. |

### K. Executed row

| Event | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| Executed date | 2016-07-09 (Alex's date field) rough=2016-07-13 | 2016-07-13 | 2016-07-13 | *"On July 13, 2016, before the stock market opened, the parties finalized and executed the merger agreement"* | **BothAIRight; Alex wrong** | Alex's 7/09 date is the date Thoma Bravo's best-and-final was submitted, not the execution date. This is a clear filing-vs-Alex divergence. |

### L. Other field-level divergences

| Field/observation | Alex | bp | try | Filing | Verdict |
|---|---|---|---|---|---|
| `source_quote` / `source_page` presence | **absent** (Alex reference JSONs omit evidence per CLAUDE.md design) | **absent** | **present on every row** (per §R3/§P-R2) | required per §R3 | **TryRight** for auditability |
| `process_phase` | null | absent | 1 | Default for deals with no stale prior | **TryRight** |
| `bidder_type.public` | null | Alex columns set `F=1` or `S=1` only | all rows have structured `{base, non_us, public}` | §F1 requires structured object | **TryRight** on schema; public=null is a legacy-converter limitation |
| `bid_type_inference_note` | absent | absent | present on formal rows and on some informal rows that rely on process-position fallback | §P-G2 (hard invariant) requires either true-range or inference_note | **TryRight** — try is the only source that passes §P-G2 |
| `flags[]` array | empty or minimal | absent | populated (info / soft / hard per §R2) | per §R2 | **TryRight** |
| Deal-level `DateEffective` | 2016-09-16 | empty | empty (`NA`) | Filing cover says closing contemplated ~Sep 2016; merger effective Sep 16, 2016 (external) | **AlexRight** on the value; the AIs defer to seeds/manifest, which is correct per §Scope-3 (DateEffective is an external/filing-cover field not reliably in the Background) |

---

## Systemic findings

### 1. NDA atomization-vs-aggregation (on-mission for the current Stage 3 question)

All three sources atomize to 7 NDA rows on Imprivata — including Alex. This deal is **not** in the group Austin flagged as "AI atomizes 15–27 NDAs vs Alex aggregates 2–3." Imprivata's NDA count is modest (7) and all three sources agree on atomization here. **No action required for Imprivata's NDA axis.**

### 2. Drop agency classification (§I1 agency language)

`bids_try` uniformly emits `DropBelowInf` for all six named-bidder drops; Alex and bp more carefully distinguish voluntary (`Drop`, `DropAtInf`) from target-initiated (`DropBelowInf`). This is the clearest systemic gap in try's classification layer: it collapses §I1's 5-code dropout vocabulary into a single "DropBelowInf" bucket on this deal. **Probable cause:** try reads any "no longer interested → no further discussions" pattern as target-initiated; per §I1, the bidder's "informed Barclays … no longer interested" language is the voluntary-withdrawal pattern unless the target then actively rejects. Alex's and bp's approach is closer to the §I1 agency table — with one caveat: for Sponsor A (6/15), the filing's decisive quote *"Barclays informed Sponsor A that it did not believe the Board would be interested"* **is** target-initiated, so try is correct there and Alex/bp are inconsistent with their own Sponsor B 6/29 treatment.

**Recommended resolution:** Keep §I1 unchanged. This is a per-row judgment that the extractor must make with care. Austin may want to re-score Alex's imprivata_alex.csv by promoting Sponsor A 6/15 to `DropBelowInf` (matching Sponsor B 6/29 and the filing language), which is an AI-identified correction per the §CLAUDE.md 4-verdict framework.

### 3. §M1 no-NDA skip discipline

bp emits event rows for three parties that never signed NDAs, stated no price, and expressed no bid intent (the 6/3 and 6/11 unnamed-strategic declines + Strategic 4). Per §M1 these should be deal-level `unsolicited_letter_skipped` info flags, not event rows. Alex and try correctly skip. **This is a bp-specific defect, not a rulebook gap.**

### 4. Date-range events (§B4)

bp's handling of the "May 6 through June 9, 2016" NDA range uses month-midpoint 5/15 rather than range-midpoint 5/23. Per §B4, date-range events populate `bid_date_precise` at the range midpoint and `bid_date_rough` with the verbatim phrase. try is §B4-conformant; bp is one week off. Minor.

### 5. Bidder typing (§F1/§F2)

All three sources classify Thoma Bravo as `f` (financial sponsor), Strategic 1/2/3 as `s`, and the sponsors correctly. bp populates the legacy Alex boolean columns (`bidder_type_financial=1` etc.); try populates the structured §F1 `{base, non_us, public}` object. try's `public=null` across all rows is the broader issue Austin flagged for `scripts/build_reference.py` — but on Imprivata, the public-status is genuinely ambiguous from filing text alone (no bidder is confirmed public other than the Company itself). **No change needed here.**

### 6. Bid value structure (§H1)

try follows §H1 (ranges populate lower+upper, per-share null); Alex and bp populate lower+upper+per-share with the lower bound duplicated into per-share. Per §H1 migration note this is legacy xlsx behavior deprecated by §H1. try is the only §H1-conformant source.

### 7. Source-quote / source-page presence (§P-R2, hard invariant)

try carries `source_page` + `source_quote` on every row. Alex and bp carry neither. The §P-R2 validator would hard-fail Alex and bp. Per CLAUDE.md, Alex reference JSONs intentionally omit evidence; bp's omission is a pipeline gap. **try is the only source that would pass the current hard invariant.**

### 8. §G1 "best and final" trigger

bp misclassified Thoma Bravo's 7/09 $19.25 best-and-final as `Informal` despite the filing's *"best and final offer"* language — an explicit §G1 formal trigger. This is a classification regression specific to bp on Imprivata.

---

## Specific rule / prompt fixes recommended

1. **No rulebook change recommended.** All three systemic gaps above are per-source bugs, not rule gaps.

2. **Prompt tweak for try (narrow):** consider adding explicit clarifying text in `prompts/extract.md` on the §I1 agency test for the "informed X that they would not meaningfully improve their bid" pattern. Specifically: when the **bidder** informs the target of a lukewarm position AND the **target** then expresses disinterest, the deciding agency is the target → `DropBelowInf`. When the bidder informs the target and the target does not actively reject → `Drop` (voluntary). try's current uniform DropBelowInf on Imprivata drop rows looks like a systematic over-application of this rule.

3. **Alex reference JSON correction candidates** (for `scripts/build_reference.py` or alex_flagged_rows.json, per CLAUDE.md §CLAUDE.md ground-truth epistemology Verdict 1: "AI correct, Alex wrong"):
   - **Sponsor A 6/15 DropAtInf → DropBelowInf** (inconsistent with Sponsor B 6/29 and with filing's target-initiated agency language)
   - **Barclays IB date 2016-03-09 → 2016-04-15** (Barclays wasn't even considered until March 14; Board-decision was April 15)
   - **6/24 Final Round Ext Ann + Final Round Ann + Final Round Ext → Final Round Ann** only (collapse the triple-coding; the 6/24 event is the first formal final-round announcement, not an extension)
   - **Executed row date 2016-07-09 → 2016-07-13** (the 7/09 date is Thoma Bravo's best-and-final submission; merger agreement was executed 7/13)
   - **Missing June 2015 Bidder Interest row** — Alex compresses 3 pre-process TB meetings into 2 rows (early 2015 + Jan 2016); filing narrates 3. Atomize per §E1.

4. **bp fix list (not rulebook):**
   - Drop §M1-skippable rows (6/3 unnamed strategic, 6/11 unnamed strategic, Strategic 4 Target Interest + Drop).
   - Re-classify TB 7/09 $19.25 as **Formal** (explicit "best and final" §G1 trigger).
   - Barclays IB date: 4/15 (Board decision, §B5 outgoing) rather than 4/19 (countersign).
   - NDA range-midpoint: 5/23 not 5/15 (per §B4).
   - Carry `source_quote` + `source_page` to meet §P-R2.

5. **try fix list (not rulebook):**
   - Emit `June 2015` Bidder Interest row (filing's compound sentence contains two events).
   - Emit `Final Round Inf` on 6/9 and `Final Round` on 7/8 deadline-only rows for completeness.
   - Re-examine drop classifications: Strategic 1/2/3 (6/8/6/12/6/14) and "Sponsor C" 4th-sponsor drop are filing-grade voluntary (`Drop`) — try uniformly uses `DropBelowInf`.

---

## Open questions for Austin

1. **Sponsor A 6/15 dropout — confirm verdict.** Adjudicate whether the deciding agency is Sponsor A's "inquired whether it should continue" (→ DropAtInf) or Barclays' "did not believe the Board would be interested" (→ DropBelowInf). This report argues for DropBelowInf on filing-text grounds and cites Alex's own Sponsor B 6/29 treatment as internal precedent.

2. **2015-era TB meetings atomization — 1, 2, or 3 rows?** Filing narrates three meetings (early 2015, June 2015, January 2016). Alex compresses to an implicit 0 rows; bp emits 3; try emits 2. Per §E1 atomization the answer is 3. Should the Alex reference JSON be regenerated to emit all 3?

3. **Drop family uniformity in try.** Austin's preferred stance: keep the §I1 voluntary/target-initiated distinction (Alex/bp approach), or accept a simpler `DropBelowInf` catchall (try approach)? The §I1 distinction carries research signal (who cut whom is auction-design relevant); suggests keeping it. Prompt change recommended.

4. **7/09 $19.25 = Formal or Informal?** Filing literally says "non-binding proposal" but the §G1 trigger "best and final" is present. §G1's trigger-table rule: *"final bid, best and final"* = `Formal`. bp read the "non-binding" substring and classified as Informal; Alex and try correctly read "best and final" as the dominating signal. Confirms §G1 priority logic.

5. **Barclays IB date (4/15 vs 4/19) — pick one.** Both are defensible per §J1 (earliest-narrated-action = 4/15) and §B5 directionality (Board's decision = sent date = 4/15; formal countersign = 4/19). try uses 4/15; bp uses 4/19; Alex's 3/09 is out of the question. If Austin wants a single answer, 4/15 (the Board-decision date) is more consistent with §J1's "earliest-narrated-date on which the filing describes the bank acting in an advisory capacity" and §B5's outgoing-sent-date anchor.

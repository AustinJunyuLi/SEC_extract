# sTec / Western Digital three-way audit report

**Deal:** sTec, Inc. acquired by Western Digital Corporation (WDC), announced 2013-06-24, closed 2013-09-12. DEFM14A filed 2013-08-08.
**Filing (ground truth):** `/Users/austinli/bids_try/data/filings/stec/raw.md` (4053 lines), "Background of the Merger" begins at line 993 / sec2md page 32.
**Sources compared:**
- Alex (`stec_alex.csv`): 28 rows
- bids_pipeline (`stec_bids_pipeline.csv`): 42 rows
- bids_try (`stec_bids_try.csv`): 31 rows

---

## TL;DR

- **bids_try wins on quality** (it more consistently applies §P-G2, §H1, §D1.b, §I1 agency, and §R3 evidence). bids_pipeline wins on **breadth of process context** (has more pre-NDA scene-setting rows and more final-round Ext/Ext-Ann rows) but its bid representation is structurally wrong.
- **Single-bound informal-bid verdict:** Only bids_try correctly handles §H1 + §P-G2. The Company D 4/23 $5.60+ verbal IOI is the one unambiguous single-lower-bound bid. bids_try: `lower=5.60, upper=null` + `bid_lower_only` info flag + `bid_type_inference_note` (correct). Alex: `lower=5.60, upper=NA` (correct shape, but no inference note — reference-JSON convention). bids_pipeline: `pershare=5.6, lower=5.6, upper=5.6` (wrong — treats a single-bound bid as a point bid with a collapsed range). Furthermore, bids_pipeline collapses every point bid (Company D $5.75, WDC $9.15, WDC $6.85) to `lower==upper`, which is neither a §P-G2 "true range" (needs `lower < upper`) nor a point bid, and it emits NO `bid_type_inference_note` on any row — so every bids_pipeline bid row would fail §P-G2 under the current validator.
- **Bidder-type accuracy verdict:** bids_try correctly types every bidder. Alex's reference covers 6 of 8 bidders with the structured `{base:"s", non_us:false, public:null}` form (Alex does not ship `public` inference). bids_pipeline fills `bidder_type_note` only on the ~8 named-counterparty rows and leaves the rest NA — losing the strategic classification on most pre-NDA rows. bids_try's `public: null` on non-WDC anonymous strategics is defensible (filing never states whether Companies A–H are publicly traded); `public: true` on WDC is correct.
- **Top 3 divergences.**
  1. **Company H dropout agency** (5/23/2013). Filing is target-initiated ("BofA... indicated that the price range Company H had submitted was not sufficient to move them forward in the process"). bids_try emits `DropBelowInf` (correct per §I1). Alex emits `Drop` (generic). bids_pipeline emits `Bid` + a separate `DropAtInf` (self-withdrawal — wrong agency).
  2. **Bid-value representation on point and single-bound bids.** bids_pipeline fills `bid_value_lower == bid_value_upper` on every point bid (9.15, 6.85, 5.75) and on a single-lower-bound bid (5.60+). This violates §H1 and puts every bid_pipeline bid row outside the §P-G2 satisfier set (not a true range, no inference note).
  3. **WDC NDA (§M4 stale-prior handling).** Filing says Mutual NDA dated Jan 29, 2009, with a Special Addendum dated April 17, 2013 (explicit in merger agreement §1.1(k), page 101). bids_try emits TWO NDA rows (2009-01-29 phase-0-style + 2013-04-17 + `nda_revived_from_stale` flag). Alex and bids_pipeline collapse to one row at 2013-04-17. bids_try's shape matches §M4's two-NDA rule; whether the 2009 NDA was a *sale-process* NDA (it wasn't — it was a commercial/technical NDA between sTec and WDT) or just a pre-existing mutual NDA is a judgment call on whether §M4 even applies.

---

## Filing event timeline (with page cites)

Page numbers are sec2md page numbers (as used in `source_page`); the `Background of the Merger` section runs pages 32–43.

| # | Date (filing) | Event | Page |
|---|---|---|---|
| 1 | 2011 (summer–fall) | WDC CEO John Coyne / Mike Hajeck informal lunch discussions with M. Moshayedi re: SSD expansion interest — no specific terms proposed | 32 |
| 2 | Q4 2012 | Board begins strategic review; in mid-Nov 2012 authorizes management to contact financial advisors re: possible sale | 32 |
| 3 | 2012-11-14 | IB representing **Company A** (storage industry) contacts sTec; draft NDA provided; meeting scheduled; meeting subsequently cancelled because non-management directors raised concerns about Company A management's involvement | 32 |
| 4 | 2012-11-16 | **Balch Hill** (activist, technology sector) Schedule 13D filed (6.4% stake) | 33 |
| 5 | 2012-12-06 | Balch Hill amends 13D and issues letter to board urging strategic alternatives | 33 |
| 6 | ~late 2012 | **Potomac Capital Partners II, L.P.** joins Balch Hill's activist campaign; jointly 9.8% | 33 |
| 7 | 2013-02-11–13 | Board meetings; on 2013-02-13, special committee formed; mandate: review strategic alternatives incl. possible sale | 33 |
| 8 | 2013-02-13 | President of **Company B** (electronics industry) meets M. Moshayedi; says Company B will discuss sTec as a possible acquisition target at its management meeting the following week | 33 |
| 9 | ~2013-02-27 / 03-05 | Company B reports back that its management is not interested and will develop the technology independently | 34 |
| 10 | 2013-03-13 | Representatives of **Company C** (semiconductor industry) express potential interest in "particular assets of sTec" (partial-asset interest, §H3 territory) | 34 |
| 11 | mid-March 2013 | Head of corporate development for **Company D** (storage industry) contacts sTec to express interest in a potential acquisition; Company D sends draft NDA on 3/26/2013 | 35 |
| 12 | 2013-03-26 | Board approves retaining BofA Merrill Lynch as financial advisor; decides to confidentially approach strategic buyers + limited confirmatory outreach to financial buyers | 35 |
| 13 | 2013-03-28 | BofA Merrill Lynch engagement letter signed | 35 |
| 14 | 2013-04-01 | BofA begins contacting potential acquirers; in total 18 prospective acquirers contacted (17 strategic, 1 financial sponsor); 3 submit written IOIs for the whole company (WDC, Company H, Company D), 6 strategics interested only in select assets, 9 not interested (incl. Company A and the financial sponsor) | 35 |
| 15 | 2013-04-04 | NDA with **Company E** (storage industry) — contains "don't ask, don't waive" provision | 35 |
| 16 | 2013-04-10 | NDA with **Company D** | 35 |
| 17 | 2013-04-11 | NDA with **Company F** (storage industry) — contains "don't ask, don't waive" | 35 |
| 18 | 2013-04-15 | Company C says it is interested only in select assets; committee declines to continue | 36 |
| 19 | 2013-04-17 | NDA with **Company G** (storage industry) | 36 |
| 20 | 2013-04-17 | Addendum to existing NDA with **WDC** (original NDA dated 2009-01-29 per merger agreement §1.1(k), page 101) | 36 |
| 21 | 2013-04-23 | BofA sends process letters to WDC and Company D, requesting non-binding IOIs by 5/3/2013 | 36 |
| 22 | 2013-04-23 | **Company D** verbal IOI "at a price greater than $5.60 per share" (§H1 single lower bound); additional diligence requirements requested | 36 |
| 23 | 2013-04-24 | **Company F** declines management presentation; interested only in select assets; no further communications | 36 |
| 24 | shortly after 2013-04-24 | **Company E** also indicates only interested in select assets; committee terminates discussions | 36 |
| 25 | 2013-04-26 | BofA sends process letter to **Company G** requesting IOI by 5/3/2013 | 36 |
| 26 | 2013-05-01 | **Company H** contacts BofA expressing transaction interest; on 5/2 BofA sends NDA | 37 |
| 27 | 2013-05-03 | **WDC** submits written IOI at range $6.60 – $7.10 per share in cash (true range; first bid; §H1 range → §G1 informal) | 37 |
| 28 | 2013-05-03 | **Company G** withdraws from process | 37 |
| 29 | 2013-05-08 | NDA with **Company H** — contains "don't ask, don't waive" | 37 |
| 30 | 2013-05-10 | **Company D** submits written non-binding IOI at **$5.75 per share cash** (point) with draft exclusivity agreement (§G1 informal trigger: "written non-binding indication of interest") | 37 |
| 31 | 2013-05-15 | **Company H** submits written non-binding IOI at range **$5.00 – $5.75** per share cash (§G1 informal; true range) | 37 |
| 32 | week of 5/13–5/20 | BofA tells **Company H** its range is "not sufficient to move them forward"; invites revised IOI | 37 |
| 33 | 2013-05-16 | Board meeting; BofA sends **final round process letters + draft merger agreement** to WDC and Company D, requesting response by 5/28 | 38 |
| 34 | 2013-05-23 | **Company H** confirms it "remained interested… but… was not able to increase its indicated value range" — target-initiated cut per §I1 DropBelowInf (BofA told them their range was insufficient; this is Company H acknowledging the cut) | 38 |
| 35 | 2013-05-28 | **WDC** submits second-round IOI **$9.15 per share cash** with mark-up of merger agreement and drafts of ancillary agreements (§G1 formal: "mark-up of the merger agreement" + submitted in response to final-round process letter) | 38 |
| 36 | 2013-05-28 | **Company D** says it needs ~2 more weeks to submit written IOI and mark-up | 38 |
| 37 | 2013-05-29 | Board directs BofA to request "best and final" proposal from WDC and written "best and final" proposal from Company D by 5/30 (Final Round Ext Ann) | 38 |
| 38 | 2013-05-30 | **WDC** verbally reconfirms $9.15/share as best; focused on 6/3 announcement. **Company D** reconfirms need for additional time. Board unanimously decides to move forward with WDC on $9.15 | 39 |
| 39 | 2013-05-31 | **WDC** withdraws — representative tells BofA WDC is "reevaluating its interest… not prepared to move forward at this time… discontinued due diligence" | 39 |
| 40 | 2013-06-01 to 06-10 | BofA–WDC discussions re: re-engagement; WDC indicates "difference of opinion had emerged internally" | 39–40 |
| 41 | 2013-06-05 | **Company D** withdraws (disengaging from process due to DD-bandwidth constraints) | 40 |
| 42 | 2013-06-10 | **WDC** submits revised written IOI at range **$6.60 – $7.10** per share cash (§H5 revision; §G1 informal: range + "written indication of interest"). Board rejects ranged proposal; demands single specific best-offer | 40 |
| 43 | 2013-06-14 | **WDC** submits written IOI at **$6.85 per share cash** — "best and final" (§G1 formal trigger: "best and final") | 40 |
| 44 | 2013-06-16–22 | WDC confirmatory due diligence | 41 |
| 45 | 2013-06-23 | Special committee and board approve; merger agreement executed; voting agreements executed | 42–43 |
| 46 | 2013-06-24 | Joint press release announcing transaction | 43 |

---

## Source-by-source row counts and structure

| Source | Rows | Pre-NDA (BidderInterest / TargetSale / ActivistSale / IB) | NDAs | Bid rows | Drops (any family) | FinalRound* | Executed |
|---|---|---|---|---|---|---|---|
| Alex | 28 | 3 (Bidder Interest×2 + IB×1) | 5 | 7 | 4 | 4 (Inf Ann, Inf, Ann, Final Round, Ext Ann, Ext) | 1 |
| bids_pipeline | 42 | 11 (Target Sale×4 + Bidder Interest×4 + Activist Sale×1 + IB×1) | 6 | 9 | 7 | 7 (adds 5/29 Ext Ann, 5/30 Ext) | 1 |
| bids_try | 31 | 7 (Target Sale×1 + Bidder Interest×3 + Activist Sale×2 + IB×1) | 6 | 7 | 6 | 1 (Final Round Ann only) | 1 |

**Per-bidder breakdown** (named bidders only):

| Bidder | Alex | bids_pipeline | bids_try |
|---|---|---|---|
| Company A | — (skipped) | 2 rows (Bidder Interest + Drop) | 2 rows (Bidder Interest + DropTarget) |
| Balch Hill | — | 1 (Activist Sale only) | 1 (Activist Sale) |
| Potomac Capital | — | — (**missing per §D1.b**) | 1 (Activist Sale) |
| Company B | 1 (Bidder Interest, precise=4/4 + rough=2/13) | 2 (BI + Drop) | 2 (BI + Drop) |
| Company C | — (skipped per §H3 partial) | 2 (BI + DropTarget) — **§H3 violation** | — (skipped, correct) |
| Company D | 5 rows | 5 rows | 5 rows |
| Company E | 2 (NDA + DropTarget) | 2 (NDA + DropTarget) | 2 (NDA + DropTarget) |
| Company F | 2 (NDA + DropTarget) | 2 (NDA + Drop) | 2 (NDA + DropTarget) |
| Company G | 2 (NDA + Drop) | 2 (NDA + Drop) | 2 (NDA + Drop) |
| Company H | 3 (NDA + Bid + Drop) | 5 (BI + NDA + Bid×2 + DropAtInf) | 4 (NDA + Bid + Bid + DropBelowInf) |
| BofA | 1 (IB) | 1 (IB) | 1 (IB) |
| WDC | 5 (NDA + Bid×3 + Executed) | 6 (NDA + Bid×4 + Drop + Executed) | 8 (NDA 2009 + NDA 2013 + TargetSale + Bid×4 + Executed — wait, only 7 with the TargetSale, 8 total: 2 NDAs, TargetSale row, 4 Bids, Drop, Executed) |

---

## Divergence table

Verdicts: `AlexRight` · `BPRight` · `TryRight` · `BothAIRight` · `NoneRight` · `JudgmentCall` · `AlexFlagged`.

| # | Divergence | Alex | bids_pipeline | bids_try | Filing evidence | Verdict |
|---|---|---|---|---|---|---|
| 1 | Company H 5/23 dropout code | `Drop` | `Bid`+`DropAtInf` (self-withdraw) | `DropBelowInf` (target cut) | "BofA… indicated that the price range Company H had submitted was not sufficient to move them forward" (week of 5/13, p37) + 5/23 "Company H… was not able to increase its indicated value range" (p38). Agency: target. | **TryRight** (§I1 target-initiated) |
| 2 | Company D 4/23 $5.60+ bid representation | `pershare=NA, lower=5.6, upper=NA` + informal | `pershare=5.6, lower=5.6, upper=5.6` + informal, NO inference note | `pershare=NA, lower=5.6, upper=NA` + informal + `bid_lower_only` flag + `bid_type_inference_note` | "Company D provided a verbal indication of its interest to pursue a transaction **at a price greater than $5.60 per share**" (p36) | **TryRight** (alex shape correct but no §P-G2 note; BP wrong shape + no note) |
| 3 | Point bids representation (D $5.75, WDC $9.15, WDC $6.85) | `pershare=5.75/9.15/6.85, lower=5.75/9.15/6.85, upper=5.75/9.15/6.85` (Alex convention: duplicates value to lower/upper) | same as Alex (pershare + lower == upper) | `pershare=5.75/9.15/6.85, lower=NA, upper=NA` per §H1 | Point-valued bids per filing | **TryRight** per §H1; Alex and BP both violate §H1 strictly (Alex's workbook convention; legitimate to re-encode via converter) |
| 4 | §P-G2 `bid_type_inference_note` coverage on non-range bid rows | None (converter intentionally omits; reference JSON convention) | None | Every non-range bid row carries one (100% coverage) | §G2 / §P-G2 requires range OR note | **TryRight** (only TRY passes §P-G2 strictly) |
| 5 | Potomac as separate activist | — | — | 1 row (Activist Sale 12/15/2012, `F`) | "Balch Hill was later joined by Potomac Capital Partners II, L.P." (p33) | **TryRight** per §D1.b (ambiguity default: per-activist rows) |
| 6 | Balch Hill `bidder_type.base` | NA (not typed) | NA | `F` (financial) | "an activist investor in the technology sector" — PE/hedge fund per §F2 row 1/6 | **TryRight** |
| 7 | Company A (unsigned-NDA, partial-asset interest) | — (skipped) | 2 rows (Bidder Interest 11/14 + Drop 4/15 — wrong date for withdrawal; filing cancellation was 11/14) | 2 rows (Bidder Interest 11/14 + DropTarget 11/14) | "A meeting was scheduled… however, it was subsequently cancelled because of concerns expressed by non-management board members, which were communicated to Company A, that the management of Company A had not demonstrated any involvement" (p32) — target-initiated, same-day outcome | **TryRight** on agency and date; **AlexFlagged** — Alex's skip is defensible via §M1 (no NDA + no concrete price); but bids_try's "Bidder Interest + DropTarget" preserves more process context. Company A later reappears among "9 not interested" after 4/1 contacting — bids_pipeline's Drop on 4/15 conflates that later re-contact with the initial Nov 2012 cancellation |
| 8 | Company F 4/24 withdrawal | `DropTarget` | `Drop` | `DropTarget` | "Company F **declined** the invitation to schedule a management presentation, indicating it was **only interested in purchasing limited, select assets** of sTec" (p36) — Company F's decline driven by its scope preference; committee decides not to pursue. Borderline: voluntary decline or target rejection? Filing calls it Company F declining, then "no further communications" — best read as §I1 `Drop` (voluntary) OR `DropTarget` (special committee decision flows from Company F's select-assets stance). | **JudgmentCall** — Alex and Try harmonize on DropTarget; BP goes voluntary. I read as DropTarget (same pattern as Company E a few days later) → **TryRight + AlexRight** |
| 9 | Company C inclusion | — (skipped) | 2 rows (Bidder Interest + DropTarget) | — (skipped, matches Alex) | Company C expressed interest only in "particular assets of sTec" (p34); never signed NDA; §H3 clean skip + §M1 skip applicable | **BothAIRight** for skipping; **BP wrong** per §H3 `partial_bid_skipped` flag guidance |
| 10 | Target Sale rows | 1 row (absent from snapshot — Alex includes one implicitly via the flagging of the Feb 13 Board creation) — actually 0 Target Sale rows in Alex | 4 Target Sale rows (11/15/2012, 2/13/2013, 3/26/2013, 4/1/2013) | 1 Target Sale row (2/13/2013, tied to WDC as bidder) | §D1: Board resolves to sell → Target Sale. The special committee was established 2/13/2013 — single Target Sale event for the current process (phase 1). 11/15/2012 is Q4 earlier authorization (pre-committee) — could be a separate Target Sale row or collapsed. | **Mostly AlexRight** — minimum 1 Target Sale row; bids_pipeline over-emits (4 Target Sale rows is too many; §D1 treats the Board's sale resolution as a single event). bids_try's attachment of Target Sale to `bidder_name=WDC` is **wrong** — Target Sale rows have `bidder_name = null` per the schema (no bidder for a target-side event) |
| 11 | WDC NDA shape (§M4 stale-prior) | 1 row (4/17/2013) | 1 row (4/17/2013) | 2 rows (2009-01-29 phase-0 + 2013-04-17 phase-1 + `nda_revived_from_stale` flag) | "Mutual Non-Disclosure Agreement, dated January 29, 2009, together with that certain Special Addendum thereto, dated April 17, 2013" (merger agreement §1.1(k), p101). Filing narrates that the 4/17/2013 NDA is the addendum that revives/amends the 2009 original. | **JudgmentCall** — §M4's two-NDA rule was written for prior *sale process* NDAs (Penford 2007/2009). The 2009 WDC NDA was a commercial/technical mutual NDA, NOT a prior sale-process NDA. Whether to encode the 2009 original as phase-0 is ambiguous. bids_try's interpretation is defensible and more complete; Alex and BP's single-row is also defensible and matches reference convention |
| 12 | Final Round vocabulary richness | Final Round Inf Ann / Final Round Inf / Final Round Ann / Final Round / Final Round Ext Ann / Final Round Ext = 6 rows | Same 6 + 5/30 Final Round Ext | Final Round Ann only (1 row — only the 5/16 final-round announcement) | Filing has 2 round structures: 4/23 Inf Ann → 5/3 Inf / 5/16 Final Round Ann → 5/28 Final Round / 5/29 Final Round Ext Ann → 5/30 Final Round Ext. §K1 rich vocabulary. | **AlexRight + BPRight share vocabulary** — bids_try misses the Final Round Inf Ann / Inf / Final Round / Final Round Ext Ann / Final Round Ext rows. This is a significant under-emission. |
| 13 | Drop agency on Company G (5/3) | `Drop` | `Drop` | `Drop` | "Also on May 3, 2013, Company G indicated it would not continue in the process" — voluntary per §I1 | **Agreement — all correct** |
| 14 | Company B Drop date | None (Alex has no Drop row) | `Drop` 2013-02-27 (rough) | `Drop` 2013-03-05 (rough) | "Approximately two weeks later" after 2/13/2013 → 2/27/2013 | **BPRight** on the arithmetic, though bids_try's choice of 3/5 (17 days) is also reasonable. Alex's omission of the Drop is an incompleteness (§I1 would add a Drop row for a bidder who withdrew) |
| 15 | `bidder_type.base` filled for pre-NDA parties (Company A, Balch Hill, Potomac) | Not all bidders typed | Only ~8 named rows typed; most NA | Every bidder row typed | Filing describes each with industry label | **TryRight** (higher completeness, accurate classifications) |
| 16 | WDC `public: true` | NA in Alex workbook (Alex uses `note=public S` string); Alex reference JSON shows `bidder_type: null` on WDC's Executed row | `bidder_type_note = "public S"` on WDC rows | `public: true` on WDC rows | WDC is publicly traded (NYSE: WDC) — ground truth (market fact) | **TryRight**; BP matches on label string; Alex reference JSON loses it via converter policy (Austin's open question) |
| 17 | `Executed` row date | `bid_date_precise = 2013-06-14, bid_date_rough = 2013-06-23` (Alex convention: `bid_date_precise` = the bid date of the winning bid, `bid_date_rough` = execution date) | `bid_date_precise = 06/23/2013` | `bid_date_precise = 2013-06-23` | Merger agreement executed 2013-06-23 | **BPRight + TryRight** per §A (event date = execution date). Alex convention is legacy, not rulebook-compliant |
| 18 | WDC row count | 5 (NDA + 4 bids via alternations + Executed) | 6 (NDA + 5 bid events incl. 5/30 verbal re-affirm of $9.15 + Drop + Executed) | 8 (NDA 2009 + NDA 2013 + Target Sale + 4 bids + Drop 5/31 + Executed) | Actual WDC bid events: 5/3 ($6.60-7.10), 5/28 ($9.15), 6/10 ($6.60-7.10 revised), 6/14 ($6.85) = 4 bids + 1 executed. Plus 5/31 withdrawal = 1 drop. | Alex = 5 ✓ (misses 5/31 drop); BP = 6 ✓ but emits duplicate 5/30 re-affirmation row (not a new bid per §H5 — same price, same day); TRY = 7 real-event rows (correctly includes 5/31 drop + 5/28, 6/10, 6/14, 5/3, NDA, Executed). Summary: **TryRight on the drop**, **BPOver** on the 5/30 re-affirm which is verbal communication on the same price, not a new bid revision |
| 19 | Final Round Ann 5/16 `bidder_name` | null (correct per schema) | null (correct) | `WDC` (wrong — Final Round Ann is a target-side process event with no bidder) | §D1/§C1: Final Round Ann emits with no specific bidder (it's a round-structure event). Alex puts `bidder_name=NA`. | **AlexRight + BPRight**; bids_try wrong on `bidder_name=WDC` |
| 20 | Source-quote NFKC byte-for-byte compliance | N/A (Alex reference has no source_quote/source_page) | N/A (bids_pipeline has no source_quote/source_page columns) | Has source_page + source_quote; several rows flagged `source_quote_not_in_page` (hard) because the extractor used ASCII `"` but the filing uses Unicode curly quotes `“ ”` | §R3 / §P-R2 require byte-for-byte (post-NFKC) substring match | **TryFlagged on itself** — this is an extractor bug that bids_try caught via its own validator. Neither Alex nor bids_pipeline exposes the underlying data, so they can't be checked |

---

## Systemic findings

### Single-bound informal bids (§P-G2 + §H1)

The sTec filing has exactly **one true single-bound** bid:

- 2013-04-23 Company D verbal: "at a price **greater than $5.60** per share" — single lower bound per §H1.

Per §H1: `bid_value_lower = 5.60, bid_value_upper = null`. Populate `bid_lower_only` info flag.
Per §P-G2: this is not a true range (upper is null), so the row must carry a non-empty `bid_type_inference_note` ≤300 chars.

| Source | lower | upper | pershare | flag | inference note | §P-G2 pass? |
|---|---|---|---|---|---|---|
| Alex | 5.6 | NA | NA | none | none | Would fail §P-G2 if run through validator (no range, no note) — but Alex reference JSON convention omits notes |
| bids_pipeline | 5.6 | 5.6 | 5.6 | none | none | **Fails** §P-G2 (lower==upper is NOT a true range per §G2 "lower < upper"; no note) |
| bids_try | 5.6 | NA | NA | `bid_lower_only` (info) | Yes: "Verbal-only indication with no binding terms… informal per §G1 process-position fallback" | **Passes** §P-G2 |

**Extended observation — the broader point-vs-range representation problem.** bids_pipeline collapses EVERY point bid (D $5.75, D $5.60+, WDC $9.15×2, WDC $6.85, H $5.00-5.75, H $5.00-5.75 reaffirm, WDC $6.60-7.10×2) into `lower = upper = pershare`. This has two problems:
1. On single-bound bids (4/23 $5.60+), it fabricates an upper bound equal to the lower bound, losing the "open upper" signal.
2. On all bids, it fails the §G2 range satisfier (needs `lower < upper`), so the §P-G2 validator would mark every bids_pipeline bid row `bid_type_unsupported` (hard) + `bid_range_inverted` (hard — since `lower >= upper` when they're equal).

This is the **biggest structural problem** with bids_pipeline on this deal.

### Bidder-type accuracy

Per §F2 decision table, every Company A–H appears only with industry-label descriptors ("a participant in the storage industry", "a participant in the electronics industry", "a participant in the semiconductor industry"). None is described as a PE/sponsor, PE executive, or mixed — all default to §F2 row 2 or 3 (publicly traded operating co or CEO-level contact) → `base: "s"`. Filing never states whether any of A–H is publicly traded → `public: null` is correct (bids_try) or `public: false` (bids_pipeline's blank) is wrong by omission — public status is unknown, not false.

WDC is known publicly traded (NYSE) → `public: true`.
Balch Hill + Potomac are activist hedge funds (non-strategic buyers) → `base: "f"` per §F2 row 1 (PE/fund).

| Bidder | Alex (note string) | bids_pipeline (note string) | bids_try (structured) | Ground truth (§F2) |
|---|---|---|---|---|
| Company A | "S" | NA | `{base:"s", non_us:false, public:null}` | `s`, public unknown |
| Company B | "S" | "S" | `{base:"s", non_us:false, public:null}` | `s`, public unknown |
| Company D | "S" | "S" | `{base:"s", non_us:false, public:null}` | `s`, public unknown |
| Company E | "S" | "S" | `{base:"s", non_us:false, public:null}` | `s`, public unknown |
| Company F | "S" | "S" | `{base:"s", non_us:false, public:null}` | `s`, public unknown |
| Company G | "S" | "S" | `{base:"s", non_us:false, public:null}` | `s`, public unknown |
| Company H | "S" | "S" | `{base:"s", non_us:false, public:null}` | `s`, public unknown |
| WDC | "S" | "public S" | `{base:"s", non_us:false, public:true}` | `s`, public=true |
| Balch Hill | — | NA | `{base:"f", non_us:false, public:null}` | `f` (hedge fund) |
| Potomac | — | — | `{base:"f", non_us:false, public:null}` | `f` (hedge fund) |
| BofA (IB) | — (role=advisor_financial) | NA | `{base:null}` w/ role advisor | advisor — N/A |

**Verdict.** bids_try gets every classification right. bids_pipeline matches Alex's abbreviated string convention but is incomplete on ~15 rows (NA instead of "S"). Austin's note "17 bidder_type field diffs" — these are almost all bids_try → Alex reference where Alex loses `public: true` on WDC or has null on bidder_type in pre-NDA rows. This is **converter-side policy**, not rulebook drift — applying the WDC→public rule to the Alex reference converter would close them.

### Dates

All three sources agree on the precise calendar dates they capture. Differences are in *which* rough-date anchor is used when the filing is imprecise (e.g., Company B Drop "approximately two weeks after 2/13/2013" → BP=2/27, TRY=3/5, Alex=omitted). Both BP and TRY attach a rough-date phrase consistent with §B2/§B3; the 2/27 vs 3/5 split is within the tolerance band of "approximately two weeks."

Alex's `bid_date_precise = 2013-04-04` convention on pre-NDA rows (Company B, Company D, BofA IB) is a **legacy workbook artifact** — Alex normalizes precise dates on pre-NDA rows to the first NDA-signing date (4/4/2013). This is inconsistent with §B1/§B2 and is not carried by BP or TRY. The actual filing-stated dates are used by both AI pipelines.

### Source-quote presence

| Source | Has `source_quote` | Has `source_page` | NFKC-verified against `pages.json` |
|---|---|---|---|
| Alex | No | No | N/A |
| bids_pipeline | No | No | N/A |
| bids_try | Yes, every row | Yes, every row | 6 rows flagged `source_quote_not_in_page` (hard) due to ASCII vs Unicode curly-quote mismatch — extractor bug. Spot-check: my NFKC substring check on 12 of bids_try's quotes (including the flagged ones) found 12/12 present; only the verbatim-quote-char mismatch trips §P-R2 |

Only bids_try satisfies §R3 / §P-R2's evidence-citation requirement (modulo the curly-quote extractor bug which flags itself).

---

## Specific rule/prompt fixes

### For bids_pipeline (the extractor that produced `stec_bids_pipeline.csv`)

1. **STOP collapsing point bids into `lower == upper`.** Per §H1, point bids populate `bid_value_pershare` only; `lower` and `upper` remain null. Single-bound bids populate ONE of `lower` / `upper`; the other stays null. This is the single largest correctness fix.
2. **Emit `bid_type_inference_note` on every non-range bid row.** Current extractor emits NO inference notes. Without them, no bid row passes §P-G2. Add a prompt clause: "For every non-range Bid row, write a ≤300-char `bid_type_inference_note` citing the §G1 trigger or fallback rule."
3. **Correct Company H 5/23 agency.** Filing is clearly target-initiated ("was not sufficient to move them forward in the process"). Emit `DropBelowInf`, not `Bid` followed by `DropAtInf`.
4. **Apply §H3 partial-bid skip to Company C.** Company C never signed an NDA and was interested only in particular assets. Emit `partial_bid_skipped` deal-level info flag instead of event rows.
5. **Reconcile Target Sale row count.** §D1 treats the Board's sale resolution as a single `Target Sale` event per phase. Current 4 `Target Sale` rows is over-emission; should collapse to 1 (on 2013-02-13 — committee formation) or 2 (mid-Nov 2012 preliminary authorization + 2013-02-13 committee formation).
6. **Add Potomac as separate Activist Sale row.** Per §D1.b default (per-activist rows unless coordinated group).
7. **Missing source_quote / source_page.** Adding `source_quote` + `source_page` would enable §P-R2 verification; currently unverifiable.

### For bids_try (the extractor that produced `stec_bids_try.csv`)

1. **Fix the ASCII vs Unicode curly-quote bug in source_quote extraction.** Multiple rows emit ASCII straight quotes `"Balch Hill"` / `"Potomac"` while the filing uses `"Balch Hill"` / `"Potomac"`. Normalize the source-quote character set to match `pages[source_page-1].content` byte-for-byte.
2. **Add missing Final Round vocabulary rows.** bids_try emits only 1 Final Round row (Final Round Ann 5/16) but the filing narrates **6 final-round events**: Final Round Inf Ann 4/23, Final Round Inf 5/3, Final Round Ann 5/16, Final Round 5/28, Final Round Ext Ann 5/29, Final Round Ext 5/30. §K1 + §K2 vocabulary is well-defined for this.
3. **Fix `bidder_name` on Target Sale and Final Round Ann rows.** bids_try emits `bidder_name=WDC` on Target Sale 2/13 and Final Round Ann 5/16 — these are target-side events and should have `bidder_name = null`.
4. **Consider whether §M4 applies to non-sale-process NDAs.** bids_try encodes WDC's 2009 NDA as a phase-0 row under §M4. §M4 was written for prior *sale processes* (Penford 2007/2009). The 2009 WDC NDA was a commercial/technical mutual NDA (WDT was a potential customer of sTec's SSDs). The rulebook should either (a) clarify that §M4 applies to any prior-dated NDA, or (b) restrict §M4 to sale-process NDAs and emit only the 4/17/2013 addendum NDA. Current behavior is ambiguous.
5. **Emit Potomac's type as `F` + a `multi_activist_coordination_ambiguous` soft flag.** Filing's "Balch Hill was later joined by Potomac… jointly increased their beneficial holdings" walks the §D1.b ambiguity line. Default to per-activist rows (done), but add the flag.

### For the rulebook

1. **§M4 clarification.** Add explicit language: "Stale-prior NDAs emitted as phase-0 must have been signed under a **prior sale process** (e.g., Penford 2007/2009) or under an auction-like strategic review. Regular commercial / operational mutual NDAs between the parties (e.g., WDC–sTec 2009 technical NDA) do NOT qualify as §M4 phase-0 and should not be emitted as separate NDA rows when their only function is that they were later amended/extended to cover the current process." Alternative: expand §M4 to cover all prior-dated NDAs and add a `nda_purpose` field.
2. **§G2 / §P-G2 validator behavior on `lower == upper`.** The validator should explicitly flag `bid_range_inverted` when lower == upper. Current §P-G2 text says "inverted ranges (lower >= upper)" which includes equality, but add an example for the collapsed-point-bid failure mode.
3. **§D1 Target Sale multiplicity.** Clarify whether multiple internal Board-level milestones (e.g., "mid-Nov 2012 authorization to contact advisors" vs. "2013-02-13 committee formation" vs. "2013-03-26 board approval of BofA retention + strategic outreach decision" vs. "2013-04-01 BofA begins contacting acquirers") each warrant a Target Sale row, or whether one is enough. Current bids_pipeline emits 4; Alex emits 0–1; bids_try emits 1. The rulebook should give concrete guidance.

---

## Open questions for Austin

1. **Does the WDC 2009 NDA qualify as §M4 phase-0?** The merger agreement page 101 confirms it's an extant Mutual NDA between the parties dating to 2009-01-29. bids_try treats it as §M4 stale prior (phase 0 + nda_revived_from_stale flag). Alex and bids_pipeline collapse to the single 2013-04-17 addendum row. Is your preferred convention "phase-0 only for prior sale-process NDAs" (Penford pattern), or "phase-0 for any substantively prior NDA"?

2. **Company C — §H3 partial-bid skip or emit as a drop?** Company C (semiconductor, 3/13) expressed interest only in "particular assets" and never signed an NDA. Alex and bids_try omit (per §H3 / §M1). bids_pipeline emits Bidder Interest + DropTarget. Per current §H3, skip is correct. Confirm or revise.

3. **Company A — emit 2 rows or skip?** Company A IB approached on 11/14/2012, draft NDA provided, meeting cancelled same day due to target's concerns about Company A management involvement. Company A never signed an NDA. Later (after 4/1/2013) Company A is listed among "9 not interested". Alex omits. bids_pipeline emits 2 rows (Bidder Interest 11/14 + Drop 4/15 — wrong date for the withdrawal). bids_try emits 2 rows (Bidder Interest + DropTarget both on 11/14 — more faithful). Preferred? Does §M1 apply (no NDA + no price stated, but bid intent IS stated via "draft NDA provided")?

4. **Activist row multiplicity — Balch Hill + Potomac.** Filing narrates them with partial coordination ("Balch Hill was later joined by Potomac… jointly increased their beneficial holdings"). Per §D1.b ambiguity default → per-activist rows. bids_try emits 2, bids_pipeline emits 1 (Balch Hill only), Alex emits 0. Confirm Potomac should be a separate Activist Sale row.

5. **Final Round vocabulary depth.** Alex and bids_pipeline emit 6 final-round rows covering Inf Ann, Inf, Ann, Round, Ext Ann, Ext. bids_try emits only Final Round Ann. For a 2-bidder final round with an extension, is the full 6-event ladder the desired granularity, or is the single Ann row sufficient signal? The rulebook (§K1, §C1) supports all 6 codes.

6. **Company H dropout** — agreement that this should be `DropBelowInf` (target-initiated) per §I1? Currently Alex = `Drop`, bids_try = `DropBelowInf`, bids_pipeline = `DropAtInf`. The target-initiated reading is the clearer interpretation of "not sufficient to move them forward in the process" (p37, week of 5/13).

7. **Overall: accept bids_try as the stec iteration baseline?** It is closer to the rulebook on §P-G2, §H1, §D1.b, §I1 agency, §R3 evidence. Remaining gaps are the Final Round vocabulary breadth (#5), source_quote curly-quote extractor bug, and the Target Sale / Final Round Ann bidder_name misattribution (minor cleanup). bids_pipeline's bid-value representation requires a substantive extractor fix before it can pass §P-G2.

---

*Report prepared 2026-04-21 by three-way audit agent.*

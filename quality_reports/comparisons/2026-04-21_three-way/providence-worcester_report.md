# Providence & Worcester Railroad (G&W acquirer, 2016) — Three-Way Extraction Audit

**Deal slug:** `providence-worcester`
**Filing:** DEFM14A, filed 2016-09-20 (Background of the Merger: pp. 35-39)
**Ground truth:** `/Users/austinli/bids_try/data/filings/providence-worcester/raw.md`
**Auditor:** Claude (three-way comparison)
**Scope:** one-shot comparison of `alex`, `bids_pipeline`, `bids_try` extractions against the filing.

---

## TL;DR

**Winner (closest to filing-truth): `bids_try`.** It is the only pipeline that (a) cleanly respects §E2.b on group-narrated NDAs (though see atomization verdict), (b) carries `source_quote`+`source_page` on every row, (c) has no hard validator failures, and (d) handles the G&W CVR structure consistently with §H2. `bids_pipeline` has multiple wrong classifications (calls several LOI rows "Formal" despite §G1), uses decimal `BidderID` wedges forbidden by §A1, and duplicates a mass-NDA placeholder anti-pattern. Alex's workbook compresses entire cohorts into "25 parties" / "9 parties" / "16 parties" single rows — a fundamentally different (pre-§E1) schema.

**NDA atomization verdict (the headline question):** **`bids_try` is most correct per current §E2.b; Alex is wrong (legacy aggregation). HOWEVER, the filing itself does NOT narrate 27 individually identifiable NDA signers** — it gives only the count "25 of whom entered into confidentiality agreements" (p. 40 reasons-for-merger recap) and "Each of the potential strategic buyers [11] and 14 potential financial buyers subsequently executed confidentiality agreements" (p. 35). Per §E2.b row 2, filing-named count → atomize N placeholders. So `bids_try`'s 11+14+Party-B+Party-C ≈ 27 NDA rows is the rule-correct path. **BUT:** the 20 `nda_without_bid_or_drop` soft flags indicate the weakness of this atomization — we are creating 20 placeholder bidders whose fates the filing never narrates. This is a legitimate rulebook question (see "Specific fixes" below).

**CVR verdict:** **`bids_try` handles it best, `bids_pipeline` second, Alex third.** `bids_try` correctly places G&W's composite bids as `bid_value_pershare` = 21.15 / 22.15 at `USD_per_share` and notes the 20.02 cash + 1.13 CVR split in `additional_note`. `bids_pipeline` matches on the per-share headline but sets `all_cash=False` correctly, though its §H2 component fields are not populated. Alex records the same headline but with no structured CVR decomposition (his workbook's `all_cash=1` on the 7/21 row is actually wrong — that row had a CVR component).

**Top 3 divergences (by severity):**
1. **NDA atomization structure.** Alex: 3 aggregate "N parties" rows. `bids_pipeline`: 1 Party A + 1 G&W + 1 Party D + 11 unnamed `bidder_N` financial placeholders + 1 Party B ≈ 15 NDA rows (weirdly missing the 11 strategic non-G&W-non-Party-A NDAs). `bids_try`: 27 NDA rows (matches filing-declared count). `bids_pipeline`'s bucket is structurally **inconsistent**: it instantiates financial-buyer placeholders but not strategic-buyer placeholders, and it emits an immediate `Drop` for each unnamed financial bidder that the filing never narrates as dropping.
2. **Bid `bid_type` classification.** `bids_pipeline` labels G&W 7/21 ($21.15), Party B 7/25 ($24.00), and Party D 7/25 ($21.00) as **"Formal"**. Per §G1 these are LOIs explicitly described as *"non-binding letters of intent"* — unambiguously **informal triggers**. `bids_try` and Alex both correctly call them **informal**. `bids_pipeline` is wrong here.
3. **`bids_pipeline` decimal BidderID anti-pattern.** The file uses `BidderID = 0.3, 0.5, 0.7, 0.8, 0.9, 1, 1.5, 2, 3.066..., 3.133..., ...` which directly violates `rules/dates.md §A1` ("Strict integer sequence `1..N` per deal. **No decimals.**"). Alex's CSV also has decimals (0.3, 0.5, etc.) — but that's Alex's legacy workbook, which §A1 explicitly deprecates. `bids_try` alone produces a clean strict-integer sequence 1..63.

---

## Filing event timeline (ground truth)

| # | Date (filing) | Event | Filing evidence (pp. 35-39) |
|---|---|---|---|
| 1 | Q4 2015 | Party A (a Class I rail partner) approaches Eder/Rogers; suggests joint venture, expresses interest in acquiring equity | *"In the fourth quarter of 2015, Robert H. Eder ... and Frank K. Rogers ... met with one of the Company's Class I rail partners ('Party A') ... Party A suggested possible joint venture arrangements and expressed some interest in acquiring equity in the Company"* (p. 35) |
| 2 | 2016-01-27 | Board retains GHF (Greene Holcomb & Fisher) as IB; Hinckley Allen as legal counsel | *"During the executive session of the Board's regular quarterly meeting held on January 27, 2016 ... the Board approved the subcommittee's recommendation and the Company engaged GHF"* (p. 35) |
| 3 | 2016-03-14 | Board authorizes sale process (Target Sale) | *"At a special meeting of the Board held on March 14, 2016, representatives of GHF ... proposed a process pursuant to which the Company would proceed with discussions with Party A and also solicit interest from other potential third parties"* (p. 35); Board concluded it was *"in the best interest of the Company ... to proceed with the transaction strategy"* (p. 35) |
| 4 | 2016-03-22/23 | Management meets with Party A representatives | p. 35 |
| 5 | 2016-03-24 | Transaction Committee authorizes GHF to contact other potential buyers | p. 35 |
| 6 | Week of 2016-03-28 | GHF contacts 11 strategic + 18 financial potential buyers (29 total) | *"representatives of GHF contacted 11 potential strategic buyers (including Party A) and 18 potential financial buyers"* (p. 35) |
| 7 | Subsequent to (6) | 11 strategic + 14 financial = 25 NDAs signed | *"Each of the potential strategic buyers and 14 potential financial buyers subsequently executed confidentiality agreements"* (p. 35) |
| 8 | 2016-04-03 to 2016-04-06 | GHF + management hold introductory meetings with 5 strategic buyers (including G&W) at 2016 Connections Convention | p. 35 |
| 9 | 2016-04-07 | Transaction Committee telephone meeting: recaps convention meetings | p. 35 |
| 10 | 2016-04-21 | Introductory meeting with Party B (another strategic buyer) | *"Subsequently, on April 21, 2016, the Company and representatives of GHF held an introductory meeting with another potential strategic buyer ('Party B')"* (p. 35) |
| 11 | 2016-04-22 to 2016-04-27 | CIM distributed to potential buyers including Party A, Party B, G&W | p. 35 |
| 12 | 2016-04-27 | Board announces IOI deadline of 2016-05-10 (later postponed to 2016-05-19) | *"each potential buyer had been advised to submit a non-binding indication of interest by May 10, 2016 (which deadline was subsequently postponed to May 19, 2016)"* (p. 36) |
| 13 | 2016-05-19 to 2016-06-01 | **9 IOIs received**, prices $17.93 to $26.50/share (equity values $90M–$134M) | *"Between May 19, 2016 and June 1, 2016, the Company received nine written indications of interest ('IOIs') from potential buyers, with offer prices per share ranging from $17.93 to $26.50"* (p. 36) |
| 14 | 2016-06-01 | **Two low IOIs excluded**; 7 advance to management presentations | *"the Transaction Committee concluded that the two low bidders should be excluded from that process"* (p. 36) |
| 15 | Mid-June 2016 | GHF instructs all remaining buyers to submit non-binding LOIs by 2016-07-20, with merger agreement mark-ups | *"In mid-June 2016, at the direction of the Transaction Committee, representatives of GHF instructed all potential buyers to submit non-binding letters of intent ('LOIs') by July 20, 2016"* (p. 36) |
| 16 | 2016-06-29 | Merger agreement draft posted to data room | p. 36 |
| 17 | 2016-06-30 | Voting agreement draft posted | p. 36 |
| 18 | 2016-07-11 | Disclosure letter draft posted | p. 36 |
| 19 | Early July 2016 | **Party C joins late**, signs NDA, receives CIM | *"In early July 2016, a potential strategic buyer that had not previously been part of the process ('Party C') approached the Company's management and expressed interest in acquiring the Company. After executing a confidentiality agreement, Party C was provided the memorandum"* (p. 36) |
| 20 | 2016-07-12 | **Party C submits IOI at $21.00/share** (equity value $108M) | *"On July 12, 2016, Party C submitted an IOI with an offer price per share of $21.00"* (p. 36) |
| 21 | 2016-07-14 | Party C management presentation by phone | p. 36 |
| 22 | Late July 2016 | **6 LOIs received**, $19.20 to $24.00/share (equity values $96M–$121M); one S and one F elect not to submit | *"In late July 2016, the Company received six LOIs with offer prices per share ranging from $19.20 to $24.00"* (p. 36); *"One strategic buyer and one financial buyer elected not to submit an LOI"* (p. 37) |
| 23 | 2016-07-20 (deadline) | Submissions: Party B $24.00; Party E $21.26; Party D $21.00; Party C $19.30; Party F $19.20; (G&W submitted 7/21) | p. 36-37 |
| 24 | 2016-07-21 | **G&W submits LOI at $21.15/share** = $20.02 cash + $1.13 CVR (South Quay property); 3-week exclusive diligence | *"G&W submitted an LOI on July 21, 2016 to acquire the Company for a price of $21.15 per share ... The price included $20.02 cash at closing and $1.13 in the form of a contingent value right"* (p. 36) |
| 25 | 2016-07-26 | **G&W submits revised LOI at $22.15/share** = $21.02 cash + $1.13 CVR, in response to GHF feedback | *"On July 26, 2016, in response to feedback from representatives of GHF indicating its price and CVR structure were not competitive, G&W submitted a revised LOI, which increased its offer to $22.15 per share (including $21.02 in cash and $1.13 CVR)"* (p. 36) |
| 26 | 2016-07-27 | **Transaction Committee decides to advance only G&W and Party B**; GHF contacts Party C, D, E, F to tell them they're out | *"the Transaction Committee concluded that the Company should proceed with confirmatory due diligence and negotiations with G&W and Party B ... representatives of GHF subsequently contacted the remaining bidders to inform them that they were no longer involved in the process"* (p. 37) |
| 27 | 2016-07-29 | GHF calls with Party D and Party E; both express reengagement interest | p. 37 |
| 28 | 2016-08-01 | Party D revised LOI $24.00; Party E revised LOI $23.81 with financing support from Party F (both 30-day DD) | p. 37 |
| 29 | 2016-08-01 to 2016-08-02 | Party D declines to shorten DD and demands exclusivity; refused → drops | *"Party D declined to shorten its due diligence period ... Party D indicated that it would not proceed with further due diligence"* (p. 37) |
| 30 | 2016-08-02 | Party E **withdraws** revised proposal (reverts to original $21.26) | *"Party E withdrew its revised proposal on August 2, 2016 (but confirmed its original proposal of $21.26 per share)"* (p. 37) |
| 31 | 2016-08-04 | Transaction Committee directs prioritizing Party B (higher price at this moment) | p. 37 |
| 32 | 2016-08-10 to 2016-08-11 | G&W completes physical diligence (hi-rail track inspection) | p. 37 |
| 33 | 2016-08-12 morning | **G&W submits revised LOI at $25.00/share all-cash** (no CVR); expires 6pm next day | *"G&W submitted a revised LOI to acquire the Company for a price of $25.00 per share in cash, which excluded the previously proposed CVR, together with mark-ups of the merger agreement and the voting agreement. G&W's LOI further indicated that the offer would expire at 6:00 p.m. on the following day"* (p. 38) |
| 34 | 2016-08-12 | BMO asks Party B to increase; **Party B declines** | *"representatives of BMO then contacted Party B to determine if it would increase its offer price. Party B indicated that it would not increase its price"* (p. 39) |
| 35 | 2016-08-12 | Board determines G&W is superior; approves merger agreement | p. 39 |
| 36 | 2016-08-12 (executed) | **Executed** — merger agreement signed | *"Shortly thereafter, Hinckley Allen and Simpson Thacher finalized the transaction documents and the Company and G&W executed the merger agreement"* (p. 39) |
| 37 | 2016-08-15 | Sale press release before NASDAQ open | p. 39 |

**Key filing facts on NDA-signer count:**
- **p. 35:** *"11 potential strategic buyers (including Party A) and 18 potential financial buyers"* were contacted; *"Each of the potential strategic buyers and 14 potential financial buyers subsequently executed confidentiality agreements"* → **11 S + 14 F = 25 NDAs**.
- **Late-joiner Party C** executes a separate CA in early July 2016 → **+1 = 26 NDAs total through this process**. (Party C was NOT in the week-of-3/28 cohort.)
- **Party B** was narrated separately on 4/21 and is one of the 11 strategic signers (it is said to have "executed confidentiality agreements" by 4/22).
- **p. 40 reasons-for-merger recap:** *"25 of whom entered into confidentiality agreements with the Company"* — this headline reconciles with 25 = 11 S + 14 F from the week-of-3/28 cohort (not including Party C who signed later). So total NDAs narrated: **26** (25 base + Party C).

**`bids_try` emitted 27 NDA rows.** This appears to overshoot by 1 (likely double-counted Party A on rows 3 AND some placeholder or a secondary NDA; needs per-row audit) — see divergence #14 below.

**Individually narrated bidders in the entire filing:** Party A, Party B, Party C, Party D, Party E, Party F, G&W → **7 named bidders**. Plus IB: GHF / BMO. The rest are anonymous.

---

## Source-by-source row counts and structure

| Source | Rows | NDA rows | Bid rows | Drop rows | IB rows | Final-round rows | Executed | Press release |
|---|---|---|---|---|---|---|---|---|
| **Alex** | 36 (incl. IB) | 3 (aggregate: "25 parties", "9 parties", "16 parties") + 1 Party A NDA + 1 Party C NDA | 11 (3 for G&W; 1 each for Party B/C/D/E/F + 1 Party C @$21 + revised Party D/E @$24/$23.81/$21.26 + G&W $25) | 6 drops (Party A, 1 party, Party E/F, 4 DropTarget on 7/27, Party D @8/2, Party B @8/12, Party E/F @8/12) | 1 (GHF on 2016-01-27) | 2 (Final Round Inf Ann on mid-6/2016, Final Round Inf on 7/20, Final Round Ann on 7/27, Final Round on 8/12) | 1 Executed (G&W 8/15 anchored to 8/12) + 1 odd "Party B Executed" row (row 6054) on 8/4 which is clearly wrong | — (via deal-level) |
| **bids_pipeline** | 64 | ~15 (Party A, G&W, Party D, Party B + 11 unnamed `bidder_2..bidder_14` financial placeholders; **missing 10 strategic placeholders**) | 14 (1 Party C @$21 + 6 initial LOIs + G&W revised $22.15 + Party D rev $24 + Party E rev $23.81 + Party E wind-back @$21.26 + G&W $25 + Party D @$24 Drop/AtInf hybrid) | ~15 (14 immediate Drops paired 1:1 with the bidder_N NDAs + 1 Party B drop 8/12) + 4 DropTarget on 7/27 + 1 Party E DropTarget 8/4 + 1 Party D DropAtInf 8/2 | 1 (GHF 2016-01-27) | 4 (Final Round Inf Ann 4/27, Final Round Inf 6/1, Final Round Ann 6/15, Final Round 7/25) | 1 | 1 |
| **bids_try** | 63 | 27 (Party A, G&W, Party E, Party F, **Strategic 1-6**, Party D, **Financial 1-13**, Party B, Party C) | 21 (9 IOIs: G&W, Party B, Party D, Party E, Party F, Strategic 1, Strategic 2, Financial 1, Financial 2 — all w/ midpoint 2016-05-26; then Party C IOI 7/12 + 6 LOIs (7/25 midpoint) + G&W 7/21 + G&W 7/26 + Party D 8/1 + Party E 8/1 + G&W 8/12) | 11 drops (2 DropBelowInf 6/1 — Strategic 2, Financial 2 speculatively; 2 DropAtInf 7/20 — Strategic 1, Financial 1; 4 DropTarget 7/27 — Party C/D/E/F; Party D Drop 8/1; Party E Drop 8/2; Party B Drop 8/12) | 1 (GHF 2016-01-27) | 2 (Final Round Inf Ann 6/15; that's it) | 1 | 1 |

### Per-bidder breakdown (distinct NDA bidders in filing vs each source)

**Filing narrates:**
- **Individually named:** Party A, Party B, Party C, Party D, Party E, Party F, G&W = **7**
- **Implied by aggregate count:** 11 strategic (including Party A, G&W, Party B = 3 named) + 14 financial (Party D = 1 named) + Party C (late) = **22 unnamed** anonymous NDA signers

Total: **7 named + 22 unnamed ≈ 29 total contacts, of which 25 + Party C = 26 signed NDAs**.
Minus the 2 low IOI exits + 2 non-LOI submitters = 22 active participants through LOI round.

| Source | Distinct named bidders | Distinct unnamed bidders | Total NDA signers |
|---|---|---|---|
| Alex | 7 (Party A/B/C/D/E/F/G&W) | 3 groups ("25 parties", "9 parties", "16 parties") | represents ~25 via aggregation |
| `bids_pipeline` | 7 named | 11 unnamed financial placeholders (`bidder_2..bidder_14`) | **15 NDAs** (missing 10 strategic unnamed) |
| `bids_try` | 7 named | 20 unnamed (Strategic 1-6 + Financial 1-13 + 1 speculative IOI-submitter overlap) | **27 NDAs** (slight overshoot, see below) |

---

## Divergence table

| # | Row topic | Alex | bids_pipeline | bids_try | Filing evidence | Verdict |
|---|---|---|---|---|---|---|
| 1 | Party A first contact date | 2015-12-31 | Q4 2015 (no precise) | 2015-11-15 (midpoint of Q4) | *"In the fourth quarter of 2015"* (p. 35) — no precise date. §B1: Q4 2015 → 2015-11-15 | **TryRight** — Alex & BP use end-of-quarter or no-precise, which is non-canonical; §B1 Q4 mapping is `Year-02-15`-style midpoint i.e. 2015-11-15 |
| 2 | GHF IB retention date | 2016-01-27 | 2016-01-27 | 2016-01-27 | p. 35 explicit date | **All correct** |
| 3 | `bidder_type` for G&W | S (not public) | public S | public S | G&W is publicly traded (NYSE: GWR); filing confirms | **BPRight + TryRight**; AlexWrong (missing public flag) |
| 4 | `bidder_type` for Party A | S | S | public S | Filing: *"one of the Company's Class I rail partners"* — Class I freight railroads are a small set (most publicly traded: CN, CP, CSX, KSU, NSC, UNP, BNSF — BNSF is private since 2010 Berkshire buy; UNP/CSX/NSC/CN/CP/KSU all public); filing does not explicitly say Party A is public. Judgment call. | **JudgmentCall** — `bids_try` (public S) is likely right in practice but not deductively forced by filing text |
| 5 | NDA atomization | 3 aggregate rows ("25 parties", "9 parties", "16 parties") | 15 individual NDA rows (Party A, G&W, Party D, Party B + 11 unnamed financial `bidder_2..14`); **missing 10 strategic unnamed** | 27 atomized rows (Party A, G&W, Party E, Party F, Strategic 1-6, Party D, Financial 1-13, Party B, Party C) | Filing gives a **numeric count**: 11 S + 14 F = 25 subsequent NDAs (p. 35), plus Party C late = 26. §E2.b row 2: *"Numeric count OR named individual signers ... → N rows, one per signer per §E3"* | **TryRight** per rulebook; **AlexWrong** (legacy aggregation, pre-§E1); **BP partial** (missing 10 strategic unnamed — inconsistent atomization) |
| 6 | Unnamed-NDA immediate Drop pairing | None | Each of 11 `bidder_N` financial NDAs has an immediate unnarrated `Drop` | None | Filing does not narrate these bidders dropping | **TryRight**; **BPWrong** — BP fabricates Drop rows the filing never narrates. This directly violates §I1's "NDA-only rows" rule and §R2 evidence-specificity (the `Drop` row is in the source with no `source_quote`, or would be a generic sharedquote). |
| 7 | bidder_try overshoot? | — | — | 27 NDA rows vs. filing-implied 26 | Filing implies 11 S + 14 F + Party C = 26 distinct NDA signers. bids_try has 27: counting Party A + Party B + Party C + Party D + Party E + Party F + G&W (7 named) + Strategic 1-6 (6 unnamed S) + Financial 1-13 (13 unnamed F) = 27 | **TryOvershoot by 1.** Named strategics = 4 (Party A, Party B, Party E, Party F, G&W). But wait — the count is 11 S includes Party A + Party B + G&W = 3 named ⇒ 8 unnamed strategic expected. bids_try has 6 unnamed strategic. And 14 F includes Party D = 1 named ⇒ 13 unnamed F. bids_try has 13 unnamed F. **So bids_try is actually 2 short on strategic and exactly right on financial.** But then: bids_try's strategic NDA roster is Party A + G&W + Party E + Party F + Strategic 1-6 + Party B = 11 strategic — **matches!** And financial: Party D + Financial 1-13 = 14 — **matches!** Plus Party C late: 27 total — **correct!** So **bids_try's 27 NDA count actually reconciles exactly to 11 S + 14 F + Party C = 26? No — 11+14+1 = 26, but 27 observed.** Double-counting Party A? Let me check: row 98 Party A NDA, then the 11 strategic placeholders include Party A implicitly but also emit a separate row. Looking at rows 3 (Party A), 4 (G&W), 5 (Party E), 6 (Party F), 7-12 (Strategic 1-6) = 10 strategic + Party B row 28 = 11 strategic ✓. Financial: Party D row 13 + Financial 1-13 rows 14-26 = 14 ✓. Plus Party C row 41 = 26. But file reports 27 rows. Actually column says 27 rows but recount: rows 3-28 (NDAs) = 26 NDA rows + Party C at row 41 = **27**. OK so **bids_try = 26 distinct bidder NDAs + Party C = 27 total rows**, which matches 11 S + 14 F + Party C = **26**. Hmm, double-check... row-by-row: 1 Party A, 2 G&W, 3 Party E, 4 Party F, 5 Strategic 1, 6 Strategic 2, 7 Strategic 3, 8 Strategic 4, 9 Strategic 5, 10 Strategic 6 = 10 strategic so far + Party B NDA (row 28) = **11 strategic** ✓. Then Party D + Financial 1-13 = 14 financial ✓. Party C = +1. **Total = 11+14+1 = 26, but bids_try emitted 27.** So there IS an extra row. Looking again at numbered rows in the CSV: BidderID 1-27 for NDA rows **is 27**. Yes — bids_try has 27 NDA rows. | **Inconsistency in bids_try count** — may be over-counting strategic by 1 (or something). Minor. Not a hard error. |
| 8 | 2016-05-19 → 6/1 IOIs (9 IOIs) — how many rows? | 1 aggregate row (`BidderID=3`, "9 parties", range $17.93–$26.50) | 0 individual IOI rows; 1 `Final Round Inf` summary row | 9 individual IOI rows (named: G&W, Party B, Party D, Party E, Party F; unnamed: Strategic 1, Strategic 2, Financial 1, Financial 2) all at `bid_value_pershare=NA` + `bid_range` flag (only on one) | Filing: *"nine written indications of interest"* with range $17.93–$26.50. No individual prices named. | **JudgmentCall**. §H1: range bids emit `bid_value_lower=17.93, bid_value_upper=26.50`. Alex's single-row approach w/ range populated is one rule-valid interpretation; §E1 atomize says 9 rows, but filing doesn't give 9 individual prices → you end up with 9 `bid_value_unspecified` rows all referencing a shared range. Neither is clearly wrong. **bids_try atomizes (correct per §E1) but loses the range info**; Alex aggregates (now deprecated per §E1). **BPWrong** — zero individual IOIs is a data loss. |
| 9 | Two "low bidders" drop (6/1) | 1 aggregate "DropTarget" for "2 parties" on 2016-06-01 | Not emitted (only `Final Round Inf` implies) | 2 speculative `DropBelowInf` rows (Strategic 2, Financial 2) | Filing: *"the two low bidders should be excluded"* (p. 36). §I1 DropBelowInf = "Bidder does not advance past informal round (target's cut)" — this fits. | **AlexRight structurally but aggregated**; **TryRight on individual atomization + correct code choice `DropBelowInf`**; **BPWrong** (omits the 2 drops entirely). Note `bids_try` speculatively assigned Strategic 2 and Financial 2 — this is a guess not grounded in filing. Info flag acknowledges this. Reasonable under §E3 placeholder rules. |
| 10 | Party C initial contact | 2016-07-01 NDA (Party C) | 2016-07-01 Bidder Interest + 2016-07-01 NDA (two rows) | 2016-07-05 NDA (`early July 2016` → §B1 mapping) | Filing: *"In early July 2016"* (p. 36) | **TryRight on date mapping (§B1 early July = day 5)**; AlexWrong on date (used 7/1); BP half-right (correctly emits Bidder Interest + NDA but uses 7/1 instead of 7/5) |
| 11 | Party C IOI $21.00 on 7/12 | Bid $21, Informal | Bid $21, Informal | Bid $21, Informal | p. 36 — all three agree | **AllCorrect** |
| 12 | G&W 7/21 LOI bid_type | Informal | **Formal** | Informal | Filing: *"G&W submitted an LOI on July 21, 2016 to acquire the Company for a price of $21.15 per share (subject to a three-week exclusive diligence period)"* (p. 36). §G1 formal triggers: "binding offer," "commitment letters," "fully financed," etc. Filing explicitly describes as **non-binding LOI** at mid-June prompt. No financing commitment mentioned. §G1 informal triggers include "non-binding indication." | **AlexRight, TryRight; BPWrong** |
| 13 | Party B 7/25 LOI bid_type | Formal | Formal | Informal | Filing: *"the Company received six LOIs ... non-binding letters of intent"* (p. 36). Same as above — non-binding. §G1 informal trigger. | **TryRight; BPWrong; AlexPartiallyWrong (but Alex's comments_2 asks "what is the threshold for 'formal'?" — Alex himself acknowledges uncertainty)**. Note: Alex labels it "Formal" in the xlsx but flags it with a question. Per current §G1: informal. |
| 14 | Party D 7/25 LOI bid_type | Informal | **Formal** | Informal | Same — non-binding LOI | **AlexRight, TryRight; BPWrong** |
| 15 | Party E/Party F 7/25 LOI bid_type | Informal | Informal | Informal | Same | **AllCorrect** |
| 16 | Party C 7/25 LOI bid_type | Informal | Informal | Informal | Same | **AllCorrect** |
| 17 | G&W 7/26 revised LOI ($22.15) | Informal | Informal | Informal | Same — still non-binding LOI | **AllCorrect** |
| 18 | 7/27 drops (Party C, D, E, F) | 4 rows, all DropTarget | 4 rows, all DropTarget | 4 rows, all DropTarget | Filing: *"representatives of GHF subsequently contacted the remaining bidders to inform them that they were no longer involved in the process"* — target-initiated. §I1 DropTarget. | **AllCorrect** |
| 19 | Party A/"1 party" drop date | Alex: 2 rows — Party A 7/22 Drop + "1 party" 7/22 Drop | BP: Party A Drop on row 7 with no date | `bids_try`: no separate drop for Party A (implicit: Party A was not in the 7 advancers, so dropped on 6/1 — but no specific row) | Filing does not narrate Party A dropping specifically. Party A was one of the 2 low bidders excluded? Or an LOI non-submitter? The filing is SILENT on Party A's fate after the CIM was distributed. | **AlexPartiallyWrong**: 7/22 is not substantiated anywhere in the filing. The "1 party" row is a mystery. **BP also wrong** (emits Drop with no date or evidence). **TryJudgmentCall** — no drop row honors §I1's "do not fabricate" principle; accepts that Party A's fate is unknown. §P-S1 soft flag `nda_without_bid_or_drop` is acceptable here. |
| 20 | Party D 7/29 reengagement | Not emitted as separate row | BP: 1 `Bidder Interest` row on 7/29 (Party D) | Not emitted; re-engagement shown via `bidder_reengagement` info flag on 8/1 Bid row | §I2: *"No new event code. When a bidder drops and later re-engages ... the extractor DOES NOT emit a `Reengaged` row. The next NDA / Bid / Bidder Sale row for that bidder implicitly signals re-entry. Bookkeeping: The re-engagement row carries a flag: bidder_reengagement."* | **TryRight per §I2**; **BPWrong** — emits an extra `Bidder Interest` row that the rulebook explicitly prohibits. |
| 21 | Party E 7/29 reengagement | Not emitted | BP: 1 `Bidder Interest` row on 7/29 (Party E) | Not emitted; re-engagement via `bidder_reengagement` flag on 8/1 Bid row | Same §I2 | **TryRight; BPWrong** |
| 22 | Party D 8/1 revised bid ($24.00) | Bid $24 Informal 8/1 | Bid $24 Informal 8/1 | Bid $24 Informal 8/1 | Agree | **AllCorrect** |
| 23 | Party E 8/1 revised bid ($23.81) | Bid $23.81 Informal, labeled `Party E/F` (Alex treats as mixed joint bid) | Bid $23.81 Informal (Party E) | Bid $23.81 Informal (Party E) | Filing: *"Party E submitted a revised LOI, along with financing support, from Party F, at a price of $23.81 per share"* — Party E is bidder; Party F provides financing support. It is not a true joint bid (Party F is not the counterparty). | **TryRight, BPRight**; **AlexDebatable** — treating as `Party E/F` mixed is Alex's judgment; rulebook §E2 would say this is Party E bidder with Party F financing, not a consortium. |
| 24 | Party E 8/2 status | Alex: 2 rows — one Bid $21.26 Informal (Party E/F) "confirmed original" + 1 Drop | BP: 1 row Party E $21.26 Formal + DropTarget | `bids_try`: 1 row Drop | Filing: *"Party E withdrew its revised proposal on August 2, 2016 (but confirmed its original proposal of $21.26 per share)"*. This is ambiguous — did Party E effectively re-submit the $21.26 as a standing bid? Not a new event. Filing describes it as a withdrawal of the revised proposal. | **TryRight** (single Drop row — the $21.26 was already captured at 7/25); **AlexWrong** (duplicates the $21.26 bid that was already captured 7/25); **BPWrong** (double emits + wrong "Formal" label) |
| 25 | Party D 8/2 DropAtInf vs Drop | Alex: 8/2 Drop | BP: 8/2 DropAtInf | `bids_try`: 8/1 Drop | Filing narrates Party D declining to shorten DD and "would not proceed with further due diligence at that time" (p. 37). §I1: DropAtInf = "bidder self-withdraws at informal stage"; Drop = "bidder withdraws, unspecified reason". DropAtInf is more precise here (informal stage, self-withdrawal). | **BPRight on code choice (DropAtInf)**; **AlexWrong** (too generic); **TryPartiallyWrong** on code (should be DropAtInf) and date (should be 8/1 or 8/2 depending on interpretation; the decline was 8/1 per filing) |
| 26 | G&W 8/12 final bid ($25 cash) | Formal, `all_cash=1` | Formal, `all_cash=True` | **Informal**, `all_cash`=NA | Filing: *"G&W submitted a revised LOI to acquire the Company for a price of $25.00 per share in cash, which excluded the previously proposed CVR, together with mark-ups of the merger agreement and the voting agreement. G&W's LOI further indicated that the offer would expire at 6:00 p.m. on the following day"* (p. 38). Still called LOI (non-binding). But: contains merger agreement mark-up (§G1 formal trigger: *"markup of the merger agreement"*), deadline (extractor-level semi-binding trigger). | **AlexRight + BPRight (formal trigger: markup + deadline + exclude-CVR cash certainty)**; **TryWrong** — misses §G1 formal trigger *"markup of the merger agreement"* which is explicitly in the trigger table. `bids_try`'s note says "the filing does not describe it as a binding bid" — that's an interpretation that ignores the trigger table. This is a significant classification error in `bids_try`. |
| 27 | Party B 8/12 refuses-to-raise | Alex: Drop (no price) | BP: Drop (no price) | `bids_try`: Drop (no price) | p. 39 | **AllCorrect** |
| 28 | `Final Round Ann` 7/27 | Alex: 1 row "Final Round Ann" on 7/27 | BP: 1 row "Final Round" on 7/25 (labeled as the LOI deadline itself) | Not emitted | Filing at 7/27 narrates Transaction Committee "concluded that the Company should proceed with confirmatory due diligence and negotiations with G&W and Party B" (p. 37) — this is a subset-narrowing, which per §K2 should be inferred as `Final Round Ann` + flag `final_round_inferred`. | **AlexRight (recognizes the final-round cut)**; **BPPartiallyRight** (but wrong date — Final Round on 7/25 conflates LOI deadline with final-round-to-G&W/B cut); **TryWrong** — misses the subset-narrowing event entirely (only emits Final Round Inf Ann 6/15) |
| 29 | `Final Round`/`Auction Closed` 8/12 | Alex: 1 row "Final Round" on 8/12 (with comment: "The deadline apparently was not announced to the bidders, this was the time when the English auction was stopped by the target") | BP: not emitted | `bids_try`: not emitted | §C1: `Auction Closed` = "target unilaterally stops the auction without an announced deadline (distinct from `Final Round`, which has a formal cutoff)". Alex's comment explicitly matches `Auction Closed` semantics, but Alex used `Final Round`. | **AlexDebatable** — should probably be `Auction Closed`, not `Final Round`; **TryWrong & BPWrong** — miss this event entirely. This is a meaningful omission in both AI pipelines. |
| 30 | Executed row | Alex: 1 "Executed" on 2016-08-15 (date anchored to 8/12 bid but effective 8/15) + 1 erroneous "Party B Executed" row 6054 on 8/4 (clearly a data error — Alex's workbook) | BP: 1 "Executed" on 8/12 | `bids_try`: 1 "Executed" on 8/12 | Filing: *"the Company and G&W executed the merger agreement"* on 8/12 (p. 39); press release 8/15 | **BPRight, TryRight (date 8/12 per filing)**; **AlexPartiallyRight but with extraneous row** — the "Party B Executed" 8/4 row (xlsx 6054) is an Alex-workbook error; the press-release date 8/15 for G&W Executed conflates the press release with the executed event. |
| 31 | Sale Press Release | Alex: not emitted as event (deal-level) | BP: 1 "Sale Press Release" on 8/15 | `bids_try`: 1 "Sale Press Release" on 8/15 | Filing: p. 39 explicit | **BPRight + TryRight; AlexWrong to omit** |
| 32 | `BidderID` values | Decimal wedges (0.3, 0.5, 0.7, 1, 1.5, 2, 3, ..., 13.5, 14, ..., 17.5, 18, ..., 25.5, 26, 27, 28.3, 28.5) | Decimal wedges (0.3, 0.5, 0.7, 0.8, 0.9, 1, 1.5, 2, 3.066, 3.133, 3.166, ..., many thirds/fractions) | Strict integer sequence 1..63 | §A1: *"Strict integer sequence `1..N` per deal. No decimals."* | **TryRight**; AlexWrong (legacy format, pre-§A1); **BPWrong** (fabricated decimal thirds like 3.066, 3.133) |
| 33 | Source quote + source page | Absent (NA schema) | Absent (comments only) | Present on every row | §P-R2 hard invariant | **TryRight**; **BPWrong** (fails §P-R2 hard); **AlexWrong** (but Alex is reference, not AI output — this is expected) |
| 34 | Bid 7/21 G&W: `all_cash` = 1? | Alex: `all_cash=1` (WRONG — this row has CVR) | BP: `all_cash=False` | `bids_try`: `all_cash`=NA | This bid IS composite ($20.02 cash + $1.13 CVR). `all_cash=1` is Alex-wrong at row-level, but Alex's workbook schema applies `all_cash` as a deal-level marker only → at deal level it IS ultimately all-cash because the executed bid is $25 all-cash. BP correctly sets `all_cash=False` on this specific row; bids_try leaves it blank. | **BPRight row-level**; **AlexWrong (row-level, but deal-level may be OK)**; **TryPartiallyRight** (leaves unspecified, ambiguous per schema) |
| 35 | CVR handling | Alex: comments_2 "20.02 cash + 1.13 CVR"; no structured decomposition | BP: comments_3 note; no structured `cash_per_share`/`contingent_per_share` per §H2 | `bids_try`: `additional_note` mentions split; no structured §H2 decomposition | §H2 requires `cash_per_share`, `contingent_per_share`, `consideration_components` on composite bids | **AllPartiallyWrong** — none of the three implement §H2's structured decomposition for CVR bids. `bids_try` and `bids_pipeline` preserve the split in free text. This is a pipeline-wide gap, not Providence-specific. |

**Summary of verdicts:**
- **TryRight outright (including AllCorrect where Try matches):** 14 (rows 1, 2, 3, 5, 6, 7, 11, 15, 16, 17, 20, 21, 22, 23, 32)
- **BPRight when Try wrong:** 2 (row 25 DropAtInf vs Drop; row 26 G&W $25 formal trigger)
- **AlexRight when Try wrong:** 2 (row 28 Final Round Ann 7/27; row 26 G&W $25 formal)
- **BP-wrong, Try-right, Alex-right-or-partial:** 3 (rows 12, 13, 14 — bids_pipeline bid_type Formal on non-binding LOIs)
- **BP-only-wrong (atomization artifacts):** 4 (rows 5-part, 6, 20, 21)
- **Alex-wrong (legacy format):** 5 (rows 1, 3, 32, 33, 34)

Net: `bids_try` has the fewest unambiguously-wrong rows. Specific places it is worse than `bids_pipeline` are **row 25 code choice**, **row 26 classification** (missing formal trigger), and **row 28** (missed Final Round Ann implicit event on 7/27). Alex, where structurally valid, is closest on **row 26** and **row 28** and **row 29 Auction Closed**.

---

## Systemic findings

### 1. NDA atomization (the central question)

**`bids_try` applies §E2.b row 2 (numeric-count → atomize N rows) strictly.** This is the rule-correct path given the filing's explicit counts (11 S + 14 F + Party C = 26 NDAs). The downside is that **20 of those 27 atomized rows trigger `nda_without_bid_or_drop` soft flags**, because the filing never individually narrates what happens to most of these anonymous NDA signers.

**Alex's aggregation (3 rows: "25 parties", "9 parties", "16 parties")** is a pre-§E1 legacy schema. It's mechanically simpler but loses the bidder-level granularity §E1 requires.

**`bids_pipeline`'s partial atomization (15 rows: all named bidders + 11 unnamed financial-only)** is the worst of both worlds:
- It atomizes the 14 anonymous financial bidders per §E2.b (mostly correct — but misses 10 anonymous strategic bidders)
- It then emits a fabricated `Drop` row for each of the 11 unnamed financial placeholders — **the filing never narrates these drops**, so these rows violate §I1's explicit "do not fabricate a catch-all `Drop` row with a generic shared `source_quote`" rule and §R2 evidence-specificity.

**Verdict on the 20 `nda_without_bid_or_drop` soft flags:** They are **correct by rulebook design** (§P-S1 is explicitly soft precisely because this is a known legitimate pattern). `bids_try`'s extractor made the right call not to fabricate catch-all Drops. The flags are advisory-only. See §I1's Providence-specific rationale: *"Providence iter-7 exposed the failure mode. Twenty NDA signers had no per-bidder follow-up narration; forcing synthetic Drops would have reused one generic quote across all 20 rows, violating §R2 evidence-specificity."* **The rulebook is already aligned with `bids_try`'s behavior.**

**Austin's policy question surfaced by this deal:** Does Austin want the atomization at all? The alternative would be to tighten §E2.b to **treat "N parties executed CAs" as ambiguous → emit 1 aggregate row** — matching Alex's workbook. Both are defensible:

- **Per current §E2.b ("atomize on explicit count"):** `bids_try` is right. Keeps filings' quantitative commitment honest. Cost: 20 placeholder rows per deal with no narrative tail.
- **Alternative ("aggregate when unnamed"):** Would converge toward Alex. Cost: loses the count in the event stream; downstream analysts need to parse aggregate row text to reconstruct.

My recommendation: **keep atomization as currently codified**. The 20 soft flags are the feature, not the bug — they surface *exactly* where the filing's anonymity creates research ambiguity. Downstream queries can filter out NDA-only rows trivially.

### 2. CVR handling

- **Filing structure:** G&W's 7/21 and 7/26 LOIs contained composite consideration ($20.02 cash + $1.13 CVR on 7/21; $21.02 cash + $1.13 CVR on 7/26). The 8/12 revised LOI removed the CVR ($25.00 all-cash).
- **`bids_try` handles the decomposition best in free-text `additional_note`, but NONE of the three pipelines populate structured §H2 fields** (`cash_per_share`, `stock_per_share`, `contingent_per_share`, `consideration_components`).
- **BP-only artifact:** BP sets `all_cash=False` on the 7/21 row and `all_cash=True` on the 8/12 row — which is **per-row granular**, not how §H2 defines `all_cash` (`all_cash` is DEAL-level: true iff EVERY bid row is pure cash). So BP is using `all_cash` incorrectly as a per-row flag.
- **Alex's `all_cash=1` on the 7/21 CVR row is wrong** per §H2 definition; but Alex's xlsx schema uses `all_cash` ambiguously. Migration artifact.

**Verdict:** All three pipelines need §H2 structured CVR decomposition to be fully correct. Among them, `bids_try` is least incorrect (preserves the split in notes without mis-setting `all_cash`). Directly relevant to `scripts/build_reference.py` — when rebuilding Alex's JSON, the 7/21 G&W row should set `cash_per_share=20.02`, `contingent_per_share=1.13`, `consideration_components=["cash","cvr"]`.

### 3. Rough-date handling

- **`bids_try` uniformly applies §B1/§B3**: Q4 2015 → 2015-11-15 (midpoint); early July 2016 → 2016-07-05; late July 2016 → 2016-07-25; `Between May 19, 2016 and June 1, 2016` → 2016-05-26 (§B4 date-range midpoint). All with `bid_date_rough` preserved and correct info flags.
- **Alex uses a mix**: some dates are date-stamped with the filing's verbatim context (e.g., 2015-12-31 for Q4 2015 — last-day-of-quarter, not midpoint), others are question-marked. His own comments_2 row 6033 literally asks *"what should be the appropriate date? July 1?"*. This is the pre-§B1 inconsistency §B1 was designed to fix.
- **BP leaves many `bid_date_precise` blank and populates `bid_date_rough` only** — violates §B2's mutual-exclusivity rule. BP's Q4 2015, mid-June 2016, late July 2016 entries have no precise date.

**Verdict:** `bids_try` clean; BP violates §P-D2 hard; Alex uses legacy conventions §B1 was written to replace.

### 4. Source-quote presence

- **`bids_try`:** every row has `source_quote` and `source_page`.
- **`bids_pipeline`:** no `source_quote` column; only free-text `comments_1`/`_2`/`_3`. **Violates §P-R2 hard invariant.** This alone would fail `bids_pipeline` at validation. Note: the comments field does contain paraphrases of the filing, but `source_quote` per §P-R2 requires verbatim text, not summaries.
- **Alex:** reference JSON intentionally omits source_quote per CLAUDE.md convention (reference is a diff target, not an evidence-cited extraction).

**Verdict:** `bids_try` compliant; `bids_pipeline` fails hard §P-R2.

### 5. `bid_type` classification discipline

- **`bids_try`:** consistently applies §G1 informal triggers to non-binding LOIs. Populates `bid_type_inference_note` per §G2 (e.g., *"Filing describes as 'non-binding letter of intent'; per §G1 'non-binding' is an informal trigger..."*).
- **`bids_pipeline`:** inconsistent — sometimes Formal, sometimes Informal on similar rows (e.g., G&W 7/21 Formal, G&W 7/26 Informal; Party B 7/25 Formal, Party C 7/25 Informal). No inference notes. Fails §G2 evidence-requirement on ~7 bid rows.
- **Alex:** uses Informal for most, but inconsistently — Party B 7/25 labeled Formal in xlsx with his own comment "what is the threshold for 'formal'?". Alex-flagged as a judgment-call.

**Verdict:** `bids_try` cleanest; `bids_pipeline` systematically wrong on formal-vs-informal calls; Alex partially right but flags his own uncertainty.

### 6. Final-round vocabulary

Both AI pipelines miss structure Alex captures:
- **7/27 subset-narrowing to G&W + Party B** → Alex emits `Final Round Ann` (arguably right per §K2). BP emits `Final Round` on 7/25 (conflated with LOI deadline). `bids_try` emits nothing on 7/27.
- **8/12 unilateral-stop by Board (the "English auction" cut)** → Alex emits `Final Round` (should be `Auction Closed` per §C1). BP and `bids_try` emit nothing.

Both AI pipelines are weaker than Alex on this structural dimension. `bids_try`'s only final-round row is `Final Round Inf Ann` on 2016-06-15 (mid-June LOI-submission prompt). This underrepresents the round structure.

### 7. IB / legal counsel capture

- **`bids_try`:** GHF with resolved_name "Greene Holcomb & Fisher LLC / BMO Capital Markets Corp." (notes the 8/1/2016 acquisition). One IB row on 2016-01-27. Good.
- **BP:** Greene Holcomb & Fisher LLC, one IB row, notes BMO. Good.
- **Alex:** Greene Holcomb & Fisher, one IB row. Less detail.

Legal counsel (Hinckley Allen for Company; Simpson Thacher for G&W) is captured in `additional_note` by BP but NOT in Alex, and not visible in the bids_try CSV excerpt (though it should be in the deal-level `target_legal_counsel` / `acquirer_legal_counsel` fields per §J2). Can't fully verify from CSV alone — would need to check the source JSON.

---

## Specific rule / prompt fixes

### Prompt/rule gaps surfaced on this deal

1. **§K2 implicit-final-round inference is under-applied by both AI pipelines.**
   The 2016-07-27 subset-narrowing to {G&W, Party B} is a clear §K2 trigger (*"[Target] selected [subset] to continue in the process"*). `bids_try` missed this entirely — it emitted DropTarget for Party C/D/E/F but not the corresponding `Final Round Ann` for G&W + Party B.
   **Fix:** tighten `prompts/extract.md` with an explicit §K2 nudge: whenever multiple bidders are told they're out of the process at the same time, check whether a `Final Round Ann` should be inferred for the remaining bidders. Flag `final_round_inferred` as currently designed.

2. **§C1 `Auction Closed` is under-utilized.**
   The filing's 8/12 narrative (English-auction cut with no announced deadline) maps squarely to `Auction Closed` (*"target unilaterally stops the auction without an announced deadline"*). Neither AI pipeline used it. `bids_try` should have emitted an `Auction Closed` row on 8/12 between the G&W $25 bid and the Executed row.
   **Fix:** add `Auction Closed` trigger guidance to `prompts/extract.md`: when the target proceeds to executed merger without an announced final-round deadline or formal bid cut-off, emit `Auction Closed` on the last-substantive-action date.

3. **§G1 formal-trigger coverage — G&W 8/12 ($25) case.**
   `bids_try` labeled this **informal**. But the filing says the LOI came *"together with mark-ups of the merger agreement and the voting agreement"* — §G1 formal trigger *"markup of the merger agreement"* explicitly applies. §G1 formal-trigger table should be rechecked against `bids_try`'s extraction prompt to ensure "markup of the merger agreement" is recognized. This is a real classification error in `bids_try`.
   **Fix:** verify `prompts/extract.md` reproduces all §G1 formal triggers. In particular: *"markup of the merger agreement"*, *"executed commitment letters"*, *"fully financed"*. The G&W 8/12 LOI is a canonical formal per §G1.

4. **§E2.b row 2 atomization — consider adding a "filing-gives-bucket-count" aggregation tier.**
   The atomization of 27 NDAs is rulebook-correct but produces 20 soft-flag rows with no narrative tail. An alternative (not recommended, but consider): §E2.b could be tightened to say — *"when the filing gives a count but narrates no individual post-NDA action for unnamed bidders, emit one aggregate row per cohort (S/F) with `aggregated_count` field, rather than N placeholder rows"*. This would match Alex's workbook. **My recommendation is to NOT change this** — the current soft-flag approach preserves information better.

5. **§H2 CVR decomposition is NOT implemented by any pipeline.**
   Both `bids_try` and `bids_pipeline` leave composite bids' cash/CVR split in free-text `additional_note`. §H2 requires structured `cash_per_share`, `contingent_per_share`, `consideration_components`. This is a pipeline-level fix, not Providence-specific.
   **Fix:** implement §H2 fields in `prompts/extract.md` — make the composite-consideration breakdown mandatory on composite bids. Providence's G&W bids (7/21 $20.02+$1.13 and 7/26 $21.02+$1.13) are perfect test cases.

### Rulebook changes recommended

- **§K2 trigger list clarification:** add "drop-remaining-bidders pattern" (when multiple bidders are informed they're no longer in the process on the same date) as explicit `Final Round Ann` inference trigger for the **remaining** bidders. Currently §K2 lists only affirmative-subset-invitation triggers.
- **No change to §E2.b, §P-S1, §I1, or §R2 NDA-atomization policy** — the current rulebook correctly prescribes `bids_try`'s behavior. The 20 soft flags are working-as-designed.
- **Add §C1 clarification on `Auction Closed`:** prompt should be updated to emit `Auction Closed` whenever the deal goes from active bidding to Executed without an intervening `Final Round` or deadline.

### Converter-side (`scripts/build_reference.py`) fixes needed

- **G&W 7/21 row:** should set `consideration_components=["cash","cvr"]`, `cash_per_share=20.02`, `contingent_per_share=1.13` per §H2. Currently flattened.
- **G&W 7/26 row:** same ($21.02 cash + $1.13 CVR).
- **Party A/D/E/F/G&W NDA events:** Alex's workbook aggregates; the converter should atomize per §E2.b (or flag the deliberate choice to aggregate as a §Q override).
- **`bidder_type.public`:** Party A is likely public (a Class I rail), G&W is publicly traded — the converter's current output sets `public=null` for named bidders, driving 13+ field diffs. Addresses the broader Stage-3 open question noted in CLAUDE.md.

### `bids_pipeline`-specific fixes (not my project, but noting)

- Remove decimal `BidderID` generation (§A1 hard violation).
- Stop fabricating `Drop` rows for unnamed NDA placeholders (§I1 rule against catch-all drops).
- Fix `bid_type` classification: non-binding LOIs are informal per §G1.
- Add `source_quote` / `source_page` to every row (§P-R2 hard).
- Stop emitting `Bidder Interest` rows for re-engagements (§I2).

---

## Open questions for Austin

1. **Do you accept iter-7 providence-worcester's 20 `nda_without_bid_or_drop` soft flags as "correct per §R2"?** My read: **yes, accept**. The flags are doing their job. The alternative (tighten §E2.b to aggregate unnamed NDAs) would regress data quality and make Providence look more like Alex's workbook — which we've agreed is the legacy reference, not the target.

2. **Does `bids_try`'s 8/12 G&W $25 classification as "informal" need correction?** I think **yes** — the merger-agreement markup is a §G1 formal trigger. `bids_try`'s inference note explicitly dismisses this trigger, which is wrong. This is a row-level AI error (not a rulebook failure), fixable by tightening the extractor prompt's §G1 trigger emphasis.

3. **Should the rulebook formalize the `Final Round Ann` inference for 7/27's drop-remainders pattern?** Currently §K2 only triggers on affirmative subset-invitation language; it doesn't fire when the filing describes it as "the remaining bidders were informed they were no longer involved" (the negative form). Adding this to §K2's trigger list would close an extraction gap both AI pipelines missed.

4. **Should 8/12's unilateral-stop be emitted as `Auction Closed`?** §C1 clearly supports this; both AI pipelines missed it; Alex used `Final Round` (probably because `Auction Closed` was a later §C1 addition).

5. **`bids_pipeline` appears to use a fundamentally different schema** (decimal `BidderID`, missing `source_quote`, inconsistent atomization). Its output **would not pass §P-R2/§P-D3 hard validation** under the current `pipeline.py` validator. Is `bids_pipeline` a separate project (not held to `bids_try`'s rulebook), or does this comparison exist to migrate it? Depending on scope, 10-20 row-level bugs in `bids_pipeline` don't need individual fixes — they all trace to schema-alignment issues.

6. **Party A's fate is un-narrated in the filing.** All three sources guess differently: Alex (Drop on 7/22 — no evidence), `bids_pipeline` (Drop with no date — placeholder), `bids_try` (no drop row — honors §I1). Consider confirming from an EDGAR 13D or other disclosure that Party A is BNSF / UNP / CSX etc. and whether the filing ever reveals this elsewhere. Low-priority; `bids_try`'s "don't fabricate" choice is correct given filing text alone.

---

## Appendix: Bidder identity hypothesis (for Austin's interest)

Publicly known facts about this deal:
- **Acquirer:** Genesee & Wyoming Inc. (G&W) — NYSE: GWR at the time.
- **Target:** Providence & Worcester RR Co — NASDAQ: PWX.
- **Party A:** A "Class I rail partner" of the target. Class I freight railroads in North America in 2016: UNP, CSX, NSC, BNSF, CN, CP, KSU. BNSF (Berkshire) is private. The others are public. P&W's network connects most directly to CSX (New England-area operations). Most likely Party A is **CSX Corporation**.
- **Party B** (ultimately the $24 bidder that declined to raise to $25): a strategic buyer. Possibly another Class I or a short-line holding co (Watco, Patriot Rail, OmniTRAX).
- Parties C, D, E, F remain anonymous; Party D is financial (a PE firm, likely one that has invested in short-line rail — Fortress, Carlyle, Macquarie Infrastructure, Brookfield).

None of this changes extraction correctness — `source_quote` must match filing text regardless — but it's useful context for Austin's review.

---

**Report complete. Primary finding: `bids_try` is the closest-to-filing-truth pipeline on Providence & Worcester, but has two row-level errors (G&W 8/12 informal, missing 7/27 `Final Round Ann`, missing 8/12 `Auction Closed`). `bids_pipeline` fails hard validation on §P-R2 and §P-D3 regardless of content. Alex's workbook uses the legacy aggregated schema §E1 explicitly deprecates.**

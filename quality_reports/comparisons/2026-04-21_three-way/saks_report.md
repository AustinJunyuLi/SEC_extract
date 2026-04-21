# Three-Way Comparison: Saks Incorporated (DEFM14A, 2013)

**Deal:** Saks Incorporated → Hudson's Bay Company, merger agreement executed 2013-07-28, closed 2013-11-04.
**Archetype:** Go-shop auction; single winning strategic; two financial-sponsor groups competed; Alex flagged two workbook rows (7013, 7015) for deletion.
**Filing:** `/Users/austinli/bids_try/data/filings/saks/raw.md` (Background p.30–36).
**Alex reference JSON:** `/Users/austinli/bids_try/reference/alex/saks.json` (23 events; Alex's xlsx slice has 25 rows 6996–7020 with two deleted by §Q1).
**bids_pipeline:** 28 rows. **bids_try:** 29 rows. **Alex workbook slice:** 25 rows (raw, incl. 2 flagged-as-delete). **Alex JSON (post-§Q1):** 23 rows.

---

## TL;DR

**Winner (closer to filing):** `bids_try` (29 rows) — noticeably more faithful to the filing. It captures the §D1 first-contact/Bidder-Interest distinction, attaches §C4 `pre_nda_informal_bid` flags to the week-of-April-15 signals, classifies Company H correctly as §D1.a `unsolicited_first_contact` (a first-contact Bid with aggregate USD `bid_value`), marks Morgan Stanley as IB, and emits clean per-row `source_page` / `source_quote`. `bids_pipeline` (28 rows) is closer to the legacy Alex style but mislabels Hudson's Bay's April-1 meeting as "Bidder Interest" with `bid_value=15/pershare=15` (it conflates the April-1 meeting with the week-of-April-15 indication), mis-emits a July-29 `Sale Press Release` that conflicts with Alex's normal go-shop reporting, and includes a `Go-Shop` row under `bid_note` that is NOT in the §C1 closed vocabulary.

**Flagged-row 7013/7015 verdict — the core deletion question for this deal:**
- **Row 7013 (Company H $2.6B aggregate "bid"):** Alex's note says DELETE. `bids_try` keeps it (1 row, `bid_note="Bid"`, `bid_value=2.6B`, informal, `unsolicited_first_contact` info flag — §D1.a). `bids_pipeline` keeps it too (1 row, but as `Bidder Interest`, no price). Alex's reference JSON drops it entirely.
  - **My adjudication against the filing (p.34):** The filing says Company H "purport[ed] to propose to acquire Saks for an aggregate price of $2.6 billion in cash, with no details or further information." Goldman then failed to reach Company H; no further communication. Under current §C4/§D1.a + §C3 unified `Bid` vocabulary, Company H's letter DOES meet the §C4 definition of a pre-NDA concrete-price indication with aggregate `bid_value=2.6B`. But because Company H never signed an NDA and never followed up, §D1.a (`unsolicited_first_contact`) is the correct exemption. `bids_try` is semantically correct under the current rulebook; `bids_pipeline` is conservative (ignores the price) but loses the §D1.a signal; Alex is using his pre-§D1.a-era skip rule §M1. **Verdict: `bids_try` is aligned with the live rulebook. Alex's "delete" note predates §D1.a.** If Austin wants to apply §M1 strictly (skip entirely), the correct action is to tighten the extractor prompt, not retract §D1.a.
- **Row 7015 (Sponsor A/E "informal $14.50–$15.50" on 7/22/2013):** Alex's note says DELETE — "Not a separate bid, should be deleted" (rationale: same range as 7/11 with no update). `bids_try` DOES emit this (row 22+23, split as Sponsor A + Sponsor E, date 2013-07-25, range 14.5–15.5). `bids_pipeline` DOES emit this (row 4.9 "Sponsor A and Sponsor E", 07/23/2013, range 14.5–15.5). Alex's reference JSON drops it per §Q1.
  - **My adjudication against the filing (p.34):** The filing (week of 7/22 + evening of 7/23) plainly narrates two separate exchanges where Sponsor A/E reaffirmed a willingness above $15 but said they couldn't exceed the $14.50–$15.50 top end. This IS new information — it's the response to Goldman's "above $15" push, and it's the signal that triggered the board's $16 floor decision on 7/23. Alex's "should be deleted" call is defensible (no new price) but the events rulebook atomizes per narrated event. Under §H5 ("each bid revision is a separate event row"), a re-stated range after a target-side price push is a research-meaningful event (revealed willingness ceiling). **Verdict: both AIs are correct per the rulebook; Alex's "delete" note is a legitimate judgment call that `bids_try` and `bids_pipeline` both (correctly) don't follow.** This is a case where the current rulebook produces more faithful data than Alex's deletion.

**Go-shop handling verdict:** `bids_try` is the only extraction that cleanly captures the go-shop period using current rules — it emits Company I's NDA (row 29) dated 2013-08-11 with a §B3 `date_inferred_from_context` flag ("approximately two weeks after merger agreement"), and does NOT fabricate a separate `Go-Shop` event. `bids_pipeline` emits a row with `bid_note="Go-Shop"` — NOT in the §C1 closed vocabulary (would hard-fail §P-R3) — and also emits a bare `Sale Press Release` on 7/29. Alex's JSON captures Company I NDA (rough 2013-07-29) + Drop (precise 2013-09-06). None of the three misses the go-shop bidder; only `bids_pipeline` mis-emits a vocabulary-illegal `Go-Shop` synthetic event.

**Top 3 divergences (rank-ordered by materiality):**
1. **Hudson's Bay on April 1, 2013:** `bids_pipeline` emits this as `Bidder Interest` with `bid_value=15, bid_value_pershare=15` — but the filing says "no specific proposals were made by Hudson's Bay, and no specific transaction terms were discussed." `bids_pipeline` is conflating the April-1 meeting with the week-of-April-15 "$15" indication. `bids_try` correctly splits: April-1 meeting = `Bidder Interest`, week-of-April-15 indication = separate `Bid` row with `pre_nda_informal_bid` flag. Alex's JSON lumps both into a single row with rough="2013-04-15" and only `bid_value_lower=15`.
2. **Sponsors C and D (Company B financing, not Saks acquisition):** `bids_try` emits NDA rows for Sponsor C (4/17) and Sponsor D (4/19) and flags them `nda_context_company_b_financing` info + `nda_without_bid_or_drop` soft. `bids_pipeline` omits both (treating them as out-of-scope for the Saks auction). Alex's JSON omits both. **Verdict:** `bids_pipeline`/Alex are correct per §M3/§Scope-1 scope intent (Sponsor C & D NDAs were NOT counterparty NDAs for Saks' sale — they were financing partners for Saks' acquisition of Company B; they don't count toward the auction threshold as Saks-side counterparties). `bids_try` is overly literal. However, emitting them with an info flag and soft `nda_without_bid_or_drop` is a defensible audit choice.
3. **Sponsor A re-engagement after Sponsor G drops:** `bids_try` correctly flags this as `bidder_reengagement` (info) per §I2 on the 7/25 row. Alex's JSON does not explicitly capture Sponsor A's re-entry; `bids_pipeline` captures it textually in `comments_3` of row 4.7 but does not split it into a Sponsor A re-entry row.

---

## Filing event timeline (per `/Users/austinli/bids_try/data/filings/saks/raw.md`)

All page citations below are sec2md page numbers; the Background section begins on page 30.

| Date | Event | Evidence (p.) | Notes |
|---|---|---|---|
| Dec 2012 | Saks board strategic review; Goldman Sachs is longstanding financial advisor and participated | 30 | Alex captures this (0.3, IB, date rough=2012-12-15); bids_try doesn't emit Dec-2012 IB row; bids_pipeline omits. Not consequential for the auction. |
| Feb 2013 | **Sponsor A unsolicited call to Sadove** — "expressing interest" (no terms discussed) | 30 | §D1 `Bidder Interest` (not `Bidder Sale` — no concrete proposal yet). |
| Early March 2013 | Sadove meets Sponsor A senior reps — "no specific proposals… no specific transaction terms" | 30 | Unclear if distinct event or continuation of Feb contact. `bids_pipeline` emits two `Bidder Interest` rows (Feb + Mar); `bids_try` and Alex emit one. |
| Mar 7, 2013 | Board informed of Sponsor A contact; considers potential sale + potential acquisition of Company B | 30 | Board-level meeting; not a counterparty event. All three extractors omit (correctly). |
| **Apr 1, 2013** | **Sadove meets Richard Baker (CEO, Hudson's Bay)** "at the request of Mr. Baker" — "no specific proposals… no specific transaction terms" | 30 | §D1 `Bidder Interest`. `bids_try` row 2 correctly captures this distinct from the $15 indication two weeks later. `bids_pipeline` row 0.5 merges it with the $15 indication (date 04/01/2013 with `bid_value=15`, which misreads the filing). Alex's JSON skips this and lumps Hudson's Bay start into a single $15 indication row. |
| Apr 4, 2013 | Board reviews HB + Sponsor A expressions of interest + Company B option | 30 | Board-level; all omit. |
| Apr 11, 2013 | Joint Finance + Executive committee meeting; Goldman Sachs + Wachtell Lipton attend | 31 | First narrated Goldman Sachs advisory action date. `bids_try` anchors `IB` to 2013-04-11 here (per §J1, soft `date_inferred_from_context`). |
| Post-Apr 11 | Discussions with **Sponsor C and Sponsor D** for equity financing of Saks→Company B acquisition | 31 | **Not Saks-side bidders.** `bids_try` emits their NDAs; `bids_pipeline` and Alex omit. |
| **Week of Apr 15, 2013** | **Hudson's Bay and Sponsor A each indicate: offer "at least $15 per share, in cash"** to Goldman Sachs — Sponsor E present in Sponsor A meeting | 31 | §C4 pre-NDA informal bids (HBC NDA is 4/30; Sponsor A NDA is 4/26). Both `bids_try` (rows 5+6) and `bids_pipeline` (rows 0.7+0.8) capture. Alex has two rows, `bid_value_lower=15`, informal, rough=2013-04-15. |
| **Apr 17, 2013** | **Sponsor C signs CA** (Company B financing context, not Saks sale) | 31 | Only `bids_try` emits. |
| Apr 19, 2013 | **Sponsor D signs CA** (same context) | 31 | Only `bids_try` emits. |
| **Apr 26, 2013** | **Sponsor A and Sponsor E each sign CAs** (joint acquisition of Saks) | 31 | All three emit 2 rows. Alex's JSON also has a Sponsor A `Drop` on 4/26 (reflecting Alex's "BidderID=4 drop" row 7001, which looks like a data-entry oddity — there is no Sponsor A drop on 4/26 in the filing). |
| **Apr 30, 2013** | **Hudson's Bay signs CA** with Saks | 31 | All three emit. |
| May 15, 2013 | Committee grants HB permission to contact equity-financing sources | 32 | Not a counterparty event. All omit. |
| May 17/20, 2013 | Saks's non-binding proposal to acquire Company B (not Saks-as-target event) | 32 | All omit (correctly). |
| Late May 2013 | Media reports of Saks sale process | 32 | `bids_try` doesn't emit; `bids_pipeline` doesn't either. Alex's row 9 has a `comments` field quoting this. |
| **Jun 1, 2013** | Finance committee reviews HB / Sponsor A / Company B status | 32 | Internal; all omit. |
| **Week of Jun 3, 2013** | **Hudson's Bay: $15–$15.25/share range (informal indicative); Sponsor A + Sponsor E: $15–$16/share range (informal joint indicative)** | 32 | Post-NDA informal bids. All three extractors emit. `bids_try` splits Sponsor A/E into two rows (rows 13+14); Alex's reference JSON merges into one `Sponsor A/E` row (row 10); `bids_pipeline` uses "Sponsor A and Sponsor E" as the `BidderName` on a single row. |
| **Jun 5, 2013** | **Board authorizes the sale process** | 32 | §D1 `Target Sale`. Only `bids_pipeline` (row 1, 06/05/2013) and `bids_try` (row 11, 06-05-2013) emit. Alex's JSON does NOT emit a `Target Sale` row — a meaningful gap on the Alex side. |
| **Week of Jun 10, 2013** | **Company F** expresses interest in joining Sponsor A + E; engages in DD; ultimately does not participate in final offer | 32 | `bids_pipeline` emits row 1.25 `Bidder Interest` for Company F. `bids_try` omits Company F entirely (major miss). Alex omits as well. **Verdict: `bids_pipeline` right here.** Company F should have a `Bidder Interest` row at minimum. |
| **Jul 2, 2013** | **Goldman distributes draft merger agreement + process details to HB, Sponsor A, Sponsor E; deadline July 11** | 33 | §K2 implicit final round: `Final Round Ann`. All three emit (with `final_round_inferred` flag in `bids_try`). |
| **Jul 8, 2013** | **Sponsor G signs CA** (joining Sponsor E after Sponsor A steps back as primary) | 33 | All three emit. |
| **Jul 11, 2013** | **Hudson's Bay formal bid $15.25 + revised draft merger agreement + committed debt+equity financing** (formal per §G1 triggers) | 33 | All three emit. |
| **Jul 11, 2013** | **Sponsor E + Sponsor G joint informal bid $14.50–$15.50** (no draft merger agreement, no financing docs) | 33 | All three emit. `bids_pipeline` row 4 uses `Sponsor E and Sponsor G`; `bids_try` row 17 uses Sponsor E with `joint_nda_aggregated` info; Alex row 17 uses `Sponsor A/E` as the bidder label (an apparent Alex-side labeling error — the July 11 joint bid was E+G, not A+E; see below). |
| ~Jul 11–15 | **Sponsor G withdraws from the process; Sponsor E rejoined by Sponsor A as primary** | 33 | `bids_pipeline` row 4.7 `Drop` with rough 07/15/2013; `bids_try` row 19 `Drop` 2013-07-15 with `drop_agency_ambiguous`; Alex row 13 `Drop` on Sponsor G (no date). |
| Week of Jul 15 | Goldman tells Sponsor A+E: lower half of range won't be acceptable | 33 | Internal negotiation; only `bids_try` arguably captures this via the subsequent week-of-7/22 row. |
| Jul 17, 2013 | Board authorizes Goldman to inform both sides their initial prices are insufficient | 33 | Internal; all omit. |
| **Jul 21, 2013** | **Company H letter: $2.6 billion aggregate, no details** — unsolicited, no NDA, no follow-up reachable | 34 | §D1.a `unsolicited_first_contact`. `bids_try` emits as `Bid` (informal, `bid_value=2,600,000,000 USD`, `unsolicited_first_contact` info). `bids_pipeline` emits row 4.8 as `Bidder Interest` with no value. Alex JSON drops per §Q1. |
| **Week of Jul 22 / Evening Jul 23** | **Sponsor A + Sponsor E indicate willingness above $15 but say unlikely to exceed $15.50 top end** | 34 | `bids_try` rows 22+23 (split Sponsor A + Sponsor E, 2013-07-25). `bids_pipeline` row 4.9 (combined, 07/23/2013). Alex JSON drops per §Q1. |
| **Jul 23, 2013** | **Board authorizes Goldman to tell HB: won't agree below $16/share** | 34 | Internal; `bids_try` has quote on row 24. |
| **Jul 24, 2013** | **Hudson's Bay: prepared to offer $16/share subject to definitive agreement + agreeable on all merger-agreement issues** | 34 | All three emit formal bid $16 at 2013-07-24. |
| **Jul 25, 2013** | Sponsor A + Sponsor E effectively dropped (below board's $16 floor); board authorizes proceeding exclusively with HB; Morgan Stanley first narrated as advisor | 35 | `bids_try` rows 24+25 emit `DropBelowM` for Sponsor A + Sponsor E separately; row 26 emits Morgan Stanley as `IB`. `bids_pipeline` and Alex do NOT emit explicit drops for A/E here (Alex row 21 has `DropTarget` on `Spnosor A/E` [sic, typo]). |
| **Jul 28, 2013** | **Merger agreement executed** (HBC + Merger Sub + Saks) | 35 | All three emit. |
| Jul 29, 2013 | Joint press release announcing the merger | 35 | `bids_try` emits `Sale Press Release`; `bids_pipeline` emits row 6.5 `Sale Press Release`; Alex JSON does not emit. |
| **Jul 28–Sep 6, 2013 (GO-SHOP)** | **40-day go-shop: Goldman contacts 58 third parties; 6 express interest; only Company I signs a CA; Company I conducts DD; no go-shop proposals submitted** | 35–36 | `bids_try` row 29 emits Company I NDA (date 2013-08-11, rough "approximately two weeks after merger agreement executed July 28, 2013"); Alex's JSON has Company I NDA (rough 2013-07-29) + Drop (precise 2013-09-06). `bids_pipeline` emits Company I NDA row 7 (rough 08/11/2013) + Drop row 7.25 + a synthesized "Go-Shop" row 7.5 with **invalid** `bid_note="Go-Shop"`. |

---

## Source-by-source row counts and structure

### Alex's workbook (raw xlsx slice, rows 6996–7020 — 25 rows)

- 25 events INCLUDING the two flagged-as-delete rows (7013 Company H, 7015 Sponsor A/E rescoped).
- `scripts/build_reference.py` §Q1 drops rows 7013 + 7015 → Alex reference JSON has **23 events**.
- Unique counterparty bidders (excluding IB Goldman): Sponsor A (4 rows: `Bidder Interest` 6997, informal bid 6999, `Drop` 7000, NDA 7001), Hudson's Bay (6 rows), Sponsor E (1 NDA), Sponsor G (1 NDA + 1 drop), Sponsor A/E (joint, 2 bid rows 7005 + 7010), Company H (2 rows 7013+7014, both dropped by §Q1), Sponsor A/E retyped "Spnosor A/E" with typo (7017 DropTarget — retained), Company I (NDA 7019 + Drop 7020).
- Alex's slice uses decimal `BidderID`s (0.3, 0.5, 1, 1.5, 4.7, 6.5, 13.5, 19.5) — the decimal-wedge convention. `scripts/build_reference.py` §A1 renumbers to strict 1..N.
- **No Target Sale event.** Alex jumps straight from NDAs to bids. This is a known gap in Alex's data.
- **No Apr 1 HB meeting event.** Alex lumps HB start into the week-of-Apr-15 $15-indication row.

### `bids_pipeline` (28 rows)

- Pre-merger events (1 `Bidder Interest` Feb Sponsor A + 1 `Bidder Interest` early-March Sponsor A, that the filing phrases as "no specific proposals" but bids_pipeline duplicates → likely overcounts start-of-process).
- 1 `Bidder Interest` Apr 1 Hudson's Bay **with `bid_value=15`** — this is a filing misread (Apr-1 meeting had NO price; the $15 indication came in the week of Apr 15). Major bug.
- 2 informal pre-NDA bids Apr 15 (HB and Sponsor A, both `$15` point value, `bid_lower=15`, `bid_upper=15` — wrong; filing says "at least $15," which is a lower bound only).
- 2 NDAs Apr 26 (Sponsor A and E), 1 NDA Apr 30 HB.
- 1 `Drop` Sponsor A (no date, `BidderID=0.855`) — the filing does NOT narrate a Sponsor A drop at 4/26; this appears to mirror Alex's confusing `Drop` row 7000. Adopting Alex's error.
- 1 `Drop` Sponsor E (no date, `BidderID=0.865`) — same issue.
- 2 informal range bids Jun 3 (HB $15–$15.25; Sponsor A+E $15–$16).
- 1 `Target Sale` Jun 5 — present.
- 1 `Bidder Interest` Company F, week of Jun 10 — present (only bids_pipeline catches this).
- 1 `Final Round Ann` Jul 2.
- 1 NDA Sponsor G Jul 8.
- 2 formal/informal bids Jul 11 (HB $15.25 formal; Sponsor E+G $14.50–$15.50 informal).
- 1 `Final Round` Jul 11.
- 1 `Drop` Sponsor G rough 07/15.
- 1 `Bidder Interest` Company H Jul 21 (NO value) — silently strips the $2.6B aggregate.
- 1 informal Sponsor A+E re-restate $14.50–$15.50 Jul 23.
- 1 formal HB $16 Jul 24.
- 1 `Executed` HB Jul 28.
- 1 `Sale Press Release` Jul 29.
- 1 NDA Company I (rough 08/11).
- 1 `Drop` Company I (no date).
- 1 **`Go-Shop`** synthesized row Sep 6 — **NOT in §C1 closed vocabulary; would hard-fail §P-R3 `invalid_event_type`.**
- **No `Bidder Interest`/`Activist Sale` for Sponsor A at any later point, no re-entry row for Sponsor A.** Reasonable.
- No `IB` row for Goldman (Dec 2012 event dropped) — inconsistency with Alex's reference.
- No `IB` row for Morgan Stanley at all.
- No Sponsor C / Sponsor D NDAs (correct per §M3 scope, but no audit trail).

### `bids_try` (29 rows)

- 1 `Bidder Interest` Sponsor A (Feb 2013).
- 1 `Bidder Interest` Hudson's Bay (Apr 1 2013) — filing-faithful, no price.
- 1 `IB` Goldman Sachs anchored to Apr 11, 2013 (soft `date_inferred_from_context`).
- 1 NDA Sponsor C (Apr 17) + 1 NDA Sponsor D (Apr 19) — both flagged `nda_context_company_b_financing` info + `nda_without_bid_or_drop` soft. Debatable inclusion (see Divergence 2 below).
- 2 informal pre-NDA bids (HB + Sponsor A), week of Apr 15, `bid_value_lower=15` ONLY, `§C4 pre_nda_informal_bid` flag. Filing-faithful on the "at least $15" phrasing.
- 2 NDAs Apr 26 (Sponsor A + Sponsor E); 1 NDA Apr 30 HB.
- 1 `Target Sale` Jun 5 — present.
- 3 range informal bids week of Jun 3 (HB $15–$15.25; Sponsor A $15–$16; Sponsor E $15–$16) — atomized per §E1, each with its own source_quote/page.
- 1 `Final Round Ann` Jul 2.
- 1 NDA Sponsor G Jul 8.
- 2 bids Jul 11 (HB $15.25 formal; Sponsor E joint-with-G $14.50–$15.50 informal with `joint_nda_aggregated`).
- 1 `Drop` Sponsor G rough 2013-07-15 (`drop_agency_ambiguous` soft).
- 1 `Bid` Company H Jul 21 **aggregate $2.6B USD**, informal, `unsolicited_first_contact` info flag (§D1.a).
- 2 informal rows week of Jul 22 (Sponsor A + Sponsor E $14.50–$15.50) — split per §E1. `bids_try` correctly flags `bidder_reengagement` on Sponsor A (§I2).
- 1 formal HB $16 Jul 24.
- 2 `DropBelowM` rows Jul 25 (Sponsor A + Sponsor E).
- 1 `IB` Morgan Stanley Jul 26 (soft `date_inferred_from_context`).
- 1 `Executed` HB Jul 28.
- 1 `Sale Press Release` Jul 29.
- 1 NDA Company I (Aug 11, rough "approximately two weeks after…", soft `date_inferred_from_context` + `nda_without_bid_or_drop`).
- Only 29 rows but zero §C1 vocabulary violations.

**Per-bidder breakdown (bids_try):**

| Bidder | Rows (bids_try) |
|---|---|
| Goldman Sachs (IB) | 1 |
| Sponsor A | 6 (Feb Bidder Interest + Apr 18 Bid + Apr 26 NDA + Jun 6 Bid + Jul 25 Bid re-engage + Jul 25 DropBelowM) |
| Hudson's Bay | 7 (Apr 1 Bidder Interest + Apr 18 Bid + Apr 30 NDA + Jun 6 Bid + Jul 11 Bid formal + Jul 24 Bid formal + Jul 28 Executed + Jul 29 Sale Press Release) — that's 8 rows actually |
| Sponsor C | 1 NDA |
| Sponsor D | 1 NDA |
| Sponsor E | 4 (Apr 26 NDA + Jun 6 Bid + Jul 11 Bid + Jul 25 Bid + Jul 25 DropBelowM) |
| Sponsor G | 2 (Jul 8 NDA + Jul 15 Drop) |
| Company H | 1 `Bid` (unsolicited, §D1.a) |
| Morgan Stanley (IB) | 1 |
| Company I | 1 NDA |

Go-shop bidders: only **Company I** (the sole go-shop bidder who signed a CA). Identified by all three extractions.

---

## Divergence table

Each row: filing-anchored event, each source's treatment, verdict.

| # | Filing event (p.) | Alex JSON | bids_pipeline | bids_try | Verdict |
|---|---|---|---|---|---|
| D01 | Goldman Sachs as IB (Dec 2012 review + "longstanding financial advisor") (p.30) | 1 `IB` row, rough 2012-12-15 | — (omitted) | 1 `IB` row anchored Apr 11, 2013 with `date_inferred_from_context` soft | **Alex right** (explicit Dec-2012 narration qualifies as earliest narrated date under §J1). `bids_try` is defensible but uses a later anchor. `bids_pipeline` drops the IB entirely. Note: Alex's date is the December review — arguably §J1 wants the earliest narrated action, not the first strategic-review mention; `bids_try`'s Apr 11 anchor is when Goldman is first narrated as part of the Saks sale process specifically. Both Alex and `bids_try` have defensible positions. **BothAIRight (judgment call under §J1)**. |
| D02 | Sponsor A first contact Feb 2013 + early-March meeting (p.30) | 1 `Bidder Interest` row, rough Feb 2013 | 2 `Bidder Interest` rows (Feb + early March) | 1 `Bidder Interest` row 2013-02-15 | **BothAIRight / `bids_pipeline` over-atomizes.** Filing narrates Feb call + early-March meeting as same "Sponsor A expressing interest" thread with "no specific proposals." One row is the faithful read. `bids_pipeline` double-emits. |
| D03 | **Apr 1, 2013 Sadove–Baker meeting (HB)** (p.30) | — | Row 0.5 `Bidder Interest` 04/01/2013 **with bid_value=15** (!) | Row 2 `Bidder Interest` 2013-04-01 (NO value) | **TryRight.** Filing: "No specific proposals were made by Hudson's Bay, and no specific transaction terms were discussed." `bids_pipeline` is mis-reading the filing: the $15 indication is a week-of-April-15 event, not April 1. |
| D04 | **Week of Apr 15, 2013 — HB and Sponsor A "at least $15"** (p.31) | Combined Sponsor A row 4 + HB row 3, `bid_value_lower=15`, rough 2013-04-15 | Rows 0.7 + 0.8, HBC and Sponsor A, `bid_value=15, pershare=15, lower=15, upper=15` (point value) | Rows 5 + 6, HBC and Sponsor A, `bid_value_lower=15, upper=null`, §C4 `pre_nda_informal_bid` flag | **TryRight.** Filing phrase: "considering making an offer to acquire Saks for at least $15 per share." "At least $X" is a single lower bound per §H1 → `bid_value_lower=15, bid_value_upper=null, bid_value_pershare=null`. Both Alex (uses lower=15 only) and `bids_try` get the bound structure right. `bids_pipeline` encodes it as a point value = $15, which contradicts "at least." |
| D05 | **Sponsor C CA Apr 17, 2013** and **Sponsor D CA Apr 19, 2013** (p.31) | — (not in scope; financing partners for Saks→Company B) | — | NDA rows 4 + 7 with `nda_context_company_b_financing` info + `nda_without_bid_or_drop` soft | **AlexRight + BPRight.** The filing narrates Sponsor C and Sponsor D as equity-financing sources for Saks's *acquisition* of Company B, not as counterparties bidding for Saks itself. They do NOT satisfy §Scope-1's "non-advisor bidder NDAs in the current sale process." `bids_try`'s choice to emit with a scope-caveat flag is defensible for audit purposes but over-collects; the clean treatment is to omit (with a deal-level `partial_bid_skipped`-style flag, or per §M3 advisor-adjacent skip rule). **JudgmentCall** — reasonable people can differ. `bids_try` is more transparent; Alex + BP are cleaner. |
| D06 | Sponsor A apparent 4/26 `Drop` (Alex row 7000 / bids_pipeline row 0.855 / bids_pipeline row 0.865 Sponsor E) | `Drop` rows on 4/26 for Sponsor A | `Drop` rows (no date) for Sponsor A + Sponsor E | — (no 4/26 drops) | **TryRight.** The filing narrates NO Sponsor A or Sponsor E drop on 4/26 (that's when they signed the joint CA!). Alex's row 7000 + `bids_pipeline`'s rows 0.855/0.865 are spurious — they do not correspond to any filing event. `bids_try` correctly omits. |
| D07 | Apr 26, 2013 — Sponsor A + Sponsor E NDAs (joint acquisition) | 2 NDA rows | 2 NDA rows | 2 NDA rows | All three agree. |
| D08 | Apr 30, 2013 — HB NDA | 1 NDA row | 1 NDA row | 1 NDA row | All three agree. |
| D09 | **Jun 5, 2013 — Target Sale** (p.32) | — (not emitted; Alex has no Target Sale row) | Row 1 `Target Sale` 06/05/2013 | Row 11 `Target Sale` 2013-06-05 | **BothAIRight.** Filing explicitly says board "authorized (1) the implementation of a process to determine whether a transaction… could be reached." This is the canonical §D1 `Target Sale` trigger. Alex's JSON lacks this row — it's a gap in the reference. |
| D10 | **Week of Jun 3, 2013 — HB $15–$15.25 range; Sponsor A+E $15–$16 range** (p.32) | 2 rows (HB range + Sponsor A/E joint range) | 2 rows (HB range + `Sponsor A and Sponsor E` combined range) | 3 rows (HB + Sponsor A + Sponsor E atomized) | **TryRight per §E1** (atomize by constituent). Alex and BP combine Sponsor A + E into one row, using `Sponsor A and Sponsor E` as bidder label — but §E1 says atomize unless narrated as a single consortium event. The June 3 exchange was distinct per-party conversations ("Goldman spoke with representatives of each of Hudson's Bay, Sponsor A and Sponsor E"). Atomized is more correct. |
| D11 | **Week of Jun 10, 2013 — Company F expresses interest** (p.32) | — | Row 1.25 `Bidder Interest` Company F, rough 06/10/2013 | — (Company F entirely missing) | **BPRight.** Filing: "Saks was informed that Company F had indicated interest in participating with Sponsor A and Sponsor E in a potential acquisition of Saks. Company F engaged in due diligence of Saks." This is a full `Bidder Interest` + DD event for a named party. `bids_try` misses it — meaningful gap. Alex also misses it. |
| D12 | Jul 2, 2013 — Final Round Ann (p.33) | 1 row, precise 2013-07-02 | 1 row, 07/02/2013 | 1 row with `final_round_inferred` flag | All three agree on event + date. `bids_try` adds the inference flag per §K2. |
| D13 | Jul 8, 2013 — Sponsor G NDA (p.33) | 1 NDA row | 1 NDA row | 1 NDA row | All three agree. |
| D14 | **Jul 11, 2013 — HB formal bid $15.25 + committed financing** (p.33) | 1 `Bid` row, formal | Row 3 formal | Row 18 formal | All three agree. |
| D15 | **Jul 11, 2013 — Sponsor E+G joint informal $14.50–$15.50** (p.33) | Row 10 `Sponsor A/E` informal range $15–$16 … wait, Alex uses `Sponsor A/E` as the bidder label here. But the filing says the July 11 joint bid was Sponsor E + Sponsor G (not A+E). **Alex's label is wrong.** | Row 4 `Sponsor E and Sponsor G` informal $14.50–$15.50 | Row 17 Sponsor E informal $14.50–$15.50 with `joint_nda_aggregated` linking Sponsor G co-bidder | **BPRight / TryRight; AlexWrong.** Alex row 6079 (→ reference row 10 `Sponsor A/E` range $15–$16 on rough 2013-06-03) and row 7010 (→ reference row 17 `Sponsor A/E` range $14.50–$15.50 on 2013-07-11) both label the bidder as A/E; by July 11 the joint bidder was E+G. Either Alex mis-labeled or is using a legacy "A/E" slot for the sponsor-group entity. This is a real Alex-side error. |
| D16 | ~Jul 15, 2013 — Sponsor G drops (p.33) | Row 13 `Drop` Sponsor G (no date) | Row 4.7 `Drop` rough 07/15 | Row 19 `Drop` 2013-07-15 with `drop_agency_ambiguous` soft | **BothAIRight + Alex underspecified.** `bids_try`'s ambiguity flag is correct — filing says "Saks was subsequently informed that Sponsor G was no longer participating," which doesn't clearly say voluntary vs target-cut. |
| D17 | **Jul 21, 2013 — Company H letter $2.6B aggregate, no details, no NDA, no follow-up** (p.34) | — (§Q1 deleted) | Row 4.8 `Bidder Interest` Company H (no value, no NDA) | Row 20 **`Bid` Company H aggregate $2.6B USD informal** with `unsolicited_first_contact` info (§D1.a) | **TryRight under current rulebook.** §D1.a is the 2026-04-19-resolved rule for unsolicited first contacts with a concrete price indication and no NDA. Under §D1.a, `bids_try`'s treatment is canonical. Alex's "delete" note predates §D1.a; it's a pre-§D1.a skip (§M1) that no longer fits the rulebook. `bids_pipeline` is conservative: emits the event as `Bidder Interest` but drops the price, losing the "$2.6B aggregate" signal. **AlexFlagged row 7013 is the most interesting verdict: the current rulebook says emit, not delete.** Row is retained in all three (Alex `xlsx` has it with "Should be deleted" note; Alex JSON drops per §Q1). |
| D18 | **Week of Jul 22 / evening Jul 23 — Sponsor A+E re-state $14.50–$15.50 ceiling** (p.34) | — (§Q1 deleted row 7015) | Row 4.9 `Sponsor A and Sponsor E` informal $14.50–$15.50, 07/23/2013 | Rows 22 + 23 Sponsor A + Sponsor E atomized, 2013-07-25 (§B3 anchored from "week of") with `bidder_reengagement` info on Sponsor A | **BothAIRight under current rulebook.** §H5 treats each narrated restatement/reaffirmation as a separate row. `bids_try` additionally flags Sponsor A's re-entry per §I2. Alex's "delete" note for row 7015 is a judgment call — reasonable-but-not-rulebook-compliant. **AlexFlagged row 7015: current rulebook says emit, not delete.** |
| D19 | **Jul 24, 2013 — HB formal $16 subject to definitive agreement** (p.34) | 1 row, formal | 1 row, formal | 1 row, formal | All three agree. |
| D20 | **Jul 25, 2013 — Board sets $16 floor; Sponsor A+E effectively dropped** (p.34–35) | Row 21 `DropTarget` on `Spnosor A/E` [typo] with precise 2013-07-28 | — (no explicit drop row) | Rows 24 + 25 `DropBelowM` on Sponsor A + Sponsor E, precise 2013-07-25 | **TryRight.** §I1 says `DropBelowM` = "Target rejects because bid is below minimum." The filing has the board set $16 as the floor and authorize exclusive negotiations with HB — the implicit rejection of A+E's $15.50 ceiling. `DropBelowM` is the canonical code. Alex's `DropTarget` on 7/28 is also defensible but too late (the rejection was 7/25). `bids_pipeline` just misses it entirely. |
| D21 | Jul 26, 2013 — Morgan Stanley narrated as Saks advisor (p.35) | — | — | Row 26 `IB` Morgan Stanley with `date_inferred_from_context` soft | **TryRight.** §J1 mandates emitting `IB` rows for named advisors. Morgan Stanley is explicitly "a long-time advisor to Saks" attending the 7/26 board meeting. The other two sources drop it. |
| D22 | Jul 28, 2013 — Executed (p.35) | 1 row | 1 row | 1 row | All three agree. |
| D23 | Jul 29, 2013 — Joint press release (p.35) | — | 1 `Sale Press Release` row | 1 `Sale Press Release` row | **BothAIRight.** §C1 `Sale Press Release` is in vocabulary; the joint press release is canonical for this event. Alex doesn't emit. |
| D24 | Jul 28–Sep 6, 2013 — Go-shop period | — (not emitted; only Company I captured implicitly) | Row 7.5 **`Go-Shop`** rough 09/06/2013 — `bid_note` NOT in §C1 vocabulary | — (no separate go-shop row; covered by Company I NDA row) | **TryRight.** `bids_pipeline` invents a `Go-Shop` event type that would hard-fail §P-R3 `invalid_event_type`. The go-shop is a deal-level attribute (`go_shop_days=40` at deal level). Company I's NDA row carries the go-shop signal. |
| D25 | Aug 11, 2013 (approx.) — Company I signs CA (during go-shop) | NDA rough 2013-07-29 [Alex uses day of go-shop start] | Row 7 NDA rough 08/11/2013 | Row 28 NDA precise 2013-08-11 (§B3 anchored "approximately two weeks after merger agreement") with `date_inferred_from_context` soft + `nda_without_bid_or_drop` soft | **TryRight.** Filing: "Company I had not signed a confidentiality agreement until approximately two weeks after the merger agreement was executed" → Aug 11 is the correct §B3 anchor date. Alex's 7/29 is wrong (it's the announcement date, not the CA date); `bids_pipeline`'s 08/11 is also correct. |
| D26 | Sep 6, 2013 — End of go-shop (Company I Drop) | Row 23 `Drop` Company I precise 2013-09-06 | Row 7.25 `Drop` Company I (no date) | — (no explicit Drop row) | **AlexRight (and BPRight with date caveat).** Per §I1, when a go-shop bidder signs a CA and then the go-shop ends with no proposal, the appropriate code is `Drop` (or arguably `DropTarget`). Alex's 9/6 dated drop is canonical. `bids_pipeline` is less specific (missing date). `bids_try` omits the Drop entirely and lets the `nda_without_bid_or_drop` soft flag fill the role — defensible per §I1 ("NDA-only rows — bidders who signed but have no later narrated activity"), but in this case the go-shop-end IS a narrated event on page 35 ("The go shop period ended on September 6, 2013, and no party has been designated by Saks as an excluded party"), so a `Drop` row on Company I is justified. **AlexRight.** |

---

## Systemic findings

### Go-shop handling

- **Go-shop is a deal-level attribute.** `go_shop_days=40` + `termination_fee=$73.5M` + `reverse_termination_fee=$173.8M` are all deal-level fields per §O1. `bids_try`'s `output/extractions/saks.json` correctly captures all three (confirmed from reading deal block). `bids_pipeline` and Alex do not explicitly capture these deal-level fields in their CSV slices (but might in JSON).
- **Go-shop events at row level:** Only **one** go-shop bidder signed a CA (Company I). The filing narrates (p.35–36): "The go shop period ended on September 6, 2013, and no party has been designated by Saks as an excluded party. During the go shop process, Goldman Sachs, on behalf of Saks, contacted 58 potentially interested third parties, including private equity firms, companies involved in the retail industry and other potential acquirors. Of those contacted, only six parties expressed interest, and only one of the six (which we refer to as Company I) executed a confidentiality agreement." Per the rulebook, the 58 contacted parties don't become `Bidder Interest` rows (they're prospective contacts, not engaged bidders); only Company I gets atomic rows. The go-shop "event" is the deal-level `go_shop_days: 40`, not a separate row event.
- **`bids_pipeline`'s `Go-Shop` row** (row 7.5 Sep 6, 2013) is a vocabulary violation under §C1 / §P-R3. It would hard-fail validation in this repo.
- **Alex's Company I handling** is reasonable: NDA (rough 2013-07-29) + Drop (precise 2013-09-06). The NDA date is wrong (should be Aug 11), but the Drop capture is correct.
- **`bids_try`'s Company I handling** is filing-accurate on the NDA date but misses the Drop. The soft `nda_without_bid_or_drop` flag serves as a proxy, but per §I1's "go-shop ended, no proposal submitted" narration, a `Drop` row is defensible. Recommend `bids_try` add it.

### Deletion of Alex-flagged rows 7013 + 7015

- **Row 7013 (Company H, $2.6B aggregate):** Alex: "Should be deleted: unsolicited letter, no NDA, no further contact, no price per share."
  - **Current rulebook verdict:** §D1.a `unsolicited_first_contact` is the 2026-04-19 rule exactly for this pattern. `bids_try` correctly emits the Bid with the flag. Alex's deletion was the right call under his pre-§D1.a rulebook; under the current rulebook, emit + flag is the right call.
  - **`bids_pipeline`** keeps the event but drops the price (emits as `Bidder Interest` with no value) — lossy.
- **Row 7015 (Sponsor A/E re-statement week of 7/22):** Alex: "Not a separate bid, should be deleted."
  - **Current rulebook verdict:** §H5 says every narrated restatement is a separate row. The week-of-7/22 restatement is research-meaningful — it's Sponsor A+E's response to Goldman's "above $15" push, and it triggered the board's $16 floor decision. Alex's deletion was a judgment call; current rulebook says emit.
  - Both AIs correctly emit; Alex's reference JSON (post-§Q1) drops it.

### Dates

- **Sponsor A "early March 2013" meeting:** Filing says "In early March 2013, Mr. Sadove met with senior representatives of Sponsor A." Per §B1, "early March 2013" → 2013-03-05. `bids_pipeline` encodes as 03/01/2013 (wrong by Alex's §B1). `bids_try` merges into the Feb row.
- **"Week of April 15, 2013":** Per §B1, week-of anchor to Monday. 2013-04-15 was a Monday, so 2013-04-15 is the canonical precise date under the rule. `bids_try` uses 2013-04-18 (mid-week midpoint) — minor deviation from §B1 table. Alex uses 2013-04-15.
- **"Week of June 3, 2013":** Similar issue. 2013-06-03 was Monday. `bids_try` uses 2013-06-06 (mid-week). Alex uses 2013-06-03.
- **"Approximately two weeks after merger agreement executed July 28, 2013":** Per §B3 anchor + offset, anchor=2013-07-28 + 14 days → 2013-08-11. `bids_try` gets this correct. `bids_pipeline` also 08/11. Alex uses 2013-07-29 — wrong (that's just the announcement date).
- **Sponsor G drop "in early July" context:** Filing has no explicit date for Sponsor G's withdrawal; it's derivable only from the Jul 11 bid narrative → "Saks was subsequently informed" → shortly after 7/11. `bids_try`'s 2013-07-15 (anchor+7 per §B1 "shortly after") is canonical. `bids_pipeline`'s 07/15/2013 agrees. Alex leaves the date null.

### Source-quote presence

- **`bids_try` is the only source with per-row `source_page` + `source_quote` columns**. Every row cites a specific page number and a verbatim snippet — this is the §R3 evidence contract.
- **`bids_pipeline`** has no source_page / source_quote columns. Row-level audit is impossible without that.
- **Alex's workbook** also has no source citations (by design — the workbook is decades old; the comments fields substitute).
- This is the biggest structural advantage of `bids_try` for Austin's per-deal manual-verification workflow.

### Extra row types only `bids_try` emits

- `IB` row for Morgan Stanley (§J1 advisor emission).
- `DropBelowM` rows for Sponsor A + Sponsor E on 2013-07-25 (when board set $16 floor).
- `Bidder Interest` for HB Apr 1 distinct from the $15 indication.
- §C4 `pre_nda_informal_bid` flags on the week-of-Apr-15 rows.
- §D1.a `unsolicited_first_contact` flag on Company H Bid row.
- §I2 `bidder_reengagement` flag on Sponsor A 2013-07-25.
- Soft `drop_agency_ambiguous` on Sponsor G drop.

---

## Specific rule / prompt fixes

1. **Company F (p.32, week of Jun 10, 2013).** `bids_try` misses this event. Prompt/extractor should not skip named parties that "indicated interest" + "engaged in due diligence" even when they don't appear on the final bid list. Add to the extractor prompt: "If the filing names a party (`Company F`, `Sponsor X`, etc.) that *engaged in due diligence* even once, emit a `Bidder Interest` row — absence from the final bid list is NOT a skip trigger."
2. **Sponsor C and Sponsor D (p.31).** `bids_try` emits these as NDAs (with context flags). Per §M3 / §Scope-1, the filing's narration ("provide equity financing for an acquisition of Company B") is unambiguous: Sponsor C and D are NOT Saks-auction bidders; they are financing partners for Saks's *acquisition* of Company B (Company B was itself a target Saks was pursuing in parallel). These should be skipped under a stricter §Scope-1 interpretation. Prompt fix: when the filing narrates an NDA whose purpose is "financing an acquisition BY the target OF a third party," skip the NDA with a deal-level flag. Distinct from §M3 advisor NDAs.
3. **Week-of date anchoring (§B1).** `bids_try` uses mid-week (e.g., 2013-04-18 for "week of April 15, 2013") but §B1's table doesn't have a "week of X" entry. The closest rules are "first week of" → Monday+5 days offset, or "mid-X" → day-15. Consider adding: "week of [Date]" → that exact date (the Monday of the week). This would align `bids_try` to Alex's convention (Alex uses 2013-04-15).
4. **Company I Drop on Sep 6 (go-shop end).** `bids_try` misses this. Prompt fix: when a go-shop period ends and a named go-shop bidder has not submitted a proposal, emit a `Drop` row with precise date = go-shop end date (here 2013-09-06). §I1 naturally supports this under "voluntary (bidder)" given the filing says "None of the parties contacted as part of the go shop process, including Company I, has submitted an acquisition proposal."
5. **`Go-Shop` as synthesized bid_note in `bids_pipeline` (invalid).** `bids_pipeline`'s row 7.5 uses `bid_note="Go-Shop"`, which is NOT in §C1's 27-value closed vocabulary. This would hard-fail `rules/invariants.md` §P-R3. If `bids_pipeline` were run through this repo's validator, it would fail immediately.
6. **Alex's `Sponsor A/E` mislabel on 7/11 joint bid (xlsx row 7010).** The filing explicitly narrates the 7/11 joint bid as "Sponsor E, together with Sponsor G" — not A+E. Alex's label is wrong. Consider adding this to `alex_flagged_rows.json` as another `reference/alex/saks.json` override candidate (relabel from `Sponsor A/E` to `Sponsor E + Sponsor G`).

---

## Open questions for Austin

1. **§D1.a scope for Company H (row 7013 verdict).** Alex flagged row 7013 for deletion (pre-§D1.a). The current rulebook says emit as `Bid` with `unsolicited_first_contact` flag. **Your call:** (a) keep the live rulebook and accept that Alex's reference JSON should NOT drop Company H on re-conversion, OR (b) tighten §D1.a to exclude letters where the target can't even contact the bidder back (i.e., require at least one return communication attempt to succeed before the event "exists"). Option (a) is the low-friction answer.

2. **§H5 row-per-restatement for Sponsor A+E week of 7/22 (row 7015 verdict).** Alex flagged row 7015 as "not a separate bid, should be deleted" (rationale: no new price info). `bids_try` and `bids_pipeline` both emit. Per §H5, "each bid revision is a separate event row" — but this was a RESTATEMENT at the same range, not a revision. **Your call:** tighten the prompt to NOT emit a row when the bidder restates the same range without new information, OR accept that the rulebook's §H5 produces a more-information-dense dataset than Alex's convention.

3. **Sponsor C and Sponsor D as Saks-side bidders (§Scope-1 ambiguity).** Filing is clear they are Company-B-financing partners, not Saks auction counterparties. `bids_try` emits; Alex and `bids_pipeline` omit. **Your call:** do these NDAs count toward Saks's §Scope-1 auction threshold? The clean answer is no (they never expressed intent to acquire Saks), so `bids_try` should omit them (or emit with a `not_counterparty_nda` info flag that subtracts from the §Scope-1 count).

4. **Company F (week of 6/10/2013, p.32).** Only `bids_pipeline` catches this. **Your call:** this looks like a meaningful `Bidder Interest` + DD event that `bids_try` should have emitted. Confirm Alex's current reference JSON should be regenerated with this row (and let `bids_try` fix its prompt).

5. **`bidder_type.public` on Hudson's Bay.** HB is a publicly-traded Canadian company (TSX: HBC). `bids_try` correctly sets `{base: "s", non_us: true, public: true}`. Alex's reference JSON has the same. Confirm — no issue.

6. **Alex's `Sponsor A/E` mis-label on 7/11 joint bid.** The filing's 7/11 joint bid is explicitly E+G, not A+E. Alex's xlsx row 7010 labels it `Sponsor A/E`. This is probably an Alex-side transcription error. **Your call:** add to `alex_flagged_rows.json`, OR treat as an Alex judgment call (Alex may have been tracking "the sponsor group" as a single entity across time, so the label is a shorthand, not a specific claim about who was in the room). `bids_try`'s approach (row 17 labels as Sponsor E with `joint_nda_aggregated` flag) is the filing-faithful answer.

7. **Morgan Stanley as Saks advisor (§J1).** Only `bids_try` emits a Morgan Stanley `IB` row. Per §J1, advisors named in the Background must be emitted. **Your call:** confirm Alex's reference JSON should be regenerated with a Morgan Stanley IB row (7/26 first narration).

---

## Appendix: row-by-row alignment (hand-aligned)

Columns: index in source; bidder; bid_note; date; bid_value; verdict.

| bids_try row | Alex row | bids_pipeline row | Event (filing summary) |
|---|---|---|---|
| 1 Sponsor A, Bidder Interest, Feb 2013 | 2 Sponsor A, Bidder Interest, Feb 2013 | 2 Sponsor A, Bidder Interest, 02/15/2013 | Feb 2013 Sponsor A first contact. All three agree. |
| — | — | 3 Sponsor A, Bidder Interest, 03/01/2013 | Early-March meeting. Only bids_pipeline atomizes (over-atomization). |
| 2 Hudson's Bay, Bidder Interest, 2013-04-01 | (none) | 4 Hudson's Bay, Bidder Interest, 04/01/2013, bid_value=15 | Apr 1 Sadove–Baker meeting. Only bids_try / bids_pipeline emit; bids_pipeline erroneously has price. |
| 3 Goldman, IB, rough 2013-04-11 | 1 Goldman, IB, rough 2012-12-15 | (none) | Advisor retention. bids_try anchors to Apr 11; Alex to Dec 2012. |
| 4 Sponsor C, NDA, 2013-04-17 | — | — | Company-B financing NDA. Only bids_try emits. |
| 5 Hudson's Bay, Bid informal, 2013-04-18, lower=15 | 3 Hudson's Bay, Bid informal, rough 2013-04-15, lower=15 | 5 Hudson's Bay, Bid informal, 04/15/2013, value=pershare=lower=upper=15 | Week-of-Apr-15 "at least $15" indication. bids_pipeline wrongly encodes as point value; bids_try + Alex correct. |
| 6 Sponsor A, Bid informal, 2013-04-18, lower=15 | 4 Sponsor A, Bid informal, rough 2013-04-15, lower=15 | 6 Sponsor A, Bid informal, 04/15/2013, value=pershare=lower=upper=15 | Same as above. |
| 7 Sponsor D, NDA, 2013-04-19 | — | — | Company-B financing NDA. Only bids_try. |
| 8 Sponsor A, NDA, 2013-04-26 | 5 Sponsor A, NDA, 2013-04-26 | 7 Sponsor A, NDA, 04/26/2013 | Apr 26 Sponsor A CA. All agree. |
| 9 Sponsor E, NDA, 2013-04-26 | 6 Sponsor E, NDA, 2013-04-26 | 9 Sponsor E, NDA, 04/26/2013 | Apr 26 Sponsor E CA. All agree. |
| — | 7 Sponsor A, Drop, 2013-04-26 | 8 Sponsor A, Drop, no date | Spurious drop — filing does not narrate. bids_try correctly omits. |
| — | — | 10 Sponsor E, Drop, no date | Same spurious. |
| 10 Hudson's Bay, NDA, 2013-04-30 | 8 Hudson's Bay, NDA, 2013-04-30 | 11 Hudson's Bay, NDA, 04/30/2013 | Apr 30 HB CA. All agree. |
| 11 Target Sale, 2013-06-05 | — | 14 Target Sale, 06/05/2013 | Board authorizes process. Only bids_try + bids_pipeline emit; Alex gap. |
| 12 Hudson's Bay, Bid informal, 2013-06-06, lower=15 upper=15.25 | 9 Hudson's Bay, Bid informal, rough 2013-06-03, value=pershare=15 lower=15 upper=15.25 | 12 Hudson's Bay, Bid informal, 06/03/2013, lower=15 upper=15.25 | Jun-3-week HB range. All agree on range. |
| 13 Sponsor A, Bid informal, 2013-06-06, lower=15 upper=16 | 10 Sponsor A/E (joint), Bid informal, rough 2013-06-03, value=pershare=15 lower=15 upper=16 | 13 Sponsor A+Sponsor E, Bid informal, 06/03/2013, lower=15 upper=16 | Jun-3-week Sponsor A+E range. bids_try atomizes; Alex/BP combine. |
| 14 Sponsor E, Bid informal, 2013-06-06, lower=15 upper=16 | (merged into row 10) | (merged into row 13) | Sponsor E constituent. |
| — | — | 15 Company F, Bidder Interest, rough 06/10/2013 | Company F DD. Only bids_pipeline catches. |
| 15 Final Round Ann, 2013-07-02 | 11 Final Round Ann, 2013-07-02 | 16 Final Round Ann, 07/02/2013 | Jul-2 process letter. All agree. |
| 16 Sponsor G, NDA, 2013-07-08 | 16 Sponsor G, NDA, 2013-07-08 | 17 Sponsor G, NDA, 07/08/2013 | Jul-8 Sponsor G CA. All agree. |
| 17 Sponsor E (joint-with-G), Bid informal, 2013-07-11, lower=14.5 upper=15.5 | 17 Sponsor A/E [label wrong], Bid informal, 2013-07-11, lower=14.5 upper=15.5 | 19 Sponsor E+Sponsor G, Bid informal, 07/11/2013, lower=14.5 upper=15.5 | Jul-11 E+G joint bid. Alex label wrong; bids_try + bids_pipeline correct. |
| 18 Hudson's Bay, Bid formal, 2013-07-11, value=pershare=15.25 | 18 Hudson's Bay, Bid formal, 2013-07-11, pershare=15.25 | 18 Hudson's Bay, Bid formal, 07/11/2013, value=pershare=15.25 | Jul-11 HB formal bid. All agree. |
| — | — | 20 Final Round, 07/11/2013 | Jul-11 Final Round. Only bids_pipeline emits. bids_try omits (Final Round Ann already captured). |
| 19 Sponsor G, Drop, 2013-07-15 | 13 Sponsor G, Drop, no date | 21 Sponsor G, Drop, rough 07/15/2013 | Sponsor G withdraws. All three emit. |
| 20 Company H, Bid informal, 2013-07-21, value=$2.6B USD | (deleted per §Q1) | 22 Company H, Bidder Interest, rough 07/21/2013, NO value | Company H $2.6B letter. All three disagree on treatment. |
| — | 14 Company H, Drop, no date | — | Alex emits a companion Drop for Company H. Filing supports the narrative that Goldman never reached them → Drop is defensible. |
| 21 Hudson's Bay, Bid formal, 2013-07-24, pershare=16 | 19 Hudson's Bay, Bid formal, 2013-07-24, pershare=16 | 24 Hudson's Bay, Bid formal, 07/24/2013, pershare=16 | Jul-24 HB formal $16. All agree. |
| 22 Sponsor A, Bid informal, 2013-07-25, lower=14.5 upper=15.5 | (deleted per §Q1) | 23 Sponsor A+Sponsor E, Bid informal, 07/23/2013, lower=14.5 upper=15.5 | Week-of-7/22 restatement. Alex flagged delete. |
| 23 Sponsor E, Bid informal, 2013-07-25, lower=14.5 upper=15.5 | (deleted per §Q1) | (merged into prev) | Same restatement, Sponsor E constituent. |
| 24 Sponsor A, DropBelowM, 2013-07-25 | — | — | Jul-25 implicit drop. Only bids_try emits. |
| 25 Sponsor E, DropBelowM, 2013-07-25 | — | — | Same. |
| 26 Morgan Stanley, IB, rough 2013-07-26 | — | — | Morgan Stanley advisor. Only bids_try emits. |
| — | 21 Spnosor A/E, DropTarget, 2013-07-28 | — | Alex has a DropTarget on 7/28 (Alex label has typo "Spnosor"). bids_try uses DropBelowM on 7/25 instead. |
| 27 Hudson's Bay, Executed, 2013-07-28 | 22 Hudson's Bay, Executed, rough 2013-07-28 | 25 Hudson's Bay, Executed, 07/28/2013 | Merger executed. All agree. |
| 28 Hudson's Bay, Sale Press Release, 2013-07-29 | — | 26 (no bidder), Sale Press Release, 07/29/2013 | Jul-29 press release. Alex omits. |
| 29 Company I, NDA, 2013-08-11 | 20 Company I, NDA, rough 2013-07-29 | 27 Company I, NDA, rough 08/11/2013 | Company I CA (go-shop). Alex date wrong (should be ~8/11). |
| — | 23 Company I, Drop, 2013-09-06 | 28 Company I, Drop, no date | Company I go-shop end drop. bids_try missing. |
| — | — | 29 (no bidder), Go-Shop, 09/06/2013 | bids_pipeline invalid bid_note. |

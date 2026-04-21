---
date: 2026-04-21
auditor: Claude (orchestrator + 9 parallel general-purpose Opus agents)
deals_audited: 9 reference deals (medivation, imprivata, zep, providence-worcester, penford, mac-gray, petsmart-inc, stec, saks)
ground_truth: SEC filings under data/filings/{slug}/raw.md
status: COMPLETE
related:
  - quality_reports/plans/2026-04-21_three-way-comparison.md
  - quality_reports/comparisons/2026-04-21_three-way/{slug}_report.md (×9)
---

# MASTER REPORT — Three-way pipeline comparison

**Question.** Which of three candidate extraction pipelines is closest to filing-truth on the 9 reference deals: `bids_pipeline` (older), `bids_try` (current), or Alex's hand-corrected workbook?

**Answer.** **`bids_try` wins — by a wide margin.** It wins outright on 7 of 9 deals, and shares the win on the other 2 (where `bids_pipeline` has more raw coverage but `bids_try` has rule compliance and provenance). `bids_pipeline` never wins outright — it fails the §P-R2 hard invariant on **every row of every deal** (no `source_quote` / `source_page` columns at all), fails §P-G2 on **every bid row** (point bids encoded as `lower==upper`), and emits out-of-vocabulary event codes (`Exclusivity`, `Go-Shop`).

**This audit is the single largest piece of independent validation evidence the project has produced.** 9 Opus agents, each reading a 1300–4900-line SEC filing as ground truth, the local rulebook (`rules/*.md`), and all three extractions. Total output: ~412KB of structured comparison reports, including ~150 individual row-level adjudications against the filing.

---

## Per-deal verdicts

| Deal | Winner | bids_try rows | bids_pipeline rows | Alex rows | Headline |
|---|---|---|---|---|---|
| medivation | **bids_try** | 20 | 22 | 16 | Only `bids_try` carries §B5 receipt-date, all 4 IBs, and termination-fee deal-level fields. Confirms Alex §Q4 row 6066/6070 BidderID=5 duplicates (precise dates wrong) and Alex's 4/13 Sanofi date is filing-wrong. |
| imprivata | **bids_try** | 26 | 34 | 29 | `bids_try` correctly skips 3 §M1 contacted-but-no-NDA parties + Strategic 4 that `bp` over-emits. Alex internally inconsistent: Sponsor A 6/15 = DropAtInf but structurally identical Sponsor B 6/29 = DropBelowInf. |
| zep | **bids_try** | 48 | **80** | 23 | `bp` fabricates **25 phantom drops** on 2014-06-19/26 + 3 phantom 2013 phase-0 events + 2 out-of-vocab Exclusivity + 1 out-of-vocab Go-Shop. `bids_try`'s 48 reconciles cleanly to filing's quantitative commitments (25 NDAs, 5 IOIs, 5+1 mid-June drops). 2 real `bids_try` bugs: misses §M4 2/27 NDA revival; misses §K2 Final Round Inf Ann/Inf rows. |
| providence-worcester | **bids_try** | 63 | 64 | 36 | NDA atomization verdict: **accept iter-7 soft flags, do NOT tighten §E2.b**. `bids_try` complies with current §E2.b row 2 (numeric count → atomize); `bp`'s 11 unnamed-NDA Drop pairs violate §I1 + §R2. Real `bids_try` miss: G&W 8/12 $25 should be formal (merger-agreement markup is §G1 trigger); missed `Auction Closed` event. |
| penford | **split — bp coverage, bids_try compliance** | 26 | 33 | 25 | `bp` uniquely captures Party B (9/12), Party E, Party F (9/29), SEACOR (8/12) as dropouts. `bids_try` uniquely captures 2007/2009 stale priors + acquirer IB (J.P. Morgan). `bids_try` real bugs: Ingredion 7/17 misclassified `Bidder Sale` (should be `Bidder Interest`); misses Ingredion 8/6 $17 + 10/14 formal $19 bids. **Bidder-type verdict: converter bug** (xlsx has `public S` for Ingredion; `build_reference.py` drops the `public` bit). |
| mac-gray | **bids_try** | 45 | 65 | 34 | `bp` fabricates 16 synthetic catch-all Drop rows on 7/25 (replicates the Providence iter-7 failure mode §I1 was written to prevent). Confirms Alex row 6960 BidderID=21 duplicates 6957. Acquirer name: `bids_try` uses filing-verbatim "CSC ServiceWorks, Inc."; **Alex reference JSON wrongly uses provenance string "CSC purchased by Pamplona in May/2013"**. Real `bids_try` miss: Party B $21.50 composite-contingent classified informal (§G1 process-letter formal trigger). |
| petsmart-inc | **split — bp coverage, bids_try compliance** | 41 | 55 | 53 | `bp` captures Industry Participant pre-history (Mar–Aug 2014) that `bids_try` misses entirely (4 rows). Both atomize 15 NDAs correctly per §E5. Catch-all Drops policy: `bp` 10, Alex 8, `bids_try` 0 (§I1 compliant). `bids_try` misses §K1/§K2 round markers (5 rows). **18+ false-positive `source_quote_not_in_page` flags** on `bids_try` are an apostrophe ASCII vs Unicode normalizer bug, not extraction defect. |
| stec | **bids_try** | 31 | 42 | 28 | `bp` collapses **every point bid** to `lower==upper` (Company D $5.75, WDC $9.15, WDC $6.85) — fails §P-G2 on every bid row. Only `bids_try` correctly uses `lower=5.60, upper=null` for the Company D 4/23 single-bound "$5.60+" bid. Company H 5/23 dropout: filing language is target-initiated → `DropBelowInf` (`bids_try` correct; Alex generic `Drop`; `bp` `DropAtInf` wrong agency). |
| saks | **bids_try** | 29 | 28 | 25 | Flagged-row 7013/7015 verdict: **emit per current §D1.a / §H5; Alex's "delete" predates these rules**. `bp` mis-encodes HB 4/1 meeting as `bid_value=15` (filing explicitly: "no specific proposals"); also encodes "at least $15" as upper=15 (§H1 violation). Real `bids_try` misses: Company F (6/10 Bidder Interest); Sponsor C/D NDAs incorrectly emitted (financing for Saks→Company B acquisition, not Saks-side). Real Alex error: 7/11 joint bid mislabeled "Sponsor A/E" (filing says E+G). |

**Score:** bids_try 7 outright + 2 split. bids_pipeline 0 outright + 2 split. Alex 0 outright.

---

## Systemic findings — which pipeline wins on which dimension

### Dimension 1: Source-citation discipline (§R3 / §P-R2 hard invariant)

| Pipeline | Coverage | Verdict |
|---|---|---|
| bids_try | 100% of rows have `source_quote` + `source_page` (every deal, every row) | **PASS** |
| bids_pipeline | **0% — `source_quote` and `source_page` columns are absent from the CSV header** | **HARD FAIL on every row of every deal** |
| Alex | 0% by design (reference JSONs intentionally omit evidence per CLAUDE.md) | N/A — reference, not extraction |

**This alone disqualifies bids_pipeline from production use.** §P-R2 is the validator's hardest invariant. Re-using bids_pipeline output would require full re-extraction with evidence fields populated — i.e., a new pipeline.

### Dimension 2: Bid value structure (§H1 + §P-G2)

| Pipeline | Behavior | Verdict |
|---|---|---|
| bids_try | Range bids: populates `lower`/`upper`, leaves `pershare` null. Single-lower-bound ("at least $X"): `lower=X, upper=null` + `bid_lower_only` flag. Point bids: `pershare=X, lower=null, upper=null`. **Always emits `bid_type_inference_note`** on bid rows. | **PASS §H1 + §P-G2** |
| bids_pipeline | **Collapses every point bid to `lower=upper=pershare`** (STec: WDC $9.15 → 9.15/9.15/9.15). Treats single-bound as point. **Emits no `bid_type_inference_note` anywhere.** | **HARD FAIL §P-G2 on every bid row** (not a true range, no inference note → fails the §P-G2 satisfier disjunction) |
| Alex (xlsx) | Legacy convention: duplicates point value into `lower=upper=pershare`. No inference notes. | Pre-§H1; `build_reference.py` re-encodes during xlsx→JSON conversion |

### Dimension 3: BidderID convention (§A1 strict-integer 1..N)

| Pipeline | Behavior | Verdict |
|---|---|---|
| bids_try | Strict integer 1..N sequence, no decimals, dense | **PASS §A1** |
| bids_pipeline | **Decimal wedges**: 0.3, 0.5, 0.7, 1.5, 3.066, 3.133, 14.5, 18.5, 21.5, 28.5, etc. | **HARD FAIL §A1** |
| Alex (xlsx) | Decimal wedges (legacy) — `build_reference.py` §A1 renumbers during conversion | Pre-§A1 |

### Dimension 4: Atomization vs aggregation (§E1 / §E2.b / §E5)

| Pipeline | Behavior on filing-stated counts | Verdict |
|---|---|---|
| bids_try | Atomizes per filing-stated count. Uses §E5 placeholders (`Strategic 1..N`, `Financial 1..N`). Carries `unnamed_count_placeholder` info flags. | **PASS §E2.b**. Producing 20 `nda_without_bid_or_drop` soft flags on Providence is the **rule's intended behavior** (§I1 + §P-S1 explicitly endorsed in the rulebook after iter-7). |
| bids_pipeline | Inconsistent. Atomizes some unnamed bidders (Mac-Gray 16 financial), then **fabricates Drop rows for each placeholder** (§I1 violation: "do not fabricate catch-all Drop rows with generic shared `source_quote`"). On Providence: atomizes 11 unnamed financial NDAs but misses 10 unnamed strategic NDAs. | **PARTIAL FAIL** — half-atomization + fabricated drops |
| Alex | Aggregates with sentence-form bidder names (`"Several parties, including Sanofi"`, `"5 parties, 4F and 1S"`, `"25 potential buyers"`). | **Legacy** — `build_reference.py` §Q1–§Q5 partially atomizes during conversion. Alex flagged row 6390 (Zep, "5 parties") himself for expansion. |

### Dimension 5: Date-precision discipline (§B1, §B3, §B4, §B5)

| Pipeline | Behavior | Verdict |
|---|---|---|
| bids_try | Receipt vs sent date per §B5; midpoint per §B4 ("May 6 through June 9" → 5/23); Q-mapping per §B1 (Q4 2015 → 2015-11-15); rough-anchor preserved with inference flags | **PASS** |
| bids_pipeline | Mixes precise/rough inconsistently. Uses month-midpoint where range-midpoint applies. Sometimes leaves precise blank with rough-only (violates §B2 mutual-exclusivity = §P-D2 hard) | Partial fail |
| Alex | §B5 violated (Sanofi 4/13 letter date used as event anchor; should be 4/15 receipt). §Q4 precise-date errors (Medivation 8/14 used for 7/19/8/10/8/19 events). | Multiple defects |

### Dimension 6: Event-vocabulary compliance (§C1)

| Pipeline | Out-of-vocab codes emitted | Verdict |
|---|---|---|
| bids_try | None observed across all 9 deals | **PASS §C1** |
| bids_pipeline | `Exclusivity` (Zep ×2), `Go-Shop` (Zep, Saks), `Target Interest` for "50 potential buyers" mass outreach (Zep) | **HARD FAIL §P-R3** |
| Alex (xlsx) | Legacy `Exclusivity 30 days` (now an attribute per §O1, not an event) | Legacy |

### Dimension 7: §G1 informal-vs-formal classification

| Pipeline | Behavior | Verdict |
|---|---|---|
| bids_try | Uses §G1 trigger table consistently. Emits inference notes. **Misclassifications observed:** Mac-Gray Party B $21.50 (composite-contingent, should be formal); Providence G&W 8/12 $25 (merger-agreement markup, should be formal). | Mostly correct, 2 specific misclassifications across 9 deals |
| bids_pipeline | Inconsistent. Imprivata: TB 7/9 $19.25 best-and-final marked **Informal** (filing literally says "best and final" — explicit §G1 formal trigger). Providence: 3 non-binding LOIs marked Formal. | Multiple misclassifications |
| Alex | Mostly correct; flags own uncertainty (Providence Party B 7/25: *"what is the threshold for 'formal'?"*). | Inconsistent but self-aware |

### Dimension 8: Bidder typing (§F1 / §F2)

| Pipeline | Behavior | Verdict |
|---|---|---|
| bids_try | Structured `{base, non_us, public}` object on every row. Correctly types financials, strategics, non-US. **Defect:** Pfizer (Medivation) marked `public:null` despite obvious public-Board narration — §F2 prompt under-fires when "publicly traded" phrase is absent but Board-of-Directors / SEC-filing context is present. | Mostly correct |
| bids_pipeline | Legacy boolean column form (`bidder_type_financial=1` etc.). Drops the `public` bit on most rows. Fills `bidder_type_note` only on ~8 named-counterparty rows; leaves rest NA. | Partial |
| Alex (xlsx) | Includes `public` in the type note (e.g., "non-US public S") | Best on `public` |
| Alex (reference JSON) | **Converter bug: `build_reference.py` drops the `public` bit during xlsx→JSON.** Penford xlsx says `public S` for Ingredion; reference JSON says `public:null`. | Converter defect — drives 43+ field-diffs across the reference set |

### Dimension 9: Coverage of process events bids_try misses

The two deals where bids_pipeline shares the win (Penford, PetSmart) reveal a real coverage gap in bids_try's prompt:

| Event class | Examples | Where bids_try misses |
|---|---|---|
| Pre-history Industry Participants | PetSmart Industry Participant March 2014 → August 2014 (Target Interest → Bidder Interest → DropTarget) | PetSmart |
| Declining counterparties (no bid, no NDA) | Penford: Party B (9/12), Party E (9/12 voicemail), Party F (9/29), SEACOR (8/12) | Penford |
| §K2 round markers | Final Round Inf Ann (Zep 3/27 process letter); Final Round Inf (Zep 4/14 deadline); Final Round Ann (Providence 7/27 cut to G&W+Party B) | Zep, Providence, PetSmart |
| §M4 NDA revival | Zep NMC 2/27 NDA extension (causes 3 hard `bid_without_preceding_nda` flags); Mac-Gray 8/27 process letter | Zep, Mac-Gray |
| `Auction Closed` (§C1) | Providence 8/12 unilateral-stop (target proceeds to Executed without final-round announcement) | Providence |

bids_pipeline catches several of these where bids_try misses — at the cost of much else. The bids_try prompt should be tightened on these specific patterns (see "Recommended fixes" below).

---

## Alex's reference defects surfaced by this audit

Per CLAUDE.md's 4-verdict adjudication framework, **Verdict 1 (AI correct, Alex wrong)** records:

| # | Deal | Alex error | Verdict source | Recommended action |
|---|---|---|---|---|
| 1 | medivation | Sanofi first-contact = 2016-04-13 (letter date). Filing p. 24: "received… on April 15, 2016." §B5 receipt date. | medivation_report §1 | Update Alex reference JSON Sanofi rows to 2016-04-15 |
| 2 | medivation | §Q4 row 6066 `Final Round Inf Ann` precise=2016-08-14. Filing: 2016-07-19. | medivation_report §6 | Already pre-flagged in `alex_flagged_rows.json`; converter §Q4 should use the rough date |
| 3 | medivation | §Q4 row 6070 `Final Round` precise=2016-08-14. Filing: 2016-08-19. | medivation_report §7 | Same |
| 4 | medivation | `Final Round Inf` precise=2016-08-14. Filing: 2016-08-08. | medivation_report §9 | Same |
| 5 | medivation | `Final Round Ann` precise=2016-08-14. Filing: 2016-08-10. | medivation_report §8 | Same |
| 6 | imprivata | Sponsor A 6/15 DropAtInf (filing language is target-initiated). Inconsistent with own Sponsor B 6/29 = DropBelowInf. | imprivata_report §F | Promote Alex Sponsor A 6/15 to `DropBelowInf` |
| 7 | imprivata | Barclays IB date = 2016-03-09 (filing: Barclays not considered until 3/14, Board-decision 4/15). | imprivata_report §B | Update to 2016-04-15 (Board-decision per §B5) |
| 8 | imprivata | 6/24 over-coding: `Final Round Ext Ann` + `Final Round Ann` + `Final Round Ext`. Filing: first formal final-round announcement, not an extension. | imprivata_report §H | Collapse to one `Final Round Ann` row |
| 9 | imprivata | Executed row date 2016-07-09. Filing (Jul 13): "the parties finalized and executed the merger agreement." | imprivata_report §K | Update to 2016-07-13 |
| 10 | imprivata | Missing June 2015 Bidder Interest (filing: "early 2015, **and again in June 2015**, representatives of Thoma Bravo informally approached") | imprivata_report §A | Add row |
| 11 | zep | NMC 19.25 bid date = 2015-02-10 (meeting date). Filing (Feb 19): "On February 19, 2015, New Mountain Capital delivered… per share price of $19.25". | zep_report §11 | Update to 2015-02-19 |
| 12 | zep | NMC best-and-final formal bid date = 2015-03-29 (revised merger agreement date, not bid date). Filing (Mar 13): "communicated that the $20.05 per share offer price was… 'best and final' offer". | zep_report §13 | Update to 2015-03-13 |
| 13 | zep | NDA aggregate count = "24 parties". Filing: 25 NDAs ("twenty-five potential buyers executed confidentiality agreements"). | zep_report §3 | Update count to 25 (or atomize per §E2.b) |
| 14 | mac-gray | Party C NDA `bid_date_precise=2013-06-20`. Filing (p. 38): "On June 30, 2013, Party C entered into…". Likely typo. | mac-gray_report Alex section | Update to 2013-06-30 |
| 15 | mac-gray | Acquirer field reads "CSC purchased by Pamplona in May/2013" (provenance commentary, not entity name). Filing-correct: "CSC ServiceWorks, Inc." | mac-gray_report TL;DR | Update reference JSON Acquirer to "CSC ServiceWorks, Inc." |
| 16 | saks | Row 7011 (xlsx 7/11 joint bid) labeled "Sponsor A/E". Filing: joint bid was Sponsor E + Sponsor G (Sponsor A had stepped back as primary). | saks_report timeline §Jul 11 | Update label to "Sponsor E/G" or split |
| 17 | penford | Reference JSON `bidder_type.public: null` for Ingredion. Xlsx: `public S`. Converter bug. | penford_report §3 | Fix `scripts/build_reference.py` to preserve `public` bit |

These are AI-identified corrections. Per CLAUDE.md: **"do NOT update the prompt/rulebook"** for these — update Alex's reference instead.

---

## Recommended bids_try fixes (real bugs to close before 392-deal run)

### Prompt / extractor fixes (high-priority)

| # | Bug | Deals affected | Fix |
|---|---|---|---|
| 1 | **§I1 Drop agency: bids_try uniformly emits `DropBelowInf`** where filing supports voluntary `Drop`. Pattern: bidder informs target "no longer interested" → bids_try reads as target-cut. | imprivata (Strategic 1/2/3, "Sponsor C") | Strengthen §I1 examples: "[Bidder] informed [Target] that [it was no longer interested]" + no target-rejection language → voluntary `Drop`. Only with explicit "[Target] informed [bidder] that…" or "[Target] decided [bidder] would not advance" → `DropBelowInf` |
| 2 | **§K2 implicit final-round inference under-applied.** bids_try misses `Final Round Inf Ann` / `Final Round Inf` / `Final Round Ann` rows when filing narrates a process-letter or subset-narrowing event. | zep (3/27 letter, 4/14 deadline), providence (7/27 G&W+Party B cut), petsmart (multiple), imprivata (6/9 deadline, 7/8 deadline) | Add §K2 trigger guidance: process letter → emit `Final Round Inf Ann`. Submission deadline → emit `Final Round Inf`. Subset-narrowing ("informed remaining bidders…" or "selected X to advance…") → emit `Final Round Ann` for the advancers |
| 3 | **§M4 NDA-revival not firing.** bids_try misses phase-2 NDA-extension events that the filing narrates. Causes hard `bid_without_preceding_nda` flags on subsequent phase-2 bids. | zep (NMC 2/27), mac-gray (8/27), stec (WDC 4/17 addendum) | Add §M4 example phrases: "extending the term of the confidentiality provision", "addendum to the prior NDA", "executed an addendum effective…". When matched, emit phase-2 `NDA` row with `nda_revived_from_stale` info flag |
| 4 | **§F2 `public` inference under-fires.** bids_try marks Pfizer `public:null` despite filing's narration of Pfizer Board acting as fiduciaries. | medivation (Pfizer), broader (43+ converter-side diffs noted in CLAUDE.md) | Tighten §F2 rule 2/3: if the bidder is textually identified as having a public Board acting as fiduciaries OR is a SEC registrant filing public disclosures referenced in the filing, infer `public:true` even without explicit "publicly traded" |
| 5 | **§G1 formal-trigger priority.** bids_try misses formal triggers when "non-binding" framing also present. | mac-gray (Party B $21.50 composite-contingent), providence (G&W 8/12 $25 with merger-agreement markup) | Reinforce §G1 trigger priority: "merger-agreement markup", "best and final", "fully financed", "executed commitment letters" → formal regardless of any "non-binding" preamble. Composite/contingent consideration alone is not an informal-downgrade signal |
| 6 | **Pre-history strategic counterparties missed.** bids_try omits Industry Participant pre-process events. | petsmart (Mar–Aug 2014 IP), penford (Party B/E/F/SEACOR) | Strengthen §D1 / §M1 distinction: contacted-but-no-NDA strategics that do receive narrated discussion (even if brief) should emit `Bidder Interest` + `DropTarget` (or `Drop` voluntary). Only skip per §M1 when filing has only one-line "X declined" with no preceding interaction |
| 7 | **`Auction Closed` (§C1) under-utilized.** bids_try goes from active bidding to `Executed` without emitting `Auction Closed` when there's no formal final-round deadline. | providence (8/12 G&W $25 → 8/12 Executed without intervening Final Round) | Add §C1 trigger: when target proceeds to Executed without intervening `Final Round` or formally announced deadline, emit `Auction Closed` on the last-substantive-action date |
| 8 | **§D1 Bidder Interest vs Bidder Sale.** bids_try over-classifies first-contact "interest in acquiring" as `Bidder Sale`. | penford (Ingredion 7/17) | Reinforce §D1 rule: when bidder expresses "interest in acquiring" without concrete price, emit `Bidder Interest`. Transition to `Bidder Sale` is recorded on the *later* date when concrete proposal is made (do NOT retcon the earlier row) |
| 9 | **NDA scope distinction (§M3 / §Scope-1).** bids_try emits financing-partner NDAs as Saks-side NDAs. | saks (Sponsor C/D — Company B financing context, not Saks-as-target) | Clarify §M3 / §Scope-1: NDAs signed by financing partners for the **target's outbound acquisition** are out of scope for the target's inbound auction. Skip with `nda_context_outside_auction` info flag (or omit entirely) |

### Pipeline-level fixes (lower priority, but blockers for clean validation)

| # | Bug | Deal where surfaced | Fix |
|---|---|---|---|
| 10 | **`source_quote_not_in_page` false positives** caused by ASCII straight-apostrophe vs Unicode curly-apostrophe mismatch | petsmart (18+ flags), providence | Add NFKC normalization + apostrophe canonicalization before substring check |
| 11 | **Page-spanning quotes** failing substring check when paragraph spans `pages.json` page boundary | zep (3 hard flags) | Either (a) post-process extractor output to split paragraph-spanning quotes into `list[str]` + `list[int]`, OR (b) re-chunk `pages.json` on paragraph boundaries |
| 12 | **Hard extraction misses on Penford Ingredion** (8/6 $17 + 10/14 formal $19) | penford | Investigate prompt — these are concrete bid events filing explicitly narrates |

### Rulebook updates (small)

| # | Update | Reason |
|---|---|---|
| 13 | **§K2 trigger list addition: "remaining bidders informed they're out" pattern** → emit `Final Round Ann` for the advancers | Providence 7/27 |
| 14 | **§I1 NDA-only soft-flag policy: keep current behavior** (do NOT tighten §E2.b) | Confirmed by Providence audit — soft flags are working as designed |
| 15 | **§D1.b atomization: "follow-up advocacy is not a new Activist Sale row"** | PetSmart (bp over-atomizes JANA 7/3 + 7/10 + Longview 7/7 + 7/10; only the 7/3 / 7/7 13D filings are events) |

---

## Converter-side (`scripts/build_reference.py`) fixes

| # | Fix | Affected reference JSONs |
|---|---|---|
| 1 | Preserve `public` bit during xlsx→JSON. Currently dropped, causing 43+ `bidder_type` field diffs. | All 9 (Penford, STec, Mac-Gray, Providence most affected) |
| 2 | Mac-Gray Acquirer field: use filing-verbatim "CSC ServiceWorks, Inc." (currently the provenance string "CSC purchased by Pamplona in May/2013") | mac-gray |
| 3 | Implement §H2 CVR decomposition for composite consideration bids (`cash_per_share`, `contingent_per_share`, `consideration_components`) | providence (G&W 7/21, 7/26 rows) |
| 4 | Reconsider §Q1 deletion of Saks rows 7013 (Company H $2.6B) and 7015 (Sponsor A/E reaffirm) — current rulebook (§D1.a, §H5) says emit | saks |
| 5 | Apply §Q4 precise-date corrections from medivation_alex.csv to reference JSON (rows 6066, 6068, 6069, 6070) | medivation |
| 6 | Fix Saks 7/11 joint bid label (Alex says "Sponsor A/E"; filing says E+G) | saks |

---

## Open questions for Austin (decisions only Austin can make)

1. **Which pipeline ships?** Recommendation: **bids_try**. bids_pipeline cannot ship — it fails §P-R2 and §P-G2 hard invariants on every row of every deal.

2. **Apply the 9 bids_try prompt/extractor fixes (items 1–9 above) before the 392-deal crank?** Strongly recommended — items 2 (§K2 round markers), 3 (§M4 NDA revival), and 5 (§G1 formal-trigger priority) each affect multiple deals.

3. **Apply the 17 Alex reference JSON corrections?** All Verdict 1 corrections (AI correct, Alex wrong). They make the diff harness more honest going forward; they do not require rulebook changes.

4. **Apply the 3 converter-side fixes (`public` bit, Mac-Gray Acquirer, §H2 CVR)?** Yes — these resolve dozens of stale field-diffs without touching extraction logic.

5. **Saks rows 7013/7015 deletion: keep §Q1 or drop §Q1?** Per current rulebook, §D1.a says Company H 7013 should emit with `unsolicited_first_contact` flag; §H5 says Sponsor A/E 7015 reaffirm should emit per restated-range rule. Alex's "delete" notes predate these rules. **Recommendation: drop §Q1** (regenerate Alex JSONs without the deletion). Both AI pipelines independently emit these rows; aligning the reference reduces noise in the diff harness.

6. **Reference-set exit clock recount.** Per CLAUDE.md the clock was at 0/3 strict, 1/3 pragmatic. This audit identifies real bids_try bugs (items 1–12) that should be fixed before the next clean-run attempt — i.e., the clock effectively resets while these are fixed, then can advance. After fixes: target 3 consecutive unchanged-rulebook clean runs.

7. **bids_pipeline future.** It captures real signal (Penford Party B/E/F/SEACOR; PetSmart Industry Participant pre-history) that bids_try misses. Are those signals worth the §P-R2 ship-blocker? **Recommendation: do not ship bids_pipeline; instead use its findings as a checklist of events bids_try should also be capturing, and tighten bids_try's prompt to close those gaps (items 6, 8 above).**

---

## Methodology note

Each deal report was produced by a separate Opus agent in parallel, with no cross-deal state. Each agent:
1. Read the local rulebook (`rules/*.md`)
2. Read the SEC filing as ground truth (`data/filings/{slug}/raw.md`, 1300–4900 lines)
3. Read all three extractions (CSV slices)
4. Read Alex's reference JSON + flagged rows
5. Built an event-by-event timeline from the filing
6. Adjudicated every meaningful divergence against the filing using the 4-verdict framework
7. Wrote a structured report to `quality_reports/comparisons/2026-04-21_three-way/{slug}_report.md`

Each report includes: filing event timeline with page citations, per-source row counts and atomization style, divergence table with verdicts (`AlexRight | BPRight | TryRight | BothAIRight | NoneRight | JudgmentCall | AlexFlagged`), systemic findings, recommended rule/prompt fixes, and open questions.

Plan: `quality_reports/plans/2026-04-21_three-way-comparison.md`. Per-deal CSV slices: `quality_reports/comparisons/2026-04-21_three-way/inputs/{slug}_{alex|bids_pipeline|bids_try}.csv` (27 files).

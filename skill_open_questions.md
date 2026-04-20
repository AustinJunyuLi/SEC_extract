# Stage 1 Open Questions — Index

**Purpose.** Slim tracker of every 🟥 OPEN question across `rules/*.md`. Resolve them in the order below. When every item shows 🟩 RESOLVED, Stage 1 is done and Stage 2 can begin.

**How to use.** For each open item, open the referenced rule file, read the Context/Options for that section, discuss with Austin (and Alex when needed), and write the answer into the `Decision:` field in that file. When the decision lands, update this file's emoji to 🟩.

**Status legend:** 🟥 OPEN · 🟨 TENTATIVE · 🟩 RESOLVED

---

## Walkthrough order

Scope decisions first (they constrain everything), schema next (defines the output), then the event/bidder/bid semantics, then dates, then invariants last (they check what everything else produces). Within each file, work top-to-bottom.

1. `rules/schema.md` §Scope-1, §Scope-2, §Scope-3 — what deals, what filings, what's out of scope.
2. `rules/schema.md` §R1, §R2, §R3 — output columns.
3. `rules/schema.md` §N1, §N2, §N3 — deal-level vs event-level split.
4. `rules/events.md` §C1, §C2, §C3 — closed event vocabulary.
5. `rules/events.md` §D1 — start-of-process decision tree.
6. `rules/events.md` §I1, §I2 — dropout codes.
7. `rules/events.md` §J1, §J2 — investment bank + legal counsel.
8. `rules/events.md` §K1, §K2 — final-round vocabulary and edge cases.
9. `rules/events.md` §L1, §L2 — prior-process inclusion.
10. `rules/bidders.md` §E1, §E2, §E3, §E4 — identity, aggregation, joint bidders, winner retrofit.
11. `rules/bidders.md` §F1, §F2, §F3 — bidder type canonical format.
12. `rules/bids.md` §G1, §G2 — informal-vs-formal call. **Highest-risk classification.**
13. `rules/bids.md` §H1, §H2, §H3, §H4, §H5 — bid value structure.
14. `rules/bids.md` §M1, §M2, §M3, §M4 — skip rules.
15. `rules/bids.md` §O1 — process conditions.
16. `rules/dates.md` §B1, §B2, §B3, §B4 — natural-language date mapping.
17. `rules/dates.md` §A1, §A2, §A3, §A4 — `BidderID` event sequencing.
18. §Q1–§Q5 — Alex-flagged rows in the reference workbook (what to do during xlsx → JSON conversion; now documented in `scripts/build_reference.py` module docstring).
19. `rules/invariants.md` §P-R*, §P-D*, §P-S* — validator invariants. Write only after 1–18.

---

## Status matrix

| # | File | Section | Question | Status |
|---|---|---|---|---|
| 1 | `rules/schema.md` | §Scope-1 | Auction-only or every M&A? | 🟩 |
| 2 | `rules/schema.md` | §Scope-2 | Which filing types? | 🟩 |
| 3 | `rules/schema.md` | §Scope-3 | What does the skill not produce? | 🟩 |
| 4 | `rules/schema.md` | §R1 | Final column set | 🟩 |
| 5 | `rules/schema.md` | §R2 | Flags column format | 🟩 |
| 6 | `rules/schema.md` | §R3 | Evidence quote column | 🟩 |
| 7 | `rules/schema.md` | §N1 | Deal-level split | 🟩 |
| 8 | `rules/schema.md` | §N2 | `all_cash` derivation | 🟩 |
| 9 | `rules/schema.md` | §N3 | `cshoc` source | 🟩 |
| 10 | `rules/events.md` | §C1 | Final `bid_note` list | 🟩 |
| 11 | `rules/events.md` | §C2 | Capitalization canonicalization | 🟩 |
| 12 | `rules/events.md` | §C3 | `bid_note` on bid rows | 🟩 |
| 13 | `rules/events.md` | §D1 | Start-of-process classification | 🟩 |
| 14 | `rules/events.md` | §I1 | Dropout code set | 🟩 |
| 15 | `rules/events.md` | §I2 | Re-engagement code | 🟩 |
| 16 | `rules/events.md` | §J1 | `IB Terminated` handling | 🟩 |
| 17 | `rules/events.md` | §J2 | Legal counsel structural home | 🟩 |
| 18 | `rules/events.md` | §K1 | Final-round vocabulary | 🟩 |
| 19 | `rules/events.md` | §K2 | Implicit final rounds | 🟩 |
| 21 | `rules/events.md` | §L1 | Prior-process inclusion | 🟩 |
| 22 | `rules/events.md` | §L2 | `process_phase` column | 🟩 |
| 23 | `rules/bidders.md` | §E1 | Aggregate vs atomize | 🟩 |
| 24 | `rules/bidders.md` | §E2 | Joint-bidder rows | 🟩 |
| 25 | `rules/bidders.md` | §E3 | Anonymous naming | 🟩 |
| 26 | `rules/bidders.md` | §E4 | Winner retrofit | 🟩 |
| 27 | `rules/bidders.md` | §F1 | Bidder type format | 🟩 |
| 28 | `rules/bidders.md` | §F2 | Type classification rules | 🟩 |
| 29 | `rules/bidders.md` | §F3 | Consortium type | 🟩 |
| 30 | `rules/bids.md` | §G1 | Informal-vs-formal rule | 🟩 |
| 31 | `rules/bids.md` | §G2 | Classification evidence | 🟩 |
| 32 | `rules/bids.md` | §H1 | Ranges + single-bound | 🟩 |
| 33 | `rules/bids.md` | §H2 | Composite consideration | 🟩 |
| 34 | `rules/bids.md` | §H3 | Partial-company bids | 🟩 |
| 35 | `rules/bids.md` | §H4 | Aggregate-dollar bids | 🟩 |
| 36 | `rules/bids.md` | §H5 | Bid revisions | 🟩 |
| 37 | `rules/bids.md` | §M1 | Unsolicited-no-NDA skip | 🟩 |
| 38 | `rules/bids.md` | §M2 | No-bid-intent skip | 🟩 |
| 39 | `rules/bids.md` | §M3 | Advisor NDA disambiguation | 🟩 |
| 40 | `rules/bids.md` | §M4 | Stale-process NDA | 🟩 |
| 41 | `rules/bids.md` | §O1 | Process-condition columns | 🟩 |
| 42 | `rules/dates.md` | §B1 | Natural-language date mapping | 🟩 |
| 43 | `rules/dates.md` | §B2 | Precise vs rough | 🟩 |
| 44 | `rules/dates.md` | §B3 | Undated events | 🟩 |
| 45 | `rules/dates.md` | §B4 | Date ranges | 🟩 |
| 46 | `rules/dates.md` | §A1 | Keep `BidderID`? | 🟩 |
| 47 | `rules/dates.md` | §A2 | Strict monotonicity | 🟩 |
| 48 | `rules/dates.md` | §A3 | Same-date tie-break | 🟩 |
| 49 | `rules/dates.md` | §A4 | `BidderID` invariants | 🟩 |
| 50 | `scripts/build_reference.py` | §Q1 | Saks deletion rows | 🟩 |
| 51 | `scripts/build_reference.py` | §Q2 | Zep row 6390 | 🟩 |
| 52 | `scripts/build_reference.py` | §Q3 | Mac Gray `BidderID=21` dup | 🟩 |
| 53 | `scripts/build_reference.py` | §Q4 | Medivation `BidderID=5` dup | 🟩 |
| 54 | `scripts/build_reference.py` | §Q5 | Medivation 'Several parties' atomization | 🟩 |
| 55 | `rules/invariants.md` | §P-R1…§P-S4 | All validator invariants | 🟩 |

**Total open:** 0 🟥 · 0 🟨 · 54 🟩

> 🎉 **Stage 1 complete — 2026-04-18.** All 54 rule decisions have been ratified and written into `rules/*.md`. Proceed to Stage 2. (Row 20 is an intentional gap: the original §K3 question was retired post-facto, and the rule itself was fully deleted in Stage 3 iter-6. §Q5 was added later, bringing the final rulebook count back to 54.)

Some questions are tightly coupled and will likely be resolved together (e.g., §E1 + §E2 + §Q2 all concern the aggregate-vs-atomize decision). Handle them as bundles where natural.

---

## What needs Alex vs what Austin can decide

**Alex required:**
- §R1 column set (final schema is a research-design call).
- §R3 evidence quote (impacts his post-extraction review workflow).
- §G1 informal-vs-formal (core to his research question).
- §H2 composite consideration (impacts downstream analysis).
- §J2 legal counsel placement.
- §L1 prior-process rule (conflicts between PDF and xlsx).
- §Q1–Q4 how to handle his own flagged rows in the reference conversion (is his own data; he picks).
- §N3 `cshoc` source.

**Austin can decide (with Claude proposing):**
- §C1 event vocabulary (Claude proposes from data; Austin ratifies).
- §C2 canonical capitalization.
- §E3 anonymous naming convention.
- §F1 bidder type format.
- §B1 natural-language date table.
- §A1–A4 `BidderID` semantics.

**Deterministic already (Claude can commit):**
- ~~§R3 evidence quote column~~ — 🟩 resolved 2026-04-18. `source_page` = sec2md page number from `pages.json`; `source_quote` = verbatim substring of that page's content (NFKC-normalized), ≤ 1000 chars, single or list form. See `rules/schema.md` §R3.
- ~~§Scope-1 auction-only vs all-M&A~~ — 🟩 resolved 2026-04-18. Pipeline extracts every valid-filing-type deal and emits a deal-level `auction: bool`. An auction = ≥2 non-advisor bidder NDAs in the current (non-stale) process. Downstream filter on `auction == true`. See `rules/schema.md` §Scope-1.
- ~~§Scope-2 accepted filing types~~ — 🟩 resolved 2026-04-18. Accepted: DEFM14A, PREM14A, SC TO-T, S-4 (primary). `/A` amendments accepted when they supersede. `SC 14D9` accepted as secondary. `DEFA14A`/`425`/`8-K`/`13D`/`13G` excluded. `fetch_filings.py` already implements this. See `rules/schema.md` §Scope-2.
- ~~§Scope-3 out-of-scope fields~~ — 🟩 resolved 2026-04-18. AI excludes COMPUSTAT fields (`cshoc`, `gvkey*`), EDGAR metadata (`DateFiled`, `FormType`, `URL`, `CIK`, `accession`), and orchestration metadata (`DealNumber`, `rulebook_version`). AI produces event array + `auction` + confirmed deal-identity fields with mismatch flags. See `rules/schema.md` §Scope-3.
- ~~§G2 classification evidence~~ — 🟩 resolved 2026-04-20. Two satisfiers: true range bid (`bid_value_lower < bid_value_upper`) or ≤300-char `bid_type_inference_note`. §G1 trigger tables are extractor guidance only; the validator `pipeline._invariant_p_g2` enforces range-OR-note. See `rules/bids.md` §G2 and `rules/invariants.md` §P-G2.

When a decision requires Alex and he isn't available, leave 🟥 and note the dependency. Don't block Austin's decisions on Alex's.

---

## Exit criteria

This file is done when every row shows 🟩 RESOLVED. At that point:
- `rules/*.md` contain a complete rulebook.
- `CLAUDE.md` updates its "current status" to reflect Stage 2 start.
- Next step: convert the 9 Alex-reference deals to JSON (`scripts/build_reference.py`) and wire up `scoring/diff.py`. The diff is a human-review aid, not a grade — Austin re-reads the SEC filing for every AI-vs-Alex divergence and assigns a verdict (see `reference/alex/README.md`).

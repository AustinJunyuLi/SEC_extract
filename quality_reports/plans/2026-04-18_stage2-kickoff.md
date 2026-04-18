# Stage 2 Kickoff Plan

> Historical note: this file records the Stage 2 kickoff plan and remains
> useful as provenance, but Stage 2 is complete and Stage 3 is now live.
> For current status, prefer `AGENTS.md` / `CLAUDE.md` / `SKILL.md` plus
> `state/progress.json`.

**Status:** A + B COMPLETE · C DEFERRED INDEFINITELY · 2026-04-18
**Date:** 2026-04-18
**Owner:** Austin
**Scope:** Unblock Stage 2 — build the xlsx→JSON converter + wire the diff harness end-to-end on one deal.

---

## Goal

Stand up the reference answer-key and diff harness so that, for **Medivation**, we can run `scoring/diff.py --slug medivation` and get a meaningful human-review report the moment the pipeline extraction exists.

## Success criteria (Stage 2 exit)

1. ✅ `reference/alex/{slug}.json` exists for all 9 reference deals, conformant to `rules/schema.md` §R1, passing §A4 invariants. (commit `3241785` + `9dda10a`)
2. ✅ `scoring/diff.py --slug medivation` runs end-to-end against a placeholder/sample extraction and emits a readable markdown + JSON report. (commit `0b0d4d7`)
3. ⏸️  ~~The 25-deal lawyer-language study is kicked off (can run async).~~ **Deferred indefinitely.** Austin will revisit only if Stage 3 diff results across the 9 reference deals surface systematic §G1 informal-vs-formal confusion that the current rulebook can't resolve. If that happens, reopen as a standalone investigation rather than a Stage-2 workstream.

---

## Workstream A — Reference JSON converter

**File:** `scripts/build_reference.py` (new)

**Input:** `reference/deal_details_Alex_2026.xlsx` (sheet `deal_details`).
**Output:** `reference/alex/{slug}.json` × 9.

### Row ranges (verified against xlsx 2026-04-18)

| Slug | Rows | TargetName |
|---|---|---|
| providence-worcester | 6024–6059 | PROVIDENCE & WORCESTER RR CO |
| medivation | 6060–6075 | MEDIVATION INC |
| imprivata | 6076–6104 | IMPRIVATA INC |
| zep | 6385–6407 | ZEP INC |
| petsmart-inc | 6408–6457 | PETSMART INC |
| penford | 6461–6485 | PENFORD CORP |
| mac-gray | 6927–6960 | MAC GRAY CORP |
| saks | 6996–7020 | SAKS INC |
| stec | 7144–7171 | S T E C INC |

### Transforms applied during conversion

1. **Deal-level lift (§N1).** `TargetName`, `Acquirer`, `DateAnnounced`, `DateEffective`, `DateFiled`, `FormType`, `URL`, `Auction`, `all_cash` → `deal` object (once, not per row).
2. **Scope-3 drops.** `gvkeyT`, `gvkeyA`, `cshoc`, `DealNumber`, `_blank` col1 — discarded.
3. **Bidder canonicalization (§E3).** Group xlsx `BidderName` → deterministic `bidder_NN` per deal; preserve original as `bidder_alias`; populate `deal.bidder_registry`.
4. **Bidder type collapse (§F1).** 4 legacy booleans + `bidder_type_note` → structured `{base: "s"|"f"|"mixed", non_us: bool, public: bool}` + preserve note if informative.
5. **Comments collapse.** `comments_1|2|3` → single `comments` string.
6. **§Q1 — Saks.** Drop xlsx rows 7013, 7015. Log `applied_alex_deletion: [7013, 7015]` in conversion log.
7. **§Q2 — Zep row 6390.** Expand 1 row → 5 atomized rows. Ambiguous bids use `[20, 22]` range per rule. Each expanded row carries `alex_row_expanded` + `bid_value_ambiguous_per_alex` info flags.
8. **§Q3/§Q4 — Mac-Gray + Medivation renumber.** Sort rows by `(bid_date_precise, xlsx_row_num as §A3-rank proxy)`, reassign `BidderID = 1..N`, flag renumbered rows with `bidder_id_renumbered_from_alex`.
9. **§R3 absence.** Alex has no `source_quote` / `source_page`. Omit those keys on reference rows (the diff reporter already expects this — Alex is not evidence-cited).

### Fields Alex does NOT provide (left null/omitted on reference rows)

- Deal-level: `target_legal_counsel`, `acquirer_legal_counsel`, `go_shop_days`, `termination_fee*`.
- Event-level: `process_phase`, `role`, `exclusivity_days`, `financing_contingent`, `highly_confident_letter`, `process_conditions_note`, `cash_per_share`, `stock_per_share`, `contingent_per_share`, `consideration_components`, `aggregate_basis`, `source_quote`, `source_page`, `flags` (except the conversion-provenance flags above).

These are AI-only structured fields; their absence on the reference side is expected and the diff reporter should not penalize it.

### Rollout order inside Workstream A

1. Write script targeting Medivation only. Emit `reference/alex/medivation.json`. Spot-check by hand.
2. Extend to Imprivata + Providence (no §Q fixes) — sanity check.
3. Apply to Mac-Gray + Medivation with §Q3/§Q4 renumber.
4. Apply to Saks (§Q1 delete) + Zep (§Q2 expand).
5. Remaining: Petsmart, Penford, STec.
6. Commit all 9 JSONs in one "Build reference/alex/ answer key" commit.

## Workstream B — Wire `scoring/diff.py` end-to-end on Medivation

**File:** `scoring/diff.py` (edit existing stub)

1. Implement `normalize_bidder()` using `rules/bidders.md` §E3 convention.
2. Implement `date_bucket()` per `rules/dates.md` §B1 (exact match for precise dates; ±7d window for rough).
3. Implement `compare_field()` per-field rules in §R1 (lenient numerics with warnings, strict bid_note/bid_type mismatches surfaced prominently).
4. Implement `diff_deal()` main body: load AI + Alex JSON, join on (bidder_normalized, event_type_bucket, date_bucket), report matched/unmatched/field-disagreements.
5. Emit `scoring/results/{slug}_{ts}.json` + `.md` report skeletons.
6. Integration test: craft a synthetic `output/extractions/medivation.json` (trivial perturbation of Alex's JSON) and run `scoring/diff.py --slug medivation` to verify it produces non-empty, readable output.

Workstream B depends on Workstream A (step 1) being done.

## Workstream C — 25-deal lawyer-language study — ⏸️ DEFERRED INDEFINITELY (2026-04-18)

Separate thread; does not block A or B. Purpose: stress-test §G1 (informal-vs-formal) and §L2 (6-month phase-gap heuristic) across a broader sample.

**Deferral rationale.** The rulebook's §G1 and §L2 decisions are already ratified. Running a broader language study now is speculative work against a hypothetical rulebook gap. The empirical trigger for reopening this is **Stage 3 diff results across the 9 reference deals surfacing systematic §G1 / §L2 confusion that the manual-verification loop can't resolve row-by-row**. If that happens, reopen as a standalone investigation plan — not a Stage-2 workstream.

---

## Out of scope (explicit)

- Implementing `run.py`'s `run_pipeline()` — that's Stage 3 groundwork.
- Fetching or re-classifying filings — scripts already done.
- Cross-deal bidder canonicalization — explicit non-goal per CLAUDE.md.
- Auto-grading — the diff is a human-review aid, not a score.

---

## Checkpoint

After Workstream A step 1 (Medivation JSON), pause and show Austin the output for spot-check before proceeding with the remaining 8 deals.

# rules/invariants.md — Validator Invariants

**Purpose.** The hard checks the Python validator runs against extracted
rows. Violations become entries in `state/flags.jsonl`. Extractor output
is **not rewritten** by the validator — only annotated.

**This file was written last.** It encodes what the validator should
check, which depends on every other `rules/*.md` file. All invariants
below are traced to the rule-file decisions that produced them.

**Status legend:** 🟥 OPEN · 🟨 TENTATIVE · 🟩 RESOLVED

> Stage 1 is complete. Some historical dependency prose below still uses the
> word "pending" when describing how the rulebook was developed. Treat the
> section headers and `Decision:` blocks as authoritative; if a section is
> marked 🟩 RESOLVED, it is closed unless explicitly reopened.

---

## Severity taxonomy

- **Hard error.** Pipeline marks the deal `status: validated` with
  `flag_count > 0`. A hard flag requires human review before the deal
  counts as verified. Any hard failure on a reference deal is
  adjudicated by Austin against the filing text.
- **Soft flag.** Pipeline marks the deal `status: passed` but logs the
  flag. No human review required unless the diff report surfaces it as
  part of an AI-vs-Alex divergence.
- **Info.** Statistical anomaly only. Logged, not flagged for review.

---

## §P-R — Row-level structural invariants (🟩 RESOLVED, 2026-04-18)

All hard errors. Violations of these are extraction defects, not
judgment calls.

### §P-R1 — `events` array exists and is non-empty
- **Check.** Top-level JSON has an `events` array with at least one
  element.
- **Fail action.** Flag `empty_events_array`. Hard.
- **Why.** Every deal in scope closed (hence has a filing), so at
  minimum an `Executed` row must be present.

### §P-R2 — Every row has `source_quote` and `source_page`, verbatim in `pages.json`
- **Check.** Per `rules/schema.md` §R3:
  1. `source_quote` is a non-empty `str` OR non-empty `list[str]` paired
     with same-length `source_page`.
  2. `source_page` is a valid 1-based index into the deal's
     `data/filings/{slug}/pages.json`.
  3. After Unicode NFKC normalization, each `source_quote` element is a
     substring of `pages[source_page - 1].content`.
  4. Each `source_quote` element ≤ 1000 characters.
  5. List-length equality when both are lists.
- **Fail actions.**
  - Missing field → `missing_evidence`.
  - Quote not on cited page → `source_quote_not_in_page`.
  - Length cap exceeded → `source_quote_too_long`.
  - List-length mismatch → `source_quote_page_mismatch`.
- Severity: **hard** in all cases.

### §P-R3 — `bid_note` ∈ closed vocabulary
- **Check.** `bid_note` ∈ the ratified set from `rules/events.md` §C1,
  or is null (permitted only on bid rows per §C3).
- **Fail action.** Flag `invalid_event_type`. Hard.

### §P-R4 — `role` ∈ canonical set
- **Check.** `role` ∈ {`bidder`, `advisor_financial`, `advisor_legal`}
  per `rules/bids.md` §M3.
- **Fail action.** Flag `invalid_role`. Hard.

### §P-R5 — `bidder_name` resolves in `bidder_registry`
- **Check.** Every non-null `bidder_name` matches a key in the
  deal-level `bidder_registry` (e.g., `bidder_01`), per
  `rules/bidders.md` §E3.
- **Fail action.** Flag `bidder_name_unregistered`. Hard.
- **Why.** The canonical-ID model only works if every row's bidder
  identity can be looked up.

---

## §P-D — Date and sequencing invariants (🟩 RESOLVED, 2026-04-18)

All hard errors. Date discipline is what makes the data chronologically
comparable across deals.

### §P-D1 — `bid_date_precise` is ISO or null
- **Check.** `bid_date_precise` matches the ISO-8601 `YYYY-MM-DD` regex
  OR is null. Per `rules/dates.md` §B1/§B2.
- **Fail action.** Flag `invalid_date_format`. Hard.

### §P-D2 — `bid_date_rough` mutual exclusivity
- **Check.** `bid_date_rough != null` IFF the row carries an
  inference flag (`date_inferred_from_rough`,
  `date_inferred_from_context`, or `date_range_collapsed`). Per
  `rules/dates.md` §B2/§B3/§B4.
- **Fail action.** Flag `rough_date_mismatch_inference`. Hard.

### §P-D3 — `BidderID` structural + chronological integrity
- **Check.** All six §A4 rules:
  1. Starts at 1.
  2. Strictly monotonic.
  3. Unique per row.
  4. No gaps (`max(BidderID) == count(events)`).
  5. Monotone in `bid_date_precise` (non-null pairs only).
  6. §A3 rank-monotone within same-date blocks.
- **Fail actions.**
  - Rules 1–4 → `bidder_id_structural_error`.
  - Rule 5 → `bidder_id_date_order_violation`.
  - Rule 6 → `bidder_id_same_date_rank_violation`.
- All **hard**.
- **Escape hatch.** Rows with `bid_date_precise = null` skip rule 5 and
  must carry the `event_sequence_by_narrative` info flag.

---

## §P-S — Semantic process invariants (🟩 RESOLVED, 2026-04-18)

One soft (§P-S1), three hard. These check that the extracted event
graph tells a coherent M&A-process story.

### §P-S1 — NDA has follow-up or explicit drop (SOFT)
- **Check.** For every row with `bid_note = NDA` and `role = "bidder"`
  in `process_phase >= 1`, there exists a later row with the same
  `bidder_name` having one of: a bid (informal or formal), a dropout
  code (`DropBelowInf`, `DropAtInf`, `DropBelowFormal`, `DropAtFormal`,
  or implicit-drop), or the `Executed` row (if they won).
- **Fail action.** Flag `nda_without_bid_or_drop`. **Soft.**
- **Why soft.** Genuine cases exist where a party signs an NDA then
  silently exits filing attention; the filing doesn't always report
  that. We want the flag for review but not to block the deal.

### §P-S2 — `auction` flag matches §Scope-1 classifier
- **Check.** Deal-level `auction` field IFF
  `count(events where bid_note == "NDA" AND role == "bidder" AND process_phase >= 1) >= 2`.
  Per `rules/schema.md` §Scope-1.
- **Fail action.** Flag `auction_flag_inconsistent`. Hard.
- **Why hard.** The `auction` flag is the downstream filter. If it's
  wrong, the entire research sample is wrong.

### §P-S3 — Each `process_phase` terminates cleanly
- **Check.** For each distinct `process_phase` value in the deal, the
  chronologically last event for that phase is one of: `Executed`,
  `Terminated`, or `Auction Closed`. Per `rules/events.md` §K1/§L2.
- **Fail action.** Flag `phase_termination_missing`. Hard.
- **Why hard.** Every process phase has a real endpoint (it succeeded,
  failed, or auction closed without a winner). A phase without a
  terminator means the extractor missed the end of a phase.

### §P-S4 — Deal-level `Executed` row present
- **Check.** Exactly one row with `bid_note = Executed`, and it's in
  the highest `process_phase` value present in the deal.
- **Fail action.** Flag `no_executed_row` (if zero),
  `multiple_executed_rows` (if >1), `executed_wrong_phase` (if in a
  stale phase).
- **Why hard.** Every deal in scope closed — the filing itself is
  evidence. A missing `Executed` row is always an extraction error.

---

## §P-G — Bid classification invariants (🟩 RESOLVED, 2026-04-19, iter-6)

### §P-G2 — `bid_type` evidence requirement
- **Check.** Every row with non-null `bid_type` satisfies one of:
  (1) `source_quote` contains a §G1 trigger phrase (case-insensitive
  substring, formal OR informal table), (2) the row is a range bid
  (both `bid_value_lower` and `bid_value_upper` populated — structural
  signal per §G1), or (3) the row carries
  `bid_type_inference_note: str`.
- **Fail action.** Flag `bid_type_unsupported`. Hard.
- **Why hard.** Informal-vs-formal is the core research variable per
  `rules/bids.md` §G2. Silent classification drift across 401 deals
  would be intractable to audit retrospectively.

---

## Invariants that tie to specific rule files

| Invariant | Rule file origin |
|---|---|
| §P-R1 | `rules/schema.md` §R1 |
| §P-R2 | `rules/schema.md` §R3 |
| §P-R3 | `rules/events.md` §C1 |
| §P-R4 | `rules/bids.md` §M3 |
| §P-R5 | `rules/bidders.md` §E3 |
| §P-D1 | `rules/dates.md` §B1/§B2 |
| §P-D2 | `rules/dates.md` §B2/§B3/§B4 |
| §P-D3 | `rules/dates.md` §A4 |
| §P-G2 | `rules/bids.md` §G1/§G2 |
| §P-S1 | `rules/events.md` §I1 + `rules/bids.md` §M3 |
| §P-S2 | `rules/schema.md` §Scope-1 |
| §P-S3 | `rules/events.md` §K1/§L2 |
| §P-S4 | `rules/schema.md` §Scope-2 |

---

## Future extensions (not-yet-ratified, captured for record)

Useful additional checks identified during Stage 1 but **not** part of
the MVP validator. Revisit after the 25-deal stress-test study and
after Stage 3 has run across the 9 reference deals.

- **NDA count cross-check.** Filings often state "by <date>, X parties
  had signed confidentiality agreements." Extractor could search for
  such statements and cross-check extracted NDA count. Soft. Deferred
  because extraction of the summary statement itself is non-trivial
  and would add validator complexity.
- **Bid value plausibility.** Numeric bids should be positive and
  within a plausible window of the final executed price. Soft.
  Deferred because bidder-type differences (strategic vs financial,
  partial-acquisition) make plausibility windows non-uniform.
- **Winner named.** `Executed` row's `bidder_name` is not an anonymous
  placeholder. Hard. Deferred only because §P-R5 already catches
  unregistered names; adding a check for "name not starting with
  `Party `" is trivially addable.
- **Dates within filing window.** Every date ≤ filing date + small
  window (for go-shop coverage). Soft. Deferred because the go-shop
  window isn't always explicitly bounded in the extractor's context.
---

## What the validator does NOT do

- **Does not rewrite or correct rows.** Flag-only discipline preserves
  the extractor's output as the single source of what was extracted.
  Corrections happen in Stage 3 by updating the rulebook/prompts, not
  by post-hoc patches.
- **Does not fetch external data** (EDGAR, COMPUSTAT, etc.). All
  cross-checks use the text already provided in the extractor's
  context.
- **Does not re-extract** — only cross-checks existing rows' citations
  against `pages.json`.
- **Does not produce diff reports.** Diffing against `reference/alex/`
  is `scoring/diff.py`'s job, run post-pipeline on reference deals
  only. The diff is a human-review aid, not a pass/fail grade.
- **Does not decide verdicts on disagreements.** Austin reads the
  filing and adjudicates each AI-vs-Alex divergence. See
  `CLAUDE.md` §Ground-truth epistemology.

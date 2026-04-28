# rules/invariants.md — Validator Invariants

**Purpose.** The hard checks the Python validator runs against extracted
rows. Violations become entries in `state/flags.jsonl`. Extractor output
is **not rewritten** by the validator — only annotated.

**This file was written last.** It encodes what the validator should
check, which depends on every other `rules/*.md` file. All invariants
below are traced to the rule-file decisions that produced them.

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

### §P-R0 — Row shape: events are dicts, process_phase is int>=0 or null

- **Check.** Every entry in `events[]` is a dict. When `process_phase` is
  present on a row, it is `int >= 0` or `null`. When `bidder_name` /
  `bidder_alias` are present, they are strings or `null`.
- **Fail action.** Flags `event_not_a_dict`, `process_phase_invalid_type`,
  or `bidder_identity_invalid_type` (all hard).
- **Why hard.** Without this check a single weird extractor row (a string
  where a dict is expected; `process_phase: "1"` instead of `1`) crashes
  the validator with an unhandled `AttributeError` / `TypeError`. At
  392-deal scale that gets masked behind `mark_failed` and the underlying
  shape bug stays silent. §P-R0 turns it into an explicit hard flag and
  lets the rest of the deal's rows still get validated.

Unless a subsection states otherwise, row-level structural violations are hard
errors.

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
  3. After Unicode NFKC normalization and curly-quote folding (per
     `pipeline._canonicalize_pdf_artifacts`), each `source_quote`
     element is a substring of `pages[source_page - 1].content`.
  4. Each `source_quote` element must be ≤1500 characters.
  5. List-length equality when both are lists.
- **Fail actions.**
  - Missing field → `missing_evidence`.
  - Quote not on cited page → `source_quote_not_in_page`.
  - 1500-character hard cap exceeded → `source_quote_too_long`.
  - List-length mismatch → `source_quote_page_mismatch`.
- Severity: missing, page mismatch, non-substring, and >1500 chars are
  **hard**. Legitimate one-paragraph multi-event anchors are allowed up to
  1500 characters.

### §P-R3 — `bid_note` ∈ closed vocabulary
- **Check.** `bid_note` ∈ the ratified set from `rules/events.md` §C1,
  with no null exception. Bid rows use the literal value `"Bid"` per §C3.
- **Fail action.**
  - Null value → `bid_note_null`. Hard.
  - Unknown vocabulary value → `invalid_event_type`. Hard.

### §P-R4 — `role` ∈ canonical set
- **Check.** `role` ∈ {`bidder`, `advisor_financial`, `advisor_legal`}
  per `rules/bids.md` §M3.
- **Fail action.** Flag `invalid_role`. Hard.

### §P-R5 — `bidder_registry` keys, aliases, and resolved names align
- **Check.**
  1. Every non-null `bidder_name` matches a key in the deal-level
     `bidder_registry` (e.g., `bidder_01`), per `rules/bidders.md` §E3.
  2. If a row carries `bidder_alias`, that alias appears in
     `bidder_registry[bidder_name].aliases_observed`.
  3. If a registry entry carries `resolved_name`, that string also
     appears in `aliases_observed`.
- **Fail actions.**
  - Missing registry key → `bidder_not_in_registry`. Hard.
  - Row alias absent from `aliases_observed` → `bidder_alias_not_observed`. Hard.
  - `resolved_name` absent from `aliases_observed` → `resolved_name_not_observed`. Soft.
- **Why.** The canonical-ID model only works if every row's bidder
  identity can be looked up.

### §P-R6 — `bidder_type` scalar value constraint
- **Check.** For every event row where `bidder_type` is present (not absent /
  not `null`), `bidder_type` must be a scalar string in `{"s", "f"}`.
  Any other type or any unknown string value fails.
- **Fail action.** Flag `bidder_type_invalid_value`. Hard.
- **Why hard.** The 2026-04-27 schema flatten made `bidder_type` a scalar.
  A nested object or an out-of-set value breaks downstream analysis.
  `null` is the correct representation of "no bidder type recorded".

### §P-R7 — CA ambiguity is hard
- **Check.** Any row carrying a `ca_type_ambiguous` flag must carry it at
  hard severity.
- **Fail action.** Flag `ca_type_ambiguous`. Hard.
- **Why hard.** Ambiguous CA type changes whether a row is an auction-funnel
  NDA, a bidder-side consortium CA, or a skipped rollover side agreement.
  Production runs showed soft flags were too easy to ignore.

### §P-R8 — Extractor-emitted flag objects conform to §R2 shape

- **Check.** Every flag object on `events[i].flags` and on
  `deal.deal_flags` must be a dict with: non-empty string `code`,
  `severity ∈ {"hard", "soft", "info"}`, and a string `reason`.
- **Fail action.** Flag `flag_shape_invalid`. Hard.
- **Why hard.** Without this check, a typo like `severity: "Hard"` (capital
  H) or `"warn"` is silently demoted to `"hard"` by `count_flags`, pinning
  the deal to `validated` for a typo. The 3-consecutive-clean-runs gate
  would never close. Cite the offending row index in the `reason`.

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
- **Escape hatch.** Rows with `bid_date_precise = null` skip rule 5.
  Such rows are placed by filing narrative order per `rules/dates.md`
  §A2.

### §P-D5 — Drop rows require prior engagement in the same phase
- **Check.** For every row with `bid_note == "Drop"` (not `DropSilent`),
  with non-null `bidder_name` and `process_phase >= 1`, there exists at
  least one other row in the same `process_phase` with the same
  `bidder_name` and `bid_note ∈ {NDA, Bidder Interest, IB,
  Drop}`. Position within phase is not enforced — §A2/§A3 canonicalization
  has already ordered rows. The prior Drop branch covers §I2 re-engagement
  cases where a bidder re-enters after an earlier drop.
- **Fail action.** Flag `drop_without_prior_engagement`. Hard.
- **Why hard.** A drop row without prior engagement means the extractor
  invented a dropout or missed the engagement row that named the
  bidder. §P-D5 is the structural twin of §P-D6 on the tail-end of the
  NDA lifecycle: §P-D6 asserts "every Bid has a prior NDA", §P-D5
  asserts "every Drop has a prior engagement".
- **Exemptions (row is skipped, no flag emitted).**
  1. `bidder_name` is null — unnamed placeholders are count-bound.
  2. `process_phase = 0` — §M4 stale-prior phase 0 rows do not require
     an in-phase prior engagement.
  3. Any row for the same `(bidder_name, process_phase)` carries the
     `unsolicited_first_contact` info flag (§D1.a). An unsolicited
     first-contact bidder approaches, submits a concrete price
     indication, and withdraws without ever signing an NDA — the
     drop row is the withdrawal itself, so requiring a prior
     engagement would defeat the §D1.a exemption. Mirrors §P-D6
     exemption #3.
- **References.** `rules/events.md` §I1 (drop vocabulary), §I2
  (re-engagement), §D1 (engagement vocabulary), §D1.a
  (unsolicited-first-contact exemption).

### §P-D7 — Drop reason matrix
- **Check.** Every `Drop` row obeys the §I1 matrix:
  `drop_initiator = "target"` requires a non-null target-side reason class;
  `drop_initiator = "bidder"` permits only `null`, `"no_response"`, or
  `"scope_mismatch"`; `drop_initiator = "unknown"` requires
  `drop_reason_class = null`.
- **Fail action.** Flag `drop_reason_class_inconsistent`. Soft.

### §P-D8 — Formal-stage status consistency
- **Check.**
  1. `submitted_formal_bid = true` on an informal `Bid` requires a formal
     `Bid` row for the same bidder and phase.
  2. `submitted_formal_bid = false` on an informal `Bid` must not coexist
     with a formal `Bid` row for the same bidder and phase.
  3. A `Drop` row with `drop_reason_class = "never_advanced"` requires
     `invited_to_formal_round = false`.
- **Fail action.** Flag `formal_round_status_inconsistent`. Soft.
- **Extractor guidance.** This is a consistency check, not a mandate to
  infer unsupported true/false values. If the filing reaches a formal
  process but bidder-specific advancement or submission status is unclear,
  leave the field null and attach a soft `formal_round_status_inferred`
  flag.

### §P-D6 — Named-Bid rows require an in-phase NDA for the same bidder
- **Check.** For every row with `bid_note = "Bid"`, non-null
  `bidder_name`, and `process_phase >= 1`, there exists at least one
  row with `bid_note = "NDA"`, the same `bidder_name`, and the same
  `process_phase`. Existence-only — not ordering.
- **Fail action.** Flag `bid_without_preceding_nda`. Hard.
- **Why hard.** Closes the retroactive-naming gap where an AI emits
  unnamed §E3 NDA placeholders (e.g., Providence Party D/E/F) that
  are never linked to named Bid rows. Silent NDA-registry breakage
  would corrupt §Scope-1 auction classification and the §P-S NDA→drop
  story downstream.
- **Exemptions (row is skipped, no flag emitted).**
  1. `bidder_name` is null — unnamed §E3 placeholders are count-bound,
     not NDA-bound.
  2. `process_phase = 0` — §M4 stale-prior phase 0 rows do not require
     an in-phase NDA.
  3. Row carries the `unsolicited_first_contact` info flag (§D1.a).
     This is the ONLY judgment-call exemption and is reserved for
     bidders who approach unsolicited and never sign an NDA (target
     declines or bidder withdraws). The flag's `reason` must contain a
     ≤120-char verbatim snippet showing that language.
  4. `pre_nda_informal_bid` (§C4) does **NOT** exempt. §C4 requires the
     bidder to sign an NDA later in the same phase, so §P-D6's
     existence check is satisfied naturally by that later NDA row.
- **Remediation path for unnamed-NDA cases.** When the filing later
  names a bidder whose NDA was emitted as an unnamed §E3 placeholder,
  the extractor attaches an `unnamed_nda_promotion` hint on the named
  Bid row. `pipeline._apply_unnamed_nda_promotions` applies the hint
  before §P-D6 runs, rewriting the placeholder NDA's `bidder_name` to
  the promoted value. Successful promotions satisfy §P-D6
  automatically; failed promotions leave the hint in place and §P-D6
  fires hard.

---

## §P-S — Semantic process invariants (🟩 RESOLVED, 2026-04-18)

These checks ensure the extracted event graph tells a coherent M&A-process
story; severities are listed per invariant.

### §P-S1 — NDA-only signer must have DropSilent (SOFT)
- **Check.** For every row with `bid_note = NDA` and `role = "bidder"`
  in `process_phase >= 1`, there exists a later row with the same
  `bidder_name` having one of: a bid (informal or formal), any dropout
  code (including `DropSilent`), or the `Executed` row (if they won).
  Per `rules/events.md` §I1, silent NDA signers are represented by an
  emitted `DropSilent` row immediately following their NDA.
- **Fail action.** Flag `missing_nda_dropsilent`. **Soft.**
- **Why soft.** Safety net for extractor failure to emit the required
  `DropSilent` row. The §I1 contract is "silent NDA → emit DropSilent";
  this invariant fires only when the extractor missed that emission.
  Soft severity allows the orchestrator to surface the miss for review
  without blocking the deal. In a healthy run, this flag count is zero
  across the entire reference set.

### §P-S2 — `auction` flag matches §Scope-1 classifier
- **Check.** Deal-level `auction` field IFF
  `count(events where bid_note == "NDA" AND role == "bidder" AND process_phase >= 1) >= 2`.
  Per `rules/schema.md` §Scope-1.
- **Fail action.** Flag `auction_flag_inconsistent`. Hard.
- **Why hard.** The `auction` flag is the downstream filter. If it's
  wrong, the entire research sample is wrong.

### §P-S3 — Each `process_phase` terminates cleanly
- **Check.** For each distinct `process_phase` value in the deal, the
  phase contains at least one event with `bid_note ∈ {Executed,
  Terminated, Auction Closed}`. Position within the phase is not
  enforced — go-shop trailing activity and §A3 rank inversions can place
  terminators mid-phase. Per `rules/events.md` §K1/§L2.
- **Exemption.** `process_phase = 0` (§M4 stale-prior) is skipped. Prior
  abandoned processes are narrated for context and separated from the
  current process by the §P-L2 ≥180-day gap; forcing them to carry an
  in-scope terminator penalized deals whose filings summarized the
  prior without re-narrating its close.
- **Fail action.** Flag `phase_termination_missing`. Hard.
- **Why hard.** Every active process phase has a real endpoint (it
  succeeded, failed, or auction closed without a winner). A phase≥1
  without a terminator means the extractor missed the end of a phase.

### §P-S4 — Deal-level `Executed` row present
- **Check.** At least one row with `bid_note = Executed`, and every
  `Executed` row is in the highest `process_phase` value present in the
  deal. Multiple `Executed` rows are allowed when a consortium winner is
  atomized per §E1 / §E2.b.
- **Fail action.** Flag `no_executed_row` (if zero),
  `executed_wrong_phase` (if any Executed row is in a stale phase).
- **Why hard.** Every deal in scope closed — the filing itself is
  evidence. A missing `Executed` row is always an extraction error.

---

## §P-L — Phase-boundary invariants (🟩 RESOLVED, 2026-04-20)

### §P-L1 — `process_phase = 2` requires an explicit restart boundary
- **Check.** If any event has `process_phase = 2`, then phase 1 contains
  a `Terminated` row and phase 2 contains a `Restarted` row.
- **Fail action.** Flag `orphan_phase_2`. Hard.
- **Why hard.** A restart phase without the narrated closure/restart pair
  means either the extractor assigned `process_phase` incorrectly or the
  phase markers were missed.

### §P-L2 — Stale prior phase must be at least 180 calendar days before main process
- **Check.** If the deal contains any `process_phase = 0` rows and any
  `process_phase >= 1` rows with precise dates, then the latest phase-0
  date is at least 180 days before the earliest phase≥1 date.
- **Fail action.** Flag `stale_prior_too_recent`. Hard.
- **Why hard.** Phase 0 is reserved for stale prior attempts. If the
  closest stale-prior date is too near the main process, the extractor
  likely split one process into two phases incorrectly.

---

## §P-H — Bid-revision chronology invariants (🟩 RESOLVED, 2026-04-20)

### §P-H5 — Multiple bids by the same bidder are chronologically ordered
- **Check.** For any bidder with more than one `Bid` row carrying
  `bid_date_precise`, those dates appear in chronological order.
- **Fail action.** Flag `bid_revision_out_of_order`. Soft.
- **Why soft.** Out-of-order revisions usually indicate extraction or
  phase assignment drift, but they do not necessarily invalidate the row
  if the filing narration itself is compressed or retrospective.

---

## §P-G — Bid classification invariants (🟩 RESOLVED, 2026-04-19)

### §P-G2 — `bid_type` evidence requirement
- **Check.** Every row with non-null `bid_type` satisfies one of:
  (1) the row is a true range bid — both `bid_value_lower` and
  `bid_value_upper` populated, numeric, and `bid_value_lower <
  bid_value_upper` (§G1 informal structural signal), or (2) the row
  carries a non-empty `bid_type_inference_note: str` of ≤300 chars
  justifying the classification, or (3) a paired/fallback `Final Round`
  row in the same phase supplies `final_round_informal` consistent with
  the bid's `bid_type`. §G1 trigger tables are *classification guidance
  for the extractor*, NOT a validator satisfier path: a trigger phrase
  alone does not pass §P-G2.
  
  **Additional hard requirement (per 2026-04-27 directive).** When (1)
  is true (the row is a true range bid), `bid_type` MUST equal
  `"informal"`. Otherwise emit hard `bid_range_must_be_informal`.
- **Fail action.** Flag `bid_type_unsupported` (no range, no note, no
  matching paired/fallback final-round classification).
  Inverted ranges (`lower >= upper`) flag `bid_range_inverted`. Range
  with `bid_type != "informal"` flags `bid_range_must_be_informal`.
  All hard.
- **Why hard.** Informal-vs-formal is the core research variable per
  `rules/bids.md` §G2. At 392-deal scale, requiring an explicit note
  on every non-range row keeps classification auditable and avoids
  brittle dependence on a closed phrase list.
- **Why note, not trigger list.** Empirical 9-deal analysis
  (2026-04-20): of 92 rows with non-null `bid_type`, only 30% contained
  a §G1 trigger phrase; 29% were range bids; 55% relied on
  `bid_type_inference_note`. Providence (22 bids) and Penford (8 bids)
  had 0% trigger coverage. The trigger-list satisfier was overfit to
  the reference sample and forced inference-note duplication on rows
  that already cited filing language.

### §P-G3 — Final-round announcement needs submission/deadline pair
- **Check.** A `Final Round` row with `final_round_announcement = true`
  followed by one or more `Bid` rows in the same `process_phase` must have a
  paired non-announcement `Final Round` row for those bids. The paired
  non-announcement row may appear immediately before or after the same-day
  `Bid` row when both cite the same narrative passage; the invariant is about
  missing submission/deadline evidence, not row-order formalism.
- **Fail action.** Flag `final_round_missing_non_announcement_pair`. Hard.

---

## Invariants that tie to specific rule files

| Invariant | Rule file origin |
|---|---|
| §P-R1 | `rules/schema.md` §R1 |
| §P-R2 | `rules/schema.md` §R3 |
| §P-R3 | `rules/events.md` §C1 |
| §P-R4 | `rules/bids.md` §M3 |
| §P-R5 | `rules/bidders.md` §E3 |
| §P-R6 | `rules/bidders.md` §F1 |
| §P-R7 | `rules/events.md` §I3 |
| §P-R8 | `rules/schema.md` §R2 |
| §P-D1 | `rules/dates.md` §B1/§B2 |
| §P-D2 | `rules/dates.md` §B2/§B3/§B4 |
| §P-D3 | `rules/dates.md` §A4 |
| §P-D5 | `rules/events.md` §I1 + §I2 + §D1 |
| §P-D6 | `rules/events.md` §D1.a + `rules/bids.md` §C4 + `rules/bidders.md` §E3 |
| §P-D7 | `rules/events.md` §I1 |
| §P-D8 | `rules/events.md` §I1 + `rules/schema.md` §R1 |
| §P-H5 | `rules/bids.md` §H5 |
| §P-L1 | `rules/events.md` §L2 |
| §P-L2 | `rules/events.md` §L2 |
| §P-G2 | `rules/bids.md` §G1/§G2 |
| §P-G3 | `rules/events.md` §K1 |
| §P-S1 | `rules/events.md` §I1 + `rules/bids.md` §M3 |
| §P-S2 | `rules/schema.md` §Scope-1 |
| §P-S3 | `rules/events.md` §K1/§L2 + `rules/bids.md` §M4 |
| §P-S4 | `rules/schema.md` §Scope-2 |

---

## What the validator does NOT do

- **Does not rewrite or correct rows.** Flag-only discipline preserves
  the extractor's output as the single source of what was extracted.
  Corrections happen by updating the rulebook/prompts, not
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
  `AGENTS.md` §Source of Truth.

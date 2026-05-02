# rules/dates.md — Dates and Event Sequencing

**Purpose.** Rules for mapping natural-language dates to calendar dates, handling undated events, and assigning `BidderID` event-sequence numbers.

---

## Resolved rules

### §B1 — Natural-language date mapping

**Decision.** Deterministic mapping table. The extractor MUST apply this
table mechanically, not creatively. Mapped dates populate `bid_date_precise`;
the original phrase goes verbatim into `bid_date_rough`.

**Mapping table** (Northern Hemisphere calendar).

| Phrase shape | Maps to (day of the stated year/month) |
|---|---|
| `early <Month> <Year>` | `<Year>-<Month>-05` |
| `mid-<Month> <Year>` | `<Year>-<Month>-15` |
| `late <Month> <Year>` | `<Year>-<Month>-25` |
| `first week of <Month> <Year>` | `<Year>-<Month>-05` |
| `last week of <Month> <Year>` | `<Year>-<Month>-26` |
| `first half of <Month> <Year>` | `<Year>-<Month>-08` |
| `second half of <Month> <Year>` | `<Year>-<Month>-22` |
| `<Month> <Year>` (month only) | `<Year>-<Month>-15` |
| `Q1 <Year>` | `<Year>-02-15` |
| `Q2 <Year>` | `<Year>-05-15` |
| `Q3 <Year>` | `<Year>-08-15` |
| `Q4 <Year>` | `<Year>-11-15` |
| `early Q<n> <Year>` | first month of quarter, day 15 |
| `mid-Q<n> <Year>` | middle month of quarter, day 15 |
| `late Q<n> <Year>` | last month of quarter, day 15 |
| `early <Year>` | `<Year>-02-15` |
| `mid-<Year>` / `middle of <Year>` | `<Year>-07-01` |
| `late <Year>` | `<Year>-11-15` |
| `<Year>` (year only) | `<Year>-07-01` |
| `Spring <Year>` | `<Year>-04-15` |
| `Summer <Year>` | `<Year>-07-15` |
| `Fall <Year>` / `Autumn <Year>` | `<Year>-10-15` |
| `Winter <Year1>-<Year2>` | `<Year2>-01-15` |

**Anchored / relative phrases** (handled under §B3 for undated/context-dependent
events):
- "shortly thereafter" / "shortly after" — anchor + 7 days.
- "in the following weeks" — anchor + 21 days.
- "the next few weeks" — anchor + 21 days.
- "within N days" — anchor + N days.
- "over the next month" — anchor + 30 days.
- "approximately/about/around N weeks later" — anchor + 7*N days.
- "approximately/about/around N months later" — anchor + 30*N days.

bare sequencing words such as "subsequently", "thereafter", "later", and
"then" are ordering cues, not date phrases. Do not copy them into
`bid_date_rough`, and do not attach `date_phrase_unmapped` for them. If the
filing gives no mapped date phrase or anchored offset beyond the bare
sequencing word, leave `bid_date_precise = null`, leave `bid_date_rough =
null`, and attach `date_unknown` under §B3 while relying on `BidderID` order.

Process-window phrases such as "during the go shop process" are also not
standalone rough dates. If the row cites a complete bounded range, apply §B4
to that range. If the row only states that the event occurred sometime during
a named process window, leave `bid_date_precise = null`, leave
`bid_date_rough = null`, and attach `date_unknown`; do not copy the process
window label into `bid_date_rough` and do not attach `date_phrase_unmapped`.

**Flag on every inferred date.**
`{"code": "date_inferred_from_rough", "severity": "info",
"reason": "phrase: '<verbatim phrase>'"}`.

**Why deterministic, not creative.** Reproducibility. Two extractor runs
on the same filing must produce the same dates. Alex's own workbook shows
the cost of creative mapping — row 6033's comment says *"what should be
the appropriate date? July 1?"* for "Early July 2016." Under this rule,
`"Early July 2016"` always maps to `2016-07-05`.

**Rejected alternatives.**
- **First day of the stated window** — biases early; loses information
  about "mid" vs "late" distinctions.
- **Store only the verbatim phrase** — makes chronological sort
  impossible; kills validator's monotone-date check.

**Cross-references.**
- `rules/dates.md` §B2 (when to populate rough vs precise).
- `rules/dates.md` §B3 (anchored / undated events).

---

### §B2 — Precise vs rough date population

**Decision.** Mutually exclusive population:
- Filing states an **explicit calendar date** (ISO-resolvable):
  - `bid_date_precise` = that date.
  - `bid_date_rough` = **null**.
- Filing states a **rough / natural-language phrase**:
  - `bid_date_precise` = inferred per §B1 mapping.
  - `bid_date_rough` = verbatim phrase (e.g., `"mid-July 2016"`).
  - Flag `date_inferred_from_rough` (info).

**Invariant.** `bid_date_rough != null` IFF the date was inferred.
Enforced by validator (`rules/invariants.md`).

**Why not populate both when precise.** Clean semantic: `bid_date_rough`
is a signal that the precise date is inferred, not measured. Populating
both would require downstream code to check "is this rough string a real
phrase or just a copy of the precise date" — adding complexity with no
gain.

**Rejected alternatives.**
- **Always populate rough with filing phrasing** — duplicates data; loses
  the "inferred-ness" signal.
- **Single `event_date` + boolean `date_is_approximate`** — functionally
  equivalent but creates an unnecessary translation layer for the workbook
  comparison workflow.

**Cross-references.**
- `rules/dates.md` §B1 (inference rules).
- `rules/dates.md` §B3 (undated events).
- `rules/invariants.md` §P-D2 (`rough_date_mismatch_inference`).

---

### §B3 — Undated events

**Decision.** Hybrid rule based on temporal anchor language:
- **Process-relative language present** (e.g., "shortly thereafter,"
  "in the following weeks," "within 10 days"):
  - Compute inferred date from anchor + offset per §B1's
    anchored/relative table.
  - Populate `bid_date_precise` (inferred).
  - Populate `bid_date_rough` with the anchor phrase.
  - Flag `date_inferred_from_context` (soft).
- **No temporal anchor** (e.g., "The Company also received a letter from
  Party D"):
  - Leave `bid_date_precise` = null, `bid_date_rough` = null.
  - Flag `date_unknown` (soft — not hard, because `BidderID` still
    provides in-section ordering).

**Anchor definition.** The anchor is the `bid_date_precise` of the
immediately preceding chronological event row (or the narratively
preceding event if no chronological predecessor exists).

**Why `date_unknown` is soft, not hard.** Some filings simply don't date
certain events. Making this hard would force a fabricated date (violating
source-quote discipline) or a skipped row (losing information). The
`BidderID` sequence per §A preserves narrative order.

**Rejected alternatives.**
- **Infer from bracketing events (midpoint of prev and next)** — creates
  phantom precision; the filing didn't say that.
- **Skip undated events entirely** — loses signals like "the Company also
  received a letter from Party D" which IS a bidder-interest event even
  without a date.
- **Hard-flag `date_unknown`** — would block the entire deal from passing
  validation just because a few rows have missing dates; too brittle.

**Cross-references.**
- `rules/dates.md` §B1 (anchor offset table).
- `rules/dates.md` §A (BidderID as ordering fallback).

---

### §B4 — Date-range events

**Decision.** Single event at the **range midpoint**. Populate
`bid_date_rough` with the verbatim range phrase. Flag
`date_range_collapsed` (info).

**Algorithm.**
1. Extract the start and end dates of the range.
2. `bid_date_precise` = midpoint, rounded down to the nearest day.
3. `bid_date_rough` = verbatim range phrase from filing (e.g., "Between
   July 15 and July 22, 2016").
4. Flag `{"code": "date_range_collapsed", "severity": "info",
   "reason": "phrase: '<verbatim>'; midpoint: <YYYY-MM-DD>"}`.

**Examples.**
- "Between July 15 and July 22, 2016" → `bid_date_precise: 2016-07-18`,
  `bid_date_rough: "Between July 15 and July 22, 2016"`.
- "During the week of August 1–5, 2016" → `bid_date_precise: 2016-08-03`,
  `bid_date_rough: "During the week of August 1–5, 2016"`.
- "July 15–July 22, 2016" → `bid_date_precise: 2016-07-18`.

**Why collapse to midpoint, not emit two rows.** The row-per-event model
(§E1) doesn't natively support duration. Most "range" language in M&A
filings is imprecise dating rather than signal about duration
("due-diligence was performed between X and Y" is ONE due-diligence
event, not two). Midpoint + verbatim phrase + flag preserves the signal
without schema churn.

**Rejected alternatives.**
- **Two rows (range start + range end)** — doubles rows for imprecise
  dating; no downstream consumer currently uses duration.
- **Populate start date only** — biases early; loses the range
  information entirely.
- **Hybrid (start/end for due-diligence and exclusivity only)** —
  requires extending event vocabulary; premature complexity.

**Cross-references.**
- `rules/dates.md` §B1 (natural-language mapping).
- `rules/dates.md` §B2 (rough vs precise population rules).
- `rules/bidders.md` §E1 (row-per-event model).

---

### §B5 — Communication-date directionality

**Rule.** When a filing narrates a communication with both an authored
date ("letter dated May 10, 2016") and a receipt date ("received on
May 12, 2016"), the row's `bid_date_precise` anchors on:

- The **receipt** date for **incoming** communications to the target
  (bidder's letter to the target's board, IOIs, LOIs, non-binding
  indications, etc.).
- The **sent** date for **outgoing** communications from the target
  (process letters, requests for revised bids, formal invitations).

**Rationale.** The event being recorded is what the target learned
(for incoming) or did (for outgoing), not the bidder's internal
drafting timeline. Incoming-receipt anchoring reflects the target's
informational state; outgoing-sent anchoring reflects the target's
action.

**Implementation.** Enforced by the extractor per `prompts/extract.md`
step 6. No deterministic `_invariant_p_b5` in `pipeline/core.py` —
directionality is a per-row semantic judgment the validator cannot
re-derive from the JSON alone.

**Cross-references.**
- `rules/dates.md` §B2 (precise vs rough population).
- `prompts/extract.md` step 6 (extractor-side enforcement).

---

## Event sequencing (§A — `BidderID`) — Resolved rules

### §A1 — Keep `BidderID`

**Decision.** Keep the column name `BidderID` for Alex-workbook comparison,
but **define the current semantics**:
- Strict integer sequence `1..N` per deal.
- Monotone in the ordering chosen by §A2/§A3.
- **No decimals.** The decimal-wedge convention (`0.3`, `1.5`) in
  Alex's workbook is a relic of hand-editing; the AI is building fresh
  rows, not patching Alex's.

**Why keep the name.** Downstream joins between our JSON and Alex's
workbook key on `BidderID`. Renaming would require a translation layer.
The name is a misnomer (it's a sequence number, not a bidder
identifier), but canonical bidder identity already lives in
`bidder_name` (canonical `bidder_NN` per §E3) and `bidder_alias`
(per-row filing label). So there's no semantic confusion with
bidder-identity fields.

**Why no decimals.** Decimals encoded "I'm inserting a row between
Chicago rows 3 and 4." The AI doesn't operate on Chicago rows; it emits
a fresh, complete sequence. A clean `1..N` is simpler for downstream
code and removes a source of sort ambiguity.

**Rejected alternatives.**
- **Drop entirely** — removes a cheap per-deal ordinal key.
- **Keep + replicate decimal-wedge logic** — maximum confusion; we're
  building fresh data, not patching.
- **Rename to `event_seq`** — semantically cleaner but adds translation
  friction for the comparison workflow.

**Cross-references.**
- `rules/dates.md` §A2 (what determines the ordering).
- `rules/dates.md` §A3 (same-date tie-break).
- `rules/dates.md` §A4 (invariants).
- `rules/bidders.md` §E3 (canonical bidder IDs, separate from `BidderID`).

---

### §A2 — Strict monotonicity in date

**Decision.** `BidderID` is **strictly monotone in `bid_date_precise`**,
with same-date ties broken by §A3 (logical/semantic order, then filing
narrative order).

**Algorithm for assignment.**
1. Sort events by `bid_date_precise` (ascending). For undated events
   (null `bid_date_precise`), use the anchor date per §B3 — they inherit
   the anchor's slot.
2. Within a same-date block, apply §A3's logical ordering.
3. Assign `BidderID = 1..N` in the resulting order.

**Rule for undated events with null anchor.** If an event has
`date_unknown` (per §B3) AND no anchor (can't be placed chronologically),
insert it at the position implied by filing narrative order relative to
its surrounding rows. Flag `event_sequence_by_narrative` (info) on the
row.

**Why chronology-first.** The research question is about auction process
dynamics over time (who bid when, did bids revise, how did dropouts
cluster). Chronological ordering is the natural primary key for that
analysis. Filings are mostly chronological anyway; the rare
narrative-first moments (recapping earlier events when introducing a
new counterparty) are narrative devices, not timeline events.

**Validator enforcement** (per §A4 / invariants).
- Hard error if `BidderID[i+1] < BidderID[i]`.
- Hard error if `date[i+1] < date[i]` but `BidderID[i+1] > BidderID[i]`
  (strictly: if both have non-null dates and no §A3 tie-break applies).

**Rejected alternatives.**
- **Follows filing narrative order** — sometimes filings group all NDAs
  for party X, then all bids for party X, then move to party Y; this
  breaks cross-party temporal comparisons.
- **Monotone only within bidder** — loses cross-bidder ordering that's
  central to the research.

**Cross-references.**
- `rules/dates.md` §A3 (same-date tie-break).
- `rules/dates.md` §B3 (undated event anchoring).
- `rules/invariants.md` (validator checks).

---

### §A3 — Same-date tie-break

**Decision.** Within a same-date block, apply **logical/semantic
ordering** first, then filing narrative order as secondary tie-break.

**Logical ordering table** (lower rank = earlier).

| Rank | Event class | Event codes |
|---|---|---|
| 1 | Process announcements | `Press Release`, `Target Sale Public`, `Final Round` with `final_round_announcement = true`, `Bidder Sale`, `Activist Sale` |
| 2 | Process start/restart | `Target Sale`, `Terminated`, `Restarted` |
| 3 | Advisor/IB changes | `IB`, `IB Terminated` |
| 4 | Bidder first-contact | `Bidder Interest` |
| 5 | NDA executions | `NDA` |
| 6 | Informal bids | `Bid` **with** `bid_type = "informal"` (per §C3) |
| 7 | Formal bids | `Bid` **with** `bid_type = "formal"` (per §C3) |
| 8 | Dropouts (mid-round) | `Drop`, `DropSilent` |
| 9 | Final-round deadlines | `Final Round` with `final_round_announcement = false`, `Auction Closed` |
| 10 | Post-deadline activity | Late bids after `Final Round`, winner confirmation |
| 11 | Signing | `Executed` |

**Bid row rank disambiguation.** All bid rows carry
`bid_note = "Bid"` per `rules/events.md` §C1/§C3. Within a same-date
cluster, bid rows are ranked 6 or 7 based on `bid_type`:

- `bid_type = "informal"` → rank 6
- `bid_type = "formal"` → rank 7
- `bid_type = null` (ambiguous per `rules/bids.md` §G1) → rank 6 (conservative)

The validator (`pipeline.core._rank()`) implements the `bid_type` lookup.

**Final-round row rank disambiguation.** `Final Round` announcement rows
rank 1; non-announcement deadline/submission rows rank 9. The validator
uses `final_round_announcement` to choose between those ranks.

**Within-rank tie-break.** Filing narrative order (top-to-bottom as
events appear in the Background section).

**Same-date count clusters.** When multiple rows share the same date and
rank, emit them in filing narrative order. `BidderID` increments one per
event row across the cluster.

**Same-date final-round submissions.** If a filing narrates multiple bids and
a non-announcement `Final Round` milestone on the same date, the bid rows
(rank 6 or 7) sort before the non-announcement `Final Round` row (rank 9);
within the bid cluster, preserve filing narrative order. Validator pairing
therefore searches same-phase, same-date final-round milestones even when the
canonical row order places the milestone after the bid.

**Why logical ordering.** Reflects actual process flow: announcements
precede the NDAs they trigger; NDAs precede the bids they enable; bids
precede the drops they induce. Makes the extracted data interpretable
chronologically even at sub-day resolution.

**Rejected alternatives.**
- **Filing narrative order only** — filings often group by party
  (all Party A rows, then all Party B rows), which breaks cross-party
  temporal comparison within a same-date block.
- **Alphabetical by bidder** — deterministic but semantically
  meaningless; arbitrary reordering of process events.

**Cross-references.**
- `rules/events.md` §C1 (closed event vocabulary).
- `rules/dates.md` §A2 (primary chronological ordering).

---

### §A4 — `BidderID` consistency invariants

**Decision.** Adopt all six invariants as **hard** validator checks, with
one narrow escape hatch for truly undated rows.

**Hard invariants (validator fails on violation).**
1. `BidderID` starts at 1 for every deal.
2. `BidderID` is monotonically increasing across rows (strict, no
   duplicates, no decreases).
3. `BidderID` is unique per row within a deal.
4. No gaps: `max(BidderID) == count(events)`.
5. **Monotone in date**: if row[i] and row[i+1] both have non-null
   `bid_date_precise`, then `date[i] <= date[i+1]`.
6. **Same-date §A3 compliance**: if `date[i] == date[i+1]`, the §A3
   logical rank of row[i] must be ≤ rank of row[i+1].

**Escape hatch for undated rows.** If a row has `bid_date_precise = null`
(per §B3 — no anchor, truly undated), the date-monotonicity check
(rule 5) skips that row. The row is placed via filing narrative order
per §A2 and carries the `event_sequence_by_narrative` info flag.

**Fail actions.**
- Rules 1–4 violated → flag `bidder_id_structural_error`, hard.
- Rule 5 violated → flag `bidder_id_date_order_violation`, hard.
- Rule 6 violated → flag `bidder_id_same_date_rank_violation`, hard.

**Why all hard.** The ordering semantics are now fully deterministic
(§A1/§A2/§A3). Any AI violation is a real defect worth catching.
Soft-flagging would let sloppy extraction slide through.

**Rejected alternatives.**
- **All structural hard, date monotonicity soft** — lenient on the
  ordering semantics we worked hard to resolve; the validator would
  miss real defects.
- **Minimal set (only uniqueness)** — gives up the chronology guarantee
  that makes downstream analysis tractable.

**Cross-references.**
- `rules/dates.md` §A1 (BidderID semantics).
- `rules/dates.md` §A2 (strict date-monotonicity).
- `rules/dates.md` §A3 (same-date tie-break table).
- `rules/invariants.md` §P-D* (validator implementation).

---

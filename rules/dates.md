# rules/dates.md — Dates and Event Sequencing

**Purpose.** Rules for mapping natural-language dates to calendar dates, handling undated events, and assigning `BidderID` event-sequence numbers.

**Status legend:** 🟥 OPEN · 🟨 TENTATIVE · 🟩 RESOLVED

> Stage 1 is complete. Some historical dependency prose below still uses the
> word "pending" when describing how the rulebook was developed. Treat the
> section headers and `Decision:` blocks as authoritative; if a section is
> marked 🟩 RESOLVED, it is closed unless explicitly reopened.

---

## Resolved rules

### §B1 — Natural-language date mapping (🟩 RESOLVED, 2026-04-18)

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

### §B2 — Precise vs rough date population (🟩 RESOLVED, 2026-04-18)

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
  equivalent but breaks legacy column compatibility.

**Cross-references.**
- `rules/dates.md` §B1 (inference rules).
- `rules/dates.md` §B3 (undated events).
- `rules/invariants.md` — validator check pending.

---

### §B3 — Undated events (🟩 RESOLVED, 2026-04-18)

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
`BidderID` sequence per §A (pending) preserves narrative order.

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
- `rules/dates.md` §A (BidderID as ordering fallback — pending).

---

### §B4 — Date-range events (🟩 RESOLVED, 2026-04-18)

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

**Open to revisit.** If the 25-deal stress-test study reveals duration
matters systematically (e.g., long exclusivity periods meaningfully
differ from short ones), we may add a `duration_days` field or a
closed list of "duration-bearing" event types that emit start/end rows.

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

## Event sequencing (§A — `BidderID`) — Resolved rules

### §A1 — Keep `BidderID` (🟩 RESOLVED, 2026-04-18)

**Decision.** Keep the column name `BidderID` for legacy-join
compatibility with Alex's workbook, but **redefine the semantics**:
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
- **Drop entirely** — breaks legacy-join; removes a cheap per-deal
  ordinal key.
- **Keep + replicate decimal-wedge logic** — maximum backward-compat,
  maximum confusion; we're building fresh data, not patching.
- **Rename to `event_seq`** — semantically cleaner but breaks
  legacy-join; not worth it.

**Cross-references.**
- `rules/dates.md` §A2 (what determines the ordering).
- `rules/dates.md` §A3 (same-date tie-break).
- `rules/dates.md` §A4 (invariants — pending).
- `rules/bidders.md` §E3 (canonical bidder IDs, separate from `BidderID`).

---

### §A2 — Strict monotonicity in date (🟩 RESOLVED, 2026-04-18)

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
- `rules/invariants.md` (validator checks, pending).

---

### §A3 — Same-date tie-break (🟩 RESOLVED, 2026-04-18)

**Decision.** Within a same-date block, apply **logical/semantic
ordering** first, then filing narrative order as secondary tie-break.

**Logical ordering table** (lower rank = earlier).

| Rank | Event class | Event codes |
|---|---|---|
| 1 | Process announcements | `Bid Press Release`, `Sale Press Release`, `Target Sale Public`, `Final Round Ann`, `Final Round Inf Ann`, `Final Round Ext Ann`, `Final Round Inf Ext Ann`, `Bidder Sale`, `Activist Sale` |
| 2 | Process start/restart | `Target Sale`, `Target Interest`, `Terminated`, `Restarted` |
| 3 | Advisor/IB changes | `IB`, `IB Terminated` |
| 4 | Bidder first-contact | `Bidder Interest` |
| 5 | NDA executions | `NDA` |
| 6 | Informal bids | `Bid` **with** `bid_type = "informal"` (per §C3) |
| 7 | Formal bids | `Bid` **with** `bid_type = "formal"` (per §C3) |
| 8 | Dropouts (mid-round) | `Drop`, `DropBelowInf`, `DropAtInf`, `DropBelowM`, `DropTarget`, implicit drops |
| 9 | Final-round deadlines | `Final Round`, `Final Round Inf`, `Final Round Ext`, `Final Round Inf Ext`, `Auction Closed` |
| 10 | Post-deadline activity | Late bids after `Final Round`, winner confirmation |
| 11 | Signing | `Executed` |

**Bid row rank disambiguation (§C3 migration).** All bid rows carry
`bid_note = "Bid"` per `rules/events.md` §C1/§C3. Within a same-date
cluster, bid rows are ranked 6 or 7 based on `bid_type`:

- `bid_type = "informal"` → rank 6
- `bid_type = "formal"` → rank 7
- `bid_type = null` (ambiguous per `rules/bids.md` §G1) → rank 6 (conservative)

The prior convention — ranking bid rows by distinct `bid_note` codes
(`Inf`, `Formal Bid`, `Revised Bid`) — is deprecated; see `rules/events.md`
§C3. The validator (`pipeline.py _rank()`) implements the `bid_type` lookup.

**Within-rank tie-break.** Filing narrative order (top-to-bottom as
events appear in the Background section).

**Example — Petsmart 12 NDAs on 10/07/2014.**
- All 12 NDAs are rank 5.
- Within rank 5, emit in filing narrative order (Party A, Party B, ...
  as they're listed in the filing).
- `BidderID` increments 1 per row across the 12 NDAs.

**Example — Providence 7/20/2016.**
- Filing has 4 informal bids + `Final Round Inf` on same date.
- Informal bids (rank 6) come before `Final Round Inf` (rank 9).
- Within the 4 informal bids, filing narrative order.
- Final result: 4 informal-bid rows, then 1 Final Round Inf row.

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

### §A4 — `BidderID` consistency invariants (🟩 RESOLVED, 2026-04-18)

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

**Note on Alex's workbook violations.** Mac Gray row 6960 and
Medivation row 6070 violate rule 3; Medivation row 6067 violates rule 5.
These are documented in `reference/alex/alex_flagged_rows.json` and
**fixed** when building `reference/alex/*.json` (per §Q3/§Q4 below).

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

## Alex-flagged rows in the reference workbook (§Q) — Resolved rules

**Frame.** When Stage 2 converts the 9 reference deals from the xlsx
workbook to `reference/alex/{deal}.json`, these rules govern how to
handle rows that Alex himself flagged as wrong. The xlsx remains the
literal source of what Alex wrote; `reference/alex/*.json` reflects
**Alex's intent** — what he'd have produced if he could edit. The
flagged xlsx rows are preserved in `reference/alex/alex_flagged_rows.json`
for provenance.

**Global principle.** `reference/alex/*.json` must pass the §A4
invariants, so structural defects (duplicate `BidderID`, gaps) are
fixed during conversion. Semantic defects that Alex explicitly
flagged are also fixed. Both kinds of fix are recorded in the source
quote / flag field so Stage 3 reviewers see the edit history.

### §Q1 — Saks rows 7013 and 7015 (🟩 RESOLVED, 2026-04-18)

**Decision.** **Apply Alex's deletion** when building
`reference/alex/saks.json`. Rows 7013 (unsolicited) and 7015 (not a
separate bid) are excluded.

**Provenance.** Both rows remain in `reference/alex/alex_flagged_rows.json`
with Alex's verbatim comments. Stage-2 conversion script logs
`applied_alex_deletion: [7013, 7015]` in the per-deal conversion log.

**Why apply.** Austin's call: `reference/alex/saks.json` should reflect
Alex's stated intent, not his literal xlsx cells. The AI's correct
exclusion of these events will not appear as a "false negative" diff,
reducing adjudication noise.

**Consequence for diff reports.** The AI will not diff against these
deleted rows. If Austin later disagrees with Alex's deletion after
reading the filing, he can add them back in Stage 3.

**Cross-references.**
- `reference/alex/alex_flagged_rows.json` (preserved Alex comments).
- `rules/dates.md` §A4 (invariants that the resulting JSON must pass).

---

### §Q2 — Zep row 6390, 5-bidder compressed row (🟩 RESOLVED, 2026-04-18)

**Decision.** **Expand row 6390 into 5 atomized rows** when building
`reference/alex/zep.json`, consistent with `rules/bidders.md` §E1.

**Expansion algorithm.**
1. Read row 6390 and Alex's comment.
2. Identify the 5 bidders and their bid values as best as the xlsx
   content allows.
3. Emit 5 separate rows, each with its own `BidderID`, bidder identity,
   and bid value.
4. Each expanded row carries a flag
   `{"code": "alex_row_expanded", "severity": "info",
     "reason": "from xlsx row 6390; original Alex comment: <verbatim>"}`.

**Ambiguity handling.** Alex's own note acknowledges ambiguity ("one
bid 20, another 22, another three [20,22]?"). For rows where Alex's
intent isn't fully specified, populate conservatively — use the range
[20, 22] as the bid value for ambiguous bidders and flag
`bid_value_ambiguous_per_alex` (info). Austin reviews during Stage 3.

**Why expand.** Same intent principle as §Q1 — Alex wanted 5 rows but
couldn't easily edit the xlsx. The atomized schema is the right target.

**Provenance.** Original row 6390 preserved in
`reference/alex/alex_flagged_rows.json`.

**Cross-references.**
- `rules/bidders.md` §E1 (atomization).
- `rules/dates.md` §A4 (BidderID invariants).

---

### §Q3 — Mac Gray `BidderID=21` duplicate (🟩 RESOLVED, 2026-04-18)

**Decision.** **Renumber** the duplicate `BidderID=21` (row 6960) during
conversion to satisfy §A4 rule 3 (uniqueness). Use the next available
integer consistent with §A2/§A3 ordering.

**Algorithm.**
1. Sort Mac Gray rows by `(bid_date_precise, §A3 rank)`.
2. Reassign `BidderID = 1..N` in that order.
3. Row that was `ID=21` (row 6960) gets its new unique integer.
4. Add flag on the renumbered row:
   `{"code": "bidder_id_renumbered_from_alex", "severity": "info",
     "reason": "original xlsx BidderID=21 duplicated row 6957; renumbered to <N>"}`.

**Why renumber.** If we copy the duplicate as-is, `reference/alex/mac-gray.json`
fails the §A4 uniqueness invariant and can't be loaded for diffing.
Renumbering with a provenance flag preserves the "this was a duplicate"
signal while keeping the file usable.

**Provenance.** Original row 6960 preserved in
`reference/alex/alex_flagged_rows.json` with its original `BidderID=21`.

**Cross-references.**
- `rules/dates.md` §A4 (uniqueness invariant).
- `reference/alex/alex_flagged_rows.json`.

---

### §Q4 — Medivation `BidderID=5` duplicate (🟩 RESOLVED, 2026-04-18)

**Decision.** Same algorithm as §Q3 — **renumber** the duplicate
`BidderID=5` (rows 6066 and 6070). Also renumber row 6067
(`ID=4` on 8/8 violates §A4 rule 5 / date-monotonicity against row 6066's
`ID=5` on 7/19).

**Algorithm.**
1. Sort Medivation rows by `(bid_date_precise, §A3 rank)`.
2. Reassign `BidderID = 1..N` in that order.
3. Rows 6066, 6067, 6070 all get new unique integers.
4. Add flag on each renumbered row:
   `{"code": "bidder_id_renumbered_from_alex", "severity": "info",
     "reason": "original xlsx row <N> violated §A4 rule <3|5>; renumbered"}`.

**Why renumber.** Row 6067's date-order violation and rows 6066/6070's
uniqueness violation both fail §A4. A single pass of chronological
renumbering fixes all three cleanly.

**Provenance.** Original rows preserved in
`reference/alex/alex_flagged_rows.json`.

**Cross-references.**
- `rules/dates.md` §A4.
- `reference/alex/alex_flagged_rows.json`.

---

### §Q5 — Medivation aggregated NDA / Drop rows (🟩 RESOLVED, 2026-04-18)

**Decision.** **Expand** Medivation's two aggregated rows during xlsx →
JSON conversion, per `rules/bidders.md` §E1 atomization. Analogous to §Q2
(Zep row 6390); applied deal-specifically to Medivation.

**Rows affected (xlsx labels verbatim).**
- The 7/5 NDA row with `BidderName = "Several parties, including Sanofi"`.
- The 8/20 Drop row with `BidderName = "Several parties"`.

**Expansion.** The filing narrates "confidentiality agreements with several
parties, including Sanofi." "Several" is ≥3 in standard English, so there
are ≥2 unnamed parties beyond Sanofi. We atomize into:

- NDA row → 3 atomic rows:
  - `bidder_alias = "Sanofi"`, reusing her existing canonical id (her 4/13
    Bidder Sale row already defined `bidder_01`).
  - `bidder_alias = "Party A"`, new canonical id.
  - `bidder_alias = "Party B"`, new canonical id.

- Drop row → 2 atomic rows (Sanofi's 8/20 Drop is already its own row in
  the xlsx, so only the unnamed parties need expansion):
  - `bidder_alias = "Party A"`, same canonical id as the NDA Party A.
  - `bidder_alias = "Party B"`, same canonical id as the NDA Party B.

**Each expanded row** carries:
```json
{"code": "alex_row_expanded", "severity": "info",
 "reason": "§Q5: from xlsx row <N> ('<verbatim>'); atomized per §E1 because the xlsx compressed ≥3 NDA signers (Sanofi + unnamed) into one row"}
```

**Sanofi's bidder_type** on the atomized NDA row is copied from her 4/13
Bidder Sale row (the aggregated xlsx row has `bidder_type=null` because Alex
didn't populate type columns for mixed aggregations). Party A / Party B
`bidder_type` stay null — the filing doesn't identify them.

**Why this matters for Stage 3 diffs.** Without expansion, the AI's
atomized extraction would show 3 `ai_only` NDA rows and 2 `ai_only` Drop
rows against the aggregated reference — artificial divergences that drown
out real extraction defects. Post-expansion, the rows join cleanly (modulo
placeholder-count interpretation, which §Scope-3 treats as legitimate AI
flexibility).

**Generalization deferred.** If future reference deals surface similar
aggregated-party rows, extend §Q5 then. Other 2026-04-18 reference builds
checked: no other deal in the 9-deal reference set has this pattern.

**Provenance.** Original aggregated rows preserved in
`reference/alex/alex_flagged_rows.json` alongside §Q3/§Q4 entries.

**Cross-references.**
- `rules/bidders.md` §E1 (atomization).
- `rules/bidders.md` §E3 (canonical IDs; Sanofi reuses hers).
- `rules/dates.md` §Q2 (analogous Zep expansion).
- `scoring/results/medivation_adjudicated.md` — divergence source.

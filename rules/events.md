# rules/events.md — Event Vocabulary

**Purpose.** Defines the closed set of `bid_note` values the extractor may emit, plus the decision tree for classifying each event.

**Status legend:** 🟥 OPEN · 🟨 TENTATIVE · 🟩 RESOLVED

---

## Resolved rules

### §C1 — Final `bid_note` vocabulary (🟩 RESOLVED, 2026-04-18)

The `bid_note` field is drawn from a **closed vocabulary**. The extractor
MUST NOT invent new values; if an event doesn't fit, flag it for rulebook
expansion.

**Start-of-process:**
- `Bidder Interest` — bidder approaches target, no concrete sale proposal.
- `Bidder Sale` — bidder approaches with concrete sale proposal (price or clear intent).
- `Target Interest` — target initiates discussions with a specific party, no committed sale (Alex's Mac Gray 6928 distinction — kept as its own code).
- `Target Sale` — target's board resolves to sell / explore sale.
- `Target Sale Public` — public announcement of target's sale process.
- `Activist Sale` — activist pressure precedes the process (separate row before `Target Sale`).

**Publicity:**
- `Bid Press Release`
- `Sale Press Release`

**Advisors:**
- `IB` — investment bank retained.
- `IB Terminated` — investment bank relationship ended (Mac Gray edge case, kept).

**Counterparty events:**
- `NDA` — confidentiality agreement signed.
- `Drop` — bidder withdraws, unspecified reason.
- `DropBelowM` — target rejects bid below minimum.
- `DropBelowInf` — bidder does not advance past informal round.
- `DropAtInf` — bidder self-withdraws at informal stage.
- `DropTarget` — target rejects for other reasons (strategic, financing, scope).

**Bid rows:**
- `Bid` — a bid was submitted (per §C3; replaces legacy `NA`-in-bid_note convention).

**Round structure:**
- `Final Round Ann`
- `Final Round`
- `Final Round Inf Ann`
- `Final Round Inf`
- `Final Round Ext Ann`
- `Final Round Ext`
- `Final Round Inf Ext Ann`
- `Final Round Inf Ext`
- `Auction Closed` — target unilaterally stops the auction without an announced deadline (Providence 6058 distinction; see §K3).

**Closing:**
- `Executed` — merger agreement signed (exactly one per deal per §P-D1).

**Prior-process:**
- `Terminated` — prior sale process formally ended (Zep pattern).
- `Restarted` — new process begins after prior `Terminated` (Zep pattern).

**Dropped from draft:**
- `Exclusivity 30 days` — re-encoded as `exclusivity_days: int` attribute on the associated bid row, NOT an event. (Zep 6405.)

**Total: 27 closed-vocabulary values.** Extractor emits exactly these; anything else → flag `unknown_bid_note`.

**Cross-references.**
- `rules/events.md` §C2 (capitalization).
- `rules/events.md` §C3 (`Bid` convention).
- `rules/events.md` §K3 (`Auction Closed`).
- `rules/invariants.md` §P-R2 (vocabulary validator check).

---

### §C3 — `bid_note` on actual bid rows (🟩 RESOLVED, 2026-04-18)

A bid row carries **`bid_note = "Bid"`** (literal string, part of the §C1
closed vocabulary). The event-type is explicit from `bid_note`; bid-specific
semantics (informal vs formal, range vs point, per-share vs aggregate) are
carried by the other fields:
- `bid_type` — `"formal" | "informal"` (per §G1).
- `bid_value*` fields — point/range/aggregate (per §H1–H4).
- `bid_date_precise` / `bid_date_rough` (per §B).

**Rejected — legacy convention (`bid_note = null` + non-null value columns).**
Required the reader to infer event-type from which columns were populated.
Brittle when a bid row has a null value (e.g., "indicated willingness to bid
but declined to name a number"). Explicit `"Bid"` is unambiguous.

**Migration note.** Alex's legacy rows with `bid_note` blank and non-null
`bid_value*` → mapped to `bid_note = "Bid"` during the xlsx-to-JSON
conversion in Stage 2. Documented in `reference/alex/README.md`.

---

### §D1 — Start-of-process classification (🟩 RESOLVED, 2026-04-18)

**Decision tree.** In chronological order, the extractor emits start-of-process
rows as follows:

- **Board resolves to sell** → `Target Sale`. Add `Target Sale Public` +
  `Sale Press Release` as separate rows if the resolution is publicly
  announced.
- **Unsolicited bid triggers the process** → `Bidder Sale` (on the bid row
  itself OR a preceding discussion row). Add `Bid Press Release` if the
  approach is leaked/announced publicly.
- **Bidder approaches with no concrete sale proposal** → `Bidder Interest`.
- **Activist pressure precedes the process** → `Activist Sale` as a
  separate row BEFORE `Target Sale` (Petsmart pattern).
- **Target initiates private discussions with a specific party without a
  board-level sale resolution** → `Target Interest` (Mac Gray pattern).

**Concurrent / overlapping initiation patterns:**

- **"Target contemplating + bidder arrived first"** (Providence row 6024):
  emit **both** rows, ordered by event date. Target-side board activity and
  bidder-side approach are separate events; the earlier one comes first.
- **`Bidder Interest` → `Bidder Sale` transition** (Imprivata Thoma Bravo:
  Interest 1/31 → Sale 3/09): emit **two separate rows**. No time-gap
  limit; the transition is signaled by the filing's language shift from
  "discussions" to "proposal to acquire at $X."

**Evidentiary standard: `Bidder Interest` vs `Bidder Sale`.**
- `Bidder Interest` — filing describes approach, discussions, NDA signing,
  preliminary due diligence, but **no price or concrete sale proposal**.
- `Bidder Sale` — filing describes a concrete sale proposal: price stated,
  explicit "proposed to acquire" / "offered to purchase" language, OR an
  unambiguous intent-to-buy even without a named price.

When in doubt → `Bidder Interest`. The transition to `Bidder Sale` is
recorded on a later date when the concrete proposal is made. Do NOT retcon
the earlier row.

**Cross-references.**
- `rules/events.md` §I1 (how drops interact with initiation).
- `rules/bidders.md` §E2 (joint-bidder initiation — pending).

---

### §I1 — Dropout code set (🟩 RESOLVED, 2026-04-18)

**The closed dropout vocabulary:**

| Code | Meaning | Initiator |
|---|---|---|
| `Drop` | Bidder withdraws, unspecified / generic reason | **Voluntary** (bidder) |
| `DropBelowM` | Target rejects because bid is below minimum / reserve | **Target** |
| `DropBelowInf` | Bidder does not advance past informal round (target's cut) | **Target** |
| `DropAtInf` | Bidder self-withdraws at informal stage | **Voluntary** (bidder) |
| `DropTarget` | Target rejects for other reasons (financing concerns, strategic fit, scope mismatch, regulatory) | **Target** |

**Narrative reason** captured in `drop_reason_note` (free text). Examples:
`"Not a strategic fit"` (Imprivata 6089), `"No firm financing"` (Mac Gray
Party B), `"Only interested in select assets"` (STec 7154).

**Voluntary vs target-initiated — agency requirement.** Every `Drop*` row's
`source_quote` MUST contain a verb / phrase that identifies the initiator:
- Voluntary: `"withdrew"`, `"declined to continue"`, `"chose not to submit"`,
  `"ceased discussions"`, `"informed [target] that it would not…"`.
- Target-initiated: `"Company terminated discussions with…"`, `"[IB]
  informed [bidder] that its bid was insufficient"`, `"[Target] decided not
  to advance [bidder]"`, `"invited to submit…" → [bidder] not on list`.

If the filing's language is genuinely ambiguous, default to `Drop` (generic)
and emit flag `drop_agency_ambiguous` (severity: soft) with the unclear
quote. **Do not guess.**

**Implicit drops — bidders who signed NDA but took no further action.**

A bidder appears on an `NDA` row but never subsequently bids, drops, or
engages → the extractor MUST emit an **implicit `Drop` row** at the end of
the main process phase with:
- `drop_reason_note = "no further engagement in filing"`
- Flag: `{"code": "implicit_drop", "severity": "info", "reason": "bidder signed NDA but took no action per filing"}`
- `event_date` = the last date the main process was active (typically
  `DateAnnounced` or a few days before), flagged as `date_inferred`.

Rationale: the `auction` classifier (§Scope-1) and the NDA-count cross-check
(§P-D6) require complete accounting of every NDA signer's fate. Silent
attrition distorts the bidder-funnel analysis.

**Consortium drops — split handling.**

When bidders who signed NDAs individually later join as a **joint bidder /
consortium** (Petsmart pattern: multiple sponsors + strategics sign
individual NDAs, form a consortium to bid), and that consortium drops:

- Emit **one `Drop*` row per original bidder** (per their individual NDA),
  citing the consortium drop event.
- Each row carries the same `drop_reason_note` and `source_quote` (the
  consortium's drop statement).
- Each row flags `{"code": "consortium_drop_split", "severity": "info",
  "reason": "consortium <name> dropped; row split per constituent NDA"}`.
- The consortium's bidding events (bids, final-round participation) follow
  the joint-bidder rule in `rules/bidders.md` §E2 — **pending**.

If the bidders never signed individual NDAs (consortium formed before any
NDA) → single consortium row per §E2. No split.

**Why split on individual NDAs.** Preserves the 1:1 mapping from NDA to
drop row, so the bidder funnel stays clean: every NDA-signer has a fate.

**Cross-references.**
- `rules/events.md` §D1 (initiation; `Drop*` rows are always preceded by
  an `NDA` or `Bidder Interest` row per §P-D5).
- `rules/events.md` §I2 (re-engagement after drop).
- `rules/bidders.md` §E2 (joint-bidder representation — pending).
- `rules/invariants.md` §P-D5 (drop-without-prior-engagement check).

---

### §I2 — Re-engagement after a drop (🟩 RESOLVED, 2026-04-18)

**No new event code.** When a bidder drops and later re-engages (Providence
Party D pattern), the extractor DOES NOT emit a `Reengaged` row. The next
`NDA` / `Bid` / `Bidder Sale` row for that bidder implicitly signals
re-entry.

**Bookkeeping.** The re-engagement row carries a flag:
`{"code": "bidder_reengagement", "severity": "info", "reason": "bidder <name> previously dropped at row <row_id>"}`.

This keeps the vocabulary lean while still surfacing the pattern to the
reviewer. Statistical analyses that care about re-engagement can filter on
the flag.

**Validator.** `§P-D5` (drop-without-prior-engagement) is unaffected — the
prior drop row still satisfies the "prior engagement" precondition for the
re-engagement's new NDA.

---

### §J1 — `IB Terminated` handling (🟩 RESOLVED, 2026-04-18)

**Decision.** `IB Terminated` is kept as a distinct event code in §C1.

**Behavior.**
- When a filing describes an investment bank relationship ending, emit an
  `IB Terminated` row with `bidder_name = <bank name>` and the termination
  date (precise or rough per §B).
- When a subsequent IB is retained — even the *same* bank (Mac Gray: BofA
  terminated, then BofA re-hired) — emit a new `IB` row.
- IB events are deal-side, not bidder-side. `BidderID` follows the event
  sequence per `rules/dates.md` §A (pending).

**Rejected alternatives.**
- **Rename to `IB Change`** — loses the explicit "relationship ended" signal
  when a second `IB` row doesn't immediately follow (target might go without
  an IB for a stretch).
- **Encode as a field on the original `IB` row** — makes the `IB` row mutable
  and breaks the "one event per row" invariant; also can't represent
  re-hire cleanly.

**Cross-references.**
- `rules/events.md` §C1 (vocabulary includes `IB Terminated`).
- `rules/invariants.md` — no special invariant needed; `IB Terminated`
  follows the same rules as any other event.

---

### §J2 — Legal counsel structural home (🟩 RESOLVED, 2026-04-18)

**Decision.** Legal counsel is **deal-level**, not event-level. Two new
fields in the `deal` object (per `rules/schema.md` §R1):

- `target_legal_counsel: str | null`
- `acquirer_legal_counsel: str | null`

**Extraction rules.**
- AI reads the first mention of legal counsel for each side in the Background
  section (typically phrases like *"The Company retained [Firm] as legal
  counsel"* or *"[Acquirer] engaged [Firm] as its legal advisor"*).
- If the filing names multiple counsel for one side (e.g., special counsel +
  general counsel), concatenate with `"; "` separator: `"Skadden, Arps; Richards, Layton"`.
- If no counsel is named for a side, emit `null`. Do NOT fabricate.
- Retention dates are NOT captured at the deal level — most filings don't
  state them, and the retention event is not analytically interesting.

**No event row.** `Legal` is NOT added to `bid_note` §C1. Creating event
rows for counsel retention would generate sparse data (date often absent)
and misrepresent counsel as a bidding-process participant.

**Source quote requirement.** Both fields follow the same evidence rule as
event rows — the `deal.deal_flags` array will include one
`legal_counsel_evidence` flag per side with `source_quote` / `source_page`
citing the passage. (Exact flag schema will be pinned in §R2 revisions; for
now, treat as a deal-level evidence entry analogous to an event `source_quote`.)

**Rejected alternatives.**
- **Event row `Legal`** — sparse dates, not a bidding-process event.
- **Both event + deal-level** — duplicative; the deal-level field already
  carries the name, and retention timing is analytically uninformative.

**Migration note.** Alex's legacy `comments_1` entries containing "Legal
advisor: [Firm]" are promoted to the deal-level fields during the
xlsx → JSON conversion in Stage 2.

**Cross-references.**
- `rules/schema.md` §R1 (deal-level fields list).
- `rules/schema.md` §R3 (evidence requirement extends to deal-level fields).

---

### §K1 — Final-round vocabulary (🟩 RESOLVED, 2026-04-18)

**Decision.** The §C1 final-round matrix is accepted as **complete for the
MVP**. Nine codes:

| Code | Informal? | Extension? | Announcement? |
|---|---|---|---|
| `Final Round Ann` | No | No | Yes (target announces final round) |
| `Final Round` | No | No | No (bids submitted at final round) |
| `Final Round Inf Ann` | Yes | No | Yes |
| `Final Round Inf` | Yes | No | No |
| `Final Round Ext Ann` | No | Yes | Yes |
| `Final Round Ext` | No | Yes | No |
| `Final Round Inf Ext Ann` | Yes | Yes | Yes |
| `Final Round Inf Ext` | Yes | Yes | No |
| `Auction Closed` | — | — | — (target halts without announced deadline; Providence 6058) |

Suffix grammar: `Inf` = informal round · `Ext` = deadline extension ·
`Ann` = target's announcement of the round (vs. the bids submitted in it).

**Gaps explicitly flagged for later revision.**
- `Best and Final` vs. `Final Round Ext` — currently collapsed into
  `Final Round Ext`. If the 25-deal lawyer-language study surfaces distinct
  usage, add `Best and Final`.
- `Final Round Deadline` as a date-only event distinct from `Final Round Ann`
  — not added; deadline is treated as an attribute of the `Final Round Ann`
  row via `round_deadline: ISO-date`.

**Extractor behavior.** If a filing uses final-round language that doesn't
map to one of the 9 codes, emit flag `unknown_final_round_phrase` (severity:
soft) with the verbatim quote. Do not force-fit.

**Cross-references.**
- `rules/events.md` §C1 (vocabulary).
- `rules/events.md` §K2 (implicit final rounds).
- `rules/events.md` §K3 (Providence `Auction Closed` case).

---

### §K2 — Implicit final rounds (🟩 RESOLVED, 2026-04-18)

**Decision.** The extractor **infers** a final-round row from subset-invitation
language, even when the filing does not explicitly say "final round."

**Inference triggers** (non-exhaustive; the 25-deal study will expand this
list):
- *"the Board authorized [IB] to advance [subset] to the second phase"*
- *"[subset] was invited to submit final proposals"*
- *"[Target] selected [subset] to continue in the process"*
- *"[IB] sent process letters to [subset]"* (typically = `Final Round Ann`
  since process letters contain the deadline and instructions)

**Emission rule.**
- If the subsequent bids from the named subset are submitted with
  binding-offer language → `Final Round Ann` on the invitation date,
  `Final Round` on the submission date(s).
- If subsequent bids are non-binding / informal → `Final Round Inf Ann`,
  then `Final Round Inf`.
- Flag every inferred row with `{"code": "final_round_inferred", "severity": "info", "reason": "no explicit 'final round' phrase; inferred from subset-invitation language"}`.

**When NOT to infer.**
- Subset invitation without subsequent bids from the named parties → do NOT
  emit a final-round row. Emit the subset as `DropBelowInf` / `DropAtInf` per
  §I1 and note the pattern in `flags`.
- Subset invitation language that is ambiguous about whether it's a final
  round or just a narrowing (e.g., target continues to accept new bidders
  afterward) → flag `final_round_ambiguous` (soft) and default to NOT
  emitting a final-round row.

**Rejected alternatives.**
- **Only explicit language** — undercounts final rounds (Petsmart, Medivation
  both have implicit round cuts).
- **New weaker code `Round Cut`** — balloons vocabulary; the soft `inferred`
  flag handles the audit-trail need.

**Cross-references.**
- `rules/events.md` §C1 (vocabulary).
- `rules/events.md` §K1 (final-round matrix).
- `rules/bids.md` §G1 (informal vs formal — determines which `Inf` suffix).

---

### §K3 — Providence row 6058 edge case (🟩 RESOLVED, 2026-04-18)

**Decision.** Providence row 6058 is emitted as **`Auction Closed`**, not
`Final Round`. Alex's original `Final Round` label is corrected during the
xlsx → JSON conversion in Stage 2.

**Rationale.** The filing language describes the target unilaterally halting
the English auction without announcing a final-round deadline to the
bidders. This is exactly the semantic `Auction Closed` was added for (see
§C1). Overloading `Final Round` here would conflate "target runs a final
round" with "target ends the process on its own terms."

**Migration note.** `reference/alex/providence-worcester.json` builder
relabels row 6058 → `Auction Closed` with flag
`alex_workbook_relabel` (severity: info, reason: `"Alex labeled Final Round; reclassified per §K3"`).

**Cross-references.**
- `rules/events.md` §C1 (`Auction Closed` in vocabulary).
- `rules/events.md` §K1 (final-round matrix).

---

### §L1 — Prior-process inclusion rule (🟩 RESOLVED, 2026-04-18)

**Decision.** Prior sale processes are **always included** in the
extraction as event rows, but they **never count toward the auction
threshold** (§Scope-1).

**Rule.**
- Every event mentioned in the Background section is extracted, regardless
  of which process it belongs to.
- Each event row carries `process_phase: int` (per §L2) that identifies
  which phase it belongs to.
- The auction classifier in §Scope-1 counts only NDAs with `process_phase ≥ 1`
  (i.e., the current or restarted process). Stale prior NDAs (`process_phase = 0`)
  do not contribute.

**Rationale.** Preserves Penford's 2007 and 2009 historical record for
downstream research on prior-process effects, while keeping the auction
classifier clean. Consistent with Zep's `Terminated`/`Restarted` treatment.
Aligns the rulebook with Alex's actual behavior (he included Penford's
prior attempts in his workbook even though his written instructions said to
ignore stale NDAs).

**Cross-references.**
- `rules/schema.md` §Scope-1 (auction classifier — non-stale NDAs only).
- `rules/events.md` §L2 (`process_phase` field).

---

### §L2 — `process_phase` column (🟩 RESOLVED, 2026-04-18)

**Decision.** Every event row carries a new integer field
**`process_phase: int`** in `events[]`.

**Values.**
- `0` — **stale prior process.** The process narrated here never reached
  close; it was abandoned with no explicit `Restarted` marker connecting it
  to the current process. Examples: Penford's 2007 and 2009 attempts.
- `1` — **main / first non-stale process.** The default. For deals with no
  prior activity (Medivation, Imprivata, etc.), all events are phase 1.
- `2` — **restarted process.** The process that follows a formal
  `Terminated` → `Restarted` marker pair. Zep's second auction is phase 2.
- `3`, `4`, … — further restarts (not observed in the 9 reference deals; reserved).

**Phase-boundary rules (applied in chronological order).**

1. **Explicit `Terminated`/`Restarted` markers are authoritative.** A
   `Terminated` event ends the current phase; the subsequent `Restarted`
   event begins the next phase. Phase number increments by 1.

2. **6-month silence heuristic (Austin's rule).** If two consecutive events
   in chronological order are **6 months or more apart**, and no
   `Terminated`/`Restarted` pair sits between them, they belong to
   different phases. Emit flag
   `{"code": "phase_boundary_inferred", "severity": "soft", "reason": "gap of <N> months between <event_date_a> and <event_date_b>"}`.

3. **Assignment algorithm.** Walk backward from the `Executed` row:
   - `Executed` is in the main / current process. If no `Restarted` marker
     appears upstream, that process is **phase 1**. If one `Restarted`
     marker appears upstream, the current process is **phase 2** (the
     restart) and the pre-`Terminated` process is **phase 1**.
   - Events separated from the main/restart chain by a ≥ 6-month gap
     (rule 2) with no `Restarted` linking them are **phase 0** (stale prior).
   - Multiple stale priors (Penford 2007 and 2009) all share `process_phase = 0`.
     If research ever needs to distinguish them, add `prior_attempt_index`
     later.

**Extractor guidance.** The extractor assigns `process_phase` as part of
row emission, using the event chronology and markers. The validator
rechecks:
- Every row between `Terminated` and `Restarted` is flagged (empty gap
  expected).
- The single `Executed` row (§P-D1) sits in the highest-numbered phase.
- No `process_phase = 2` rows exist without a preceding `Terminated` +
  `Restarted` pair.
- No `process_phase = 0` rows exist within 6 months of any phase-1/phase-2 event.

**Impact on existing §Scope-1 classifier.** The auction-threshold NDA count
is taken over `{row ∈ events : row.bid_note == "NDA" and row.process_phase ≥ 1 and row.bidder_type not in advisor_types}`.

**Rejected alternatives.**
- **Infer phase from `bid_note` alone** — works for explicit Zep pattern
  but fails for Penford's pure-gap priors (no `Terminated` marker).
- **Skip the field; reconstruct downstream** — pushes the judgment call
  (6-month rule) into N different analysis scripts. Cleaner to freeze it
  once at extraction time.

**Cross-references.**
- `rules/events.md` §L1 (prior-process inclusion).
- `rules/schema.md` §Scope-1 (auction classifier).
- `rules/schema.md` §R1 (event-level field list — add `process_phase`).
- `rules/invariants.md` — new §P-D* checks pending (terminated-restarted
  pairing, Executed in highest phase, no gaps ≥ 6 months within a phase).

---

### §C2 — Canonical capitalization (🟩 RESOLVED, 2026-04-18)

The extractor MUST emit `bid_note` values byte-for-byte matching the strings
in §C1 (case-sensitive). Variants like `"non-US public S"` vs `"Non-US public S"`
are collapsed to the canonical form listed above.

**Absence-of-value convention:**
- `null` — value not collected / not stated in filing. **Default.**
- `"NA"` — genuinely not applicable for this row type. Rare; use only when
  a field is structurally N/A (e.g., `bid_value_pershare = "NA"` on a
  deal-announcement row — but such rows are usually filtered by the event
  type, so `null` suffices in practice).

**Validator check.** `rules/invariants.md` §P-R2 checks `bid_note ∈` the §C1
set; non-canonical variants flag `invalid_event_type` (hard).

**Rejected.** Tolerant/case-insensitive matching → would let `"bidder sale"`
slip through and make downstream grouping unreliable.

---

---

## Draft vocabulary (observed in the 9 reference deals; pending ratification)

### Start-of-process
- `Bidder Interest`
- `Bidder Sale`
- `Target Sale`
- `Target Sale Public`
- `Activist Sale`
- `Target Interest` *(Mac Gray only — status uncertain)*

### Publicity
- `Bid Press Release`
- `Sale Press Release`

### Advisors
- `IB`
- `IB Terminated` *(Mac Gray only — not in Alex's instructions)*
- *(Legal counsel — see §J2)*

### Counterparty events
- `NDA`
- `Drop`
- `DropBelowM`
- `DropBelowInf`
- `DropAtInf`
- `DropTarget`

### Bid rows
- `NA` or blank in `bid_note` (event-type implied by bid-value columns).
- Candidate alternative: a dedicated `Bid` tag (see §C3).

### Round structure
- `Final Round Ann`
- `Final Round`
- `Final Round Inf Ann`
- `Final Round Inf`
- `Final Round Ext Ann`
- `Final Round Ext`
- `Final Round Inf Ext Ann`
- `Final Round Inf Ext` *(Mac Gray)*
- `Exclusivity 30 days` *(Zep — may belong on the bid row instead of as an event)*

### Closing
- `Executed`

### Prior-process
- `Terminated`
- `Restarted`

---

## Open questions

### §C1 — Final authoritative `bid_note` list
- 🟩 **RESOLVED** — see top of this file. 27 closed-vocabulary values. `IB Terminated` kept, `Target Interest` kept as own code, `Exclusivity 30 days` dropped (→ bid-row attribute). New: `Auction Closed` (Providence), `Bid` (replaces legacy NA).

### §C2 — Canonical capitalization and spelling
- 🟩 **RESOLVED** — see top of this file. Case-sensitive byte-for-byte match against §C1. `null` = not collected; `"NA"` = not applicable (rare).

### §C3 — What goes in `bid_note` for an actual bid row?
- 🟩 **RESOLVED** — see top of this file. Dedicated `Bid` value in `bid_note`. Other fields (`bid_type`, `bid_value*`, `bid_date_*`) carry bid-specific semantics.

### §D1 — Start-of-process classification rules
- 🟩 **RESOLVED** — see top of this file. Decision tree formalized. Concurrent initiation (target + bidder) → both rows. `Bidder Interest` → `Bidder Sale` transition → two rows. Evidentiary standard: Bidder Sale requires concrete proposal (price or unambiguous intent).

### §I1 — Dropout code set
- 🟩 **RESOLVED** — see top of this file. 5 codes kept. Agency (voluntary vs target) must appear in `source_quote`. **Implicit drops** required for NDA-but-no-action bidders. **Consortium drops** split into one row per original NDA.

### §I2 — Re-entering after a drop
- 🟩 **RESOLVED** — see top of this file. No new code; info flag `bidder_reengagement` on the re-entry row.

### §J1 — Investment bank events
- 🟩 **RESOLVED** — see top of this file. `IB Terminated` kept as distinct code. Re-hire emits new `IB` row.

### §J2 — Legal counsel — structural home
- 🟩 **RESOLVED** — see top of this file. Deal-level `target_legal_counsel` / `acquirer_legal_counsel` fields. No event row.

### §K1 — Final-round vocabulary
- 🟩 **RESOLVED** — see top of this file. 8-code matrix + `Auction Closed` accepted as MVP-complete. Unknown phrases → soft flag.

### §K2 — Implicit final rounds
- 🟩 **RESOLVED** — see top of this file. Infer from subset-invitation language + subsequent bid submissions. Flag `final_round_inferred`.

### §K3 — Providence row 6058 edge case
- 🟩 **RESOLVED** — see top of this file. Use `Auction Closed` (per §C1); relabel Alex's workbook during xlsx → JSON conversion.

### §L1 — Prior-process inclusion rule
- 🟩 **RESOLVED** — see top of this file. Always include prior processes; never count toward §Scope-1 auction threshold. Stale priors = `process_phase = 0`.

### §L2 — Process-phase column
- 🟩 **RESOLVED** — see top of this file. New per-event `process_phase: int`. Phase-boundary rules: explicit `Terminated`/`Restarted` markers are authoritative; **6-month silence** otherwise forces a phase boundary (Austin's rule).

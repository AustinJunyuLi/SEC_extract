# rules/events.md — Event Vocabulary

**Purpose.** Defines the closed set of `bid_note` values the extractor may emit, plus the decision tree for classifying each event.

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
- `NDA` — **target ↔ bidder** confidentiality agreement (auction NDA, Type A per §I3). Grants the bidder access to MNPI; usually paired with a standstill. This is the auction-funnel signal counted by §Scope-1.
- `ConsortiumCA` — **bidder ↔ bidder** confidentiality agreement (consortium / inter-bidder, Type B per §I3). Two would-be bidders share proprietary analysis / financing plans / strategic intent under mutual confidentiality. NOT auction-funnel signal; does NOT count toward §Scope-1's auction threshold; does NOT discharge §P-D6 (target-NDA precondition for a Bid).
- `Drop` — bidder withdraws, unspecified reason.
- `DropBelowM` — target rejects bid below minimum.
- `DropBelowInf` — bidder does not advance past informal round.
- `DropAtInf` — bidder self-withdraws at informal stage.
- `DropTarget` — target rejects for other reasons (strategic, financing, scope).
- `DropSilent` — bidder signed NDA but the filing narrates no later activity (no bid, no narrated drop, no execution); inferred withdrawal. Required by §I1; date is null with `date_unknown` info flag; agency is unknowable.

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
- `Auction Closed` — target unilaterally stops the auction without an announced deadline (distinct from `Final Round`, which has a formal cutoff).

**Closing:**
- `Executed` — merger agreement signed (exactly one per deal per §P-D1).

**Prior-process:**
- `Terminated` — prior sale process formally ended (Zep pattern).
- `Restarted` — new process begins after prior `Terminated` (Zep pattern).

**Total: 31 closed-vocabulary values.** Extractor emits exactly these; anything else → flag `unknown_bid_note`.

**Note on exclusivity.** Exclusivity periods are NOT events in this vocabulary.
They are re-encoded as an `exclusivity_days: int` attribute on the associated
bid row (Zep 6405 pattern). `scripts/build_reference.py` migrates legacy
"Exclusivity 30 days" xlsx rows accordingly; the extractor should never emit
such a row.

**Cross-references.**
- `rules/events.md` §C2 (capitalization).
- `rules/events.md` §C3 (`Bid` convention).
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

**Migration note.** Two legacy conventions appear in Alex's xlsx; both map
to `bid_note = "Bid"` during the xlsx-to-JSON conversion:

1. `bid_note` blank with non-null `bid_value*` columns → `bid_note = "Bid"`,
   `bid_type` set from the xlsx `bid_type` column when present.

2. `bid_note ∈ {"Inf", "Formal Bid", "Revised Bid"}` (Alex's event-type-
   in-bid_note convention, which §C3 deprecates) → `bid_note = "Bid"` with:
   - `"Inf"` → `bid_type = "informal"`
   - `"Formal Bid"` → `bid_type = "formal"`
   - `"Revised Bid"` → `bid_type = "formal"` and `additional_note` includes
     `"revised"` provenance so a subsequent formal bid from the same bidder
     remains traceable without a distinct `bid_note`.

Both cases preserve the original xlsx label in a `legacy_bid_note` field on
the converted row so the provenance survives. Documented in
`reference/alex/README.md`.

This resolves the prior internal tension between §C1 (text listed only
`Bid`) and `rules/dates.md` §A3's rank table (which used the legacy labels
`Inf`, `Formal Bid`, `Revised Bid` as distinct codes). §A3's rank table now
ranks bid rows by `bid_type` rather than bid_note — see `rules/dates.md`
§A3.

---

### §D1 — Start-of-process classification (🟩 RESOLVED, 2026-04-18; amended 2026-04-19)

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
  separate row BEFORE `Target Sale` (Petsmart pattern). Per §D1.b,
  multiple separately-narrated activists emit **one row per activist**;
  collapse to a single row only when the filing treats them as a
  coordinated group.
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

### §D1.a — Unsolicited first-contact Bid exemption from §P-D5 / §P-D6 (🟩 RESOLVED, 2026-04-19)

**Non-negotiable.** When an unsolicited bid is itself the first contact
from a bidder, emit the `Bid` row only; do NOT emit a duplicate
standalone `Bidder Sale` row.

**Rule.** When a §D1 unsolicited-first-contact Bid row has no
accompanying NDA in the same `process_phase`, attach:

```json
{"code": "unsolicited_first_contact", "severity": "info",
 "reason": "<summary + ≤120-char single-quoted verbatim snippet from the filing showing the decline/withdrawal language>"}
```

The flag exempts the matching `(bidder_name, process_phase)` from both
`_invariant_p_d6()` (no NDA precedes the Bid) and `_invariant_p_d5()`
(no engagement precedes the subsequent Drop/withdrawal). This is the
ONLY exemption flag for those two invariants; §C4's
`pre_nda_informal_bid` is documentation-only. Attach to the Bid row
only — §P-D5's witness check scans the full (bidder, phase) slice.

**Attachment conditions (all three must hold).**

1. Row is §D1 unsolicited first-contact (approach is unsolicited AND
   first narrated contact from this bidder).
2. No `NDA` row with the same `bidder_name` exists in the same
   `process_phase`. (If the bidder signs an NDA later in the phase,
   use §C4 instead.)
3. The filing narrates the target declining to engage OR the bidder
   withdrawing before any NDA is signed. The `reason` field MUST
   include a ≤120-char single-quoted verbatim snippet showing that
   language.

If the filing language is ambiguous, do NOT attach the flag — let
§P-D6 fire and let Austin adjudicate. The verbatim-quote requirement
is the generalizable safety check; no closed verb list, because
filings phrase these outcomes many ways.

### §D1.b — Multi-activist atomization (🟩 RESOLVED, 2026-04-19)

**Rule.** When the filing narrates **multiple activists** separately
pressuring the target in parallel, emit **one `Activist Sale` row per
activist**. Collapse to a single `Activist Sale` row ONLY when the
filing treats the activists as a coordinated group (e.g., *"a group of
activist investors led by X, including Y and Z, jointly filed a
Schedule 13D…"*).

**Decision tree:**
1. Filing narrates each activist separately (separate 13D filings,
   separate letters, separate press releases) → **N rows**, one per
   activist. Each row's `bidder_alias` = that activist's filing label.
2. Filing narrates activists as a coordinated group → **1 row** with
   `bidder_alias` = the group label and `joint_bidder_members` listing
   the constituent canonical ids.
3. Ambiguous (filing narrates activists on different dates but mentions
   coordination at some point) → default to per-activist rows; flag
   `multi_activist_coordination_ambiguous` (soft).

**Examples.**
- Petsmart (2013–2014): JANA and Longview filed separate 13Ds and
  pressured the target on different dates → **2 `Activist Sale` rows**,
  not 1.
- Coordinated-group example (hypothetical): *"An investor consortium
  led by X, including Y and Z, filed a joint 13D and issued a press
  release calling for a sale"* → **1 row** with the coordinated-group
  label.

**Migration note.** Alex's Petsmart workbook collapsed JANA + Longview
into 1 Activist Sale row; under this rule the AI emits 2. This is a
legitimate AI-identified correction per the ground-truth epistemology
(§CLAUDE.md).

**Cross-references.**
- `rules/events.md` §I1 (how drops interact with initiation).
- `rules/events.md` §C1 (`Activist Sale` vocabulary).
- `rules/bidders.md` §E2 / §E2.a / §E2.b (joint-bidder handling).
- `rules/invariants.md` §P-D6 (§D1.a's `unsolicited_first_contact`
  flag exempts rows from §P-D6).

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
| `DropSilent` | Bidder signed NDA but the filing narrates no later activity for them (no bid, no narrated drop, no execution); inferred withdrawal | **Inferred** (no narrated agency) |

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

**NDA-only rows — bidders who signed but have no later narrated activity.**

A bidder may appear on an `NDA` row and never subsequently bid, drop, or
execute in bidder-specific narration. In that case the extractor MUST emit
a `DropSilent` row for that bidder, immediately after the matching NDA row
in narrative order:

- `bid_note = "DropSilent"`
- `bid_date_precise = null`, `bid_date_rough = null`
- `flags` includes `{"code": "date_unknown", "severity": "info", "reason":
  "DropSilent: filing narrates no withdrawal date for silent NDA signer"}`
- `source_quote` and `source_page` re-cite the matching NDA row (the
  silence in the rest of the filing is the evidence; the NDA passage is
  the closest filing anchor)
- All other identity fields (`bidder_name`, `bidder_alias`, `bidder_type`,
  `process_phase`, `role`) copied verbatim from the matching NDA row

Validator `rules/invariants.md` §P-S1 fires (soft, `missing_nda_dropsilent`)
only when the extractor failed to emit the required `DropSilent` row. It is
a backstop, not an expected-noise channel.

Rationale: silent post-NDA behavior IS a withdrawal — the filing's silence
is the evidence. Encoding it as a dedicated `DropSilent` code (rather than
generic `Drop` or `DropAtInf`) preserves the distinction between
filing-narrated drops and inferred-from-silence drops, which matters for
downstream auction-funnel analysis. Re-citing the NDA quote is consistent
with §R2 because the row's *meaning* (no later activity) is genuinely
sourced from that bidder's absence from the rest of the filing; the NDA
passage is the only concrete anchor the filing gives us.

Reverses the Providence iter-7 stance ("do not fabricate catch-all
Drops"). The earlier rationale — "synthetic Drops would have reused one
generic quote across all 20 rows" — is addressed by the dedicated
`DropSilent` code: the row's semantics make explicit that the quote is the
NDA passage, not a fabricated drop narration.

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
  the joint-bidder rule in `rules/bidders.md` §E2.

If the bidders never signed individual NDAs (consortium formed before any
NDA) → single consortium row per §E2. No split.

**Why split on individual NDAs.** Preserves the 1:1 mapping from NDA to
drop row, so the bidder funnel stays clean: every NDA-signer has a fate.

**Cross-references.**
- `rules/events.md` §D1 (initiation; `Drop*` rows are always preceded by
  an `NDA` or `Bidder Interest` row per §P-D5).
- `rules/events.md` §I2 (re-engagement after drop).
- `rules/bidders.md` §E2 (joint-bidder representation).
- `rules/invariants.md` §P-D5 (drop-without-prior-engagement check).

---

### §I3 — Confidentiality-agreement scope: target ↔ bidder vs consortium vs rollover (🟩 RESOLVED, 2026-04-26 per Decision #4)

**Problem.** The "Background of the Merger" section often describes
multiple confidentiality agreements within the deal process. Three
legally distinct CA types appear:

- **Type A — Target ↔ bidder NDA (auction NDA).** The classic.
  Asymmetric: the target shares MNPI (material non-public information)
  with a potential bidder under confidentiality, usually paired with a
  standstill restricting the bidder from buying target stock or making
  unsolicited offers. **This is the auction-funnel signal** counted by
  §Scope-1 (≥2 ⇒ `auction = true`).
- **Type B — Bidder ↔ bidder CA (consortium / inter-bidder).** Two
  would-be bidders sign a mutual CA to share their proprietary
  analysis, financing plans, or strategic intent before forming a
  consortium. Mutual, not asymmetric. Does NOT grant MNPI access; does
  NOT involve the target as a party. Examples: petsmart's December 2014
  CAs between Longview (an activist holder) and the BC Partners-led
  Buyer Group.
- **Type C — Shareholder ↔ acquirer rollover CA.** A major target
  shareholder agrees to roll their equity into the post-merger entity;
  the CA covers the negotiation period for that side-deal. Operational;
  not auction-funnel signal. Rare across the 9 reference deals.

**Decision** (2026-04-26):

- **Type A** → `bid_note = "NDA"` (the existing event). Counted by
  §Scope-1; satisfies §P-D6 (NDA-before-Bid precondition); subject to
  §I1 DropSilent rule for silent signers.
- **Type B** → `bid_note = "ConsortiumCA"` (new event in §C1; rank 5
  by §A3). NOT counted by §Scope-1; does NOT satisfy §P-D6 (a Type B
  CA is not target-bidder, so a separate Type A NDA is still required
  for that bidder's later target-NDA-precondition); does NOT trigger
  §I1 DropSilent (a silent ConsortiumCA signer is not a silent
  auction-funnel signer).
- **Type C** → **skipped.** No row emitted. See `rules/bids.md` §M5.
  Rollover CAs are not auction-process events; they belong to a
  separate research domain (post-merger capital structure).

**Disambiguation guidance for the extractor.** When the filing narrates
a CA, use these heuristics to classify:

| Filing language pattern | Type | Code |
|---|---|---|
| *"\[Target\] entered into a confidentiality agreement with \[Bidder\]"* / *"\[Bidder\] executed a confidentiality agreement with \[Target\]"* | A | `NDA` |
| *"\[Target\]'s representatives delivered a confidentiality agreement to \[Bidder\]"* / *"\[Bidder\] signed a CA in connection with the auction process"* | A | `NDA` |
| *"\[Bidder1\] and \[Bidder2\] entered into a confidentiality agreement"* / *"the consortium members entered into a confidentiality agreement among themselves"* / *"\[Bidder\] joined the buyer group / consortium and executed a confidentiality agreement with \[other-bidder(s)\]"* | B | `ConsortiumCA` |
| *"\[Activist Holder\] / \[Major Shareholder\] entered into a confidentiality agreement with \[Buyer Group\] regarding their potential rollover"* / *"\[Shareholder\] agreed to roll their equity"* | C | **skip** (per §M5) |

**When the language is ambiguous** between A and B (e.g., a CA whose
parties are not clearly named), default to Type A and attach
`{"code": "ca_type_ambiguous", "severity": "soft", "reason": "<summary>"}`.
Austin adjudicates against the filing.

**ConsortiumCA emission rule.**
- `bid_note = "ConsortiumCA"`
- `bidder_name` = canonical id of the named CA signer (the bidder side
  the filing identifies; for the petsmart example, Longview's id)
- `bidder_alias` = filing's verbatim label for the consortium relationship
  (e.g., `"Longview and the Buyer Group"`)
- `bid_date_precise` = the CA execution date as narrated
- `joint_bidder_members` = optional; populated when the filing names
  the consortium constituents
- `source_quote` / `source_page` = the filing language describing the
  consortium CA
- `process_phase` follows the surrounding events (typically phase 1)
- `role = "bidder"` (still a bidder-side event, just not target-bidder)

**Validator behavior on ConsortiumCA.**
- §P-S1 (silent NDA → DropSilent) applies only to `bid_note = "NDA"`.
  ConsortiumCA signers without later activity do NOT trigger
  `missing_nda_dropsilent`.
- §P-S2 (auction count) counts only `bid_note = "NDA"`. ConsortiumCA
  is NOT in the count.
- §P-D6 (NDA-before-Bid precondition) requires a `bid_note = "NDA"`.
  ConsortiumCA does NOT discharge §P-D6; a bidder who later submits a
  Bid still needs a Type A NDA for §P-D6.
- §P-D5 (drop-without-prior-engagement) — the engagement set
  (`{"NDA", "Bidder Interest", "IB"}` plus all Drop codes) does NOT
  include `ConsortiumCA`. A bidder who signed only a ConsortiumCA and
  then dropped will fire §P-D5; this is intentional (the filing should
  show how the bidder engaged with the target before withdrawing).

**Why a new event type, not a flag on NDA.**
- Type A is the auction signal. Mixing types (even with a
  disambiguating flag) muddies every NDA-count downstream and forces
  every consumer to filter.
- The new vocabulary entry is cheap (1 closed-vocabulary value); the
  signal-cleanliness benefit applies to every analysis.

**Why skip Type C, not capture it.**
- Rare (1 ambiguous instance in petsmart across 9 reference deals).
- Tangential to auction theory.
- Capture-cost (extraction time, schema bloat) > value.
- If a future paper needs rollover behavior, re-extract with a
  targeted pass.

**Cross-references.**
- `rules/events.md` §C1 (vocabulary entry for `NDA` / `ConsortiumCA`).
- `rules/bids.md` §M5 (skip rule for Type C rollover CAs).
- `rules/schema.md` §Scope-1 (auction count uses NDA only).
- `rules/invariants.md` §P-D6, §P-S1, §P-S2 (validator behavior).
- `prompts/extract.md` (extractor classification guidance).
- `quality_reports/decisions/2026-04-26_six-policy-decisions.md` #4.

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

### §J1 — `IB` and `IB Terminated` emission (🟩 RESOLVED, 2026-04-18)

**Decision.** Both `IB` and `IB Terminated` are event-row codes in §C1.

**Initial-retention emission (mandatory).** When the filing names a
financial advisor to either side — target or acquirer — emit one `IB`
row per named advisor:

- `bid_note = "IB"`
- `role = "advisor_financial"` (per `rules/bids.md` §M3)
- `bidder_name` = canonical id assigned to the bank (per `rules/bidders.md`
  §E3)
- `bidder_alias` = filing's verbatim label for the bank
- `bid_date_precise` = the **bank's first narrated action** in advisory
  capacity (per the IB date anchor rule below).

**IB date anchor (sharpened 2026-04-26 per Decision #6).** The
`bid_date_precise` on an IB row is the **earliest narrated date on
which the bank itself takes an action in advisory capacity** for its
side. The rule is observability-driven and excludes target-side
preparatory acts.

**Bank's first-action set** (any of these qualifies; pick the earliest
narrated):

- Signing the engagement letter (*"entered into an engagement letter"*,
  *"executed an engagement letter"*).
- Sending process letters or NDAs to potential bidders on behalf of
  its side.
- Contacting bidders (*"\[Firm\] contacted potential strategic acquirers"*).
- Presenting to the special committee or board (*"\[Firm\] presented its
  preliminary analysis"*, *"\[Firm\] reviewed strategic alternatives"*).
- Any other narrated action where the bank, named explicitly, takes a
  step on behalf of its side.

**Does NOT count as the bank's first action:**

- **Board approval to retain** (*"the board approved the retention of
  \[Firm\]"*, *"the board authorized management to engage \[Firm\]"*).
  This is the **target's** action — a corporate-governance step that
  precedes the bank's involvement. The bank has no advisory
  relationship until the engagement letter is signed.
- **Discussions about which bank to retain** (*"the board considered
  candidates including \[Firm\]"*). Pre-relationship.
- **Mentions of the bank in a different context** (*"a year earlier,
  \[Firm\] had advised the company on …"*). Different engagement.

**When neither engagement letter nor any narrated action carries an
explicit date**, populate `bid_date_precise` with the earliest-narrated
date the bank is named in advisory capacity for this process,
populate `bid_date_rough` with a short anchor phrase naming the
inference source (e.g., `"first narration: 2016-05-11 contact"`), and
attach `{"code": "date_inferred_from_context", "severity": "soft",
"reason": "filing does not narrate engagement-letter date; inferred
from first action"}`. The rough phrase is required by §B3 and is
enforced as a hard validator check (`rules/invariants.md` §P-D2 —
`rough_date_mismatch_inference`).

**Trigger phrases for the bank's first action** (non-exhaustive):
- *"\[Firm\] entered into an engagement letter with \[Side\] on \[date\]"*
- *"\[Firm\] sent a process letter to \[N\] potential bidders on \[date\]"*
- *"representatives of \[Firm\], financial advisor to \[Side\], contacted \[Bidder\] on \[date\]"*
- *"\[Firm\] presented its preliminary analysis to the board on \[date\]"*
- *"\[Firm\] sent a confidentiality agreement to \[Bidder\] on \[date\]"*

If the filing describes \[Firm\] taking advisor actions on behalf of
\[Side\] but does not narrate an explicit retention or engagement-
letter event, the bank is retained for that process; emit one `IB`
row anchored on the **earliest** such action. If \[Firm\] acts for
the same \[Side\] on multiple events (sent process letters, contacted
bidders, ran the auction), emit **one** `IB` row for the earliest
action.

**Why first-narrated-action and not engagement-letter-or-board-approval
fallback chain.** Per Decision #6 (2026-04-26), the rule is the
single-question one: *"what is the earliest narrated date on which the
bank acted?"* — instead of a multi-tier priority chain
(engagement-letter > board-approval > first-action). Engagement-letter
signing IS a first action and dominates naturally because it precedes
any subsequent advisory work; board approval is excluded because it is
not the bank's act. The single-question rule generalizes more honestly
across the 392 target deals than a fallback chain built from the 9
reference cases.

**Termination and re-hire.**
- When a filing describes an investment bank relationship ending, emit an
  `IB Terminated` row with `bidder_name = <bank canonical id>` and the
  termination date (precise or rough per §B).
- When a subsequent IB is retained — even the *same* bank (Mac Gray: BofA
  terminated, then BofA re-hired) — emit a new `IB` row following the
  initial-retention rules above.

**Advisors to acquirers are also emitted.** (Example: Medivation's
Centerview row as Pfizer's advisor.) This keeps the `IB` event count
complete for downstream research on advisor effects.

**BidderID.** IB events are deal-side, not bidder-side; they follow the
event sequence per `rules/dates.md` §A.

**Validator.** No special invariant — an IB row follows the same §P-R
rules as any other event. The auction-threshold classifier in
§Scope-1 excludes `role = "advisor_financial"` rows from its NDA count.

**Rejected alternatives.**
- **Skip advisors entirely.** Loses retention data Alex records in his
  workbook; the initial-retention event is analytically meaningful
  (advisor choice shapes process design).
- **Fold advisor retention into a deal-level field.** Can't represent
  multiple advisors, re-hires, or termination cleanly; also breaks
  uniformity of event-row structure.
- **Rename `IB Terminated` to `IB Change`.** Loses the explicit
  "relationship ended" signal when a second `IB` row doesn't immediately
  follow (target might go without an IB for a stretch).

**Cross-references.**
- `rules/events.md` §C1 (vocabulary includes `IB` and `IB Terminated`).
- `rules/bids.md` §M3 (`role = "advisor_financial"`).
- `rules/schema.md` §Scope-1 (auction classifier filters `role == "bidder"`).

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
| `Auction Closed` | — | — | — (target halts without announced deadline; distinct from `Final Round`, which has a formal cutoff) |

Suffix grammar: `Inf` = informal round · `Ext` = deadline extension ·
`Ann` = target's announcement of the round (vs. the bids submitted in it).

**Extractor behavior.** If a filing uses final-round language that doesn't
map to one of the 9 codes, emit flag `unknown_final_round_phrase` (severity:
soft) with the verbatim quote. Do not force-fit.

**Cross-references.**
- `rules/events.md` §C1 (vocabulary).
- `rules/events.md` §K2 (implicit final rounds).

---

### §K2 — Implicit final rounds (🟩 RESOLVED, 2026-04-18)

**Decision.** The extractor **infers** a final-round row from subset-invitation
language, even when the filing does not explicitly say "final round."

**Inference triggers** (non-exhaustive):
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
   different phases. This is an assignment rule, not a standalone soft-flag
   vocabulary item.

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
- The single `Executed` row (§P-S4) sits in the highest-numbered phase.
- No `process_phase = 2` rows exist without the explicit restart
  boundary: a phase-1 `Terminated` row followed by a phase-2
  `Restarted` row (§P-L1).
- No `process_phase = 0` rows exist within 6 months of any
  phase-1/phase-2 event (§P-L2).

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

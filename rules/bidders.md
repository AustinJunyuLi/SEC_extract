# rules/bidders.md — Bidder Identity & Type

**Purpose.** Rules for identifying, naming, classifying, and aggregating bidders across rows of a single deal.

---

## Resolved rules

### §E2 — Joint-bidder rows (🟩 RESOLVED, 2026-04-18; amended 2026-04-19)

**Decision.** `BidderID` is an **event-sequence number, not a bidder-
identity number**. Jointness is carried by `joint_bidder_members`, not by
reusing a `BidderID` across multiple rows. **Two exceptions remain:**

1. **Executed rows are always exactly 1 per deal** (see §E2.a below).
2. **Group-narrated NDAs collapse to 1 row** when the filing does not
   give per-constituent detail (see §E2.b below).

**Rule.**
- When the filing narrates a **single consortium event** (joint NDA, Bid,
  Drop, or Executed exception below), emit **one row** for that narrated
  event.
- `bidder_alias` is the filing's consortium label for that row.
- `bidder_name` is the canonical id for the narrated signer on that row
  (often the nominal acquirer or consortium label registered in §E3).
- `joint_bidder_members` carries the constituent canonical ids, e.g.
  `["bidder_06", "bidder_07"]`.
- That row still receives its own unique event-sequence `BidderID`
  assigned by `pipeline._canonicalize_order()`.
- When the filing instead gives **per-constituent detail**, emit one row
  per narrated constituent; each row still receives its own unique
  `BidderID` and may carry `joint_bidder_members` if that adds clarity.

**Example.** A consortium bid narrated once in the filing can appear as:

```json
{
  "BidderID": 14,
  "bid_note": "Bid",
  "bidder_alias": "CSC/Pamplona",
  "bidder_name": "bidder_06",
  "joint_bidder_members": ["bidder_06", "bidder_07"]
}
```

### §E2.a — Executed-row joint-bidder exception (🟩 RESOLVED, 2026-04-19)

**Decision.** An `Executed` row is **always exactly one per deal**, even
when the merger-agreement counterparty is a consortium / joint bidder.
Hard invariant §P-S4 (`multiple_executed_rows`) remains the law.

**Rule.**
- When the merger agreement is executed by a consortium (e.g., Mac-Gray:
  CSC + Pamplona; Petsmart: BC Partners + Caisse + GIC + StepStone +
  Longview), emit **one** `Executed` row with:
  - `bidder_alias` = the merger-agreement counterparty label as the
    filing names it. Use the filing's exact consortium label when
    present (e.g., `"CSC/Pamplona"`, `"Buyer Group"`). If the filing
    lists only the nominal acquirer entity (`"Parent"` / `"MergerSub"`)
    without narrating a consortium label, use that.
  - `bidder_name` = the canonical id of the nominal acquirer (the entity
    that is legally the counterparty on the merger agreement). If the
    filing's consortium label is used as the alias and no canonical id
    yet exists for it, register it in `bidder_registry`.
  - `joint_bidder_members: list[str]` — a list of canonical ids of all
    consortium constituents (e.g., `["bidder_04", "bidder_07"]`).
    Required when the Executed counterparty is a consortium.
- §E2's per-constituent atomization rule applies to NDAs (subject to
  §E2.b), Bids, and Drops — but **NOT** to Executed.

**Why one row for Executed.** There is exactly one merger agreement; the
Executed event is a single atomic legal act. Per-constituent atomization
of Executed would fabricate N signing events the filing does not narrate
as distinct. The `joint_bidder_members` field preserves the consortium
structure for downstream queries.

**Interaction with §A3 ranking.** Executed remains rank 11 (closing).
One row per deal; no same-date collision with itself.

### §E2.b — Group-narrated NDA aggregation (🟩 RESOLVED, 2026-04-19)

**Principle.** Emit one NDA row per *identifiable signer the filing
narrates*. Filing granularity decides the shape; the rulebook does not
re-split or re-aggregate against the filing.

**Rule.**

| Filing narrates the NDA as… | Emit | Key fields |
|---|---|---|
| Single consortium event, no per-constituent detail, no count (e.g., *"Buyer Group executed a CA on 7/11/2013"*) | **1 row**, consortium-as-signer | `bidder_alias` = consortium label; `bidder_name` = canonical id for consortium; `joint_bidder_members` = constituent ids if named elsewhere, else null; flag `{"code": "joint_nda_aggregated", "severity": "info", "reason": "...bidder_alias=<label>"}` |
| Numeric count OR named individual signers (e.g., *"15 financial sponsors executed CAs"* or *"BC Partners, Caisse, GIC, … each executed CAs"*) | **N rows**, one per signer per §E3 | Named → filing label; unnamed → `"Strategic k"` / `"Financial k"` placeholders; each row's `bidder_name` = own canonical id; `joint_bidder_members` = null |

**Example.** *"On July 11, 2013, Buyer Group entered into a
confidentiality agreement with the Company."* → 1 aggregated row with
`joint_bidder_members = ["bidder_06", "bidder_07"]` (the two constituents
named earlier in the filing).

**Cross-references.**
- §E1 (atomization), §E3 (canonical IDs / placeholders).
- `rules/events.md` §I1 (consortium-drop splitting).
- `rules/invariants.md` §P-S4 (exactly-one Executed — §E2.a).
- `rules/invariants.md` §P-D6 (NDA-before-Bid existence check matches
  on `bidder_name`; if Bid rows use per-constituent ids while NDA is
  aggregated, promote via `unnamed_nda_promotion` hint or emit
  per-constituent NDAs up front).

---

### §E3 — Anonymous bidder naming (🟩 RESOLVED, 2026-04-18)

**Decision.** `bidder_name` holds a **canonical deal-local ID**;
`bidder_alias` holds the filing's verbatim label for that bidder on that
row.

**Canonical ID format.** `bidder_NN` where `NN` is zero-padded to two
digits, assigned in deal-local chronological order of first appearance.
Examples: `bidder_01`, `bidder_02`, …, `bidder_99`. For deals with >99
bidders (not observed), extend to 3 digits.

**Assignment procedure.**
1. Walk events in chronological order.
2. The first time a distinct bidder appears (under ANY filing label),
   assign the next available canonical ID.
3. All subsequent rows for the same bidder reuse that ID, regardless of
   whether the filing's label for them has changed.
4. Same-entity determination is made by the extractor using filing language
   (e.g., *"Party A, which is a publicly traded pharmaceutical company, …"*
   followed later by *"Pfizer, the same bidder previously referred to as
   Party A, …"* → same canonical ID).

**`bidder_alias`.** Verbatim filing label on THIS row. Examples:
`"Party A"`, `"Pfizer Inc."`, `"Strategic 1"`, `"Sponsor C"`. For joint
bids (§E2), each constituent's row has its own alias.

**Deal-level registry.** The deal object carries a `bidder_registry` map:

```json
"bidder_registry": {
  "bidder_01": {
    "resolved_name": "Pfizer Inc.",
    "aliases_observed": ["Party A", "Pfizer", "Pfizer Inc."],
    "first_appearance_row_index": 3
  },
  "bidder_02": {
    "resolved_name": null,
    "aliases_observed": ["Party B", "Strategic 1"],
    "first_appearance_row_index": 5
  }
}
```

- `resolved_name` — real company name if the filing ever reveals it; `null`
  for bidders that stay anonymous throughout.
- `aliases_observed` — deduped list of all filing labels used for this
  bidder.
- Populated by the extractor after all events are emitted.

**Why canonical ID + alias, not one-or-the-other.**
- `bidder_name` = canonical → stable joins across rows; `groupby(bidder_name)`
  collects every row for a given entity including pre- and post-reveal rows.
- `bidder_alias` = filing label → preserves source-quote integrity; the
  text on row 4 says "Party A approached the Company," and the row matches
  the filing verbatim.

**Rejected alternatives.**
- **Verbatim-only** (`bidder_name = "Party A"`) — breaks cross-row joins;
  pre- and post-reveal rows for the same bidder have different names.
- **Canonical-only** (no alias) — loses the filing's label, breaking
  source-quote correspondence.

**Cross-references.**
- `rules/schema.md` §R1 (event-level `bidder_name` and `bidder_alias`;
  deal-level `bidder_registry`).
- `rules/bidders.md` §E4 (winner retrofit — handled via alias, not rename).

---

### §E4 — Winning-bidder name retrofit (🟩 RESOLVED, 2026-04-18)

**Decision.** **No retrofit.** `bidder_name` (the canonical ID per §E3) is
stable from first appearance. `bidder_alias` tracks the filing's usage
per-row — it may start as `"Party A"` on early rows and change to
`"Pfizer Inc."` on later rows when the filing reveals the identity. The
canonical ID `bidder_03` stays the same across all rows.

**Identity resolution.** Captured at the deal level in `bidder_registry`
(see §E3):
- `resolved_name` — the real company name if the filing ever reveals it.
- `aliases_observed` — the full list of filing labels used.

**Validator checks (see `rules/invariants.md`).**
- Every row's `bidder_alias` must be one of the `aliases_observed` for its
  `bidder_name`.
- `resolved_name` (when non-null) should appear in `aliases_observed`.

**Why no retrofit.**
- Source-quote integrity — a row dated March 2016 that quotes
  *"Party A approached the Company"* must have `bidder_alias = "Party A"`.
  Retrofitting to `"Pfizer"` would break the source-quote match against
  the filing text.
- The canonical ID already provides stable joins; retrofitting the filing
  label is both lossy (destroys the original language) and unnecessary.

**Cross-references.**
- `rules/bidders.md` §E3 (canonical ID + alias structure).

---

### §E5 — Unnamed-party quantifier semantics (🟩 RESOLVED, 2026-04-20)

When the filing uses a quantifier for unnamed parties:

- **Exact counts:** "three parties" → 3 placeholder rows (`bidder_name`
  null, `unnamed_count_placeholder=3` info flag on the first).
- **"Several":** minimum 3. Emit 3 placeholder rows +
  `unnamed_count_placeholder=3` info flag. If a later narrative reveals a
  higher count, Austin may reconcile it during review.
- **Vague plurals** ("a number of," "a few," "multiple"): emit ONE
  placeholder row with the relevant `bid_note` and a
  `vague_plural_unnamed` info flag. Do not guess a count.
- **"Certain parties", "various parties":** same as vague plurals.

**Rationale.** This is the minimum-bias stance at 392-deal scale.
Exact-count text should be preserved exactly; `"several"` supports a
minimum of 3; vaguer plurals should not be over-atomized.

**Cross-references.**
- `prompts/extract.md` numeric-count and placeholder instructions.
- `rules/invariants.md` §P-D6 (NDA-before-Bid existence checks depend on
  placeholder rows being emitted when the filing commits to a count).

---

### §F2 — Classification rules for `bidder_type.base` (🟩 RESOLVED, 2026-04-18)

**Decision.** Accept the 8-rule decision table below. Ambiguous cases
default to `"f"` and flag.

**Decision table** (evaluate top-to-bottom; first match wins):

| # | Filing signal | `base` | Extra flags |
|---|---|---|---|
| 1 | Filing explicitly names a **PE firm / buyout fund / private-equity sponsor** as the bidder | `f` | — |
| 2 | Filing names a **publicly traded operating company** as the bidder | `s` | `public: true` |
| 3 | Point of contact is a **CEO or named corporate executive**; letterhead / counsel is corporate | `s` | — |
| 4 | Point of contact is a **partner / managing director / principal at a fund**; letterhead is fund | `f` | — |
| 5 | Consortium explicitly described as including **both** PE and strategic members | `mixed` | — |
| 6 | **Sovereign-wealth fund, pension fund, or family office** acting alone | `f` | — |
| 7 | **SPAC** (special-purpose acquisition company) | `f` | — |
| 8 | Genuinely ambiguous → default | `f` | `bidder_type_ambiguous` (soft) |

**`non_us` and `public` determination:**
- `non_us: true` iff filing states the bidder is incorporated or
  headquartered outside the US.
- `public: true` iff filing states the bidder is publicly traded. For PE
  firms, this is always `false` (PE sponsors are private). For SPACs,
  `public: true` if the SPAC is itself listed.

**Evidence requirement.** The `source_quote` on the first row for each
bidder MUST contain the filing language that supports the classification
(e.g., *"a private equity firm"*, *"a publicly traded pharmaceutical
company"*, *"a strategic acquirer in the same industry"*). If the filing
only reveals the bidder type on a later row, the classification is set
from that row going forward; earlier rows for that bidder carry
`bidder_type_provisional: true` until the evidence-bearing row resolves it.

**Why default `f` on ambiguity.** Anecdotally, when filings are coy about
bidder identity, it's usually because the bidder is a PE sponsor (operating
companies have less competitive reason to hide their name). This default
is a heuristic to be re-evaluated after the 25-deal lawyer-language study.

**Rejected alternatives.**
- **Default `s` on ambiguity** — empirically wrong direction.
- **Hard-flag all ambiguity** — creates too much manual-review burden on a
  recoverable judgment.

**Cross-references.**
- `rules/bidders.md` §F1 (structured object schema).
- `rules/bidders.md` §F3 (consortium type — `base: "mixed"`).

---

### §F1 — Bidder type canonical format (🟩 RESOLVED, 2026-04-18)

**Decision.** `bidder_type` is a **structured object** (not a string) with
three fields.

```json
"bidder_type": {
  "base": "s",
  "non_us": false,
  "public": true
}
```

**Fields.**
- `base: "s" | "f" | "mixed"` — strategic, financial, or mixed (consortium
  with both strategic and financial members).
- `non_us: bool` — true iff the filing describes the bidder as a non-US
  entity (country of incorporation or headquarters outside the US).
- `public: bool` — true iff the bidder is publicly traded at the time of
  the bid.

**Classification rules** — §F2.

**Consortium type** — `base: "mixed"` fully covers §F3. Constituent types
are still on their individual rows per atomization (§E1).

**Why structured object, not a string.**
- Downstream code never has to parse `"non_us_public_s"` strings.
- Each attribute is queryable independently (filter all financial bidders,
  filter all public bidders, filter all non-US bidders) — a common Alex-style
  analysis.
- Booleans handle the "present / absent" case cleanly; the legacy 4
  booleans (`financial`, `strategic`, `mixed`, `nonUS`) are preserved
  faithfully, with `public` added (was `public_s` / `public_f` prefix in
  legacy strings; now a standalone boolean).

**`base: "mixed"` semantics.** Used only for consortium rows when the
filing describes the consortium as having both strategic and financial
members. Individual constituent rows in a joint-bid (§E2) have their own
non-mixed `base`.

**Rejected alternatives.**
- **Strict single-token string** (`"non_us_public_s"`, …) — requires
  downstream parsing; 10+ value enum.
- **Legacy 4 booleans** — works but loses the `base` semantics; can't
  distinguish "S with F consortium member" from "pure S bidder."
- **Permissive free-form** — drift-prone; what Alex's workbook did.

**Cross-references.**
- `rules/bidders.md` §F2 (classification rules for base).
- `rules/bidders.md` §F3 (consortium type — covered by `base: "mixed"`).
- `rules/schema.md` §R1 (event-level `bidder_type` object schema).

---

### §F3 — Consortium type classification (🟩 RESOLVED, 2026-04-18)

**Decision.** Fully absorbed by §F1. A consortium row carries
`bidder_type.base = "mixed"` when its members span both strategic and
financial types. Non-mixed consortiums (all-strategic or all-financial)
take their uniform `base` value.

See `rules/bidders.md` §F1 for the structured object.

---

### §E1 — Group rows: aggregate vs atomize (🟩 RESOLVED, 2026-04-18)

**Decision.** Events are **atomized** — one row per event. A single bidder
appears on many rows (once for NDA, once per bid, once for drop, once for
execution if winner). This matches Alex's legacy format.

**Rule.**
- No aggregated per-bidder rows. No aggregated per-group rows either —
  Providence's "25 NDAs in one row" and Zep row 6390's "5 parties, 4F and
  1S" are both **expanded** during the xlsx → JSON conversion in Stage 2.
- Each atomized row carries its own `source_quote` for the specific event.
- Anonymous bidders get placeholder names per §E3.
- Joint bidders are handled per §E2.

**Why atomized.**
1. Matches the research question (event-level auction dynamics, hazard
   analysis, informal-to-formal transition).
2. Keeps `source_quote` tractable — one quote per event, not one bidder
   record referencing many passages.
3. Compatible with `BidderID` as an event-sequence number (see
   `rules/dates.md` §A).
4. Allows the validator to check per-event invariants (`NDA before bid`,
   monotone dates, etc.) without disaggregating on the fly.

**Migration note.** Providence row 6027 (25 NDAs aggregated) and Zep row
6390 (5 parties aggregated) are expanded during Stage 2 conversion.
Placeholder names follow §E3; see `reference/alex/README.md` for
the expansion procedure.

**Rejected alternatives.**
- **Aggregate by bidder** — fewer rows, but makes multi-bid trajectories
  hard to represent and breaks per-event evidence contract.
- **Hybrid (atomize named, aggregate unnamed)** — splits the schema by
  bidder identity, creating two code paths for every downstream analysis.

**Cross-references.**
- `rules/bidders.md` §E2 (joint bidders).
- `rules/bidders.md` §E3 (anonymous naming).
- `rules/events.md` §I1 (consortium-drop splitting follows the atomized rule).
- `rules/dates.md` §A (`BidderID` as event sequence).

# rules/bidders.md — Bidder Identity & Type

**Purpose.** Rules for identifying, naming, classifying, and aggregating bidders across rows of a single deal.

**Status legend:** 🟥 OPEN · 🟨 TENTATIVE · 🟩 RESOLVED

> Stage 1 is complete. Some historical dependency prose below still uses the
> word "pending" when describing how the rulebook was developed. Treat the
> section headers and `Decision:` blocks as authoritative; if a section is
> marked 🟩 RESOLVED, it is closed unless explicitly reopened.

---

## Resolved rules

### §E2 — Joint-bidder rows (🟩 RESOLVED, 2026-04-18; amended 2026-04-19 iter-4)

**Decision.** A joint bid by a consortium or pair of parties is represented
as **one row per constituent** for *Bids* and *Drops*, all sharing the
same `BidderID` and the same `bid_value*` fields. The joint-ness is
signaled by a flag. **Two exceptions** (iter-4 amendments):

1. **Executed rows are always exactly 1 per deal** (see §E2.a below;
   Class A fix).
2. **Group-narrated NDAs collapse to 1 row** when the filing does not
   give per-constituent detail (see §E2.b below; Class E fix).

**Rule (Bids and Drops — per-constituent).**
- For a single bid event submitted jointly by N parties, emit **N rows**.
- Each row's `bidder_name` is the constituent's canonical deal-local ID
  (per §E3). Each row's `bidder_alias` is the constituent's filing label.
- All N rows share the same `BidderID` (event-sequence number per
  `rules/dates.md` §A).
- All N rows carry **identical** `bid_value`, `bid_value_pershare`,
  `bid_value_lower`, `bid_value_upper`, `bid_value_unit`, `multiplier`,
  `bid_date_precise`, `bid_date_rough`, `bid_type`, `source_quote`,
  `source_page`.
- Each row carries flag `{"code": "joint_bid", "severity": "info",
  "reason": "joint bid with <other constituent canonical ids>"}`.

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

**Migration note.** The Mac-Gray and Petsmart iter-3b extractions emitted
N Executed rows (2 and 5 respectively). These fire hard on
`multiple_executed_rows`. Iter-4 extractions collapse to 1.

### §E2.b — Group-narrated NDA aggregation (🟩 RESOLVED, 2026-04-19)

**Decision.** When the filing narrates a consortium / joint-bidder NDA
as a **single group event without per-constituent detail**, emit **one**
NDA row with the consortium label. When the filing narrates each
constituent's NDA execution separately, emit per-constituent rows per
§E2's default rule.

**Rule — filing-granularity-driven.**

- **Filing narrates the NDA jointly** (e.g., *"CSC/Pamplona executed a
  confidentiality agreement on 7/11/2013"* with no separate per-party
  description): emit **ONE** `NDA` row with:
  - `bidder_alias` = the consortium label the filing uses.
  - `bidder_name` = canonical id for the consortium (new if needed).
  - `joint_bidder_members: list[str]` — canonical ids of constituents,
    when the constituents are individually named in the filing.
  - Flag `{"code": "joint_nda_aggregated", "severity": "info", "reason":
    "filing narrates consortium NDA as single group event without
    per-constituent detail"}`.

- **Filing narrates each constituent's NDA separately**: emit
  **per-constituent** NDA rows (default §E2 rule). Each row carries the
  `joint_bid` flag referencing the other constituents.

- **Filing gives a group NDA count but does not break it down** (e.g.,
  *"15 confidentiality agreements were executed by the Buyer Group"*):
  emit one row per constituent-count per §E3 (count audit), using
  §E3 placeholder aliases when individual constituents are not named.
  This is the Petsmart pattern: filing gave a count (15) without
  per-constituent detail, so emit N rows with placeholders.

**Decision tree (apply top-to-bottom; first match wins):**

1. Filing names each constituent's NDA individually → per-constituent
   rows (§E2 default).
2. Filing narrates the NDA as a consortium group event AND does not
   give a per-constituent count → ONE aggregated row with
   `joint_nda_aggregated` flag.
3. Filing gives a constituent COUNT without per-constituent narration
   → emit N rows per §E3 placeholder-count rule.

**Downstream impact on §P-D6.** `§P-D6` (NDA-before-Bid existence check)
operates on `bidder_name`. For aggregated NDA rows the consortium's own
canonical id satisfies §P-D6 for the Bid rows that also use the
consortium label as `bidder_name`. If the consortium's individual Bid
rows use constituent `bidder_name`s (per-constituent atomization), the
aggregated NDA row does NOT satisfy §P-D6 for those individual bidders;
in that case promote the aggregated NDA via an `unnamed_nda_promotion`
hint or emit per-constituent NDA rows anyway. **In practice, when the
filing aggregates the NDA, it also aggregates the Bids** (e.g., Mac-Gray
CSC/Pamplona: joint NDA, joint Bid); per-constituent atomization only
arises when the filing itself narrates constituents separately.

**Migration note.** Iter-3b AI extractions on Mac-Gray (7/11 CSC+Pamplona)
and Petsmart (10/05 Buyer Group) over-split the consortium NDA into N
per-constituent rows, violating the filing's own granularity. Iter-4
extractions follow this amended §E2.b.

**Rejected alternatives.**
- **Single row with `bidder_name = "Party E / Party F"`** — loses
  structure; can't express bidder_type cleanly; breaks with 3+ parties.
- **Structured primary/secondary columns** — hard-caps at 2 parties.
- **Synthetic consortium as first-class bidder** — inserts a
  `bidder_name` the filing never uses; violates source-quote integrity.
  (§E2.b's `bidder_alias` IS the filing's consortium label verbatim, so
  this objection does not apply.)

**Cross-references.**
- `rules/bidders.md` §E1 (atomization).
- `rules/bidders.md` §E3 (canonical IDs; consortium label registered).
- `rules/events.md` §I1 (consortium-drop splitting rule).
- `rules/invariants.md` §P-S4 (exactly-one Executed; §E2.a keeps this
  hard).
- `rules/invariants.md` §P-D6 (NDA-before-Bid; §E2.b reinforces the
  bidder-name-matching precondition).

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
- `rules/invariants.md` — new `bidder_alias_not_in_registry` check pending.

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

**Classification rules** — §F2 (pending ratification).

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
- `rules/bidders.md` §F2 (classification rules for base — pending).
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
- Anonymous bidders get placeholder names per §E3 (pending).
- Joint bidders are handled per §E2 (pending).

**Why atomized.**
1. Matches the research question (event-level auction dynamics, hazard
   analysis, informal-to-formal transition).
2. Keeps `source_quote` tractable — one quote per event, not one bidder
   record referencing many passages.
3. Compatible with `BidderID` as an event-sequence number (see
   `rules/dates.md` §A, pending).
4. Allows the validator to check per-event invariants (`NDA before bid`,
   monotone dates, etc.) without disaggregating on the fly.

**Migration note.** Providence row 6027 (25 NDAs aggregated) and Zep row
6390 (5 parties aggregated) are expanded during Stage 2 conversion.
Placeholder names follow §E3 (pending); see `reference/alex/README.md` for
the expansion procedure.

**Rejected alternatives.**
- **Aggregate by bidder** — fewer rows, but makes multi-bid trajectories
  hard to represent and breaks per-event evidence contract.
- **Hybrid (atomize named, aggregate unnamed)** — splits the schema by
  bidder identity, creating two code paths for every downstream analysis.

**Cross-references.**
- `rules/bidders.md` §E2 (joint bidders — pending).
- `rules/bidders.md` §E3 (anonymous naming — pending).
- `rules/events.md` §I1 (consortium-drop splitting follows the atomized rule).
- `rules/dates.md` §A (`BidderID` as event sequence — pending).

---

---

## Open questions

### §E1 — Group rows: aggregate vs atomize
- 🟩 **RESOLVED** — see top of this file. Atomize: one row per event. Group rows (Providence 6027, Zep 6390) expanded during xlsx → JSON conversion.

### §E2 — Joint-bidder rows
- 🟩 **RESOLVED** — see top of this file. One row per constituent; shared `BidderID`; identical `bid_value*` + `source_quote`; `joint_bid` info flag per row.

### §E3 — Anonymous bidder naming convention
- 🟩 **RESOLVED** — see top of this file. Canonical `bidder_NN` in `bidder_name`; filing label in `bidder_alias`; deal-level `bidder_registry`.

### §E4 — Winning bidder name retrofit
- 🟩 **RESOLVED** — see top of this file. No retrofit. Canonical ID stable; alias tracks per-row filing usage.

### §F1 — Bidder type canonical format
- 🟩 **RESOLVED** — see top of this file. Structured object: `{base, non_us, public}` with `base ∈ {s, f, mixed}`.

### §F2 — Classification rule for ambiguous bidders
- 🟩 **RESOLVED** — see top of this file. 8-rule decision table. Default `f` on ambiguity. Re-evaluate after 25-deal lawyer-language study.

### §F3 — Consortium type classification
- 🟩 **RESOLVED** — see top of this file. Covered by §F1: consortium row uses `bidder_type.base = "mixed"`.

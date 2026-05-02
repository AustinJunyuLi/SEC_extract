# rules/bidders.md — Bidder Identity & Type

**Purpose.** Rules for identifying, naming, classifying, and aggregating bidders across rows of a single deal.

---

## Resolved rules

### §E2 — Joint-bidder rows

**Decision.** `BidderID` is an **event-sequence number, not a bidder-
identity number**. Joint-bidder events are atomized per identifiable
constituent.

**Rule.**
- Filing names consortium constituents → emit one row per constituent.
- Each atomized row receives its own unique event-sequence `BidderID`.
- `bidder_alias` is the filing label for the constituent on that row.
- `bidder_name` is that constituent's canonical id per §E3.
- If the filing does not provide either a numeric count or identifiable
  constituent members, fail loud. Do not invent members, and do not collapse
  to a single consortium-label row as a fallback.

### §E2.b — Group-narrated event atomization

**Decision.** Filing granularity decides the shape — but every buyer-group
lifecycle event atomizes per identifiable constituent. There is no
"consortium-as-1-row" shortcut for any event type, including `NDA` and
`Executed`.

**Rule.**

| Filing narrates the event as… | Emit |
|---|---|
| Named individual signers (e.g., *"BC Partners, Caisse, GIC, … each executed CAs"*) | **N rows**, one per named signer per §E3 |
| Numeric count without names (e.g., *"15 financial sponsors executed CAs"*) | **N rows**, where N is the stated count, with `bidder_alias` placeholders (`"Strategic 1"`, `"Financial 1"`, …) per §E5 |
| Single consortium event with no per-constituent detail and no count (e.g., *"Buyer Group executed a CA on 7/11/2013"*) | **N rows** only when N identifiable consortium constituents are named elsewhere in the filing. If the filing names neither a count nor identifiable constituents, fail loud; do not invent members and do not emit a single consortium-label fallback row. |

When a target-side `NDA` is narrated at buyer-group level, emit one `NDA`
row per identifiable buyer-group constituent bound by that group status. If
a member later joins an already-NDA-bound buyer group, emit that member's
own `NDA` row dated to the join date. That row records inherited group-NDA
status; it does not assert that the late member personally signed the
original earlier agreement.

When the merger agreement is with a legal shell but the filing explicitly
identifies the operational/economic buyer consortium (e.g., petsmart's
BC Partners + Caisse + GIC + StepStone + Longview), emit one Executed row
per identified constituent, all with the same date. If the operational/
economic members are not identifiable from the filing, treat the extraction
as incomplete rather than silently creating a shell-only or consortium-label
Executed row.

Every atomized buyer-group lifecycle row, including `NDA`, `Bid`, `Drop`,
`DropSilent`, and `Executed`, carries
`{"code": "buyer_group_constituent", "severity": "info", "reason": "<short filing-grounded statement identifying this party as a buyer-group constituent>"}`.
This is the validator-visible evidence that the row is an atomized
constituent lifecycle event, not an ordinary standalone bidder row. The
`NDA` row is the auction-funnel row counted by §Scope-1; a `ConsortiumCA`
row remains only bidder-bidder confidentiality evidence and never counts
toward the auction threshold.

**Rationale.** Atomization is unconditional and applies symmetrically to NDA, Bid, Drop, Restarted, Terminated, and Executed. This matches the `DropSilent` convention (§I1) of one row per bidder.

**Cross-references.**
- §E1 (universal atomization).
- §E3 (canonical IDs / placeholders).
- §E5 (numeric-count → row-count commitment).
- `rules/events.md` §I1 (consortium-drop splitting).

---

### §E3 — Anonymous bidder naming

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

Do not substitute typed placeholders for filing labels. If the filing says
`"Party A"`, the row's `bidder_alias` is `"Party A"`, not `"Strategic Buyer
1"` or `"Financial Buyer 1"`. Use typed placeholders only for unnamed exact
counts where no filing label is available.

For consortium or buyer-group relationship rows, `bidder_alias` still names
the actor represented by `bidder_name`, not the relationship phrase. If the
filing says "Longview and the Buyer Group entered into a confidentiality
agreement" and the row represents Longview, use `bidder_alias = "Longview"`.
Preserve the full relationship language in `source_quote` and, when useful,
`additional_note`. Do not add relationship phrases to `aliases_observed`
unless the filing actually uses the phrase as that actor's standalone label.

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

### §E4 — Winning-bidder name retrofit

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

### §E5 — Unnamed-party quantifier semantics

When the filing uses a quantifier for unnamed parties:

- **Exact counts:** "three parties" → 3 placeholder rows with stable
  deal-local aliases (`bidder_name = null`, `unnamed_count_placeholder=3`
  info flag on the first).
- **"Several":** minimum 3. Emit 3 placeholder rows +
  `unnamed_count_placeholder=3` info flag. If a later narrative reveals a
  higher count, Austin may reconcile it during review.
- **Vague plurals** ("a number of," "a few," "multiple"): emit ONE
  placeholder row with the relevant `bid_note` and a
  `vague_plural_unnamed` info flag. Do not guess a count.
- **"Certain parties", "various parties":** same as vague plurals.

**Stable exact-count handles.** Exact-count unnamed aliases are lifecycle
handles, not disposable labels. If an NDA passage creates
`"Other NDA Signer 1"` through `"Other NDA Signer 18"`, later unnamed
`Bid`, `Drop`, `DropSilent`, or `Executed` rows for that same cohort must
reuse those aliases. Do not switch to a second alias family such as
`"Potential Buyer 1"` through `"Potential Buyer 18"` for later events in
the same cohort.

If a later unnamed subset is countable but still unidentified, allocate the
subset to the lowest-numbered compatible open placeholders and attach
`{"code": "anonymous_subset_allocation", "severity": "info", "reason": "<short filing-grounded allocation note>"}`.
If the filing is genuinely unclear whether the later unnamed group is the
same cohort or a new cohort, attach `anonymous_cohort_identity_ambiguous`
with hard or soft severity as warranted. Do not silently invent a second
alias family while compatible unnamed NDA handles remain available.

Buyer-group atomization can make row counts diverge from filing party counts.
For example, a filing may count a buyer group as one "party" while the schema
atomizes some buyer-group constituents into separate rows. In that case, do
not create fresh anonymous aliases merely to make later "all parties" or
"non-submitters" arithmetic balance. Reuse compatible open NDA handles first.
If the remaining lifecycle row is genuinely unclear because the filing's
party count cannot be reconciled with atomized rows, attach
`anonymous_cohort_identity_ambiguous` to that row rather than silently
inventing another anonymous alias family.

Never emit an unnamed lifecycle row (`Bid`, `Drop`, `DropSilent`, or
`Executed`) for a numbered alias that lacks a prior same-phase `NDA` handle.
When a later count appears to exceed the available open NDA handles, emit
only rows supported by existing handles and attach
`anonymous_cohort_identity_ambiguous` where the filing-grounded cohort
boundary is unclear. Do not create aliases such as `"Financial Buyer 13"`
through `"Financial Buyer 15"` unless those aliases were created by earlier
same-phase NDA rows.

**Rationale.** This is the minimum-bias stance at 392-deal scale.
Exact-count text should be preserved exactly; `"several"` supports a
minimum of 3; vaguer plurals should not be over-atomized. Stable handles
preserve the lifecycle link from NDA to later bidder activity without
pretending that the filing revealed real identities.

**Cross-references.**
- `prompts/extract.md` numeric-count and placeholder instructions.
- `rules/invariants.md` §P-D6 (NDA-before-Bid existence checks depend on
  placeholder rows being emitted when the filing commits to a count).

---

### §F1 — Bidder type canonical format

**Decision.** `bidder_type` is a **scalar string** (not an object) holding one of two values: `"s"`, `"f"`, or `null`.

```json
"bidder_type": "s"
```

**Values.**
- `"s"` — strategic. Filing names a corporate operating buyer (active in target's industry or adjacent).
- `"f"` — financial. Filing names a private-equity firm, buyout fund, sovereign-wealth fund, family office, pension fund, or SPAC.
- `null` — filing does not classify.

**Why scalar, not structured object.** Geography and capital structure of the bidding firm are not recorded; with one axis remaining, the object shape is dead weight and the scalar is direct.

**Decision rule** (evaluate top-to-bottom; first match wins):

| # | Filing signal | `bidder_type` |
|---|---|---|
| 1 | Filing explicitly names a **PE firm / buyout fund / private-equity sponsor** as the bidder | `"f"` |
| 2 | Filing names a **publicly traded operating company** as the bidder | `"s"` |
| 3 | Point of contact is a **CEO or named corporate executive**; letterhead / counsel is corporate | `"s"` |
| 4 | Point of contact is a **partner / managing director / principal at a fund**; letterhead is fund | `"f"` |
| 5 | **Sovereign-wealth fund, pension fund, or family office** acting alone | `"f"` |
| 6 | **SPAC** (special-purpose acquisition company) | `"f"` |
| 7 | Genuinely ambiguous → default | `"f"` + `bidder_type_ambiguous` (soft flag) |

Consortium mixedness is not a row-level `bidder_type` value. Under §E2.b,
identifiable consortium constituents are atomized and each constituent row
gets `"s"` or `"f"` as applicable. A deal-level mixed-consortium property is
recoverable downstream by grouping the atomized winner or bidder rows.

**Why default `"f"` on ambiguity.** Anecdotally, when filings are coy about bidder identity, it's usually because the bidder is a PE sponsor. Operating companies have less competitive reason to hide their name.

**Rejected alternatives.**
- **Default `"s"` on ambiguity** — empirically wrong direction.
- **Hard-flag all ambiguity** — creates too much manual-review burden on a recoverable judgment.

**Cross-references.**
- `rules/schema.md` §R1 — event-level `bidder_type` field signature.
- `rules/bidders.md` §E1 (atomization), §E3 (canonical IDs).

---

### §F3 — Consortium type classification

**Decision.** Fully absorbed by §F1 and §E2.b. Consortium rows are atomized
per identifiable constituent; no row-level mixed value exists.

See `rules/bidders.md` §F1 for the scalar format.

---

### §E1 — Group rows: aggregate vs atomize

**Decision.** Events are **atomized** — one row per event. A single bidder
appears on many rows (once for NDA, once per bid, once for drop, once for
execution if winner).

**Rule.**
- Atomization is **unconditional**. There are no exceptions — NDA, Bid, Drop, DropSilent, Restarted, Terminated, AND Executed all atomize one row per bidder.
- No aggregated per-bidder rows. No aggregated per-group rows.
- Each atomized row carries its own `source_quote` for the specific event.
- Anonymous bidders get placeholder names per §E3.
- Joint bidders are handled per §E2 (every constituent gets its own row).

**Why atomized.**
1. Matches the research question (event-level auction dynamics, hazard
   analysis, informal-to-formal transition).
2. Keeps `source_quote` tractable — one quote per event, not one bidder
   record referencing many passages.
3. Compatible with `BidderID` as an event-sequence number (see
   `rules/dates.md` §A).
4. Allows the validator to check per-event invariants (`NDA before bid`,
   monotone dates, etc.) without disaggregating on the fly.

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

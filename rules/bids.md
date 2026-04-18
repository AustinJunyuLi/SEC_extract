# rules/bids.md — Bids, Values, Classification, Skip Rules

**Purpose.** How to record a bid row: value structure (ranges, composite, aggregate), informal-vs-formal classification, and what not to record at all.

**This is the most subjective file in the rulebook.** Informal-vs-formal is the highest-risk classification in the whole pipeline. Treat every borderline call as a flag, not a forced choice.

**Status legend:** 🟥 OPEN · 🟨 TENTATIVE · 🟩 RESOLVED

---

## Resolved rules

### §G1 — Informal-vs-formal bid classification (🟩 RESOLVED, 2026-04-18)

**This is the highest-risk classification in the pipeline.** It is also
subject to revision based on the 25-deal lawyer-language study; the rules
below are the MVP baseline.

**Decision.** A bid is classified by the **strongest signal** in the
filing passage describing it, evaluated against the trigger tables below.
Where no trigger fires, fall back to process-position heuristics. Where
still ambiguous, emit `bid_type = null` + hard flag.

**Formal triggers** (any → `bid_type = "formal"`):
- *"binding offer"*, *"binding proposal"*, *"binding bid"*
- *"executed commitment letters"* or *"financing commitments"* (debt + equity)
- *"fully financed"*, *"no financing contingency"*
- *"definitive agreement submitted"* or a draft merger agreement included
  with the bid
- *"final bid"*, *"best and final"*
- *"markup of the merger agreement"*
- Bid submitted in direct response to a **"process letter"** or an
  explicit final-round invitation (§K2)

**Informal triggers** (any → `bid_type = "informal"`):
- *"non-binding indication of interest"*, *"preliminary indication"*
- *"expression of interest"*
- *"indicative offer"*, *"indicative proposal"*
- *"subject to due diligence"* (without financing commitments)
- *"preliminary proposal"*
- **Structural signal: bid is stated as a range** (`bid_value_lower` and
  `bid_value_upper` both populated) — Austin's heuristic. Range-valued
  bids are almost always informal; if a range coexists with a formal
  trigger, the formal trigger wins but flag
  `range_with_formal_trigger` (soft) for manual review.

**Process-position fallback** (no explicit trigger present):
- Bid submitted in response to `Final Round Ann` / `Final Round Inf Ann`
  (§C1) → matches the announcing phase:
  - `Final Round Ann` → `formal`
  - `Final Round Inf Ann` → `informal`
- Bid submitted **before** any round structure is established (initial
  approach, pre-NDA or pre-process-letter) → `informal`.
- Topping bid submitted post-`Executed` under go-shop provisions → `formal`
  (go-shop topping bids require binding terms).

**When still ambiguous.** Emit `bid_type = null` + hard flag
`informal_vs_formal_ambiguous` with the `source_quote` that caused the
ambiguity. The row is still emitted; downstream research filters on
non-null `bid_type`.

**Stress-test plan.** The 25-deal lawyer-language study (deferred to
post-Stage-1) will audit §G1 against a broader corpus. Expected revisions:
more trigger phrases, refined process-position heuristics, possibly a
formal/informal scoring function rather than first-match.

**Rejected alternatives.**
- **Trigger tables only, no fallback** — undercounts formal bids in clean
  auctions where process letters set expectations implicitly.
- **Default `informal` when ambiguous** — biases estimates; the null +
  flag is more honest.

**Cross-references.**
- `rules/bids.md` §G2 (evidence requirement).
- `rules/bids.md` §H1 (range structure → informal heuristic).
- `rules/events.md` §K2 (implicit final rounds → `formal` process position).
- `rules/events.md` §C1 (final-round vocabulary).

---

### §G2 — Classification evidence requirement (🟩 RESOLVED, 2026-04-18)

**Decision.** Hard invariant. Every row with non-null `bid_type` MUST
satisfy at least one of:

1. `source_quote` contains at least one trigger phrase from §G1's formal
   or informal trigger tables. (Structural signal — range bid — qualifies
   without a textual phrase.)
2. The row carries `bid_type_inference_note: str` (≤ 200 chars) explaining
   the process-position inference (e.g., *"submitted in response to
   Final Round Ann row #12; classified formal per §G1 process-position
   fallback"*).

**Validator.** `rules/invariants.md` adds check §P-R* (pending numbering):
for every row with non-null `bid_type`, verify one of the above holds.
Violations → hard flag `bid_type_unsupported`.

**Why hard.** Informal-vs-formal is the core research variable. Manual
verification of 401 deals × ~5 bids each = ~2000 classifications is
intractable without per-row evidence. Soft flagging would let silent drift
accumulate.

**Cross-references.**
- `rules/bids.md` §G1 (classification rule).
- `rules/invariants.md` — new §P-R check pending.
- `SKILL.md` non-negotiable rule #5 (already mandates evidence citation).

---

### §H2 — Composite consideration (🟩 RESOLVED, 2026-04-18)

**Decision.** Extend the event schema with **component-level fields** for
cash, stock, and contingent consideration. Headline `bid_value_pershare`
is the sum of components valued at the bid date.

**New per-row fields:**
- `cash_per_share: float | null` — cash component.
- `stock_per_share: float | null` — stock component, valued at the bid date
  using the acquirer's closing price or the exchange-ratio-implied value
  stated in the filing.
- `contingent_per_share: float | null` — CVR, earnout, escrow, or any
  contingent component.
- `consideration_components: list[str]` — ordered list of components
  present. Allowed values: `["cash"]`, `["cash", "stock"]`,
  `["cash", "cvr"]`, `["cash", "earnout"]`, `["cash", "stock", "cvr"]`,
  `["stock"]`, `["stock", "cvr"]`, etc.

**Invariants.**
- `bid_value_pershare` = `cash_per_share` + `stock_per_share` + `contingent_per_share`
  (treating nulls as 0). If the filing states a headline that doesn't
  reconcile, keep the filing's headline in `bid_value_pershare` and flag
  `composite_reconciliation_mismatch` (soft) with the arithmetic detail.
- Pure-cash bids: `consideration_components = ["cash"]`;
  `cash_per_share = bid_value_pershare`; `stock_per_share = null`;
  `contingent_per_share = null`. (Most reference-deal bids.)
- Range bids with composite structure: populate `cash_per_share_lower` /
  `cash_per_share_upper` etc. only IF the filing ranges each component
  separately; otherwise keep the range in `bid_value_lower` / `upper` and
  note the composite breakdown in `additional_note`.

**`all_cash` deal-level derivation (§N2 cross-reference).**
`deal.all_cash = true` iff EVERY bid event row has
`consideration_components == ["cash"]`. Any bid with a non-cash component
→ `all_cash = false`.

**CVR vs earnout.** If the filing uses "contingent value right" or "CVR,"
use `"cvr"`. If it uses "earnout" or "contingent consideration based on
milestones," use `"earnout"`. If the filing is agnostic, default to
`"cvr"` and flag `contingent_type_ambiguous` (info).

**Stock-per-share valuation.** Filings typically state the exchange ratio
("0.25 shares of Acquirer stock per Target share") and the implied value
at the signing date ("$15.30 based on Acquirer's closing price of
$61.20"). Use the filing-stated implied value for `stock_per_share`;
record the exchange ratio in `additional_note` as
`exchange_ratio: <float>`.

**Legacy migration.** Alex's `comments_1` entries like "20.02 cash + 1.13
CVR" are parsed into components during xlsx → JSON conversion.

**Rejected alternatives.**
- **Single value + structured note string** — still requires downstream
  parsing; error-prone.
- **Single value + free text comments** — current practice; makes
  composite bids unanalyzable without NLP.

**Cross-references.**
- `rules/schema.md` §R1 (event-level field additions).
- `rules/schema.md` §N2 (`all_cash` derivation).
- `rules/bids.md` §H1 (range structure).
- `rules/bids.md` §H4 (aggregate-dollar bids — interacts for mixed-stock deals).

---

### §H3 — Partial-company bids (🟩 RESOLVED, 2026-04-18)

**Decision.** Clean segment/region/business-unit bids are **silently
skipped** with an info flag. Ambiguous cases (all-assets, majority-stake,
two-step proposals) are **surfaced with a soft flag** for manual review
rather than silently emitted or silently skipped.

**Skip unambiguous partial bids.** Filing language such as:
- *"for the Company's business in the United Kingdom and Europe"*
- *"for the [Division Name] operations"*
- *"for the [region] assets"*
- *"for a [percentage <50%] interest"* (minority stake)

→ Do NOT emit a bid row. Emit a deal-level flag (or a "skipped-bid"
registry entry) `{"code": "partial_bid_skipped", "severity": "info",
"reason": "<summary>", "source_quote": "<quote>", "source_page": <N>}`
so the pattern is auditable.

**Flag ambiguous cases for review.** Filing language such as:
- *"for all of the Company's operating assets"* (effectively whole
  company, but worded differently — could be asset sale vs stock sale)
- *"for a majority interest"* or *"for approximately [51–80]%"*
  (majority stake — is this a takeover bid?)
- Two-step proposals (*"first for Division X, then for the remainder"*)

→ Do NOT emit a bid row. Emit a deal-level flag
`{"code": "partial_bid_ambiguous", "severity": "soft", "reason": "<description>", "source_quote": "<quote>"}`
requiring manual adjudication. Austin reads the filing and decides
whether to add the bid row manually in Stage 3 verification.

**Rationale for skip-not-flag on clean segments.** Segment bids are
explicitly out of scope per Alex's instructions; surfacing every one as
soft would drown the flag queue. Info-level is enough for audit.

**Rejected alternatives.**
- **Always skip, never flag ambiguous cases** — loses the "is this a
  takeover bid?" adjudication opportunity.
- **Always emit; filter downstream** — pollutes the dataset with rows
  that have no research meaning.

**Cross-references.**
- `rules/bids.md` §M (skip rules — related "unsolicited no-NDA" skip).
- `rules/invariants.md` — new partial-bid flag invariant pending.

---

### §H4 — Aggregate-dollar bids (🟩 RESOLVED, 2026-04-18)

**Decision.** Emit the aggregate value as-is in `bid_value` +
`bid_value_unit = "USD"`. Populate `bid_value_pershare` **only if the
filing itself states the per-share equivalent alongside the aggregate**.
No extraction-time arithmetic from inferred share counts.

**Field semantics.**

| Bid shape | `bid_value` | `bid_value_pershare` | `bid_value_unit` | `aggregate_basis` |
|---|---|---|---|---|
| Per-share only (*"$45 per share"*) | null | 45 | `"USD_per_share"` | null |
| Aggregate only (*"$10 billion"*) | 10_000_000_000 | null | `"USD"` | `"enterprise_value"` / `"equity_value"` / `"purchase_price"` / null |
| Aggregate + filing-stated per-share (*"$10 billion, or $45 per share"*) | 10_000_000_000 | 45 | `"USD"` | from filing |
| Non-USD (*"€5 billion"*) | 5_000_000_000 | null | `"EUR"` | from filing |

**New field.** `aggregate_basis: str | null`. Values: `"enterprise_value"`,
`"equity_value"`, `"purchase_price"`, or `null` if the filing doesn't
distinguish. Only populated when `bid_value` is aggregate.

**Explicit non-policy.** The extractor does NOT divide aggregate by shares
outstanding. `cshoc` is out of scope for the AI (§Scope-3); any
aggregate-to-per-share conversion happens downstream where COMPUSTAT data
is available.

**Why filing-stated per-share only.** Filings frequently state both
(*"enterprise value of $10 billion, or $45 per share"*) — capture both
when available. But AI-inferred per-share from statement share counts
introduces rounding and definitional errors (basic vs diluted, treasury
shares, etc.); leave that to downstream processing.

**Rejected alternatives.**
- **AI computes per-share from filing's share statements** — error-prone;
  creates silent data-quality issues.
- **Aggregate only; per-share always null** — drops usable filing-stated
  per-share data.

**Cross-references.**
- `rules/schema.md` §R1 (new field `aggregate_basis`).
- `rules/schema.md` §Scope-3 (`cshoc` out of scope).
- `rules/bids.md` §H1 (value-field invariants).

---

### §H5 — Bid revisions (🟩 RESOLVED, 2026-04-18)

**Decision.** Each bid revision is a **separate event row** — same
`bidder_name` (canonical ID per §E3), new `BidderID` (event sequence),
chronological date. No explicit revision-linking field.

**Rationale.** Revisions chain naturally via `groupby(bidder_name)` +
chronological `BidderID`. An explicit `revises_row_index: int` field
would be:
- Redundant (the chain is already reconstructible from sorts).
- Fragile (row indices shift on reordering).
- Ambiguous for non-linear histories (withdrawal + re-bid at a different
  level).

**Examples.**
- Medivation: Pfizer revises $58.50 → $71 → $81.50. Three separate bid
  event rows, same `bidder_name = "bidder_01"`, ascending `BidderID`
  and bid dates. Trajectory reconstructs on groupby.
- Withdrawal-and-return: bidder drops at price X, later re-engages with
  new bid at price Y. The `Drop` row sits between the two bids;
  `bidder_reengagement` info flag (§I2) fires on the post-drop bid.

**Validator.** `rules/invariants.md` adds a soft check: for any bidder
with >1 bid row, bids are chronologically ordered by `bid_date_precise`
(when present); violations flag `bid_revision_out_of_order`.

**Rejected alternatives.**
- **Amend the original row in place** — destroys revision history, which
  IS the research question.
- **Explicit `revises_row_index`** — no analytical gain; maintenance burden.

**Cross-references.**
- `rules/bidders.md` §E3 (canonical bidder ID).
- `rules/events.md` §I2 (re-engagement flag).
- `rules/dates.md` §A (`BidderID` as event sequence — pending).

---

### §O1 — Process-condition structured columns (🟩 RESOLVED, 2026-04-18)

**Decision.** Promote the most research-relevant process conditions to
structured columns; keep the long tail in `process_conditions_note` free
text.

**New deal-level fields (deal object per §R1):**

| Field | Type | Semantics |
|---|---|---|
| `go_shop_days` | int \| null | Go-shop duration in days, parsed from the merger agreement. Null if no go-shop. |
| `termination_fee` | float \| null | Target termination fee in USD. Null if not stated. |
| `reverse_termination_fee` | float \| null | Acquirer reverse termination fee in USD. Null if not stated. |
| `termination_fee_pct` | float \| null | Target termination fee as % of deal value, when the filing states it. |

**New event-level fields (on bid rows per §R1):**

| Field | Type | Semantics |
|---|---|---|
| `exclusivity_days` | int \| null | Exclusivity period granted to this bidder at this bid event, in days. |
| `financing_contingent` | bool \| null | True iff bid is subject to financing contingency. Null if filing silent. |
| `highly_confident_letter` | bool | True iff bid includes a "highly confident" letter from a financing bank. Default false. |
| `process_conditions_note` | str \| null | Free text for conditions not captured above (regulatory, no-solicitation, DD duration, etc.). |

**Extraction rules.**
- `go_shop_days` and termination fees are extracted from the merger
  agreement summary section (usually right after the Background). The AI
  reads both Background and merger-agreement-summary when populating deal-
  level fields.
- `exclusivity_days` is only set on the bid row where exclusivity is
  granted; it's implicitly still active on subsequent rows for the same
  bidder until the exclusivity period expires (not re-stated).
- `financing_contingent` = true when filing says "subject to financing,"
  "subject to satisfactory financing arrangements," etc. False when
  filing says "fully financed," "no financing contingency," "executed
  commitment letters delivered." Null when silent.

**Interaction with §G1.**
- `financing_contingent = false` + `highly_confident_letter = true` is a
  common signal for `bid_type = "formal"` (per §G1 trigger table).
- `highly_confident_letter` alone (without financing commitments) is a
  weaker formal signal; the §G1 rule reads "fully financed" OR "executed
  commitment letters" OR the highly-confident-letter pattern.

**Migration note.** Alex's `comments_2` entries like "Exclusivity 30 days"
are parsed into `exclusivity_days: 30` during xlsx → JSON conversion.
"Go-shop 30 days" → `go_shop_days: 30`. "No financing condition" →
`financing_contingent: false`. Residual free text → `process_conditions_note`.

**Rejected alternatives.**
- **Free text only** — makes these unanalyzable without NLP. Exclusivity
  and go-shop are core auction-dynamics covariates.
- **Every condition as a column** — bloats the schema; regulatory
  requirements and no-solicitation terms are rarely analyzed.

**Cross-references.**
- `rules/schema.md` §R1 (field list).
- `rules/bids.md` §G1 (informal-vs-formal triggers).
- `rules/events.md` §C1 (dropped `Exclusivity 30 days` event; re-encoded
  as `exclusivity_days` here).

---

### §M1 — Unsolicited-no-NDA skip (🟩 RESOLVED, 2026-04-18)

**Decision.** Skip any party mentioned in the filing when **all three** of
the following hold:

1. No NDA is signed by the party.
2. No price (point, range, or per-share) is stated.
3. No clear bid intent ("offered," "proposed," "agreed to consider,"
   "expressed willingness to submit") is stated.

No event row emitted. Deal-level flag added:
`{"code": "unsolicited_letter_skipped", "severity": "info",
"reason": "<summary>", "source_quote": "<quote>", "source_page": <N>}`.

**Why skip.** Drive-by unsolicited letters are out of scope per Alex's
instructions; they are not part of the auction process. The deal-level
flag preserves the audit trail so Austin can verify the skip was correct.

**When NOT to skip** (even without NDA / price):
- Party is mentioned as part of a **consortium** that later signed NDAs —
  handled via §E2 joint-bidder rule.
- Party signed an NDA (Condition 1 fails) — the §I1 implicit-drop rule
  applies.
- Party stated bid intent without price (Condition 3 fails) — emit
  `Bidder Interest` row with `bid_value_unspecified` flag per §H1.

**Migration note.** Saks row 7013 (Company H, Alex-flagged "should be
deleted: unsolicited letter, no NDA, no further contact, no price per
share") matches this skip rule. Drop during xlsx → JSON conversion; emit
deal-level flag.

**Rejected alternatives.**
- **Emit as `Bidder Interest` with flags** — pollutes the dataset with
  drive-by letters; breaks the auction-participant count.

**Cross-references.**
- `rules/events.md` §D1 (`Bidder Interest` criteria).
- `rules/events.md` §I1 (implicit drops for NDA signers).

---

### §M2 — No-bid-intent skip (🟩 RESOLVED, 2026-04-18)

**Decision.** Folded into §I1's **implicit-drop rule**. No separate skip.

**Rule.** A party that signs an NDA but never submits a bid, drops, or
otherwise engages further → emit an NDA row + an implicit `Drop` row (per
§I1). Do NOT skip; do NOT omit the NDA.

Rationale: the §Scope-1 auction classifier counts non-advisor bidder NDAs.
A party that signed an NDA with bid intent, even without a submitted bid,
is a meaningful auction participant. The implicit-drop row ensures the
NDA-to-drop 1:1 mapping (§P-D6 invariant) stays intact.

**Saks row 7015 (Sponsor A/E) migration note.** Alex flagged this as "not
a separate bid, should be deleted." Under this rule: if the row
represents non-bid activity by an NDA signer, replace with an NDA row +
implicit Drop row during conversion. If it represents an activity of a
party that never signed an NDA, apply §M1 skip.

**Rejected alternatives.**
- **Skip entirely (no NDA, no drop)** — drops the NDA-signer from the
  auction count; silently breaks §Scope-1.
- **Emit NDA only (no drop)** — breaks NDA-to-drop mapping (§P-D6).

**Cross-references.**
- `rules/events.md` §I1 (implicit drops).
- `rules/schema.md` §Scope-1 (auction classifier).

---

### §M3 — Advisor NDA disambiguation (🟩 RESOLVED, 2026-04-18)

**Decision.** Every event row carries a new **`role`** field. Default
value `"bidder"`. Advisor NDAs use `role = "advisor_financial"` or
`role = "advisor_legal"`. The auction classifier (§Scope-1) counts only
rows with `role == "bidder"`.

**New per-row field.** `role: "bidder" | "advisor_financial" | "advisor_legal"`
— defaults to `"bidder"` on every event row.

**Assignment rules.**

| Filing signal | `role` |
|---|---|
| Counterparty named as a potential acquirer / transaction counterparty | `"bidder"` |
| Counterparty is an **investment bank pitching for an engagement** with the target | `"advisor_financial"` |
| Counterparty is an **IB that is subsequently retained** (§J1 `IB` row) | `"advisor_financial"` |
| Counterparty is a **law firm** being vetted as legal advisor | `"advisor_legal"` |
| Accounting / valuation advisor | `"advisor_financial"` (same bucket as IB for filtering) |

**On `IB` event rows specifically.** `role = "advisor_financial"` always.
This is a sanity alignment — the event type `IB` already signals advisor
status; the `role` field makes it queryable uniformly with advisor NDA
rows.

**Auction classifier update.** `rules/schema.md` §Scope-1's NDA count is
now formally:
`count({row ∈ events : row.bid_note == "NDA" AND row.role == "bidder" AND row.process_phase ≥ 1})`.

**`bidder_type` interaction.** Advisor rows (`role != "bidder"`) have
`bidder_type = null`. The `bidder_type` classification (§F1/§F2) applies
only to bidders. A validator check catches violations.

**Rejected alternatives.**
- **Use `bidder_type.base = "advisor"`** — overloads the type field,
  conflates identity (advisor vs bidder) with classification (strategic
  vs financial).
- **Skip advisor NDAs entirely** — loses useful retention data that Alex
  explicitly records (financial advisor NDAs are in his workbook).

**Cross-references.**
- `rules/schema.md` §R1 (new event-level field `role`).
- `rules/schema.md` §Scope-1 (auction-classifier filter on `role`).
- `rules/events.md` §J1 (`IB` events always `role = "advisor_financial"`).
- `rules/bidders.md` §F1 (`bidder_type` applies only when `role == "bidder"`).

---

### §M4 — Stale-process NDA handling (🟩 RESOLVED, 2026-04-18)

**Decision.** An NDA that spans a stale-to-current transition (revival
case) is recorded as **two NDA events** — one in `process_phase = 0` for
the original signing, one in `process_phase = 1` (or higher) for the
revival.

**Rule.**
- Original NDA signing in a prior stale process → `NDA` row with
  `process_phase = 0`. Counted in no auction.
- If the same NDA is explicitly **revived / still-binding** when the
  bidder re-engages in the current process → second `NDA` row with:
  - `process_phase` matching the current process (1 or 2).
  - `bid_date_precise` = date of re-engagement / revival acknowledgement.
  - Flag `{"code": "nda_revived_from_stale", "severity": "info", "reason": "revives NDA originally signed on <date>"}`.
- If the bidder re-engages without an explicit NDA revival (filing
  silent), emit only the phase-1 `Bidder Interest` / `Bidder Sale` row per
  §D1 and flag `nda_revival_unclear` (soft).
- If the bidder signs a **new** NDA in the current process (common), emit
  only the current-process NDA at `process_phase = 1`; the old stale NDA
  is a separate row with `process_phase = 0`.

**Rationale.**
- Preserves the 2007/2009 record (matches Alex's Penford inclusion).
- Auction classifier (§Scope-1) correctly counts the revived bidder as a
  current-process NDA signer.
- §P-D6 (NDA-to-drop mapping) operates within a single `process_phase`.

**Rejected alternatives.**
- **Single NDA in phase 1** (drop the 2007/2009 record) — loses history.
- **Single NDA in phase 0** (ignore revival) — undercount current-process
  NDAs; §Scope-1 misses revived bidders.

**Cross-references.**
- `rules/events.md` §L1 (prior-process inclusion).
- `rules/events.md` §L2 (`process_phase` field).
- `rules/schema.md` §Scope-1 (auction classifier).

---

### §H1 — Bid value ranges and single-bound bids (🟩 RESOLVED, 2026-04-18)

**Decision.** Ranges populate `bid_value_lower` and `bid_value_upper`;
single-bounds populate only the stated side; unspecified-price bids
populate neither but still emit a row with a flag.

**Rules.**

| Bid shape | `bid_value_pershare` | `bid_value_lower` | `bid_value_upper` | Flag |
|---|---|---|---|---|
| Point value (*"$45 per share"*) | 45 | null | null | — |
| Range (*"$42 to $48 per share"*) | null | 42 | 48 | `bid_range` (info) |
| Single lower bound (*"at least $45"*) | null | 45 | null | `bid_lower_only` (info) |
| Single upper bound (*"up to $50"*) | null | null | 50 | `bid_upper_only` (info) |
| Unspecified (*"willing to bid but did not state a price"*) | null | null | null | `bid_value_unspecified` (info) |

**Key invariants.**
- Exactly one of `{pershare, (lower, upper), (lower only), (upper only), all-null}`
  is populated per bid row.
- Midpoints are NOT computed at extraction time. Downstream analysis can
  derive `(lower + upper) / 2` when needed; the raw range is preserved.
- Unspecified-price rows still emit — the bid *event* occurred (the bidder
  expressed intent), even without a number. The `source_quote` must
  contain the non-number language (e.g., *"declined to specify a price"*).

**Cross-reference to §G1.** Range-valued bids are a structural signal of
`informal` per §G1 (Austin's heuristic).

**Aggregate-dollar bids** (*"$1.2 billion enterprise value"*) — handled
separately in §H4, which uses `bid_value` + `bid_value_unit` instead of
the per-share fields.

**Legacy migration.** Alex's workbook practice varies: sometimes
`bid_value_pershare` is set to the lower bound on range bids, sometimes
to the midpoint, sometimes left as `NA`. During xlsx → JSON conversion,
relabel per the table above and flag any divergent legacy rows as
`legacy_bid_value_reinterpreted` (info).

**Rejected alternatives.**
- **Populate midpoint in `bid_value_pershare` on ranges** — loses the
  range; also mixes derived with raw data.
- **Add a `bid_value_bound_type` enum** — redundant with the populated-
  field pattern; downstream code checks which fields are non-null anyway.

**Cross-references.**
- `rules/bids.md` §G1 (range → informal).
- `rules/bids.md` §H2 (composite consideration — pending).
- `rules/bids.md` §H4 (aggregate-dollar bids — pending).
- `rules/schema.md` §R1 (event-level value fields).

---

---

## Open questions

### §G1 — The informal-vs-formal call
- 🟩 **RESOLVED** — see top of this file. Trigger tables + process-position fallback + range-implies-informal heuristic. To be stress-tested against 25-deal lawyer-language study.

### §G2 — Evidence requirement for classification
- 🟩 **RESOLVED** — see top of this file. Hard invariant: every non-null `bid_type` requires a trigger phrase in `source_quote` OR a `bid_type_inference_note`.

### §H1 — Ranges and single-bound bids
- 🟩 **RESOLVED** — see top of this file. Ranges populate both bounds; single-bounds populate one side; unspecified-price still emits a row with flag.

### §H2 — Composite consideration
- 🟩 **RESOLVED** — see top of this file. Component fields (`cash_per_share`, `stock_per_share`, `contingent_per_share`, `consideration_components`). Headline = sum.

### §H3 — Entire-company vs partial bids
- 🟩 **RESOLVED** — see top of this file. Silent skip + info flag on clean segments; soft flag for manual review on ambiguous (all-assets, majority-stake, two-step).

### §H4 — Aggregate-dollar bids
- 🟩 **RESOLVED** — see top of this file. Emit aggregate in `bid_value` + `bid_value_unit = "USD"`. Populate `bid_value_pershare` only if filing states it. New `aggregate_basis` field.

### §H5 — Bid revisions
- 🟩 **RESOLVED** — see top of this file. Each revision = separate event row. Chain via `bidder_name` + chronology.

---

## Skip rules (§M — what NOT to record)

### §M1 — Unsolicited letters with no NDA
- 🟩 **RESOLVED** — see top of this file. Skip when all three: no NDA + no price + no bid intent. Deal-level info flag.

### §M2 — Non-bid activity mistakenly recorded
- 🟩 **RESOLVED** — see top of this file. Folded into §I1 implicit-drop rule. No separate skip.

### §M3 — Advisor NDAs
- 🟩 **RESOLVED** — see top of this file. New per-row `role` field (`"bidder" | "advisor_financial" | "advisor_legal"`); auction classifier filters `role == "bidder"`.

### §M4 — Stale-process confidentiality agreements
- 🟩 **RESOLVED** — see top of this file. Two NDA events on revival: phase 0 original + phase 1 revival with `nda_revived_from_stale` flag.

---

## Process conditions (§O)

### §O1 — Which process conditions become structured columns
- 🟩 **RESOLVED** — see top of this file. Structured: `go_shop_days`, `termination_fee(_pct)`, `reverse_termination_fee` (deal); `exclusivity_days`, `financing_contingent`, `highly_confident_letter`, `process_conditions_note` (event). Long tail in `process_conditions_note`.

# rules/bids.md — Bids, Values, Classification, Skip Rules

**Purpose.** How to record a bid row: value structure (ranges, composite, aggregate), informal-vs-formal classification, and what not to record at all.

**This is the most subjective file in the rulebook.** Informal-vs-formal is the highest-risk classification in the whole pipeline. Treat every borderline call as a flag, not a forced choice.

---

## Resolved rules

### §C4 — Pre-NDA informal bid classification (🟩 RESOLVED, 2026-04-19)

**Decision.** When a prospective bidder communicates a **concrete price
indication** (point, range, or "at least $X") to the target BEFORE
signing an NDA, emit a `Bid` row (per §C3) with `bid_type = "informal"`
and attach the `pre_nda_informal_bid` flag. The flag is
**documentation-only**: it records the pre-NDA timing for research and
adjudication, but it does NOT trigger a validator carve-out.

**Rule.**
- `bid_note = "Bid"` (per §C3; unified bid vocabulary).
- `bid_type = "informal"` (filing-pre-NDA concrete-price signals are
  non-binding by construction; they can never carry the formal triggers
  from §G1's formal table — no commitment letters, no process-letter
  context, no markup of a merger agreement).
- Flag:
  ```json
  {"code": "pre_nda_informal_bid", "severity": "info",
   "reason": "<short summary — e.g., 'Hudson's Bay communicated $15.50-17.00/share indication on 4/15/2013; NDA executed 5/03/2013'>"}
  ```
- Evidence requirement: `source_quote` must contain BOTH the concrete
  price AND the pre-NDA context (either an explicit statement that
  no NDA was yet in place, OR the NDA row appears later in the filing
  timeline).

**§P-D6 interaction.** §P-D6 is an EXISTENCE check ("the bidder has an
NDA row somewhere in the same phase"), not an ORDERING check. Under
§C4, the bidder signs an NDA LATER in the same phase. §P-D6 is
therefore satisfied naturally by the later NDA row; no validator
exemption is needed. If the bidder **never** signs an NDA, use §D1.a's
`unsolicited_first_contact` flag instead — that one DOES exempt from
§P-D6 because the NDA legitimately doesn't exist.

**Distinguishing from §D1 unsolicited-first-contact (§D1.a in events.md).**
- §D1.a covers the case where a bidder sends an unsolicited bid and
  **never signs an NDA at all** (target declines, bidder withdraws).
  Flag: `unsolicited_first_contact`. Exempts from §P-D6.
- §C4 covers the case where a bidder gives a concrete price BEFORE
  signing an NDA, but **later does sign an NDA** and continues in the
  process.
  Flag: `pre_nda_informal_bid`. Does NOT exempt from §P-D6 (the later
  NDA row satisfies the existence check).

Decision tree: does an NDA eventually exist for this bidder in this
phase? YES → §C4 (documentation flag only). NO → §D1.a (exemption
flag). A single Bid row never carries both flags — one excludes the
other.

**Distinguishing from §M1 unsolicited-no-NDA skip.** §M1 skips parties
that signed no NDA AND gave no concrete price AND had no bid intent.
§C4 covers the opposite pattern: concrete price given, NDA signed
later.

**Rejected alternatives.**
- **Use `Bidder Sale`** (saks-extractor ad-hoc convention) — §C1's
  `Bidder Sale` is for first-contact initiation, not for concrete price
  signals. Semantically conflates "bidder expressed intent to propose
  sale" with "bidder gave price before NDA."
- **Skip per §M1 spirit** — loses research-relevant signal about how
  the negotiation evolved before the NDA.
- **New event code `Pre-NDA Bid`** — balloons vocabulary; the flag +
  `bid_type="informal"` handles this cleanly within §C3.

**Cross-references.**
- `rules/bids.md` §C3 (unified `Bid` vocabulary; not rules/events.md —
  §C3 on `bid_note` on bid rows lives in `rules/events.md`).
- `rules/bids.md` §G1 (informal-vs-formal triggers; pre-NDA price
  indications default to informal by construction).
- `rules/events.md` §D1 / §D1.a (unsolicited first-contact cousin).
- `rules/bids.md` §M1 (unsolicited-no-NDA skip; §C4 is the positive
  case where the pattern is NOT skipped).
- `rules/invariants.md` §P-D6 (NDA-before-Bid existence check; §C4
  does NOT need an exemption because the bidder's later NDA satisfies
  the check — contrast §D1.a which DOES exempt).

---

### §C5 — Same-price reaffirmations (🟩 RESOLVED, 2026-04-26 per Decision #5)

**Problem.** A bidder restates a price they previously submitted —
verbally, in a confirming letter, or in response to a board prompt.
Without a rule, the extractor inconsistently emits a second `Bid` row
sometimes and a note other times. Bid counts become unstable
run-to-run.

**Decision.** A same-price reaffirmation gets a new `Bid` row **only
when the filing language describes it as a substantive response to a
narrated process step** (e.g., a board's "best and final" deadline, a
formal final-round letter, an explicit invitation to confirm). In all
other reaffirmation patterns — verbal "my $X stands" between scheduled
events, day-of-signing confirmations — append the reaffirmation
language to the prior bid row's `additional_note` instead of emitting
a new row.

**The rule, operationalized.**

A bid event is a **same-price reaffirmation** when:
1. The same bidder (same `bidder_name`) has a prior `bid_note = "Bid"`
   row in the same `process_phase`, AND
2. The reaffirmed price equals the prior price on every populated
   bid-value field (`bid_value_pershare` / `bid_value_lower` /
   `bid_value_upper` / `bid_value` all match), AND
3. The structural terms (consideration components, financing
   contingency, exclusivity, etc.) are unchanged.

When all three hold, decide row-vs-note by trigger language:

| Filing language pattern in the reaffirmation passage | Treatment |
|---|---|
| *"in response to the Board's best-and-final request,"* / *"\[Bidder\] confirmed its best and final offer of \$X,"* / *"as its formal final-round bid in response to the process letter dated …"* | **New `Bid` row.** Same price; capture the trigger language in `additional_note` (e.g., `"reaffirmation in response to board's best-and-final deadline of May 30, 2013"`). |
| *"\[Bidder\] verbally reiterated"* / *"called to confirm \$X stood"* / *"reaffirmed during the negotiation of the merger agreement"* | **Note, not row.** Append to prior bid's `additional_note`: `"verbally reaffirmed on [date]: '<short verbatim phrase>'"`. |
| Day-of-signing or pre-signing confirmation: *"on \[signing-day\], \[Bidder\] confirmed it remained at \$X and was prepared to execute"* | **Note on `Executed` row.** Fold into `Executed` row's `source_quote` / `additional_note`; do not emit a separate Bid row. |
| Anything else (ambiguous, one-off, no clear trigger language) | **Default: note, not row.** When in doubt, append to prior bid. |

**Why a single rule, not four sub-cases.** The 4-case framing in
Decision #5's discussion was pedagogical; the operational rule is one
filter (was the reaffirmation a substantive response to a narrated
process step?) with one default (no → note). The reference cases just
exemplify the boundary.

**Why no separate event vocabulary or new flag.** A reaffirmation row
IS a `Bid` row. Inventing `Bid Confirmation` as a vocabulary entry, or
attaching a `bid_reaffirmation: true` flag, would add schema bloat for
a pattern whose trigger language ("best and final" / "in response to
the board's request") is already preserved verbatim in `source_quote`
and `additional_note`. Downstream code that wants to count
reaffirmations across the dataset can grep `additional_note` for the
trigger phrases. Keeping the rule note-only is the explicit
"least-overengineered" choice from Decision #5.

**Reference deals affected (3 of 9):**

- **zep:** New Mountain's April 2015 reiteration of $20.05
  best-and-final during merger-agreement negotiations is a verbal
  reaffirmation, not a response to a new process step → **note**, not
  a new row. AI today emits a row; after re-extraction it becomes a
  note on the prior best-and-final row.
- **penford:** Ingredion's October 14, 2014 confirmation of $19.00
  the day before signing is pre-signing glue → **note** on the
  `Executed` row (or fold into its `additional_note`). AI today emits
  a row; after re-extraction it disappears from the events list.
- **stec:** WDC's May 30, 2013 verbal confirmation of $9.15 was made
  in direct response to the board's "best and final by May 30"
  request → **new `Bid` row**, same price, with `additional_note`
  capturing the trigger language. AI today already emits a row; the
  change is to ensure the reaffirmation context lives in
  `additional_note`.

**Validator implications.** None. A reaffirmation `Bid` row is a
regular bid row and goes through §G1 / §P-G2 normally. The
`bid_type_inference_note` for Case 3 reaffirmation rows can read
*"reaffirmation of formal best-and-final from [prior-row date];
bid_type inherited"* — that satisfies §P-G2.

**Reference data.** Alex's reference is not regenerated. AI-vs-Alex
disagreements on these 3 deals are real adjudication signal, not noise
(Alex's coding here was inconsistent and worth re-evaluating against
the filing per case).

**Cross-references.**
- `rules/bids.md` §C3 / §C4 / §G1 / §H1 (the surrounding bid-row
  emission rules).
- `prompts/extract.md` (extractor classification guidance).

---

### §G1 — Informal-vs-formal bid classification (🟩 RESOLVED, 2026-04-18)

**This is the highest-risk classification in the pipeline.**

**Decision.** A bid is classified by the **strongest signal** in the
filing passage describing it, evaluated against the trigger tables below.
Where no trigger fires, fall back to process-position heuristics. Where
still ambiguous, emit `bid_type = null` + hard flag.

These trigger tables and fallback heuristics are **classification
guidance for the extractor** — they tell the extractor how to *pick*
`informal` vs `formal`. The validator (§G2 / §P-G2) enforces
*evidence* (range, ≤300-char `bid_type_inference_note`, or paired /
fallback `Final Round.final_round_informal`), not trigger presence. A
trigger hit in `source_quote` alone does NOT satisfy §P-G2; the
extractor must still attach the inference note unless the row is a true
range bid or the final-round row already supplies the classification.

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
- **Structural signal: bid is stated as a true range** (both `bid_value_lower` and `bid_value_upper` populated, numeric, with `lower < upper` per §G2) — **range always wins**. Whenever a true range is present, `bid_type = "informal"` regardless of any formal trigger phrase the filing uses. If a formal trigger coexists with the range, emit soft flag `range_with_formal_trigger_override` to preserve the audit trail; do NOT change `bid_type` based on the trigger. Per Alex 2026-04-27 directive.

**Process-position fallback** (no explicit trigger present):
- Bid submitted in response to a paired or fallback `Final Round` row (§K1)
  inherits that row's `final_round_informal` value:
  - `final_round_informal = false` → `formal`
  - `final_round_informal = true` → `informal`
- Bid submitted **before** any round structure is established (initial
  approach, pre-NDA or pre-process-letter) → `informal`.
- Topping bid submitted post-`Executed` under go-shop provisions → `formal`
  (go-shop topping bids require binding terms).

**When still ambiguous.** Emit `bid_type = null` + hard flag
`informal_vs_formal_ambiguous` with the `source_quote` that caused the
ambiguity. The row is still emitted; downstream research filters on
non-null `bid_type`.

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

### §G2 — Classification evidence requirement (🟩 RESOLVED, 2026-04-20)

**Decision.** Hard invariant. Every row with non-null `bid_type` MUST
satisfy at least one of:

1. The row is a true range bid — both `bid_value_lower` and
   `bid_value_upper` populated, numeric, and `bid_value_lower <
   bid_value_upper` (§G1 informal structural signal).
2. The row carries `bid_type_inference_note: str`, non-empty, ≤ 300
   chars, stating why this bid is informal or formal. The note SHOULD
   cite §G1 guidance (trigger phrase it matches, process-position
   fallback rule, or structural signal); it MUST be grounded in the
   filing.
3. A paired/fallback `Final Round` row in the same phase supplies
   `final_round_informal` consistent with the bid's `bid_type` (§K1 /
   §K2). This covers process-position classifications where the
   final-round row already stores the informal/formal call.

**§G1 triggers are classification guidance, not a validator
satisfier.** The extractor uses §G1's formal/informal trigger tables
and process-position fallback to *pick* `bid_type`. But §P-G2
validates on range, note, or paired/fallback final-round evidence; a
trigger match alone does not pass.
Rationale: at 392-deal scale, a closed trigger list overfits the
9-deal reference corpus. Empirical 9-deal distribution (2026-04-20):
30% of 92 bids relied on trigger hits, 29% on range, 55% on
inference_note; providence-worcester (22 bids) and penford (8 bids)
had 0% trigger coverage. Absent a paired/fallback final-round
classification, the note-on-every-non-range rule holds regardless of
filing language.

**Cap rationale.** 300 chars ≈ 2–3 sentences, enough for
`"<classification> per §G1 <rule>: <filing evidence>"`. The prior
200-char cap produced truncated reasoning; one observed failure
(medivation row 16) ran to ~370 chars. 300 leaves headroom without
inviting essays.

**Validator.** `pipeline._invariant_p_g2`: hard flag
`bid_type_unsupported` if no satisfier holds; hard flag
`bid_range_inverted` if `lower >= upper`; hard flag
`bid_range_must_be_informal` if a true range carries any non-informal
`bid_type`.

**Additional hard requirement (per 2026-04-27 directive).** When the row
satisfies satisfier (1) — i.e., is a true range bid — `bid_type` MUST
equal `"informal"`. A range with `bid_type = "formal"` is a structural
contradiction and the validator (§P-G2) flags it hard as
`bid_range_must_be_informal`.

**Why hard.** Informal-vs-formal is the core research variable.
Manual verification of 401 deals × ~5 bids each = ~2000
classifications is intractable without per-row evidence. Soft
flagging would let silent drift accumulate.

**Cross-references.**
- `rules/bids.md` §G1 (classification rule).
- `rules/invariants.md` §P-G2.
- `SKILL.md` §Non-negotiable rules (evidence citation: every row
  carries `source_quote` and `source_page`).

---

### §H2 — Composite consideration (🟩 RESOLVED, 2026-04-18)

**Decision.** Keep a compact component-label field for mixed-consideration
structure. Do not decompose the headline price into separate dollar columns
inside the AI extraction schema.

**Per-row field:**
- `consideration_components: list[str]` — ordered list of consideration
  components present. Allowed values: `["cash"]`, `["cash", "stock"]`,
  `["cash", "cvr"]`, `["cash", "earnout"]`, `["cash", "stock", "cvr"]`,
  `["stock"]`, `["stock", "cvr"]`, etc.

**Invariants.**
- Pure-cash bids: `consideration_components = ["cash"]`.
- Mixed-consideration bids: keep the filing-stated headline value in
  `bid_value_pershare` when one is stated; use `consideration_components`
  for the structure and `additional_note` for any filing-stated detail that
  does not fit the current numeric fields.
- Range bids with composite structure: keep the range in
  `bid_value_lower` / `bid_value_upper` and note the composite breakdown in
  `additional_note` unless the filing itself states a single headline
  value.

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
$61.20"). Use the filing-stated implied value as the headline
`bid_value_pershare` only when the filing gives one; record the exchange
ratio in `additional_note` as `exchange_ratio: <float>`.

**Reference conversion.** Alex's `comments_1` entries like "20.02 cash +
1.13 CVR" are preserved for manual review, with the component labels captured
where the current schema supports them.

**Rejected alternatives.**
- **Detailed per-component dollar columns in this AI extraction.** Alex does
  not use them in the reference workbook, and they inflate Austin's manual
  verification surface for no current research gain.
- **Only free-text comments.** Loses the quick all-cash / mixed-consideration
  split that is useful during verification.

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
whether to add the bid row during manual verification.

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

---

### §H4 — Aggregate-dollar bids (🟩 RESOLVED, 2026-04-18)

**Decision.** Emit the aggregate value as-is in `bid_value` +
`bid_value_unit = "USD"`. Populate `bid_value_pershare` **only if the
filing itself states the per-share equivalent alongside the aggregate**.
No extraction-time arithmetic from inferred share counts.

**Field semantics.**

| Bid shape | `bid_value` | `bid_value_pershare` | `bid_value_unit` |
|---|---|---|---|
| Per-share only (*"$45 per share"*) | null | 45 | `"USD_per_share"` |
| Aggregate only (*"$10 billion"*) | 10_000_000_000 | null | `"USD"` |
| Aggregate + filing-stated per-share (*"$10 billion, or $45 per share"*) | 10_000_000_000 | 45 | `"USD"` |
| Non-USD (*"€5 billion"*) | 5_000_000_000 | null | `"EUR"` |

If the filing labels the aggregate value as enterprise value, equity value,
purchase price, or similar, preserve that label in `additional_note` rather
than introducing a separate structured column.

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
- `rules/schema.md` §R1 (current value fields).
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
- `rules/dates.md` §A (`BidderID` as event sequence).

---

### §O1 — Process-condition structured column (🟩 RESOLVED, 2026-04-18)

**Decision.** Keep the one process-condition field that directly affects
auction dynamics in the current research design: bidder exclusivity. Other
merger-agreement economics and financing-condition terms are outside the
current AI extraction scope.

**Event-level field (on bid rows per §R1):**

| Field | Type | Semantics |
|---|---|---|
| `exclusivity_days` | int \| null | Exclusivity period granted to this bidder at this bid event, in days. |

**Extraction rules.**
- `exclusivity_days` is only set on the bid row where exclusivity is
  granted; it's implicitly still active on subsequent rows for the same
  bidder until the exclusivity period expires (not re-stated).

**Migration note.** Alex's `comments_2` entries like "Exclusivity 30 days"
are parsed into `exclusivity_days: 30` during xlsx → JSON conversion.

**Rejected alternatives.**
- **Free text only** — makes exclusivity unanalyzable without NLP.
- **Broad merger-agreement term capture in this pipeline** — bloats the
  schema and Austin's verification surface; those terms are better sourced
  from dedicated M&A databases if a future paper needs them.

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
- Party signed an NDA (Condition 1 fails) — keep the NDA row; per §I1
  the extractor must also emit a `DropSilent` row for that signer.
  Validator §P-S1 raises `missing_nda_dropsilent` (soft) only if the
  required `DropSilent` is missing.
- Party stated bid intent without price (Condition 3 fails) — emit
  `Bidder Interest` row with `bid_value_unspecified` flag per §H1.

**Rejected alternatives.**
- **Emit as `Bidder Interest` with flags** — pollutes the dataset with
  drive-by letters; breaks the auction-participant count.

**Cross-references.**
- `rules/events.md` §D1 (`Bidder Interest` criteria).
- `rules/events.md` §I1 (NDA-only rows for silent signers).

---

### §M2 — No-bid-intent skip (🟩 RESOLVED)

**Decision.** Folded into §I1's NDA-only rule. No separate skip.

**Rule.** A party that signs an NDA but never submits a bid, drops, or
otherwise engages further is an NDA-only signer per §I1. Do NOT skip;
do NOT omit the NDA. The extractor MUST emit a `DropSilent` row for that
signer, immediately after the matching NDA row in narrative order, with
null dates and a `date_unknown` info flag (see §I1 for the full row
shape). The dedicated `DropSilent` code distinguishes inferred-from-
silence drops from filing-narrated drops.

Rationale: the §Scope-1 auction classifier counts non-advisor bidder NDAs.
A party that signed an NDA with bid intent, even without a submitted bid,
is a meaningful auction participant. Silent post-NDA behavior is an inferred
withdrawal, and the dedicated `DropSilent` code makes the inferred-from-silence
semantics explicit. The re-cited NDA quote anchors the signer identity; the
row's meaning comes from the absence of later narration.

**Rejected alternatives.**
- **Skip entirely (no NDA, no drop)** — drops the NDA-signer from the
  auction count; silently breaks §Scope-1.
- **Emit synthetic generic `Drop` rows for silent NDA signers** —
  loses the inferred-from-silence distinction. The dedicated `DropSilent`
  code preserves it.

**Cross-references.**
- `rules/events.md` §I1 (NDA-only rows for silent signers).
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
`bidder_type = null`. The `bidder_type` classification (§F1) applies
only to bidders. A validator check catches violations.

**Rejected alternatives.**
- **Use `bidder_type = "advisor"`** — overloads the type field,
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

### §M4 — Cross-phase NDA continuity (🟩 RESOLVED, 2026-04-18; extended 2026-04-21)

**Decision.** An NDA that carries forward across any phase-change
transition — phase 0 → phase 1 (stale prior revived) or phase 1 →
phase 2 (Terminated then Restarted) — is recorded as **two NDA
events**, one per phase. The earlier phase's NDA row records the
original signing; the later phase's NDA row records the revival /
continuation.

**Rule.**
- Original NDA signing → `NDA` row with the phase of the original
  signing (`process_phase = 0` for prior stale processes,
  `process_phase = 1` for an earlier run of the current deal that was
  later Terminated and Restarted).
- If the same NDA is explicitly **revived / still-binding** when the
  bidder re-engages in the later phase → second `NDA` row with:
  - `process_phase` matching the later process (1 or 2).
  - `bid_date_precise` = date of re-engagement / revival acknowledgement.
  - Flag `{"code": "nda_revived_from_stale", "severity": "info", "reason": "revives NDA originally signed on <date>"}`.
    The flag name is historical; it applies to every phase-change
    revival (phase-0→1 stale-prior AND phase-1→2 Terminated-Restarted).
- If the bidder re-engages without an explicit NDA revival (filing
  silent), emit only the later-phase `Bidder Interest` / `Bidder Sale`
  row per §D1 and flag `nda_revival_unclear` (soft).
- If the bidder signs a **new** NDA in the later phase (common), emit
  only the later-phase NDA; the old phase's NDA is a separate row.

**Rationale.**
- Preserves the earlier-phase record (e.g. Penford 2007/2009 stale
  priors; Zep's first-attempt bidders carrying into phase 2 after
  Terminated → Restarted).
- Auction classifier (§Scope-1) correctly counts the revived bidder as a
  current-phase NDA signer.
- §P-D6 (NDA-to-Bid existence) operates within a single `process_phase`,
  so a bidder who bids in phase 2 needs a phase-2 NDA row — either a
  newly-signed NDA or a revival row under this rule.

**Rejected alternatives.**
- **Single NDA in the original phase only** (drop the revival record) —
  loses history and forces §P-D6 violations whenever the bidder bids in
  the later phase.
- **Single NDA in the later phase only** (ignore prior signing) —
  undercounts earlier-phase NDAs and breaks the Penford stale-prior
  inclusion.

**Cross-references.**
- `rules/events.md` §L1 (prior-process inclusion).
- `rules/events.md` §L2 (`process_phase` field).
- `rules/schema.md` §Scope-1 (auction classifier).

---

### §M5 — Rollover-CA skip (Type C confidentiality agreements) (🟩 RESOLVED, 2026-04-26 per Decision #4)

**Decision.** When the filing narrates a confidentiality agreement
between a target shareholder and the acquirer / buyer group covering
the shareholder's potential equity rollover, **skip it**. Do not
emit a row. Do not classify as `NDA` or `ConsortiumCA`.

**Definition (Type C per `rules/events.md` §I3).** A rollover CA is a
confidentiality agreement between (a) a target shareholder (founder,
strategic partner, holding fund, or similar) and (b) the acquirer or
buyer group, covering the negotiation period for the shareholder's
agreement to roll their existing equity into the post-merger entity
rather than cash out. Distinct from:

- **Type A (`NDA`)**: target ↔ bidder confidentiality covering MNPI access
- **Type B (`ConsortiumCA`)**: bidder ↔ bidder consortium-formation CA

**Identification heuristics.** The filing's language usually makes the
shareholder-rollover purpose explicit:

- *"\[Major Shareholder\] entered into a confidentiality agreement
  with \[Buyer Group\] regarding their potential rollover"*
- *"\[Shareholder\] agreed to roll over their equity in the merger"*
- *"the rollover agreement"* / *"the equity-rollover commitment"*
- *"\[Shareholder\]'s shares would be exchanged for equity in the
  surviving company"* (paired with a CA reference)

**When ambiguous between Type B and Type C.** If the filing's
language could plausibly describe either a consortium-formation CA
(Type B) or a rollover CA (Type C), prefer Type B (emit
`ConsortiumCA`) and attach `{"code": "ca_type_ambiguous", "severity":
"hard", "reason": "<summary including the specific Type B vs Type C
ambiguity>"}`. Austin adjudicates against the filing.

**Why skip.** Rollover CAs are not auction-process events; they
belong to a separate research domain (post-merger capital structure).
Across the 9 reference deals, only petsmart has any candidate
narrative for Type C, and even that is ambiguous (Longview's CAs are
classified as Type B per Decision #4 since Longview joined the BC
Partners-led Buyer Group as a constituent rather than rolling over a
passive stake).

**Why not capture as a separate event type.** Capture-cost (extraction
attention, schema entry, downstream filtering) > research value at
this scale. If a future paper specifically needs rollover behavior,
re-extract with a targeted pass.

**Cross-references.**
- `rules/events.md` §I3 (three CA types — auction NDA, consortium CA,
  rollover CA — full definitions and disambiguation table).
- `rules/events.md` §C1 (`NDA` and `ConsortiumCA` vocabulary entries).

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
- Exactly one of `{pershare, (lower, upper), (lower only), (upper only), all-null}` is populated per bid row. When the bid is shaped as a range, both `bid_value_lower` and `bid_value_upper` MUST be populated and numeric with `lower < upper`. Per Alex 2026-04-27.
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

**Rejected alternatives.**
- **Populate midpoint in `bid_value_pershare` on ranges** — loses the
  range; also mixes derived with raw data.
- **Add a `bid_value_bound_type` enum** — redundant with the populated-
  field pattern; downstream code checks which fields are non-null anyway.

**Cross-references.**
- `rules/bids.md` §G1 (range → informal).
- `rules/bids.md` §H2 (composite consideration).
- `rules/bids.md` §H4 (aggregate-dollar bids).
- `rules/schema.md` §R1 (event-level value fields).

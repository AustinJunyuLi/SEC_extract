# Six Policy Decisions — Living Tracker

**Opened:** 2026-04-26
**Owner:** Austin
**Source:** Cross-deal patterns surfaced by the 2026-04-23 clean_ref9 adjudication
  (`quality_reports/adjudication/2026-04-23_clean_ref9/MASTER_ADJUDICATION.md`)

This file is the single place we track six policy decisions that block forward
progress on Stage 3. Each decision unblocks one or more reference deals and
removes a recurring noise source from the AI-vs-Alex diff. We work them one at a
time. Nothing is lost: even when a decision is taken, the rationale and the
discarded options stay here.

---

## Status Summary

| # | Topic | Status | Last Update |
|---|---|---|---|
| 1 | Silent NDA signers → emit DropSilent | 🟩 IMPLEMENTED (pending re-extraction) | 2026-04-26 |
| 2 | `bidder_type.public` for unknown bidders | 🟩 IMPLEMENTED (pending re-extraction) | 2026-04-26 |
| 3 | `Acquirer` field semantics (legal vs operating) | 🟩 IMPLEMENTED (pending re-extraction) | 2026-04-26 |
| 4 | NDA scope: target-bidder only, or include inter-bidder/rollover CAs? | 🟩 IMPLEMENTED (pending re-extraction) | 2026-04-26 |
| 5 | Same-price reaffirmations: new bid row or note? | 🟥 OPEN | 2026-04-26 |
| 6 | IB date anchor: board approval vs engagement letter vs first action | 🟥 OPEN | 2026-04-26 |

**Legend:** 🟩 DECIDED · 🟨 LEANING (Austin has a view, wants discussion) · 🟥 OPEN

---

## How to use this file

For each problem:

- **Problem statement** — what the disagreement is, in plain language
- **Why it matters** — what breaks if we don't decide, who is affected
- **Affected deals** — concrete pointers from the 04-23 adjudication
- **Options** — every defensible answer, with tradeoffs
- **Recommendation** — my (Claude's) read, when I have one
- **Decision** — Austin fills this in; date-stamped
- **Rationale** — why this decision (so future-us remembers)
- **Implementation** — files/code/rules to change after the decision
- **Open sub-questions** — implementation details to confirm before coding

Once a decision is implemented and verified across the 9 reference deals, mark
it 🟩 IMPLEMENTED in the status table and add the commit SHAs.

---

## 1. Silent NDA signers → emit Drop, no flag

### Status: 🟩 DECIDED at policy level (2026-04-26). Implementation details TBC.

### Problem statement

When a filing names or counts confidentiality-agreement (NDA) signers but never
narrates a follow-up event (no bid, no executed merger, no explicit drop), the
extractor today leaves them as NDA-only rows and the validator emits a soft
`nda_without_bid_or_drop` flag for each one. This produces 15-19 soft flags per
heavily-NDA'd deal (medivation 18, providence 15, zep 19), and the same
discussion has been re-litigated across multiple debug sessions.

### Why it matters

- Recurring noise in every adjudication report
- The "soft flag" framing implies "maybe a problem" when the policy is "this is
  actually a Drop" — so the flag is misleading
- Reference data (Alex) does the same thing differently (synthetic catch-all
  drop), and the diff harness flags every mismatch
- Implementation work today is wasted reading the same flag and dismissing it

### Affected deals

All 9 reference deals to varying degrees. Heaviest: medivation, providence,
zep. Lightest: stec.

### Decision (2026-04-26)

**Silent NDA signers (NDA row with no later bid / drop / executed event for
that bidder) are coded as Drop. The extractor must emit the Drop row. The
validator must not raise a flag about NDA-without-follow-up.**

This reverses the prior `rules/events.md` §I1 stance ("do not fabricate
catch-all drops"). The new stance is that silent post-NDA behavior is, by
definition, a withdrawal from the process.

### Rationale

- Conceptually: an NDA signer who never bids has, in fact, dropped out — the
  filing's silence is the evidence
- Operationally: kills a recurring noise source
- For research: a Drop row is more useful than an NDA-only row because
  downstream auction-funnel counts work without special-casing
- Reference-side: brings AI behavior closer to what Alex's reference does
  (he aggregates silent signers into a catch-all drop), reducing diff noise

### Implementation

**Three files change:**

1. `rules/events.md` §I1 — flip the policy. Replace "do NOT fabricate catch-all
   drops" with the new rule: silent post-NDA bidders get a Drop row.
2. `rules/invariants.md` §P-? — remove `nda_without_bid_or_drop` from the
   validator's flag table, OR repurpose it to fire only if the extractor failed
   to emit the now-required Drop.
3. `prompts/extract.md` §E? — add explicit instruction: "for every NDA signer
   without a later bid/exec/named drop in the filing, emit a Drop row with the
   conventions below."
4. `pipeline.py` — adjust the validator function for NDA-without-followup; if
   we keep the check, change semantics to "extractor missed a required Drop."

**Once committed, regenerate all 9 reference deals and confirm:**

- Soft `nda_without_bid_or_drop` flags drop to zero
- Diff against Alex's reference shrinks for the heavy-NDA deals

### Implementation sub-decisions (Austin, 2026-04-26)

- **(a) Date:** **B** — null with `date_unknown` info flag. Honest about
  unknown date.
- **(b) Drop code:** **C** — new `DropSilent` enum value. Machine-
  distinguishable from filing-narrated drops.
- **(c) Marker:** **A (subsumed)** — the dedicated `DropSilent` code is
  itself the marker; no additional info flag needed beyond `date_unknown`.

### Sub-decision: reference parity (Austin, 2026-04-26)

Alex's converted reference stays unchanged. Silent NDA signers remain as
bare NDA rows on the reference side. The diff harness (`scoring/diff.py`)
filters DropSilent rows out of the AI side at comparison time so the diff
treats both sides equivalently.

### Sub-decision: validator role (Austin, 2026-04-26)

Repurpose §P-S1 as a **soft safety net**. New flag code:
`missing_nda_dropsilent`. Fires only when extractor failed to emit the
required DropSilent. Severity stays soft so a missed row surfaces for
review without blocking the deal.

### Sub-decision: extractor placement (Austin, 2026-04-26)

Extractor emits `DropSilent` immediately after the matching NDA in
narrative order. The canonical sort (`pipeline._canonicalize_order`)
sorts null-dated rows to the deal-end via the `or "9999-12-31"` coalesce;
DropSilent rows therefore cluster at the end of the canonicalized output,
which signals "metadata block" to readers. §P-D5's set-membership check
finds the prior NDA regardless of position.

---

## 2. `bidder_type.public` for unknown bidders

### Status: 🟨 LEANING toward `null` (Austin's view). Discussion open.

### Problem statement

When the filing identifies a party but does not state whether it is publicly
traded:

- The current AI behavior: default to `public = false` (under §F2: "true only
  if filing states publicly traded")
- Alex's reference: `public = null` (the converter refuses to infer)

Because `public` appears on every event row, this single mismatch produces
dozens of "field disagreements" per deal. Across the 9-deal reference set, this
alone is the largest single source of apparent AI-vs-Alex divergence.

### Why it matters

- Inflates diff counts, making real disagreements harder to spot
- Forces a rule decision: do we want a tri-state field (`true` / `false` /
  `unknown`) or a strict boolean (`true` / `false`)?
- Affects every named-but-untyped bidder in every deal
- Touches schema, prompt, validator, AND reference converter

### Affected deals

All 9. Particularly bad on deals with many unnamed financial sponsors:
medivation (Pfizer + 2 unnamed), imprivata (4 financial sponsors), petsmart
(15 financial buyers), saks (sponsors A, E, G), stec (companies A-H).

### Austin's leaning (2026-04-26)

> "When a bidder is unknown the public verifier should be set to null
> (leave blank). I do want to discuss about this a bit more."

### Options

**Option A: Strict boolean (`true` / `false`), false = "filing did not state
public"** — current AI behavior

- Pro: schema is simple, no nullability handling downstream
- Pro: matches information-theoretic prior (most unnamed bidders ARE private)
- Con: conflates "filing says private" with "filing says nothing"
- Con: we are guessing on every silent case

**Option B: Tri-state with `null` = unknown** — Austin's lean

- Pro: honest about absence of evidence
- Pro: matches reference converter, eliminates diff noise immediately
- Pro: standard practice in research datasets (NA for unknown)
- Con: every consumer of the field must handle null
- Con: "null" loses the reasonable prior that an unnamed PE sponsor is private

**Option C: Boolean + companion `public_known` boolean**

- Pro: keeps simple boolean for analysis, adds nullability info separately
- Pro: backward-compatible with research code expecting boolean
- Con: schema bloat
- Con: nobody else does this; will look weird

### Discussion points to work through

1. What does "public" mean for the research question? Is it about (a) information
   asymmetry (public bidders disclose their identity → market reaction), or
   (b) capital structure (public bidders fund deals from issued equity)?
   The answer should drive whether unknown defaults to false or to null.

2. For the named-but-untyped financial sponsors (e.g., "Sponsor A"): is the
   filing's "private equity firm" language sufficient to set `public=false`?
   Or do we still want to leave that as null because we don't know whether the
   sponsor ITSELF is public (Blackstone is publicly traded, KKR is publicly
   traded — these are not edge cases)?

3. What about strategic acquirers identified by name without trading status?
   E.g., the filing names "Ingredion" but doesn't say "publicly traded." Most
   named strategics ARE public. Does our rule allow inference from common
   knowledge, or strictly filing-only?

### Recommendation pending discussion

Tentatively: **Option B (tri-state with `null` = unknown), with a refinement:**
for parties the filing affirmatively describes as "private equity firm" or
"financial sponsor" or "private company," set `public = false`. Reserve `null`
strictly for parties whose status the filing leaves silent.

This gives you the diff-noise win immediately, stays honest about ignorance,
but doesn't throw away strong filing signals.

### Decision (2026-04-26)

**`bidder_type.public` is tri-state (`true | false | null`), strict-filing-only.**

Three sub-decisions, all settled:

- **Q1 — Meaning:** `public` measures **capital structure** (is the bidding
  firm itself publicly listed on the day of the bid), not disclosure /
  identification. This is meaning (b) from the framing.
- **Q2 — Named strategics without "publicly traded" qualifier:** strict
  filing-only — silent → `null`. No common-knowledge inference. If the
  filing did not say "publicly traded," the AI emits `null`. Future
  enrichment via CRSP/Compustat join is a deterministic post-pass, not an
  AI judgment.
- **Q3 — PE sponsors:** the pre-2026 §F2 carve-out (*"For PE firms,
  `public` is always `false`"*) is **removed**. PE-firm rows get `public`
  by the same strict rule as everyone else: `null` unless the filing names
  the sponsor AND addresses its listing. KKR (NYSE: KKR), Blackstone (NYSE:
  BX), Apollo (NYSE: APO), Carlyle (NASDAQ: CG), Ares (NYSE: ARES), TPG
  (NASDAQ: TPG) — all listed sponsor firms; the *"private equity firm"*
  descriptor refers to the fund vehicle, not the parent firm.

### Rationale

- **Honest about silence.** A strict boolean conflated "filing says
  private" with "filing says nothing" — the latter was 70%+ of all rows.
  The tri-state separates the two.
- **Diff-noise reduction.** Pre-policy AI extractions carry 302
  `public=false` rows across the 9 reference deals; the reference carries
  189 `public=null` rows in the same population. Most of the 302 will
  flip to `null` after re-extraction with the new prompt, eliminating the
  largest single source of AI-vs-Alex field mismatches.
- **Reproducibility.** Strict-filing-only keeps extraction stable across
  runs; common-knowledge inference would drift with model updates.
- **Orthogonality.** `base` (S/F/mixed) classifies the bid vehicle's
  funding model; `public` classifies the firm's listing status. The two
  are independent observables.

### Implementation (2026-04-26 — completed)

Five files touched:

1. **`rules/bidders.md` §F1 (line ~282)** — type signature changed:
   `public: bool` → `public: bool | null`. Field description rewritten
   to document tri-state semantics with the listed-sponsor examples.
2. **`rules/bidders.md` §F2 (line ~234)** — rewrote the `public`
   determination block. Added the strict-filing-only table
   (true/false/null). Added the "silent → null" cases (PE sponsors,
   named strategics without qualifier, anonymized rows, SPACs without
   listing language). Removed the pre-2026 PE-firm carve-out and
   replaced with explicit independence-of-`base` statement. Expanded
   rejected alternatives to include strict-boolean and
   common-knowledge inference.
3. **`rules/schema.md` §R1 (line ~237)** — `bidder_type.public` field
   signature updated to `bool | null` with a one-line tri-state
   explanation pointing back to §F1/§F2.
4. **`prompts/extract.md` (Non-negotiable constraints, after the
   "do not invent" bullet, line ~64)** — added an explicit constraint
   bullet describing the new strict-filing-only tri-state rule, with
   the listed-sponsor reasoning called out.
5. **`scripts/build_reference.py`** — **no changes needed.** The
   converter at line 491 already emits `True if has_public else False
   if has_private else None`, and inspection of the actual reference
   confirms zero `public=false` rows across all 9 deals (Alex's notes
   never trigger the `False` branch in practice). The
   `test_bidder_type_sets_public_false_only_on_private_signal` test
   exercises a code path that does not fire on real data.
6. **`pipeline.py`** — **no changes needed.** No validator enforces the
   `public` field type, so `null` is already accepted.

### Verification (2026-04-26)

- `pytest tests/`: 103 passed in 2.88s. Includes
  `test_build_deal_keeps_public_unknown_for_plain_type_note` which
  exercises the converter's `null` behavior directly.
- `python scripts/build_reference.py --all`: rebuild produces
  bit-identical JSONs for all 9 reference deals (no diff in
  `reference/alex/`).
- Simulated diff-noise reduction: across the 9 deals, current AI
  extractions carry 302 `public=false` rows; after re-extraction with
  the updated prompt, most of these will flip to `null` and match
  Alex's `null`, eliminating the dominant field-mismatch source from
  the 04-23 adjudication run.

### Status

🟩 **IMPLEMENTED at policy + code level.** Pending: re-extract all 9
reference deals with the updated prompt; confirm `public=false` count
drops to ≤ a small handful (only filing-explicit *"private company"*
language) and the diff-harness `bidder_type` mismatch count collapses.

---

## 3. `Acquirer` field semantics (legal vehicle vs operating buyer)

### Status: 🟥 OPEN. Austin has flagged he lacks field knowledge here.

### Problem statement

In sponsor-backed and shell-mediated mergers, the filing names two or three
distinct entities as "the acquirer":

- **The legal acquirer** — usually a Delaware shell formed for the merger
  (e.g., `Argos Holdings Inc.` for Petsmart, `Spin Holdco Inc.` for Mac-Gray,
  `NM Z Parent Inc.` for Zep, `Harry Acquisition Inc.` for Saks)
- **The operating acquirer** — the company or buyer group that controls the
  shell (e.g., the Buyer Group for Petsmart, `CSC ServiceWorks, Inc.` for
  Mac-Gray, `New Mountain Capital` for Zep, `Hudson's Bay Company` for Saks)
- **The ultimate owner** — sometimes a private-equity fund or family of funds
  behind the operating acquirer

The filing supports all three labels for the same field. Today the AI and the
reference disagree on which to use, deal by deal.

### Why it matters

- This is THE canonical research-design question for an M&A dataset
- Once decided, every deal's `Acquirer` field needs to be regenerated
- Has implications for matched analyses (acquirer characteristics, repeat
  acquirers, sponsor identification)

### Affected deals

Most directly: petsmart (legal `Argos Holdings`, operating Buyer Group),
mac-gray (legal `Spin Holdco`, operating `CSC ServiceWorks`), zep (legal
`NM Z Parent`, operating `New Mountain Capital`), saks (legal `Harry
Acquisition`, operating `Hudson's Bay Company`).

### Field-knowledge framing for Austin

**What the legal acquirer is:**
A shell company is formed solely to execute the merger. It has no operations,
no employees, no public profile. Once the merger closes, it usually merges
into the target and ceases to exist. The shell's name appears on the merger
agreement and in the shareholder vote materials. It is the legal counterparty
for litigation and post-closing claims.

**What the operating acquirer is:**
The corporate or sponsor entity that ACTUALLY made the bidding decisions, sat
at the negotiation table, and will own the target's assets through the shell.
This is the entity referenced in the auction narrative ("Hudson's Bay said
its best price was $16"), in news coverage, in analyst reports, and in M&A
league tables.

**Why both exist:**
The shell isolates legal liability and tax treatment. The Delaware Chancery
case law assumes the shell as the formal counterparty. But economically,
nothing about the shell matters — it's a pass-through.

### Options

**Option A: Use the operating acquirer (recommended for research)**

- Matches what every M&A research dataset does (Thomson, SDC, Refinitiv, etc.)
- Matches what the auction-process narrative uses
- Allows joining to acquirer characteristics (size, prior deals, industry)
- Loses the legal counterparty info (rarely needed in this kind of research)

**Option B: Use the legal acquirer**

- Matches the shareholder vote materials and merger agreement
- Useful if the research touches Delaware litigation or post-closing disputes
- Makes the dataset un-joinable to standard acquirer-characteristic data
- Forces every consumer to do their own shell-to-operating mapping

**Option C: Both (separate fields)**

- `acquirer_legal` and `acquirer_operating`
- Maximum information
- Schema bloat; downstream code must pick

### Recommendation

**Option A (operating acquirer).** This is what your research question almost
certainly cares about — who actually decided what to bid, who owns the assets
post-close, who the market reacts to. The legal vehicle is irrelevant to
auction theory and auction-process empirics.

Specifically for the four affected deals:

| Deal | Recommended `Acquirer` | NOT this |
|---|---|---|
| Petsmart | The Buyer Group (specific naming TBD) | `Argos Holdings Inc.` |
| Mac-Gray | `CSC ServiceWorks, Inc.` | `Spin Holdco Inc.` |
| Zep | `New Mountain Capital` | `NM Z Parent Inc.` |
| Saks | `Hudson's Bay Company` | `Harry Acquisition Inc.` |

For PE-led deals, the question of "fund vs sponsor brand" still arises (e.g.,
"Thoma Bravo Fund XII" vs "Thoma Bravo, LLC"). Recommend using the sponsor
brand (`Thoma Bravo, LLC`) for joinability and recognizability.

### Discussion points

1. Are there research questions you have in mind (current or future) that need
   the legal counterparty? If yes, Option C.
2. For consortium bids (Petsmart's Buyer Group has multiple PE sponsors), do
   you want one field with all members, or a primary plus members-list?
3. Does the schema need a `sponsor` field separately from `Acquirer` for cases
   like Mac-Gray where CSC is operationally the buyer but Pamplona is the
   funder?

### Decision (2026-04-26)

**`Acquirer` is the operating acquirer; `Acquirer_legal` is a new sidecar
for the legal shell when it differs.**

Four sub-decisions, all settled (Austin's "proceed as your recommendation"):

- **Q1 — Default (single-buyer cases):** Operating acquirer (the entity
  that negotiated, will own assets, appears in news / league tables).
  Reject the legal shell. This matches Thomson SDC, Refinitiv,
  MergerMarket, and every M&A research dataset.
- **Q2 — PE consortia / club deals:** Lead sponsor (largest LBO equity
  check / operationally lead per filing language); fall back to filing's
  verbatim consortium label if no lead is identifiable. For petsmart:
  `BC Partners, Inc.` (lead) over the full Buyer Group list.
- **Q3 — Schema shape:** One primary `Acquirer` field plus optional
  `Acquirer_legal: string | null` sidecar. No separate `sponsor` field
  — for the one deal that needs it (mac-gray: CSC operates, Pamplona
  funds), the funding sponsor goes in the `Executed` row's
  `additional_note`.
- **Q4 — Stickiness:** Deal-level only; no per-row change. The harder
  per-row consortium-membership question is governed by §E2.a / §E2.b.

### Rationale

- **Operating acquirer is the research convention.** The legal shell is
  irrelevant to auction theory, auction-process empirics, market
  reactions, and acquirer-characteristic joins. It exists only for
  liability isolation and Delaware Chancery case law and disappears at
  closing. Standard M&A research datasets (Thomson SDC, Refinitiv,
  MergerMarket) use the operating acquirer.
- **Sidecar instead of replacement.** `Acquirer_legal` is rarely needed
  (4 of 9 reference deals) but cheap to preserve. Drops nothing;
  downstream code that needs the legal counterparty for litigation or
  post-closing claims can join on it.
- **Lead sponsor for consortia.** Atomization at the deal level loses
  joinability. The lead sponsor is a clean primary key; the rest of the
  consortium is recoverable from the `Executed` row's
  `joint_bidder_members` per §E2.a.
- **No `sponsor` field.** Only mac-gray needs a third entity; not worth
  permanent schema bloat. Document Pamplona on the `Executed` row.

### Implementation (2026-04-26 — completed)

Five files touched:

1. **`rules/schema.md` §R1 (line ~197)** — `Acquirer` description
   updated to specify "operating acquirer per §N4"; new
   `Acquirer_legal: string | null` field added.
2. **`rules/schema.md` §N4 (new section, between §N3 and §R3)** —
   the full `Acquirer` decision rule. 5-rule decision table covering
   single corporate buyer, shell-mediated buyer, single PE sponsor as
   buyer, sponsor-backed corporate buyer, and PE consortium / club
   deal. Documents lead-sponsor heuristic, why operating not legal,
   why sidecar over replacement, why no separate sponsor field, and
   the per-deal reference values for the 4 sponsor-backed deals.
3. **`rules/schema.md` canonical example** — updated to include
   `"Acquirer_legal": null`.
4. **`prompts/extract.md` (Non-negotiable constraints, after
   "deal identity fields" bullet)** — new bullet codifies the §N4
   rule with shell-name-shape heuristics ("X Holdings Inc.",
   "X Acquisition Inc.", "X Parent Inc.", "X Merger Sub" → goes in
   `Acquirer_legal`), lead-sponsor instruction for consortia, and
   sponsor-backed-corporate-buyer pattern (operating in `Acquirer`,
   funding sponsor in Executed row's `additional_note`).
5. **`prompts/extract.md` deal-skeleton example** — `"Acquirer_legal": null`
   added.
6. **`scripts/build_reference.py`** — new constants:
   - `Q6_ACQUIRER_OVERRIDES` map for the 4 sponsor-backed deals
     (petsmart-inc, mac-gray, zep, saks) with operating + legal +
     human-readable note.
   - `apply_q6_acquirer_override(slug, deal)` mutates the deal in
     place when slug ∈ Q6 map, sets Acquirer / Acquirer_legal, appends
     `acquirer_overridden_per_q6` deal_flag with the original xlsx
     Acquirer string for provenance.
   - Wired into `build_deal()` immediately after `build_deal_object`,
     before the §Q1 saks pass.
   - `build_deal_object()` now seeds `Acquirer_legal: None` so all 9
     deals carry the field even when no override applies.
   - Module docstring extended with §Q6 entry.
7. **`scoring/diff.py` `COMPARE_DEAL_FIELDS`** — `Acquirer_legal` added.

### Verification (2026-04-26)

- `pytest tests/`: 103 passed in 2.83s.
- `python scripts/build_reference.py --all`: §Q6 override applied to 4
  deals; `Acquirer_legal` populated for them and null for the other 5.
- Reference values now match the §N4 decision table:
  | Deal | `Acquirer` | `Acquirer_legal` |
  |---|---|---|
  | medivation | `PFIZER INC` | null |
  | imprivata | `THOMA BRAVO, LLC` | null |
  | zep | `New Mountain Capital` | `NM Z Parent Inc.` |
  | providence-worcester | `GENESEE & WYOMING INC` | null |
  | petsmart-inc | `BC Partners, Inc.` | `Argos Holdings Inc.` |
  | penford | `INGREDION INC` | null |
  | mac-gray | `CSC ServiceWorks, Inc.` | `Spin Holdco Inc.` |
  | saks | `Hudson's Bay Company` | `Harry Acquisition Inc.` |
  | stec | `WESTERN DIGITAL CORP` | null |
- Each of the 4 overrides records its provenance in
  `deal_flags` with `acquirer_overridden_per_q6` (original xlsx text
  preserved in the reason field).

### Status

🟩 **IMPLEMENTED at policy + code level.** Pending: re-extract all 9
reference deals; petsmart's AI today emits `Argos Holdings Inc.`
(legal shell), so post-re-extraction it should match the reference's
`BC Partners, Inc.` and the diff drops the persistent Acquirer
mismatch on petsmart. The other 3 sponsor-backed deals should also see
clean Acquirer / Acquirer_legal alignment after the next AI run.

---

## 4. NDA scope: target-bidder only, or include inter-bidder/rollover CAs?

### Status: 🟥 OPEN. Austin has flagged legal-implications discussion needed.

### Problem statement

The schema event `NDA` was originally conceived as the auction-funnel
confidentiality agreement: target ↔ bidder, signed before the bidder gets
data-room access. Filings sometimes describe other confidentiality agreements
within the merger process, and the extractor today captures all of them as
`NDA` rows. This conflates three distinct things.

### The three CA types

**Type A: Target ↔ bidder NDA (auction NDA)**
The classic. Target shares non-public info with a potential bidder under
confidentiality and a standstill. This is the auction signal — counting NDAs
tells you how many parties seriously looked at the deal.

Petsmart example: 15 financial buyers signed CAs in the first week of October
2014. These are auction NDAs.

**Type B: Bidder ↔ bidder CA (inter-bidder / consortium CA)**
When two bidders combine into a consortium, they sign confidentiality
agreements with each other. This is a corporate-finance event, not an
auction-funnel event.

Petsmart example: Longview (an activist holder) signed CAs with bidders
during the auction. Not auction signal — it's the activist managing
information flow into the bidding consortium.

**Type C: Shareholder ↔ acquirer rollover CA**
Major shareholders who agree to roll equity into the new ownership structure
sign CAs as part of the negotiation. Operational; not auction signal.

### Why it matters

- Auction-process counts (how many bidders were "in the funnel") get inflated
  if Type B and Type C are mixed in
- Downstream stats like "average NDAs per deal" become noisy
- Conversely, dropping Type B/C entirely loses real information about
  consortium structure and rollover behavior

### Affected deals

Petsmart most clearly (Longview rollover CAs in December). Possibly others
where the AI may have over-emitted (Mac-Gray CSC/Pamplona joint CA — though
that's defensible as a single auction NDA for the consortium).

### Legal-implications framing for Austin

**What the legal scope of an auction NDA is:**
A target-bidder NDA grants the bidder access to material non-public
information. The standstill clause (often paired) restricts the bidder from
buying target stock or making unsolicited offers for X months. These
provisions exist because the bidder is now an insider.

**What a consortium NDA is:**
Two bidders agree to share their proprietary analysis, financing plans, or
strategic intent with each other. The legal clauses are mutual, not
asymmetric. This usually exists because the bidders are forming a joint
acquisition vehicle.

**What a rollover CA is:**
A major shareholder (often the founder, a strategic partner, or a holding
fund) agrees that as part of the merger, their equity will be converted into
equity in the post-merger entity. The CA covers the negotiation period.

**Why filings mention all three:**
The "Background of the Merger" section is required to disclose all material
events. Different CAs are material for different reasons. Litigation
discovery has historically pushed targets to over-disclose in this section.

### Options

**Option A: NDA = target-bidder only (strict)**

- Pro: clean auction-funnel signal
- Pro: matches Alex's intent
- Con: loses consortium/rollover information
- Implementation: extractor skips Type B and Type C; possibly emits an
  `info_flag` noting their existence

**Option B: NDA = any CA in the merger process (inclusive)**

- Pro: no information loss
- Pro: easier extractor logic (no scope decision required)
- Con: auction counts become noisy
- Con: requires downstream filtering for any auction-funnel analysis

**Option C: NDA = target-bidder; new event types for the others**

- New event: `Consortium CA` (Type B), `Rollover CA` (Type C)
- Pro: full information, preserved with semantic tags
- Pro: auction-funnel counts remain clean
- Con: schema bloat; three new event vocabulary entries
- Con: extractor must classify, sometimes from ambiguous filing language

### Recommendation pending discussion

**Option A (target-bidder only).** Reasoning:

- The research question is auction process; auction NDAs are the signal
- Type B and Type C are interesting but rare and analyzable separately
- Keeping the NDA event clean is more valuable than capturing every CA
- If Type B/C ever matter for a future paper, they can be re-extracted in a
  targeted pass

If Austin wants Option C, the schema cost is real but manageable.

### Discussion points

1. Have you ever needed to know about consortium structure (who joined whom)?
   If yes, Type B matters and Option C is better.
2. Have you ever needed rollover information for the dataset? If no, Option A.
3. For the Petsmart Buyer Group: do you want to know that it included a
   particular activist? That would push toward Option C.

### Decision (2026-04-26)

**Three CA types, three different treatments. Auction-funnel only.**

Four sub-decisions, all settled (Austin's "A yes, B new event type, C
skip, D confirm"):

- **Q1 — Auction-funnel counts only:** Yes. The `NDA` event vocabulary
  measures Type A (target ↔ bidder) confidentiality agreements only.
  Type B and Type C are different legal acts and must not contaminate
  the auction count.
- **Q2 — Type B (consortium) handling:** New event type
  `ConsortiumCA` (rank 5 alongside `NDA`). Captures bidder ↔ bidder
  consortium-formation CAs without polluting the NDA count.
- **Q3 — Type C (rollover) handling:** Skip entirely. New §M5 skip
  rule. Rollover CAs are out of scope for the auction-process schema.
- **Q4 — Petsmart Longview classification:** ConsortiumCA, not
  RolloverCA. Longview joined the BC Partners-led Buyer Group as a
  consortium constituent (named on the executed merger agreement),
  not as a passive shareholder rolling over equity.

### Rationale

- **Legal mechanics differ.** Type A grants MNPI access and pairs
  with a standstill. Type B is mutual information-sharing about
  bidder-side analysis. Type C is shareholder-side capital-structure
  negotiation. Conflating them muddles every downstream count.
- **Auction signal cleanliness.** The §Scope-1 auction threshold
  (≥2 NDA signers ⇒ `auction = true`) is meaningful only when `NDA`
  rows are exclusively Type A. Mixing Type B inflates the count.
- **Schema cost is one vocabulary entry.** `ConsortiumCA` adds 1
  closed-vocabulary value (vocabulary 30 → 31). The signal-cleanliness
  benefit applies to every analysis going forward.
- **Type C frequency justifies skipping.** Across the 9 reference
  deals, only petsmart has any candidate Type C narrative, and it
  resolves to Type B (per Q4). Capture-cost for a hypothetical
  future use > value at this scale.

### Implementation (2026-04-26 — completed)

Six files touched:

1. **`pipeline.py`** — `EVENT_VOCABULARY` adds `"ConsortiumCA"`;
   `EVENT_RANK` adds `"ConsortiumCA": 5`; vocabulary count comment
   updated 30 → 31.
2. **`rules/events.md` §C1** — `NDA` description rewritten to
   specify "target ↔ bidder (Type A per §I3)"; new `ConsortiumCA`
   entry; total count updated 30 → 31.
3. **`rules/events.md` §I3 (new section, between §I2 and §J1)** —
   full three-CA-type definition with disambiguation table,
   ConsortiumCA emission rule, validator behavior summary
   (§P-S1 / §P-S2 / §P-D5 / §P-D6 all checked), why-new-event-type
   reasoning, why-skip-Type-C reasoning, cross-references.
4. **`rules/bids.md` §M5 (new section, before §H1)** — Type C
   skip rule with definition, identification heuristics
   (rollover-language patterns), Type B vs Type C ambiguity
   tiebreaker (default to Type B with `ca_type_ambiguous`), why-skip
   rationale.
5. **`prompts/extract.md`** — Step 7 expanded with the three-CA-type
   classification block (Type A → NDA, Type B → ConsortiumCA, Type C
   → skip per §M5); Step 9 references §M5; Step 7 DropSilent
   paragraph notes that ConsortiumCA signers don't trigger §I1; new
   self-check item "CA classification (§I3)".
6. **`scripts/build_reference.py` `A3_RANK`** — `"ConsortiumCA": 5`
   added with comment noting no synthesis (Alex's xlsx coding
   doesn't preserve the CA-type distinction).

**Validator interactions (no code change needed; pre-existing logic
already correct):**

- `_invariant_p_s1` (line 925) — already filters on
  `bid_note != "NDA"`; ConsortiumCA does not trigger
  `missing_nda_dropsilent`.
- `_invariant_p_s2` (line 1024) — already filters on
  `bid_note == "NDA"`; ConsortiumCA does not count toward auction
  threshold.
- `_invariant_p_d6` (line 685) — already requires
  `bid_note == "NDA"` for the precondition; ConsortiumCA does not
  satisfy NDA-before-Bid.
- `_invariant_p_d5` (line 612) — `engagement_notes` set is
  `{"NDA", "Bidder Interest", "IB"}` (plus all Drop codes);
  ConsortiumCA is intentionally NOT in this set, so a bidder who
  signed only a ConsortiumCA and then dropped will fire §P-D5
  (intentional: the filing should narrate target-bidder engagement
  before withdrawal).

**Reference data:** No `§Q7` override added. Alex's xlsx coding
doesn't preserve the CA-type distinction (only `NDA`); his
"Buyer Group" NDA aggregations (e.g., petsmart) may correspond to
Type A or Type B depending on filing context. Per the
"Alex's reference stays unchanged" pattern from Decisions #1–#3, the
reference is not regenerated. The diff harness will surface
AI-vs-Alex disagreements (e.g., AI reclassifies petsmart's
Longview/Buyer Group rows as `ConsortiumCA`; Alex has them as `NDA`)
as cardinality mismatches Austin can adjudicate per deal.

### Verification (2026-04-26)

- `pytest tests/`: 103 passed in 2.69s.
- `python scripts/build_reference.py --all`: rebuild succeeds; no
  new reference deltas from Decision #4 (the deltas visible in
  `git diff reference/alex/` are all from Decision #3's
  `Acquirer_legal` field addition).
- `from pipeline import ...`: `EVENT_VOCABULARY` size = 31;
  `ConsortiumCA` ∈ `EVENT_VOCABULARY`; `EVENT_RANK['ConsortiumCA'] = 5`;
  `ConsortiumCA` ∉ `BID_NOTE_FOLLOWUPS` (correct — does not discharge
  §P-S1 silent-NDA obligation).

### Status

🟩 **IMPLEMENTED at policy + code level.** Pending: re-extract all 9
reference deals; petsmart's AI today emits 2 `bid_note = "NDA"` rows
for "Longview and the Buyer Group" (12/9 + 12/12); after re-extraction
those should reclassify to `ConsortiumCA`. Cardinality mismatches
against Alex's `NDA`-coded rows are adjudication signal, not noise.
Other deals are unlikely to be affected (zep, mac-gray, providence,
imprivata, medivation, penford, saks, stec do not appear to narrate
clear Type B / Type C CAs in initial inspection).

---

## 5. Same-price reaffirmations: new bid row or note?

### Status: 🟥 OPEN.

### Problem statement

Multiple deals show this pattern: a bidder submits a price, then later
restates the same price (often during merger-agreement negotiations or in
response to a "best and final" request). The extractor today sometimes emits
a second `Bid` row at the same price, and sometimes does not. Inconsistent.

### Why it matters

- Bid counts per deal become unstable (run-to-run variance)
- Auction "rounds" analyses get polluted with non-rounds
- The validator can't tell what's right because the rule isn't written

### Affected deals

- **Zep**: New Mountain reiterated its $20.05 best-and-final in April 2015
  during merger-agreement negotiations. AI emitted a separate row.
- **Penford**: Ingredion's October 14 confirmation of the $19.00 price
  before signing. AI emitted a separate row.
- **STec**: WDC's May 30 verbal confirmation of its May 28 $9.15 best-and-
  final, in response to the board's "best and final by May 30" request. AI
  emitted a separate row.

### The four sub-cases

**Case 1: True new bid**
Bidder submits at a NEW price, OR with new merger-agreement structure, OR
with new financing commitments, OR through a new process step. Clearly an
event. Always emit a row.

**Case 2: Verbal reiteration during ongoing negotiations**
Bidder says "my $X stands" in a phone call between scheduled events. No new
content. Currently sometimes emitted, sometimes not.

**Case 3: Best-and-final confirmation in response to a process request**
Board says "submit best and final by Friday." Bidder says "$X is best and
final" (same as prior). This is a process event (it answers the question)
but not an economic event (no price change).

**Case 4: Pre-signing reaffirmation**
Day-of-signing call: "Yes, we're still at $X, ready to sign." Operational
glue. Almost certainly not a bid event.

### Options

**Option A: Same price → never a new row. Add to `additional_note` on prior bid.**

- Pro: bid counts measure economic events
- Pro: unambiguous rule; no judgment required
- Con: loses process granularity (when did the bidder confirm vs first state?)

**Option B: Same price → new row IF the filing narrates a process step.**

- Pro: process events get captured
- Con: requires extractor to judge "process step or not"
- Specifically: Cases 1 and 3 emit; Cases 2 and 4 do not

**Option C: Same price → new row if it's at a different process stage.**

- Process stages: initial IOI, revised IOI, first-round bid, final-round bid,
  best-and-final, pre-signing
- One row per (bidder, process stage)
- Pro: structured
- Con: complicated rule; requires the extractor to track process stage

### Recommendation pending discussion

**Option B (process step → new row, otherwise note).** Specifically:

- Case 1 (new content): always a new bid row
- Case 2 (verbal reiteration in ongoing negotiations): NOT a new bid; add to
  additional_note on the prior row
- Case 3 (best-and-final in response to a process request): NEW bid row,
  even if same price — because it's the bidder's substantive response to a
  formal process step
- Case 4 (pre-signing): NOT a new bid; this is execution glue

The Case 3 carve-out is the only judgment call, and the extractor can be told
to look for "best and final" or "in response to" language.

### Discussion points

1. Is the "process granularity" valuable to you? In auction theory, the
   answer is usually yes — knowing that Bidder A confirmed $X under a "best
   and final" deadline tells you something about commitment.
2. If we go with Option A (simpler), we lose the ability to ask "when did
   each bidder commit to their final price?" Acceptable?
3. Should there be a distinct `Bid Confirmation` event type for Case 3, to
   keep `Bid` rows pure to economic events?

### Decision (to be filled in after discussion)

_Pending Austin discussion_

### Implementation (after decision)

- `rules/bids.md` — add the new section (suggested name: §C5 or §G3,
  "reaffirmations and confirmations")
- `prompts/extract.md` — explicit guidance with worked examples
- Possibly `rules/events.md` if a new event type is added
- Affected deals (zep, penford, stec) need regeneration

---

## 6. IB date anchor: board approval vs engagement letter vs first action

### Status: 🟥 OPEN.

### Problem statement

When the filing narrates an investment bank engagement, three dates often
appear:

- **Board-approval date**: the target's board approves retaining the IB
- **Engagement-letter date**: the IB and target sign the engagement letter
- **First-action date**: the IB performs its first observable action
  (e.g., sends process letters, contacts buyers, presents to the committee)

These dates can differ by hours, days, or weeks. The current §J1 says use
"earliest narrated date acting in advisory capacity." This is vague enough
that extractor and reference disagree.

### Why it matters

- Affects every IB row in every deal
- Determines what "IB engagement length" looks like in the dataset
- Affects whether IB events appear before or after early bidder events on
  the timeline

### Affected deals

- **STec**: board approval 2013-03-26, engagement letter 2013-03-28. AI used
  03-26; Alex used 04-04 (which is wrong — looks like a process date). The
  rule should pick one.
- **Penford**: board direction to "proceed to retain Deutsche Bank" on July
  24; first observed advisory action on August 11. AI used Aug 11; Alex
  conflated.

### The three candidate anchors

**Anchor A: Board approval to retain**

- Earliest date
- Definite filing language ("the board approved retaining X")
- Not always present (sometimes management retains without board action)
- Conceptually: when the target committed to engaging the bank

**Anchor B: Engagement letter execution**

- Legally binding
- Usually a few days after board approval
- Filing language is precise ("X entered into an engagement letter on Y")
- Conceptually: when the legal advisory relationship started

**Anchor C: First narrated advisory action**

- Most observable in the filing
- Sometimes precedes engagement letter (banks act before paperwork)
- Most "narrative" — matches what the auction process looks like
- Conceptually: when the bank started actually advising

### Options

**Option A: Always use board approval (when stated); fall back to engagement
letter; fall back to first action.**

- Pro: earliest available; aligns IB row before any subsequent bidder events
- Con: when board approval isn't stated, falls to engagement letter — which
  itself is sometimes inferred

**Option B: Always use engagement letter (when stated); fall back to board
approval; fall back to first action.**

- Pro: legally clear
- Pro: standard finance-research convention (M&A league tables use signing
  date)
- Con: not always explicitly stated in the filing

**Option C: Always use first narrated action.**

- Pro: matches what the auction-process narrative actually looks like
- Pro: avoids the "approval but not yet acting" gap
- Con: latest date; IB row may appear well after the bank started informally
  advising
- Con: requires inference from narrative
- This is the current §J1.

### Discussion: what's standard in finance research?

For M&A advisory data, the major commercial datasets use **public announcement
date** (the day the deal becomes public) as the IB anchor. Proxy-extracted
data is a different beast — the proxy describes the engagement explicitly.

For auction-process research specifically, what matters is when the IB
**started running the auction**. That is typically:

- For target advisors: when they began contacting buyers
- For acquirer advisors: when they began assessing the bid

These are first-action events, not engagement-letter events.

### Recommendation pending discussion

**Option B (engagement letter when stated; fall back to board approval; fall
back to first action).** Reasoning:

- Engagement letter is unambiguous and legally definite
- Most filings state it
- Matches finance-research convention
- Fallback chain handles the rare cases when it's missing

For STec specifically: this would set the IB date to 2013-03-28 (engagement
letter), not 2013-03-26 (board approval) or 2013-04-04 (Alex's wrong date).

### Discussion points

1. Does the auction-research literature have a convention here? The closest
   convention is the SDC/Thomson "announcement-date IB," which doesn't
   apply to proxy-extracted data.
2. Is there a research question that hinges on the gap between board
   approval and engagement letter? If yes, may need both fields.
3. For acquirer-side IBs, the engagement letter is usually before the
   acquirer is publicly known — does that affect the anchor choice?

### Decision (to be filled in after discussion)

_Pending Austin discussion_

### Implementation (after decision)

- `rules/dates.md` §J1 — rewrite with the chosen anchor and fallback chain
- `prompts/extract.md` — instruct extractor on the anchor preference
- All 9 reference deals will need IB date review and possible regeneration

---

## Sequencing (after this file is filled in)

When all six decisions are made, the order of work is:

1. Implement #1 (NDA-silent → Drop) — biggest noise reduction; deterministic
2. Implement #2 (`public` field) — biggest diff-noise reduction
3. Decide and implement #3 (`Acquirer`) — affects 4 deals
4. Decide and implement #4 (NDA scope) — affects 1-2 deals
5. Decide and implement #5 (reaffirmations) — affects 3 deals
6. Decide and implement #6 (IB anchor) — affects all 9 deals (small change each)

Then: regenerate all 9 reference deals from the updated rulebook, run the
diff harness, and confirm the noise floor has dropped substantially. Only
then start the rulebook-stability clock.

---

## Change log

| Date | Change |
|---|---|
| 2026-04-26 | File created. #1 decided at policy level; #2-6 framed for discussion. |
| 2026-04-26 | #4 implementation completed. Files: `pipeline.py` (`EVENT_VOCABULARY` + `EVENT_RANK` add `ConsortiumCA` at rank 5; vocabulary count 30 → 31), `rules/events.md` (§C1 `NDA` description specifies "target ↔ bidder Type A"; new `ConsortiumCA` entry; new §I3 with three-CA-type definitions, disambiguation table, validator behavior summary), `rules/bids.md` (new §M5 skip rule for Type C rollover CAs), `prompts/extract.md` (Step 7 expanded with three-CA-type classification block; Step 9 references §M5; new self-check item "CA classification (§I3)"; DropSilent paragraph notes ConsortiumCA exclusion), `scripts/build_reference.py` (`A3_RANK` adds `ConsortiumCA: 5` for vocabulary completeness; no synthesis). All 103 tests pass; ConsortiumCA ∈ EVENT_VOCABULARY (size 31); ConsortiumCA ∉ BID_NOTE_FOLLOWUPS (correct — does not discharge §P-S1). No reference regeneration needed (Alex's xlsx coding doesn't preserve the CA-type distinction; AI-vs-Alex CA reclassifications surface as adjudication signal). Pending: re-run extractor — petsmart's 2 "Longview and the Buyer Group" NDA rows (12/9 + 12/12) should reclassify to ConsortiumCA. |
| 2026-04-26 | #3 implementation completed. Files: `rules/schema.md` (§R1 `Acquirer` clarified to operating; new `Acquirer_legal` field added; new §N4 with 5-rule decision table covering single buyer / shell-mediated / single PE sponsor / sponsor-backed corporate / PE consortium; canonical example updated), `prompts/extract.md` (new non-negotiable bullet codifies §N4 with shell-name heuristics + lead-sponsor instruction + sponsor-backed-corporate pattern; deal skeleton example updated), `scripts/build_reference.py` (new §Q6 override with `Q6_ACQUIRER_OVERRIDES` map + `apply_q6_acquirer_override()` function for petsmart-inc, mac-gray, zep, saks; module docstring extended; `Acquirer_legal: null` seeded in `build_deal_object()`), `scoring/diff.py` (`Acquirer_legal` added to `COMPARE_DEAL_FIELDS`). All 103 unit tests pass. Reference rebuild applies the 4 overrides correctly with provenance flags; the other 5 deals carry `Acquirer_legal: null`. Pending: re-run extractor on all 9 reference deals — petsmart's AI today emits `Argos Holdings Inc.` (legal shell); post-re-extraction it should match the reference's `BC Partners, Inc.` and the persistent Acquirer mismatch drops. |
| 2026-04-26 | #2 implementation completed. Files: `rules/bidders.md` (§F1 type signature → `bool | null`; §F2 derivation rule rewritten with strict-filing-only tri-state semantics; pre-2026 PE-firm `public=false` carve-out removed), `rules/schema.md` (§R1 `bidder_type.public` updated to `bool | null`), `prompts/extract.md` (new non-negotiable constraint on tri-state `public` rule). No changes needed in `scripts/build_reference.py` (already produces `null` for silent rows; zero `public=false` rows in actual reference data) or `pipeline.py` (no validator enforces `public` typing). All 103 unit tests still pass. Reference rebuild bit-identical. Simulation: 302 currently-spurious AI `public=false` rows across the 9 deals will flip to `null` after re-extraction, collapsing the largest single source of field mismatches in the 04-23 diff. Pending: re-run extractor on all 9 reference deals. |
| 2026-04-26 | #1 implementation completed. Plan: `~/.claude/plans/i-think-encodinga-dropsilent-abundant-moler.md`. Files touched: `pipeline.py` (vocabulary + `_invariant_p_s1` rename to `missing_nda_dropsilent`), `rules/events.md` (§C1 + §I1 reversal), `rules/invariants.md` (§P-S1 rewrite), `rules/bids.md` (§M1/§M2 context), `prompts/extract.md` (Step 7 + Step 9 + self-check), `scripts/build_reference.py` (A3_RANK vocab only), `scoring/diff.py` (`AI_ONLY_BID_NOTES` filter), `tests/fixtures/synthetic_ps1_fail.json` (renamed flag), `tests/fixtures/synthetic_ps1_dropsilent_pass.json` (new positive test), `tests/test_invariants.py` (parametrize), `report/scripts/build_figures.py` (label), `SKILL.md` (flag rename). All 103 unit tests pass. Old flag `nda_without_bid_or_drop` produces 0 across the 9 reference deals. New flag `missing_nda_dropsilent` produces 54 on the existing pre-policy extractions, correctly identifying NDAs that need DropSilent rows added by the next extractor run. Pending: re-run extractor on all 9 reference deals to drive `missing_nda_dropsilent` count to 0. |

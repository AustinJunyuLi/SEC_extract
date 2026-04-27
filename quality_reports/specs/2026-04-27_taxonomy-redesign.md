# Taxonomy Redesign — Classification Vocabulary and Schema

**Date:** 2026-04-27
**Status:** RATIFIED — three adversarial review rounds complete; ready for implementation (rules/prompt rewrite + 9-deal regeneration)
**Scope:** `bid_note` closed vocabulary, drop subcodes, final-round matrix, adjacent classification systems, plus schema columns driven by the screening-model data needs.
**Backward compatibility:** None. Per CLAUDE.md "no backward compatibility" rule, old extractions are regenerated under the new schema; no migration shims, no dual-format readers.

---

## 1. Problem statement

The current `bid_note` closed vocabulary (`rules/events.md` §C1) carries 31 codes accreted by edge-case addition over the rule-resolution phase. Empirical usage across the 9 reference deals (435 events) shows:

- **2 codes never fired** (`Final Round Inf Ext Ann`, `Final Round Inf Ext`, `Sale Press Release`).
- **9 codes fired in exactly 1 deal** (one-deal accretions).
- **The top 6 codes account for 57% of all events.** The taxonomy is ~3× the size the data needs.
- **AI-confusion clusters in the drop subcodes (6 codes) and the final-round matrix (9 codes).** Adjudication evidence: 12+ verdicts on drop-subcode disagreements, 7+ verdicts on final-round-matrix disagreements across 9 deals.

Senior collaborator Alex acknowledged on 2026-04-27 that the taxonomy was over-specified by accretion. Austin authorized a redesign with no backward-compatibility constraint, optimized for "most accurate and streamlined."

## 2. Research-question scope

Per Austin's decision (2026-04-27 conversation): the dataset must continue to support Alex's broader research agenda beyond the current screening-model paper, including potential analyses of dropout heterogeneity, process-design effects, advisor effects, and activism effects. **Scope (B)** — not the most aggressive simplification possible, but ruthless within each axis.

The current screening model's data inputs (per the `informal_bids` simulation repo) are narrow:
- per-bidder informal bid value + range
- per-bidder admission to the formal stage (binary)
- per-bidder formal bid value or NaN
- per-bidder type (strategic / financial)
- per-auction bidder count, share strategic, exogenous instrument Z

This spec adds `invited_to_formal_round` and `submitted_formal_bid` columns to separate the target's admission decision from the bidder's formal-bid submission (currently inferred from event combinations) without sacrificing structure for future research.

## 3. `bid_note` closed vocabulary: 31 → 18

### Codes kept (18)

| Code | Why | Filing language signature |
|---|---|---|
| `NDA` | Workhorse #1; auction-funnel signal | "executed a confidentiality agreement with" |
| `Bid` | Workhorse #2; carries informal/formal via `bid_type` | submitted indication / proposal / offer |
| `Drop` | Consolidated drop event | bidder withdrawal or target rejection (any agency) |
| `DropSilent` | Inferred-from-silence; structurally distinct (evidence is the absence of later activity) | NDA signer with no later narration |
| `IB` | Universal | "engaged [bank]", "first action of advisor" |
| `IB Terminated` | Mac-Gray edge but unambiguous signature | "terminated the engagement" |
| `Executed` | Universal closing event | "executed the merger agreement" |
| `Target Sale` | Board sale resolution | "the Board determined to explore a sale" |
| `Target Sale Public` | Public announcement of sale process (when distinct from Target Sale date) | "issued a press release announcing strategic alternatives" |
| `Bidder Interest` | First-contact bidder approach, no concrete proposal | "informally approached", "expressed interest" |
| `Bidder Sale` | Bidder-initiated acquisition intent without concrete price | "interest in acquiring" |
| `Activist Sale` | Activist pressure event | "filed Schedule 13D", "open letter urging sale" |
| `Final Round` | Single round-structure event; modifiers carry the rest | "process letters sent", "final bids due" |
| `Auction Closed` | Target halt without announced deadline (semantically distinct from Final Round) | "process concluded", "no further engagement" |
| `Terminated` | Formal abandonment of a process phase | "decided to terminate the process" |
| `Restarted` | Phase-2 restart marker | "[bidder] re-engaged after the prior process ended" |
| `Press Release` | Unified publicity event | "issued a press release" |
| `ConsortiumCA` | Bidder-to-bidder confidentiality agreement | "[bidders] entered into a CA among themselves" |

### Codes eliminated (13)

| Source | Disposition | Captured as |
|---|---|---|
| `DropBelowM` | merge into `Drop` | `drop_initiator = "target"`, `drop_reason_class = "below_minimum"` |
| `DropBelowInf` | merge into `Drop` | `drop_initiator = "target"`, `drop_reason_class = "never_advanced"` |
| `DropAtInf` | merge into `Drop` | `drop_initiator = "bidder"`, `drop_reason_class = null` (default) or `"no_response"` (only when filing literally narrates non-response) |
| `DropTarget` | merge into `Drop` | `drop_initiator = "target"`, `drop_reason_class = "target_other"` |
| `Final Round Ann` | merge into `Final Round` | `final_round_announcement = true` |
| `Final Round Inf Ann` | merge into `Final Round` | `final_round_announcement = true`, `final_round_informal = true` |
| `Final Round Inf` | merge into `Final Round` | `final_round_informal = true` |
| `Final Round Ext Ann` | merge into `Final Round` | `final_round_announcement = true`, `final_round_extension = true` |
| `Final Round Ext` | merge into `Final Round` | `final_round_extension = true` |
| `Final Round Inf Ext Ann` | merge into `Final Round` | all three booleans true |
| `Final Round Inf Ext` | merge into `Final Round` | `final_round_extension = true`, `final_round_informal = true` |
| `Bid Press Release` | merge into `Press Release` | `press_release_subject = "bidder"` |
| `Sale Press Release` | merge into `Press Release` | `press_release_subject = "sale"` |
| `Target Interest` | merge into `Bidder Interest` | direction noted in `additional_note` ("target-initiated"); see §6 |

Net `bid_note`: **31 → 18 (−42%)**.

## 4. New structured columns (8)

### 4.1 `drop_initiator`

Type: `"bidder" | "target" | "unknown"`.
Required on every `Drop` row. Null on `DropSilent` (silent by definition).

**Assignment rule** (deterministic from filing language):
- Filing names the *target* as the subject of the rejection ("the Special Committee determined", "Barclays informed [bidder] that…", "the Board did not advance", "[Target] decided not to continue") → `target`.
- Filing names the *bidder* as the subject of the withdrawal ("[bidder] withdrew", "declined to continue", "did not submit", "stopped responding", "informed [Target] that it would not…") → `bidder`.
- Filing's agency language is genuinely ambiguous (passive voice, no clear subject) → `unknown`. Soft flag `drop_initiator_ambiguous` with the unclear quote.

**Edge case (Stec Company F pattern):** when a bidder "declined" but the underlying reason is target-scope-driven (e.g., "Company F declined because it was only interested in limited assets and the target wasn't selling assets"), follow the verb's subject — `bidder` initiator, with `drop_reason_class = "scope_mismatch"` (per §4.2) and the verbatim reason in `drop_reason_note`. Do NOT recode as `target_other` based on inferred underlying agency. Filings are ground truth; the verb subject is what the filing says; the structured `scope_mismatch` value keeps the reason queryable.

### 4.2 `drop_reason_class`

Type: `"below_market" | "below_minimum" | "target_other" | "no_response" | "never_advanced" | "scope_mismatch" | null`.
Required-when-applicable per the matrix below.

| `drop_initiator` | Allowed `drop_reason_class` values |
|---|---|
| `target` | `below_market` / `below_minimum` / `target_other` / `never_advanced` / `scope_mismatch` (one required) |
| `bidder` | `null` (default) OR `no_response` (only when filing literally narrates the bidder did not respond) OR `scope_mismatch` |
| `unknown` | `null` |

Use `scope_mismatch` when the filing text indicates the bidder's interest ended because the asset or scope on offer did not match what the bidder sought, regardless of which party initiated.

**Why bidder-side defaults to null** (per GPT adversarial review 2026-04-27): forcing voluntary withdrawals into a closed reason class would mislabel narrated reasons (e.g., "no longer interested due to other priorities") as `no_response` and corrupt downstream dropout-heterogeneity analyses. The free-text `drop_reason_note` already preserves the bidder's stated reason verbatim; a closed taxonomy of voluntary-exit reasons is not justified by the 9-deal sample and would invent structure the filings don't carry.

**Validator** (new soft check `drop_reason_class_inconsistent`): flag when `drop_initiator = "bidder"` and `drop_reason_class ∉ {null, "no_response", "scope_mismatch"}`, OR when `drop_initiator = "target"` and `drop_reason_class = null`, OR when `drop_initiator = "target"` and `drop_reason_class = "no_response"` (target rejections are not "no response" events).

### 4.3 `final_round_announcement`

Type: `bool`. Required on every `Final Round` event.

`true` when the row records the *announcement* / process-letter / invitation event ("Barclays sent final bid process letters requesting bids by July 8").
`false` when the row records the *deadline / submission* event ("on July 8, only Thoma Bravo submitted a bid").

### 4.4 `final_round_extension`

Type: `bool`. Required on every `Final Round` event.

`true` when the row records an extension or re-request after a prior final-round event ("after May 28 bids, the Board directed BofA to request best-and-final by May 30").
`false` when the row records the first/initial final round.

### 4.5 `final_round_informal`

Type: `bool | null`. Required on every `Final Round` event.

(Added per GPT adversarial review 2026-04-27.)

`true` when the round is announced/conducted as informal — non-binding indications of interest, preliminary proposals, no binding-offer requirement.
`false` when the round is formal — binding bids, final/best-and-final, process letter requests definitive offers, draft merger agreements required.
`null` only when the filing genuinely doesn't classify the round.

**Why this is necessary** (against the original audit's "informal-ness derives from paired Bid rows" argument): the existing rulebook uses `Final Round Ann` vs `Final Round Inf Ann` as a *process-position fallback* under §G1 to classify bids whose own language lacks explicit informal/formal triggers. If the round row inherits informal-ness from the bid rows, a bid with a non-trigger source quote becomes unclassifiable — circular dependence. Empirical 9-deal evidence (per `rules/invariants.md` §P-G2): 30% of bids relied on §G1 trigger phrases, 29% on range-shape, 55% on inference notes; the round's informal/formal signal is a non-redundant disambiguator.

**Pairing rule (deterministic):** A `Bid` row is "paired" first with the most recent `Final Round` event in the same `process_phase` whose `final_round_announcement = false` AND whose `bid_date_precise <= bid.bid_date_precise`. If no paired non-announcement row exists, fall back to the most recent applicable `Final Round` event in the same `process_phase` regardless of `final_round_announcement`, subject to `final_round.bid_date_precise <= bid.bid_date_precise`. If no applicable `Final Round` event exists, the bid is not in a final round (likely informal-stage indication; bid_type defaults to informal per §G1's pre-process-letter rule).

**Validator (new hard check `final_round_missing_non_announcement_pair`):** flag when a `Final Round` row with `final_round_announcement = true` is followed by one or more `Bid` rows in the same `process_phase` but has no paired non-announcement `Final Round` row. Message: "Final Round announcement has subsequent bids but no paired non-announcement Final Round row — check for missing row."

### 4.6 `press_release_subject`

Type: `"bidder" | "sale" | "other" | null`. Required on every `Press Release` event.

- `"bidder"` — public announcement of a bidder's proposal (formerly `Bid Press Release`).
- `"sale"` — public announcement of a target's sale process (formerly `Sale Press Release`); use only when the publicity event is structurally distinct from `Target Sale Public`.
- `"other"` — other public statements (rare).

### 4.7 `invited_to_formal_round`

Type: `bool | null`. Required on every `Bid` row with `bid_type = "informal"` in `process_phase >= 1`.

Driven by the screening-model data needs (per the `informal_bids` simulation, `core/modeling/types.py:ScreeningAuctionObs.admitted`). Encodes the target's act only:

- `true` — target explicitly advanced the bidder past the informal screen or invited the bidder to the formal round.
- `false` — bidder did not advance to a formal-round invitation (target cut OR bidder withdrew before invitation).
- `null` — process did not reach a formal round (e.g., Zep first auction terminated; saks no formal round; pre-execution informal-only deals).

`invited_to_formal_round = true` does not require a paired formal `Bid` row; STec Company D-style invited-but-no-formal-bid cases remain valid.

### 4.8 `submitted_formal_bid`

Type: `bool | null`. Required on every `Bid` row with `bid_type = "informal"` in `process_phase >= 1`.

Encodes the bidder's act only:

- `true` — bidder actually submitted a formal `Bid` row in the same phase.
- `false` — bidder did not submit a formal bid in that phase.
- `null` — process did not reach a formal round (e.g., Zep first auction terminated; saks no formal round; pre-execution informal-only deals).

**Validator (new soft check `formal_round_status_inconsistent`):** flag when:
- A bidder has `submitted_formal_bid = true` on their informal bid but no paired formal `Bid` row in the same phase.
- A bidder has `submitted_formal_bid = false` but a formal `Bid` row in the same phase.
- A bidder has a `Drop` event with `drop_reason_class = "never_advanced"` but `invited_to_formal_round != false`.

## 5. Schema fields dropped

### 5.1 `bidder_type = "mixed"` (value)

Empirical: 0 rows across 9 deals × 435 events. Universal atomization (§E1/§E2.b) emits one row per identifiable consortium constituent, each carrying scalar `"s"` or `"f"`. "Mixed" is a derived deal-level property recoverable via aggregation (any `Executed` row carrying both `"s"` and `"f"` constituents → mixed deal).

Vocabulary becomes `{"s", "f", null}`. §F1's decision rule loses row 5 (consortium-mixed case). Validator §P-R6 updated.

### 5.2 `joint_bidder_members` (column)

Empirical: 0 rows populate it under the 2026-04-27 universal-atomization directive. Pure schema bloat. Drop the column entirely. Consortium membership is recoverable from same-date `Executed` rows sharing the deal's winner narrative, plus the deal-level `bidder_registry`.

## 6. `Target Interest` → `Bidder Interest` merge

Empirical: 3 emissions across 9 deals (Mac-Gray Party A April 8; Petsmart Industry Participant March 2014; Stec BofA outreach to bidder list — the last is misuse per adjudication, 33% misuse rate).

The legitimate cases (Mac-Gray, Petsmart) are structurally identical to `Bidder Interest` from the auction-process perspective: exploratory contact between target and a specific party with no price. The directional distinction (target-initiated vs bidder-initiated) is preserved in `additional_note` ("target-initiated") and visible in `source_quote`. Removing `Target Interest` eliminates a 33%-misuse-rate code requiring directional judgment that filings often muddy.

## 7. ConsortiumCA boundary tightening (vocabulary kept, prompt sharpened)

Empirical: 5 emissions in 1 deal (Petsmart). Adjudication: 3 of 5 are misuses (rows 41, 42, 45). The pattern: AI used `ConsortiumCA` for any "bidders working together" narration, including "permission to work together" (which is NOT a CA event) and Type-A NDAs misclassified as Type B.

Prompt changes (no vocabulary change):

1. **Hard rule**: `ConsortiumCA` REQUIRES the filing to explicitly say a confidentiality agreement was "entered into" / "executed" / "signed" between two or more bidders. Phrases like "permission to work together," "authorized to coordinate," "discussions among bidders," "joint participation in due diligence" do NOT count.

2. **Misuse-trap example** in the prompt: cite Petsmart Bidder 3's "two bidders requested and received permission to work together" passage as a non-CA event (do NOT emit `ConsortiumCA`).

3. **Validator promotion**: `ca_type_ambiguous` from soft to hard. The soft-flag-without-action pattern observed in 2026-04-27 production run shows the AI does not adjust on soft flags; hard-flag forces adjudication.

## 8. Boundary-tightening prompt rules (no vocabulary change)

### 8.1 `Bidder Interest` continuation guard

Per Providence-Worcester adjudication: AI over-emits `Bidder Interest` for already-active bidders' continuation events (G&W Aug 9, Party B Aug 12 — both already had NDA + bid earlier).

Prompt rule: `Bidder Interest` is for *first-contact initiation only*. A later diligence call, negotiation contact, or follow-up meeting with a bidder who already has a `Bidder Interest`, `NDA`, or `Bid` row in the same process_phase does NOT warrant a fresh `Bidder Interest` row. Such activity belongs in `additional_note` on the relevant existing row, or as `source_quote` context.

### 8.2 `Target Sale` over-emission guard

Per Zep adjudication (`both-wrong`): AI emitted two `Target Sale` rows for one process (July 1, 2013 + Feb 27, 2014).

Prompt rule: emit at most one `Target Sale` per `process_phase` unless the filing narrates a *re-authorization* event (board re-affirms the sale process after a hiatus). Boilerplate strategic-review discussions do not count.

## 9. Conversion-test examples

(Per GPT adversarial review recommendation 2026-04-27.) The following adjudication-derived examples are the validation fixtures for the drop-classification logic. The prompt and rule documentation MUST cite at least these examples to anchor the AI's decisions.

### Drop classification fixtures

| Deal | Filing language | `drop_initiator` | `drop_reason_class` | `drop_reason_note` |
|---|---|---|---|---|
| Imprivata Strategic 1 | "Strategic 1 was no longer interested and would not submit an indication of interest" | `bidder` | `null` | "no longer interested" |
| Imprivata Strategic 2 | "Strategic 2 was no longer interested in exploring a potential transaction because of other internal corporate priorities" | `bidder` | `null` | "internal corporate priorities" |
| Imprivata Strategic 3 | "Strategic 3 was no longer interested because of its internal focus on other corporate transactions and a perceived overlap in technologies" | `bidder` | `null` | "internal focus + tech overlap" |
| Imprivata Sponsor A | "any second-round bid would not be meaningfully higher than its June 9 price; Barclays told Sponsor A the Board would not be interested at essentially the same valuation" | `target` | `never_advanced` | "Board declined to advance at June-9 price" |
| Mac-Gray Party C | "Party C did not submit a revised indication of interest or reiterate its prior indication of interest" | `bidder` | `no_response` | (null) |
| Mac-Gray Party A | "Special Committee chose CSC/Pamplona over the other indications and authorized moving toward exclusivity only if CSC/Pamplona increased above $20.75 to $21.25" | `target` | `below_minimum` | "below board's stated minimum" |
| Mac-Gray Party B | "Party B's contingent/deferred option value and financing risk even though headline value was facially higher" | `target` | `target_other` | "financing risk" |
| Saks Sponsor A/E | "the board would not agree to an acquisition below $16/share; Sponsor A and Sponsor E did not indicate readiness to improve beyond the $14.50-$15.50 range" | `target` | `below_minimum` | "below board's stated $16 minimum" |
| Petsmart Industry Participant | "J.P. Morgan told Industry Participant it would not be invited into the sale process because of the board's concerns" | `target` | `target_other` | "board concerns" |
| Petsmart Financial 5/6 | "the board advanced four bidders at or above $80 and notified eliminated parties" | `target` | `never_advanced` | "below $80 threshold for advancement" |
| Providence Party C/D/E/F | "the Transaction Committee proceeded with G&W and Party B because their offers were higher; the remaining bidders were told they were no longer involved" | `target` | `never_advanced` | "lower price than advancing parties" |
| Providence Party B (final stage) | "Party B asked to increase, would not, Board selected G&W" | `target` | `below_minimum` | "would not match superior offer" |
| Stec Company E/F | "Company F declined the management-presentation invitation because it was only interested in limited, select assets, then no further communications; Company E shortly thereafter indicated only interest in limited, select assets" | `bidder` | `scope_mismatch` | "limited-assets scope mismatch" |
| Stec Company D | "Company D said it would not be able to actively conduct diligence for more than two weeks and was disengaging from the process" | `bidder` | `null` | "diligence-timeline incompatible" |
| Penford 2007/2009 industry parties | "discussions did not result in offers" (no agency narrated) | `unknown` | `null` | "discussions did not result in offers" |
| Petsmart Buyer Group / Bidder 2 / Bidder 3 (winner-track) | (these stay or become winner-side; not drop rows) | — | — | — |

**Note on Stec E/F**: Per §4.1's "verb subject" rule, this is `bidder`-initiated, with `drop_reason_class = "scope_mismatch"` carrying the target-scope-driven reason as a queryable structured value. This *disagrees* with Alex's prior `DropTarget` coding (which used target-initiator) but is consistent with filings-as-ground-truth (CLAUDE.md) while preserving the scope-mismatch signal in structured form. Worth flagging to Alex for confirmation.

### Final-round informal-ness fixtures

| Deal | Filing language | `final_round_announcement` | `final_round_informal` | `final_round_extension` |
|---|---|---|---|---|
| Imprivata June 24 | "Barclays sent final bid process letters … requesting marked merger-agreement drafts by July 7 and final bids by July 8" | `true` | `false` | `false` |
| Imprivata July 8 | "on July 8, only Thoma Bravo submitted a bid" | `false` | `false` | `false` |
| Mac-Gray Aug 27 | "BofA Merrill Lynch sent letters … requesting revised written proposals by September 9" | `true` | `true` | `false` |
| Mac-Gray Sept 11 | "BofA Merrill Lynch instructed to request final indications by September 18" | `true` | `false` | `false` |
| Stec May 16 | "after the May 16 board meeting, BofA Merrill Lynch sent final-round process letters requesting a response by May 28" | `true` | `false` | `false` |
| Stec May 29 | "the board directed BofA Merrill Lynch to request best-and-final proposals by May 30" | `true` | `false` | `true` |
| Stec May 30 | "WDC reaffirmed $9.15 and Company D said it needed additional time" | `false` | `false` | `true` |

## 10. Open Austin items

These are surfaced from the audit for explicit decision; they are not blockers for the rest of the redesign.

### 10.1 `Auction Closed` for go-shop expiry (Zep)

Current §K1 defines `Auction Closed` as "target halts without an announced deadline." Zep's go-shop-expiry case had a contractually announced deadline (May 7, 2015), making it ambiguously fit. Options:

- **(a)** Tighten `Auction Closed` to its strict "no announced deadline" definition. Zep's go-shop expiry re-classifies as fold-into-`Executed`'s `additional_note` (no separate row). Recommended for cleanliness.
- **(b)** Broaden `Auction Closed` to include go-shop expirations with no topping bids. Keeps Zep's row but blurs the code's filing-language signature.

**Default if Austin doesn't decide:** option (a). Tightening preserves the cleaner semantic.

### 10.2 `drop_reason_class = "below_minimum"` semantic boundary

Providence Party B (final-stage loser to G&W's higher offer) was `needs-Austin` in adjudication. Under the new schema:

- "Would not increase to match superior offer" → `target` + `below_minimum` (the target's "minimum" was effectively "G&W's price").
- "Below stated reserve / minimum" → `target` + `below_minimum`.

Both treated as the same class. Minimal-judgment rule. Confirm with Austin.

## 11. Migration plan

Per CLAUDE.md "no backward compatibility":

1. Update `rules/events.md` §C1 to the new 18-code vocabulary; remove the 13 eliminated codes.
2. Update `rules/events.md` §I1 to define `Drop` consolidation + the two new structured columns; add the conversion fixtures from §9.
3. Update `rules/events.md` §K1 to define `Final Round` + 3 booleans; remove the 9-code matrix.
4. Update `rules/bidders.md` §F1 to remove `"mixed"` value; remove §F1 row 5 (consortium-mixed case).
5. Update `rules/schema.md` §R1 to add 8 new columns, drop `joint_bidder_members`, update `bidder_type` enum.
6. Update `rules/invariants.md`:
   - §P-D5: simplify check from `bid_note startswith "Drop"` to `bid_note == "Drop"` (with separate §P-S1 backstop for `DropSilent`).
   - §P-G2: range-locks-to-informal still applies; informal/formal fallback now reads `final_round_informal` from the paired or fallback round row.
   - §P-R6: `bidder_type ∈ {"s", "f", null}` only.
   - New: §P-D7 `drop_reason_class_inconsistent` (soft); §P-D8 `formal_round_status_inconsistent` (soft); §P-G3 `final_round_missing_non_announcement_pair` (hard); §P-R7 `ca_type_ambiguous` (hard, promoted from soft).
7. Update `prompts/extract.md`:
   - Replace the 31-code vocabulary reference with 18.
   - Add the conversion fixtures from §9 as in-prompt examples.
   - Add the boundary-tightening rules from §7 and §8 with their misuse-trap citations.
   - Add the `invited_to_formal_round` and `submitted_formal_bid` extraction guidance.
8. Regenerate all 9 reference deal extractions under the new schema (`output/extractions/*.json`).
9. Regenerate `reference/alex/*.json` from `scripts/build_reference.py` under the new schema (the §Q overrides may need refresh — separate work item).
10. Re-run `scoring/diff.py --all-reference --no-write` to verify diffs are no worse than the prior baseline.
11. Re-run all 9 deals through the pipeline and confirm zero hard validator flags.

The 3-clean-run gate (CLAUDE.md exit criteria) resets at this change and must be re-met before target-deal extraction.

## 12. Validator implications

| Invariant | Change |
|---|---|
| §P-R3 (closed vocab) | Set updates from 31 to 18; reject merged codes if seen |
| §P-R6 (bidder_type) | Drop `"mixed"` from accepted set |
| §P-D5 (drop without prior engagement) | Single-string match `bid_note == "Drop"` (cleaner than prefix check) |
| §P-G2 (bid_type evidence) | Range-locks-to-informal unchanged; trigger fallback now reads `final_round_informal` from paired round, or from the most recent applicable final-round event when the non-announcement row is missing |
| §P-S3 (phase termination) | Set updates: `{Executed, Terminated, Auction Closed}` unchanged |
| New §P-D7 | `drop_reason_class_inconsistent` (soft) |
| New §P-D8 | `formal_round_status_inconsistent` (soft) |
| New §P-G3 | `final_round_missing_non_announcement_pair` (hard): "Final Round announcement has subsequent bids but no paired non-announcement Final Round row — check for missing row." |
| Promoted §P-R7 | `ca_type_ambiguous` from soft to hard |

## 13. Out of scope for this spec

- Auction classifier (`§Scope-1`) NDA-count semantics — unchanged.
- Date-mapping rules (`rules/dates.md` §B1–B5) — unchanged.
- Process-phase logic (`§L1`/`§L2`/`§P-L1`/`§P-L2`) — unchanged; mechanical and working.
- Composite consideration breakdown (`§H2`) — unchanged.
- Aggregate-dollar bids (`§H4`) — unchanged.
- Same-price reaffirmation rule (`§C5`) — unchanged.
- IB date anchoring (`§J1`) — unchanged.
- Cross-phase NDA continuity (`§M4`) — unchanged.
- Type-C rollover skip (`§M5`) — unchanged (already a skip rule, not a CA classification).

## 14. Risks

- **AI may resist the new `drop_reason_class` constraint.** The bidder-side null default requires the AI to *not* invent a reason class. In production the AI may default-fill; validator §P-D7 is a soft flag, so silent drift is possible. Consider promoting to hard if production runs show drift.
- **Final-round pairing rule depends on chronology being right.** If the AI emits a `Final Round` in the wrong process_phase or with a wrong date, the §G1 fallback breaks. The pairing rule assumes correct §A2/§A3 ordering, which `pipeline.finalize()` enforces deterministically.
- **Formal-stage status inference becomes the AI's judgment.** Currently the model can derive invitation and submission status from event combinations; making them explicit shifts the cognitive load to the extractor. Mitigate via the §P-D8 cross-check.
- **Stec E/F initiator disagreement with Alex.** The "verb subject" rule says `bidder`; Alex's reference says `target`. This is a deliberate departure — defensible per CLAUDE.md ground-truth rule but worth Alex's explicit confirmation.

## 15. Net change summary

| Metric | Before | After | Δ |
|---|---:|---:|---:|
| `bid_note` codes | 31 | 18 | −13 (−42%) |
| New structured columns | 0 | 8 | +8 |
| Dead schema fields | 2 (`mixed`, `joint_bidder_members`) | 0 | −2 |
| Drop subcodes | 6 | 2 (Drop, DropSilent) | −4 |
| Final-round matrix | 9 codes | 1 code (Final Round) + 3 booleans + Auction Closed separate | −7 codes, +3 booleans |
| Codes used in 0 deals | 3 | 0 | −3 |

The vocabulary contracts by 42%; the structured-column count goes up by 8 (+1 versus the prior design draft because one formal-stage column becomes two). The schema preserves all (B)-research signal while reducing what the AI must weigh per event from "pick from 31" to "pick from 18, then set 1–3 booleans."

---

**Next step:** apply migration plan from §11 — update `rules/*.md` and `prompts/extract.md`, regenerate the 9 reference extractions under the new schema, then reset the 3-clean-run gate.

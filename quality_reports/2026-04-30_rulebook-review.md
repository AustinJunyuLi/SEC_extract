# Rulebook Review — 2026-04-30

Three-agent thorough audit of `rules/*.md` against (a) internal consistency,
(b) prose-vs-validator alignment, and (c) past-run flag evidence.

**Scope:** `rules/schema.md`, `rules/events.md`, `rules/bidders.md`,
`rules/bids.md`, `rules/dates.md`, `rules/invariants.md`, plus
`pipeline/core.py` for code/doc alignment, plus the latest reference-deal
audit runs and `state/flags.jsonl` for evidence.

**Bottom line:** rule machinery is mostly self-consistent (27/27 validator
codes aligned with code), but two HIGH-severity bugs are actively breaking
production runs and several MEDIUM consistency gaps invite interpretation
variance. Total flag volume across 9 reference deals: **408** (9 hard, 207
soft, 192 info). Only **petsmart-inc** fails to clear soft-only — 8 hard
`bid_without_preceding_nda` + 1 `repair_loop_exhausted`.

---

## Convergent findings (flagged by ≥2 agents)

### 1. §L2 phase-boundary doctrine has three problems at once  [CRITICAL]

Three independent agents flagged this; together they form one large bug.

- **Internal:** §L2 rule 1 says "explicit `Terminated`/`Restarted` markers are
  authoritative." §P-L2 says "no `process_phase=0` rows within 180 days of
  any phase≥1 event" (hard). Markers cannot be authoritative if a
  subsequent calendar check overrules them.
- **Doc/code:** the 180-day threshold is the single most consequential
  numeric in stale-prior policy and **does not appear in §L1 or §L2 prose**.
  It lives only in `rules/invariants.md` and `pipeline/core.py`. A reader
  following the CLAUDE.md instruction "read this file and SKILL.md before
  changing extraction behavior" cannot learn the cutoff from the rules.
- **Evidence (zep instability):** zep run `908b9bcb` (12:58 UTC) emitted 35
  events with phase=1 covering 2014 and phase=2 covering 2015. zep run
  `44aaf0bb` (14:58 UTC) emitted 70 events with phase=null covering 2013–14
  and phase=1 covering 2015. **Same input, dramatically different
  interpretations.** Run-1 hit `stale_prior_too_recent` + repair-loop
  exhausted. Run-2 cleared by lumping everything into phase=null (which the
  validator silently coerces to phase 1 in some checks but not others —
  see §L2/null below).

**Impact:** zep cannot satisfy the 3-consecutive-unchanged-rulebook
stability gate while §L2 is ambiguous. This blocks the reference-set exit
gate.

**Fix sketch:**

1. Rewrite [rules/events.md §L2](rules/events.md#L778) step 3 with
   explicit precedence: (a) explicit `Terminated`/`Restarted` markers create
   phase boundaries regardless of calendar gap; (b) any event ≥180 days
   before the earliest phase≥1 event with no upstream `Restarted` linkage is
   phase 0; (c) `process_phase` MUST be a non-null integer in extractor
   output.
2. Move the 180-day threshold into §L1/§L2 prose so readers learn it from
   the rulebook.
3. Add a §P-L2 exemption for explicit-marker boundaries (or accept that the
   threshold and markers never need to compete because (a) makes markers
   take precedence at extraction time).
4. Forbid `process_phase=null` at the schema level (§P-R0 hard
   `process_phase_invalid_type`); canonicalize null → 1 nowhere.

### 2. `process_phase = null` semantics is doubly inconsistent  [HIGH]

[rules/schema.md:226-229](rules/schema.md#L226) says null is interpreted as
phase 1 by the validator. But the actual validator paths split:

- §P-L2 checks the literal value (only fires on `process_phase = 0` rows).
- §P-S2 (auction count) filters on `process_phase >= 1` — null doesn't match.
- §P-S3, §P-D5, §P-D6 exemption #2 also check the literal.

So an extractor emitting `null` vs `1` produces **different §P-S2
auction-classification outcomes**. zep run-2's 64 phase=null events are a
live example of this leak.

**Fix:** disallow `null` in the schema (force int output) OR canonicalize
`null → 1` exactly once at the top of `pipeline.core.validate()` before any
check runs. Pick one and apply it uniformly.

### 3. petsmart §P-D6 buyer-group atomization is a real rule gap  [CRITICAL — blocking]

petsmart-inc latest run (`64b57266`) emits 8 hard `bid_without_preceding_nda`
flags for bidder_09–bidder_14 (aliased "another bidder", "Bidder 2",
"Bidder 3", "Lower Indication Party 1-3"). Filing narrates 15 anonymous
"Financial Buyer N" NDAs, then later names some at the bid stage. For named
constituents (BC Partners, La Caisse, GIC, StepStone — rows 22–25), the
model linked separate NDAs successfully. For the 6 unnamed-then-named
bidders, the model never used `unnamed_nda_promotion` to link them.

**Why it failed:** `unnamed_nda_promotion` is documented only inside
[rules/invariants.md:266-302](rules/invariants.md#L266) §P-D6 with **no
worked example anywhere** in `rules/bidders.md` or `prompts/extract.md`.
The model has no concrete pattern to follow.

Worse: repair turn 1 left 1 hard flag; repair turn 2 made it WORSE (1 → 8
hard). The model regresses under repair pressure on this case.

**Fix options:**

A. Add a worked example to [rules/bidders.md §E3/§E5](rules/bidders.md)
   showing the placeholder→named resolution, mirror in
   [prompts/extract.md](prompts/extract.md). Lowest-risk; targets compliance.

B. Loosen §P-D6 to accept exact-count cohort matches by `bidder_type` +
   phase: if N anonymous placeholders sit in the same phase with no other
   resolution, treat them as covering up to N later same-phase bids by the
   same `bidder_type`. Higher-risk; changes validator semantics.

Option A is recommended first; if compliance still fails, escalate to B.

### 4. §P-S1 / `missing_nda_dropsilent` over-fires on unnamed cohorts  [MEDIUM, high volume]

§I1 documents the cohort-level Drop pattern: a single `Drop` /
`drop_group_count_unspecified` row can cover an exact-count placeholder
cohort. But §P-S1 has no awareness of cohort coverage — it fires once per
NDA row that lacks an individually-tied follow-up. Result: 40 soft
`missing_nda_dropsilent` flags across 2 deals (petsmart 15, providence 25)
that are all **per-design noise**.

**Fix:** make §P-S1 honor cohorts: if a phase has N placeholder NDA rows
sharing an alias family AND a later cohort-coverage row exists, suppress
per-row fires. Reduces flag floor by ~10% and makes real divergences
easier to spot.

### 5. Advisor-row `bidder_type = null` validator is promised but missing  [MEDIUM]

[rules/bids.md:591-593](rules/bids.md#L591) §M3: "Advisor rows
(`role != \"bidder\"`) have `bidder_type = null`. **A validator check
catches violations.**" There is no such validator. §P-R6 only checks the
scalar value when present.

**Fix:** add a §P-R6 sub-check: `role != "bidder"` ⇒ `bidder_type IS NULL`,
hard. Or drop the prose promise.

---

## Other HIGH severity issues (single-agent flags, still real)

### A. §A3 same-date ordering rank table is incomplete  [HIGH, structural]

Two problems in [rules/dates.md:310](rules/dates.md#L310):

1. **`ConsortiumCA` is missing entirely.** Prose at
   [rules/events.md:377](rules/events.md#L377) says "rank 5 by §A3" but
   the §A3 table only lists `NDA` at rank 5. When `ConsortiumCA` and `NDA`
   co-occur same-date, ordering is undefined → run-to-run instability.
2. **`Bidder Sale` and `Activist Sale` sit at rank 1** (process
   announcements), which puts them before `NDA` (rank 5) and `Bidder
   Interest` (rank 4) on same-date clusters — contradicting natural
   lifecycle and breaking §P-G3 pairing logic.

**Fix:** add `ConsortiumCA` to rank 5 (or its own rank); move
`Bidder Sale`/`Activist Sale` to rank 4 alongside `Bidder Interest`.

### B. §G1 informal triggers vs §G2 evidence requirement clash  [HIGH]

[rules/bids.md §G1](rules/bids.md#L170) lists explicit trigger phrases
("non-binding indication of interest", etc.) the extractor uses to
classify. [rules/invariants.md §P-G2](rules/invariants.md#L436) says
"§G1 trigger tables are *classification guidance for the extractor*, NOT
a validator satisfier path: a trigger phrase alone does not pass §P-G2."

Result: every clean trigger-driven classification needs a redundant
inference note that just restates the trigger phrase, OR the model gets
hard-flagged. The model will either bloat every note (Run A) or get
flagged (Run B) — interpretation variance.

**Fix:** accept "verbatim §G1 trigger quoted in source_quote" as a §P-G2
satisfier OR drop the trigger tables from §G1.

### C. §C4 pre-NDA informal bid: missing inference-note mandate  [HIGH]

[rules/bids.md §C4](rules/bids.md#L11) says emit a Bid row with
`bid_type=informal` "by construction" when a price indication precedes the
bidder's NDA. But §C4 doesn't specify the §G2-required `bid_type_inference_note`.
Every §C4 bid will fail §P-G2 unless the extractor remembers to write a
note. The rule should mandate exact note content.

**Fix:** §C4 should specify the required note (e.g., `"pre-NDA price
indication; informal by construction per §C4"`).

---

## MEDIUM severity issues (selected)

| # | Issue | File | Effect |
|---|---|---|---|
| M1 | Press Release `subject="sale"` vs `Target Sale Public` overlap | [events.md:23](rules/events.md#L23) | Same-day ambiguity; runs may emit one row vs two. |
| M2 | `Acquirer` "lead sponsor in primary position" undefined | [schema.md:203](rules/schema.md#L203) | "Primary position" is vague when filing alphabetizes. |
| M3 | Single-bound bid (`>=$45`) has no §G1 classification rule | [bids.md:709](rules/bids.md#L709) | Silently defaults to null + hard flag. |
| M4 | `bidder_type` ambiguity default conflicts (`"f"` vs `null`) | [bidders.md:255](rules/bidders.md#L255) | §F1 row 7 says default `f`; schema allows `null`. Two valid behaviors. |
| M5 | §K1 same-day final-round pairing vs §A3 ordering | [events.md:692](rules/events.md#L692) | §K1 pairing search may report missing pairs that §A3 placed structurally. |
| M6 | §C5 Case 3 reaffirmation has no Bid row | [bids.md:122](rules/bids.md#L122) | Downstream "winner's bid" analysis ambiguous; conflicts with §H5. |
| M7 | `consideration_components` default vs `all_cash` divergence | [bids.md:287](rules/bids.md#L287) | Earlier bid silently `["cash"]` while signed has CVR; biases informal-bid economics. |
| M8 | §P-D8 has no dedicated §-section; rules scattered | [invariants.md:488](rules/invariants.md#L488) | 20 soft flag fires; rule editing is unsafe because dependencies aren't enumerated. |

---

## LOW severity (cosmetic / mild)

- `Q1 <Year>` and `mid-Q1 <Year>` collide (both → `Year-02-15`); `early
  Q<n>` uses day 15 but `early <Month>` uses day 05. Inconsistent grain.
- §I1 `DropSilent` source_quote re-cites NDA — technically violates §R3
  "quote supports the specific event"; needs explicit carve-out.
- §L1 says "every prior-process event always included" but §M1 skip rules
  override; mild absolute-vs-conditional clash.
- "Usually paired with a standstill" in §C1 — hedge language without a
  classifier consequence.

---

## Code/doc alignment is clean

Agent B verified all 27 §P-XX codes in `rules/invariants.md` are
implemented in `pipeline/core.py`, and vice versa — no divergence.
Numbering gaps (no §P-D4, §P-S6, §P-H1..H4, §P-G1, §P-L3) are intentional
per the no-backward-compat doctrine. **No code-vs-doc bugs** in this audit.

The only minor weaknesses are five §P-XX codes whose prose anchors are
diffuse rather than dedicated sections:

| Code | Issue |
|---|---|
| §P-R0 | No §-section anchor anywhere; lives only in invariants.md. |
| §P-D8 | Cited cross-reference is wrong; rules sit in field-list bullets. |
| §P-L2 | 180-day threshold not in prose at all. |
| §P-S4 | "Executed in max phase" buried at events.md:822 without enumeration. |
| §P-G2 | §G1 triggers vs §G2 satisfier path conflict (see HIGH B above). |

---

## Top 5 recommended actions, ranked by impact

| Rank | Action | Files | Unblocks | Risk |
|---|---|---|---|---|
| 1 | Rewrite §L2 step 3 with explicit precedence; forbid `process_phase=null`; move 180-day threshold into prose | events.md, schema.md, invariants.md, core.py | zep stability gate | Medium — resets stability clock, but it's already broken |
| 2 | Add worked `unnamed_nda_promotion` example to §E3/§E5 + extract.md | bidders.md, prompts/extract.md | petsmart §P-D6 | Low — pure compliance nudge, no validator change |
| 3 | Make §P-S1 cohort-aware: suppress per-row fires when cohort coverage exists | invariants.md, core.py | 40 soft-flag noise | Low — reduces noise, doesn't change semantics |
| 4 | Add §A3 rank for `ConsortiumCA`; move `Bidder Sale`/`Activist Sale` to rank 4 | dates.md | Same-date ordering instability | Medium — affects all deals' canonical row order |
| 5 | Add §P-R6 advisor sub-check (`role != "bidder"` ⇒ `bidder_type IS NULL`) | invariants.md, core.py | Promise→reality alignment | Low — codifies existing prose |

**Stability-clock implication:** any rulebook change resets the
3-consecutive-unchanged-runs clock per CLAUDE.md. Doing #1 + #2 + #3
together as one batch is much cheaper than doing them serially. #4 and #5
can ride along.

---

## Open questions for Austin

1. **Approve action #1 (§L2 doctrine fix)?** This is the highest-leverage
   change. It will reset the stability clock but the clock is already
   stuck at 1 run because of zep's 35-vs-70-event swings — there is no
   coherent stability state to lose.

2. **Approve action #2 (`unnamed_nda_promotion` worked example)?** This
   is the lowest-risk fix; pure prose addition. Likely fixes petsmart's 8
   hard flags without changing validator semantics.

3. **Approve action #3 (§P-S1 cohort awareness)?** Reduces flag noise by
   ~10%, makes real divergences easier to spot.

4. Anything from the MEDIUM list that's bothering you in particular?
   Several are quick fixes; happy to bundle them.

Once Austin signals which actions to take, the orchestrator workflow runs:
spec → plan → implement → verify → re-extract reference batch → confirm
fixes → mark stability clock as restarted.

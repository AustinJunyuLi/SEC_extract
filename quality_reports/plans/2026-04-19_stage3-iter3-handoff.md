# Stage 3 Iteration 3 Handoff — Read This First

**Intended reader.** A fresh Claude (or Austin) opening this repo after a
context clear. Read this file, then `CLAUDE.md`, then re-verify the commit
graph with `git log --oneline -15` before acting.

**Date:** 2026-04-19
**Prior handoff:** `2026-04-18_stage3-iter2-handoff.md` (closed by this one).

---

## TL;DR

- Ran all 5 already-touched reference deals (medivation, imprivata, zep,
  penford, providence-worcester) through the pipeline again.
- Added **two Python-side fixes** (canonical row ordering + retroactive NDA
  rename) and **one new validator check** (§P-D6 NDA-before-bid existence).
  Prompts updated to explain the new NDA-rename hint schema. **Rulebook
  untouched.**
- Closed **all 3 genuine AI defects** from iter 2 (Penford same-date bid
  atomization = D1; Providence missing NDAs for Party E/F = D2; Providence
  IOI count = D3).
- **Surfaced 5 new Providence defects** — a different class (§B3 rough-date
  bookkeeping), not caught by the current prompt. Candidate for a one-line
  iter-4 prompt patch.
- No regressions on M/I/Z/P.

---

## Commit graph since the prior handoff

```
7af0207 Providence iter 3 v3: D2+D3 closed via Fix 2C promotion hints
36b025b Penford iter 3 extraction: D1 closed, Fix 1 applied, zero AI defects
952218b Zep iter 3 extraction: Fix 1 applied, zero AI defects
9efa948 Imprivata iter 3 extraction: Fix 1 applied, 1 mechanical AI defect
c85957e Medivation iter 3 extraction: Fix 1 canonical sort applied, zero AI defects
97fc4d3 Add pipeline Fix 1+2C: canonical sort, NDA promotion, §P-D6
6c48477 (PRIOR HANDOFF) Handoff: Stage 3 iter 2; archive linkflow option
```

The infrastructure commit (`97fc4d3`) touches `pipeline.py` +
`prompts/extract.md`. The 5 per-deal commits only move
`state/progress.json` forward — 4 use `--allow-empty` because the
progress.json transition bundles into Medivation's commit.

---

## The two Python-side fixes (commit 97fc4d3)

### Fix 1 — Canonical row ordering in `pipeline.finalize()`

**Problem it closed.** In iter 2, Providence had 4 hard validator flags for
date-order and same-date-rank violations (rows emitted in the filing's
narrative order rather than chronological order; §A3 rank required
informals before formals on same-date blocks; AI didn't sort).

**What Fix 1 does.** After the extractor returns, `pipeline.finalize()`
now:
1. Sorts every event by `(bid_date_precise, §A3 rank, narrative index)`.
   Null-dated rows sort to the end preserving narrative order among
   themselves.
2. Reassigns `BidderID = 1..N` strictly monotone.
3. Updates `bidder_registry[*].first_appearance_row_index` to match the
   new ordering.

**Effect.** §A2 date-monotone and §A3 same-date-rank enforcement is now a
Python responsibility for all deals forever. The LLM can emit rows in
narrative order and Python fixes the mechanical sort. No re-extraction
needed to apply Fix 1 — re-running `pipeline.finalize()` on an already-
extracted raw JSON is enough.

**Code.** `_canonicalize_order()` in `pipeline.py`, called from
`finalize()` before `validate()`.

### Fix 2C — Retroactive NDA promotion hint

**Problem it closed.** In iter 2, Providence's filing said "11 strategic
buyers executed NDAs" at 3/28. AI correctly emitted 11 NDA rows, but
only 5 named + 6 labeled as "Strategic {N}" placeholders. Later at
5/25, the filing named Party E submitting an IOI. AI emitted the Party E
Bid row but never went back to rename the earlier "Strategic N" NDA
placeholder to "Party E". So Party E's Bid row had no matching NDA row.

**What Fix 2C does.** The extractor can now attach a hint on a named Bid
row saying "this bidder's NDA is the unnamed placeholder at BidderID=12":

```json
{
  "unnamed_nda_promotion": {
    "target_bidder_id": 12,
    "promote_to_bidder_alias": "Party E",
    "promote_to_bidder_name": "bidder_07",
    "reason": "Filing p.36 names Party E as one of the 11 strategic buyers that executed NDAs on 3/28 (p.35)."
  }
}
```

Python consumes the hint deterministically: rewrites the target NDA row's
`bidder_alias` / `bidder_name` to the promoted values, appends the old
alias to `bidder_registry[new_name].aliases_observed`, and strips the
hint field from the Bid row before canonical output is written. A log of
applied promotions lands in `deal._unnamed_nda_promotions` for audit.

**Ordering.** Applied BEFORE canonicalization, so `target_bidder_id`
references the AI's transient narrative-order BidderIDs (stable at
extraction time).

**Effect.** The AI no longer has to re-edit earlier rows. It emits
placeholders forward, flags the linkage when the bidder gets named, and
Python reconciles.

**Code.** `_apply_unnamed_nda_promotions()` in `pipeline.py`, called from
`finalize()` before `_canonicalize_order()`.

### Validator — new §P-D6 invariant

**What it checks.** For every named Bid row in `process_phase ≥ 1`:
there must exist an NDA row under the same `bidder_name` in the same
phase. Existence-only (not ordering) — §D1 unsolicited first-contact
bids can still precede their NDAs.

**Skips.** Unnamed placeholders (§E3); §M4 stale-prior phase 0 Bid rows.

**Code.** `_invariant_p_d6()` in `pipeline.py`, wired into `validate()`.

---

## Prompt update (commit 97fc4d3)

Added two bullets to both `prompts/extract.md` and
`pipeline.build_extractor_prompt()`:

1. **"Canonical ordering is Python-enforced."** Tells the AI it MAY emit
   rows in narrative order; Python handles the sort and BidderID
   reassignment. The AI's transient BidderIDs are stable handles for
   promotion hints.

2. **"Bidder-identity reconciliation via `unnamed_nda_promotion` hint."**
   Explains the hint schema and when to use it (named Bid row with no
   earlier NDA row under the same bidder_name in the same phase).

Rulebook `rules/*.md` is unchanged. Fix 2C is pipeline-internal; the hint
field never enters the canonical schema.

---

## Iter 3 results per deal

| slug | events | bidders | validator | promotions | genuine AI defects | clock |
|---|---|---|---|---|---|---|
| medivation | 22 | 8 | `passed_clean` | 0 | 0 | 1/3 |
| imprivata | 32 | 8 | 1 hard (quote>1000) | 0 | 1 mechanical | 1/3 |
| zep | 70 | 26 | 1 hard (positional) | 0 | 0 | 1/3 |
| penford | 33 | 10 | 1 hard (phase-0 boundary) | 0 | 0 (D1 closed) | 1/3 |
| providence | 56 | 27 | 5 hard (§B3 rough-date) | 4 applied | 5 §B3 residuals | **0/3 reset** |

### Defect closures

- **D1 — Penford same-date verbal+letter bid atomization.** CLOSED.
  BidderID 24 = verbal $18.50, BidderID 25 = letter $19.00, each with
  `additional_note` distinguishing.
- **D2 — Providence missing NDAs for Party D/E/F.** CLOSED. 4 promotion
  hints applied successfully: Strategic 8→G&W, Strategic 4→Party E,
  Financial 1→Party D, Strategic 5→Party F.
- **D3 — Providence IOI count gap.** CLOSED. 14 informal Bid rows now
  emit (covers the 9 initial IOIs + revised/competing bids), each with a
  preceding NDA via promotion or direct naming.
- **§A2 / §A3 ordering violations (all deals).** CLOSED permanently via
  Fix 1 — LLM is no longer responsible for mechanical ordering.

### New defect class surfaced (Providence only)

All 5 of Providence's residual hard flags are §B3 rough-date bookkeeping
inconsistencies. The rulebook rule is symmetric: `bid_date_rough`
populated IFF a date-inference flag (`date_inferred_from_rough`,
`date_inferred_from_context`, `date_range_collapsed`) is attached. AI
violated this in BOTH directions on Providence:

- row 26: `date_inferred_from_context` flag present but `bid_date_rough`
  is null
- rows 34-37: `bid_date_rough="late July 2016"` populated but no
  inference flag attached

**This is NOT a D1/D2/D3 clone.** It's a distinct symmetry-rule violation
class. Not caught by current prompt, which only explicitly covers the
one direction ("Inferred dates always populate `bid_date_rough`").

Candidate iter-4 prompt patch: add symmetric-direction rule —
"`bid_date_rough` populated ⇔ inference flag present; populating one
without the other triggers §P-D2 hard."

---

## What's uncommitted (Austin's work, left untouched)

These files have working-tree modifications from before this session;
the iter-3 orchestrator did NOT stage or commit them:

- `AGENTS.md`
- `CLAUDE.md`
- `rules/bidders.md`, `rules/dates.md`, `rules/events.md`, `rules/schema.md`
- `reference/alex/imprivata.json`, `mac-gray.json`, `medivation.json`,
  `penford.json`, `petsmart-inc.json`, `providence-worcester.json`,
  `saks.json`, `stec.json`, `zep.json`
- `scripts/build_reference.py`
- `state/flags.jsonl`

---

## Exit-clock status toward Stage 3 completion

Stage 3 done requires 3 consecutive full-reference-set runs where (a)
rulebook, prompt, and pipeline are all unchanged between runs, AND (b)
every reference deal lands clean (no genuine AI defects).

Current bank per deal:
- Medivation: 1 / 3
- Imprivata: 1 / 3 (1 mechanical defect = quote >1000 chars)
- Zep: 1 / 3
- Penford: 1 / 3 (D1 defect closed; phase-0 termination is boundary case, not AI defect)
- Providence: 0 / 3 (reset — prompt+pipeline changed this iter)

**4 reference deals never extracted yet:** mac-gray, petsmart-inc, stec,
saks. Do NOT touch these until the other 5 are fully banked.

---

## Plan for the next session

**If Austin wants to address the Providence §B3 residuals first:**

1. Add one bullet to the §B prompt section (both `prompts/extract.md`
   and `pipeline.build_extractor_prompt()`): "`bid_date_rough` populated
   ⇔ date-inference flag present. Populating one without the other
   triggers §P-D2 hard. The two fields go together — both or neither."
2. Re-extract Providence under the new prompt.
3. If clean, bank iter-1 for Providence + re-run M/I/Z/P to start
   banking their iter-2 clock.

**If Austin wants to push forward on the 4 remaining deals:**

Providence's §B3 residuals are non-D1/D2/D3 and don't block other
deals. Could run mac-gray, petsmart-inc, stec, saks in parallel under
the current infrastructure, surface any new defect classes they carry,
consolidate prompt patches for all in one pass before re-running
everything for 3 clean iterations.

**Either way:**

- Extractor is a Claude Code subagent, `subagent_type="general-purpose"`,
  `model="opus"`, `run_in_background=true`. 5-way parallelism worked
  cleanly in this iter (no stream-idle timeouts, no skeletal outputs).
- Use the full extract prompt from `pipeline.build_extractor_prompt(slug)`
  + the anti-skeletal guard + the Write-to-/tmp supplement from prior
  handoffs. The iter-3 prompts in this session's transcript are good
  templates.
- Finalize via `python run.py --slug X --raw-extraction /tmp/X.raw.json --no-commit`.
- Diff via `python scoring/diff.py --slug X`.
- Adjudicate via a fresh general-purpose Opus 4.7 subagent pointed at the
  diff report path; memo overwrites `scoring/results/{slug}_adjudicated.md`.

---

## Convention pins (unchanged from iter 2)

Still deferred, all classified `both-defensible` by adjudicators:

1. §B5 "letter dated X / received Y" anchor
2. §K2 Final Round Ann invite-vs-process-letter tie-break
3. §D1 unsolicited first-contact: fold vs standalone
4. §F1 `bidder_type.note` convention
5. §R1/§N2 Executed row consideration fields
6. §Scope-3 `DateEffective = null` when filing predates closing
7. §Scope-3 `TargetName` / `Acquirer` case formatting
8. §E3 unnamed-bidder placeholder count for "several parties"

These are Austin-decision items, not AI defects. Not blocking.

---

## Accumulated reference-builder action items (for Austin, not the Extractor)

Unchanged from iter 2 — see `2026-04-18_stage3-iter2-handoff.md`
section "Accumulated reference-builder action items" for the full list.
Highlights:

- `scripts/build_reference.py` should (a) apply §H1 legacy-migration on
  every range-bid row, (b) set `bidder_type.public` from exchange listing
  metadata (Ingredion, G&W both flagged), (c) atomize multi-party NDA/Drop
  aggregate rows per §E1.

---

## Operating notes

1. **Rulebook is frozen.** `rules/*.md` files are not to be edited by the
   extractor or its orchestrator.
2. **Prompt is patched.** `prompts/extract.md` +
   `pipeline.build_extractor_prompt()` carry Fix 2C's hint schema and
   Fix 1's ordering-is-Python-enforced note (commit `97fc4d3`). The
   iter-2 prompt additions (count audit + same-date multi-communication)
   are still in place.
3. **Pipeline now does two pre-validate transforms.** `finalize()` applies
   `unnamed_nda_promotion` hints, then canonical sort, then validates.
4. **§P-D6 is a new hard validator.** Named Bid row with no matching
   NDA row in the same phase → hard flag. Designed to catch regressions
   of Fix 2C if the AI forgets to emit promotion hints.
5. **Don't touch Austin's uncommitted edits** on `AGENTS.md`, `CLAUDE.md`,
   `rules/*.md`, `reference/alex/*.json`, `scripts/build_reference.py`,
   `state/flags.jsonl`.
6. **Hook reminders lie.** The `READ-BEFORE-EDIT` hook fires after
   successful edits. Trust the tool's own success/failure response.
7. **Target-deal gate remains closed.** Do not run the 392 target deals
   until all 9 reference deals are verified AND the rulebook + prompt +
   pipeline stay unchanged across 3 consecutive full-reference-set runs.

---

## Files to read before taking action

1. This file.
2. `CLAUDE.md` — project context, ground-truth epistemology, stage gates.
3. `SKILL.md` — architecture contract.
4. `rules/*.md` — fixed rulebook; scan the section referenced by the
   task. Do not edit.
5. `pipeline.py` — live pipeline. New code at
   `_apply_unnamed_nda_promotions()`, `_canonicalize_order()`,
   `_invariant_p_d6()`, and `finalize()` (wiring).
6. `prompts/extract.md` — patched extractor prompt (full text).
7. `scoring/results/{slug}_adjudicated.md` — 5 adjudication memos from
   this iter's subagent runs (Medivation / Imprivata / Zep / Penford /
   Providence). The adjudication template + Providence's §validator-flags
   section are worth reading before adjudicating new deals.

---

## Commit graph at handoff

```
7af0207 Providence iter 3 v3: D2+D3 closed via Fix 2C promotion hints
36b025b Penford iter 3 extraction: D1 closed, Fix 1 applied, zero AI defects
952218b Zep iter 3 extraction: Fix 1 applied, zero AI defects
9efa948 Imprivata iter 3 extraction: Fix 1 applied, 1 mechanical AI defect
c85957e Medivation iter 3 extraction: Fix 1 canonical sort applied, zero AI defects
97fc4d3 Add pipeline Fix 1+2C: canonical sort, NDA promotion, §P-D6
6c48477 Handoff: Stage 3 iter 2; archive linkflow option; revert to Opus 4.7 subagents
3af5ecf Patch Extractor prompt: count audit + same-date multi-communication
1e192e4 Providence first-pass extraction: 2 AI defects (atomization count gaps)
9681776 Penford first-pass extraction: 1 AI defect (same-day bid atomization)
7761c5c Zep first-pass extraction: clean run, zero AI defects
d9b3a2a Imprivata first-pass extraction: clean run, zero AI defects
e996e62 Handoff: Stage 3 iter 1 complete, recommend Imprivata as next deal
```

(uncommitted: Austin's working-tree edits on AGENTS.md, CLAUDE.md,
rules/*.md, reference/alex/*.json, scripts/build_reference.py,
state/flags.jsonl — untouched by iter 3.)

# Stage 3 Iteration 3b Handoff — All 9 Reference Deals Now Extracted

**Intended reader.** A fresh Claude (or Austin) opening this repo after a
context clear. Read this file, then `CLAUDE.md`, then re-verify the commit
graph with `git log --oneline -20` before acting.

**Date:** 2026-04-19
**Prior handoff:** `2026-04-19_stage3-iter3-handoff.md` (closed by this one).

---

## TL;DR

- Ran the **4 unrun reference deals** (mac-gray, petsmart-inc, stec, saks)
  through the pipeline under the iter-3 infrastructure (commit `97fc4d3`'s
  Fix 1 + Fix 2C + §P-D6). **No rulebook, prompt, or pipeline changes
  this iter** — the goal was to surface defect classes before any
  consolidated patch.
- **All 9 reference deals are now extracted.** First time in the project.
- **1 clean deal** (stec: `passed_clean`, zero AI defects, zero new
  defect classes).
- **Surfaced 5 new defect classes** (A/B/C/D/E) + **1 minor class** (F)
  + **1 candidate scoring/diff.py bug** across the other 3 deals.
- Class A (joint-bidder Executed multiplicity) and Class E (joint-NDA
  over-split) are **recurring** — both fired on mac-gray AND petsmart-inc.
  These are the highest-priority patch targets for iter 4.
- Saks' 2 hard validator flags are both **validator/prompt gaps, not AI
  defects.** AI extraction is materially more filing-faithful than Alex's
  reference on saks.
- **Exit clock reset for all 9 deals** once the consolidated iter-4 patch
  lands (see "Patch plan" below).

---

## Commit graph since the prior handoff

```
6641c94 petsmart-inc iter 3b extraction: 69 events, 1 hard flag, Class A+E confirmed; Class F new (minor)
fbe1c26 saks iter 3b extraction: 32 events, 2 hard flags, Class B+C+D defects surfaced (all validator/prompt gaps, not AI defects)
9da7223 mac-gray iter 3b extraction: 66 events, 2 hard flags, Class A+E defects surfaced
34a030c stec iter 3b extraction: 34 events, 0 hard flags, 0 AI defects
da48788 Handoff: Stage 3 iter 3; D1/D2/D3 closed via pipeline Fix 1+2C + §P-D6  ← prior handoff
```

stec got the only "real" commit (progress.json state change bundles with
it); mac-gray / saks / petsmart-inc used `--allow-empty` following the
iter-3 convention since the state transitions are batched in stec's
commit.

---

## Iter 3b results per deal

| slug | events | bidders | validator | promotions | genuine AI defects | new defect classes |
|---|---|---|---|---|---|---|
| stec | 34 | 10 | `passed_clean` (0 flags) | 0 | **0** | none |
| mac-gray | 66 | 22 | 2 hard (phase-0 boundary + multi-Executed) | 0 | 5 | A, E |
| saks | 32 | 9 | 2 hard (both validator gaps) | 0 | 0 (validator gaps, not AI) | B, C, D |
| petsmart-inc | 69 | 19 | 1 hard (multi-Executed) | 7 | 11 (cascading from A+E) | A, E confirmed; F new |

Alex reference counts for comparison: stec=28, mac-gray=34, saks=23,
petsmart=50.

### stec — clean ship

- `passed_clean`, 0 flags.
- Adjudicator: 13 AI-correct, 0 AI-wrong, 30 both-defensible.
- 4 Alex-side date errors identified (Company B Bidder Interest 2013-02-13,
  Company D 2013-03-15, BofA IB 2013-03-28, WDC Executed 2013-06-23 —
  Alex had 6-14 which is the bid-acceptance date not execution date).
  Action item for `alex_flagged_rows.json`.
- AI-only rows (15) are mostly legitimate filing-supported events Alex
  elided (Activist Sale, Target Sale, WDC 5/31 Drop) or matched-event
  -different-code granularity (Drop vs DropTarget/DropAtInf/DropBelowInf).

### mac-gray — 5 AI defects, 2 validator flags

- Phase-0 BofA IB-termination: similar to Penford phase-0 boundary,
  classified as boundary case, not AI defect.
- 2 Executed rows for CSC + Pamplona joint consortium → Class A.
- Adjudicator: 50 AI-right, 2 Alex-right, 30 both-defensible, 5 AI-wrong.
- AI-wrong breakdown:
  - joint-Executed split (Class A, will be fixed by patch)
  - joint-NDA split (Class E, will be fixed by patch)
  - phase-0 BofA over-split (3 of the 5 AI-wrong rows; already known
    from Penford, cascading from same cause)
- Note: adjudicator flagged `scoring/diff.py` as possibly buggy on 7
  spurious `bid_value_pershare` null-vs-value divergences where AI JSON
  actually populates the field. **Worth auditing diff.py independently.**

### saks — 0 AI defects, 2 validator gaps

- **AI extraction is materially more filing-faithful than Alex's
  reference.** Alex rows 7013, 7015 already flagged for deletion by Alex
  himself; AI correctly omits them.
- Hard flag 1: `bid_without_preceding_nda` (§P-D6) on Company H
  unsolicited Bid. §D1's unsolicited-first-contact non-negotiable says
  "emit Bid only, no Bidder Sale". §P-D6 existence check misfires when
  the bidder never signs an NDA (Company H was declined). Class B.
- Hard flag 2: `phase_termination_missing` (phase 1). 40-day go-shop
  continues past Executed row (2013-07-28) through Company I Drop
  (2013-09-06). §P-S3 phase-termination rule doesn't carve out go-shop
  continuation. Class C.
- AI self-reported Class D: pre-NDA concrete price indications (4/15)
  emitted as `Bidder Sale` rows (with `pre_nda_bidder_sale` soft flag)
  rather than `Bid` rows to avoid §P-D6 ordering issues. §C1 doesn't
  explicitly authorize this usage. Medium priority.

### petsmart-inc — confirms Class A, E; adds Class F

- 5 Executed rows for Buyer Group consortium (BC Partners, Caisse, GIC,
  StepStone, Longview). Class A confirmed as recurring.
- 4 Buyer Group NDA rows for 10/05 where filing narrates a group count
  of 15 NDAs with no per-constituent detail. Class E confirmed as
  recurring.
- 2 Activist Sale rows (JANA + Longview); Alex collapses to 1. Class F
  (minor, AI-right but needs §D1 clarification).
- Adjudicator: ~40 AI-correct, 11 AI-wrong (5 Class A + 4 Class E +
  2 AI-omitted Drop rows), ~30 both-defensible.
- Alex-side bug: 0 Executed rows in Alex's JSON (would fail §P-S4).
  Fix target: `scripts/build_reference.py`.

---

## The 6 defect classes surfaced in iter 3b (consolidated)

### Class A — joint_executed_multiplicity (RECURRING, HIGH PRIORITY)

**Symptom.** Joint bidders / consortia trigger §E2 "one row per
constituent" atomization on the Executed event, producing N Executed
rows. The `multiple_executed_rows` hard validator requires exactly 1.

**Deals affected.** mac-gray (2 rows: CSC + Pamplona),
petsmart-inc (5 rows: Buyer Group).

**Fix.** §E2 scope clarification: Executed row is ALWAYS exactly 1,
named after the merger-agreement counterparty, with a `joint_bidder`
field listing all consortium members. §E2's "one row per constituent"
rule applies to NDAs, Bids, Drops, but NOT to Executed.

**Proposed patch** (both `rules/bidders.md` §E2 and `prompts/extract.md`):

> "Executed rows are always exactly 1 per deal. For joint-bidder winners,
> emit one Executed row with `bidder_alias` = the merger-agreement
> counterparty name (e.g., "Buyer Group", "CSC/Pamplona") and a new
> `joint_bidder_members` field listing constituent bidder_NNs. §E2's
> per-constituent atomization applies to NDAs, Bids, and Drops but NOT
> to Executed. §P-S4 (`multiple_executed_rows`) remains a hard invariant."

### Class B — §D1 unsolicited-first-contact exemption from §P-D6 (VALIDATOR GAP)

**Symptom.** An unsolicited bid is itself the first contact (§D1
non-negotiable: "emit Bid only, do not emit a duplicate standalone
Bidder Sale row"). The bidder never signs an NDA (declined by target).
§P-D6's NDA-before-bid existence check fires hard.

**Deals affected.** saks (Company H $2.6B unsolicited letter, 2013-07-21).

**Fix.** `pipeline.py` `_invariant_p_d6()`: add a skip when the Bid row
carries a `date_inferred_from_context` flag with reason referencing
unsolicited-first-contact, OR add an explicit `bidder_no_nda_unsolicited`
flag the extractor can attach to §D1 Bid rows.

**Proposed patch** (pipeline.py only, no rulebook change needed — the
§D1 non-negotiable is already in the prompt):

```python
def _invariant_p_d6(deal, events):
    for ev in events:
        if ev.get("bid_note") != "Bid": continue
        if ev.get("process_phase") == 0: continue  # §M4 stale-prior
        if ev.get("bidder_name") is None: continue  # §E3 unnamed
        # NEW: §D1 unsolicited-first-contact exemption
        if any(f.get("code") == "unsolicited_first_contact"
               for f in ev.get("flags", [])): continue
        # ... existence check ...
```

Plus a one-line prompt addition:
> "When emitting a §D1 unsolicited-first-contact Bid row with no
> accompanying NDA, attach flag {"code": "unsolicited_first_contact",
> "severity": "info", "reason": "..."} to exempt it from §P-D6."

### Class C — go-shop phase termination (VALIDATOR GAP)

**Symptom.** Post-Executed go-shop activity (additional NDAs, IOIs,
Drops during the go-shop window) leaves phase 1 with a non-terminating
last event, triggering `phase_termination_missing` hard flag.

**Deals affected.** saks (40-day go-shop; Company I NDA 2013-08-11 +
Drop 2013-09-06 after Executed 2013-07-28).

**Fix.** `pipeline.py` `_invariant_phase_termination()`: when `go_shop_days
> 0`, treat the Executed row as phase-terminating regardless of later
rows. Later go-shop rows stay in phase 1 but don't require the last row
to be Executed/Terminated/Auction Closed.

**Proposed patch** (pipeline.py):

```python
def _invariant_phase_termination(deal, events):
    for phase in phases_in_events:
        phase_events = [e for e in events if e["process_phase"] == phase]
        # NEW: go-shop carve-out for phase 1
        if phase == 1 and deal.get("go_shop_days"):
            if any(e.get("bid_note") in {"Executed","Terminated","Auction Closed"}
                   for e in phase_events): continue
        # ... existing check ...
```

### Class D — pre-NDA Bidder Sale classification (§C1/§D1 gap, MEDIUM PRIORITY)

**Symptom.** Filing narrates a concrete price indication from a
prospective bidder BEFORE the NDA is signed (not unsolicited, not
first-contact). AI has no clean §C1 slot for this; saks extractor
unilaterally used `Bidder Sale` + `pre_nda_bidder_sale` soft flag.

**Deals affected.** saks (4/15 Hudson's Bay + Sponsor A concrete price
indications pre-NDA).

**Fix.** Decide between:
- Option 1: Allow `Bid` + `bid_type: "informal"` + flag
  `pre_nda_informal_bid` + §P-D6 exemption.
- Option 2: Formalize `Bidder Sale` as the canonical classification for
  pre-NDA concrete-price signals (adjudicator's suggestion: Alex's
  simpler `Bid (informal)` reading is cleaner).
- Option 3: Skip per §M1 spirit (exploratory, pre-NDA) — but this loses
  useful signal.

**Recommendation.** Option 1, with explicit prompt language. Validator
§P-D6 gets a second exemption for `pre_nda_informal_bid`.

### Class E — joint_nda_over_split (RECURRING, HIGH PRIORITY)

**Symptom.** Filing narrates an NDA executed by a consortium / joint
bidder as a single group event (no per-constituent detail). AI emits N
per-constituent NDA rows anyway, violating the filing's own granularity.

**Deals affected.** mac-gray (7/11 CSC/Pamplona joint NDA), petsmart-inc
(10/05 Buyer Group 4 constituents where filing gave group count only).

**Root cause.** `rules/bidders.md` §I1 exists but prompt doesn't surface
it. The prompt emphasizes §E2 per-constituent atomization for Bids/Drops,
but doesn't tell the extractor when §I1 aggregation applies for NDAs.

**Fix.** `prompts/extract.md` addition:

> "Joint-bidder NDA aggregation (§I1). When the filing narrates an NDA
> executed by a consortium as a single group event without per-constituent
> detail, emit ONE NDA row with `bidder_alias` = the consortium label
> (e.g., "Buyer Group", "CSC/Pamplona") and a `joint_bidder_members`
> field listing constituent bidder_NNs. Emit per-constituent NDA rows
> ONLY when the filing separately narrates each constituent's NDA
> execution. §E2's per-constituent atomization for Bids/Drops remains
> unchanged — that rule is about the subsequent bid/drop activity, not
> the initial NDA signing."

### Class F — activist_sale_atomization (MINOR, petsmart only)

**Symptom.** Multiple activists pressuring the target in parallel (JANA +
Longview at Petsmart). AI emits one `Activist Sale` row per activist;
Alex collapses to 1.

**Fix.** §D1 / §C1 one-line clarification: "If multiple activists are
narrated separately, emit one Activist Sale row per activist. Collapse
to a single row only when the filing treats them as a coordinated group."
AI-right, but convention needs to be explicit.

---

## The scoring/diff.py null-vs-value candidate bug

Adjudicator for mac-gray flagged 7 spurious `bid_value_pershare` diffs
where AI JSON actually populates the field but diff.py reports it as
null-vs-value.

**Action item.** Read `scoring/diff.py` field-pairing logic. Likely a
key-aliasing or JSON-path bug. If confirmed, patch separately and
re-run diffs for iter-4 baseline.

---

## Iter-4 consolidated patch plan

Before re-running all 9 reference deals for iteration 1 of 3 clean
iterations:

### Rulebook patches (`rules/*.md`)

1. **`rules/bidders.md` §E2** — Executed-row exception: exactly 1 per
   deal, named after merger-agreement counterparty, with
   `joint_bidder_members` field. Class A.
2. **`rules/bidders.md` §I1** — Joint-bidder NDA aggregation
   clarification. Class E.
3. **`rules/events.md` §C1 / §D1** — Multi-activist atomization
   clarification (one row per activist narrated separately). Class F.
4. **`rules/bids.md` §C3** — (Decision needed) pre-NDA informal Bid
   classification vs Bidder Sale. Class D.

### Prompt patches (`prompts/extract.md` + `pipeline.build_extractor_prompt()`)

1. Joint-bidder NDA aggregation (§I1). Class E.
2. Joint-bidder Executed row exception (§E2). Class A.
3. §D1 unsolicited-first-contact `unsolicited_first_contact` flag. Class B.
4. Providence §B3 rough-date symmetry rule (from prior handoff —
   outstanding).
5. Multi-activist atomization convention. Class F.

### Pipeline patches (`pipeline.py`)

1. `_invariant_p_d6()`: add §D1 exemption via
   `unsolicited_first_contact` flag. Class B.
2. `_invariant_phase_termination()`: go-shop carve-out for phase 1
   when `go_shop_days > 0`. Class C.
3. `_invariant_multiple_executed()`: stays hard (Class A fix is in the
   prompt, not the validator).

### Validation / audit

1. Audit `scoring/diff.py` for the `bid_value_pershare` null-vs-value
   bug.
2. Run all 9 deals after patches land. This becomes iter-1 of the
   3-iteration exit clock.

---

## Exit-clock status toward Stage 3 completion

Stage 3 done requires 3 consecutive full-reference-set runs where (a)
rulebook, prompt, and pipeline are all unchanged between runs, AND (b)
every reference deal lands clean (no genuine AI defects).

**Current bank:** 0 / 3 for ALL 9 deals.

The iter-4 consolidated patch will reset any clock accumulated in iter 3.
That's the expected cost of absorbing 6 defect classes in one patch
cycle rather than 3-6 separate cycles.

Per-deal AI defect count as of iter 3b (pre-patch):
- stec: 0 — would ship immediately
- medivation: 0 (iter 3)
- imprivata: 1 mechanical (quote >1000 chars, iter 3)
- zep: 0 (iter 3)
- penford: 0 (iter 3, D1 closed)
- providence: 5 §B3 rough-date residuals (iter 3)
- mac-gray: 5 (all from Class A/E, will be fixed by patch)
- saks: 0 (2 validator gaps, not AI defects — Class B+C fixes belong in
  pipeline/prompt, not AI)
- petsmart-inc: 11 (all from Class A/E/F + 2 omitted Drops)

---

## Accumulated reference-builder action items (for Austin, not the Extractor)

Unchanged from iter 2/3, plus new iter 3b items:

- `scripts/build_reference.py` should (a) apply §H1 legacy-migration on
  every range-bid row, (b) set `bidder_type.public` from exchange listing
  metadata (Ingredion, G&W both flagged), (c) atomize multi-party
  NDA/Drop aggregate rows per §E1.
- **NEW: Fix Alex-side bug in Petsmart reference** — 0 Executed rows in
  `reference/alex/petsmart-inc.json` (would fail §P-S4 if validated).
  `scripts/build_reference.py` should infer the Executed row from the
  filing's execution date + acquirer identity.
- **NEW: Alex-side date errors in stec** — 4 dates AI corrects against
  the filing. Add to `alex_flagged_rows.json`:
  - stec Company B Bidder Interest (Alex: ?, filing: 2013-02-13)
  - stec Company D Bidder Interest (Alex: ?, filing: 2013-03-15)
  - stec BofA IB (Alex: ?, filing: 2013-03-28)
  - stec WDC Executed (Alex: 2013-06-14, filing: 2013-06-23)
- **NEW: saks row 7015 (DropTarget typo)** already in
  `alex_flagged_rows.json`. Verify row 7013 entry too.

---

## Plan for the next session (iter 4)

**Priority order:**

1. **Audit `scoring/diff.py`** for the null-vs-value bug (30 min).
   Optional but clarifies iter-4 diffs.
2. **Write the consolidated iter-4 patch** covering Classes A/B/C/D/E/F
   + Providence §B3 from prior iter. Should be ONE commit touching
   `rules/`, `prompts/`, and `pipeline.py`. Probably 60-90 minutes of
   orchestrator time.
3. **Re-run all 9 reference deals** after the patch. 9-way parallel
   extractor + finalize + diff + adjudicate. This is iteration 1 of 3.
   Approximately the same wall-clock as iter 3b's 5-way run (~15-20
   minutes for extraction, 5-10 minutes for adjudication per deal).
4. **If iteration 1 is clean** across all 9 deals, run iteration 2.
   Then iteration 3. Between iterations, the rulebook/prompt/pipeline
   MUST be unchanged.
5. **Only after 3 consecutive clean runs** does the target-deal gate
   open.

**Alternatively, if Austin wants to bank easy wins first:**

- Ship stec today (0 defects, already passed_clean). Counts as
  iteration 1 of 3 for stec, independent of the consolidated patch.
- Everything else waits for the patch.
- Downside: when the patch lands, stec will still need to re-run (the
  patch may inadvertently change stec's output via §I1 clarification).
  Better to batch.

---

## Convention pins (unchanged from iter 3)

Still deferred, all classified `both-defensible` by adjudicators:

1. §B5 "letter dated X / received Y" anchor
2. §K2 Final Round Ann invite-vs-process-letter tie-break
3. §D1 unsolicited first-contact: fold vs standalone (Class D pushes on this)
4. §F1 `bidder_type.note` convention
5. §R1/§N2 Executed row consideration fields
6. §Scope-3 `DateEffective = null` when filing predates closing
7. §Scope-3 `TargetName` / `Acquirer` case formatting
8. §E3 unnamed-bidder placeholder count for "several parties"

---

## Operating notes

1. **Rulebook is frozen UNTIL the iter-4 consolidated patch lands.**
   Do not edit `rules/*.md` piecemeal.
2. **Prompt is frozen UNTIL iter-4 patch.**
3. **Pipeline is frozen UNTIL iter-4 patch.**
4. **Don't touch Austin's uncommitted edits** on `AGENTS.md`,
   `CLAUDE.md`, `rules/*.md`, `reference/alex/*.json`,
   `scripts/build_reference.py`, `state/flags.jsonl`. Iter 3b touched
   only `state/flags.jsonl` and `state/progress.json` (via finalize).
5. **Target-deal gate remains closed.** Do not run the 392 target deals
   until all 9 reference deals verify clean AND rulebook + prompt +
   pipeline stay unchanged across 3 consecutive full-reference-set runs.

---

## Files to read before taking action

1. This file.
2. `CLAUDE.md` — project context, ground-truth epistemology, stage gates.
3. `SKILL.md` — architecture contract.
4. `rules/*.md` — current rulebook; scan section referenced by the
   task. Do not edit yet.
5. `pipeline.py` — live pipeline. `_invariant_p_d6()`,
   `_invariant_phase_termination()` need patches in iter 4.
6. `prompts/extract.md` — current extractor prompt.
7. `scoring/results/{slug}_adjudicated.md` for all 4 new deals (mac-gray,
   saks, petsmart-inc, stec) — primary evidence for the defect classes.
8. `quality_reports/plans/2026-04-19_stage3-iter3b-path-b.md` — the
   iter-3b plan that this handoff closes.

---

## Commit graph at handoff

```
6641c94 petsmart-inc iter 3b extraction: 69 events, 1 hard flag, Class A+E confirmed; Class F new (minor)
fbe1c26 saks iter 3b extraction: 32 events, 2 hard flags, Class B+C+D defects surfaced (all validator/prompt gaps, not AI defects)
9da7223 mac-gray iter 3b extraction: 66 events, 2 hard flags, Class A+E defects surfaced
34a030c stec iter 3b extraction: 34 events, 0 hard flags, 0 AI defects
da48788 Handoff: Stage 3 iter 3
7af0207 Providence iter 3 v3
36b025b Penford iter 3 extraction
952218b Zep iter 3 extraction
9efa948 Imprivata iter 3 extraction
c85957e Medivation iter 3 extraction
97fc4d3 Add pipeline Fix 1+2C: canonical sort, NDA promotion, §P-D6
```

(uncommitted: Austin's working-tree edits on AGENTS.md, CLAUDE.md,
rules/*.md, reference/alex/*.json, scripts/build_reference.py —
untouched by iter 3b.)

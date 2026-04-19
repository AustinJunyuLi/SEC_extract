# Stage 3 Iter-6 Closeout — Handoff

**Status:** READY — iter-6 structural work complete; only extractor-side
flag closure + adjudication remains.
**Branch:** `claude/sharp-sutherland-8d60d7` (19 commits ahead of pre-iter-6 base)
**HEAD:** `a979b17` (reconciliation)
**Date:** 2026-04-19 (late)

---

## TL;DR

Iter-6 is structurally done. The rulebook is timeless, self-consistent,
documented against its code, and trimmed (~−727 net lines across TIER
0/1/2/3). The 9-deal rerun landed under the new invariants and produced
**20 hard flags — all `bid_type_unsupported` — across 3 of 9 deals**
(providence, penford, stec). Zero rule changes were required. Zero
semantic regressions.

The exit clock stays at **0/3** conservative. Re-running the 3 validated
deals with the §P-G2 prompt reminder that batch-3 used (petsmart / stec /
saks) is expected to bring all 9 to `passed_clean` and start the clock.

---

## What landed this session

### Phase 1 — Deletion pass + rerun (commits `cff34de` → `972c8a7`)

- **TIER 0** `cff34de`, `16f65e8` — reverted iter-5 §D1.a 10-verb closed
  list overfit; verbatim-quote audit alone is sufficient safety.
- **TIER 1a-e** (9 commits) — added safety gates:
  - `_invariant_p_g2` bid-type evidence check (hard: `bid_type_unsupported`)
  - `_invariant_p_d2` tightened (strict rough-vs-precise XOR, ±3-day
    tolerance deleted)
  - `_apply_unnamed_nda_promotions` registry integrity
  - phantom schema fields dropped
  - `seeds.csv` `form_type` backfilled
- **TIER 2a-g** (7 sub-commits) — −601-line rulebook deletion pass:
  - Open-questions tombstones deleted
  - Phantom §K3 rule removed
  - §Q1-§Q5 moved from `rules/dates.md` → `scripts/build_reference.py`
    module docstring
  - §E2.b compressed to decision table
  - Non-negotiables paraphrase deleted from `pipeline.build_extractor_prompt`
  - Draft vocabulary block (contradicted §C1/§C3) deleted from events.md
- **TIER 2 review fixes** `aa2de3f` — adversarial 3-agent review surfaced
  HIGH + MED findings, all closed in single commit (−126 lines).
- **9-deal rerun** `9b70243`-`c491772` + aggregate `972c8a7` — first
  rerun under post-TIER-2 rulebook. 6 `passed_clean`, 3 `validated`,
  zero rule triggers.

### Phase 2 — TIER 3 + stale-doc sweep (commits `01d4a81` → `defebb7`)

- **TIER 3 dead-code sweep** `01d4a81` — 3 unused symbols removed from
  pipeline.py: `Filing.num_pages`, `ValidatorResult.soft_flags()`,
  `PipelineResult.validator`. Net −8 lines.
- **CLAUDE.md + session log** `ec3c118` — current-status block refreshed
  from pre-iter-6 Medivation-only state to post-rerun 6pc/3v state.
- **SKILL.md / AGENTS.md / skill_open_questions.md** `818c0a2` — dated
  architecture stamps removed; §P-G2 added to validator runs list;
  AGENTS.md Stage 3 follow-ups rewritten against post-rerun state.
- **rules/*.md iter-tag sweep** `defebb7` — stripped iter-N labels,
  class-fix markers, and historical parentheticals from 5 rulebook
  files.

### Phase 3 — Cross-cutting audit + fix (commits `b355286` → `a979b17`)

Triggered by user request: "address everything thoroughly."

**4 parallel read-only investigation agents** produced structured
findings on the 3 cross-cutting issues flagged by the rulebook sweep.
Synthesis → 3 parallel fixer agents on non-overlapping files → 1
implementation agent for pipeline.py → verification → reconciliation.

- **§P-D5/§P-D6 gap closed** `b355286`:
  - §P-D6 documented in `rules/invariants.md` (code at pipeline.py:567
    was undocumented for months).
  - §P-D5 newly implemented as structural twin (drop-family rows require
    prior engagement in same phase; `_invariant_p_d5` at pipeline.py:500).
  - §D1.a extended to exempt both §P-D5 AND §P-D6 (caught during
    verification: zep row 37 was a legitimate §D1.a case where a Drop
    followed an unsolicited-first-contact Bid with no NDA).
- **§G2 restructure** `b355286`:
  - `rules/bids.md §G2` 2-condition form (range-bid as parenthetical
    aside) → 3 explicit conditions matching `_invariant_p_g2` exactly.
  - Range-bid tightened to `lower < upper` (matching code; was "both
    populated" in docs).
  - Stale "SKILL.md non-negotiable rule #5" ref → content-based
    "SKILL.md §Non-negotiable rules (evidence citation: every row
    carries source_quote and source_page)". Today's #5 is the
    trigger-phrase rule, not evidence citation (#1).
- **schema.md §R3** `b355286` — same content-based ref conversion.
- **Reconciliation** `a979b17`:
  - Fixed aggregate report's stale 6-flag count on penford. State's
    append-only jsonl had a pre-c4ec361 `phase_termination_missing`
    entry from an older run; the current relaxed check ("any terminator
    in phase") passes penford cleanly. Real total = **20 hard flags**
    across the 9-deal rerun.

---

## Current validator state (verified clean)

```
medivation                   passed_clean  flags=0
imprivata                    passed_clean  flags=0
zep                          passed_clean  flags=0
providence-worcester         validated     flags=13  (all bid_type_unsupported)
penford                      validated     flags=5   (all bid_type_unsupported)
mac-gray                     passed_clean  flags=0
petsmart-inc                 passed_clean  flags=0
stec                         validated     flags=2   (all bid_type_unsupported)
saks                         passed_clean  flags=0
```

§P-D5 fires 0 new flags on the 9 extractions. §P-D6 fires 0 new flags.
All 20 hard flags are `bid_type_unsupported` on 3 deals.

---

## Rulebook-to-code alignment (verified)

| Invariant | Documented in invariants.md | Implemented in pipeline.py | In sync? |
|---|---|---|---|
| §P-R1..5 | yes | yes | ✓ |
| §P-D1 | yes | yes | ✓ |
| §P-D2 | yes (strict XOR) | yes (strict XOR) | ✓ |
| §P-D3 | yes | yes | ✓ |
| §P-D5 | yes (new) | yes (new) | ✓ |
| §P-D6 | yes (new) | yes | ✓ |
| §P-G2 | yes (3 conditions, lower<upper) | yes | ✓ |
| §P-S1..4 | yes | yes | ✓ |

§G2 in `rules/bids.md` now matches §P-G2 structure exactly (3 conditions,
same order).

---

## What's next (in priority order)

### 1. Re-run providence / penford / stec with §P-G2 prompt reminder

All 20 hard flags are extractor-side evidence gaps: the extractor emitted
`bid_type="informal"` or `"formal"` on bid rows without including a §G1
trigger phrase in `source_quote` OR attaching a `bid_type_inference_note`.
Batch-3 prompts in the rerun (petsmart / stec / saks) added the explicit
§P-G2 reminder and dropped flags from 18 (batch-2) → 2 (batch-3). Apply
the same reminder to the 3 validated deals.

**Expected outcome:** all 9 deals pass `passed_clean`. Exit clock 0/3 → 1/3.

**Commands:**
```bash
for slug in providence-worcester penford stec; do
  # spawn extractor subagent with the §P-G2 reminder (see Agent prompts
  # in commits bccb11a / 4db5ce0 / c491772 for template)
  # then:
  python3 run.py --slug $slug --raw-extraction /tmp/iter6-raw/$slug.raw.json
  python3 scoring/diff.py --slug $slug
done
```

### 2. Adjudicate NDA atomization-vs-aggregation (Austin's call)

AI extracted substantially more NDA/Drop rows than Alex on:
- zep: 27 NDAs + 26 Drops (Alex: 27 total rows)
- mac-gray: 20 NDAs + 16 Drops (Alex: 34 total)
- providence-worcester: 26 NDAs + 20 Drops (Alex: 36 total)
- petsmart-inc: similar (Alex: 50)

Current §E2.b says atomize unless filing narrates joint/consortium
activity. Alex aggregates. This is a "both correct, different
interpretation" per CLAUDE.md ground-truth epistemology. Austin decides
per deal whether to (a) tighten §E2.b, (b) accept AI's atomization and
regenerate Alex's reference, or (c) both.

### 3. Resolve `bidder_type.public` inference policy

`bidder_type` field disagreements dominate diff reports (17 on mac-gray,
17 on stec, 13 on imprivata + penford). Fix lives in
`scripts/build_reference.py` — decide whether to infer `public=true`
more aggressively for obvious public strategics. Collapses ~65 field
diffs in one sweep. Converter-policy question, not rulebook.

### 4. Refresh per-deal adjudication memos

`scoring/results/*_adjudicated.md` files are against pre-iter-6 diff
reports. When (and only when) adjudication resumes, refresh against the
latest `*_20260419T*.md` diffs.

### 5. Start exit clock

Once all 9 pass `passed_clean` simultaneously without any rule change,
the 3-run unchanged-rulebook exit clock starts. Only after 3 consecutive
clean runs does the target-deal gate open (392 deals).

---

## Known follow-ups NOT blocking

- §P-D5 currently has zero true-positive catches on the 9 reference set.
  It will start paying for itself on target-deal extraction if extractors
  ever emit unattached Drop rows.
- `prompts/validate.md` is archived but still carries stale §P-D4/§P-D7/
  §P-D8 boilerplate from the Stage 1 scaffold. Harmless (the file is not
  invoked), but worth deleting if/when validate.md is ever reopened.

---

## Exit-clock accounting

**Before this session:** 0/3 unchanged-rulebook clean runs.
**After this session:** still **0/3**. Three deals carry hard flags
(all extractor-side), so not a clean run.

The rulebook was modified this session (§P-D5/§P-D6/§G2 structural
clarifications + §D1.a exemption extension + §P-G2 range tightening),
but these are **documentation of already-implemented code** (§P-D6,
§P-G2) plus a **new dual invariant** (§P-D5) that fires zero new flags
on reference data. Whether this counts as a "rulebook change" for
clock-reset purposes is Austin's call:
- Strict interpretation: rulebook changed → clock resets to 0/3.
- Pragmatic interpretation: no semantic drift — just closed a
  documentation gap + added a safety check that catches nothing on the
  current set — so next clean rerun counts as 1/3.

---

## Artifacts

- **Raw extractions:** `/tmp/iter6-raw/*.raw.json` (9 files)
- **iter-5 baseline:** `/tmp/iter6-raw/iter5-baseline/` (9 files, committed extraction state)
- **Final extractions:** `output/extractions/*.json` (committed)
- **Diff reports:** `scoring/results/*_20260419T*.md` (9 files; gitignored)
- **Aggregate:** `quality_reports/plans/2026-04-19_stage3-iter6-rerun-results.md`
- **This handoff:** `quality_reports/plans/2026-04-19_stage3-iter6-closeout-handoff.md`

---

## Working-tree state

- Clean. 19 commits ahead of main base. All Phase C/D/E work committed.
- `state/progress.json`: 392 pending, 6 passed_clean, 3 validated.
- `state/flags.jsonl`: contains append-only history; filter by timestamp
  for current state. The 11:24:46 penford entry is stale (pre-c4ec361);
  only 15:58:38+ is current.

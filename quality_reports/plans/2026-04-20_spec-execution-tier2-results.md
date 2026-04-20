# 2026-04-20 Spec Execution — Tier 2 Results

## Scope

Tier 2 execution landed in these commits:

- `1ccdf3f` — T2-A align §P-D5 docs with same-phase witness semantics
- `ba09059` — T2-B align §P-S3 docs with phase-level terminator check
- `3407aad` — T2-C document `BidderID` as event-sequence row index
- `6b981c0` — T2-D add phase-boundary invariants for restart / stale-prior gaps
- `60fa5a5` — T2-E enforce bidder-registry alias consistency
- `1d5e5fc` — T2-F add soft bid-revision ordering check
- `a41a8d5` — T2-G reject null `bid_note`
- `ff8b290` — T2-H clarify Adjudicator as orchestrator-owned workflow
- `e415fa4` — T2-I make dry-run use the same pre-validation transforms

Reference-set rerun method:

1. Reuse the post-Tier-1 raw extractor outputs in `/tmp/spec-tier1-raw/{slug}.raw.json`.
2. Finalize each reference deal via `python3 run.py --slug {slug} --raw-extraction /tmp/spec-tier1-raw/{slug}.raw.json`.
3. Regenerate reference diffs via `python3 scoring/diff.py --all-reference`.

Exit-clock note:

- This rerun is a Tier 2 baseline only.
- It does **not** count as `1/3` toward the exit clock because Tier 3 still includes rulebook / prompt edits (`T3-E`, `T3-F`) that would reset the clock if landed afterward.

## Status Summary

All 9 reference deals finalized with **zero hard flags**.

Aggregate combined flags across the rerun:

- `hard=0`
- `soft=173`
- `info=206`
- `flag_count=379`

Per-deal status:

| Slug | Status | Hard | Soft | Info | Flag Count | Per-deal Commit |
|---|---:|---:|---:|---:|---:|---|
| `medivation` | `passed` | 0 | 18 | 3 | 21 | `3e652be` |
| `imprivata` | `passed` | 0 | 3 | 13 | 16 | `d3b0778` |
| `zep` | `passed` | 0 | 75 | 53 | 128 | `fd5c801` |
| `providence-worcester` | `passed` | 0 | 28 | 54 | 82 | `6036642` |
| `penford` | `passed` | 0 | 2 | 7 | 9 | `d14efc7` |
| `mac-gray` | `passed` | 0 | 32 | 4 | 36 | `ee03652` |
| `petsmart-inc` | `passed` | 0 | 0 | 40 | 40 | `0a8b694` |
| `stec` | `passed` | 0 | 10 | 9 | 19 | `52f823d` |
| `saks` | `passed` | 0 | 5 | 23 | 28 | `573fbe9` |

## Observations

- T2-D's new phase-boundary invariants did not introduce any hard failures on `zep` or `penford`; the live rulebook semantics remain `Terminated` closes phase 1 and `Restarted` opens phase 2.
- T2-E raised expected soft totals on deals where the extractor registry resolved names beyond the per-row alias vocabulary (`resolved_name_not_observed`), but no reference deal emitted the new hard alias-registry failures.
- T2-F and T2-G were quiet on the rerun set: no out-of-order bid revisions and no null `bid_note` rows survived finalization.
- Providence remains soft-only and still carries NDA-only rows without synthetic Drops, consistent with T1-D Path A.

## Diff Summary

Latest post-T2 diff reports:

| Slug | Matched | AI-only | Alex-only | Deal Disagreements | Field Disagreements | Latest Report |
|---|---:|---:|---:|---:|---:|---|
| `medivation` | 11 | 7 | 8 | 3 | 7 | `scoring/results/medivation_20260420T140601Z.json` |
| `imprivata` | 25 | 6 | 4 | 3 | 14 | `scoring/results/imprivata_20260420T140601Z.json` |
| `zep` | 14 | 58 | 13 | 3 | 7 | `scoring/results/zep_20260420T140601Z.json` |
| `providence-worcester` | 21 | 46 | 15 | 4 | 13 | `scoring/results/providence-worcester_20260420T140601Z.json` |
| `penford` | 17 | 12 | 8 | 3 | 15 | `scoring/results/penford_20260420T140601Z.json` |
| `mac-gray` | 27 | 18 | 7 | 3 | 25 | `scoring/results/mac-gray_20260420T140601Z.json` |
| `petsmart-inc` | 19 | 35 | 31 | 3 | 11 | `scoring/results/petsmart-inc_20260420T140601Z.json` |
| `stec` | 25 | 6 | 3 | 3 | 20 | `scoring/results/stec_20260420T140601Z.json` |
| `saks` | 17 | 9 | 6 | 3 | 7 | `scoring/results/saks_20260420T140601Z.json` |

## Next Step

Proceed to Tier 3. The next shared commit removes deprecated reference-data fields and vocabulary from `scripts/build_reference.py`, regenerates all 9 Alex reference JSONs, and keeps the live rulebook untouched until T3-E / T3-F land.

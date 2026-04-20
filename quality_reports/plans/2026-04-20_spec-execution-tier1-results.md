# 2026-04-20 Spec Execution — Tier 1 Results

## Scope

Tier 1 execution landed in these commits:

- `cbd09eb` — T1-A combined final-flag accounting + pytest fixture harness
- `e63a45f` — T1-B/T1-C §P-G2 directionality + range enforcement
- `ef57994` — T1-D Providence Path A rulebook rewrite
- `8ed0bef` — T1-E exact bidder-suffix normalization in `scoring/diff.py`
- `473852a` — T1-F fetcher 425 exclusion + unknown-form failure

Reference-set rerun method:

1. Spawn clean-context Extractor subagents for all 9 reference deals.
2. Write raw JSON to `/tmp/spec-tier1-raw/{slug}.raw.json`.
3. Finalize each deal via `python3 run.py --slug {slug} --raw-extraction /tmp/spec-tier1-raw/{slug}.raw.json`.
4. Regenerate reference diffs via `python3 scoring/diff.py --all-reference`.

Exit-clock note:

- This rerun is a Tier 1 diagnostic baseline only.
- It does **not** count as `1/3` toward the exit clock because Tier 2 and Tier 3 still include rulebook/prompt work that can reset the clock.

## Status Summary

All 9 reference deals finalized with **zero hard flags**.

Aggregate combined flags across the rerun:

- `hard=0`
- `soft=153`
- `info=206`
- `flag_count=359`

Per-deal status:

| Slug | Status | Hard | Soft | Info | Flag Count | Per-deal Commit |
|---|---:|---:|---:|---:|---:|---|
| `medivation` | `passed` | 0 | 12 | 3 | 15 | `8191966` |
| `imprivata` | `passed` | 0 | 2 | 13 | 15 | `8c58d21` |
| `zep` | `passed` | 0 | 75 | 53 | 128 | `bfb351e` |
| `providence-worcester` | `passed` | 0 | 22 | 54 | 76 | `73266f2` |
| `penford` | `passed` | 0 | 2 | 7 | 9 | `58fa567` |
| `mac-gray` | `passed` | 0 | 32 | 4 | 36 | `b012a77` |
| `petsmart-inc` | `passed` | 0 | 0 | 40 | 40 | `19b08f7` |
| `stec` | `passed` | 0 | 3 | 9 | 12 | `a8655e8` |
| `saks` | `passed` | 0 | 5 | 23 | 28 | `cafe6ac` |

## Observations

- T1-A is now visible in live state: every reference deal is `passed`, not `passed_clean`, because extractor-side soft/info annotations are counted in `state/progress.json`.
- T1-B/T1-C did not introduce any hard failures in the rerun outputs. The tightened §P-G2 validator is consistent with this rerun set.
- T1-D held on Providence: the deal remained soft-only with NDA-only rows preserved. The rerun produced `22` soft `nda_without_bid_or_drop` outcomes rather than the pre-spec `20`, but still no hard flags and no synthetic drops.
- The heaviest soft/info loads remain `zep`, `mac-gray`, and `providence-worcester`; these are expected review-heavy archetypes rather than Tier 1 regressions.

## Diff Summary

Latest post-T1 diff reports:

| Slug | Matched | AI-only | Alex-only | Deal Disagreements | Field Disagreements | Latest Report |
|---|---:|---:|---:|---:|---:|---|
| `medivation` | 11 | 7 | 8 | 3 | 7 | `scoring/results/medivation_20260420T122250Z.json` |
| `imprivata` | 25 | 6 | 4 | 3 | 14 | `scoring/results/imprivata_20260420T122250Z.json` |
| `zep` | 14 | 58 | 13 | 3 | 7 | `scoring/results/zep_20260420T122250Z.json` |
| `providence-worcester` | 21 | 46 | 15 | 4 | 13 | `scoring/results/providence-worcester_20260420T122250Z.json` |
| `penford` | 17 | 12 | 8 | 3 | 15 | `scoring/results/penford_20260420T122250Z.json` |
| `mac-gray` | 27 | 18 | 7 | 3 | 25 | `scoring/results/mac-gray_20260420T122250Z.json` |
| `petsmart-inc` | 19 | 35 | 31 | 3 | 11 | `scoring/results/petsmart-inc_20260420T122250Z.json` |
| `stec` | 25 | 6 | 3 | 3 | 20 | `scoring/results/stec_20260420T122250Z.json` |
| `saks` | 17 | 9 | 6 | 3 | 7 | `scoring/results/saks_20260420T122250Z.json` |

## Next Step

Proceed to Tier 2. The immediate goal is still rulebook↔validator contract reconciliation, not target-deal rollout.

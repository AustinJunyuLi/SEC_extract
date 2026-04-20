# 2026-04-20 Spec Execution — Tier 3 Results

## Scope

Tier 3 execution landed in these commits:

- `e3e9e04` — T3-A/T3-B/T3-D clean reference schema and deprecated vocabulary
- `89b2ca8` — T3-C surface bucket cardinality mismatches in diff reports
- `83a1f95` — T3-E formalize unnamed-party quantifier semantics
- `0e21fa1` — T3-F rewrite extractor prompt for live architecture
- `38c1490` — T3-G document append-only flag-log semantics

Reference-set rerun method:

1. Reuse the saved raw extractor outputs in `/tmp/spec-tier1-raw/{slug}.raw.json`.
2. Re-finalize each reference deal via `python3 run.py --slug {slug} --raw-extraction /tmp/spec-tier1-raw/{slug}.raw.json --no-commit`.
3. Regenerate reference diffs via `python3 scoring/diff.py --all-reference`.
4. Re-run the full local test suite via `python3 -m pytest tests` (`61 passed`).

Why the saved raw set was reused:

- Tier 3 changed reference JSONs, diff behavior, and documentation, but did
  not change validator logic or finalization semantics.
- A fresh extractor-subagent rerun was attempted first, but the subagents
  did not materialize any raw files in `/tmp/spec-tier3-raw/` in this
  environment. Reusing the saved raw set was sufficient to verify the
  deterministic Tier 3 surfaces and the current reference-set status.

Exit-clock note:

- `T3-E` and `T3-F` changed the live rulebook / prompt and therefore reset
  the clock.
- This rerun is therefore **clock run `1/3`**: post-Tier-3, zero hard flags,
  current reference JSONs, current diff logic, and current prompt/rulebook.

## Status Summary

All 9 reference deals finalized with **zero hard flags**.

Aggregate combined flags across the rerun:

- `hard=0`
- `soft=173`
- `info=206`
- `flag_count=379`

Per-deal status:

| Slug | Status | Hard | Soft | Info | Flag Count |
|---|---:|---:|---:|---:|---:|
| `medivation` | `passed` | 0 | 18 | 3 | 21 |
| `imprivata` | `passed` | 0 | 3 | 13 | 16 |
| `zep` | `passed` | 0 | 75 | 53 | 128 |
| `providence-worcester` | `passed` | 0 | 28 | 54 | 82 |
| `penford` | `passed` | 0 | 2 | 7 | 9 |
| `mac-gray` | `passed` | 0 | 32 | 4 | 36 |
| `petsmart-inc` | `passed` | 0 | 0 | 40 | 40 |
| `stec` | `passed` | 0 | 10 | 9 | 19 |
| `saks` | `passed` | 0 | 5 | 23 | 28 |

## Observations

- T3-A/T3-B/T3-D changed the reference side only. The live extraction
  outputs and combined flag totals remained unchanged on rerun.
- T3-C replaced arbitrary zip-pairing noise with explicit
  `cardinality_mismatch` entries. Across the 9 latest diff JSONs, total
  field-disagreement counts moved from `119` to `115`, while
  `cardinality_mismatch` counts moved from `0` to `24`.
- Providence now shows the intended NDA aggregation mismatch explicitly:
  one `cardinality_mismatch` entry with `27` AI NDA rows versus `2` Alex
  NDA rows, instead of a long AI-only tail.
- T3-E/T3-F/T3-G are documentation / prompt-alignment changes. The rerun
  confirms they did not create any hard validator regressions on the saved
  raw set.

## Diff Summary

Latest post-T3 diff reports:

| Slug | Matched | AI-only | Alex-only | Cardinality Mismatches | Deal Disagreements | Field Disagreements | Latest Report |
|---|---:|---:|---:|---:|---:|---:|---|
| `medivation` | 11 | 3 | 7 | 1 | 3 | 7 | `scoring/results/medivation_20260420T142356Z.json` |
| `imprivata` | 24 | 4 | 4 | 1 | 3 | 14 | `scoring/results/imprivata_20260420T142356Z.json` |
| `zep` | 12 | 7 | 8 | 3 | 3 | 7 | `scoring/results/zep_20260420T142356Z.json` |
| `providence-worcester` | 17 | 8 | 10 | 4 | 4 | 13 | `scoring/results/providence-worcester_20260420T142356Z.json` |
| `penford` | 14 | 4 | 3 | 4 | 3 | 15 | `scoring/results/penford_20260420T142356Z.json` |
| `mac-gray` | 26 | 2 | 6 | 1 | 3 | 25 | `scoring/results/mac-gray_20260420T142356Z.json` |
| `petsmart-inc` | 15 | 15 | 13 | 4 | 3 | 10 | `scoring/results/petsmart-inc_20260420T142356Z.json` |
| `stec` | 23 | 5 | 3 | 1 | 3 | 20 | `scoring/results/stec_20260420T142356Z.json` |
| `saks` | 10 | 0 | 1 | 5 | 3 | 4 | `scoring/results/saks_20260420T142356Z.json` |

## Next Step

Tier 1–3 implementation is complete. The remaining work is the spec §11
success-criteria sweep and handoff to Austin. Do **not** start the 392-deal
target rollout.
